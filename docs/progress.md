# 项目进度跟踪 (Progress)

> 每次会话开始时读取此文件，完成功能后立即更新

---

## 当前状态

**当前阶段**: MVP 完成（联调整体验收收口中）

**当前步骤**: 联调与验收

**进度**: 100%

- [x] 已新增 `docs/session_handoff.md` 作为新 session 的固定交接入口
- [x] 已完成交接 issue 1-9 收口，并补齐默认黄金基线与宿主入口多语言回归
- [x] 已完成宿主 Dock 点击、宿主连线状态持久化、全局 mock 默认禁用 3 项新增问题收口
- [x] 已完成“基线发布重复创建 / 定义与基线刷新丢失 / 炉次筛选刷新跳变 / 待分析炉次缺少基线 tab”一轮收口
- [x] 已补充炉次列表与炉次详情的数据来源说明，页面可区分“演示台账 / 真实曲线 / 演示曲线”
- [x] 已完成 EDC 炉次主数据接口阶段性探测，确认当前基座未暴露炉次台账 request
- [x] 已落第一版“基于真实功率曲线推断炉次台账”，炉次列表可优先展示 `live_inferred` 记录
- [x] 已收口“宿主显示离线 / 从宿主进入 EDC 首屏实时数据 503”两项新增联调问题
- [x] 已完成“炉次浏览 / 基线向导 Step 2 仍拿不到真实炉次”原因分析，确认当前是“真实炉次推断开关关闭 + `/api/heats` 40 秒级慢查询 + 前端 10 秒超时误报”为叠加问题
- [x] 已完成“普通接口 mock fallback 统一收口”第一轮改造：普通接口不再隐式回退 mock，前端不再本地拼接 mock 数据
- [x] 已完成 `showtime` 在 Dashboard / 任务 / 报表链路的第二轮扩展，默认模式下不再展示演示任务、演示日报和 Dashboard 硬编码演示卡片
- [x] 已完成 `showtime` 第三轮文案与来源提示收口，默认模式下不再提示用户开启 mock，炉次列表演示 banner 仅对明确 demo/mock 来源生效
- [x] 已完成 `showtime` 第四轮收口：baseline 详情默认模式不再泄露 demo 曲线，前端残留 `ingestMock` 演示入口已清理，并补齐默认模式 vs `showtime` 的基线边界回归
- [x] 已完成“宿主为入口、后端统一读取面、EDC 只消费后端状态”的第一阶段接入：新增统一运行态摘要接口，Dashboard / 炉次 / 基线主页面已消费统一状态
- [x] 已继续把统一运行态摘要扩到 Tasks / Reports / Inbox 与相关详情页，主业务导航页已基本切到同一状态读取面
- [x] 已继续把统一运行态摘要补齐到基线定义页与设置页，主导航入口页现已全部接到统一运行态读取面
- [x] 已完成 `live_inferred` 炉次 ID 稳定化代码修复：后端改为 canonical ID + legacy 兼容解析；待服务重启后现场验证旧详情链接与基线来源炉次链路
- [x] 已完成宿主子路径部署与同域联通第一轮收口：去掉宿主对 `/assets` 根路径、`127.0.0.1:3000/edc/`、`127.0.0.1:8000/api` 的硬编码依赖，并新增宿主生产服务入口 `server.mjs`
- [x] 已收口“新建黄金基线后炉次浏览看起来空白”问题：确认不是 `/api/heats` 无数据，而是列表页轻量状态未基于基线重算，异常筛选被误空
- [x] 已把当前服务器目录布局、systemd 模板和同步脚本正式收进仓库，后续不再依赖口头命令
- [x] 已统一 ASNS 部署文档口径，区分“代理剥前缀”和“保留前缀”两类运行方式，避免把当前服务器的 `ASNS_BASE_PATH=/` 误写成 `/asns/`
- [x] 已完成第一批 issue 收口：Dashboard 假空态与炉次详情超时后长期 loading 两个 P0 已改为明确错误态，并补 UI 回归

---

## 已完成

### 2026-03-25（第二批 issue：炉次详情状态口径拆分）

- [x] 已按 investigate 顺序完成 `P0 同一炉次在详情页显示“正常”，但在炉次浏览概览中显示“异常”` 的根因定位
  - [x] 已确认这不是后端同一字段算出两套值，而是详情页同时暴露了“偏差状态”和“切割执行状态”两种语义，却只把后者标成了“切割状态”
  - [x] 炉次列表仍按 `status` 展示偏差状态，因此才会出现“列表异常、详情看起来正常”的错觉
- [x] 已完成最小展示层修复
  - [x] `apps/web/src/views/HeatDetailView.vue` 摘要区已新增“偏差状态”并把原“切割状态”明确重命名为“切割执行状态”
  - [x] `apps/web/e2e/issue-acceptance.spec.ts` 已补验收断言，固定验证同一条炉次可同时出现“偏差状态：异常”和“切割执行状态：正常”
  - [x] 多语言文案已同步补齐：`zh-CN / zh-TW / ja-JP / en-US`
- [x] 本轮测试留痕
  - [x] 测试范围：炉次详情摘要状态展示、异常区间与手动调整既有主链路
  - [x] 验证步骤：打开问题炉次详情，检查摘要区状态标签，再继续执行既有 compare / abnormal range / manual adjust 回归
  - [x] 执行命令：`pnpm --dir apps/web lint`
  - [x] 执行命令：`pnpm --dir apps/web exec playwright test e2e/issue-acceptance.spec.ts -g "heat detail renders multi-metric comparison, abnormal ranges, and stable manual adjust interactions"`
  - [x] 结果：均通过；详情页状态语义已拆分，既有热详情关键交互未回归
  - [x] 未覆盖项：本轮未同时处理同页 `cutReason` 技术 key/英文文案问题，该问题仍在 issue 列表中单独保留
  - [x] 下一步：继续处理炉次详情原因文案未翻译与其它仍在线 issue

### 2026-03-25（issue 核对：报表详情 loading 问题确认已收口）

- [x] 已按 investigate 顺序重新核对 `P1 报表详情接口已返回成功，但页面仍长期停留在“加载中”`
  - [x] 代码侧复查确认：当前报表详情成功态与失败态都已有退出 loading 的分支
  - [x] issue 文档已更新为“当前代码无法复现”，避免继续把历史问题当作现状重复修复
- [x] 本轮测试留痕
  - [x] 测试范围：报表列表进入详情页后的成功渲染链路
  - [x] 验证步骤：打开报表列表，进入已有日报详情，确认正文区域可正常显示而非停留 loading
  - [x] 执行命令：`pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts -g "reports and inbox pages can navigate into detail pages"`
  - [x] 结果：通过；报表详情与收件箱详情导航链路正常
  - [x] 未覆盖项：未重放 2026-03-21 现场那组真实后端返回体，仅确认当前 `master` 代码与现有前端回归下无法复现
  - [x] 下一步：继续处理仍在线的炉次详情状态口径不一致问题

### 2026-03-24（第一批 issue：Dashboard 假空态与炉次详情错误态收口）

- [x] 已按 investigate 顺序完成首批 P0 分析与修复
  - [x] 根因确认：Dashboard store 在失败时把统计和最近炉次直接清成 `0 / []`，导致超时被伪装成空数据
  - [x] 根因确认：Heat detail store 缺少独立错误态，请求失败后页面只能继续表现成 loading
- [x] 已完成代码修复
  - [x] `apps/web/src/stores/dashboard.ts` 已新增 `statsError / recentHeatsError`
  - [x] `apps/web/src/views/DashboardView.vue` 已新增仪表盘错误横幅，首轮统计失败时改显示 `--`
  - [x] `apps/web/src/components/dashboard/HeatList.vue` 已新增最近炉次 loading / error 态
  - [x] `apps/web/src/stores/heat.ts` 已新增详情错误态
  - [x] `apps/web/src/views/HeatDetailView.vue` 已新增详情错误页，不再把失败伪装成持续 loading
  - [x] `apps/web/src/utils/apiError.ts` 已统一前端 API 错误文案解析
- [x] 已补多语言文案
  - [x] `apps/web/src/locales/zh-CN.json`
  - [x] `apps/web/src/locales/zh-TW.json`
  - [x] `apps/web/src/locales/ja-JP.json`
  - [x] `apps/web/src/locales/en-US.json`
- [x] 已完成针对性回归
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/loading-error-states.spec.ts`

### 2026-03-24（ASNS 部署文档口径统一）

- [x] 已用当前正式 service 和服务器布局文档反查 ASNS 正确运行口径
  - [x] 当前服务器实际运行仍是：构建 `VITE_ASNS_BASE_PATH=/asns/`，运行 `ASNS_BASE_PATH=/`
  - [x] 根因不是服务配置错误，而是通用部署文档把另一类“保留前缀转发”的写法混成了默认值
- [x] 已修正文档表述
  - [x] `docs/DEPLOYMENT.md` 现已明确按“代理是否剥离 `/asns/` 前缀”区分运行时 `ASNS_BASE_PATH`
  - [x] 已注明当前服务器应以 `docs/SERVER_LAYOUT_AND_SYNC.md` 与 `deploy/systemd/asns-host.service.example` 为准

### 2026-03-24（服务器布局与同步模板入库）

- [x] 已把当前服务器固定路径和同步原则沉淀为仓库内可追踪文件
  - [x] `deploy/systemd/edc-backend.service.example` 已记录 EDC 后端用户态 service 模板
  - [x] `deploy/systemd/asns-host.service.example` 已记录 ASNS 宿主用户态 service 模板
  - [x] `scripts/sync-edc-server.sh` 已固化“主仓 `apps/server` -> 运行副本 `/home/openclaw/edc-electricity-server`”的安全同步流程
  - [x] `scripts/publish-edc-web-and-asns.sh` 已固化“版本化发布 EDC 前端 + 构建并重启 ASNS”的发布流程
- [x] 已更新部署与服务器文档
  - [x] `docs/SERVER_LAYOUT_AND_SYNC.md` 已指向 service 模板与脚本入口
  - [x] `docs/DEPLOYMENT.md` 已补当前服务器的固定执行入口
- [x] 已完成最小校验
  - [x] `bash -n scripts/sync-edc-server.sh`
  - [x] `bash -n scripts/publish-edc-web-and-asns.sh`

### 2026-03-24（炉次浏览状态筛选与空态提示收口）

- [x] 已定位“新建黄金基线后炉次浏览不显示”的直接原因
  - [x] 后端日志确认 `/api/heats` 仍正常返回 live 炉次，不是列表接口挂掉
  - [x] 页面空白时实际请求为 `/api/heats?...&status=abnormal`，当前筛选命中 0 条
  - [x] 已确认新建并发布基线不会自动替换 active baseline；这不是本次空白的直接根因
- [x] 已修复炉次列表轻量口径与筛选口径不一致
  - [x] `apps/server/src/api/heats.py` 现会先为列表批量 hydrate 已用基线，再按当前炉次时间窗重映射基线曲线并重算 `deviation_percent / avg_deviation_percent / status`
  - [x] 列表筛选改为基于重算后的状态执行，`status=abnormal` 不再被旧的轻量状态误空
- [x] 已补前端空态可解释性
  - [x] `apps/web/src/views/HeatListView.vue` 空列表时会明确显示“当前筛选下没有匹配炉次”
  - [x] 已增加一键回到“全部状态 / 清空日期”的重置入口，降低误判为“炉次消失”
- [x] 本地验证结果
  - [x] `apps/server/.venv/Scripts/python.exe -m pytest apps/server/tests/test_heats_api.py -k "test_list_heats_recomputes_status_before_filtering or test_list_heats_filter_by_status"` 通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src/api/heats.py apps/server/tests/test_heats_api.py` 通过
  - [x] `pnpm --dir apps/web lint` 通过
  - [x] `pnpm --dir apps/web build` 通过
  - [x] 现有 `test_heat_list_and_compare_follow_active_default_baseline` 在当前环境仍会碰到既有 SQLite 路径问题：`unable to open database file`，与本次修复无关

### 2026-03-24（炉次详情 live inferred 深链 canonical 路由收口）

- [x] 已定位“同一炉次详情刷新后 compare 视图不稳定”的第一层根因
  - [x] 旧 `live_inferred` URL 会在后端被重新解析到当前最接近的 canonical 炉次
  - [x] 前端详情页此前只消费 `route.params.id`，加载成功后不会把地址替换为后端返回的 canonical `heat_id`
- [x] 已补详情页 canonical 路由同步
  - [x] `apps/web/src/views/HeatDetailView.vue` 现已改为监听路由参数变化统一加载详情
  - [x] 若后端返回的 `current.base.id` 与当前路由 `id` 不一致，前端会立即 `router.replace()` 到 canonical 详情地址，避免用户停留在会漂移的旧 live URL
- [x] 本地验证结果
  - [x] `pnpm --dir apps/web lint` 通过
  - [x] `pnpm --dir apps/web build` 通过

### 2026-03-21（live_inferred 炉次 ID 稳定化代码修复）

- [x] 修复 `live_inferred` 炉次 ID 随重新推断漂移
  - [x] `apps/server/src/api/heats.py` 已把推断炉次主键改为稳定 canonical 格式：`live-heat-{ctx8}-{anchor_ms}-{dur5}`
  - [x] live inference cache 已改为按推断上下文分桶，详情解析不再永远绑死当前 active baseline
  - [x] 旧 `live-heat-{start}-{end}` 链接已可继续解析到当前 canonical 记录，不再直接 `404`
- [x] 收口 canonical ID 在后续链路中的传播
  - [x] `compare / analyze / cutting-timeline / update / resume-cutting` 已统一按 resolved canonical `heat_id` 处理缓存与返回值
  - [x] 已补 persisted live heat alias 合并，运行态残留旧 legacy key 时不会直接丢失已写状态
- [x] 收口基线侧 `source_heat_id` 与时间窗解析
  - [x] 新建基线时会先解析来源炉次并落 canonical `source_heat_id`
  - [x] baseline preview / baseline 时间窗解析已优先使用定义自身的功率通道上下文，不再依赖当前 active baseline
- [x] 后端回归通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
- [x] 额外说明
  - [x] `tests/test_api_edge_cases.py` 仍有与本轮无关的既有失败：`test_task_invalid_state_transitions_and_validation` 当前返回 `404` 而非预期 `400`
  - [x] 本地 `http://127.0.0.1:8000/health` 仍在线，但当前运行中的服务尚未热更新到新的 canonical ID 实现，直接请求 `/api/heats` 仍能看到旧 `live-heat-{start}-{end}` 形式

### 2026-03-23（宿主 `/asns/` 子路径部署与同域联通收口）

- [x] 已定位线上“宿主系统和智慧熔炉系统连不到一起”的根因不是单点故障
  - [x] `https://hopeofthepantheon.me/asns/` 原构建产物仍引用 `/assets/*`，部署到 `/asns/` 后直接 404
  - [x] 宿主前端原先把 EDC 内嵌地址写死为 `http://127.0.0.1:3000/edc/`
  - [x] 宿主同步业务后端原先把 API 地址写死为 `http://127.0.0.1:8000/api`
  - [x] 线上 `runtime-status` 已验证后端在线，但宿主同步摘要仍是 `host_disconnected`
  - [x] 线上 `/asns/host-api/*` 返回 HTML fallback，说明“只发静态文件、不保留宿主 Node 进程”时宿主专用 API 不存在
- [x] 已完成宿主部署侧代码收口
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/vite.config.ts` 已支持 `VITE_ASNS_BASE_PATH`
  - [x] `src/App.tsx` 已改为优先走 `VITE_ASNS_EDC_APP_URL`，默认回退同域 `/edc/`
  - [x] `src/hostConnectivitySync.ts` 已改为优先走运行时/环境变量配置，默认回退同域 `/api` 与按 base 推导的 `host-api`
  - [x] 已新增 `server.mjs`，可在生产环境同时提供宿主静态文件与 `host-api`
  - [x] 已补 `src/vite-env.d.ts`，宿主 TypeScript 现可识别 `import.meta.env`
  - [x] 已更新宿主 `.env.example` 与 `docs/DEPLOYMENT.md` 的 `/asns/ + /edc/ + /api` 部署口径
- [x] 本地验证结果
  - [x] 宿主 `npm run lint` 已通过
  - [x] 宿主在 `VITE_ASNS_BASE_PATH=/asns/` 下 `npm run build` 已通过
  - [x] 构建产物 `dist/index.html` 已确认引用 `/asns/assets/*`
- [ ] 线上待操作
  - [ ] 需按新口径重建宿主前端并以 `ASNS_BASE_PATH=/asns/ npm start` 或等价 Node 进程方式部署，不能只上传静态 `dist`
  - [ ] 重部署后需验证 `/asns/`、`/asns/host-api/edc/test-connection`、宿主内嵌 `/edc/`、以及 `/api/settings/runtime-status` 四条链路

### 2026-03-21（性能定位与第一轮性能收口）

- [x] 已完成 Dashboard / 炉次详情首屏变慢问题的代码级定位
  - [x] 前端调用面确认：Dashboard 首屏固定请求 `runtime-status + stats + realtime + recent-heats + 2 条 tasks`，炉次详情首屏固定请求 `runtime-status + compare + cutting-timeline`
  - [x] 当前未发现炉次详情重新回到 `get + getCurve + getCompare` 的前端重复请求回归
  - [x] 已确认 Dashboard 不是“前端重复发很多次”，而是多个聚合接口在冷态下会各自触发同一轮 live inference 重计算
- [x] 已量化后端热点链路（代码内直测）
  - [x] `_get_live_inferred_heat_store()` 冷态约 `5.36s`，热态约 `0.2ms`
  - [x] `get_heat_compare()` 冷态约 `9.28s`，热态约 `44.4ms`
  - [x] 已确认 compare 短 TTL cache 命中后效果正常，当前主要问题不在 cache key 漂移
- [x] 已确认两个最可能瓶颈并完成低风险修复
  - [x] `apps/server/src/api/heats.py` 已给 live inference cache 增加同 context 的并发去重，避免 Dashboard 冷态并发请求各自重复拉 72 小时功率历史
  - [x] `apps/server/src/api/heats.py` 已改为显式消费 `_hydrate_baseline_item()` 返回值，不再沿用旧的“函数内部回写 store”假设
  - [x] compare 路径的 baseline hydrate 现会把 hydrated 结果在当前请求内复用，不再白做重链路后仍读到空基线曲线
  - [x] `_load_live_heat_inference_power_points()` 已补更稳妥的异常兜底，避免底层连接错误直接把 compare 打成 500
- [x] 回归已通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check src/api/heats.py tests/test_heats_api.py`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -q`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -q`
- [ ] 现场联调待补
  - [ ] 当前本地重启后的 `8000` 运行态仅恢复到 1 条宿主通道，外部 `/api/heats` 现返回空列表，导致无法在“当前重启后的本地服务”上完整复现 issue 文档里的 Dashboard / HeatDetail UI 超时场景
  - [ ] 下一步需在保留真实宿主通道集合的运行态下，再做一次页面级冷启动验证，补齐 `GET /api/heats?page=1&page_size=50`、`GET /api/heats/{id}/compare`、`GET /api/dashboard/realtime?duration=1h` 与首屏前端请求总数的现场值

### 2026-03-21（性能定位第二轮：现场 HTTP 量化与前端轻量去重）

- [x] 已恢复本地联调运行态，补齐页面级与 HTTP 级现场值
  - [x] 通过宿主专用写接口把本地 `host-channels` 恢复为 fallback 8 条关键通道，`def-001` 已重新启用，`/api/heats` 恢复为 52 条 `live_inferred` 记录
  - [x] 已在冷启动进程上单独量化关键接口：
    - [x] `GET /api/heats?page=1&page_size=50` 冷态约 `4746.8ms`，热态约 `133.2ms`
    - [x] `GET /api/heats/{id}/compare` 冷态约 `10433.8ms`，热态约 `39.8ms`
    - [x] `GET /api/dashboard/realtime?duration=1h` 冷态约 `909.9ms`，热态约 `1050.1ms`
  - [x] 已用浏览器实测首屏 API 请求总数：
    - [x] Dashboard 首屏为 6 条：`runtime-status + stats + realtime + recent-heats + 2 条 tasks`
    - [x] HeatDetail 首屏已收口为 3 条：`runtime-status + compare + cutting-timeline`
- [x] 已补一个低风险前端收口点
  - [x] `apps/web/src/App.vue` 已改为单一路由监听触发运行态刷新，不再同时用 `onMounted + watch`
  - [x] `apps/web/src/stores/runtimeStatus.ts` 已补 in-flight + 1 秒短窗去重，避免直达详情页时 `runtime-status` 连续打两次
  - [x] `pnpm --dir apps/web exec eslint src/App.vue src/stores/runtimeStatus.ts` 已通过
- [x] 现场结论已进一步明确
  - [x] Dashboard 首屏慢的主因仍是 live inference 冷态约 4.7-5.3 秒，不是前端重复请求
  - [x] HeatDetail 首屏慢的主因仍是 compare 冷态约 10.4 秒；前端重复请求只剩一个已修掉的轻量 `runtime-status`
  - [x] 当前 `runtime-status` 仍可能在“宿主连接摘要仍是 ready，但已选通道集合不足”时给出误导性 ready，后续可继续收口统一运行态判定口径

### 2026-03-22（性能定位第三轮：compare 冷态深挖与 runtime-status 误判收口）

- [x] 已拆解 `compare` 冷态子步骤并定位真正放大点
  - [x] `_hydrate_compare_baselines()` 旧链路量级约 `9.57s`，`_load_channel_curves_from_edc()` 约 `6.05s`，`_build_metric_curve_series()` 仅毫秒级
  - [x] 已确认 baseline hydrate 的主要放大点不是偏差计算，而是某些 baseline 在 `_resolve_baseline_time_window()` 里拿着无效 `source_heat_id` 继续回退到 live inference
  - [x] 原型验证表明：只要跳过这类无效 source heat 的 live lookup，`compare` 单次耗时可从约 `7.7s` 降到约 `2.4s`
- [x] 已实施低风险后端修复
  - [x] `apps/server/src/api/baselines.py` 已在 `_resolve_baseline_time_window()` 增加快路径：默认真实模式下，若 `source_heat_id` 既不在本地 heat store、也不是 live heat ID，则直接回退最近一小时窗口，不再白跑 live inference
  - [x] `apps/server/src/api/settings.py` 已把 `runtime-status` 的 ready 判定改为基于“后端当前已选且可用于业务的通道”，不再直接信宿主摘要里的 `enabled_channel_count`
- [x] 修复后量化结果
  - [x] 代码内打点显示 `baseline-001 / baseline-002` 时间窗解析已降为 `0ms`
  - [x] `_hydrate_compare_baselines()` 当前约 `1253.7ms`
  - [x] `_load_channel_curves_from_edc()` 当前约 `847.6ms`
  - [x] `get_heat_compare()` 代码内冷态约 `5936.6ms`，热态约 `16.5ms`
  - [x] 外部 HTTP 已验证：当宿主摘要仍上报 `enabled_channel_count=2127`、但后端当前仅保存 1 条电压通道时，`runtime-status` 现返回 `overall_code=no_enabled_channels`
- [x] 回归已通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src/api/baselines.py apps/server/src/api/settings.py apps/server/tests/test_heats_api.py apps/server/tests/test_tasks_reports_settings_api.py`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py tests/test_tasks_reports_settings_api.py -q`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -q`

### 2026-03-22（性能定位第四轮：compare 子链路共享缓存收口）

- [x] 已按 `compare` 子链路补两层短 TTL 共享缓存
  - [x] `apps/server/src/api/heats.py` 已为 baseline hydrate 增加跨请求共享缓存，key 仅使用稳定身份字段、选区与指标绑定，不再重复对白名单内 baseline 做同一轮 hydrate
  - [x] `apps/server/src/api/heats.py` 已为 compare 当前曲线批量读取增加短 TTL 共享缓存与 in-flight 去重，同一时间窗/同一通道集的并发请求不再重复打 EDC
- [x] 已补回归并量化收益口径
  - [x] `tests/test_heats_api.py` 已新增“跨两个不同炉次 compare 复用 baseline hydrate”断言
  - [x] `tests/test_heats_api.py` 已新增“同一通道批量取数并发去重 + TTL 复用”断言
  - [x] 当前代码级收益已确认：
    - [x] 两次不同炉次 compare 共享同一组 baseline 时，baseline hydrate 由每次都跑降为每个 baseline 仅 1 次
    - [x] 两次并发同窗口通道取数时，底层 `get_local_datas` 由 4 次降为 2 次；后续同窗口再读 0 次新增取数
- [x] 回归已通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src/api/heats.py apps/server/tests/conftest.py apps/server/tests/test_heats_api.py`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -q`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -q`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py -q`

### 2026-03-22（性能定位第五轮：compare 配置失效与 draft 口径收口）

- [x] 已确认 compare 剩余两个可修风险并完成最小修复
  - [x] `apps/server/src/api/heats.py` 已新增统一 compare runtime cache invalidation helper；heat 自身修改继续按 heat 维度失效，baseline / host-channel / edc-connection 变更改为整组 compare cache 一次性失效
  - [x] `apps/server/src/api/heats.py` 的 `_resolve_compare_baseline_ids()` 已收紧为“主基线 + 其他已发布基线”，默认 compare 不再额外带 draft baseline
  - [x] `apps/server/src/api/baselines.py` 的 `create / update / publish / disable / delete / activate` 已联动清 compare 相关缓存
  - [x] `apps/server/src/api/settings.py` 的 `host-channels / edc-connection` 更新已联动清 compare 相关缓存
- [x] 已补回归
  - [x] `tests/test_heats_api.py` 已更新默认 compare 口径断言：当前默认样本仅返回 `baseline-001`，不再附带 draft `baseline-002`
  - [x] `tests/test_baselines_dashboard_api.py` 已补 baseline 变更会清 compare caches 的断言
  - [x] `tests/test_tasks_reports_settings_api.py` 已补 `host-channels / edc-connection` 更新会清 compare caches 的断言
- [x] 回归已通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src/api/heats.py apps/server/src/api/baselines.py apps/server/src/api/settings.py apps/server/tests/test_heats_api.py apps/server/tests/test_baselines_dashboard_api.py apps/server/tests/test_tasks_reports_settings_api.py`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py tests/test_baselines_dashboard_api.py tests/test_tasks_reports_settings_api.py -q`

### 2026-03-20（宿主恢复同步与实时数据链路收口）

- [x] 修复宿主恢复后“离线状态与历史摘要并存”的误导展示
  - [x] 宿主启动时会基于已保存草稿自动做一次真实 EDC 连线校验
  - [x] 连线设置页离线态改为占位显示，不再复用旧节点名、旧同步时间和旧通道统计
- [x] 修复从宿主进入 EDC 后 Dashboard 实时数据直接 503
  - [x] 宿主启动时会自动把本地恢复的连接配置与已保存通道集合回写到 `8000`
  - [x] 宿主通道集合补齐推荐的功率/电压关键通道，避免默认基线缺失实时来源
  - [x] 实测 `GET /api/dashboard/realtime?duration=1h` 已恢复真实曲线返回
- [x] 宿主回归通过
  - [x] `npm test`
  - [x] `npm run lint`
  - [x] `npm run build`

### 2026-03-20（联调问题第二轮收口）

- [x] 修复基线发布后弹窗不关闭、重复点击连续创建的问题
  - [x] 基线创建 store 在“创建后立即发布”成功路径下返回明确成功结果
  - [x] 基线向导新增提交中锁定，发布/存草稿/翻页/取消在请求完成前不可重复触发
  - [x] Playwright smoke 覆盖“创建并发布基线”流程仍通过
- [x] 修复基线定义、基线实例、宿主通道与设置刷新后丢失的问题
  - [x] 新增 `apps/server/src/runtime_state.py`，将运行态内存 store 持久化到 SQLite `settings`
  - [x] 应用启动时恢复运行态，避免 dev reload / 页面刷新后回到初始演示状态
  - [x] 基线定义、基线实例、宿主通道、系统设置、炉次修改类写操作已统一接入持久化
- [x] 收口炉次浏览刷新后筛选状态跳变
  - [x] Heat store 持久化 `status / dateRange / page / pageSize`
  - [x] 刷新页面后不再因为筛选状态回到默认值而出现“2 条 / 60 条”无解释切换
- [x] 修复待分析炉次详情缺少默认黄金基线 tab
  - [x] 炉次详情/对比接口改为统一按默认黄金基线解析 `baseline_id / baseline_ids`

### 2026-03-20（真实曲线推断炉次第一版）

- [x] 将炉次列表主记录从“仅 demo seed”推进到“优先使用真实 EDC 功率曲线推断”
  - [x] 后端 `heats.py` 新增真实炉次推断入口，按当前默认黄金基线绑定的功率通道读取最近 72 小时历史曲线
  - [x] 新增启发式切割规则：基于动态阈值识别活跃段，并按定义期望时长对过长连续段做分段
  - [x] 推断出的炉次主记录以 `live_inferred` 来源返回，当前曲线标识为 `live_edc`
  - [x] 若真实推断失败，则回退到现有持久化/demo 炉次记录，不会把空结果误当成功
- [x] 打通推断炉次 ID 在后续链路中的可用性
  - [x] 基线向导 preview 已可接受 `live_inferred` 炉次 ID
  - [x] 基线实例按 `source_heat_id` 解析时间窗时，已兼容推断炉次而不只认 `_HEAT_STORE`
  - [x] 炉次详情 / 对比 / 分析 / 手动修改统一改为通过解析函数读取炉次，避免只认内存 seed
- [x] 前端补齐 `live_inferred` 来源文案与类型
  - [x] 炉次浏览来源标签新增“真实 EDC 推断炉次”
  - [x] 炉次详情来源说明同步支持 `live_inferred`
- [x] 阶段性真实验证完成
  - [x] 使用真实 EDC 通道 `2349-199` 跑第一版推断，当前可稳定推断出 63 条炉次
  - [x] 最新样例已落到 `2026-03-20 09:01 ~ 09:25`、`2026-03-20 08:27 ~ 09:00` 等连续时间窗
  - [x] 当前结果仍属于启发式切割，不等同于上游官方炉次台账
- [x] 回归通过
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`

### 2026-03-20（炉次浏览真实数据问题原因分析）

- [x] 已确认基线向导 Step 2 报“未获取到真实炉次候选”时，失败点来自 `heatApi.list` 请求异常，而不是单纯空列表
  - [x] `apps/web/src/components/baseline/BaselineWizard.vue` 中 `loadHeatCandidates()` 直接调用 `/api/heats?page=1&page_size=50`
  - [x] 该提示只在 `catch` 分支设置，说明前端看到的是超时/失败，不是后端正常返回空数组
- [x] 已确认炉次浏览当前并未稳定走真实炉次主记录
  - [x] `GET /api/settings` 当前持久化值里 `live_heat_inference_enabled=false`
  - [x] `apps/server/src/api/heats.py` 中 `_get_live_inferred_heat_store()` 在开关关闭时直接返回空，`_list_heat_store()` 随后回退到 `_HEAT_STORE`
  - [x] 当前 `GET /api/heats` 实际返回仍包含 `record_source=demo_seed`
- [x] 已确认 `/api/heats` 本身存在 40 秒级性能问题，足以把前端打成“假离线”
  - [x] 本地实测 `GET /api/heats?page=1&page_size=50` 单次耗时约 `43.7s`
  - [x] `apps/server/src/api/heats.py` 的 `list_heats()` 会对分页内每条记录执行 `_build_heat_response_view()`
  - [x] `_build_heat_response_view()` 会进一步调用 `apps/server/src/api/baselines.py` 的 `_hydrate_baseline_item()`，按基线绑定再去 EDC 拉真实曲线
- [x] 已确认前端错误提示会把接口超时误报成“后端未连接”
  - [x] `apps/web/src/api/client.ts` 当前 `timeout` 为 `10000`
  - [x] 同文件中 `error.response` 为空时统一弹出“后端服务未连接，当前页面不会回退为 Mock 数据”
  - [x] 因此用户看到的黄色横幅并不等价于后端服务真的没起
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
  - [x] 待分析炉次也会返回可切换的基线 tab，而不是顶部空白
  - [x] 前端基线 tab 选中态在 compare 数据刷新后保持稳定
- [x] 补充炉次数据来源透明化
  - [x] 热次接口新增 `record_source / current_curve_source / baseline_curve_source`
  - [x] 炉次浏览顶部新增来源说明提示，并在列表项展示当前台账来源标签
  - [x] 炉次详情新增来源说明栏，明确区分“炉次台账 / 当前曲线 / 对比基线曲线”
- [x] 完成真实 EDC 炉次主数据阶段性测试
  - [x] 使用当前配置成功登录 `http://60.251.229.32`
  - [x] 从文档 `EDC AI通信基座API使用說明書.docx` 中提取到的公开 request 只有 `getAllSensorList / getLocalDatas / getMonitorboardToken`
  - [x] 针对 `getHeatList / getHeatRecords / getMeltList / getBatchList` 等候选 request 的现网探测均返回“未知请求”
  - [x] 当前结论：现有 EDC 基座可提供设备清单与历史曲线，但未提供炉次台账接口，暂不具备直接替换热次主记录的条件
- [x] 验证通过
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（普通接口 mock fallback 统一收口）

- [x] 后端普通接口不再按 mock 开关隐式回退
  - [x] `apps/server/src/api/dashboard.py` 的 `/api/dashboard/realtime` 在真实曲线不可用时固定返回 `503`
  - [x] `apps/server/src/api/baseline_definitions.py` 的 `/preview-curves` 在无真实预览点位时固定返回 `503`
  - [x] `apps/server/src/api/baselines.py` 与 `apps/server/src/api/heats.py` 已移除“真实曲线缺失时补本地生成曲线”的分支
- [x] 专用 mock 入口仍保留为显式演示接口
  - [x] `/api/heats/stream/mock`
  - [x] `/api/heats/stream/mock/ingest`
- [x] 前端已移除本地 mock 数据拼装
  - [x] 删除 `apps/web/src/utils/mockDataset.ts`
  - [x] `dashboard / heat / baseline / baselineDefinition / report / task` store 不再在请求失败时本地塞 mock 列表或详情
  - [x] `BaselineWizard.vue` 不再在候选炉次失败或 preview 失败时生成本地假候选和本地图形
- [x] 前端网络错误提示已去掉“会不会回退 mock”的双口径
  - [x] 超时提示改为“请求超时，请检查后端服务状态或接口性能”
  - [x] 断连提示改为“后端服务未连接，请检查网络或服务状态”
- [x] Dashboard 统计与最近炉次列表已去掉硬编码演示值
  - [x] `/api/dashboard/stats` 改为按当前 heat/task store 动态计算
  - [x] `/api/dashboard/recent-heats` 改为复用当前热次列表数据源
- [x] 自动化已同步更新
  - [x] 后端新增断言：mock 开启时普通接口也不得 fallback
  - [x] 前端 E2E 已修正基线向导验收桩与等待条件
- [x] 验证通过
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 当前明确残留

- [ ] `GET /api/heats` 在 `live_heat_inference_enabled=false` 时仍可能返回 `demo_seed` 主记录
  - 这是“炉次主记录真源替换”问题，不再是“普通接口 fallback mock”问题
  - 下一轮如果继续收这条，需要进一步拆分 heat 主 store 与 demo seed store

### 2026-03-19（宿主连接持久化与 mock 回退收口）

- [x] 修复宿主 Dock 中 `EDC electricity` 图标点击无响应
  - [x] Dock 与桌面入口统一复用同一套窗口切换逻辑
  - [x] 补充宿主纯状态测试，覆盖“首次打开”和“已打开聚焦不重复开窗”
- [x] 修复宿主 EDC 登录后刷新回到离线的问题
  - [x] 宿主根层启动时恢复本地保存的连线草稿与在线状态
  - [x] 连线设置页持久化 `isConnected / machineName / lastSync / meta / addedChannelIds`
  - [x] 刷新或重开后可恢复在线态与最近同步摘要
- [x] 收口全局 mock 数据集默认禁用策略
  - [x] 后端新增统一 mock 开关，默认关闭
  - [x] 基线 preview、Dashboard realtime、mock stream 等接口在 mock 关闭时不再偷偷回退
  - [x] 前端 store 与基线向导仅在显式开启 flag 时才允许回退 mock
  - [x] 补齐后端 pytest、前端 Playwright、宿主状态测试
- [x] 验证通过
  - [x] `.\.venv\Scripts\pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`（`apps/server`）
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
  - [x] 宿主原型 `npm test`
  - [x] 宿主原型 `npm run lint`
  - [x] 宿主原型 `npm run build`

### 2026-03-19（交接 issue 1-9 收口）

- [x] 完成基线向导 / 炉次浏览 / 炉次详情 / 宿主入口的 9 项联调问题收口
  - [x] 基线向导 Step 2 候选炉次列表改为默认限高并内部滚动
  - [x] 基线向导次操作按钮改为“上一页”，选点图横轴按分钟粒度展示
  - [x] 炉次浏览移除“模拟流入一炉”入口，展开区重排为“功率 / 温度 / 摘要”三栏
  - [x] 炉次详情移除“指标来源”模块，并保证新增黄金基线可出现在对比 tab 中
  - [x] 新增“默认黄金基线”激活能力，炉次列表偏离度、详情对比与分析统一按默认基线口径计算
  - [x] ASNS 宿主入口补齐应用商店、内嵌应用与 App Studio 的多语言入口文案
- [x] 默认黄金基线口径下沉到后端统一解析
  - [x] `GET /api/baselines/active` 改为真正读取当前激活基线
  - [x] 新增 `POST /api/baselines/{id}/activate` 用于显式设置默认黄金基线
  - [x] 基线发布 / 停用时同步维护默认基线的初始化与回退
  - [x] 热次列表、详情、对比、分析统一复用同一套默认基线解析与 compare 顺序
- [x] 验证通过
  - [x] `.\.venv\Scripts\ruff.exe check src tests`（`apps/server`）
  - [x] `.\.venv\Scripts\pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`（`apps/server`）
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
  - [x] 宿主原型 `npm run build`

### 2026-03-17（智慧熔炉指标引用宿主通道）

- [x] 修复宿主连线设置与智慧熔炉通道候选未联动的问题
  - [x] `/api/settings/host-channels` 改为表达“宿主层已保存通道清单”，不再被全量 EDC 同步结果覆盖
  - [x] 新增 `PUT /api/settings/host-channels`，允许宿主显式保存当前已添加通道集合
  - [x] 宿主 `保存设置` 改为同步写回 EDC 连接配置与已选通道清单，智慧熔炉读取到的候选将与宿主保存结果一致
  - [x] 宿主补充保存失败文案，避免提示裸 key
  - [x] 后端回归新增宿主通道清单保存断言
  - [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] 验证通过：宿主原型 `npm run build`

- [x] 打通宿主已添加通道到智慧熔炉“管理指标”弹窗的最小闭环
  - [x] 后端新增 `/api/settings/host-channels`，返回宿主层已添加通道候选清单
  - [x] 基线定义“管理指标”弹窗新增宿主通道选择器，并按设备分组展示
  - [x] 选择宿主通道后自动带出默认指标名称与单位，且允许在应用内继续修改
  - [x] 指标创建与编辑时写入 `edc_channel_id`，保留后续真实数据绑定入口
  - [x] 现有指标列表补充来源通道摘要回显，便于核对映射关系
- [x] 自动化回归补强
  - [x] 后端测试新增宿主通道列表接口验证
  - [x] 后端测试补充指标 `edc_channel_id` 创建/编辑回归
  - [x] Playwright 覆盖“选择宿主通道 -> 自动填名称/单位 -> 创建指标”流程
- [x] 指标绑定体验继续收口
  - [x] 基线定义卡片补充“已绑定通道 x/y”概览
  - [x] 指标列表补充“未绑定宿主通道”提示
  - [x] 宿主通道选择器过滤当前定义内已占用通道，避免重复绑定
- [x] 验证通过
  - [x] `apps/server/.venv/Scripts/ruff.exe check tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts`
- [x] 宿主通道绑定继续下沉到炉次详情与手动调整
  - [x] 炉次对比接口不再硬编码固定三四个指标，改为按所选黄金基线实例关联的定义动态生成对比指标
  - [x] `GET /api/heats/{id}/compare` 的 `metric_curves` 补充 `edc_channel_id / source_channel_name / source_channel_label`
  - [x] 炉次详情新增“指标来源”面板，直接展示当前对比基线下每个指标是否绑定宿主通道及其来源摘要
  - [x] 手动调整继续复用同一组动态指标与来源元数据，保证与炉次详情主图一致
- [x] Heat compare 回归补强
  - [x] 后端 `test_heats_api.py` 新增动态指标数量与来源字段断言
  - [x] Playwright `issue-acceptance.spec.ts` 新增“指标来源”面板断言
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe apps/server/tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web lint`
  - [x] 验证通过：`pnpm --dir apps/web build`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/issue-acceptance.spec.ts`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`
- [x] Dashboard 开始消费宿主通道绑定摘要
  - [x] `GET /api/dashboard/realtime` 补充当前激活基线与功率/电压宿主来源摘要
  - [x] 总览页实时曲线卡片补充“功率来源 / 电压来源”摘要面板
  - [x] Dashboard 标题文案改为跟随当前激活基线名称
  - [x] 默认基线定义补齐宿主通道绑定，保证总览与炉次详情来源信息一致
- [x] Dashboard 回归补强
  - [x] 后端 `test_baselines_dashboard_api.py` 新增来源摘要断言
  - [x] Playwright `issue-acceptance.spec.ts` 覆盖 Dashboard 来源摘要展示
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe apps/server/tests/test_baselines_dashboard_api.py apps/server/tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web lint`
  - [x] 验证通过：`pnpm --dir apps/web build`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/issue-acceptance.spec.ts e2e/app.spec.ts`
- [x] 真实 EDC 取数开始替换后端 mock 当前曲线
  - [x] 新增 `apps/server/src/services/edc_client.py`，支持登录、设备清单读取、历史曲线读取
  - [x] 设置模块扩展 `edc_username / edc_password`，并让 `/api/settings/edc-connection/test` 走真实登录校验
  - [x] Dashboard `realtime` 接口优先使用绑定功率/电压通道的真实历史曲线，失败时自动回退 mock
  - [x] 炉次详情对比 `metric_curves` 优先使用指标绑定宿主通道的真实历史曲线，失败时自动回退 mock
  - [x] 后端回归新增“Dashboard 优先走真实曲线”和“炉次对比优先走真实当前曲线”测试桩断言
  - [x] 只读实测 EDC 客户端可从 `60.251.229.32` 拉取通道 `2349/199` 最近 15 分钟历史曲线
  - [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web build`
- [x] 基线实例详情开始消费真实 EDC 曲线
  - [x] 基线详情接口按“选区时间 -> 来源炉次时间 -> 最近一小时”顺序解析取数时间窗
  - [x] 基线实例 `curves_data / power_curve / voltage_curve` 优先使用指标绑定宿主通道的真实历史曲线
  - [x] 基线创建与编辑后会立即尝试水合真实曲线，避免详情页首次打开仍停留在纯 mock
  - [x] 后端回归新增“基线详情优先走真实曲线”测试桩断言
  - [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web build`
- [x] 继续收口剩余本地生成链路
  - [x] 宿主通道接口 `/api/settings/host-channels` 改为优先从真实 EDC 同步并缓存，不再只返回固定 8 条示例
  - [x] 基线定义新增 `/api/baseline-definitions/{id}/preview-curves`，按“定义 + 炉次”返回候选预览曲线
  - [x] 基线向导改为使用后端 heat 列表与 preview 曲线接口，不再默认在前端生成全天候选曲线
  - [x] 回归补充：宿主通道同步与基线向导 preview 接口测试
  - [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web lint`
  - [x] 验证通过：`pnpm --dir apps/web build`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`
- [x] 炉次基础曲线进一步切到真实链路
  - [x] `GET /api/heats/{id}/curve` 会优先按炉次主基线绑定的功率/电压宿主通道读取真实 EDC 历史曲线
  - [x] 炉次对比 `metric_curves` 的黄金基线曲线优先复用已水合的真实基线实例曲线，不再一律临时生成
  - [x] 炉次分析 `POST /api/heats/{id}/analyze` 改为复用同一套已水合热次/基线曲线，避免分析仍吃旧 mock
  - [x] 回归补充：炉次基础曲线优先走真实 EDC、炉次对比优先走已水合真实基线曲线
  - [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`
  - [x] 验证通过：`pnpm --dir apps/web build`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`
- [x] 炉次列表展开预览改为懒加载真实曲线优先
  - [x] Heat store 新增按炉次缓存的 preview 曲线
  - [x] 展开炉次行时懒加载 `getCurve + getCompare`，优先展示真实功率/炉温预览
  - [x] 后端不可达或通道无数据时仍保留本地 preview 回退，避免展开交互空白
  - [x] 验证通过：`pnpm --dir apps/web lint`
  - [x] 验证通过：`pnpm --dir apps/web build`
  - [x] 验证通过：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`

### 2026-03-16（ASNS 宿主层接入边界梳理）

- [x] 梳理 ASNS 宿主层与 EDC electricity 应用层职责边界
  - [x] 确认 EDC electricity 将作为 ASNS 应用商店中的已安装应用嵌入
  - [x] 确认系统连接应归属 ASNS 宿主层，而不是本应用重复维护
- [x] 梳理 EDC 网关调用模型
  - [x] 确认 `POST /login` 获取全局 token
  - [x] 确认 `POST /systemcfg` 通过 `request` 指令执行设备发现与历史查询
  - [x] 确认 WebSocket 需额外获取 `monitorBoardToken`
  - [x] 确认历史与实时订阅均依赖 `suid + cuid`
- [x] 形成应用级参数映射方案
  - [x] 推荐配置页位置为 `应用商店 -> 已安装应用 -> EDC electricity -> 配置`
  - [x] 推荐将业务字段映射与系统连接解耦
  - [x] 输出文档 `docs/ASNS_INTEGRATION_PLAN.md`

### 2026-03-16（ASNS 宿主最小串联原型）

- [x] 将当前 EDC electricity 应用接入 ASNS 宿主原型
  - [x] 在 ASNS 宿主桌面与 Dock 中加入 `EDC electricity` 应用入口
  - [x] 在应用商店中加入 `EDC electricity` 卡片入口
  - [x] 在宿主窗口中以内嵌 iframe 方式打开当前 Vue 业务应用
- [x] 本地联调环境串联完成
  - [x] 当前业务应用运行于 `http://127.0.0.1:3000/edc/`
  - [x] ASNS 宿主原型运行于 `http://127.0.0.1:3001/`
  - [x] 已验证宿主窗口中可以加载业务应用首页

### 2026-03-13（炉次详情手动调整复杂交互专项收口）

- [x] 手动调整数据上下文修复
  - [x] 图表与底部滑块从“前后 5 小时局部窗口”改为“当前炉次所在当天完整数据”
  - [x] 黄金基线与当前生产双参考线补齐到全天上下文，避免 tooltip 中基线值缺失
- [x] 手动调整图表结构对齐炉次详情主图
  - [x] 手动调整图按当前激活基线渲染多指标、多单位双组曲线，而不是只显示单一功率曲线
  - [x] 选点只更新当前炉次起止时间与选区，不回写黄金基线曲线
- [x] 手动调整基线切换与默认视窗补齐
  - [x] 弹窗内补齐与炉次详情一致的基线切换 tab
  - [x] 打开手动调整时默认聚焦当前炉次区间，而不是先展示全天全幅视窗
- [x] 手动调整选点与拖动解耦
  - [x] 图表选点改为基于坐标系反算最近时间点，不再依赖普通 `click + dataIndex`
  - [x] 图内拖动/滚轮缩放只更新观察窗口，不再误改起止时间
  - [x] 图表点击、底部滑块、起止时间输入框共享同一组选区状态
- [x] 自动化验收补强
  - [x] Playwright 新增手动调整专项验收：全天上下文、基线数据完整性、图表点击、缩放拖动、输入框联动
  - [x] 手动调整 smoke test 同步更新为“全天上下文”文案
- [x] 验证通过
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web test`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web test:e2e`

### 2026-03-13（基线向导复杂交互专项收口）

- [x] 基线向导选点与拖动冲突修复
  - [x] 图表选点改为基于坐标系反算最近时间点，不再依赖普通 `click + dataIndex`
  - [x] 将图表点击选点与 `dataZoom` 缩放/平移手势解耦，避免拖动时误改起止时间
  - [x] 普通模式与全屏模式共享同一组选区状态与缩放窗口
- [x] 基线向导全屏 UI 同构化
  - [x] 全屏模式补齐与普通模式一致的标题说明、选点区间按钮、起止时间表单结构
  - [x] 全屏内继续支持选起点/选终点与秒级微调
- [x] 基线向导全屏布局按验收截图微调
  - [x] 调整为“图表 -> 选点/时间操作区 -> 统计卡片”的三段式结构
  - [x] 左侧保留选点区间，右侧保留起止时间，底部保留确认按钮
- [x] 自动化验收补强
  - [x] Playwright 新增基线向导专项验收：图表点击、图内拖动、全屏共享状态
  - [x] 基线向导 smoke test 补等待条件，避免异步加载导致误判
- [x] 验证通过
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web test:e2e`

### 2026-03-13（UI 验收问题第一轮收口）

- [x] 联调 issue 台账沉淀
  - [x] `docs/ui_issues.md` 记录 11 条问题，并补充复现步骤、期望结果、测试方法
  - [x] 已为本轮完成项补充“已修复待验收”状态，保留待继续优化项
- [x] Dashboard / 基线向导 / 炉次详情第一轮修复
  - [x] Dashboard 实时曲线范围切换增强，后端 mock 按不同时间范围返回不同点位密度
  - [x] 基线向导起止时间布局改为更易读的纵向输入区
  - [x] 基线向导全屏选点恢复“选起点 / 选终点”按钮
  - [x] 基线向导统计卡补充峰值单位与天/小时/分钟/秒时长格式
  - [x] 炉次详情与基线对比改为多指标双组曲线展示
  - [x] 异常炉次缺失异常区间时补充可展示区间，避免顶部异常但列表为空
  - [x] 手动调整弹窗移除错误的基线选点按钮，并改为图表点击自动更新最近边界
  - [x] 手动调整图补充黄金基线 / 当前生产双曲线参考
  - [x] 异常炉次时间轴最终结论改为与顶部状态一致
- [x] 验证通过
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web test`
  - [x] `pnpm --dir apps/web test:e2e`
  - [x] `apps/server/.venv/Scripts/pytest.exe`
  - [x] `apps/server/.venv/Scripts/ruff.exe check tests`

### 2026-03-12（前端自动化测试接入）

- [x] Web 端接入 Playwright 浏览器级自动化测试
  - [x] 新增 `@playwright/test`、`playwright.config.ts` 与 `test:e2e` 脚本
  - [x] 浏览器安装与本地启动配置完成，可直接运行 `pnpm --dir apps/web test:e2e`
- [x] 首批关键 UI 回归用例落地
  - [x] 基线向导创建并发布
  - [x] 炉次列表展开并跳转详情
  - [x] 炉次详情手动调整弹窗打开并保存
- [x] 自动化覆盖继续扩展到主要页面
  - [x] Dashboard 快捷入口与侧边导航烟测
  - [x] 基线定义创建与指标管理
  - [x] 任务列表跳转详情并完成任务
  - [x] 报表列表/详情与收件箱跳转
  - [x] 设置页 EDC、阈值、报表时间、切割配置保存
- [x] 联调缺陷修复
  - [x] 修复 `HeatDetailView` 手动调整区间 watcher 互相写值导致的递归更新错误
  - [x] 为关键交互补充稳定 `data-testid` 锚点，降低 E2E 脆弱性
  - [x] 修复 `SettingsView` 中表单内原生按钮未声明 `type="button"` 导致的意外 submit 导航
- [x] 验证通过：`pnpm --dir apps/web build`、`pnpm --dir apps/web test`、`pnpm --dir apps/web test:e2e`（8 条全部通过）、`pnpm --dir apps/web lint`（仅剩历史 warning）

### 2026-03-12（后端 API 测试补齐）

- [x] 后端 pytest 覆盖扩展到缺失模块
  - [x] 新增 Dashboard 接口回归测试
  - [x] 新增基线定义 CRUD / 指标管理回归测试
  - [x] 新增基线实例创建 / 发布 / 停用 / 删除回归测试
- [x] 测试稳定性补强
  - [x] 为后端全局 in-memory store 增加自动重置 fixture，避免测试顺序互相污染
- [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe`（15 条全部通过）
- [x] 验证通过：`apps/server/.venv/Scripts/ruff.exe check tests`

### 2026-03-12（后端错误分支测试扩展）

- [x] 新增 API 错误分支与边界场景测试
  - [x] Dashboard 非法参数返回 422
  - [x] 基线定义启停非法状态转换、缺失指标 404
  - [x] 基线实例非法发布/停用/校验失败路径
  - [x] 任务完成/取消/编辑的非法状态转换
  - [x] 设置页参数校验与非法 scope_mode 返回
  - [x] 炉次不存在与非法查询参数返回
- [x] 验证通过：`apps/server/.venv/Scripts/pytest.exe`（21 条全部通过）

### 2026-03-12（测试工程化收口）

- [x] 新增仓库级一键检查脚本 `scripts/check-all.ps1`
  - [x] 串联前端 lint/build/unit/e2e
  - [x] 串联后端 tests lint/pytest
  - [x] 支持 `-SkipE2E` 快速检查
- [x] 新增多语言回归检查
  - [x] 新增 `scripts/check-i18n-locales.mjs`，校验 locale key 结构一致性
  - [x] 新增占位符一致性校验，避免 `{count}` 等变量漂移
  - [x] 接入 `apps/web` 的 `pnpm test:i18n`
  - [x] 接入 `check-all.ps1`、`check-all.sh` 与 GitHub Actions
- [x] 新增 `docs/testing.md`
  - [x] 记录当前测试覆盖范围
  - [x] 记录一键执行方式与维护约定
- [x] 新增 GitHub Actions 工作流 `.github/workflows/ci.yml`
  - [x] 前端云端执行 lint/build/unit/e2e
  - [x] 后端云端执行 tests lint/pytest
  - [x] Playwright 失败产物自动归档
- [x] 新增 Linux / Codex cloud 检查脚本 `scripts/check-all.sh`
  - [x] 与 Windows 版一键检查保持相同回归口径
  - [x] `docs/testing.md` 补充 Codex cloud setup script 与执行方式

### 2026-03-13（前端 lint warning 收口）

- [x] 批量清理历史 Vue 模板格式 warning
  - [x] 通过 `eslint --fix` 收口可自动修复的模板/属性/缩进问题
  - [x] 前端 `pnpm lint` 当前无 error、无 warning
- [x] Playwright 稳定性补强
  - [x] 手动调整弹窗 smoke test 改为等待 `data-testid`
  - [x] 基线向导 smoke test 改为显式等待发布按钮出现
- [x] 验证通过：`pnpm --dir apps/web lint`、`pnpm --dir apps/web build`、`pnpm --dir apps/web test`、`pnpm --dir apps/web test:e2e`

### 2026-03-12（UI 联调问题修复）

- [x] 新建基线向导联调修复
  - [x] 步骤顺序调整为“设置基线 / 选择炉次与选点 / 确认发布”
  - [x] 选点图按基线定义渲染多曲线，并支持长时间轴平移缩放
  - [x] 图上选点、时间输入框、全屏弹窗状态统一
  - [x] 修复向导步骤高亮不同步
- [x] 炉次浏览与详情页交互修复
  - [x] 炉次列表新增行展开简要视图与完整报告入口
  - [x] 炉次详情移除错误的基线选点按钮
  - [x] 炉次详情新增“手动调整”弹窗，支持前后 5 小时窗口重划区间
  - [x] 右侧信息面板限制为仅编辑描述，不再直接编辑时间
- [x] 全局联调体验修复
  - [x] 左侧导航栏菜单顺序调整
  - [x] API 客户端默认前缀纠正为 `/api`
  - [x] 后端未启动时全局报错改为单次提示，避免页面切换刷屏
- [x] 工程化补充
  - [x] 新增项目内 UI 联调修复 skill：`.agent/skills/ui-regression-fix/SKILL.md`
  - [x] 验证通过：`pnpm --dir apps/web build`、`pnpm --dir apps/web test`、`pnpm --dir apps/web lint`（仅剩历史 warning）

### 2026-02-23（基线向导调整）

- [x] 基线向导改为 3 步（选炉次+选点 / 参数设置 / 确认发布）
- [x] Step1 使用全天完整曲线并支持选点微调与全屏同步

### 2026-02-11（联调推进）

- [x] 黄金基线定义模块落地
  - [x] 新增黄金基线定义后端 API 与前端页面
  - [x] 新增定义级指标管理（名称/单位/颜色）
- [x] 黄金基线实例模型升级
  - [x] 实例关联定义（definition_id）
  - [x] 新增动态曲线结构（curves_data），保留旧字段兼容
  - [x] 新建基线向导支持“基线定义”选择
- [x] 炉次多黄金基线对比
  - [x] 对比接口支持返回多基线结果数组
  - [x] 炉次详情页支持 Tab 切换多基线对比
- [x] 炉次切割与重大事故演示能力
  - [x] 新增切割设置（时间容忍率、重大事故阈值、班次/休息）
  - [x] 新增 mock 实时流入接口
  - [x] 炉次列表/详情展示切割状态与时间偏移
  - [x] 手动编辑炉次时间并可选择自动调整后续炉次
  - [x] Demo 两组数据：时间偏移可控+数值偏差、重大事故后阻断
- [x] 联调性能优化（前端）
  - [x] vite manualChunks 分包（vue/elementPlus/echarts）
  - [x] 移除全量 Element Plus 图标全局注册
  - [x] 产物验证：分包生效，构建通过
- [x] 前端类型系统收敛
  - [x] API client 统一返回数据类型（消除 AxiosResponse 级联类型问题）
  - [x] 修复 baseline/heat/task/report 等模块 TS 类型错误
  - [x] 验证通过：`vue-tsc --noEmit`、`pnpm build`
- [x] 基线创建交互补全（图上选点）
  - [x] 向导支持图上点击选择起止点
  - [x] 支持秒级时间微调（±1s）
  - [x] 支持图表全屏选点
  - [x] 提交时携带选点起止时间到基线实例创建接口
- [x] 炉次切割恢复闭环补全
  - [x] 新增恢复切割接口 `POST /api/heats/{id}/resume-cutting`
  - [x] 炉次详情新增“恢复切割”操作并支持是否联动后续炉次
  - [x] 炉次列表新增重大事故/阻断提示信息

### 2026-02-12（连续迭代轮次）

- [x] 第1轮：后端切割判定增强
  - [x] 增加连续不一致分钟字段与切割原因字段
  - [x] 增加班次标签（作业/休息/班次外）
  - [x] 按切割配置阈值触发重大事故并锁定后续炉次
- [x] 第2轮：前端炉次切割可视化增强
  - [x] 炉次列表展示班次标签、连续不一致分钟、切割原因
  - [x] 炉次详情展示切割原因与班次窗口信息
  - [x] 四语种文案补齐
- [x] 第3轮：炉次详情到基线创建连贯性增强
  - [x] 炉次详情图上选择基线起止点
  - [x] 一键带着选区跳转到基线向导并自动预填
  - [x] 基线向导支持预填炉次、预填选区、预填实例名
- [x] 第4轮：切割可解释性增强
  - [x] 新增切割时间轴接口 `GET /api/heats/{id}/cutting-timeline`
  - [x] 切割状态新增连续不一致分钟/班次标签/切割原因字段
  - [x] 炉次详情展示切割判定时间轴
- [x] 第5轮：切割流程可操作增强
  - [x] 新增 mock 实时流入接口 `POST /api/heats/stream/mock/ingest`
  - [x] 炉次列表增加“模拟流入一炉”触发入口
  - [x] 设置页新增“基线等长校验范围”配置（定义/系统/生产线预留）

### 2026-02-09

- [x] 创建项目目录结构
- [x] 创建 AGENTS.md 主配置文件
- [x] 创建 opencode.json 配置
- [x] 创建规范文档体系
  - [x] PRD.md - 产品需求文档
  - [x] TECH_STACK.md - 技术栈文档
  - [x] APP_FLOW.md - 应用流程文档
  - [x] FRONTEND_GUIDELINES.md - 前端规范
  - [x] BACKEND_STRUCTURE.md - 后端结构
  - [x] IMPLEMENTATION_PLAN.md - 实施计划
  - [x] progress.md - 进度跟踪（本文件）
  - [x] lessons.md - 经验教训
- [x] Step 1.1 项目初始化
  - [x] 安装 pnpm 包管理器 (v10.29.2)
  - [x] 创建前端项目 (Vue 3.5 + Vite 7 + TypeScript 5.9)
  - [x] 配置 Tailwind CSS 3.4 + Element Plus 2.13
  - [x] 配置 vue-i18n 11.2 (zh-CN/en-US/zh-TW/ja-JP)
  - [x] 配置 ESLint 9 + Prettier 3.8
  - [x] 创建后端项目 (FastAPI 0.114 + SQLAlchemy 2.0)
  - [x] 配置 Ruff 0.15 (Python linter/formatter)
  - [x] 配置 Python 3.11.13 虚拟环境 (uv)
  - [x] 初始化 Git 仓库
  - [x] 创建路由配置和视图占位文件
  - [x] 前端构建验证通过
- [x] Step 1.2 基础布局
  - [x] 更新 tailwind.config.js 添加设计令牌（颜色、间距、阴影）
  - [x] 创建 AppSidebar.vue（可折叠导航菜单，7个导航项）
  - [x] 创建 AppHeader.vue（页面标题、系统状态、搜索、通知）
  - [x] 创建 PageContainer.vue（页面内容容器）
  - [x] 创建 AppLayout.vue（主布局组件，响应式支持）
  - [x] 更新 App.vue 使用 AppLayout
  - [x] 前端构建验证通过
- [x] Step 1.3 后端基础
  - [x] 配置数据库连接（SQLite）
  - [x] 创建基础模型（Baseline, Heat, Task, Setting）
  - [x] 配置 Alembic 迁移
  - [x] 创建 API 路由框架
  - [x] 实现健康检查接口
- [x] Step 1.4 Dashboard 页面
  - [x] 创建统计卡片组件 (StatCard)
  - [x] 实现 Mock 数据服务
  - [x] 创建实时曲线图组件 (RealtimeChart)
  - [x] 实现时间范围选择（5分钟/1小时/6小时/全天）
  - [x] 创建最近炉次列表组件
- [x] Step 2.1 基线列表页
  - [x] 创建基线卡片组件 (BaselineCard)
  - [x] 实现基线列表页面
  - [x] 实现状态筛选（草稿/已发布/已停用）
  - [x] 前端基线 API 模块与 Store（含 Mock 回退）
- [x] Step 2.2 新建基线向导
  - [x] 创建向导组件框架 (BaselineWizard)
  - [x] Step 1: 候选炉次选择（日期范围、炉次选择、曲线预览）
  - [x] Step 2: 预览对比（基线与当前曲线、统计信息）
  - [x] Step 3: 设置参数（名称、容许误差、描述）
  - [x] Step 4: 发布确认（保存草稿/发布）
- [x] Step 2.3 基线详情页
  - [x] 基线信息展示
  - [x] 曲线图展示
  - [x] 版本历史
  - [x] 编辑/停用/创建新版本操作
- [x] Step 2.4 基线 API
  - [x] GET /api/baselines
  - [x] GET /api/baselines/{id}
  - [x] POST /api/baselines
  - [x] PATCH /api/baselines/{id}
  - [x] POST /api/baselines/{id}/publish
  - [x] POST /api/baselines/{id}/disable
  - [x] DELETE /api/baselines/{id}
- [x] Step 3.1 炉次列表页
  - [x] 创建炉次列表组件
  - [x] 实现日期范围筛选
  - [x] 实现偏差状态筛选（正常/异常/待分析）
  - [x] 实现分页
- [x] Step 3.2 炉次详情页
  - [x] 炉次基本信息
  - [x] 曲线对比图（与黄金基线叠加）
  - [x] 异常区间红色高亮
  - [x] 偏差分析结果展示
  - [x] 生成纠偏任务入口
- [x] Step 3.3 偏差分析服务
  - [x] 实现曲线对齐算法
  - [x] 实现偏差计算逻辑
  - [x] 实现异常区间识别
  - [x] 单元测试（3项通过）
- [x] Step 3.4 炉次 API
  - [x] GET /api/heats
  - [x] GET /api/heats/{id}
  - [x] GET /api/heats/{id}/curve
  - [x] GET /api/heats/{id}/compare
  - [x] POST /api/heats/{id}/analyze
- [x] Step 3.5 Mock 数据完善
  - [x] 生成模拟炉次数据（正常/异常/待分析）
  - [x] 生成模拟曲线数据
  - [x] API 测试覆盖（heats API + deviation service）
- [x] Step 4.1 任务列表页
  - [x] 任务列表
  - [x] 状态筛选（待处理/处理中/已完成/已取消）
  - [x] 分页
- [x] Step 4.2 任务详情页
  - [x] 关联炉次信息
  - [x] 偏差信息展示
  - [x] 原因分析/改善方法/预防对策表单
  - [x] 保存与完成提交流程
- [x] Step 4.3 任务 PDF 导出
  - [x] 后端任务 PDF 导出接口可下载
  - [x] 前端导出入口
- [x] Step 4.4 任务 API
  - [x] GET /api/tasks
  - [x] GET /api/tasks/{id}
  - [x] POST /api/tasks
  - [x] PATCH /api/tasks/{id}
  - [x] POST /api/tasks/{id}/complete
- [x] Step 4.5 日报系统
  - [x] 日报列表页
  - [x] 日报详情页
  - [x] 日报 PDF 导出接口与前端入口
  - [x] GET /api/reports/daily
  - [x] GET /api/reports/daily/{date}
  - [x] GET /api/reports/daily/{date}/pdf
- [x] Step 4.6 系统设置
  - [x] 设置页面
  - [x] 容许误差设置
  - [x] EDC 连接配置（含测试连接）
  - [x] 报表生成时间设置
  - [x] GET /api/settings
  - [x] PATCH /api/settings
- [x] Step 4.7 偏差收件箱（简化版）
  - [x] 偏差收件箱列表页
  - [x] 查看偏差详情（跳转炉次详情）
- [x] Step 1.5 Dashboard API 前后端联调验证
  - [x] /api/dashboard/stats
  - [x] /api/dashboard/realtime
  - [x] /api/dashboard/recent-heats

### 2026-03-11（UI 规范统一与打磨）
- [x] 全局设计令牌 (Design Tokens) 引入 (色彩 `#1152d4`, 字体 `Noto Sans`, 阴影圆角)
- [x] 整体布局框架升级 (侧边栏导航分组, 头部原生化, UI 响应式容器优化)
- [x] Dashboard 各组件重制 (彩条 StatCard, 快速导航 QuickLinks, 原生表格 HeatList)
- [x] 通用组件沉淀 (`PageHeader`, `Breadcrumb`, `StatusBadge`) 替代 Element 原有旧组件
- [x] 全量列表页 (`BaselineList`, `HeatList`, `TaskList`, `ReportList`, `Settings`) 翻新，统一使用 Tailwind CSS Card
- [x] 全量详情页 (`BaselineDetail`, `HeatDetail`, `TaskDetail`, `ReportDetail`, `InboxView`) 深度布局重做与图表 UI 升级
- [x] 修复因重构带来的所有 TypeScript 未使用变量报错，确保 `Exit code: 0` 纯净构建

### 2026-03-16（ASNS 宿主串联与连线设置原型）
- [x] 输出 `ASNS_INTEGRATION_PLAN.md`，明确宿主层负责系统连接、应用层负责业务字段映射
- [x] 将 `EDC electricity` 作为宿主原型中的应用商店应用、桌面图标和 Dock 入口接入
- [x] 在宿主中以内嵌窗口方式打开当前 Vue 业务应用，完成页面串联
- [x] 只读验证 EDC 测试机 `60.251.229.32` 的登录、设备清单、历史数据查询调用链
- [x] 宿主 `连线设置` 页面升级为两段式原型：
  - [x] API 连接区：URL、账户名、密码、连接状态、最近同步、节点信息
  - [x] 通道 Mapping 区：左侧可搜索分组来源目录，右侧固定业务字段槽位
- [x] 宿主层新增多语言文案，覆盖连接与 Mapping 原型页
- [x] 将宿主中的 Mapping 来源从 mock 候选通道替换为测试 EDC 机器的真实只读清单快照（26 台设备 / 2286 通道）
- [x] 宿主默认语言切换为简体中文
- [x] 宿主新增 `/host-api/edc/test-connection` 与 `/host-api/edc/sync-channels` 两个真实联调接口
- [x] 宿主 Mapping 工作台改为三栏式：左侧来源目录 / 中间通道详情 / 右侧映射目标
- [x] 修正宿主原型 `dev` 脚本端口为 `3001`，避免与业务前端 `3000` 冲突；宿主页恢复可访问
- [x] 宿主原型构建与 TypeScript 校验通过（`vite build` / `tsc --noEmit`）
- [x] 基于用户验收反馈，重新梳理宿主层与应用层的绑定边界
  - [x] 明确宿主层 `连线设置` 不应直接出现 `EDC electricity` 的业务字段
  - [x] 输出 `docs/ASNS_HOST_CONNECTIVITY_REDESIGN.md`，总结“原始通道 -> 平台级标准点位 -> 应用业务字段”两级绑定模型
  - [x] 沉淀大量通道绑定的推荐 UI 实践：筛选栏 / 结果表 / 详情动作面板，而不是纯树状逐项点选
 - [x] 宿主 `连线设置` 原型改为平台级标准点位绑定
  - [x] 右侧工作台从 `EDC electricity` 业务字段槽位改为“平台级标准点位”
  - [x] 左侧与中间区的提示文案改为宿主级语义，不再暗示应用字段映射
  - [x] 选中通道详情补充“已绑定标准点位”摘要
  - [x] 验证通过：宿主原型 `vite build` / `tsc --noEmit`
 - [x] 基于最新交互讨论，将宿主原型进一步改为“硬件通道直接添加”
  - [x] 取消当前页的标准点位预置逻辑，改为直接把硬件通道加入宿主层采集清单
  - [x] 左侧设备组支持“整组添加”，单条通道支持“逐条添加”
  - [x] 右侧改为“已添加通道清单”，按设备分组展示，并支持单条/整组移除
  - [x] 设备组与已添加组均补充明显标题，避免长列表滚动后内容失去上下文
  - [x] 验证通过：宿主原型 `vite build` / `tsc --noEmit`
 - [x] 宿主 `连线设置` 进一步收敛为两栏布局
  - [x] 删除中间“当前选中通道”栏位，避免重复信息占位
  - [x] 左栏保留硬件通道目录与直接添加操作
  - [x] 右栏保留已添加通道清单与分组移除操作
  - [x] 验证通过：宿主原型 `vite build` / `tsc --noEmit`
 - [x] 宿主 `保存草稿 / 保存设置` 接入最小持久化能力
  - [x] 使用本地存储保存连接配置与已添加通道清单
  - [x] 页面重开时自动恢复最近一次草稿
  - [x] 保存与恢复动作会给出明确状态反馈
  - [x] 保存按钮旁补充就地成功提示，避免用户必须回看顶部状态区才知道已保存
  - [x] 验证通过：宿主原型 `vite build` / `tsc --noEmit`
 - [x] 智慧熔炉基线流程开始消费宿主通道绑定元数据
  - [x] 基线向导 Step 1 显示每个指标的宿主通道绑定状态，并提示未绑定指标
  - [x] 基线向导确认页显示当前定义的绑定覆盖率与未绑定提醒
  - [x] 基线详情新增“指标来源”信息卡，展示每条曲线的宿主通道来源摘要
  - [x] 基线详情接口 `curves_data` 补充 `edc_channel_id / source_channel_*` 元数据，避免后续真实取数时再改结构
  - [x] 验证通过：`pytest apps/server/tests/test_baselines_dashboard_api.py`、`pnpm --dir apps/web lint`、`pnpm --dir apps/web build`、`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`

### 2026-03-20（炉次主记录源头切真：普通接口与 mock stream 拆分）
- [x] `apps/server/src/api/heats.py` 拆分普通炉次主记录 store 与显式 mock stream store
- [x] 普通 `/api/heats*`、详情、分析、恢复切割只消费真实推断记录与持久化 overlay，不再默认暴露 `demo_seed`
- [x] 显式 mock 仅保留在 `/api/heats/stream/mock*`，并单独维护 `mock_stream` 记录与自增索引
- [x] `apps/server/src/runtime_state.py` 运行态持久化新增 `mock_heats`，并在恢复旧 `runtime_heats` 时自动过滤 `demo_seed/mock_stream`
- [x] 后端测试夹具改成“测试专用 historical_import 炉次”，不再默认依赖 demo seed 作为普通接口前提
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（炉次列表性能第一刀：移除列表级基线 hydrate）
- [x] `/api/heats` 列表改为轻量 summary view，不再在列表请求里逐条 `_hydrate_baseline_item()`
- [x] 列表仍保留默认基线 ID、来源字段和本地可算的偏差值，但把重 IO 留给详情/对比接口
- [x] `GET /api/heats?page=1&page_size=50` 本地实测由 30 秒级降到约 `213ms`
- [x] 基线向导 Step 2 继续复用 `/api/heats`，因此本轮性能优化会直接影响黄金基线候选炉次加载
- [x] 新增回归：`test_list_heats_does_not_hydrate_baselines`
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（炉次详情性能第二刀：前端去重重复请求）
- [x] 炉次详情页从 `get / getCurve / getCompare / getCuttingTimeline` 四请求收敛为 `getCompare / getCuttingTimeline` 两请求
- [x] 炉次浏览展开预览从 `getCurve + getCompare` 两请求收敛为仅 `getCompare`
- [x] 保持详情页多基线对比、异常区间、手动调整和展开区预览能力不变
- [x] 验证通过：
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（炉次详情性能第三刀：compare 去重取数与短 TTL 缓存）
- [x] `apps/server/src/api/heats.py` 的 `get_heat_compare()` 去掉与指标批量取数重复的功率/电压主曲线 EDC 请求
- [x] compare 链路优先复用已批量读取的通道曲线回填主曲线，仅在缺失时才回退单独 `_load_heat_curves_from_edc`
- [x] 新增 20 秒级炉次 compare 响应缓存，同一炉次短时间重复打开详情/展开区时不再重复 hydrate 基线和拉 EDC 曲线
- [x] `update_heat / resume_cutting / analyze_heat` 已接入 compare 缓存失效，避免炉次修改后继续命中旧响应
- [x] 后端测试夹具新增 compare cache 隔离，避免跨用例污染
- [x] 实测效果：
  - [x] 冷启动首包 `GET /api/heats/heat-007/compare` 约 `3.2s`
  - [x] 同炉次二次请求约 `0.08s`
  - [x] 冷启动首包 `GET /api/heats/heat-008/compare` 约 `2.8s`
  - [x] 同炉次二次请求约 `0.14s`
- [x] 新增回归：
  - [x] `test_heat_compare_reuses_short_ttl_cache`
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`

### 2026-03-20（基线向导体验补充：preview loading 与整日曲线口径提示）
- [x] 已确认“切换不同炉次图形看起来不变”不是单纯前端未刷新
  - [x] `baseline-definitions/{id}/preview-curves` 当前按所选炉次所在自然日整天取数
  - [x] 同一天内切换不同炉次时，图表主体会高度相似，真正变化的是默认选区时间窗
- [x] `apps/web/src/components/baseline/BaselineWizard.vue` 新增 preview loading 状态
  - [x] 切换炉次或定义时，图表区域会显示“正在加载所选炉次预览曲线...”
  - [x] 新增请求 token，避免旧 preview 结果晚到后覆盖新选中炉次
- [x] 基线向导图表区新增当前炉次时间窗与整日预览口径提示
  - [x] 明确显示“当前炉次：...”
  - [x] 明确显示“当前预览展示所选炉次所在自然日整天曲线：...”
- [x] i18n 已同步补齐 `zh-CN / zh-TW / ja-JP / en-US`
- [x] 实测当前较连续的测试通道：
  - [x] `2349-199` 总有功功率
  - [x] `2349-128` A相电压
  - [x] `2349-142` A相有功功率
  - [x] `2349-130` B相电压
  - [x] 次连续：`2054-128`、`2066-128`、`769-128`
- [x] 验证通过：
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`

### 2026-03-20（基线向导 preview 图修正：多指标按原始时间序列直绘）
- [x] 已确认 preview 图出现“零星碎点”不是上游没数据，而是前端把不同指标按完全相同 timestamp 硬合并导致大量点位对不上
- [x] `apps/web/src/components/baseline/BaselineWizard.vue` 已改为每条 series 直接使用各自原始 `[timestamp, value]`
- [x] 图上选点改为优先吸附主指标原始点，不再依赖跨指标合并后的 `pointMap`
- [x] 统计卡（平均/峰值/时长）改为基于主指标原始曲线计算，避免跨指标混点
- [x] 当前效果：
  - [x] 功率/电压类高频通道会恢复连续曲线
  - [x] 温度类低频通道保留其原本较稀疏的采样特征
- [x] 验证通过：
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`

### 2026-03-20（showtime 请求级切换：默认真实 only，显式 showtime 才允许 mock）
- [x] 已新增请求级 `showtime` 模式
  - [x] 后端新增 `apps/server/src/request_mode.py`
  - [x] `apps/server/src/main.py` 新增 middleware，从 query/header 解析 `showtime`
  - [x] `apps/server/src/mock_dataset.py` 不再读取进程级 mock 开关，改为只认当前请求是否处于 `showtime`
- [x] 前端已统一透传 `showtime`
  - [x] `apps/web/src/utils/showtime.ts` 统一读取 URL `showtime=true`
  - [x] `apps/web/src/api/client.ts` 统一透传 `X-Showtime: true`
  - [x] `apps/web/src/router/index.ts` 已在路由跳转时保持 `showtime=true`
- [x] 普通 `/api/heats` 已切为默认真实 only
  - [x] 默认模式只返回真实推断炉次，不再漏出 `demo_seed/mock_stream`
  - [x] `showtime=true` 时，普通 `/api/heats` 会切到 mock 炉次集合
  - [x] 显式 mock 流接口 `/api/heats/stream/mock*` 也改为只接受 `showtime` 请求
- [x] 前端炉次页已兼容新口径
  - [x] `apps/web/src/api/heat.ts` 已补 `mock_stream/mock_curve` 数据源类型
  - [x] `apps/web/src/views/HeatListView.vue` 只在 `showtime` 模式下显示演示来源提示
- [x] 后端测试夹具已改为默认 live 口径
  - [x] `apps/server/tests/conftest.py` 改为预置 `live_inferred` 缓存，不再用 demo seed 充当普通链路
  - [x] `apps/server/tests/test_heats_api.py` 已补 `showtime` 请求断言与默认真实列表断言
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_heats_api.py -x -vv`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（阶段 1：宿主入口与 EDC 统一状态收敛整理）
- [x] 已完成当前状态源审计
  - [x] 宿主本地草稿态：`hostSettingsStorageKey`
  - [x] 宿主运行时内存态：`config / isConnected / meta / addedChannelIds`
  - [x] 后端统一读取面：`_SETTINGS_STORE / _HOST_CHANNEL_STORE / runtime_state`
  - [x] EDC 前端重复写入口：`SettingsView.vue -> /settings/edc-connection`
- [x] 已确认当前 4 个关键真源冲突：
  - [x] 宿主和 EDC 设置页都能写系统连接配置
  - [x] 连接在线摘要主要存在宿主本地，没有后端统一只读视图
  - [x] 宿主草稿态与后端运行态可能短时漂移
  - [x] `showtime` 还没扩到全部页面和演示 UI
- [x] 已新增状态收敛文档：
  - [x] `docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md`
- [x] 已明确下一阶段顺序：
  - [x] 先补后端统一宿主状态视图
  - [x] 再收掉 EDC 设置页系统连接双写
  - [x] 再把 `showtime` 扩到全系统

### 2026-03-20（阶段 2：补后端统一宿主连接状态视图）
- [x] 已新增后端统一宿主连接状态模型与接口
  - [x] `apps/server/src/schemas/setting.py` 新增 `HostConnectivityStatus*`
  - [x] `apps/server/src/api/settings.py` 新增 `GET/PUT /api/settings/host-connectivity-status`
  - [x] `apps/server/src/runtime_state.py` 已持久化 `host_connectivity_status`
- [x] 宿主回写链路已补齐“配置 + 通道 + 连接摘要”
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
- [x] 测试已收口，不再依赖本地 `localhost:8080`
  - [x] `apps/server/tests/test_tasks_reports_settings_api.py` 改为 monkeypatch `EDCClient.login`
  - [x] `apps/server/tests/conftest.py` 已补 `_HOST_CONNECTIVITY_STATUS` 隔离恢复
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - [x] 宿主 `npm run lint`
  - [x] 宿主 `npm run build`

### 2026-03-20（阶段 3：收掉 EDC 设置页系统连接双写）
- [x] EDC 设置页已改为只读展示宿主状态
  - [x] `apps/web/src/views/SettingsView.vue` 不再提供 `test/save edc` 按钮
  - [x] `apps/web/src/stores/setting.ts` 改为读取 `/settings + /settings/host-connectivity-status`
  - [x] `apps/web/src/api/setting.ts` 已补宿主连接摘要读取接口
- [x] 后端已把宿主同步写入口收成专用 header
  - [x] `PUT /api/settings/edc-connection`
  - [x] `PUT /api/settings/host-channels`
  - [x] `PUT /api/settings/host-connectivity-status`
  - [x] 以上接口现在都要求 `X-ASNS-Host-Sync: true`
- [x] 宿主同步链路已补 header
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`
- [x] 相关回归已更新：
  - [x] `apps/server/tests/test_tasks_reports_settings_api.py`
  - [x] `apps/server/tests/test_baselines_dashboard_api.py`
  - [x] `apps/web/e2e/coverage.spec.ts`
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts -g "settings page shows host connectivity" e2e/app.spec.ts e2e/issue-acceptance.spec.ts`
  - [x] 宿主 `npm run lint`
  - [x] 宿主 `npm run build`

### 2026-03-21（阶段 4：统一运行态读取面接入 Dashboard / Heat / Baseline）
- [x] 后端新增统一运行态摘要接口
  - [x] `apps/server/src/api/settings.py` 新增 `GET /api/settings/runtime-status`
  - [x] 返回统一状态：宿主连接摘要、EDC 配置摘要、激活基线摘要、运行模式，以及 `dashboard / heats / baselines` 三条业务链路的就绪码
  - [x] `apps/server/tests/test_tasks_reports_settings_api.py` 已补默认模式与 `showtime=true` 两条断言
- [x] 前端新增统一运行态 store，并由应用根层持续刷新
  - [x] `apps/web/src/stores/runtimeStatus.ts` 新增统一运行态 store
  - [x] `apps/web/src/App.vue` 在应用启动、路由切换与 30 秒轮询时刷新运行态
  - [x] `apps/web/src/components/layout/AppHeader.vue` 已改为消费统一运行态，不再硬编码“系统运行正常”
- [x] Dashboard / 炉次浏览 / 黄金基线库已改为消费统一运行态 banner
- [x] Heat / Baseline 详情页也已接入统一运行态 banner
  - [x] `apps/web/src/components/common/SystemReadinessBanner.vue` 新增统一状态提示组件
  - [x] `DashboardView.vue / HeatListView.vue / BaselineListView.vue` 已接入统一 banner
  - [x] `HeatDetailView.vue / BaselineDetailView.vue` 已继续接入统一 banner
  - [x] 当前页面不再各自猜测“宿主是否已同步 / 是否可走真实链路”，统一以 `/api/settings/runtime-status` 为准
- [x] 前端 E2E 已补统一运行态覆盖
  - [x] `apps/web/e2e/coverage.spec.ts` 新增 Dashboard 统一运行态 banner 校验
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/coverage.spec.ts e2e/issue-acceptance.spec.ts`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-21（阶段 5：统一运行态读取面扩展到 Tasks / Reports / Inbox）
- [x] 后端统一运行态摘要已扩展到剩余业务页
  - [x] `runtime-status` 的 `pipelines` 新增 `inbox / tasks / reports`
  - [x] `Inbox` 复用 `heats` 链路状态
  - [x] `Tasks / Reports` 当前复用统一宿主同步与 EDC 配置就绪状态
- [x] 剩余业务页与详情页已接入统一 banner
  - [x] `InboxView.vue`
  - [x] `TaskListView.vue`
  - [x] `TaskDetailView.vue`
  - [x] `ReportListView.vue`
  - [x] `ReportDetailView.vue`
- [x] E2E 已补一条“Reports 复用统一运行态 attention”回归
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_heats_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts e2e/app.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-21（阶段 6：统一运行态读取面补齐到基线定义页与设置页）
- [x] 后端统一运行态摘要已新增 `settings` pipeline
  - [x] `apps/server/src/schemas/setting.py` 的 `RuntimePipelinesSummary` 新增 `settings`
  - [x] `apps/server/src/api/settings.py` 的 `/api/settings/runtime-status` 已返回 `settings` 链路状态
  - [x] `apps/server/tests/test_tasks_reports_settings_api.py` 已补 `settings / baselines` 状态断言
- [x] 前端统一运行态 store 已同步补齐 `settings`
  - [x] `apps/web/src/api/setting.ts`、`apps/web/src/stores/runtimeStatus.ts` 已支持 `pipelines.settings`
  - [x] `apps/web/src/components/common/SystemReadinessBanner.vue` 已支持 `section="settings"`
- [x] 剩余顶层入口页已补齐统一运行态 banner
  - [x] `apps/web/src/views/BaselineDefinitionListView.vue` 已接 `section="baselines"`
  - [x] `apps/web/src/views/SettingsView.vue` 已接 `section="settings"`
  - [x] 这意味着主导航全部入口页现已统一消费后端运行态摘要，不再各自猜宿主/EDC状态
- [x] 设置页宿主连接卡已进一步切到统一运行态 store
  - [x] `apps/web/src/stores/setting.ts` 不再额外拉取 `/settings/host-connectivity-status`
  - [x] `apps/web/src/views/SettingsView.vue` 的宿主连接卡改为直接读取 `runtimeStatusStore.data.host / edc`
  - [x] 设置页现在只保留业务设置读取，宿主连接展示与其余页面完全同源
- [x] E2E 已补基线定义页与设置页统一运行态覆盖
  - [x] `coverage.spec.ts` 新增“baseline definitions and settings pages reuse unified runtime attention state”
  - [x] 基线定义用例已补 GET `/api/baseline-definitions` 桩，避免依赖本地后端常驻
- [x] 当前验证结果：
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src apps/server/tests`
  - [x] `npm.cmd run lint`（`apps/web`）
  - [x] `npm.cmd run build`（`apps/web`，提权运行）
  - [x] `npx.cmd playwright test e2e/coverage.spec.ts e2e/app.spec.ts e2e/issue-acceptance.spec.ts`（`apps/web`，提权运行）
  - [ ] `apps/server` pytest 当前被本地失效的 uv Python 解释器阻塞，需先修复 `.venv` 再恢复

### 2026-03-21（联调收口：报表详情成功后仍卡 loading）
- [x] 修复报表详情页把“未加载 / 加载失败 / 成功空列表”混成同一 loading 占位的问题
  - [x] `apps/web/src/stores/report.ts` 已拆分 `listLoading / detailLoading / detailError`，并给详情请求补 token，避免旧响应覆盖新日期
  - [x] `apps/web/src/views/ReportDetailView.vue` 已改为明确的成功 / loading / 错误三态，不再仅凭 `current === null` 永久显示“加载中...”
  - [x] 报表详情成功响应中的 `top_deviations=[]` 现会渲染明确空态，不再因空数组场景停留在加载占位
  - [x] 报表详情在 404/失败场景下现会显示明确错误态，而不是继续展示 `pending`
- [x] 报表详情文案与回归已补齐
  - [x] 四套 locale 已新增报表详情副标题、空偏差文案、失败提示与刷新提示
  - [x] `apps/web/e2e/coverage.spec.ts` 已补“空 `top_deviations` 成功态”和“详情接口失败错误态”两条回归
- [x] 验证通过
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/coverage.spec.ts -g "reports and inbox pages can navigate into detail pages|report detail shows explicit error state when detail request fails"`

### 2026-03-20（showtime 第二轮扩展：Dashboard / 任务 / 报表默认真实 only）
- [x] 任务链路已按请求级 `showtime` 拆分真实与演示数据源
  - [x] `apps/server/src/api/tasks.py` 默认 `_TASK_STORE` 改为空的真实运行态任务库
  - [x] showtime 请求才会切到 `_SHOWTIME_TASK_STORE` 的 seeded mock 任务
  - [x] Dashboard 待处理任务统计已改为按当前请求模式下的任务库计算
- [x] 报表链路已去掉合成日报，默认改为基于当前炉次/任务数据实时汇总
  - [x] `apps/server/src/api/reports.py` 不再用 `_build_report()` 生成 30 天假报表
  - [x] `/api/reports/daily` 与详情改为按当前请求模式下的 heat/task store 动态汇总
  - [x] 默认模式下无真实炉次时返回空列表/404，不再露出合成日报
- [x] Dashboard 默认模式下的演示 UI 已清理
  - [x] 统计卡片移除硬编码“较昨日增加 14 炉 / 上次校准 2023-10-24”等演示文案
  - [x] 偏差收件箱预览改为基于真实异常/待分析炉次派生，没有数据就显示空态
  - [x] 纠偏任务待办改为基于真实任务列表派生，没有数据就显示空态
  - [x] 快捷入口角标改为按当前真实异常炉次数动态显示
- [x] E2E 已改为确定性口径
  - [x] `coverage.spec.ts` 的日报/收件箱走显式 mock 桩，不再依赖当前本地后端运行态一定有数据
  - [x] 基线定义“选择宿主通道”用例已改成选择真正可用的剩余通道，不再依赖被占用的演示选项
- [x] 验证通过：
  - [x] `apps/server/.venv/Scripts/ruff.exe check src tests`
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_tasks_reports_settings_api.py tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/coverage.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-20（showtime 第三轮收口：默认模式文案去 mock，演示 banner 判定收紧）
- [x] 基线向导默认模式错误文案已去掉“检查 mock 开关 / 显式开启 mock 数据集”
  - [x] `baseline.wizard.previewUnavailable` 改为只提示宿主连接与通道绑定
  - [x] `baseline.wizard.heatCandidatesUnavailable` 改为只提示后端数据源
  - [x] `zh-CN / zh-TW / en-US / ja-JP` 已同步
- [x] 炉次列表演示来源提示已收紧为 showtime 专用
  - [x] `HeatListView.vue` 中 `hasDemoHeatRecords` 不再用“非 live_edc”粗暴判定
  - [x] 当前仅当 `record_source` 明确属于 `demo_seed / mock_stream / demo_curve / mock_curve` 且 URL 带 `showtime=true` 时才显示演示 banner
  - [x] 数据来源文案兜底已改为 `none`，避免把未知来源误标成“演示炉次台账”
  - [x] `HeatDetailView.vue` 的数据来源映射已与列表页对齐，不再把 `mock_stream` 或未知来源默认落到“演示炉次台账”
- [x] 验证通过：
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`

### 2026-03-20（showtime 第四轮收口：baseline 默认真实 only，演示曲线仅限显式 showtime）
- [x] baseline 后端曲线 hydrate 已改为请求级来源解析，不再把 showtime 的 demo 曲线写回共享 store
  - [x] `apps/server/src/api/baselines.py` 新增 `curve_source` 显式返回
  - [x] 默认模式下若无真实基线曲线则返回 `curve_source=none`
  - [x] 仅在 `showtime=true` 请求下才允许返回 `curve_source=demo_curve`
  - [x] 已补回归，验证 showtime 请求不会污染后续默认模式
- [x] baseline 详情页已与 heat 页面统一来源口径
  - [x] `apps/web/src/views/BaselineDetailView.vue` 新增曲线来源说明
  - [x] 仅在 `showtime=true` 且命中 `demo_curve` 时显示演示提示 banner
  - [x] 默认模式下无真实曲线时明确显示“暂无曲线”，不再暗示演示数据
- [x] 前端残留演示入口已继续清理
  - [x] 删除 `apps/web/src/api/heat.ts` 的 `ingestMock`
  - [x] 删除 `apps/web/src/stores/heat.ts` 的 `ingestMockHeat`
  - [x] 四套 locale 已去掉 `ingestMockHeat` 文案
- [x] 边界验证已补齐并通过
  - [x] `apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py -x -vv`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web test:i18n`
  - [x] `pnpm --dir apps/web build`
  - [x] `pnpm --dir apps/web exec playwright test e2e/app.spec.ts e2e/coverage.spec.ts e2e/issue-acceptance.spec.ts`

### 2026-03-22（偶发超时追踪：request_id + 慢请求/超时诊断最小链路）
- [x] 前端已补最小诊断链路
  - [x] `apps/web/src/api/client.ts` 为每个请求生成 `X-Request-ID`
  - [x] 慢请求（`>=4s`）、超时、网络错误、`5xx` 会写入 `window.__ASNS_NETWORK_DIAGNOSTICS__`
  - [x] 诊断记录已包含 `route / method / url / request_id / duration / outcome`
- [x] 后端已补统一 request_id 与结构化耗时日志
  - [x] `apps/server/src/observability.py` 新增最小日志 helper
  - [x] `apps/server/src/main.py` 中间件会回传 `X-Request-ID`，并记录重点接口慢请求
  - [x] `apps/server/src/api/heats.py` 已记录 `/api/heats`、`/api/heats/{id}/compare` 以及 compare 子步骤耗时
  - [x] `apps/server/src/api/dashboard.py` 已记录 `/api/dashboard/realtime` 聚合耗时
  - [x] `apps/server/src/services/edc_client.py` 已记录 `get_local_datas` 子调用耗时和点数
- [x] 已补最小回归
  - [x] `apps/server/tests/test_tasks_reports_settings_api.py` 新增 `X-Request-ID` 回传验证
- [x] 已完成本地静态验证
  - [x] `apps/server/.venv/Scripts/ruff.exe check src/observability.py src/main.py src/services/edc_client.py src/api/heats.py src/api/dashboard.py tests/test_tasks_reports_settings_api.py`
  - [x] `npm.cmd exec eslint src/api/client.ts`
- [ ] 后端 pytest 暂未在当前环境跑通
  - [ ] 当前 `apps/server/.venv/pyvenv.cfg` 指向丢失的 `uv` Python 3.11 路径，`python.exe / pytest.exe` 都无法启动
  - [ ] 代码层已静态检查通过，待本地 3.11 运行时恢复后再补回归执行
- [x] 已补新 session 交接材料
  - [x] 新增 `docs/AI_TIMEOUT_TRACE_GUIDE.md`，供 AI 直接按 request_id 链路定位偶发超时
  - [x] 已更新 `docs/session_handoff.md`，纳入本轮性能收口、超时追踪和当前验证限制

### 2026-03-22（部署文档收口与旧部署资料清理）
- [x] 已新增统一部署文档
  - [x] 新增 `docs/DEPLOYMENT.md`，统一说明 `apps/server`、`apps/web` 与宿主“神经系统”的部署口径
  - [x] 已明确当前生产拓扑推荐：`/` 指向宿主、`/edc/` 指向业务前端、`/api` 指向 FastAPI
- [x] 已收口陈旧部署说明入口
  - [x] `apps/server/README.md` 已补统一部署文档入口与生产启动命令
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/README.md` 已去掉 AI Studio / Gemini 旧说明，改为当前宿主参考工程口径
  - [x] `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/.env.example` 已改为“当前无必填环境变量”的说明
- [x] 已清理明显陈旧的旧单体安装脚本
  - [x] `docs/Ref/install_asns_server-m-1.sh` 不再保留在当前工作区

### 2026-03-23（新建基线 compare：重合提示 + 当前曲线补齐 + 500 回归修复）
- [x] 已修复炉次详情 compare 偶发 500
  - [x] `apps/server/src/api/heats.py` 对 compare 路径中的 `power_curve` / `baseline_curve` 统一先做 `CurvePoint` 归一化，避免运行态里混入 `dict` 结构时在偏差计算阶段访问 `.timestamp` 报错
- [x] 已补 compare 当前曲线缺口兜底
  - [x] 当 shared channel 只取回部分指标时，`/api/heats/{id}/compare` 会继续回退到炉次主曲线补齐缺失的 `power/voltage`
  - [x] 本地复核 `live-heat-0ef1bbda-1774263900000-30` 后，`范德萨` tab 下 `power` / `voltage` 当前曲线都已恢复为 `361` 点
- [x] 已修复“新建基线下看起来没显示当前炉次”的可视反馈
  - [x] `apps/web/src/views/HeatDetailView.vue` 已把基线线与当前生产线样式拉开
  - [x] 当当前炉次曲线与所选基线完全重合时，页面会明确显示提示，不再像“当前炉次没画出来”
- [x] 已补最小回归
  - [x] `apps/server/tests/test_heats_api.py` 新增 shared current curve 缺口 fallback 用例
  - [x] `apps/server/tests/test_heats_api.py` 新增 dict 结构 live curves 不应导致 compare 500 的回归用例
- [x] 已完成本地验证
  - [x] `apps/server/.venv/Scripts/python.exe -m pytest apps/server/tests/test_heats_api.py -k "prefers_edc_curves_when_available or falls_back_to_direct_live_voltage_curve or accepts_dict_live_curves_without_500"`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`

### 2026-03-23（炉次列表重复显示同一炉次：live inferred alias 误合并修复）
- [x] 已定位 `/api/heats` 多行显示同一炉次的根因
  - [x] 不是前端渲染重复，也不是本轮 compare 修复引入；根因在 `apps/server/src/api/heats.py` 的 live inferred 炉次 alias 合并逻辑
  - [x] `runtime_heats` 里仅有 1 条旧的持久化 `live_inferred` 炉次，但 `_find_persisted_live_heat_alias()` 会把当前不同时间窗的 live 炉次都误判成它的别名，导致多行被同一条旧记录的 `heat_no / start_time / deviation_percent` 覆盖
- [x] 已修复 live inferred alias 误合并
  - [x] `apps/server/src/api/heats.py` 现在只有在持久化炉次与当前 live 炉次时间窗真实重叠时，才允许执行 alias 合并
  - [x] 已恢复当前 `/api/heats` 返回各自独立的实时推断炉次，不再把 2026-03-23 的 live 行全部套成 2026-03-19 的旧炉次
- [x] 已补最小回归
  - [x] `apps/server/tests/test_heats_api.py` 新增 stale persisted live record 不得覆盖全部当前 live rows 的回归用例
- [x] 已完成本地验证
  - [x] `apps/server/.venv/Scripts/python.exe -m pytest tests/test_heats_api.py -k "list_heats_prefers_live_inferred_records_when_enabled or does_not_alias_stale_live_record_into_all_current_rows or live_inferred_legacy_id_remains_resolvable_and_returns_canonical_ids or live_inferred_canonical_id_stays_stable_across_small_boundary_changes"`（在 `apps/server` 目录执行）

### 2026-03-24（炉次详情 compare 展示窗口回退：缺通道时不得退回炉次本体短窗）
- [x] 已定位 compare 偶发短窗根因
  - [x] `apps/server/src/api/heats.py` 在展示窗口共享曲线缺失时，`metric_curves.current_curve` 会回退到 `response_item["power_curve"] / ["voltage_curve"]`
  - [x] compare 路由传入的 `response_item` 主曲线本身是炉次本体窗口，因此会把展示窗口图表污染成短窗
  - [x] `/compare` 整包响应带 `20s` TTL，某次短窗回退一旦被写入缓存，前端短时间内会稳定看到错误窗口
- [x] 已修复展示窗口 fallback 口径
  - [x] `apps/server/src/api/heats.py` 新增按指定时间窗读取主功率/电压曲线的 helper
  - [x] compare 路由在展示窗口共享曲线缺失时，会优先回退到“展示窗口主曲线”，不再退回炉次本体短窗
- [x] 已补最小回归
  - [x] `apps/server/tests/test_heats_api.py` 新增展示窗口共享曲线缺失时仍应回退到展示窗口长曲线的回归
- [x] 已完成本地验证
  - [x] `apps/server/.venv/Scripts/python.exe -m pytest apps/server/tests/test_heats_api.py -k "test_heat_compare_extends_display_current_curves_with_plus_minus_60_minutes or test_heat_compare_display_metric_curves_fall_back_to_display_window_live_curves or test_heat_compare_falls_back_to_direct_live_voltage_curve"`
  - [x] `apps/server/.venv/Scripts/ruff.exe check apps/server/src/api/heats.py apps/server/tests/test_heats_api.py`

### 2026-03-23（新建基线 compare 跨天拉轴：基线时间窗映射与当前上下文窗口修复）
- [x] 已记录新 issue 并按台账跟踪
  - [x] `docs/ui_issues.md` 已新增“新建基线在炉次详情 compare 中沿用来源炉次绝对时间，图表与当前炉次信息不匹配”
- [x] 已定位 compare 图表跨天拉轴根因
  - [x] 新建基线 `source_heat_id` 指向历史真实炉次时，compare 直接使用基线来源炉次的绝对时间戳上图
  - [x] 当来源炉次与当前炉次跨天时，基线曲线与当前曲线共用同一绝对时间轴，图表会被拉成跨天范围
- [x] 已修复 compare 展示窗口口径
  - [x] `apps/server/src/api/heats.py` 已把 baseline metric curves 重映射到当前炉次核心时间窗
  - [x] compare 当前曲线展示已扩到当前炉次前后各 `60` 分钟
  - [x] `apps/web/src/views/HeatDetailView.vue` 已把 x 轴固定为当前炉次前后各 `60` 分钟，并让重合提示只看当前炉次核心窗口
- [x] 已补最小回归
  - [x] `apps/server/tests/test_heats_api.py` 新增 baseline curve timestamps 应重映射到当前炉次窗口的回归
  - [x] `apps/server/tests/test_heats_api.py` 新增 compare 当前曲线展示应扩到前后 `60` 分钟的回归
- [x] 已完成本地验证
  - [x] `apps/server/.venv/Scripts/python.exe -m pytest apps/server/tests/test_heats_api.py -k "rebases_baseline_curve_timestamps_into_current_heat_window or extends_display_current_curves_with_plus_minus_60_minutes or prefers_hydrated_baseline_metric_curves or prefers_edc_curves_when_available"`
  - [x] `pnpm --dir apps/web lint`
  - [x] `pnpm --dir apps/web build`
  - [x] 本地 HTTP 复核：新建基线 `范德萨` 的 compare baseline 时间戳已收口到当前炉次核心窗口，当前曲线已扩到前后 `60` 分钟

### 2026-03-24（服务器目录映射与同步手册）
- [x] 已新增 `docs/SERVER_LAYOUT_AND_SYNC.md`
  - [x] 已记录当前服务器上的代码库、运行库、发布目录与 systemd service 指向关系
  - [x] 已记录 GitHub -> 主仓 -> 运行副本 / 发布目录 的单向同步口径
  - [x] 已补 EDC 后端、EDC 前端、ASNS 三条同步流程与最小验收命令

---

## 进行中

- [ ] 联调整体验收（跨页面走查）
- [ ] 继续校准真实曲线推断炉次规则（阈值、长段切分、异常/待分析判定）
- [ ] 继续拆解 `/api/heats` 性能瓶颈（当前第一刀已去掉列表级基线 hydrate，后续仍需评估 live_inferred 推断与详情链耗时）
- [ ] 生产线维度等长校验（当前为定义维度）
- [ ] 切割在线引擎进一步增强（真实数据接入后的持续判定参数自学习）

---

## 待开始

- 无（MVP 功能与 UI 原型全部开发完成）

---

## 已知问题

- 前端构建仍有大 chunk warning（`elementPlus` / `echarts` 产物体积较大）

---

## 笔记

- 当前炉次主记录已进入“真实曲线推断”阶段，不再只靠 Mock；但仍不是上游官方炉次台账
- 当前普通 `/api/heats` 已与 demo/mock 主记录解耦；剩余“拿不到真实数据”问题主要转到真实推断开关与列表性能链路
- 当前 mock 治理已进入请求级 showtime 模式：默认真实 only，`showtime=true` 才允许普通业务接口切到 mock 数据集
- 当前 `showtime/mock` 第一阶段收口已完成：默认模式不再暴露 baseline demo 曲线与前端演示入口，后续可回到“宿主为入口、后端统一读取面”的大目标推进
- 当前“宿主为入口、后端为统一读取面、EDC 只读消费”的主干方向已继续推进到统一运行态摘要：Header 与 Dashboard / Heat / Baseline 主页面已切到后端统一读取面
- 当前统一运行态读取面已继续扩到 `Tasks / Reports / Inbox` 与详情页，主业务导航页基本都已不再各自猜宿主同步状态
- 当前统一运行态读取面已继续补齐到基线定义页与设置页，主导航入口页已全部接到同一套后端状态摘要
- 炉次详情链已做前端请求去重；若后续仍慢，下一步应转到后端 `compare` 与详情聚合链路继续收重
- 单台 EDC 设备，架构预留多台扩展能力
- 模块化设计，支持按插件销售
