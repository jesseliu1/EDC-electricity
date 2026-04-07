# 会话交接 (Session Handoff)

> 用于在新 session 中快速恢复上下文。开始新会话时，优先阅读本文件，再按需展开 `progress.md / lessons.md / ui_issues.md`。

> 口径说明：本文件顶部“最新交接摘要”才是当前现状。后续各节保留历史交接快照，内部出现的“当前 / 下一步 / ready / 8000 / 真源”都只代表对应时点，不代表现在。

---

## 2026-04-07 replay job 取消锁库与 replay/head 重叠展示已在本地代码层修复，尚未重新部署公网（最新交接摘要，优先于下面旧记录）

- 当前代码状态：
  - 本地工作区已完成修复，尚未形成新的公网部署结论
  - 受影响文件：
    - `apps/server/src/services/heat_replay_batch_service.py`
    - `apps/server/src/api/heats.py`
    - `apps/server/src/services/live_heat_runtime_service.py`
    - `apps/server/tests/test_heat_replay_api.py`
    - `apps/server/tests/test_formal_heat_api.py`
- 本轮本地修复点：
  - replay job 新增内存态快照 `_REPLAY_JOB_SNAPSHOTS`
  - `GET /api/heats/replay-jobs/{job_id}` 运行中优先读快照，不再和 SQLite job 表直接抢锁
  - `_update_job(...)` 已增加 SQLite `database is locked` 重试
  - replay runner 已兼容 snapshot / ORM 两种 job 读取口径
  - 前一轮已加的 replay 完成后 `head runtime rebuild` 仍保留
  - `/api/heats` formal-first 合并仍保留，继续隐藏与正式历史重叠的 `previous_runtime`
- 本轮本地验证：
  - `python3 -m pytest -q tests/test_heat_replay_api.py tests/test_formal_heat_api.py -k 'replay or prefers_formal_history_over_overlapping_previous_runtime'`
    - `4 passed`
  - `python3 -m pytest -q tests/test_heat_replay_api.py tests/test_formal_heat_api.py tests/test_heats_api.py -k 'replay or previous_runtime or formal_history or live_incremental'`
    - `5 passed`
  - `python3 -m pytest -q tests/test_heat_replay_api.py tests/test_formal_heat_api.py tests/test_heats_api.py`
    - `61 passed`
  - `git diff --check`
    - 通过
- 当前结论：
  - 本地已不再复现 `test_cancel_replay_job_marks_job_cancelled` 的 `sqlite3.OperationalError: database is locked`
  - 本地也已验证 replay 完成后的 head rebuild 与 formal-first 列表保护没有被这次修复带坏
  - 之前交接里提到的“replay 后 `/api/heats` 会短时同时看到 `sealed_history` 与 `previous_runtime` 重叠”问题，已在本地代码层收口
- 下一步：
  - 需要把当前工作区修复部署到公网
  - 部署后用真实源复验：
    - replay job 创建 / 取消 / 完成
    - `/api/heats` 是否仍只展示 formal-first 结果
    - replay 完成后 head runtime 是否被正确重建

## 2026-04-07 `live_incremental + replay_batch` 已在公网真源下完成实跑验证（最新交接摘要，优先于下面旧记录）

- 当前公网代码提交：
  - `286a3b54a85d83d900550d532ff6f34f2231cb08`
  - `git log --oneline -1` -> `286a3b5 Refactor heat runtime to live/replay pipeline`
- 本轮公网真实源接入实际执行：
  - 运行库备份：
    - `/home/openclaw/edc-electricity-server/backups/20260407T123508Z-source-connect/asns.db.before-source-connect`
  - 切源：
    - `POST /api/settings/source-switch`
    - `base_url = http://60.251.229.32/`
    - `username = volapu`
    - `password = admin`
  - runtime 刷新：
    - `/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin --db /home/openclaw/edc-electricity-server/data/asns.db --mode deploy-refresh`
  - 后端重启：
    - `systemctl --user restart edc-backend.service`
- 当前公网运行态：
  - `https://hopeofthepantheon.me/api/settings/runtime-status` -> `overall_code = ready`
  - `host.is_connected = true`
  - `host.machine_name = EDC Gateway (60.251.229.32)`
  - `host.meta.sensor_count = 26`
  - `host.meta.channel_count = 2127`
  - `host.meta.enabled_channel_count = 6`
  - `channel_roles`：
    - `dashboard_primary = 2347-199`
    - `dashboard_secondary = 2347-128`
    - `live_heat_inference = 2347-199`
- live 新链路验证结论：
  - 重启后的第一轮真实取数窗口已收敛到近 `3` 小时，而不是旧 `72h`
  - 随后增量刷新窗口约 `90` 秒
  - `/api/heats?page=1&page_size=10` 当前返回 `N-1 / N` runtime 视图，`snapshot_status = ready`
  - 当前新进程下未再复现旧的 `UNIQUE constraint failed: heats.heat_no`
- replay 新链路验证结论：
  - 已创建并完成任务：
    - `job_id = heat-replay-20260407130213-dd0c8eb7`
    - 窗口：`2026-04-07T09:02:06.837Z -> 2026-04-07T13:02:06.837Z`
    - `status = completed`
    - `generated_heat_count = 3`
  - SQLite：
    - `heats = 3`
    - `metric_series = 3`
    - `heat_replay_jobs = 1`
    - `heat_baseline_bindings = 0`
- 当前对外验活：
  - `https://hopeofthepantheon.me/api/health` -> `{"status":"ok"}`
  - `https://hopeofthepantheon.me/api/heats?page=1&page_size=10` -> 返回 live + formal 混合结果，`refresh_error = null`
  - `https://hopeofthepantheon.me/edc/` -> `200`
  - `https://hopeofthepantheon.me/asns/` -> `200`
- 当前注意事项：
  - 现在“公网重新接真实源”的正确顺序已经明确为：
    - `source-switch -> deploy-refresh -> restart backend`
  - 只做 `source-switch` 不够，后端内存态不会自动吃到最新 `runtime_host_channels / channel_role_bindings / host_connectivity_status`
  - replay 后 `/api/heats` 暂时会同时看到 `sealed_history` 与 `previous_runtime` 的短时重叠展示，这属于后续可继续收口的列表语义问题，不影响正式入库链路

## 2026-04-06 `1炉次 -> N黄金基线` 重构已上线到 blank 公网，当前真源口径已切到 bindings（最新口径，优先于下面旧记录）

- 当前核心实现：
  - `baselines` 已新增 `is_default`
  - 已新增 `heat_baseline_bindings`
  - `heats` 已回归只存炉次事实
  - 历史炉次列表 / 详情 / compare / analyze / 任务快照已统一从 `heats + heat_baseline_bindings + metric_series` 组装
  - 任务创建链已显式带 `baseline_id`
- 当前结构文档：
  - 主计划：`docs/heat-baseline-binding-refactor-plan.md`
  - 结构说明：`docs/BACKEND_STRUCTURE.md`
  - 部署说明：`docs/DEPLOYMENT.md`
- 当前 blank 重部署附加口径：
  - `scripts/sync-edc-server.sh` 已支持 `EDC_SERVER_SKIP_START=1`
  - 以后 blank 重部署应优先使用：
    - `EDC_SERVER_SKIP_SOURCE_REFRESH=1 EDC_SERVER_SKIP_START=1 ./scripts/sync-edc-server.sh`
  - 原因：避免后端在删库前先带着旧 SQLite 和旧 source 配置短暂启动一次
- 本轮代码验证结果：
  - `pytest -q`（工作目录 `apps/server`）-> `115 passed`
  - `pnpm --dir apps/web exec tsc --noEmit`
  - `pnpm --dir apps/web build`
  - `pnpm --dir apps/web exec playwright test e2e/app.spec.ts -g "can create and publish a baseline from the wizard|baseline detail source heat CTA opens the linked heat detail page|heat detail create task button posts to tasks api and opens the created task detail"` -> `3 passed`
  - `pnpm --dir apps/web exec playwright test e2e/public-blank-cutting-uat.spec.ts --config=playwright.uat.config.ts` -> `1 passed`
- 本轮公网实际执行：
  - SQLite 备份：
    - `/home/openclaw/edc-electricity-server/backups/20260406T134640Z-factory-reset/asns.db.before-reset`
  - 后端同步：
    - `EDC_SERVER_SKIP_SOURCE_REFRESH=1 ./scripts/sync-edc-server.sh`
  - 删库重建：
    - `systemctl --user stop edc-backend.service`
    - `/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin --db /home/openclaw/edc-electricity-server/data/asns.db --mode factory-reset`
    - `systemctl --user start edc-backend.service`
  - 前端 / 宿主发布：
    - `./scripts/publish-edc-web-and-asns.sh`
- 当前公网状态：
  - 服务：
    - `edc-backend.service = active`
    - `asns-host.service = active`
  - 健康：
    - `http://127.0.0.1:8001/health` -> `{"status":"ok"}`
    - `https://hopeofthepantheon.me/api/health` -> `{"status":"ok"}`
  - 页面：
    - `https://hopeofthepantheon.me/edc/` -> `200`
    - `https://hopeofthepantheon.me/asns/` -> `200`
  - 静态资源：
    - `/edc/` -> `/edc/assets-github-20260406T134757Z/index-CPNB5O-d.js`
    - `/edc/` -> `/edc/assets-github-20260406T134757Z/index-Dfe2v_0I.css`
    - `/asns/` -> `/asns/assets/index-CPYSMy8j.js`
    - `/asns/` -> `/asns/assets/index-xM4OlUIX.css`
    - 上述资源均 `200`
  - blank 数据：
    - `GET /api/baseline-definitions` -> `{"items":[],"total":0}`
    - `GET /api/baselines` -> `{"items":[],"total":0}`
    - `GET /api/heats?page=1&page_size=5` -> 空列表，`snapshot_status="error"`，`refresh_error="live_heat_inference_unavailable"`
    - `GET /api/settings/runtime-status`：
      - `overall_code = host_disconnected`
      - `edc.configured = false`
      - `active_baseline.id = null`
      - `runtime.cutting_mode = signal_inference`
      - `runtime.fixed_interval_minutes = null`
    - SQLite：
      - `baseline_definitions = 0`
      - `baseline_definition_metrics = 0`
      - `baselines = 0`
      - `heats = 0`
      - `metric_series = 0`
      - `tasks = 0`
      - `settings.runtime_baseline_definitions = {}`
      - `settings.runtime_baselines = {}`
      - `settings.runtime_settings_store.active_baseline_id = ""`
      - `settings.runtime_settings_store.edc_base_url = ""`
- 当前重要结论：
  - 公网已经再次回到干净 blank 状态
  - 本轮结构改造后的正式历史真源口径已切到 bindings，不再把 `heats` 当作单基线结果表
  - `https://hopeofthepantheon.me/health` 仍为 `404`，这仍是 nginx 根路径未暴露健康检查，不是后端故障
  - 下一轮如果要接真实 EDC，只能从当前 blank 状态继续，不要再默认继承旧 source 或旧业务数据

## 2026-04-05 公网已重部署到 84cafe9，当前为 factory-reset + blank，且切割设置 roundtrip 已验证（最新口径，优先于下面旧记录）

- 当前部署提交：
  - 工作区 / 实际发布提交：`84cafe93f1ca769cf796a5432a9270ce8c348176`
  - `git log --oneline -1`：`84cafe9 feat: add configurable heat cutting modes`
- 本轮实际执行：
  - 备份运行数据库到：
    - `/home/openclaw/edc-electricity-server/backups/20260405T151229Z-factory-reset/asns.db.before-reset`
  - 后端同步：
    - `EDC_SERVER_SKIP_SOURCE_REFRESH=1 ./scripts/sync-edc-server.sh`
  - SQLite 强清空：
    - `systemctl --user stop edc-backend.service`
    - `/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin --db /home/openclaw/edc-electricity-server/data/asns.db --mode factory-reset`
    - `systemctl --user start edc-backend.service`
  - EDC 前端 + ASNS 宿主发布：
    - `./scripts/publish-edc-web-and-asns.sh`
- 当前公网 blank 结果：
  - `https://hopeofthepantheon.me/api/health` -> `{"status":"ok"}`
  - `https://hopeofthepantheon.me/api/baseline-definitions` -> `{"items":[],"total":0}`
  - `https://hopeofthepantheon.me/api/baselines` -> `{"items":[],"total":0}`
  - `https://hopeofthepantheon.me/api/heats?page=1&page_size=5` -> 空列表，`snapshot_status="error"`，`refresh_error="live_heat_inference_unavailable"`
  - `https://hopeofthepantheon.me/api/settings/runtime-status`：
    - `overall_code = host_disconnected`
    - `edc.configured = false`
    - `host.is_connected = false`
    - `runtime.cutting_mode = signal_inference`
    - `runtime.fixed_interval_minutes = null`
    - `channel_roles.missing_required_role_keys = ["dashboard_primary", "live_heat_inference"]`
- 当前 SQLite 验证：
  - `baseline_definitions = 0`
  - `baseline_definition_metrics = 0`
  - `baselines = 0`
  - `heats = 0`
  - `metric_series = 0`
  - `tasks = 0`
  - `settings.runtime_baseline_definitions = {}`
  - `settings.runtime_baselines = {}`
  - `settings.runtime_settings_store.active_baseline_id = ""`
  - `settings.runtime_settings_store.edc_base_url = ""`
  - `settings.runtime_settings_store.cutting_mode = "signal_inference"`
  - `settings.runtime_settings_store.fixed_interval_minutes = ""`
- 当前静态资源指纹：
  - `/edc/` -> `/edc/assets-github-20260405T151303Z/index-DUqdBweX.js`
  - `/edc/` -> `/edc/assets-github-20260405T151303Z/index-Dfe2v_0I.css`
  - `/asns/` -> `/asns/assets/index-CPYSMy8j.js`
  - `/asns/` -> `/asns/assets/index-xM4OlUIX.css`
  - 上述资源均 `200`
- 当前已完成的公网可视化定向验证：
  - Playwright 用例：
    - `apps/web/e2e/public-blank-cutting-uat.spec.ts`
  - 执行命令：
    - `pnpm --dir apps/web exec playwright test e2e/public-blank-cutting-uat.spec.ts --config=playwright.uat.config.ts`
  - 结果：
    - `1 passed`
  - 证据目录：
    - `docs/test-reports/assets/2026-04-05-public-blank-cutting-uat/public/`
    - `docs/test-reports/assets/2026-04-05-public-blank-cutting-uat/evidence.json`
    - `docs/test-reports/assets/2026-04-05-public-blank-cutting-uat/screenshot-review.json`
    - `docs/test-reports/assets/2026-04-05-public-blank-cutting-uat/uat-summary.md`
  - 实测结论：
    - `/asns/` 可打开，连线设置中“已添加通道清单”为空
    - `/edc/` 可打开，Dashboard 显示 `宿主尚未同步真实连接状态`
    - `/edc/settings` 可打开
    - 切割模式可从 `signal_inference` 切到 `fixed_interval=20` 并成功保存
    - 保存后 `runtime-status.runtime.cutting_mode = fixed_interval`、`fixed_interval_minutes = 20`
    - 随后已恢复默认 `signal_inference`，恢复后 runtime 已再次核对正确
- 当前已知差异：
  - nginx 仍未暴露公网根路径 `/health`，所以 `https://hopeofthepantheon.me/health` 仍是 `404`
  - 后端真实健康检查仍使用：
    - `http://127.0.0.1:8001/health`
    - `https://hopeofthepantheon.me/api/health`
  - 当前只完成 blank 定向验证，不等于完整商业 UAT；若下一轮要做 `S01 ~ S07`，需在 blank 一致性已确认的前提下再接真实 EDC 源

## 2026-04-05 公网已重部署到本地提交 9b2c048，当前为 factory-reset + blank 空白态（最新口径，优先于下面旧记录）

- 当前部署提交：
  - 工作区 / 实际发布提交：`9b2c048e8140582ee5ca882dd3ad5686da7fd800`
  - `git log --oneline -1`：`9b2c048 fix baseline day-first wizard flow and history compare sourcing`
  - 注意：当前 `master` 相对 `origin/master` 为 `ahead 1`，也就是公网已经跑到本地提交，但 GitHub 还没包含这次提交
- 本轮实际执行：
  - 备份运行数据库到：
    - `/home/openclaw/edc-electricity-server/backups/20260405T110619Z-factory-reset/asns.db.before-reset`
  - 后端同步：
    - `EDC_SERVER_SKIP_SOURCE_REFRESH=1 ./scripts/sync-edc-server.sh`
  - SQLite 强清空：
    - `/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin --db /home/openclaw/edc-electricity-server/data/asns.db --mode factory-reset`
  - EDC 前端 + ASNS 宿主发布：
    - `./scripts/publish-edc-web-and-asns.sh`
- 当前公网 blank 结果：
  - `https://hopeofthepantheon.me/api/health` -> `{"status":"ok"}`
  - `https://hopeofthepantheon.me/api/baseline-definitions` -> `{"items":[],"total":0}`
  - `https://hopeofthepantheon.me/api/baselines` -> `{"items":[],"total":0}`
  - `https://hopeofthepantheon.me/api/heats?page=1&page_size=5` -> 空列表，`snapshot_status="warming"`，`refresh_error="live_heat_inference_unavailable"`
  - `https://hopeofthepantheon.me/api/settings/runtime-status`：
    - `overall_code = host_disconnected`
    - `edc.configured = false`
    - `host.is_connected = false`
    - `channel_roles.missing_required_role_keys = ["dashboard_primary", "live_heat_inference"]`
- 当前 SQLite 验证：
  - `baseline_definitions = 0`
  - `baseline_definition_metrics = 0`
  - `baselines = 0`
  - `heats = 0`
  - `metric_series = 0`
  - `tasks = 0`
  - `settings.runtime_baseline_definitions = {}`
  - `settings.runtime_baselines = {}`
  - `settings.runtime_settings_store.active_baseline_id = ""`
  - `settings.runtime_settings_store.edc_base_url = ""`
- 当前静态资源指纹：
  - `/edc/` -> `/edc/assets-github-20260405T110742Z/index-DTiC0rAT.js`
  - `/edc/` -> `/edc/assets-github-20260405T110742Z/index-Dfe2v_0I.css`
  - `/asns/` -> `/asns/assets/index-CPYSMy8j.js`
  - `/asns/` -> `/asns/assets/index-xM4OlUIX.css`
  - 上述资源均 `200`
- 当前已知差异：
  - nginx 仍未暴露公网根路径 `/health`，所以 `https://hopeofthepantheon.me/health` 仍是 `404`
  - 后端真实健康检查仍使用：
    - `http://127.0.0.1:8001/health`
    - `https://hopeofthepantheon.me/api/health`

## 2026-04-04 公网部署刷新链时间类型 bug 已修，线上炉次时间/曲线症状已恢复（最新口径，优先于下面旧记录）

- 当前工作区状态：
  - 基线 SHA 仍是 `46dcd4d2ee6e726e72a5765f7b441a9a953eedd3`
  - 当前额外存在未提交修复：
    - `apps/server/src/runtime_state_admin.py`
    - `apps/server/tests/test_runtime_state_admin.py`
- 本轮关键发现：
  - `runtime_state_admin.py` 仍在用 raw SQL `CURRENT_TIMESTAMP` 写 `settings.updated_at`
  - `settings.updated_at` 已改为 `timestamp(ms)` 后，这会把 `runtime_host_channels / runtime_channel_role_bindings / runtime_host_connectivity_status` 等 runtime 记录写成 text 时间
  - 一旦后端重启，`load_runtime_state()` 读取 `settings` 时会直接因 text/`timestamp_ms` 不匹配崩溃
- 已完成修复：
  - `_upsert_json_record(...)` 改为写 `utc_now_ms()`
  - `apps/server/tests/test_runtime_state_admin.py` 已补 `updated_at` 为 `integer` 的回归断言
  - `pytest -q apps/server/tests/test_runtime_state_admin.py` 已通过（`5 passed`）
- 已完成部署：
  - 执行 `./scripts/sync-edc-server.sh`
  - 后端 runtime 目录：`/home/openclaw/edc-electricity-server`
  - 这次同步会顺手用修复后的 `deploy-refresh` 重写先前那几条写坏的 runtime settings
- 当前公网状态：
  - `https://hopeofthepantheon.me/api/health` -> `{"status":"ok"}`
  - `https://hopeofthepantheon.me/api/settings/runtime-status` -> `overall_code=ready`
  - `https://hopeofthepantheon.me/api/heats?page=1&page_size=5` 已恢复晚间炉次，例如：
    - `H20260404-2016`
    - `H20260404-1930`
    - `H20260404-1843`
  - 最新炉次 `live-heat-c4019e8d-1775306400000-45` 的 `/curve`：
    - `power_curve` 共 `2792` 点
    - 非零点 `2792`
    - `power_min=5.216327`
    - `power_max=14.041406`
  - `/edc/` 引用：
    - `/edc/assets-github-20260404T143126Z/index-C4EzkwlH.js`
    - `/edc/assets-github-20260404T143126Z/index-Dfe2v_0I.css`
    - 上述资源均 `200`
  - `/asns/` 引用：
    - `/asns/assets/index-CPYSMy8j.js`
    - `/asns/assets/index-xM4OlUIX.css`
    - 上述资源均 `200`
- 当前要点：
  - 用户之前报的两个直接症状目前在公网都不再复现：
    - “炉次像只到早上 9 点多”
    - “炉次详情曲线空白”
  - 但 auto-pick 当前仍选中：
    - `dashboard_primary = 2347-199`
    - `live_heat_inference = 2347-199`
  - 该通道现在已非零并能正常产出 heats/curve，但与以下候选相比数值明显偏弱：
    - `2349-199`
    - `2702-205`
  - 如果后续要继续提高“选中正确主功率通道”的把握，应继续改 live 通道 ranking / 设备元数据利用，不要回头再按时区问题误判
- 补充口径：
  - 当前公网 nginx 未暴露根路径 `/health`，所以 `https://hopeofthepantheon.me/health` 返回 `404`
  - 后端本体健康检查仍可用：
    - `http://127.0.0.1:8001/health`
    - `https://hopeofthepantheon.me/api/health`

## 2026-04-04 旧 heats 测试重写 + factory-reset blank 部署已完成（最新口径，优先于下面旧记录）

- 当前已完成：
  - `apps/server/tests/test_heats_api.py` 已按正式表口径重写，不再补旧 runtime 兼容层
  - `apps/server/src/api/heats.py` 已补 `_ensure_formal_baseline_mirrors_loaded(...)` 缺口，避免“正式表里有基线，但内存镜像没加载到”导致 `curve / compare / analyze` 读不到
  - `apps/server/src/runtime_state_admin.py` 的 `factory-reset` 现会同时清空正式业务表：
    - `baseline_definitions`
    - `baseline_definition_metrics`
    - `baselines`
    - `heats`
    - `metric_series`
    - `tasks`
  - `apps/server/tests/test_runtime_state_admin.py` 已新增回归，防止 factory-reset 只清 runtime 不清正式表
- 当前已验证：
  - `uv --directory apps/server run pytest tests/test_heats_api.py -q`
  - `uv --directory apps/server run pytest tests/test_runtime_state_admin.py -q`
  - `uv --directory apps/server run pytest tests/test_formal_baseline_api.py tests/test_formal_heat_api.py tests/test_api_edge_cases.py tests/test_tasks_reports_settings_api.py tests/test_baselines_dashboard_api.py tests/test_heats_api.py tests/test_runtime_state_admin.py -q`
    - 结果：`103 passed, 1 warning`
  - `uv run ruff check src/api/heats.py src/runtime_state_admin.py tests/test_heats_api.py tests/test_runtime_state_admin.py`（工作目录：`apps/server`）
- 当前本机 blank 部署状态：
  - 后端：`http://127.0.0.1:8000`
  - 前端：`http://localhost:3000/edc/`
  - 宿主：`http://localhost:3001/`
  - 日志目录：`D:\project\EDC electricity\.tmp_run\local\`
    - `backend.log / backend.err.log`
    - `web.log / web.err.log`
    - `asns.log / asns.err.log`
- 当前 blank 验证结果：
  - `curl.exe -I http://localhost:3000/edc/` -> `200`
  - `curl.exe -I http://localhost:3001/` -> `200`
  - `curl.exe -s http://127.0.0.1:8000/health` -> `{"status":"ok"}`
  - `curl.exe -s http://localhost:3000/api/health` -> `{"status":"ok"}`
  - `curl.exe -s http://localhost:3001/api/health` -> `{"status":"ok"}`
  - `curl.exe -s http://localhost:3001/` 已确认包含 `window.__ASNS_EDC_APP_URL__ = "http://localhost:3000/edc/";`
  - `GET /api/baseline-definitions` -> `{"items":[],"total":0}`
  - `GET /api/baselines` -> `{"items":[],"total":0}`
  - `GET /api/heats` -> 空列表，`snapshot_status="warming"`
  - SQLite `settings.runtime_baseline_definitions = {}`
  - SQLite `settings.runtime_baselines = {}`
  - SQLite `settings.runtime_settings_store.active_baseline_id = ""`
- 当前重要结论：
  - 现在这台开发机已经不是“runtime 空但正式表残留样板数据”的假 blank
  - 当前可以直接留给用户手动验证 blank 新系统
- 下一步建议：
  - 直接从 `3001` 宿主入口开始手测 blank 路径
  - 若后续再改正式表主链，记得 `factory-reset` 已经属于“清正式表 + 清 runtime”的强清空入口，不要再手工补删库脚本

## 2026-04-04 测试与本地 blank 部署交接提示词（优先于下面旧口径）

- 已新增可直接给新 session 使用的交接提示词：
  - `docs/TEST_DEPLOY_HANDOFF_PROMPT.md`
- 使用方式：
  - 新 session 先读 `AGENTS.md / progress.md / lessons.md / BACKEND_STRUCTURE.md / BACKEND_FORMAL_DATA_REBUILD_PLAN.md / testing.md / session_handoff.md`
  - 然后按提示词继续做：
    - 重写旧 `test_heats_api.py` 为正式表口径
    - 串行完成后端回归
    - 最后把本地切到 `factory-reset + blank` 可测状态
- 关键提醒：
  - 不补旧 runtime 兼容层
  - 不恢复 `baseline-001` 旧 ID 语义
  - 不并发跑多个 pytest 进程共享 SQLite
  - 最终部署必须是 blank 空白态，等用户手测

## 2026-04-04 heats 历史写路径继续切到正式表（优先于下面旧口径）

- 当前已完成：
  - `apps/server/src/services/formal_heat_service.py` 新增：
    - `update_formal_heat_record(...)`
    - `resume_formal_heat_cutting(...)`
    - `save_formal_heat_analysis(...)`
  - `apps/server/src/api/heats.py` 已进一步切正式历史写路径：
    - `PATCH /api/heats/{id}` 对 `sealed_history` 直接写正式 `heats`
    - `POST /api/heats/{id}/resume-cutting` 对 `sealed_history` 直接写正式 `heats`
    - `POST /api/heats/{id}/analyze` 对 `sealed_history` 直接写正式 `heats`
  - `POST /api/heats/{id}/analyze` 已去掉默认 `baseline-001` fallback；炉次未绑定基线时现在显式报错
- 当前已补测试：
  - `apps/server/tests/test_formal_heat_api.py`
    - 历史修改写 DB
    - 历史恢复切割写 DB
    - 历史分析不再依赖实时 EDC
- 当前已验证：
  - `uv --directory apps/server run pytest tests/test_formal_baseline_api.py tests/test_formal_heat_api.py -q`
  - `uv --directory apps/server run ruff check src/services/formal_baseline_service.py src/services/formal_heat_service.py src/services/__init__.py src/api/baselines.py src/api/heats.py tests/test_formal_baseline_api.py tests/test_formal_heat_api.py`
  - `uv --directory apps/server run python -m py_compile src/services/formal_baseline_service.py src/services/formal_heat_service.py src/services/__init__.py src/api/baselines.py src/api/heats.py tests/test_formal_baseline_api.py tests/test_formal_heat_api.py`
- 全量测试现状：
  - 已执行 `uv --directory apps/server run pytest -q`
  - 目前仍有 49 个失败
  - 失败主因已确认：大量旧测试仍绑定旧样板 `def-001 / baseline-001 / heat-001`、旧 `_BASELINE_STORE / _HEAT_STORE` 和旧 baseline id 形态，不再代表当前正式链主回归
- 下一步建议：
  - 先决定是“补正式表测试 seed/兼容层”，还是“直接重写旧测试为正式表口径”
  - 若继续改代码主链，优先保持 `heats` 历史主读写与正式表一致，不要再往 `_HEAT_STORE` 回写

## 2026-04-04 heats 历史主读链已开始切到正式表（优先于下面旧口径）

- 当前已完成：
  - 新增 `apps/server/src/services/formal_heat_service.py`
  - `apps/server/src/api/heats.py` 已开始改为：
    - 历史列表优先读 `heats + metric_series`
    - 历史详情优先读 `heats + metric_series`
    - `GET /api/heats/{id}/curve` 对 `sealed_history` 直接读正式表曲线
    - 运行态刷新时，`runtime_candidates[2:]` 开始正式写入 `heats`
- 当前缓存边界：
  - 只保留当前炉次和上一炉次运行态缓存
  - `_HEAT_STORE` 已不再承担历史主读职责，只剩过渡残留
- 本轮顺手已修：
  - `_resolve_baseline_version_for_time()` 不再把未来基线 fallback 到过去炉次
- 当前已补新测试：
  - `apps/server/tests/test_formal_heat_api.py`
  - 覆盖历史列表读 DB、历史曲线读 `metric_series`、未来基线不再反向作用过去炉次
  - 覆盖运行态刷新后只缓存 `n-1 / n`，其余历史直接落正式表
- 当前已验证：
  - `uv --directory apps/server run pytest tests/test_formal_baseline_api.py tests/test_formal_heat_api.py -q`
  - `uv --directory apps/server run ruff check src/services/formal_heat_service.py src/api/heats.py src/services/__init__.py tests/test_formal_baseline_api.py tests/test_formal_heat_api.py`
  - `uv --directory apps/server run python -m py_compile src/services/formal_heat_service.py src/api/heats.py src/services/__init__.py tests/test_formal_baseline_api.py tests/test_formal_heat_api.py`
- 当前未完成：
  - `GET /api/heats/{id}/compare` 仍是过渡态：历史当前曲线已可读 DB，但基线曲线仍走旧 hydrate
  - `tests/test_heats_api.py` 仍大量绑定旧 `_BASELINE_STORE / _HEAT_STORE` 样板假设，当前不能再作为正式主链回归依据，需要后续重写
- 下一步建议：
  - 继续切 `compare / cutting-timeline / update` 到正式表口径
  - 再把旧 `test_heats_api.py` 改写为正式表测试集

## 2026-04-03 基线正式表主链已切到 DB（优先于下面旧口径）

- 当前已完成：
  - 新增 `apps/server/src/services/formal_baseline_service.py`
  - `apps/server/src/api/baseline_definitions.py` 已切到正式表
  - `apps/server/src/api/baselines.py` 已切到正式表
- 当前已经由 DB 承担主读写的能力：
  - 基线定义列表 / 详情 / 创建 / 更新 / 删除 / 启停
  - 定义指标项新增 / 更新 / 删除
  - 基线版本列表 / 详情 / 创建 / 更新 / 发布 / 停用 / 删除 / 激活
- 当前为了不提前打断 `heats` 旧链路，仍保留：
  - `_DEFINITION_STORE`
  - `_BASELINE_STORE`
  作为过渡镜像；镜像内容由正式表回填，不再是源数据
- 新增验证：
  - `apps/server/tests/test_formal_baseline_api.py`
  - `uv --directory apps/server run pytest tests/test_formal_baseline_api.py -q` 已通过
- 测试基座已更新：
  - `apps/server/tests/conftest.py` 每轮测试先重建 schema，避免旧 SQLite 表结构污染正式表验证
- 当前下一步：
  - 转入 `heats` 主链路重构
  - 目标是让历史炉次、偏离度、详情主读逐步脱离 runtime JSON

## 2026-04-03 后端正式表重构已进入实现（优先于下面旧口径）

- 已按主线文档：
  - `docs/BACKEND_FORMAL_DATA_REBUILD_PLAN.md`
  开始真正落代码
- 当前已完成的实现层内容：
  - 重写 `apps/server/src/models/baseline.py`
    - `BaselineDefinition`
    - `BaselineDefinitionMetric`
    - `Baseline`
  - 新增 `apps/server/src/models/metric_series.py`
  - 重写 `apps/server/src/models/heat.py`
  - 重写 `apps/server/src/models/task.py`
  - 更新 `apps/server/src/models/__init__.py`
  - 重写 `apps/server/alembic/versions/26998facdffe_initial_schema.py`
- 当前已落地的新正式表：
  - `baseline_definitions`
  - `baseline_definition_metrics`
  - `baselines`
  - `metric_series`
  - `heats`
  - `tasks`
  - `settings`
- 当前已验证：
  - `uv --directory apps/server run python -m py_compile src/models/baseline.py src/models/heat.py src/models/metric_series.py src/models/task.py src/models/__init__.py alembic/versions/26998facdffe_initial_schema.py`
  - `uv --directory apps/server run ruff check src/models/baseline.py src/models/heat.py src/models/metric_series.py src/models/task.py src/models/__init__.py alembic/versions/26998facdffe_initial_schema.py`
- 当前未做：
  - 尚未把 `apps/server/src/api/*.py` 的主读写链路切到正式表
  - 尚未补正式表流转测试
- 下一步建议：
  - 先改 `baseline_definitions.py / heats.py` 的 service 与 API 主链路
  - 再补 pytest
  - 最后再接 UI

## 2026-04-03 后端正式表结构定稿（优先于下面旧口径）

- 本轮已把新的后端目标结构正式写入：
  - `docs/BACKEND_STRUCTURE.md`
- 当前定稿口径：
  - 主数据主表：`baseline_definitions`
  - 业务主表：`heats`
  - 从表/外部表：
    - `baseline_definition_metrics`
    - `baselines`
    - `metric_series`
    - `tasks`
    - `settings`
- 关键结构约束已定死：
  - `baseline_definition_metrics.item` 表示指标项号，如 `001 / 002 / 003`
  - `baselines.item` 表示基线版本项，如 `001 / 002 / 003`
  - `metric_series` 统一承载“基线指标值”和“炉次指标值”
  - `heats` 除真实 `start_time / end_time` 外，还保留：
    - `context_start_time`
    - `context_end_time`
  - `metric_series.series_json` 当前口径为：
    - 前 30 分钟
    - 当前炉次区间
    - 后 30 分钟
- 当前炉次运行态缓存口径也已定：
  - 运行态缓存应尽量与 `heats + metric_series` 同构
  - 不再鼓励单独发明一套运行态字段语义
  - 当前炉次仍可在缓存层存在，但正式历史主读链路应逐步切到正式表
- 当前阶段结论：
  - 结构信息已经足够进入正式开发
  - 不需要再继续扩展设计范围到 PostgreSQL/时序库/批量修订功能实现
  - 下一步建议顺序：
    - 先改 SQLAlchemy models
    - 再改 Alembic migration
    - 再切 baseline/heats 主读写链路
    - 最后补测试与 UI 对接

## 2026-04-03 晚间新增未修理问题（优先于下面旧口径）

- 本轮用户明确要求“先记录不要修理”，因此以下问题当前只登记，不做代码修改：
  - 新创建基线会作用到创建时间之前的历史炉次，违反“历史数据固定、生效时间之后才影响新数据”的业务要求
  - 已固化历史炉次读取仍偏慢，用户预期固定态应直接读取
  - 炉次浏览开始时间仍在变化，需核对是实现未完全生效还是本地未部署到最新版本
  - 偏离度计算未稳定触发，多条炉次长期停留在“待计算”
- 问题已同步登记到：
  - `issue.md`
  - `docs/ui_issues.md`
  - `docs/progress.md`
- 下一轮正确顺序：
  - 先核对本地实际运行版本与 API 返回值
  - 再判断是部署问题、读链路问题还是计算触发问题
  - 最后才进入修复

## 2026-04-03 炉次“当前 + 前一”运行态收口（优先于下面旧口径）

- 炉次列表不再允许“最近几条全部是动态推断历史”
- 后端现改为三层语义：
  - `active_runtime`：当前炉次
  - `previous_runtime`：前一个炉次，允许短暂待收口
  - `sealed_history`：其余全部固化历史
- 当前实现要点：
  - 刷新时只允许前两条运行态变化
  - 第三条及更早记录会封口进入历史，不再继续重切
  - 旧运行态 ID 会通过 alias 映射到当前有效记录，详情 `/api/heats/{id}`、`/compare`、`/cutting-timeline` 不应再因 rollover 直接 404
- 已同步更新：
  - `apps/server/src/api/heats.py`
  - `apps/server/src/runtime_state.py`
  - `apps/server/src/schemas/heat.py`
  - `apps/server/tests/conftest.py`
  - `apps/server/tests/test_heats_api.py`
  - `apps/web/src/api/heat.ts`
  - `apps/web/src/views/HeatListView.vue`
  - `apps/web/src/views/HeatDetailView.vue`
  - `apps/web/src/locales/zh-CN.json`
  - `apps/web/src/locales/en-US.json`
  - `apps/web/src/locales/zh-TW.json`
  - `apps/web/src/locales/ja-JP.json`
- 本轮验证结论：
  - 定向 pytest 已覆盖“仅两条运行态”“历史不重复”“旧运行态 ID rollover 后仍可打开详情”
  - `ruff` 与前端 `build` 通过
  - 仍缺一轮真实页面点击回归，尤其要回看：
    - 历史炉次时间不再漂移
    - 历史炉次首次点击详情不再偶发空态
- 后续测试若需要先恢复宿主真实链路，默认测试源 A 已固定：
  - endpoint：`http://60.251.229.32/`
  - username：`volapu`
  - password：`admin`
  - 该口径已同步写入 `docs/UAT_CONTINUATION_PROMPT.md` 与正式 UAT 文档 PRE-04 / S01-TC02

## 2026-04-02 炉次 freshness 状态机（优先于下面旧口径）

- 炉次运行态不再只在 `startup / manual refresh` 触发，后端已补后台定时刷新循环：
  - 有进行中炉次时 `30s`
  - 否则 `60s`
- `/api/heats` 已不再只返回 `snapshot_status`，还会返回：
  - `snapshot_watermark`
  - `last_refresh_started_at`
  - `last_refresh_completed_at`
  - `refresh_error`
  - `refresh_failure_count`
- `snapshot_status` 现在统一按 freshness 解释：
  - `ready`
  - `warming`
  - `refreshing_history`
  - `stale`
  - `error`
- 单条炉次响应新增：
  - `runtime_snapshot_status`
  - `realtime_current`
- 当前口径必须这样理解：
  - `completion_status=in_progress` 不再等于“可信当前炉次”
  - 只有 `realtime_current=true` 时，前端才允许显示“当前炉次实时态”
  - stale / error 时旧 `active_runtime` 只能按“运行态炉次快照”展示，不能再冒充实时当前
- 已同步更新：
  - `apps/server/src/api/heats.py`
  - `apps/server/src/main.py`
  - `apps/server/src/schemas/heat.py`
  - `apps/web/src/api/heat.ts`
  - `apps/web/src/stores/heat.ts`
  - `apps/web/src/views/HeatListView.vue`
  - `apps/web/src/views/HeatDetailView.vue`
  - `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
- 后续如需把测试 / UAT 交给其他人，直接使用：
  - `docs/UAT_CONTINUATION_PROMPT.md`

## 2026-04-02 测试规则升级（优先于下面旧口径）

- 已把“完整用户路径验证”正式写入仓库规则，不再只是口头要求
- 以后代码修改完成后，若影响用户可见流程、状态机、图表、筛选、时间语义或正式验收结论，必须：
  - 先按 `docs/testing.md` 的完整用户路径规则验证
  - 再检查并必要时更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
- 已同步更新：
  - `AGENTS.md`
  - `docs/testing.md`
  - `docs/IMPLEMENTATION_PLAN.md`
  - `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

## 2026-04-02 基线向导日期筛选补丁（优先于下面旧口径）

- 基线向导 Step 2 已新增「选择日期 + 刷新候选炉次」入口
- 候选炉次为空时显示显式空态提示，避免空白
- i18n 已同步：`zh-CN / en-US / zh-TW / ja-JP`

## 2026-04-01 前端运行态对接与 UAT 脚本更新（优先于下面旧口径）

- 前端炉次列表/详情已对接运行态字段：
  - `completion_status / last_point_at`
  - `baseline_version_id / baseline_effective_from`
  - `snapshot_status`
- 炉次列表新增进行中标识与历史台账刷新/预热提示，详情页进行中炉次每 60 秒自动刷新
- 已更新 UAT 脚本，新增「进行中炉次实时刷新与时间显示」用例：
  - `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`（S06-TC03A）

## 2026-04-01 架构问题交接摘要（优先于下面旧口径）

- 本轮没有做架构重构，只完成了“已确认、未处理”的问题盘点
- 已新增专项交接文档：
  - `docs/ARCHITECTURE_DEBT_HANDOFF.md`
- 当前结论应统一理解为：
  - 前后台边界方向基本正确，但还没有做到“前端只展示、后端只提供标准化数据”
  - 当前最大结构问题不是前端再写系统连接，而是后端内部仍通过 API 模块级 `_STORE` 和跨模块私有调用耦合在一起
  - `baseline / heat / task` 仍主要依赖 `runtime_*` 快照落库，而不是各自正式业务表
  - 前端仍有局部数据推导与假图兜底，典型在 Heat List 微缩图与 Heat Detail 手工调整/compare 视图逻辑
- 后续若要继续处理这类问题，建议顺序：
  - 先拆后端内部边界与 service/repository
  - 再迁业务实体持久化
  - 再收缩前端重数据推导
  - 最后再推进真正插件化
- 新 session 若是为了继续做架构治理，优先阅读：
  - `docs/ARCHITECTURE_DEBT_HANDOFF.md`
  - `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
  - `docs/progress.md`

## 2026-03-31 最新交接摘要（优先于下面所有旧口径）

- 当前本地最新提交：
  - branch：`master`
  - commit：`a38efd7`
  - message：`feat: consolidate host runtime source truth`
- 当前公网已经重新部署到这版：
  - 已执行 `./scripts/sync-edc-server.sh`
  - 已执行 `./scripts/publish-edc-web-and-asns.sh`
  - `/edc/` 当前资源目录：`assets-github-20260331T064047Z`
  - `/edc/` 当前入口脚本：`index-PrnKX7Pq.js`
  - `/asns/` 当前入口脚本：`index-D_DiDccN.js`
  - `GET /api/settings/runtime-status` 当前返回 `overall_code=ready`
  - `GET /api/settings/host-bootstrap` 当前真源仍是 `http://61.216.55.133`
- 当前最重要的结论：
  - 会影响当前 UAT 正确性的来源收口问题已经修完并已部署
  - 当前不需要继续调查“为什么还有旧源”
  - 下一步应该直接围绕当前公网版本做完整 UAT
- 当前明确未完事项：
  - 基于公网最新版本跑完整 UAT，总验要带视觉确认和截图回看
  - 决定 4 个未跟踪临时文件如何处理：
    - `asns_settings_html.txt`
    - `asns_settings_text.txt`
    - `asns_settings_text_final.txt`
    - `uat_s01_s02.sh`
  - 若后续继续做结构治理，方向是：
    - `tasks / heats / baselines` 逐步迁到正式业务表
    - 收缩 `settings` 表对 `runtime_*` 快照的承载
    - 清理默认参数与 demo/seed 数据硬编码
- 当前不要遗漏的事实：
  - 本轮只创建了本地 commit 并已部署公网
  - 是否 push 到远端仓库，本轮没有执行
  - 仓库工作树现在除了 4 个临时文件外是干净的
  - 新 session 如果只是为了上线判断，先读：
    - `docs/progress.md`
    - `docs/HARDCODED_INVENTORY.md`
    - `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
    - `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

## 2026-03-31 硬编码审计分支合流结果（优先于下面旧调查口径）

- 用户要求检查并合回 `codex/hardcode-remediation`
- 已确认远端 `origin/codex/hardcode-remediation` 在 `0b0e047` 只是 docs-only 审计分支：
  - 只新增 `docs/HARDCODED_INVENTORY.md`
  - 只新增 `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
  - 不包含任何代码修复
- 本轮没有把审计文档原样照搬，而是按当前代码状态重写后落库：
  - 已修复项写成“已收口”
  - 仍存在但不阻塞 UAT 的项写成“结构债”
- 本轮补掉的真实代码问题：
  - `apps/server/src/api/tasks.py` + `apps/server/src/runtime_state.py`
  - 非 `showtime` 任务已持久化到 `runtime_tasks`
  - `apps/web/src/api/setting.ts` 已移除残留系统连接写面
  - `apps/web/src/stores/setting.ts` 已移除 `edcBaseUrl / edcApiKey`
  - `apps/web/src/views/SettingsView.vue` 已移除本地旧连接兜底
  - `apps/server/src/config.py` / `apps/server/src/main.py` / `apps/web/vite.config.ts` / `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs` 已补环境化配置
- 本轮验证已经通过：
  - 后端：`pytest tests/test_tasks_reports_settings_api.py tests/test_baselines_dashboard_api.py tests/test_heats_api.py tests/test_runtime_state_admin.py -q` -> `75 passed`
  - EDC 前端：`pnpm build` -> 通过
  - 宿主：`node --import tsx --test src/hostConnectivityState.test.ts src/hostApiServer.test.ts` -> `13 passed`
  - 宿主：`npm run build` -> 通过
- 当前建议下一步：
  - 可以开始完整 UAT
  - 不要再把“调查分支里的盘点清单”直接当成当前现状，优先看：
    - `docs/HARDCODED_INVENTORY.md`
    - `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
    - `docs/progress.md`

## 2026-03-31 宿主运行态真源收口第一阶段已完成（优先于下面“待进入定向修复”口径）

- 本轮已完成真实部署与线上核验：
  - 已执行 `./scripts/sync-edc-server.sh`
  - 已执行 `./scripts/publish-edc-web-and-asns.sh`
  - `8001` 当前 `runtime-status` = `ready`
  - `host-bootstrap` 当前真源 = `http://61.216.55.133`
  - 当前宿主连接摘要 = `EDC Gateway (61.216.55.133) / 739 channels / 6 enabled`
  - 公网 `/edc/` 当前资源目录 = `assets-github-20260331T052340Z`
  - 公网 `/asns/` 正常返回，由 `/home/openclaw/asns-host-runtime` 提供
- 已完成浏览器级实证：
  - `/edc/` 截图显示“宿主已连入 · 真实链路就绪”
  - 渲染后 DOM 中不再出现“未获取到真实实时数据，请检查宿主连接和通道绑定”
  - 注入旧草稿后再打开宿主“连线设置”，浏览器本地草稿会被清掉，页面回到后端当前真源 `http://61.216.55.133`
- 本轮顺手补掉的部署脚本问题：
  - `scripts/publish-edc-web-and-asns.sh` 原本会在 `asns-host` 刚重启时立刻请求公网 `/asns/`
  - 真实部署中曾短暂遇到一次瞬时 `502`
  - 现已新增 `wait_for_url`，并调整为：
    - 先等本机 `http://127.0.0.1:3001/`
    - 再等公网 `https://hopeofthepantheon.me/asns/`
  - 已用真实二次发布验证通过，不再误判失败
- 已落地的核心结果：
  - 后端新增 `GET /api/settings/host-bootstrap`
  - 后端新增 `PUT /api/settings/host-runtime-sync`
  - 宿主正式写入统一要求 `source_revision`
  - revision 冲突时返回 `409`，宿主会清草稿并重新读取后端真源
- 宿主前端当前行为：
  - `SettingsView.tsx` 启动先拉 `host-bootstrap`
  - 本地草稿现在必须同时满足：
    - `sourceIdentity` 与后端当前 source 一致
    - `baseSourceRevision` 与后端当前 revision 一致
  - 不满足时直接清草稿，不再恢复
  - `测试连接 / 同步通道 / 保存设置` 都已接到新 revision 护栏
- 宿主生产快照路径已清理：
  - `App.tsx` 旧 bootstrap restore 已删除
  - 废弃内联 `SettingsView` 已删除
  - `src/edcChannelSnapshot.ts` 已删除
- 宿主测试面已更新：
  - `hostConnectivityState.test.ts` 已覆盖 `sourceIdentity + baseSourceRevision`
  - `hostApiServer.test.ts` 已去掉 Windows 硬路径并修复挂死问题
- 后端测试面已更新：
  - `tests/test_tasks_reports_settings_api.py` 已补 `host-bootstrap / host-runtime-sync / stale revision 409`
  - `tests/conftest.py` 已隔离 `_HOST_SOURCE_REVISION`
- 宿主与后端运行时发布模型已统一到 runtime：
  - ASNS runtime：`/home/openclaw/asns-host-runtime`
  - `publish-edc-web-and-asns.sh` 现在会备份 runtime、清旧 `node_modules`、复制最小运行文件、执行 `npm ci --omit=dev`
  - `deploy/systemd/asns-host.service.example` 与当前机器 `~/.config/systemd/user/asns-host.service` 都已指向 runtime
- 本轮已完成验证：
  - 后端：`pytest tests/test_tasks_reports_settings_api.py -q` -> `16 passed`
  - 宿主：`node --import tsx --test src/hostConnectivityState.test.ts src/hostApiServer.test.ts` -> `13 passed`
  - 宿主：`npm run lint` -> 通过
  - 宿主：`npm run build` -> 通过
  - 脚本：`bash -n scripts/publish-edc-web-and-asns.sh scripts/sync-edc-server.sh` -> 通过
- 当前下一步：
  - 若要继续推进，不是再修部署，而是基于当前线上状态做完整 UAT 总验
  - 浏览器侧留证文件在：
    - `/tmp/edc-verify/edc.png`
    - `/tmp/edc-verify/asns.png`
    - `/tmp/edc-verify/asns-settings-stale-draft-check.png`

## 2026-03-31 宿主运行态真源收口准备（优先于下面旧“只要换源清库就够了”的认知）

- 当前已查清 3 条独立根因链：
  - `ASNS` 宿主前端 bundle 本身仍内置旧测试源快照 `60.251.229.32`
  - 浏览器 `localStorage['asns-host-connectivity-draft']` 当前优先于后端当前设置恢复
  - `8001` 后端跑的是 `/home/openclaw/edc-electricity-server` runtime 副本，且未同步到仓库最新版本
- 当前必须先认定：
  - 不是“单纯数据库没清”
  - 不是“单纯漏部署 ASNS”
  - 也不是“只要换源后清旧数据就自然没事”
- 当前宿主页面加载时的真实动作链：
  - `App.tsx` 启动 effect 会先读后端 `GET /api/settings`
  - 同时读本地 `asns-host-connectivity-draft`
  - 当前优先级：`restored?.config || persistedConfig`
  - 若本地草稿可恢复，会继续调用 `/host-api/edc/test-connection`
  - 然后调用 `syncSelectionToBackend(...)` 把宿主通道与连接摘要重新写回后端
- 当前线上 bundle 中的旧快照并不属于正式 `showtime`：
  - 正式 showtime 只在后端请求级模式里生效
  - 入口：`apps/server/src/request_mode.py`, `apps/server/src/mock_dataset.py`
  - 只有显式 `showtime=true` 或 `X-Showtime` 才开放 mock 数据
- 当前还未改代码，但已与用户对齐后续目标：
  - 生产宿主不再使用 bundle 内置 EDC 快照
  - 系统只保留一套正式 `showtime`
  - `showtime` 假数据也必须由后端 API 提供，不再依赖前端快照
  - 若发生换源，本地草稿直接清空，不再额外确认
  - 宿主启动恢复不得再无条件把本地恢复结果自动回写后端
- 第一阶段解决方案已单独成文：
  - `docs/HOST_SOURCE_TRUTH_FIRST_STAGE_PLAN.md`
  - 核心原则：
    - 后端当前 source 是唯一真源
    - 本地草稿只表示当前浏览器未提交编辑态
    - 启动先读后端，再判草稿是否失效
    - 所有正式写操作带 `source_revision`
    - 第一阶段不做后台草稿
- 进入修改前应优先检查的文件：
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`
  - `scripts/sync-edc-server.sh`
- 当前额外遗漏，不要只盯“换源清理”：
  - 宿主页卡片仍硬编码 `EDC Test Gateway / 2026-03-16 11:12 / 26 devices / 2286 channels`
  - `realChannelCatalog` 仍直接来自 `edcChannelSnapshot`
  - `SettingsView` 初始 `meta` 默认值仍是旧快照
  - 若后端 source 被别的入口改掉，旧浏览器草稿下次开宿主仍可能把旧源重新推回后端

## 2026-03-30 换源收口进展（优先于下面旧“散落处理”认知）

- 已完成整体调查，并补统一方案文档：
  - `docs/SOURCE_SWITCH_UNIFICATION_PLAN.md`
- 当前关键结论：
  - `换源` 不是普通保存动作，而是“破坏性重建来源上下文”
  - 不能继续把换源副作用散落在宿主 `测试连接 / 同步通道 / 保存设置` 与后端各局部逻辑里
- 当前统一语义：
  - `source identity = base_url + username`
  - `connection material = base_url + username + password + api_key`
  - 仅密码/API Key 变化：不是换源，只重置连线验证态
  - 地址或账号变化：才是真正换源，必须清 source-bound state
- 当前后端已落地统一入口：
  - 服务：`apps/server/src/services/source_switch_service.py`
  - 路由：`POST /api/settings/source-switch`
  - schema：`apps/server/src/schemas/source_switch.py`
- 旧入口当前仍保留，但已委托到同一套逻辑：
  - `PUT /api/settings/edc-connection`
- 启动恢复路径也已走同一套换源逻辑：
  - `apps/server/src/runtime_state.py`
- 当前真正换源会统一清掉：
  - 宿主已添加通道
  - 宿主通道目录缓存
  - 宿主最近同步时间
  - 宿主连接状态
  - 当前活动基线
  - 基线定义通道绑定 `edc_channel_id`
  - 比对/实时相关缓存
- 当前不会被换源顺手清掉：
  - 基线主体
  - 炉次/任务/报表历史
  - 容差/切割/报表时间等通用设置
- 已补回归：
  - `apps/server/tests/test_tasks_reports_settings_api.py`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.test.ts`
  - `apps/server` 定向 pytest：`13 passed`
  - 宿主 `npm test`：`11 passed`
- 下一步不要再改后端边界；应继续做：
  - 宿主确认弹窗
  - 宿主单编排方法，避免 `SettingsView.tsx` 继续分散处理 `sourceSwitched`

## 2026-03-30 宿主换源交互收口进展（优先于上面“待做前端收口”口径）

- 宿主侧已开始与后端统一入口对齐：
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
- 当前调整点：
  - `applySourceSwitchToBackend(...)` 专门负责调用后端 `POST /api/settings/source-switch`
  - `syncSelectionToBackend(...)` 现在只负责保存宿主通道与宿主连接摘要，不再顺手承担换源
  - `SettingsView.tsx` 新增 `prepareSourceAwareAction(...)`
  - `测试连接 / 同步通道 / 保存设置` 已统一先走这层预处理
- 当前宿主行为：
  - 如果 `source identity` 变化且本地存在 source-bound state，会先弹确认框
  - 用户确认后，宿主先调后端统一换源入口，再继续原动作
  - 用户取消后，本次动作终止，不再继续执行
- 当前已补文案：
  - `App.tsx` 中新增 `sourceSwitch*` 多语言文案（当前至少覆盖 `zh-CN / zh-TW / en-US`）
- 当前已验证：
  - 宿主 `npm test`：`11 passed`
  - 宿主 `npm run build`：通过，当前新 bundle 为 `index-BYiChWWV.js`
- 当前已新增浏览器回归：
  - `apps/web/e2e/host-source-switch-confirmation.spec.ts`
  - 当前已覆盖：
    - 取消换源后保持 source A / ready
    - 确认换源后继续测试连接并切到 source B
    - 确认换源后继续同步通道
    - 确认换源后继续保存设置
  - 当前 spec 已改为串行，避免多个用例并发踩宿主/后端共享运行态
  - 已执行：`pnpm exec playwright test e2e/host-source-switch-confirmation.spec.ts --project=chromium`
  - 结果：`3 passed`
- 当前环境收尾：
  - 已拉起本地 `3001` 与 `8001` 供宿主回归使用
  - 回归完成后 `http://127.0.0.1:8001/api/settings/runtime-status` 已恢复 `overall_code=ready`
  - 当前 `8001` 设置口径为 `source A (http://60.251.229.32 / volapu / admin)`
- 当前真正剩余工作：
  - 把“是否存在 source-bound state”的判断继续抽成可复用规则
  - 补前端更细粒度单测，避免后续只靠 Playwright 兜底

## 2026-03-30 正式 UAT 总账口径补充（优先于旧“只看切源成功”理解）

- 正式 UAT 主文档已更新：
  - `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
- 当前正式口径新增：
  - `S04-TC02` 不再只看“新源连接成功 + 保存成功”
  - 如果切源前存在旧来源状态，则必须先出现换源确认弹窗
  - 正式证据必须写明：
    - 是否出现确认弹窗
    - 用户点了 `确认` 还是 `取消`
    - 确认后继续的是 `测试连接 / 同步通道 / 保存设置` 哪条路径
- `S05` 现在默认依赖上述 `S04-TC02` 口径成立；如果 S04 没有形成确认证据，S05 不得直接记正式 `PASS`
- `S05` 的正式执行顺序现已固定为：
  - `S04-TC02 -> S05-TC01 -> S05-TC02 -> S05-TC03`
  - 优先使用干净的 `3001 -> 8001`
  - 不允许混用 `8000` 的历史持久化运行态来判 `S05 PASS`
- `S05-TC01 / TC02 / TC03` 的正式通过标准也已进一步收紧：
  - `TC01` 必须证明同步到的是新源目录，而不是旧源目录残留
  - `TC02` 必须证明绑定结果中的 `suid/cuid` 属于当前新源目录
  - `TC03` 必须同时有 Dashboard 截图和 API / 运行态回看，证明数据来自新源链路而非缓存
- 当前总账报告说明也已补到：
  - `docs/test-reports/2026-03-28-uat-followup.md`
  - 已明确其中 `2026-03-28` 的 `23 / 20 / 3 / 0 / 3` 只是当次续跑时点，不代表当前最终正式总账

## 2026-03-29 S05 后续调查结果（优先于旧“8080 阻塞”口径）

- 已补调查报告：`docs/test-reports/2026-03-29-s05-realtime-followup-investigation.md`
- 已完成代码修复：
  - `apps/server/src/api/dashboard.py`
  - Dashboard 实时曲线现已支持在“无活动基线但宿主已绑定功率/电压通道”时回退取数
- 已完成后端回归：
  - `pytest tests/test_baselines_dashboard_api.py -q` → `19 passed`
  - `pytest tests/test_tasks_reports_settings_api.py -q` → `11 passed`
- 当前关键现场结论：
  - source B `61.216.55.133` 的真实设备 `suid` 是 `2752 / 2755 / 300000000000000000001`
  - `8000` 某些持久化状态里残留的仍是旧源绑定：`2349-* / 2054-* / 769-*`
  - 直接用 `EDCClient` 对 source B 查询旧绑定通道 `2349-199 / 2349-128`，在 `5m / 1h / 24h` 内均返回 `0` points
- 因此当前 `S05` 的更真实阻塞不是 `8080`，而是：
  - 旧源 `suid/cuid` 绑定残留
  - 用旧绑定去读 source B，自然拿不到实时点
- 若继续正式推进 `S05`，优先走：
  - `3001 -> 8001`
  - 重新执行 `S05-TC01 / S05-TC02 / S05-TC03`
  - 不要继续沿用 `8000` 的历史持久化状态作为正式依据

## 2026-03-29 `127.0.0.1:8080` 调查结果（优先于旧“外部阻塞”口径）

- 已补调查报告：`docs/test-reports/2026-03-29-8080-blocking-investigation.md`
- 当前已确认：
  - 本机 `127.0.0.1:8080` 无监听进程，`curl` 为 `connection refused`
  - 当前仓库内没有需要由本项目启动的 `8080` 本地服务定义
  - `apps/server/src/config.py` 的 `http://localhost:8080` 只是历史默认占位值
  - 前端 `3000` 当前代理到 `8000`，宿主 `3001` 当前默认代理到 `8001`
- 当前真实运行态：
  - `8000` 已直连 `http://61.216.55.133`
  - `8001` 已直连 `http://60.251.229.32`
  - 因此 `S05` 不应再继续按“被 `127.0.0.1:8080` 阻塞”统一记账
- 当前更真实的后续阻塞：
  - `GET http://127.0.0.1:8000/api/dashboard/realtime?duration=5m` 返回“未获取到真实实时数据，请检查宿主连接和通道绑定”
  - 若继续推进 `S05`，应转查实时数据链路，而不是再查 `8080`

## 2026-03-29 S04-TC02 正式重跑结果（优先于下面旧 FAIL 口径）

- 已新增正式重跑脚本：`apps/web/e2e/s04-tc02-source-switch-rerun.spec.ts`
- 已确认本机 `3001` 当前加载的是新构建入口 `index-DtLUiBmF.js`
- 已执行：
  - 宿主：`http://127.0.0.1:3001/`
  - 后端：`http://127.0.0.1:8001/api`
  - 命令：`pnpm exec playwright test e2e/s04-tc02-source-switch-rerun.spec.ts --project=chromium`
  - 结果：`1 passed`
- 本轮留档已补齐：
  - `docs/test-reports/2026-03-29-s04-tc02-rerun.md`
  - `docs/test-reports/assets/2026-03-29-s04-tc02-rerun/evidence.json`
  - `docs/test-reports/assets/2026-03-29-s04-tc02-rerun/screenshot-review.json`
- 当前正式结论：
  - `S04-TC02`：正式重跑通过
  - `source B (http://61.216.55.133 / admin / admin)` 可成功测试连接并保存
  - 保存后宿主维持在线，不再落入 `host_disconnected`
  - 当前保存后运行态是 `no_enabled_channels`，原因是本用例未继续执行“同步通道 + 绑定宿主通道”闭环
- 环境收尾：
  - 脚本 `finally` 已恢复 source A 与原始宿主通道
  - `http://127.0.0.1:8001/api/settings/runtime-status` 已恢复 `overall_code=ready`

## 2026-03-29 无人值守补记（优先于下面同日旧状态）

- `S07-TC02 / S07-TC03` 已不再处于“正式 UAT 未重跑”状态
- 已新增正式导出回归脚本：`apps/web/e2e/uat-export-followup.spec.ts`
- 已在真实本地链路完成重跑：
  - 前端：`http://127.0.0.1:3000/edc/`
  - 后端：`http://127.0.0.1:8000/api`
  - 命令：`pnpm exec playwright test e2e/uat-export-followup.spec.ts --project=chromium`
  - 结果：`2 passed`
- 本轮留档已补齐：
  - `docs/test-reports/2026-03-29-uat-export-followup.md`
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/evidence.json`
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/screenshot-review.json`
- 当前结论：
  - `S07-TC02`：正式重跑通过
  - `S07-TC03`：正式重跑通过
  - `S04-TC02`：已完成正式重跑并通过
  - `S05-TC01 / S05-TC02 / S05-TC03`：继续按 `127.0.0.1:8080` 外部阻塞处理
- 本轮新增证据：
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc02-task-detail-before-export.png`
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc02-task-detail-after-export.png`
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc03-report-detail-before-export.png`
  - `docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc03-report-detail-after-export.png`
- 注意：总账 `26 / 19 / 17 / 2 / 7` 仍未在本文件直接重算，原因是历史 testcase 粒度口径存在不一致；下次收口时应按正式 UAT 台账统一回写

## 2026-03-29 S04-TC02 调查补充（优先于旧“源码仍失败”猜测）

- 已补调查报告：`docs/test-reports/2026-03-29-s04-tc02-host-runtime-investigation.md`
- 当前已确认：
  - `source B (http://61.216.55.133 / admin / admin)` 在当前环境可成功通过宿主 `host-api test-connection`
  - 本机 `3001` 宿主之前确实存在旧 dist 运行面；旧 bundle 会把设置写请求打到 `http://127.0.0.1:8000/api/*`
  - 重建宿主 dist 后，请求已恢复为同域 `3001/api/*`
- 当前源码下的切源行为要点：
  - 切源后直接 `保存设置`：运行态会进入 `host_disconnected`
  - 切源后先 `测试连接`：运行态会进入 `no_enabled_channels`
- 因此 `S04-TC02` 当前不应再简单理解为“source B 不通”或“当前源码仍有宿主连接缺陷”
- 更合理的解释是：
  - 当时 `3001` 跑的是旧宿主构建 / 旧环境口径
  - 或者执行步骤没有形成“测试连接成功后再保存”的闭环
- 下次若要正式重跑 `S04-TC02`，先确认两件事：
  - `3001` 已加载新构建
  - 宿主页面写请求走的是同域 `3001/api/*`

## 2026-03-29 当前执行口径补充（优先于下面旧总账）

- 当前 UAT 执行层基线先按最新人工确认记忆，不直接沿用 `progress.md` 里尚未完全收敛的旧总账数字
- 当前最关键状态：
  - `S07-TC02 / S07-TC03`：代码已修复，定向回归 `2 passed`，但正式 UAT 脚本尚未重跑，因此正式总账里仍暂按 `FAIL`
  - `S04-TC02`：当前仍按正式 `FAIL` 处理；已知口径仍是“新源保存后 `host_disconnected`”，但是否有新证据待复核
  - `S05-TC01 / S05-TC02 / S05-TC03`：继续按 `127.0.0.1:8080` 外部依赖阻塞处理
- 当前未执行用例数：`7`
- 当前总账先按以下口径记忆，待正式重跑/复核后再统一：
  - 总计 `26`
  - 已执行 `19`
  - 已通过 `17`
  - 已失败 `2`
  - 剩余 `7`
- 当前 bug 台账先按以下口径记忆，待与正式留档统一：
  - 已登记 `58`
  - 已修复 `55`
  - 待回归 `0`

## 2026-03-25 最新交接（优先于下面历史内容）

- 当前开发/收口阶段已完成：`docs/ui_issues.md` 中 tracked issues 已统一收口到标准状态，最近两次收口提交已推到 `origin/master`
  - `6d7b985` `docs: close remaining tracked issue statuses`
  - `7d5cbfb` `docs: finalize progress closure state`
- 当前仓库状态：
  - 分支：`master`
  - 工作树：干净
  - 下一阶段不再是继续点修 UI issue，而是交给 **Code X + `review` skill** 做 **full review / full test**
- 最新 QA 同步：
  - `apps/web` 的 `lint / test:i18n / build` 与关键 Playwright 抽测已通过，mocked 回归层面基本成立
  - 当前本地 review/test 后端 `127.0.0.1:8000` 已恢复可达，运行副本后端 `127.0.0.1:8001` 与宿主 `127.0.0.1:3001` 也在线
  - 当前真实联调仍剩一项外部阻塞：`127.0.0.1:8080` 不可达
  - `Heat Detail` 在详情失败时“手动调整”按钮 silent no-op 已按最小方案收口：当前按钮会进入禁用态，并显示明确不可用提示
  - ASNS 宿主 `npm test` 的 `import.meta.env` / `Invalid URL` 基座问题已在本轮修复，`npm test / lint / build` 当前都可运行
  - EDC 后端 pytest 入口也已恢复：可直接用运行副本现有 venv 对主仓 `apps/server` 跑最小用例

### 下一阶段目标

- 目标：在不重新理解整段历史上下文的前提下，直接对当前 `master` 做一轮完整审查与完整回归，判断是否达到可继续联调/部署的质量门槛
- 建议工作模式：
  - 先读 `docs/progress.md` 最新两轮记录，确认已收口 issue 与当前未覆盖项
  - 再读 `docs/ui_issues.md`，抽查已验收条目的证据口径
  - 启动 `review` skill，重点看回归盲区、测试入口缺口、环境依赖问题，而不是重新做 UI 小修

### 建议测试范围

- EDC 前端基础回归
  - `pnpm --dir apps/web lint`
  - `pnpm --dir apps/web test:i18n`
  - `pnpm --dir apps/web build`
- EDC 前端关键 Playwright 回归
  - `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY pnpm --dir apps/web exec playwright test e2e/loading-error-states.spec.ts`
  - `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY pnpm --dir apps/web exec playwright test e2e/issue-acceptance.spec.ts`
  - `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts`
  - `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY pnpm --dir apps/web exec playwright test e2e/app.spec.ts`
- ASNS 宿主基础回归
  - `npm --prefix 'docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統' run lint`
  - `npm --prefix 'docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統' run build`
  - `npm --prefix 'docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統' run test`
  - 若要补宿主浏览器级验证，应优先把此前一次性 Playwright 控制台脚本收成可复用入口
- EDC 后端测试
  - 现有可用最小入口：
    - `cd apps/server && /home/openclaw/edc-electricity-server/venv/bin/pytest tests/test_baselines_dashboard_api.py::test_baseline_definition_crud_and_metric_workflow tests/test_tasks_reports_settings_api.py::test_settings_get_and_update -q`
  - 后续可继续扩到：`tests/test_baselines_dashboard_api.py`、`tests/test_heats_api.py`、`tests/test_tasks_reports_settings_api.py`

### 重点回归面

- Dashboard / Heat Detail 的 timeout/error state 不再伪装为空态或长期 loading
- Heat Detail 在 error-state 下“手动调整”按钮已改为禁用态 + 明确提示，真实联调阶段需顺手确认 happy path 与 error-state 都未回退
- i18n missing-key 告警、默认中文界面的中英混排、不完整 locale 回退
- Heat Detail 的状态口径拆分、异常原因/切割原因本地化
- Baseline/Task/Heat 列表中的占位按钮、假搜索/假筛选、误导性空偏差文案
- `live_inferred` canonical URL 替换与 Heat Detail 创建任务最小闭环
- ASNS 宿主设置页的 `Maximum update depth exceeded` / nested button 风险是否仍无回流

### 已知环境缺口

- EDC 后端 pytest 当前已恢复到“可运行的临时基线”，但还不是标准环境
  - 当前可用入口依赖运行副本现有 venv：`/home/openclaw/edc-electricity-server/venv/bin/pytest`
  - `apps/server/tests/conftest.py` 已补 startup 初始化，并在每条测试前清理 `runtime_*` SQLite 持久化残留，因此最小用例当前可稳定串行通过
  - 仍未回到项目文档推荐的 `uv + Python 3.11` 标准形态；若后续要做完整后端回归，最好再补齐标准环境
- `127.0.0.1:8080` 仍是外部 EDC 上游依赖阻塞
  - 当前仓库内没有对应的本地服务定义或可直接启动入口
  - 当前应把它视为“真实上游未恢复”，而不是继续在仓内伪造一个临时 8080 服务
- ASNS 宿主 `npm test` 当前已恢复为稳定最小入口
  - `import.meta.env` / `Invalid URL` 的 Node test 基座问题已收口
  - 仍缺少的是宿主浏览器级自动化入口，而不是模块级单测可运行性

### 建议下一步

1. 先复用当前已恢复的本地基线继续 full review/full test
   - 本地 API 基线：`http://127.0.0.1:8000`
   - 运行副本 API：`http://127.0.0.1:8001`
   - 宿主：`http://127.0.0.1:3001/`
   - 后端最小 pytest：使用 `/home/openclaw/edc-electricity-server/venv/bin/pytest`
2. 然后由 Code X + `review` skill 做 full review/full test
   - 先跑前端/宿主基础验证
   - 再把后端 pytest 从“最小入口可跑”扩到更完整的模块覆盖
   - 然后优先复跑以下真实 acceptance 面：
     - Dashboard 最近炉次 -> Heat Detail
     - Heat Detail 手动调整
     - 生成纠偏任务 -> Task Detail
     - legacy -> canonical URL
     - Heat List 行展开 / CTA
     - Reports 列表 -> 详情
     - Baselines 列表 -> 详情动作
   - 最后汇总未覆盖项、真实阻塞和是否可继续部署/联调
3. 若要进入真实 EDC 上游联调，再单独解决 `127.0.0.1:8080` 外部依赖

> 下面内容保留为历史上下文，不再代表当前“下一步”。

## 当前状态

- 当前阶段：MVP 完成，进入联调整体验收与真实 EDC 替换收口阶段
- 主分支状态：当前 `master` 已比 `origin/master` 超前 `1` 个提交；本轮工作区仍有未提交改动
- 当前工作区：本轮主要是性能收口与超时可观测性补强，相关后端/前端/文档改动均仍在工作区；另保留 2 个未跟踪参考文件不会纳入版本控制
- 当前部署文档：已新增 `docs/DEPLOYMENT.md` 作为统一部署入口；宿主 README 与后端 README 已改为指向该文档
- 已完成交接 issue 1-9、新增 issue 1-3、第二轮联调问题的一轮收口、真实曲线推断炉次第一版、宿主恢复同步、实时数据链路修复、炉次详情 compare 第三刀性能优化，以及 `showtime` 在 Dashboard / 任务 / 报表链路的第二轮统一，并已通过关键回归
- 已继续收 `showtime` 第三轮尾巴：默认模式下的基线向导错误文案已去掉 mock 引导，炉次列表演示 banner 改为仅对明确 demo/mock 来源生效
- 已完成 `showtime` 第四轮尾巴：baseline 详情默认模式不再泄露 demo 曲线，前端残留 `ingestMock` 入口已移除，并补齐 baseline 默认模式 vs `showtime` 的边界回归
- 已完成最近一轮性能收口：
  - Dashboard 首屏慢的主要瓶颈已确认是 `live_inferred` 冷态推断
  - 炉次详情首屏慢的主要瓶颈已确认并收口到 `compare` 冷态链路
  - 已补 compare 子链路共享缓存、配置变更主动失效，以及默认 compare 不再混入额外 draft baselines
- 已新增一版“偶发超时追踪”最小链路：
  - 前端 `client.ts` 已补 `X-Request-ID`
  - 浏览器可从 `window.__ASNS_NETWORK_DIAGNOSTICS__` 读取慢请求/超时诊断
  - 后端已补 request 级 JSON 日志，以及 `compare / heats / realtime / edc get_local_datas` 子步骤耗时
- 已新增 `docs/AI_TIMEOUT_TRACE_GUIDE.md`
  - 供新 session 的 AI 直接按步骤读取前端诊断和后端日志，不必重新摸索这套追踪链路
- 已新增 `docs/DEPLOYMENT.md`
  - 当前 `apps/server`、`apps/web` 与宿主“神经系统”部署说明以该文档为准
  - 宿主参考工程不再按 AI Studio / Gemini 口径说明
- 已完成“宿主为入口、后端统一读取面、EDC 只消费后端状态”的第一阶段页面接入：`/api/settings/runtime-status` 已上线，Header 与 Dashboard / Heat / Baseline 主页面已切到统一运行态摘要
- Heat / Baseline 详情页也已继续接入统一运行态摘要 banner，入口页与详情页的宿主同步提示口径已对齐
- 已继续把统一运行态摘要扩展到 `Tasks / Reports / Inbox` 与相应详情页，主业务导航页已基本切到同一套后端状态读取面
- 已继续把统一运行态摘要补齐到 `BaselineDefinitionListView / SettingsView`，主导航入口页现已全部消费统一运行态摘要
- 已补基线向导 Step 2 的 preview loading 与整日曲线口径提示，避免同日切炉次时误判成“图没刷新”
- 已修基线向导 preview 图的多指标渲染方式：不再先按 timestamp 硬合并，不同指标直接按各自原始时序绘制
- 已收掉 Dashboard 默认模式下的演示统计卡与两块硬编码预览；当前任务/报表默认模式已改为真实派生数据或空态
- 已修复报表详情页“接口 200 但正文长期卡在 loading”问题：前端已拆出成功 / loading / 错误三态，`top_deviations=[]` 与 404 都不会再伪装成 `pending`
- 已完成 `live_inferred` 炉次 ID 稳定化代码修复：后端已改用 canonical ID，并兼容旧 `live-heat-{start}-{end}` 详情链接与基线来源炉次解析；待服务重启后现场验证
- 未纳入版本控制的参考文件：
  - `docs/Ref/EDC AI通信基座API使用說明書.docx`

---

## 已确认决策

### 宿主层 / 应用层边界

- ASNS 宿主层负责：
  - 后台连接
  - 通道同步
  - 通道清单整理与保存
- `EDC electricity` 应用层负责：
  - 从宿主已保存通道中选择来源
  - 给应用内指标命名、绑定、消费
- 不再强行引入“平台标准点位”作为第一版前置模型
- 当前第一版采用：
  - 宿主层：直接维护“已添加通道清单”
  - 应用层：引用宿主通道并允许应用内重命名

### 真实 EDC 替换范围

- 已优先切到真实 EDC 的链路：
  - Dashboard 实时曲线
  - 炉次详情对比
  - 手动调整图
  - 基线详情
  - 基线向导 preview
  - 炉次基础曲线与列表展开预览
- 仍保留 demo/mock 的部分：
  - 炉次异常判定、待分析状态与切割原因仍主要基于本地启发式
  - 当真实推断不可用时的后备炉次记录
  - 任务/报表等非本轮重点模块
  - 仅在显式开启 mock flag 时才允许的演示数据回退
- 新增阶段性方案：
  - 炉次主记录优先走 `live_inferred`
  - `live_inferred` 由真实 EDC 功率历史曲线本地切割推断，不是上游官方炉次台账
  - 基线 preview / 基线实例时间窗 / 炉次详情已兼容这类推断炉次 ID

### 当前服务入口

- 宿主框架：`http://127.0.0.1:3001/`
- 智慧熔炉前端：`http://127.0.0.1:3000/edc/`
- 后端健康检查：`http://127.0.0.1:8000/health`

---

## 最近关键提交

- `3dbfd86` `fix(host): sync selected channels into app backend`
- `3e3e735` `feat(heat): lazy load live heat previews`
- `9dc42f9` `feat(heat): hydrate live heat curves in base flow`
- `0e94e0b` `feat(baseline): drive wizard preview from backend`
- `add1129` `feat(baseline): hydrate baseline curves from live edc`
- `a062007` `feat(server): bind dashboard and heats to live edc history`
- `ea34e94` `feat(dashboard): surface host channel sources in realtime view`
- `1ad5aa1` `feat(heat): surface host channel sources in compare flow`
- `8336102` `feat(baseline): surface host channel bindings in flow`
- `e20ac6d` `feat(baseline): tighten host channel binding flow`
- `a413402` `feat(baseline): bind metrics to host channels`
- `bc58b31` `feat(host): add asns connectivity milestone`

---

## 当前待办

### 本轮刚完成（2026-03-19）

1. 基线向导 Step 2 候选炉次默认限高，超出部分内部滚动
2. 向导底部左侧次操作从“取消”改为“上一页”
3. 基线向导选点图横轴时间粒度改为按分钟显示
4. 炉次浏览移除“模拟流入一炉”按钮及入口
5. 炉次详情可显示新建黄金基线 tab，并保持切换稳定
6. 炉次详情移除“指标来源”模块
7. 新增“默认黄金基线”，炉次偏离度与分析统一按默认基线计算
8. 炉次浏览展开区重排为“左功率 / 中温度 / 右摘要卡”
9. ASNS 宿主框架相关功能入口补齐多语言匹配
10. 宿主 Dock 与桌面区 `EDC electricity` 入口统一切窗逻辑
11. 宿主连线设置在成功登录后持久化在线状态与同步摘要，刷新后自动恢复
12. 全局 mock 数据集改为默认关闭，真实数据失败时返回错误/空态而不是自动回退

### 本轮刚完成（2026-03-20）

1. 基线向导发布成功后会关闭弹窗，且提交中禁用重复点击
2. 基线定义、基线实例、宿主通道、设置与炉次修改类运行态改为落 SQLite，刷新后不再丢失
3. 炉次浏览筛选条件与分页刷新后可恢复，收口“2 条 / 60 条”跳变中的筛选重置因素
4. 待分析炉次详情会返回默认黄金基线 compare tab，不再出现顶部空白 tab 条
5. 炉次列表与炉次详情新增来源说明，可明确区分“演示炉次台账 / 真实 EDC 曲线 / 演示曲线”
6. 已完成真实 EDC 炉次主数据阶段性探测，确认当前基座未暴露炉次台账 request
7. 已落第一版“真实功率曲线推断炉次”，炉次列表优先展示 `live_inferred` 记录
8. 基线 preview / 基线实例时间窗 / 炉次详情与分析已兼容 `live_inferred` 炉次 ID
9. 使用真实 EDC 通道 `2349-199` 实测当前可推断 63 条炉次，最新窗口落在 `2026-03-20 09:01 ~ 09:25`
10. 宿主启动时会自动把本地恢复的连接配置与通道集合回写到 `8000`，并补做一次真实 EDC 连线校验
11. 宿主连线设置页离线态已改为占位显示，不再把旧节点摘要误渲染成“仍像在线”
12. 实测修复后 `GET /api/dashboard/realtime?duration=1h` 已恢复真实实时曲线返回，来源为 `2349-199 / 2349-128`
13. 已完成“炉次浏览 / 基线向导 Step 2 仍拿不到真实数据”原因分析，确认这是多问题叠加，不是单点接口挂掉
14. 已完成“普通接口不再 fallback mock”的第一轮收口，前端本地 mock 拼装已删除，普通接口在真实失败时统一返回错误/空态
15. 已完成炉次详情 compare 第三刀性能优化：去掉重复功率/电压取数，新增 20 秒短 TTL 缓存，并对炉次修改类接口接入缓存失效
16. 已完成基线向导 preview 体验补充：切炉次时显示 loading，并明确提示当前展示的是所选炉次所在自然日整天曲线
17. 已完成基线向导 preview 图修正：不同指标改为各画各的原始 `[timestamp, value]`，解决碎点和“看起来只有总功率有数”问题
18. 已完成 `showtime` 第二轮扩展：任务默认任务库切回真实运行态空库，showtime 才走 seeded mock 任务
19. 已完成报表默认链路去演示：日报列表/详情改为按当前 heat/task store 动态汇总，不再生成 30 天合成日报
20. 已完成 Dashboard 默认模式下的演示 UI 清理：收件箱预览、任务待办、统计卡角标与文案全部改为真实派生或空态
21. `coverage.spec.ts` 已改为确定性桩数据，不再依赖本地运行态一定有日报或特定宿主通道
22. 已完成 `showtime` 第三轮文案收口：基线向导默认模式不再提示用户开启 mock，炉次列表演示来源提示仅在 `showtime=true` 且命中明确 demo/mock 来源时显示
23. 已完成 `showtime` 第四轮收口：`/api/baselines/{id}` 默认模式只允许 `live_edc / none`，showtime 才允许 `demo_curve`
24. 基线详情页已补齐曲线来源说明，且仅在 `showtime=true` 命中 demo 曲线时显示演示 banner
25. 前端残留 `ingestMock` / `ingestMockHeat` 与对应 locale 文案已删除
26. baseline 边界回归已补齐：已验证 showtime 请求不会把 demo 曲线污染回后续默认模式
27. 已完成报表详情 loading 收口：`report` store 新增详情错误态与请求 token，详情页已支持成功 / loading / 错误分支
28. 报表详情回归已补“空 `top_deviations` 成功态”和“接口 404 错误态”，不再只验证“能进入详情页”

### 本轮刚完成（2026-03-21，代码已修复待现场验证）

1. `apps/server/src/api/heats.py` 已把 `live_inferred` 主键从 `live-heat-{start}-{end}` 改为稳定 canonical 格式：`live-heat-{ctx8}-{anchor_ms}-{dur5}`
2. live inference cache 已改为按推断上下文分桶，详情解析不再只认当前 active baseline 的那一份 live store
3. 旧 `live-heat-{start}-{end}` 链接已兼容解析到当前 canonical 记录，`compare / analyze / cutting-timeline` 返回值也会统一回 canonical `heat_id`
4. persisted live heat 若仍保留旧 legacy key，列表与详情会按 alias 合并回当前 canonical 记录，避免已分析状态直接丢失
5. 新建基线时会先解析来源炉次并落 canonical `source_heat_id`
6. baseline preview / baseline 时间窗已优先按定义自身功率通道做 live heat 解析，避免 active baseline 切换后旧 live source 失联
7. 后端回归已通过：
   - `apps/server/.venv/Scripts/ruff.exe check src tests`
   - `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
   - `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
8. 当前额外观察：
   - `apps/server/.venv/Scripts/pytest.exe tests/test_api_edge_cases.py -x -vv` 仍有与本轮无关的既有失败：`test_task_invalid_state_transitions_and_validation`
   - 本地 `http://127.0.0.1:8000/health` 仍是 `200`，但当前运行中的 `8000` 服务尚未热更新到 canonical ID 实现，直接访问 `/api/heats` 仍可见旧 `live-heat-{start}-{end}` 形式

### 当前下一步建议

1. 继续做真实 EDC 联调整体验收，重点走查“宿主在线 -> 创建基线 preview -> 炉次浏览 -> 炉次详情 / 手动调整”的整链路
2. 在“后端统一读取面”基础上继续扩到详情页与其余页面，优先看 BaselineDetail / HeatDetail / Reports / Tasks 是否也要消费统一运行态摘要
3. 继续校准 `live_inferred` 规则，重点关注阈值、长连续段拆分、异常/待分析判定，避免把连续生产长段均分得过于机械
4. 如继续优化性能，可优先关注 `apps/web` 与宿主原型构建中的大 chunk warning
5. 如果下一轮要继续修“炉次浏览拿不到真实数据”，优先顺序应是：
   - 先确认为什么 `settings` 里持久化成了 `live_heat_inference_enabled=false`
   - 再继续拆 `/api/heats` 剩余慢链路，目前已去掉列表级逐条基线 hydrate
   - 最后再修前端错误语义，把“超时/网关失败”和“后端未启动”区分开
6. 如果下一轮继续收炉次详情性能，重点应转向：
   - 继续压 `get_heat_compare()` 首包，当前仍是 `2.8s ~ 3.2s`
   - 评估 `cutting-timeline` 是否要并行缓存或与详情接口再聚合一层
   - 评估是否要把 compare 的短 TTL 响应缓存下沉成更细粒度的 EDC 通道曲线缓存
7. 如果下一轮继续收基线向导体验，重点应转向：
   - 评估 preview 是否仍需要按整日口径，还是改成默认聚焦所选炉次窗口
   - 如果保留整日口径，继续加强当前炉次选区高亮，避免用户只看到“图形主体没变”
8. 下一轮可继续推进的大目标重点：
   - 把统一运行态读取面再沉到需要更细粒度状态的页面（例如是否需要区分“任务页可读但实时链路未就绪”）
   - 评估 `Tasks / Reports` 是否需要单独的业务摘要，而不仅是复用宿主同步就绪态
   - 继续清点是否还有页面仍在本地推断系统状态而非读取 `runtime-status`
9. 若后续还发现零星演示语义，继续按“请求级 showtime、默认模式真实 only”的原则点状清理，不要重新引入页面级 mock 决策
10. 当前大目标下一步建议：
   - 以“宿主为入口、后端统一读取面、EDC 只消费后端状态”为主线，开始做跨页面整链路回归
   - 优先走 `宿主启动 -> 同步 -> 打开 EDC -> Dashboard / Heats / Baseline Definitions / Settings` 的一致性验证
   - 若发现页面仍在本地推断状态，再继续点状下沉到对应 store 或视图

### 已确认的阶段性测试结论

- 当前 EDC 配置可成功登录：`http://60.251.229.32`
- `GET /api/settings` 当前仍能读到 `live_heat_inference_enabled=false`
- `GET /api/heats?page=1&page_size=50` 本地实测耗时约 `43.7s`
- 本轮已收第一刀性能优化：
  - `/api/heats` 列表已不再逐条 `_hydrate_baseline_item()`
  - 重启最新后端后，`GET /api/heats?page=1&page_size=50` 本地实测约 `213ms`
  - 黄金基线向导 Step 2 直接复用该接口，因此这条优化会同步降低候选炉次超时概率
- 本轮已收第二刀性能优化：
  - 前端炉次详情页请求由 `get / getCurve / getCompare / getCuttingTimeline` 收敛到 `getCompare / getCuttingTimeline`
  - 炉次浏览展开预览由 `getCurve + getCompare` 收敛到仅 `getCompare`
  - 这一步主要去掉重复请求；若详情仍慢，后续应继续拆 `getCompare` 本身的后端重链路
- 本轮已收第三刀性能优化：
  - `get_heat_compare()` 已去掉和指标批量取数重复的功率/电压主曲线请求
  - compare 优先复用批量读取的通道曲线回填主曲线，仅在缺失时才单独回退 `_load_heat_curves_from_edc`
  - 同一炉次详情/展开区 20 秒内复开会命中短 TTL compare 缓存
  - `update_heat / resume_cutting / analyze_heat` 已接入 compare cache 失效
  - 本地实测冷启动首包约 `2.8s ~ 3.2s`，同炉次二次请求约 `0.08s ~ 0.14s`
- 本轮已补基线向导 preview 体验说明：
  - `preview-curves` 当前按所选炉次所在自然日整天取数，因此同一天内切换不同炉次时图表主体会高度相似
  - 前端已新增 loading 覆盖层、当前炉次说明和整日预览范围提示
  - 前端已新增请求 token，避免旧 preview 响应覆盖最新选中炉次
- 本轮已修 preview 图的多指标点位组织：
  - 前端不再把多指标先压进统一 `pointMap`
  - 每条 series 直接消费自己的原始 `[timestamp, value]`
  - 图上选点与摘要统计统一改为基于主指标原始点列
- 本轮已新增请求级 `showtime` 模式，作为新的 mock 入口总开关：
  - 前端通过 `apps/web/src/utils/showtime.ts` 统一读取 URL `showtime=true`
  - `apps/web/src/api/client.ts` 统一透传 `X-Showtime: true`
  - `apps/web/src/router/index.ts` 在页面跳转时会保持 `showtime=true`
  - 后端 `apps/server/src/request_mode.py` + `apps/server/src/main.py` middleware 会按请求解析 showtime 模式
  - `apps/server/src/mock_dataset.py` 现在只认当前请求的 showtime，不再用进程级 mock 开关驱动业务入口
- 本轮已把炉次主记录切成“默认真实 only，showtime 才 mock”：
  - 普通 `/api/heats` 默认只返回真实推断炉次
  - 普通 `/api/heats?showtime=true` 会切到 mock 炉次集合
  - `/api/heats/stream/mock*` 现在也要求 `showtime=true`
  - `apps/web/src/views/HeatListView.vue` 只在 `showtime` 模式下显示演示来源提示
- 本轮已把任务/报表/Dashboard 的默认演示口径继续收掉：
  - `apps/server/src/api/tasks.py` 默认任务库已为空，showtime 才切到 seeded mock 任务
  - `apps/server/src/api/reports.py` 已改为按当前 heat/task store 动态汇总日报
  - `apps/web/src/views/DashboardView.vue` 已移除硬编码演示统计、演示收件箱和演示任务卡
  - `apps/web/src/stores/dashboard.ts` 新增真实任务预览抓取，Dashboard 待办卡现在按真实待处理任务派生
- 本轮已补一层默认模式文案与 banner 收口：
  - 基线向导默认模式不再提示“检查 mock 开关 / 开启 mock 数据集”
  - `apps/web/src/views/HeatListView.vue` 只在 `showtime=true` 且命中 `demo_seed / mock_stream / demo_curve / mock_curve` 时显示演示来源 banner
  - 炉次来源文案兜底不再默认落到“演示炉次台账”
  - `apps/web/src/views/HeatDetailView.vue` 的来源映射已与列表页对齐，`mock_stream / mock_curve` 会按明确来源显示，未知值回落为 `none`
- 本轮已补 baseline 默认模式与 showtime 的边界：
  - `apps/server/src/api/baselines.py` 已改为按请求解析基线曲线来源，不再把 showtime demo 曲线写回 `_BASELINE_STORE`
  - 默认模式下 `/api/baselines/{id}` 只允许返回 `live_edc / none`
  - `showtime=true` 时 `/api/baselines/{id}` 才允许返回 `demo_curve`
  - `apps/web/src/views/BaselineDetailView.vue` 已新增曲线来源说明，showtime + demo 时显示演示 banner
  - `apps/web/src/api/heat.ts` 与 `apps/web/src/stores/heat.ts` 已删除无 UI 入口的 `ingestMock` / `ingestMockHeat`
- 本轮新增验证：
  - `apps/server/.venv/Scripts/ruff.exe check src tests`
  - `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - `pnpm --dir apps/web test:i18n`
  - `pnpm --dir apps/web lint`
  - `pnpm --dir apps/web build`
  - `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/coverage.spec.ts e2e/issue-acceptance.spec.ts`
  - `pnpm --dir apps/web lint`
  - `pnpm --dir apps/web test:i18n`
  - `pnpm --dir apps/web build`
  - `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
  - `pnpm --dir apps/web exec playwright test e2e/app.spec.ts -g "can expand a heat row and navigate to detail"`
  - `pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts -g "reports and inbox pages can navigate into detail pages|report detail shows explicit error state when detail request fails"`
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 1 整理：
  - 已新增 `docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md`
  - 已把当前状态源拆成三层：
    - 宿主本地草稿/运行态
    - 后端统一读取面（`_SETTINGS_STORE / _HOST_CHANNEL_STORE / runtime_state`）
    - EDC 业务前端消费层
  - 已明确当前最大的真源冲突：
    - 宿主和 EDC 设置页都能写系统连接配置
    - 连接在线摘要主要还停留在宿主本地，没有后端统一只读视图
  - 下一阶段顺序已固定：
    1. 先补后端统一宿主状态只读视图
    2. 再收掉 EDC 设置页系统连接双写
    3. 再把 `showtime` 扩到全系统
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 2 第一刀：
  - 后端已新增 `GET/PUT /api/settings/host-connectivity-status`
  - `apps/server/src/runtime_state.py` 已持久化 `host_connectivity_status`
  - 宿主现在会把 `配置 + 已选通道 + 连接摘要` 一起回写到后端
  - `tests/test_tasks_reports_settings_api.py` 已不再真实依赖 `localhost:8080`
  - 这意味着后续 EDC 页面已经有条件改成“只读展示宿主统一状态”
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 3 第一刀：
  - EDC `SettingsView.vue` 已不再允许直接测试/保存系统级 `edc-connection`
  - EDC 设置页现在只读展示 `/api/settings` + `/api/settings/host-connectivity-status`
  - 后端已把宿主同步写接口收成专用 header：`X-ASNS-Host-Sync: true`
  - 宿主 `hostConnectivitySync.ts` 已携带该 header 回写 `edc-connection / host-channels / host-connectivity-status`
  - 这一步已经把“宿主写、EDC 读”的边界从 UI 层推进到了接口层
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 4 第一刀：
  - 后端新增 `GET /api/settings/runtime-status`
  - 该接口统一返回：
    - 宿主连接摘要
    - EDC 配置摘要
    - 激活基线摘要
    - 运行模式（`showtime / live_heat_inference_enabled / baseline_length_scope_mode`）
    - `dashboard / heats / baselines` 三条业务链路的统一状态码
  - 前端新增 `apps/web/src/stores/runtimeStatus.ts`
  - `apps/web/src/App.vue` 已在启动、路由切换和 30 秒轮询时刷新统一运行态
  - `apps/web/src/components/layout/AppHeader.vue` 已改为消费统一运行态，不再硬编码“系统运行正常”
  - `apps/web/src/components/common/SystemReadinessBanner.vue` 已接入：
    - `DashboardView.vue`
    - `HeatListView.vue`
    - `BaselineListView.vue`
  - 当前这三处业务页不再各自猜测“宿主是否已同步 / 是否允许真实链路”，统一按 `/api/settings/runtime-status` 渲染提示
  - `HeatDetailView.vue / BaselineDetailView.vue` 也已继续接入同一套统一状态 banner
- 本轮新增验证：
  - `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - `pnpm --dir apps/web lint`
  - `pnpm --dir apps/web test:i18n`
  - `pnpm --dir apps/web build`
  - `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/coverage.spec.ts e2e/issue-acceptance.spec.ts`
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 5 第一刀：
  - 后端 `runtime-status` 已新增：
    - `pipelines.inbox`
    - `pipelines.tasks`
    - `pipelines.reports`
  - `InboxView.vue / TaskListView.vue / TaskDetailView.vue / ReportListView.vue / ReportDetailView.vue` 已接入统一状态 banner
  - `apps/web/e2e/coverage.spec.ts` 已补“Reports 复用统一运行态 banner”回归
  - 目前主业务导航页与主要详情页都已接到统一运行态读取面
- 本轮已完成“宿主入口与 EDC 统一状态收敛”的阶段 6 第一刀：
  - 后端 `runtime-status` 已新增 `pipelines.settings`
  - `apps/web/src/views/BaselineDefinitionListView.vue` 已接 `section="baselines"` 统一 banner
  - `apps/web/src/views/SettingsView.vue` 已接 `section="settings"` 统一 banner
  - `apps/web/src/stores/setting.ts` 已不再额外读取 `/settings/host-connectivity-status`
  - 设置页宿主连接卡现直接读取 `runtimeStatusStore.data.host / edc`
  - `apps/web/e2e/coverage.spec.ts` 已补“baseline definitions and settings pages reuse unified runtime attention state”
  - 基线定义 coverage 用例已补 GET `/api/baseline-definitions` 桩，避免依赖本地后端常驻
  - 当前主导航入口页已全部接入同一套统一运行态读取面
- 本轮验证补充：
  - `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - `npm.cmd run lint`（`apps/web`）
  - `npm.cmd run build`（`apps/web`，提权运行）
  - `npx.cmd playwright test e2e/coverage.spec.ts e2e/app.spec.ts e2e/issue-acceptance.spec.ts`（`apps/web`，提权运行）
  - `apps/server` 的 `pytest` 当前被失效的 uv Python 解释器阻塞，需修复 `.venv` 后再恢复
- 普通 `/api/heats` 已不再默认返回 `demo_seed`；当前 demo/mock 炉次只保留在显式 `/api/heats/stream/mock*`
- 运行态恢复已兼容旧 `runtime_heats`：加载时会自动过滤 `demo_seed/mock_stream`，避免旧脏数据再次进入普通接口
- 基线向导 Step 2 的“未获取到真实炉次候选”来自 `loadHeatCandidates()` 捕获到请求失败，不是正常空列表
- 当前普通接口的 fallback 规则已统一：
  - `dashboard/realtime` 与 `baseline-definitions/*/preview-curves` 不再因为 mock 开关而补本地假数据
  - 前端 store 与 `BaselineWizard` 不再本地生成 mock 列表、详情或 preview 曲线
  - 唯一保留的显式 mock 业务入口是 `/api/heats/stream/mock*`
- 本轮新增验证：
  - `tests/test_heats_api.py` 已覆盖“普通列表为空时不漏出 mock stream”“mock stream 仍独立可用”
  - `tests/test_heats_api.py` 已覆盖“列表接口不得触发 baseline hydrate”
  - `tests/conftest.py` 已改为测试专用 `historical_import` 炉次夹具，不再把 demo seed 当普通主记录前提
- 从本地文档 `docs/Ref/EDC AI通信基座API使用說明書.docx` 提取到的 request 只有：
  - `getAllSensorList`
  - `getLocalDatas`
  - `getMonitorboardToken`
- 使用现网 token 探测 `getHeatList / getHeatRecords / getHeatRecordList / getMeltList / getBatchList` 均返回“未知请求”
- 当前结论：
  - 现有基座支持设备/通道清单与历史曲线读取
  - 现有基座不支持直接读取炉次台账
  - 若后续要替换热次主记录，只能走两条路：上游补接口，或本地基于真实曲线做炉次切割推断
- 已落地的第一版补救方案：
  - 当前默认基线绑定的真实功率通道会被用于拉取最近 72 小时历史曲线
  - 后端已基于动态阈值 + 活跃段分组 + 按期望时长拆分的启发式规则生成 `live_inferred` 炉次
  - 实测当前真实 EDC 上可推断出 63 条炉次，最新时间窗落在 `2026-03-20 09:01 ~ 09:25`
  - 该结果可用于当前 UI 与基线流程联调，但仍需继续调参，不能等同官方台账

---

## 关键文件

### 前端

- `apps/web/src/components/baseline/BaselineWizard.vue`
- `apps/web/src/views/HeatListView.vue`
- `apps/web/src/views/HeatDetailView.vue`
- `apps/web/src/views/BaselineDefinitionListView.vue`
- `apps/web/src/components/baseline/BaselineCard.vue`
- `apps/web/src/stores/baseline.ts`
- `apps/web/src/stores/heat.ts`
- `apps/web/src/api/baseline.ts`
- `apps/web/src/api/heat.ts`
- `apps/web/src/api/client.ts`
- `apps/web/src/api/setting.ts`
- `apps/web/src/stores/setting.ts`
- `apps/web/src/utils/showtime.ts`
- `apps/web/src/router/index.ts`
- `apps/web/src/views/SettingsView.vue`
- `apps/web/src/locales/zh-CN.json`

### 后端

- `apps/server/src/api/heats.py`
- `apps/server/src/api/baselines.py`
- `apps/server/src/api/baseline_definitions.py`
- `apps/server/src/api/dashboard.py`
- `apps/server/src/observability.py`
- `apps/server/src/runtime_state.py`
- `apps/server/tests/test_heats_api.py`
- `apps/server/tests/test_baselines_dashboard_api.py`
- `apps/server/src/config.py`
- `apps/server/src/mock_dataset.py`
- `apps/server/src/request_mode.py`
- `apps/server/src/api/settings.py`
- `apps/server/src/schemas/setting.py`
- `apps/server/src/services/edc_client.py`
- `apps/server/src/schemas/baseline.py`

### 宿主框架

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

### 过程文档

- `docs/progress.md`
- `docs/lessons.md`
- `docs/AI_TIMEOUT_TRACE_GUIDE.md`
- `docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md`
- `docs/ui_issues.md`
- `docs/ASNS_INTEGRATION_PLAN.md`
- `docs/ASNS_HOST_CONNECTIVITY_REDESIGN.md`

---

## 启动与验证

### 常用启动

- 智慧熔炉前端：`pnpm --dir apps/web dev --host 127.0.0.1 --port 3000`
- 后端：`apps/server/.venv/Scripts/python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload`
- 宿主框架：在 `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統` 下运行 `npm run dev`

### 常用验证

- 前端 lint：`pnpm --dir apps/web lint`
- 前端 build：`pnpm --dir apps/web build`
- 前端 E2E：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
- 前端设置页定向回归：`pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts -g "settings page shows host connectivity" e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
- 后端 ruff：`apps/server/.venv/Scripts/ruff.exe check src tests`
- 后端 pytest：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
- 后端回归补充：`apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
- 后端全量：`apps/server/.venv/Scripts/pytest.exe tests -x -vv`
- 当前已知说明：
  - 当前 `apps/server/.venv/pyvenv.cfg` 仍指向失效的 `uv` Python 3.11 路径；本机若未先修复 3.11 运行时，`python.exe / pytest.exe` 可能直接启动失败
  - 本轮“超时追踪”改动已通过 `ruff`、`eslint`、`vue-tsc`、`py_compile`，但后端 pytest 尚未在当前环境补跑
  - `tests/test_tasks_reports_settings_api.py::test_settings_get_and_update` 已改为 monkeypatch `EDCClient.login`，不再真实依赖 `localhost:8080`
- 宿主测试：在 `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統` 下运行 `npm test`
- 宿主类型检查：在 `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統` 下运行 `npm run lint`
- 宿主构建：在 `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統` 下运行 `npm run build`

---

## 新 session 建议开场

1. 先读：
   - `docs/session_handoff.md`
   - `docs/progress.md`
   - `docs/lessons.md`
   - `docs/AI_TIMEOUT_TRACE_GUIDE.md`
2. 确认当前目标：
   - 若是偶发超时/首屏慢，优先按 `AI_TIMEOUT_TRACE_GUIDE.md` 的 request_id 链路追踪
   - 若是一般联调问题，再继续真实 EDC 联调整体验收或整理本轮修复的提交边界
3. 开工前先看：
   - `git status --short --branch`
   - `git log --oneline -12`
