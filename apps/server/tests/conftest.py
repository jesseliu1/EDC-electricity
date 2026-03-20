"""测试配置"""

import copy

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.baseline_definitions import _DEFINITION_STORE
from src.api.baselines import _BASELINE_STORE
from src.api.heats import (
    _HEAT_COMPARE_CACHE,
    _HEAT_STORE,
    _LIVE_HEAT_CACHE,
    _MOCK_HEAT_STREAM_STORE,
    _NEXT_MOCK_HEAT_INDEX,
    _seed_heats,
)
from src.api.settings import (
    _HOST_CHANNEL_CATALOG_CACHE,
    _HOST_CHANNEL_LAST_SYNC_AT,
    _HOST_CHANNEL_STORE,
    _SETTINGS_STORE,
)
from src.api.tasks import _TASK_STORE
from src.config import settings
from src.main import app


def _build_test_reference_heats() -> dict[str, dict]:
    """测试专用：构造一组非 mock 的参考炉次。"""
    seeded = copy.deepcopy(_seed_heats())
    for item in seeded.values():
        item["record_source"] = "historical_import"
        item["current_curve_source"] = "historical_curve"
        item["baseline_curve_source"] = "historical_curve"
    return seeded


@pytest.fixture
async def client():
    """创建测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """隔离 API 模块内的全局内存状态，避免测试互相污染。"""
    baseline_snapshot = copy.deepcopy(_BASELINE_STORE)
    definition_snapshot = copy.deepcopy(_DEFINITION_STORE)
    heat_snapshot = copy.deepcopy(_HEAT_STORE)
    live_heat_cache_snapshot = copy.deepcopy(_LIVE_HEAT_CACHE)
    heat_compare_cache_snapshot = copy.deepcopy(_HEAT_COMPARE_CACHE)
    mock_heat_snapshot = copy.deepcopy(_MOCK_HEAT_STREAM_STORE)
    task_snapshot = copy.deepcopy(_TASK_STORE)
    settings_snapshot = copy.deepcopy(_SETTINGS_STORE)
    host_channel_snapshot = copy.deepcopy(_HOST_CHANNEL_STORE)
    host_channel_catalog_snapshot = copy.deepcopy(_HOST_CHANNEL_CATALOG_CACHE)
    host_channel_last_sync_snapshot = _HOST_CHANNEL_LAST_SYNC_AT
    next_heat_index_snapshot = _NEXT_MOCK_HEAT_INDEX
    enable_mock_dataset_snapshot = settings.enable_mock_dataset
    _HEAT_STORE.clear()
    _HEAT_STORE.update(_build_test_reference_heats())
    _LIVE_HEAT_CACHE["expires_at"] = None
    _LIVE_HEAT_CACHE["items"] = {}
    _HEAT_COMPARE_CACHE["entries"] = {}
    _SETTINGS_STORE["live_heat_inference_enabled"]["value"] = "false"

    yield

    _BASELINE_STORE.clear()
    _BASELINE_STORE.update(copy.deepcopy(baseline_snapshot))

    _DEFINITION_STORE.clear()
    _DEFINITION_STORE.update(copy.deepcopy(definition_snapshot))

    _HEAT_STORE.clear()
    _HEAT_STORE.update(copy.deepcopy(heat_snapshot))

    _LIVE_HEAT_CACHE.clear()
    _LIVE_HEAT_CACHE.update(copy.deepcopy(live_heat_cache_snapshot))

    _HEAT_COMPARE_CACHE.clear()
    _HEAT_COMPARE_CACHE.update(copy.deepcopy(heat_compare_cache_snapshot))

    _MOCK_HEAT_STREAM_STORE.clear()
    _MOCK_HEAT_STREAM_STORE.update(copy.deepcopy(mock_heat_snapshot))

    _TASK_STORE.clear()
    _TASK_STORE.update(copy.deepcopy(task_snapshot))

    _SETTINGS_STORE.clear()
    _SETTINGS_STORE.update(copy.deepcopy(settings_snapshot))

    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(copy.deepcopy(host_channel_snapshot))

    _HOST_CHANNEL_CATALOG_CACHE.clear()
    _HOST_CHANNEL_CATALOG_CACHE.extend(copy.deepcopy(host_channel_catalog_snapshot))

    import src.api.settings as settings_module

    settings_module._HOST_CHANNEL_LAST_SYNC_AT = host_channel_last_sync_snapshot

    import src.api.heats as heats_module

    heats_module._NEXT_MOCK_HEAT_INDEX = next_heat_index_snapshot
    settings.enable_mock_dataset = enable_mock_dataset_snapshot
