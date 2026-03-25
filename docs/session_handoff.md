# 会话交接 (Session Handoff)

> 用于在新 session 中快速恢复上下文。开始新会话时，优先阅读本文件，再按需展开 `progress.md / lessons.md / ui_issues.md`。

---

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
  - 当前真实联调仍被环境阻塞：`127.0.0.1:8000` 不可达、`127.0.0.1:8080` 不可达
  - `Heat Detail` 在详情失败时“手动调整”按钮 silent no-op 已按最小方案收口：当前按钮会进入禁用态，并显示明确不可用提示
  - ASNS 宿主 `npm test` 的 `import.meta.env` / `Invalid URL` 基座问题已在本轮修复，`npm test / lint / build` 当前都可运行

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
  - 目标应覆盖至少：`tests/test_baselines_dashboard_api.py`、`tests/test_heats_api.py`、`tests/test_tasks_reports_settings_api.py`
  - 但当前机器的前置阻塞尚未解除，见下面“已知环境缺口”

### 重点回归面

- Dashboard / Heat Detail 的 timeout/error state 不再伪装为空态或长期 loading
- Heat Detail 在 error-state 下“手动调整”按钮已改为禁用态 + 明确提示，真实联调阶段需顺手确认 happy path 与 error-state 都未回退
- i18n missing-key 告警、默认中文界面的中英混排、不完整 locale 回退
- Heat Detail 的状态口径拆分、异常原因/切割原因本地化
- Baseline/Task/Heat 列表中的占位按钮、假搜索/假筛选、误导性空偏差文案
- `live_inferred` canonical URL 替换与 Heat Detail 创建任务最小闭环
- ASNS 宿主设置页的 `Maximum update depth exceeded` / nested button 风险是否仍无回流

### 已知环境缺口

- EDC 后端 pytest 目前 **不能直接在这台机器上跑**
  - `apps/server/pyproject.toml` 已声明 `pytest` / `pytest-asyncio`
  - `apps/server/README.md` 口径是 `uv sync --all-extras` + `uv run pytest`
  - 但当前机器缺少 `uv`
  - 当前机器缺少 `python3.11`
  - 当前 `apps/server/venv` 不是完整虚拟环境，只剩 `lib/python3.11/site-packages`
  - 其中 `pytest/` 与 `pytest_asyncio/` 目录本体也不完整，不能直接作为可运行入口复用
- ASNS 宿主 `npm test` 当前已恢复为稳定最小入口
  - `import.meta.env` / `Invalid URL` 的 Node test 基座问题已收口
  - 仍缺少的是宿主浏览器级自动化入口，而不是模块级单测可运行性

### 建议下一步

1. 优先在安全前提下补齐 EDC 后端测试环境
   - 推荐方案：在项目约束内提供 `uv` + Python 3.11，再执行 `cd apps/server && uv sync --all-extras && uv run pytest`
   - 不建议方案：直接用系统 `python3.13` 强行跑 `apps/server`，因为 `pyproject` 明确要求 `>=3.11,<3.12`
2. 然后由 Code X + `review` skill 做 full review/full test
   - 先跑前端/宿主基础验证
   - 再补全后端 pytest
   - 然后优先复跑以下真实 acceptance 面：
     - Dashboard 最近炉次 -> Heat Detail
     - Heat Detail 手动调整
     - 生成纠偏任务 -> Task Detail
     - legacy -> canonical URL
     - Heat List 行展开 / CTA
     - Reports 列表 -> 详情
     - Baselines 列表 -> 详情动作
   - 最后汇总未覆盖项、真实阻塞和是否可继续部署/联调

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
