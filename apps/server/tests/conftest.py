"""测试配置"""

import copy

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.baseline_definitions import _DEFINITION_STORE
from src.api.baselines import _BASELINE_STORE
from src.api.heats import _HEAT_STORE, _NEXT_HEAT_INDEX
from src.api.settings import _HOST_CHANNEL_STORE, _SETTINGS_STORE
from src.api.tasks import _TASK_STORE
from src.main import app


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
    task_snapshot = copy.deepcopy(_TASK_STORE)
    settings_snapshot = copy.deepcopy(_SETTINGS_STORE)
    host_channel_snapshot = copy.deepcopy(_HOST_CHANNEL_STORE)
    next_heat_index_snapshot = _NEXT_HEAT_INDEX

    yield

    _BASELINE_STORE.clear()
    _BASELINE_STORE.update(copy.deepcopy(baseline_snapshot))

    _DEFINITION_STORE.clear()
    _DEFINITION_STORE.update(copy.deepcopy(definition_snapshot))

    _HEAT_STORE.clear()
    _HEAT_STORE.update(copy.deepcopy(heat_snapshot))

    _TASK_STORE.clear()
    _TASK_STORE.update(copy.deepcopy(task_snapshot))

    _SETTINGS_STORE.clear()
    _SETTINGS_STORE.update(copy.deepcopy(settings_snapshot))

    _HOST_CHANNEL_STORE.clear()
    _HOST_CHANNEL_STORE.extend(copy.deepcopy(host_channel_snapshot))

    import src.api.heats as heats_module

    heats_module._NEXT_HEAT_INDEX = next_heat_index_snapshot
