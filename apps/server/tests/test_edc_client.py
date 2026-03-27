"""EDC 客户端错误包装测试。"""

from unittest.mock import AsyncMock

import httpx
import pytest

from src.services.edc_client import EDCClient, EDCClientError


@pytest.mark.asyncio
async def test_edc_client_login_wraps_connect_timeout() -> None:
    client = EDCClient(
        base_url="http://edc.test",
        username="tester",
        password="secret",
        timeout=0.1,
    )
    client._client.post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    try:
        with pytest.raises(EDCClientError) as exc_info:
            await client.login()
    finally:
        await client.aclose()

    message = str(exc_info.value)
    assert "EDC 登录超时" in message
    assert "ConnectTimeout" in message
