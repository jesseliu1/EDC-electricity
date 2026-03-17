"""EDC API 客户端。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from ..schemas.common import CurvePoint


class EDCClientError(RuntimeError):
    """EDC API 调用失败。"""


class EDCClient:
    """面向 EDC AI 通信基座的最小客户端。"""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._token: str | None = None

    async def __aenter__(self) -> EDCClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """关闭底层 HTTP 客户端。"""
        await self._client.aclose()

    async def login(self) -> str:
        """登录并返回 token。"""
        response = await self._client.post(
            "/login",
            json={"username": self.username, "password": self.password},
        )
        payload = self._parse_json_response(response)
        self._ensure_success(payload, action="登录")

        token = payload.get("data") or payload.get("token")
        if not isinstance(token, str) or not token:
            raise EDCClientError("EDC 登录成功但未返回有效 token")

        self._token = token
        return token

    async def get_all_sensor_list(self) -> list[dict[str, Any]]:
        """获取设备与通道清单。"""
        payload = await self._systemcfg_request("getAllSensorList", "")
        decoded = self._decode_structured_payload(payload.get("data"))
        if not isinstance(decoded, list):
            raise EDCClientError("EDC 设备清单返回格式异常")
        return decoded

    async def get_local_datas(
        self,
        *,
        suid: str,
        cuid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[CurvePoint]:
        """获取指定通道历史曲线。"""
        payload = await self._systemcfg_request(
            "getLocalDatas",
            {
                "suid": suid,
                "cuid": cuid,
                "startTime": str(int(start_time.timestamp() * 1000)),
                "endTime": str(int(end_time.timestamp() * 1000)),
            },
        )
        return self._parse_curve_text(payload.get("data"))

    async def _systemcfg_request(self, request_name: str, value: object) -> dict[str, Any]:
        """调用 systemcfg 指令式接口。"""
        token = await self._ensure_token()
        response = await self._client.post(
            "/systemcfg",
            json={"request": request_name, "value": value, "token": token},
        )
        payload = self._parse_json_response(response)
        self._ensure_success(payload, action=request_name)
        return payload

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        return await self.login()

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise EDCClientError("EDC 返回了无法解析的 JSON") from exc

        if not isinstance(payload, dict):
            raise EDCClientError("EDC 返回格式异常")
        return payload

    def _ensure_success(self, payload: dict[str, Any], *, action: str) -> None:
        code = payload.get("code")
        if code not in {0, "0", None}:
            message = payload.get("msg") or payload.get("message") or payload.get("data") or "未知错误"
            raise EDCClientError(f"EDC {action}失败: {message}")

    def _decode_structured_payload(self, payload: object) -> object:
        """兼容 EDC 直接 JSON 或十进制字节串返回。"""
        if isinstance(payload, (list, dict)):
            return payload
        if not isinstance(payload, str):
            return payload

        stripped = payload.strip()
        if not stripped:
            return []

        if stripped.startswith("{") or stripped.startswith("["):
            return json.loads(stripped)

        if self._looks_like_decimal_bytes(stripped):
            decoded = bytes(int(part) for part in stripped.split(",")).decode("utf-8")
            return json.loads(decoded)

        raise EDCClientError("EDC 结构化数据格式无法识别")

    def _parse_curve_text(self, payload: object) -> list[CurvePoint]:
        if not isinstance(payload, str):
            return []

        points: list[CurvePoint] = []
        for row in payload.splitlines():
            line = row.strip()
            if not line:
                continue
            try:
                timestamp_raw, value_raw = line.split(",", 1)
                points.append(
                    CurvePoint(
                        timestamp=int(timestamp_raw.strip()),
                        value=float(value_raw.strip()),
                    )
                )
            except ValueError:
                continue
        return points

    def _looks_like_decimal_bytes(self, payload: str) -> bool:
        parts = payload.split(",")
        return bool(parts) and all(part.isdigit() for part in parts)
