"""EDC API 客户端。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from time import perf_counter
from typing import Any

import httpx

from ..observability import log_event
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
        self._login_lock = asyncio.Lock()

    async def __aenter__(self) -> EDCClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """关闭底层 HTTP 客户端。"""
        await self._client.aclose()

    async def login(self) -> str:
        """登录并返回 token。"""
        if self._token:
            return self._token

        async with self._login_lock:
            if self._token:
                return self._token

            payload = await self._post_json(
                "/login",
                action="登录",
                payload={"username": self.username, "password": self.password},
            )
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
        started_at = perf_counter()
        payload = await self._systemcfg_request(
            "getLocalDatas",
            {
                "suid": suid,
                "cuid": cuid,
                "startTime": str(int(start_time.timestamp() * 1000)),
                "endTime": str(int(end_time.timestamp() * 1000)),
            },
        )
        points = self._parse_curve_text(payload.get("data"))
        log_event(
            "edc_get_local_datas",
            suid=suid,
            cuid=cuid,
            start_time=start_time,
            end_time=end_time,
            duration_ms=round((perf_counter() - started_at) * 1000, 1),
            points_count=len(points),
        )
        return points

    async def _systemcfg_request(self, request_name: str, value: object) -> dict[str, Any]:
        """调用 systemcfg 指令式接口。"""
        token = await self._ensure_token()
        payload = await self._post_json(
            "/systemcfg",
            action=request_name,
            payload={"request": request_name, "value": value, "token": token},
        )
        self._ensure_success(payload, action=request_name)
        return payload

    async def _ensure_token(self) -> str:
        return await self.login()

    async def _post_json(self, path: str, *, action: str, payload: object) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise EDCClientError(
                f"EDC {action}超时（{exc.__class__.__name__}），请检查当前环境到上游 EDC 的网络连通性"
            ) from exc
        except httpx.RequestError as exc:
            raise EDCClientError(
                f"EDC {action}请求失败（{exc.__class__.__name__}），请检查当前环境到上游 EDC 的网络连通性"
            ) from exc

        return self._parse_json_response(response)

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


_SHARED_CLIENTS: dict[tuple[str, str, str, float], EDCClient] = {}
_SHARED_CLIENTS_LOCK = asyncio.Lock()


async def get_shared_edc_client(
    *,
    base_url: str,
    username: str,
    password: str,
    timeout: float = 30.0,
) -> EDCClient:
    """返回按连接配置复用的共享 EDC client。"""
    client_key = (base_url.rstrip("/"), username, password, float(timeout))
    async with _SHARED_CLIENTS_LOCK:
        client = _SHARED_CLIENTS.get(client_key)
        if client is None:
            client = EDCClient(
                base_url=base_url,
                username=username,
                password=password,
                timeout=timeout,
            )
            _SHARED_CLIENTS[client_key] = client
        return client


async def close_shared_edc_clients() -> None:
    """关闭当前进程内缓存的共享 EDC clients。"""
    async with _SHARED_CLIENTS_LOCK:
        clients = list(_SHARED_CLIENTS.values())
        _SHARED_CLIENTS.clear()

    for client in clients:
        await client.aclose()
