# Runtime Stage 3/4 交接提示词

请先阅读：

1. `AGENTS.md`
2. `docs/progress.md`
3. `docs/lessons.md`
4. `docs/BACKEND_STRUCTURE.md`
5. `docs/testing.md`
6. `docs/session_handoff.md`
7. `docs/runtime-source-of-truth-refactor-plan.md`
8. `docs/runtime-code-review-2026-04-08.md`

当前代码状态：

- runtime 真源重构已完成 Stage 3/4，本地代码已做到：
  - 当前炉次出生即冻结
  - live 运行中只增量更新 runtime
  - `birth_context` 已冻结：
    - `primary_baseline_id`
    - `baseline_bindings_snapshot`
    - `definition_metric_snapshots`
    - `baseline_curve_snapshots`
    - `cutting_config_snapshot`
  - same active heat 延续时，不再重新走 `compile_runtime_candidates(...)`
  - replay 批量固化已透传同一份 `cutting_config`
  - runtime compare 只在“完整 runtime 快照到位”时走新真源路径
  - runtime compare 不再请求期回源 EDC / hydrate baseline 现场拼曲线

本地验证结果：

- `pytest -q tests/test_heat_runtime_factory.py tests/test_heat_stream_processor.py tests/test_heats_api.py tests/test_formal_heat_api.py tests/test_heat_replay_api.py`
  - `76 passed`
- `pytest -q`
  - `135 passed`
- `git diff --check`
  - 通过

本轮关键文件：

- `apps/server/src/api/heats.py`
- `apps/server/src/services/formal_heat_service.py`
- `apps/server/src/services/heat_runtime_factory.py`
- `apps/server/src/services/heat_runtime_updater.py`
- `apps/server/src/services/heat_replay_batch_service.py`
- `apps/server/src/services/heat_runtime_types.py`
- `apps/server/tests/test_heats_api.py`
- `apps/server/tests/test_heat_runtime_factory.py`

当前未完成项：

1. 还没做公网部署
2. 还没做 blank / 真实源的公网验证
3. 正式多指标主链仍主要是 `power / voltage`
   - `baseline metric_series` 已支持按定义多指标存储
   - `heat metric_series` 主链目前仍主要只写 `power / voltage`
   - 偏离分析当前仍主要按 `power` 计算

如果本 session 继续推进，默认下一步顺序：

1. 先确认是否要部署当前工作区到公网
2. 若部署：
   - 按当前部署语义做干净部署
   - 部署后验证 runtime / compare / replay 真源路径没有回退
3. 若继续后端开发：
   - 进入“heat 正式多指标主链”改造
   - 目标不是只改展示，要把 runtime / formal heat / compare / analysis 一起打通

明确禁止：

- 不要把 runtime compare 又退回到“请求期现场取 EDC 曲线”的旧逻辑
- 不要只因为 `record_source=active_runtime/previous_runtime` 就强行切新 compare 路径
- 必须先确认这条 runtime 已带齐：
  - `runtime_metric_series`
  - `definition_metric_snapshots`
  - `baseline_curve_snapshots`
- 不要把“页面能动态显示更多指标”误当成“正式主链已经多指标化”
