<!-- 生命周期：仅本轮“正式表重构 + 测试收口 + 本地 factory-reset + blank 部署”有效；本轮任务完成后可删除或并入 session_handoff.md。 -->

# 测试与部署交接提示词

请接手 `D:\project\EDC electricity` 的后续测试与本地部署工作。先不要扩散范围，严格沿用当前主线：**正式表重构继续推进，旧 runtime JSON 只保留最小运行态，测试直接重写到正式表口径，不补旧兼容层。**

## 一、开始前必须先读

1. `D:\project\EDC electricity\AGENTS.md`
2. `D:\project\EDC electricity\docs\progress.md`
3. `D:\project\EDC electricity\docs\lessons.md`
4. `D:\project\EDC electricity\docs\BACKEND_STRUCTURE.md`
5. `D:\project\EDC electricity\docs\BACKEND_FORMAL_DATA_REBUILD_PLAN.md`
6. `D:\project\EDC electricity\docs\testing.md`
7. `D:\project\EDC electricity\docs\session_handoff.md`

## 二、当前主线结论

1. 正式表结构、模型、migration 已落地：
   - `baseline_definitions`
   - `baseline_definition_metrics`
   - `baselines`
   - `metric_series`
   - `heats`
   - `tasks`
   - `settings`
2. `baseline_definitions / baselines` 主读写链路已经切到正式表。
3. `heats` 历史列表/详情/部分写路径已经开始切到正式表。
4. 当前策略已定：
   - 不再给旧 runtime 链路补兼容层
   - 直接把旧测试重写成正式表口径
5. 当前本地 HEAD 还是 `89f4d2f`，但工作区有大量未提交正式表重构改动。

## 三、优先任务

### Task A：继续重写旧后端测试

当前已完成并通过的测试：

- `uv --directory apps/server run pytest tests/test_formal_baseline_api.py -q`
- `uv --directory apps/server run pytest tests/test_formal_heat_api.py -q`
- `uv --directory apps/server run pytest tests/test_api_edge_cases.py -q`
- `uv --directory apps/server run pytest tests/test_tasks_reports_settings_api.py -q`
- `uv --directory apps/server run pytest tests/test_baselines_dashboard_api.py -q`

当前未完成的重点文件：

- `D:\project\EDC electricity\apps\server\tests\test_heats_api.py`

继续重写 `test_heats_api.py` 时，必须遵守：

1. 统一使用正式 baseline id：
   - `def-001:001`
   - `def-002:001`
2. 不再假设旧字符串：
   - `baseline-001`
   - `baseline-002`
3. 不再把 `_BASELINE_STORE / _HEAT_STORE` 当作主真源。
4. 需要接受测试基座现在会预置一条正式历史炉次 `heat-001`，不能再写“清空 runtime 后 total=0”这类旧断言。
5. 所有 pytest 必须**串行执行**，不要并发开多个 pytest 进程共享同一个 SQLite 文件。

建议先跑：

```powershell
uv --directory apps/server run pytest tests/test_heats_api.py -q
```

重写后再跑：

```powershell
uv --directory apps/server run pytest tests/test_formal_baseline_api.py tests/test_formal_heat_api.py tests/test_api_edge_cases.py tests/test_tasks_reports_settings_api.py tests/test_baselines_dashboard_api.py tests/test_heats_api.py -q
```

### Task B：完成本地部署并留在可测试状态

目标：最终把本地环境部署成 **factory-reset + blank** 模式，等用户手动验证。

要求：

1. 不要使用旧 runtime 数据。
2. 最终要让本地是“空白初始化态”，不是带旧测试数据的脏状态。
3. 需要确认：
   - `3000` 前端可打开
   - `3001` 宿主可打开
   - `8000` 后端健康
4. 需要记录最终部署方式、端口、启动命令和 blank 初始化结果到：
   - `D:\project\EDC electricity\docs\progress.md`
   - `D:\project\EDC electricity\docs\session_handoff.md`

如果需要重建本地环境，优先查现有脚本和部署文档，不要自己发明新入口。

## 四、测试与验证规则

1. 纯后端测试按 `docs/testing.md` 的“纯后台测试”执行。
2. 如果改动影响 UI 或正式 UAT 路径，必须补完整用户路径验证。
3. 如果修改了正式验收路径或状态语义，检查是否需要更新：
   - `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`

## 五、完成后必须更新

1. `D:\project\EDC electricity\docs\progress.md`
2. `D:\project\EDC electricity\docs\session_handoff.md`
3. 如有新的问题模式，更新：
   - `D:\project\EDC electricity\docs\lessons.md`

## 六、不要做的事

1. 不要回头补旧 runtime 兼容层。
2. 不要为了让旧测试过而恢复 `baseline-001` 这类旧 ID 语义。
3. 不要并发跑多个 pytest。
4. 不要把 factory-reset + blank 部署成带旧测试数据的状态。

