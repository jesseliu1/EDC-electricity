# 经验教训 (Lessons Learned)

> 记录开发过程中的问题模式和解决方案，帮助 AI 避免重复犯错

---

## 使用说明

当用户纠正 AI 的错误时，使用以下格式记录：

```markdown
## [日期] 问题简述

- **错误模式**: 描述导致问题的行为
- **正确做法**: 描述应该如何做
- **适用场景**: 何时应用这个规则
- **相关文档**: 可选，指向相关规范文档
```

---

## 记录

### 2026-04-17 fixed_interval 不能再挂靠“活跃段首点起算”的旧语义

- **错误模式**: 配置虽然叫 `fixed_interval`，实现却先按功率阈值找活跃段，再从每个活跃段首点开始按固定分钟数切。结果 replay 即使传了 `start_time=12:00`，落库炉次仍会漂到 `12:16 / 12:46 / 13:32` 这类不均匀时间点，和“从锚点开始硬切”的业务语义完全不一致。
- **正确做法**: `fixed_interval` 必须独立成自己的策略层，先基于显式 anchor 生成理想切割线，再按 `time_tolerance_percent` 在切点左右搜索活跃结束点；搜到就吸附，搜不到就回退理想切点。`signal_inference` 可以继续按活跃段推断，但 fixed 模式绝不能再复用“活跃段首点起算”。
- **适用场景**: live/replay 共核切割、按班次或指定起点做固定窗口切炉、任何“配置名是固定、实现却跟着波形漂”的后端时间切片逻辑。
- **相关文档**: `apps/server/src/services/heat_cutting_service.py`, `docs/BACKEND_STRUCTURE.md`, `docs/progress.md`

### 2026-04-17 pytest 默认库不能再落到联调共享 `apps/server/data/asns.db`

- **错误模式**: 后端 pytest 的 `client` / `reset_test_database` fixture 直接复用应用全局 `engine`，而 `engine` 默认指向 `apps/server/data/asns.db`。一旦跑测试，`drop_all/create_all`、seed、runtime reload 就会直接污染联调中的 EDC 配置、黄金基线、炉次与运行态。
- **正确做法**: pytest 必须在导入 `src.config` / `src.database` 前先把 `ASNS_DATABASE_URL` 切到独立测试库；默认使用独立 test DB，必要时只允许通过 `ASNS_TEST_DB_PATH` 指定测试库路径。同时对共享库路径加硬保护，若测试仍指向 `apps/server/data/asns.db`，应在 `conftest.py` 加载阶段直接失败。
- **适用场景**: 本项目所有后端 pytest、任何会触发 `drop_all/create_all`、`load_runtime_state()`、runtime seed、formal table seed 的测试入口。
- **相关文档**: `apps/server/tests/conftest.py`, `docs/testing.md`

### 2026-04-13 Windows 上用 Git Bash 驱动 PowerShell 启动脚本时，不能混用 POSIX 路径、反引号续行和“无监听也返回 1”的默认退出码

- **错误模式**: `start-local-edc-stack.sh` 里直接把 Git Bash 的 `/d/...` 路径传给 PowerShell / `Start-Process`，同时在 `-Command "..."` 里继续使用 PowerShell 反引号续行，并默认相信 `Get-NetTCPConnection` 在“端口未监听”时也会返回 `0`。结果脚本会在停端口、找 `.venv`、或执行 `Start-Process` 参数时被 Bash/PowerShell 交叉语义提前打断。
- **正确做法**: Bash 侧保留 POSIX 路径只用于 `cd/rm/mkdir`，传给 PowerShell/`Start-Process` 的目录和日志路径必须先转成 Windows 路径；PowerShell 命令尽量写成单行参数，不依赖反引号续行；对“端口本来就没监听”这类正常空操作，要显式 `exit 0`，避免被 `set -e` 当成失败。
- **适用场景**: Windows 开发机上用 Git Bash 执行需要调用 `powershell.exe`、`cmd.exe`、`Start-Process` 的启动脚本，尤其是本项目这种同时拉起后端、Vite 前端和宿主进程的本机 blank 重部署入口。
- **相关文档**: `scripts/start-local-edc-stack.sh`, `docs/DEPLOYMENT.md`

### 2026-04-09 live 炉次推断前置条件未满足时，不能直接累计为 runtime 刷新失败

- **错误模式**: `refresh_heat_runtime_state()` 只要拿不到 `live_heat_inference_context`，就直接记 `live_heat_inference_unavailable` 失败并累计 `refresh_failure_count`。而当前 inference context 又只从 `active/published baselines` 构建，导致系统在“尚未录入任何黄金基线”的正常 blank 冷启动阶段，被误判成后台连续刷新失败。
- **正确做法**: 必须把“前置业务条件未满足（例如尚无黄金基线）”与“runtime 真刷新失败（例如实时链路异常、请求 EDC 失败）”拆开。前者应进入 `warming / pending / unconfigured` 一类状态，不应累计失败次数，也不应把台账页打成 `error`。
- **适用场景**: blank 冷启动、首次部署后尚未配置黄金基线、任何依赖业务前置配置才能启动实时推断的页面或后台刷新链路。
- **相关文档**: `apps/server/src/api/heats.py`, `docs/progress.md`, `docs/BACKEND_STRUCTURE.md`

### 2026-04-08 runtime compare 切真源时，不能只看 record_source，必须先确认完整快照已经到位

- **错误模式**: 看到记录来源是 `active_runtime / previous_runtime`，就直接把 compare 主链切到“只读 runtime 快照”新路径，结果把还没带齐 `runtime_metric_series / definition_metric_snapshots / baseline_curve_snapshots` 的旧样板 runtime 一起带进去了，瞬间打坏旧回归。
- **正确做法**: runtime compare 的新路径必须以“完整快照已存在”为前提，不是只以 `record_source` 判定。至少要确认当前 runtime 已带齐当前曲线真源、指标模板快照、基线曲线快照，再切到纯 runtime compare；未满足时继续走旧兼容路径。
- **适用场景**: runtime 真源重构过渡期、compare 接口切换真源、旧样板 runtime 仍在仓库或测试里存在、任何“同一 record_source 里混着新旧两代结构”的重构阶段。
- **相关文档**: `apps/server/src/api/heats.py`, `docs/runtime-source-of-truth-refactor-plan.md`, `docs/BACKEND_STRUCTURE.md`

### 2026-04-08 runtime 真源改造不能边改边漂语义，每完成一个修改点都要回看设计文档并做一次 review

- **错误模式**: 在 runtime、状态机、基线绑定、compare 这类跨层共享能力上，一边改代码一边凭局部直觉推进，导致新结构外面包着旧语义，最后出现“对象像是 runtime 真源，实际还在每轮 refresh 重新查外部状态”的半成品实现。
- **正确做法**: 这类工业化改造必须先锁正式计划文档，再按阶段实施。每完成一个修改点，都要回看当前计划文档、`docs/BACKEND_STRUCTURE.md`、相关 runtime 设计文档，确认代码语义仍与设计一致；然后按 `review` skill 口径做一次差异审查，再进入下一阶段。
- **适用场景**: runtime 真源改造、状态机重构、共享业务对象建模、基线绑定语义重写、live/replay 共核重构、任何“新对象模型承接旧逻辑”风险很高的后端主链改造。
- **相关文档**: `docs/BACKEND_STRUCTURE.md`, `docs/runtime-layering-design-draft.md`, `docs/heat-baseline-binding-refactor-plan.md`

### 2026-04-08 compare 接口必须显式给出上下文窗口，前端不能再靠裁曲线或猜点范围决定显示口径

- **错误模式**: 后端 compare 已返回更宽的 `current_curve`，但接口没有把 `context_start_time / context_end_time` 作为显式契约带出来，前端于是继续把“摘要判断逻辑”和“图表显示逻辑”混在一起，最终把上下文曲线又裁回当前炉次本体。
- **正确做法**: compare 这类“核心窗口 + 展示上下文窗口”并存的接口，必须显式输出上下文边界。前端图表直接显示上下文曲线，只在局部业务判断里按核心窗口裁剪；不要再让 UI 靠点集范围猜窗口，也不要用核心曲线做 silent fallback。
- **适用场景**: 炉次详情 compare、任何同时存在“业务本体时间窗”和“展示上下文时间窗”的图表接口、需要前后文但又要保留核心边界识别的工业时序页面。
- **相关文档**: `apps/server/src/api/heats.py`, `apps/server/src/schemas/heat.py`, `apps/web/src/views/HeatDetailView.vue`, `docs/heat-compare-context-display-plan.md`

### 2026-04-08 炉次偏离度不能继续挂在详情/compare 请求阶段现场补算

- **错误模式**: 正式炉次和 runtime 里只存了 `pending / null`，列表字段、详情 compare、甚至任务快照却又在请求阶段按曲线现场重算偏离度。结果就是“列表空、详情有值、DB 还是空”，同一业务事实在不同 API 上分裂成两套口径。
- **正确做法**: 偏离度必须在后端主链里统一计算并落到 binding 上，再由列表 / 详情 / compare / 任务等接口只读透传。`compare` 最多负责组装展示曲线，不能再承担业务真源补算；如果 binding 还是 `pending`，接口就应明确返回空分析结果，而不是偷偷 fallback 现算。
- **适用场景**: 运行态 + 正式表并存、需要列表/详情/任务共享同一业务分析字段、任何“用户点进详情页才把业务结果算出来”的后端设计。
- **相关文档**: `apps/server/src/services/heat_deviation_analysis_service.py`, `apps/server/src/services/formal_heat_service.py`, `apps/server/src/api/heats.py`

### 2026-04-07 SQLite 上的长任务状态查询不能每次都直读正式表

- **错误模式**: replay job 正在运行或刚收到取消时，前台轮询 `GET /api/heats/replay-jobs/{job_id}` 仍然每次都去 SQLite 读正式表；与此同时后台 worker 也在同一张 `heat_replay_jobs` 表上 commit 进度或最终状态。SQLite 单文件锁下，读轮询会反向把写 commit 卡住，最后表面看起来像“取消时写 cancelled 失败”。
- **正确做法**: 长任务要拆成“运行态快照 + 正式持久化”两层。运行中 / 取消中 / 刚完成的 job 状态先读内存快照，SQLite 只负责持久化与补偿恢复；正式写库再补 `database is locked` 重试。不要让轮询查询和后台 worker 在同一个单文件库上硬碰硬。
- **适用场景**: SQLite、`asyncio.create_task` 后台任务、任务轮询接口、进度型 job API、任何“前台频繁查状态 + 后台持续写进度”的后端。
- **相关文档**: `apps/server/src/services/heat_replay_batch_service.py`, `apps/server/tests/test_heat_replay_api.py`

### 2026-04-07 SQLite 上的后台 job 取消不能由 API 线程和 worker 线程同时回写同一状态行

- **错误模式**: replay job 运行中，`cancel` 接口一边 `task.cancel()`，一边自己立刻把 `heat_replay_jobs.status` 改成 `cancelled`；后台 worker 在收到 `CancelledError` 后又会再写同一行。SQLite 单文件写锁下，这种“双写同一任务状态”的并发很容易直接打成 `database is locked`。
- **正确做法**: 取消接口只负责发取消信号，不与后台 worker 竞争最终状态写入。只要后台 task 仍在运行，就让它在 `CancelledError` 分支里单点回写 `cancelled`；接口侧返回当前 job 快照，调用方再轮询最终状态。
- **适用场景**: SQLite 作为单文件运行库、进程内 `asyncio.create_task` 后台任务、需要支持 `cancel` / `running` / `failed` / `completed` 生命周期查询的任务型后端。
- **相关文档**: `apps/server/src/services/heat_replay_batch_service.py`, `docs/BACKEND_STRUCTURE.md`

### 2026-04-07 共享 SQLite 测试库不能并行跑多个 pytest 进程

- **错误模式**: 为了省时间，把依赖 `apps/server/data/asns.db` 的后端测试文件并行跑，例如同时起两个 `pytest` 进程分别跑 `test_formal_heat_api.py` 和 `test_heats_api.py`。这两边都会重建同一个测试库，最终出现 `no such table`、`readonly database`、`disk I/O error` 这类伪故障。
- **正确做法**: 只要测试共用同一个 SQLite 文件，就必须串行跑；如果确实要并行，只能先把每个进程切到独立测试库路径。当前仓库的默认口径是共享 `apps/server/data/asns.db`，因此默认不要并行多个 `pytest` 进程。
- **适用场景**: 本仓库后端单测、`conftest.py` 会重建 SQLite schema 的测试、任何使用共享文件库而不是临时独立 DB 的本地回归。
- **相关文档**: `apps/server/tests/conftest.py`, `docs/progress.md`

### 2026-04-06 blank 重部署时，代码同步和删库重建之间不能让后端先带旧库启动

- **错误模式**: 先执行 `sync-edc-server.sh`，脚本会在 runtime 同步完成后自动拉起 `edc-backend.service`。如果这时旧 SQLite 里仍保留真实 EDC 配置，后端会在 `factory-reset` 前短暂按旧配置启动，和“先 blank 再启动”的语义冲突。
- **正确做法**: blank 重部署要把“同步代码”和“第一次启动后端”拆开。同步 runtime 时使用 `EDC_SERVER_SKIP_START=1`，让后端在旧库阶段保持停止；完成 `factory-reset` 删库重建后，再手动 `systemctl --user start edc-backend.service`。这样后端第一次启动就是对着新空库的 blank 态。
- **适用场景**: 公网 blank 重部署、要求“不接真实 EDC”“不带旧业务数据”“彻底空白启动”的服务器重建场景。
- **相关文档**: `scripts/sync-edc-server.sh`, `docs/DEPLOYMENT.md`, `docs/progress.md`

### 2026-04-06 公网 blank 重部署不能把“清数据”误当成“重建数据库”

- **错误模式**: 看到 `factory-reset + blank` 已执行，就默认认为线上 SQLite 已经和当前代码 schema 对齐，实际上旧库文件只是被清空了数据，表结构仍可能停留在旧版本，最终出现“代码允许、线上 DB 不允许”的漂移，例如 `baselines.source_heat_id` 代码已可空，但线上列仍是 `NOT NULL`。
- **正确做法**: 只要任务目标是“公网部署 / 公网重部署 / blank 重建”，默认必须把 SQLite 也纳入重建范围。`factory-reset` 应直接删除旧 `asns.db` 及 `-wal/-shm/-journal`，再按当前代码 schema 重建空库；随后再用 `ASNS_BOOTSTRAP_MODE=blank` 启动。不能再把“删表数据”当成“数据库已重建”。
- **适用场景**: 公网部署、服务器重部署、blank 环境重建、跨 schema 重构后的上线、任何用户明确要求“彻底删除干净、结果与当前代码一致”的场景。
- **相关文档**: `docs/DEPLOYMENT.md`, `apps/server/src/runtime_state_admin.py`, `apps/server/tests/test_runtime_state_admin.py`

### 2026-04-05 正式表与旧内存样板并存时，详情解析必须优先 formal record

- **错误模式**: 炉次列表已经切到正式表，但详情/compare/analyze/task 仍在 `resolve_heat_record()` 里先命中旧 `_HEAT_STORE`。一旦 legacy 样板和正式炉次共用同一个 `heat_id`，就会出现“列表看起来有基线，详情点进去却变成旧 demo/pending/block 状态”的混搭。
- **正确做法**: 在正式表成为主真源后，记录解析顺序必须明确为：`active_runtime / previous_runtime / formal_db / legacy_store`。旧内存样板只能作为兜底，不能覆盖同 ID 的正式记录。
- **适用场景**: 正式表重构过渡期、runtime + formal 并存、旧 `_HEAT_STORE` 或 demo seed 仍保留在代码里、任何“列表和详情来源不同”风险场景。
- **相关文档**: `apps/server/src/api/heats.py`, `apps/server/src/services/formal_heat_service.py`, `docs/progress.md`

### 2026-04-04 直接写 SQLite 的运维脚本必须同步遵守 `timestamp(ms)` 列契约

- **错误模式**: 模型层已经把 `settings.updated_at` 切到 `TimestampMsType`，但 `runtime_state_admin.py` 仍通过原生 SQL 用 `CURRENT_TIMESTAMP` 写入 text 时间。结果 `deploy-refresh` 当场看似成功，下一次后端启动在 `load_runtime_state()` 读取 `settings` 表时就会因为 text/`timestamp_ms` 不匹配直接崩溃。
- **正确做法**: 只要某张表的时间列已经切到 `timestamp(ms)`，所有绕过 SQLAlchemy 的脚本、CLI、raw sqlite upsert 也必须显式写整数毫秒时间戳，例如 `utc_now_ms()`。同时补回归测试，至少断言 `typeof(updated_at) = 'integer'`，不要只看 value 写进去了没有。
- **适用场景**: `runtime_state_admin.py`、部署刷新脚本、`factory-reset` 相关工具、SQLite 运维脚本、任何“模型类型已改，但脚本还在手写 SQL”的重构场景。
- **相关文档**: `apps/server/src/runtime_state_admin.py`, `apps/server/src/runtime_state.py`, `apps/server/src/db_types.py`, `docs/DEPLOYMENT.md`

### 2026-04-04 时间重构里必须分清“日期选择器 wall-clock”与“已存在绝对时间戳”

- **错误模式**: 把同一个“按天取范围”的前端 helper 同时用于日期选择器返回的 `Date` 和后端已存在的绝对 `timestamp(ms)`。前者需要按用户选中的日历日期解释，后者需要先转成 `plant_timezone` 下的本地日期；两者混用时，会把浏览器本地时区偷偷带回业务语义。
- **正确做法**: 前端时间工具必须至少拆成两类：1) 处理日期选择器 wall-clock 的 helper，例如“根据用户选中的日期生成 plant day range”；2) 处理后端绝对时间戳的 helper，例如“根据 timestamp 先投影到 `plant_timezone`，再求该业务日范围”。不要复用同一个 helper 同时处理这两类输入。
- **适用场景**: Vue/Element Plus 日期选择器、按自然日筛炉次、整天曲线预览、热详情上下文日范围、任何“浏览器本地日期对象”和“业务绝对时间戳”同时存在的前端时间改造。
- **相关文档**: `apps/web/src/utils/time.ts`, `apps/web/src/views/HeatDetailView.vue`, `apps/web/src/components/baseline/BaselineWizard.vue`

### 2026-04-04 服务器上收到“重新部署 GitHub 最新内容”指令时，默认先刷新当前工作区到目标版本

- **错误模式**: 用户已经明确要求在服务器上重新部署 GitHub 最新内容，但排查或部署前没有先刷新当前工作区，继续基于旧工作区代码阅读、判断或比对，导致“工作区代码版本”“GitHub 目标版本”“正在运行版本”三者口径混杂。
- **正确做法**: 只要任务目标是“在服务器上部署 GitHub 当前版本”或“重部署最新 master/main”，默认第一步先把当前工作区刷新到用户要求的目标版本，例如 `git fetch origin` + `git checkout <branch>` + `git reset --hard origin/<branch>`；随后再单独核对运行目录、运行 commit、实际 DB 路径和部署结果。工作区刷新只解决“当前阅读和修改的代码版本”问题，不等于已经完成部署。
- **适用场景**: 服务器重部署、拉取 GitHub 最新代码、按指定分支/commit 回放部署、部署后线上问题回查、同机同时存在工作区与运行目录的场景。
- **相关文档**: `AGENTS.md`, `docs/DEPLOYMENT.md`, `docs/session_handoff.md`

### 2026-04-04 线上排查前必须先确认“当前工作区”与“正在运行的部署目录”不是同一个概念

- **错误模式**: 在服务器上排查公网问题时，直接把当前工作区源码或工作区 SQLite 当成线上真实运行版本，没有先核对 systemd/进程实际指向的部署目录、当前运行 commit 和实际 DB 路径，结果把“工作区现状”误当成“公网线上现状”。
- **正确做法**: 只要用户反馈的是服务器/公网问题，默认先按线上问题处理，第一步必须确认运行中的服务目录、运行 commit、实际 DB 路径和反向代理指向；只有完成这一步后，才能判断接下来该看线上部署目录还是本地工作区。开发工作区只用于改代码和做局部验证，不能默认等于线上运行代码。
- **适用场景**: 服务器排障、公网问题调查、部署后验活、线上 SQLite 核对、systemd 服务排查、同一台机器同时存在开发工作区与运行目录的场景。
- **相关文档**: `AGENTS.md`, `docs/DEPLOYMENT.md`, `docs/session_handoff.md`

### 2026-04-04 factory-reset 语义必须跟着主数据真源一起升级，不能只停留在旧 runtime 表层

- **错误模式**: 后端主链已经从 `settings.runtime_*` 迁到正式表 `baseline_definitions / baselines / heats / metric_series / tasks` 后，仍把 `factory-reset` 只实现成“删除 runtime settings 记录”。结果表面上运行态是空的，但正式业务表还残留旧样板数据，blank 部署会变成假空白态。
- **正确做法**: 只要业务真源发生迁移，所有运维入口尤其是 `factory-reset / blank bootstrap / 本机重置脚本` 都必须同步升级，明确清理新的正式业务表，并补自动化回归覆盖“正式表也被清空”。
- **适用场景**: 正式表重构、从缓存/JSON store 迁到业务表、交付新厂初始化、Windows 本机 `factory-reset + blank` 启动、任何需要保证“空白系统不带旧业务数据”的部署场景。
- **相关文档**: `docs/DEPLOYMENT.md`, `docs/BACKEND_FORMAL_DATA_REBUILD_PLAN.md`, `apps/server/src/runtime_state_admin.py`, `apps/server/tests/test_runtime_state_admin.py`

### 2026-04-03 计划文档主线：一次结构性任务必须有唯一主计划，临时文档要标生命周期

- **错误模式**: 在一轮结构性任务里同时产生多份临时说明、阶段笔记、交接草稿、设计片段，但没有明确哪一份是“主线计划文档”，导致后续实现时口径分叉，压缩上下文或跨 session 交接后更容易丢主线；同时临时文档没有生命周期标记，时间一长就会污染仓库。
- **正确做法**: 每次结构性任务都应明确一份唯一的主计划文档，后续实现、交接、测试都以它为主线推进；其余临时文档必须显式标注生命周期，例如“仅本轮有效 / 实现完成后可删除 / 仅交接用”，方便后续清理。
- **适用场景**: 大型重构、表结构重建、架构调整、跨多 session 的连续开发、任何会产生多份设计/交接/临时说明文档的任务。
- **相关文档**: `docs/BACKEND_FORMAL_DATA_REBUILD_PLAN.md`, `docs/session_handoff.md`, `docs/progress.md`

### 2026-04-03 企业系统回退规则：任何未经确认的回退、补全、替换都不允许进入正式业务链路

- **错误模式**: 在通道被删除、数据缺失、基线未命中、记录失效或运行态过旧时，系统通过“自动补全最像的通道”“自动回退到最新基线”“自动替换成旧快照”“自动跳到别的记录”等方式静默兜底，表面上让页面继续可用，实则破坏业务语义和审计可信度。
- **正确做法**: 企业系统必须把这类状态显式标成 `missing / invalid / stale / unbound / failed`，保留明确告警和人工确认入口；除非用户显式确认或执行明确修订动作，否则不允许静默回退、自动补全、自动换绑或自动替换。
- **适用场景**: 宿主通道绑定、基线选择、生效时间匹配、历史详情解析、运行态与历史态切换、偏离度计算、任何存在 fallback 或 auto-heal 诱惑的正式业务链路。
- **相关文档**: `issue.md`, `docs/BACKEND_STRUCTURE.md`, `apps/server/src/channel_roles.py`, `apps/server/src/api/heats.py`, `apps/server/src/api/settings.py`

### 2026-04-02 Windows 本机联调验活：不要把 `Invoke-WebRequest` 对 Vite 的结果直接当成最终健康结论

- **错误模式**: 在 Windows 本机恢复联调栈时，用 PowerShell `Invoke-WebRequest` 轮询 `http://localhost:3000/edc/` 与 `http://localhost:3000/api/health`，并把返回的 `503` 直接当成前端未启动。实际 Vite 已经 ready，`curl.exe` 访问同一地址返回 `200`，导致启动脚本等价实现被误判中断。
- **正确做法**: Windows 本机对 Vite/代理链路做健康检查时，优先用 `curl.exe` 或直接看实际 HTTP 响应内容，不要只依赖 `Invoke-WebRequest` 的成功/失败分支。若 PowerShell 报 `503`，必须先用第二种方式复核，再判断服务是否真的未启动。
- **适用场景**: Windows PowerShell 本机联调、Vite 开发服务器、前端 `/api` 代理链路、本地启动脚本从 Bash 改写为 PowerShell 的场景。
- **相关文档**: `docs/DEPLOYMENT.md`, `scripts/start-local-edc-stack.sh`

### 2026-04-01 重构边界：不要为了“最小改动”保留不该保留的旧错误路径

- **错误模式**: 在已经确认旧架构主路径本身就是问题源时，仍试图做“兼容旧路径的最小重构”，例如让新运行态继续依赖旧 `live cache` 做 bootstrap，或者在新旧读链路之间保留默认 fallback。这样会把旧错误语义一起带进新实现，形成长期中间态，后面更难拆。
- **正确做法**: 只要决定做结构性重构，就应让新主路径与旧错误路径脱钩，直接完成完整替换。可以接受因此暴露出新的 bug，但不要为了短期稳态把旧错误设计继续包装进新架构。主读链路、运行态、API 职责必须一次切干净，旧路径最多保留为显式调试能力，不能再做默认兼容。
- **适用场景**: API 主读链路重构、前后台分离改造、运行态缓存替换、去除请求期现算、拆除错误 fallback、任何“旧实现已被确认是设计问题而不是局部 bug”的重构场景。
- **相关文档**: `docs/HEAT_RUNTIME_CACHE_AND_BASELINE_WIZARD_REDESIGN.md`, `apps/server/src/api/heats.py`, `apps/server/src/runtime_state.py`

### 2026-03-31 宿主 API 路径：不能在调用方和封装层同时拼接同一个前缀

- **错误模式**: 宿主设置页调用 `callHostApi(...)` 时直接传入完整 `/host-api/edc/*` 路径，而 `callHostApi(...)` 自身又会基于 `hostApiBase=/host-api` 再拼一次。结果真实请求变成 `/host-api/host-api/edc/*`，后端返回 HTML 404，页面再执行 `response.json()` 就会炸成 `Unexpected token '<'`。
- **正确做法**: 宿主 API 调用要统一约定一层负责拼前缀。调用方只传相对业务路径如 `/edc/test-connection`、`/edc/sync-channels`；底层封装再统一拼 `hostApiBase`。同时在封装层增加防重前缀保护，避免误传完整路径时再次生成双前缀。
- **适用场景**: 宿主页 API 封装、React/Vite 前端 fetch helper、带运行时注入 `hostApiBase` 的微宿主页面、任何“base path + 业务 path”双层拼接的前端请求代码。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs`

### 2026-03-31 跨厂迁移：不能把“保留 SQLite”与“新厂全新系统”混成同一套部署口径

- **错误模式**: 默认部署脚本会保留 `data/` 与 SQLite，适合同厂升级；但如果系统要从 A 厂迁到 B 厂，仍沿用这套口径，就会把 A 厂的基线、炉次、任务、宿主通道、角色绑定和连接配置一并带到 B 厂。更隐蔽的是，当前不少真正有业务意义的数据虽然存放在 `runtime_*`，名字看起来像“运行态/缓存”，却不能按“可忽略缓存”处理。
- **正确做法**: 必须显式区分两种场景：1) 同厂升级，保留 SQLite；2) 跨厂迁移/新厂交付，提供明确的“清空数据库/新厂初始化”模式，把旧厂业务数据整体清空，并以 `blank` 初始态启动。不能让操作者靠猜测 `factory-reset`、手工删库或直接重部署来凑这个流程。
- **适用场景**: 工厂迁移、客户环境复制、新厂初始化、PoC 环境转正式环境、任何需要保证“新环境不继承旧环境业务数据”的交付场景。
- **相关文档**: `docs/DEPLOYMENT.md`, `apps/server/src/runtime_state.py`, `apps/server/src/runtime_state_admin.py`, `scripts/sync-edc-server.sh`

### 2026-03-31 本机宿主启动：不能把“重启 3001”当成“宿主前端已经是最新代码”

- **错误模式**: 在 Windows 本机联调时，只把 ASNS 宿主 `node server.mjs` 拉起来，就默认浏览器会拿到当前 `src` 对应的新逻辑；但宿主实际服务的是磁盘里的 `dist/`，如果启动前没先重建，页面仍会跑旧 bundle，继续请求已经废弃的旧接口。
- **正确做法**: 本机凡是涉及 ASNS 宿主前端改动，都必须先 `npm run build`，再启动或重启 `3001`。不能把“进程活着”误当成“前端代码已更新”。应固定使用一条带 build 的本机启动脚本，避免再次漏掉这一步。
- **适用场景**: Windows 本机联调、ASNS 宿主 `3001`、React/Vite 构建产物由 `server.mjs` 提供、宿主源码改了但页面表现仍像旧逻辑的场景。
- **相关文档**: `scripts/start-local-edc-stack.sh`, `docs/DEPLOYMENT.md`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs`

### 2026-03-31 宿主真源协议：后端返回 `snake_case` 时，前端不能直接按 `camelCase` 消费

- **错误模式**: 宿主前端把 `host-bootstrap` / `host-runtime-sync` 返回的通道项和连接摘要，直接当成 `deviceName / channelName / machineName / sensorCount` 这类 `camelCase` 结构来用；而后端真实返回的是 `device_name / channel_name / machine_name / sensor_count`。结果前端内存态混入一批 `undefined` 字段，再回写 `host-runtime-sync` 时被后端 schema 以 `422` 拒绝。
- **正确做法**: 只要宿主前端消费后端真源协议，就必须在入口层把后端响应统一归一化，再进入页面状态。不要假设宿主 `host-api` 的本地对象结构和后端 API 响应结构天然一致。
- **适用场景**: `host-bootstrap`、`host-runtime-sync`、宿主 source truth 协议、任何前端本地对象与后端 Pydantic/JSON 响应字段风格不同的场景。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`, `apps/server/src/schemas/setting.py`

### 2026-03-31 部署闭环：不能只看 health，要核对公网资源指纹是否真的切到目标版本

- **错误模式**: 发布脚本跑完、`health` 正常、`runtime-status=ready` 后就默认“公网已经是最新代码”。这样如果静态资源目录没切、反代还指向旧资源，或者只更新了后端没更新前端，交接时会误把“服务活着”写成“版本已同步”。
- **正确做法**: 每次正式部署后，至少同时核对三类证据：1) 公网页面 HTML 里引用的 JS/CSS 资源指纹，2) 后端运行态接口是否正常，3) 本次目标 commit / 资源目录是否已写入交接文档。没有资源指纹比对，就不能写“公网已是最新版本”。
- **适用场景**: Nginx 静态发布目录切换、Vite hash 资源发布、宿主 Node 服务重启、前后端分离部署、需要做交接留痕的任何上线动作。
- **相关文档**: `docs/progress.md`, `docs/session_handoff.md`, `scripts/publish-edc-web-and-asns.sh`

### 2026-03-31 审计分支合入：调查文档不能脱离当前主线状态原样照搬

- **错误模式**: 看到一个“硬编码盘点 / 架构调查”分支后，直接把文档原样复制回当前主线，默认它写的仍然都是现状。这样很容易把已经修掉的问题继续记成“当前仍存在”，反而污染 handoff 和下一轮判断。
- **正确做法**: 先确认审计分支到底是 docs-only 还是带代码修复；如果只是调查文档，就必须逐项对照当前主线代码，把结论重新标成“已收口 / 仍存在 / 结构债”，再入库。
- **适用场景**: docs-only 审计分支、事故复盘文档、硬编码盘点、前后台边界调查、任何跨时点合并的调查类文档。
- **相关文档**: `docs/HARDCODED_INVENTORY.md`, `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`, `docs/session_handoff.md`

### 2026-03-31 宿主草稿版本护栏：本地未提交编辑态必须绑定后端 `source_revision`

- **错误模式**: 只按“草稿里自带的 endpoint / username / channelCatalogSource 是否自洽”来恢复本地设置，却不绑定后端当前 `source_revision`。这样即使后端当前 source 已被其它入口改掉，旧浏览器标签页下次打开仍可能把旧草稿重新带回来。
- **正确做法**: 浏览器草稿必须显式存 `sourceIdentity + baseSourceRevision`，启动时先拉后端当前真源，再判断草稿是否与后端当前 revision 完全一致；不一致就直接清草稿，不做恢复，更不能自动反写后端。
- **适用场景**: 宿主设置页、localStorage draft、多个浏览器标签/多个入口都可能修改同一连接配置的系统。
- **相关文档**: `docs/HOST_SOURCE_TRUTH_FIRST_STAGE_PLAN.md`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`

### 2026-03-31 部署边界：宿主和后端不能一边跑主仓、一边跑 runtime 副本

- **错误模式**: 后端使用独立 runtime 副本，宿主却直接从主仓目录运行。这样一次“部署”没有统一发布对象，很容易出现宿主是新代码、后端还是旧 runtime 的分叉状态。
- **正确做法**: 代码真源、运行时、数据目录必须分层。宿主和后端都应只从 runtime 副本启动，部署脚本负责从主仓构建、清理旧运行库、重建依赖、复制最小运行文件并重启 service；运行中的 runtime 不能再充当开发目录。
- **适用场景**: 同机部署的前后端/宿主混合系统、systemd user service、需要保留 SQLite / logs / backups 但不保留旧运行库的项目。
- **相关文档**: `docs/HOST_BACKEND_RUNTIME_UNIFICATION_PLAN.md`, `scripts/sync-edc-server.sh`, `scripts/publish-edc-web-and-asns.sh`, `docs/SERVER_LAYOUT_AND_SYNC.md`

### 2026-03-31 发布脚本健康检查：user service 重启后不能立刻拿一次公网结果就判失败

- **错误模式**: `asns-host.service` 刚重启就立即请求公网 `/asns/`，把反代层短暂返回的 `502` 直接当成部署失败。实际服务几秒后已经恢复，但脚本会提前退出，让人误判成“发布没成功”。
- **正确做法**: 发布脚本必须给重启后的健康检查留出等待窗口，先轮询本机 runtime 入口，再轮询公网入口；只有重试耗尽后仍失败，才判部署失败。不要把“服务启动窗口期”混成“真实故障”。
- **适用场景**: systemd user service、Node/ASNS 宿主重启、Nginx 反代到本机端口、任何“服务刚拉起但公网探针先到一步”的发布脚本。
- **相关文档**: `scripts/publish-edc-web-and-asns.sh`, `docs/progress.md`

### 2026-03-31 宿主生产运行态：不要把真实测试源快照编进前端 bundle 参与默认启动

- **错误模式**: 为了让宿主页在“连线里程碑”阶段先有可看目录和摘要，把真实测试源的设备/通道快照直接做成 `edcChannelSnapshot` 编进前端 bundle，并在 `App.tsx / SettingsView.tsx` 的默认启动、默认展示、默认目录恢复里直接消费。结果一旦进入生产路径，这份旧快照就会以“默认摘要”“默认目录”“恢复兜底”的形式长期污染运行态。
- **正确做法**: 生产宿主的默认启动只能读取后端当前运行态或显式请求级 `showtime` API，不能依赖 bundle 内置快照。若确实需要 demo/showtime，也必须由后端按显式模式返回演示数据，前端 bundle 不得再内置可被生产启动路径直接消费的真实源快照。
- **适用场景**: 宿主 + 子应用架构、工业采集系统、需要区分真实模式与 showtime/mock 模式的前端宿主页、任何存在“构建期快照”和“运行期真源”两套数据的系统。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/edcChannelSnapshot.ts`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`, `apps/server/src/request_mode.py`

### 2026-03-31 宿主本地草稿：浏览器缓存不能压过后端当前 source，更不能在启动时自动反写后端

- **错误模式**: 宿主页启动时同时读取后端当前设置和浏览器 `localStorage` 草稿，却使用 `restored?.config || persistedConfig` 让本地草稿优先；随后又在启动恢复里自动执行 `test-connection + syncSelectionToBackend`。这样一来，只要旧浏览器里还留着自洽草稿，即使后端 source 已被其它入口切换，宿主下次打开也可能把旧 source 和旧通道重新推回后端。
- **正确做法**: 后端当前 source 必须是唯一真源。本地草稿只能作为“同源未提交编辑态”恢复，且在恢复前必须先比较后端当前 source；一旦 source 不一致，应直接判草稿失效并清空。宿主启动恢复默认应为只读恢复，不得在未完成 source 一致性校验前自动反写后端。
- **适用场景**: 多浏览器/多入口都可能修改系统连接的宿主系统、工业采集换源、浏览器 localStorage rehydrate、任何“本地缓存”和“服务端当前配置”都可能变化的前端设置页。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

### 2026-03-30 验收口径：架构边界变了，UAT 文档也必须同轮升级

- **错误模式**: 后端已经把 `host channels` 和 `channel role bindings` 拆成两层，正式 UAT 却还沿用“`host-channels total > 0` 就算链路 ready”的旧口径，导致原始通道目录恢复和业务链路就绪被混成同一件事。
- **正确做法**: 只要运行态边界或 ready 判定变了，UAT 主文档、follow-up 总账、最终放行标准必须同轮同步升级。正式验收里要把 `GET /api/settings/channel-role-bindings` 和 `GET /api/settings/runtime-status.channel_roles` 作为独立证据；没有角色绑定证据时，只能说“宿主通道已恢复”，不能说“业务链路 ready”。
- **适用场景**: EDC 换源、部署后 runtime 自愈、工业采集通道重绑、任何把“原始通道清单”和“业务用途”拆层的系统，以及所有依赖 ready 判定的 UAT/商业交付总账。
- **相关文档**: `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`, `docs/test-reports/2026-03-28-uat-followup.md`, `apps/server/src/channel_roles.py`, `apps/server/src/api/settings.py`

### 2026-03-30 运行态边界：不要再把“宿主通道清单”和“业务角色用途”混成同一层状态

- **错误模式**: 让 Dashboard、炉次推断等业务链路直接从宿主已添加通道或基线定义名字里反推“功率/电压主通道”，结果一旦上游源缺少对应名字、只剩一条主信号、或旧绑定虽然还在 catalog 里但当前窗口读空，业务层就会继续误读、误判 ready，甚至整条链路一起 503。
- **正确做法**: 必须拆成三层：`raw host channels` 只表示宿主当前同步到的可选通道，`channel role bindings` 单独表达业务用途，业务 API 只读角色绑定，不再偷看定义名。换源时清角色绑定，部署自愈时同时 reconcile 宿主通道、角色绑定和定义绑定；对当前窗口确认读空的旧角色，要允许被 live probe 结果替换。
- **适用场景**: 单源工业采集系统、未来上游指标命名不稳定或不保证有“功率/电压”字样的 EDC 场景、部署后 runtime 自愈、炉次推断主信号选择、Dashboard 实时主/辅曲线绑定。
- **相关文档**: `apps/server/src/channel_roles.py`, `apps/server/src/api/settings.py`, `apps/server/src/api/dashboard.py`, `apps/server/src/api/heats.py`, `apps/server/src/runtime_state_admin.py`

### 2026-03-30 实时通道推荐：不要把“目录里看起来像功率/电压”的基波通道直接当成默认生产通道

- **错误模式**: 在自动推荐宿主功率/电压通道时，只按名称和单位做静态匹配，结果把 `A相基波實功功率 / A相基波電壓` 这类当前 5 分钟窗口读空的通道排到了 `總有功功率 / A相電壓` 前面；表面看是“新源已对齐”，实际 Dashboard 实时仍然 503。
- **正确做法**: 默认推荐不能只看 catalog 名字，还要结合真实可读性。至少要做到三点：识别繁简体（`总/總`、`电压/電壓`、`压/壓`、`温/溫`），对 `基波` 通道降权，对 `總有功功率` 这类总功率通道升权；部署自愈时还要用当前源近 5 分钟真实点去校验功率/电压绑定，发现“有效但读空”的旧绑定时自动替换成有点的通道。
- **适用场景**: EDC 切源后自动重建宿主通道、部署后 runtime 自愈、Dashboard 实时取数、默认定义绑定、任何“目录里存在多个名字相近但采样状态不同的功率/电压通道”的工业采集场景。
- **相关文档**: `apps/server/src/runtime_state_admin.py`, `apps/server/src/api/dashboard.py`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

### 2026-03-30 部署修复：不要为了清旧源残留，把当前仍有效的运行绑定也一并重建掉

- **错误模式**: 为了修复旧源 `suid/cuid` 残留，在部署脚本或运维修复脚本里每次都把宿主通道清单、基线定义绑定粗暴重建成一套“默认推荐值”，结果同源下用户已经手工确认过的有效绑定也被覆盖。
- **正确做法**: 部署侧修复只能修“坏的 source-bound 状态”，不能重写“好的 source-bound 状态”。应先用当前 catalog 校验已有宿主通道和 `edc_channel_id` 是否仍有效：有效的保留，无效的剔除或重绑，再按默认规则补齐最小功率/电压/温度/压力覆盖。
- **适用场景**: GitHub 覆盖部署、运行态自愈脚本、数据库修复、迁移旧环境到新环境、任何“要清旧源脏状态但不想毁掉现场已确认配置”的场景。
- **相关文档**: `apps/server/src/runtime_state_admin.py`, `scripts/sync-edc-server.sh`

### 2026-03-30 换源语义：不要把“密码变更”误判成“真正换源”

- **错误模式**: 只要 EDC 连接配置有任一字段变化，就把它统一当成“换源”，顺手清掉宿主通道、活动基线和基线通道绑定。
- **正确做法**: 必须拆开两层语义：`source identity = base_url + username`，`connection material = base_url + username + password + api_key`。只有地址或账号变化才算真正换源；仅密码/API Key 变化时，只重置连线验证态和相关缓存，不清 source-bound business bindings。
- **适用场景**: 宿主设置页改密码、EDC API Key 轮换、后端连接配置更新、任何“连接信息变化但业务来源未变”的场景。
- **相关文档**: `docs/SOURCE_SWITCH_UNIFICATION_PLAN.md`, `apps/server/src/services/source_switch_service.py`

### 2026-03-30 换源收口：必须由后端定义唯一重置入口，不要让多个按钮各自决定清什么

- **错误模式**: 在宿主 `测试连接 / 同步通道 / 保存设置`、后端设置接口、启动恢复逻辑里分别写一部分 `sourceSwitched` 清理分支，导致每条路径的重置边界不一致，最后留下“新源地址 + 旧源绑定”的混搭状态。
- **正确做法**: 把“换源”收口成后端单入口，统一由一套服务决定哪些状态该清、哪些状态不该清；前端只负责判断是否需要确认，并调用这一个入口，不再各自实现一套局部 reset。
- **适用场景**: 多入口都可能触发来源切换的系统设置页、宿主同步链路、启动恢复覆盖、任何需要统一副作用边界的配置切换场景。
- **相关文档**: `docs/SOURCE_SWITCH_UNIFICATION_PLAN.md`, `apps/server/src/api/settings.py`

### 2026-03-30 换源交互：用户取消确认时，不能把“取消”误处理成“连接失败”

- **错误模式**: 把“用户取消换源确认”与“测试连接失败 / 同步失败”放在同一条错误分支处理，导致用户明明只是点了取消，界面却被重置成断线或失败态。
- **正确做法**: 宿主前端必须把“换源预处理未通过”和“真正执行动作后失败”拆开；取消确认时只提示“本次操作未执行”，不要重置当前已生效状态。
- **适用场景**: 带确认弹窗的宿主设置页、破坏性配置切换、任何“先确认再执行”的前端动作编排。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`

### 2026-03-29 新源联调：登录成功不等于当前绑定的 `suid/cuid` 仍属于这个源

- **错误模式**: 只要看到新源登录成功、宿主连接成功，就默认现有通道绑定也还能继续用；没有核对这些 `suid/cuid` 是否真的属于当前新源目录。
- **正确做法**: 只要发生上游源切换，就必须重新核对功率/电压/温度通道的 `suid/cuid` 是否来自当前源的真实目录；若当前目录的设备 ID 已从 `2349/2054/...` 变成 `2752/2755/...`，旧绑定即使格式合法，也只是在新源上读空数据。
- **适用场景**: `S05-TC01 / S05-TC02 / S05-TC03`、宿主切源后重新同步通道、真实 EDC 多源切换、任何依赖通道 ID 持久化的联调场景。
- **相关文档**: `docs/test-reports/2026-03-29-s05-realtime-followup-investigation.md`

### 2026-03-29 联调阻塞排查：先分清“历史默认地址”与“当前真实运行链路”

- **错误模式**: 看到文档或默认配置里还有 `http://localhost:8080`，就继续把它当成当前联调主阻塞，默认认为仓库里应该还有一个没启动的本地服务。
- **正确做法**: 排查联调阻塞时，先看当前运行中的真实链路和端口绑定，再决定阻塞是否仍成立；如果运行中的 `8000/8001/3000/3001` 已经直接连到新的真实上游 IP，就不能继续沿用历史默认地址来给当前 UAT 定性。
- **适用场景**: 本地多端口联调、运行副本/宿主代理并存、后端默认值和真实设置可能分叉的 EDC / ASNS 验收场景。
- **相关文档**: `docs/test-reports/2026-03-29-8080-blocking-investigation.md`, `apps/server/src/config.py`, `apps/web/vite.config.ts`

### 2026-03-29 宿主切源验收：`S04-TC02` 的通过口径应与“业务 ready”分开判断

- **错误模式**: 把“切换新源并保存成功”误等同于“保存后整站必须立刻回到 `ready`”，从而看到 `no_enabled_channels` 就继续把 `S04-TC02` 判成失败。
- **正确做法**: 对宿主切源类用例，先拆清验收目标。如果本用例只验证“新源可连、测试连接成功、保存成功”，那通过条件应落在连接与保存证据上；若没有继续执行“同步通道 + 绑定宿主通道”，保存后出现 `no_enabled_channels` 属于当前真实预期，不能混判成 `host_disconnected` 或源码失败。
- **适用场景**: `S04-TC02`、宿主设置页切换 EDC 上游、只验证连接和保存但未完成通道绑定的联调/正式 UAT 场景。
- **相关文档**: `docs/test-reports/2026-03-29-s04-tc02-rerun.md`, `apps/web/e2e/s04-tc02-source-switch-rerun.spec.ts`

### 2026-03-29 UAT 失败复盘：现场失败不能直接外推为当前源码仍有同一缺陷

- **错误模式**: 看到正式 UAT 留档里某条仍是 `FAIL`，就直接把它当成“当前源码还没修好”，没有先验证当前运行代码、现场宿主版本和真实请求返回是否一致；结果容易在已经修复的路径上重复盲改。
- **正确做法**: 对悬挂的 UAT `FAIL`，先复现当前源码行为，再核对现场实际运行宿主/后端版本与返回证据；如果当前源码已通过，就补最小回归测试固定住解析和接口闭环，再把问题转为“环境口径 / 旧包版本 / 现场证据”核查，而不是继续改业务代码。
- **适用场景**: 宿主代理、外部 EDC 联调、`S04-TC02` 这类“正式失败但当前源码本地已通”的场景，尤其是上游返回格式特殊（如 `systemcfg` 数字字节串）时。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostApiServer.test.ts`, `docs/session_handoff.md`

### 2026-03-29 宿主 UAT：`3001` 页面观察必须先确认正在跑的 dist 不是旧构建

- **错误模式**: 看到 `server.mjs` 和源码里的 `hostConnectivitySync.ts` 已经改成“同域 `/api` + 同域 `host-api`”，就默认 `127.0.0.1:3001` 当前页面一定也在跑这版逻辑；但如果 `dist` 是旧构建，浏览器实际发出的设置写请求仍可能落到旧地址（例如 `127.0.0.1:8000/api/*`），导致宿主页面、正式联调后端、UAT 结论彼此分叉。
- **正确做法**: 只要问题涉及 `3001` 宿主页面行为，就先核实当前加载的构建入口和浏览器实际请求去向；至少确认页面已加载最新 `dist`，且宿主写请求走的是同域 `3001/api/*`。不要只看源码结论，不看正在被 `server.mjs` 提供的 bundle。
- **适用场景**: 宿主 `server.mjs` 本机联调、S04 类切源 UAT、任何“源码已修但 3001 页面表现仍像旧逻辑”的场景。
- **相关文档**: `docs/test-reports/2026-03-29-s04-tc02-host-runtime-investigation.md`, `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/dist/`

### 2026-03-28 正式 UAT 脚本基准：取数口径必须跟当前真实可用链路一致

- **错误模式**: 正式 UAT 脚本里仍硬编码旧 API 基准（例如 `127.0.0.1:8000/api`），而当前实际可用链路已经切到宿主代理 `3001/api` 或运行副本 `8001/api`；结果业务本身已恢复，但正式回归先失败在过期环境口径上。
- **正确做法**: 正式 UAT 脚本执行前先核实当前真实可用链路，并把 API 基准收口到可配置入口；优先复用宿主代理口径，避免把“环境漂移”误记成“业务失败”。
- **适用场景**: Playwright 正式 UAT、宿主代理环境、本地联调有 `3001 -> 8001` 代理链、任何端口和代理层可能变化的联调脚本。
- **相关文档**: `apps/web/e2e/uat-full.spec.ts`, `docs/test-reports/2026-03-28-uat-full.md`

### 2026-03-27 正式 UAT 证据位：`visible` 断言不等于截图里真的看得见

- **错误模式**: 自动化里已经断言某个元素 `visible`，就直接截图并认为证据齐了；但元素可能仍在内部滚动容器的视口外，或页面下半区根本没有拍进 PNG，最终“断言通过”与“截图证据合格”分离。
- **正确做法**: 对正式 UAT 的关键证据位，在截图前不仅要断言 `visible`，还要显式 `scrollIntoViewIfNeeded`，并用 `toBeInViewport` 或等价检查保证目标确实进入截图视口，再执行截图。
- **适用场景**: 宿主设置页、长表单、滚动面板、抽屉、iframe 容器内页面、任何“用户流程每一步都要截图留存”的正式验收场景。
- **相关文档**: `docs/testing.md`, `apps/web/e2e/asns-edc-source-switch-reset-uat.spec.ts`

### 2026-03-27 上游 EDC 切换：切换服务器时必须同时清空或重建宿主通道绑定

- **错误模式**: 只更新 EDC 连接配置或只做“测试连接”，却继续沿用旧服务器的宿主通道清单、通道快照或本地草稿；结果运行态里出现“新服务器地址 + 旧服务器 suid/cuid”的混搭状态，业务页取数失败。
- **正确做法**: 只要发生上游 EDC 服务器切换，就必须把宿主通道目录、已添加通道清单、默认选择和本地草稿一起按“新服务器”口径重建；至少要保证旧服务器的通道 ID 不会在切换后继续写回后端运行态。
- **适用场景**: 宿主连线设置、EDC 服务器切换、通道同步、宿主 bootstrap 恢复草稿、任何“上游数据源身份变化但下游绑定仍复用旧 ID”的场景。
- **相关文档**: `docs/test-reports/2026-03-27-edc-server-switch-stale-groups-investigation.md`

### 2026-03-27 正式 UAT 留证：截图如果没拍到目标证据，必须重跑，不能硬算已留图

- **错误模式**: 虽然已经生成了截图文件，但截图并没有真正把目标证据拍进可见区域；如果不做图片回看，就会误把“拍到了页面”当成“拍到了问题证据”。
- **正确做法**: 正式 UAT 截图必须在回看阶段逐张核对“目标证据是否真的出现在图里”；如果截图没有拍到关键证据，就不是合格留存，必须修脚本或重跑，再重新回看。
- **适用场景**: 可滚动容器、图表窗口、宿主设置页、iframe 嵌套页面、任何“截图成功但证据可能仍在视口外”的用户可见流程测试。
- **相关文档**: `docs/testing.md`, `docs/test-reports/assets/2026-03-27-edc-server-switch-stale-groups/screenshot-review.json`

### 2026-03-27 部署命令：`systemctl --user` 不能默认假设当前 shell 已带 user bus 环境

- **错误模式**: 在 agent、脚本或非交互 shell 里直接执行 `systemctl --user stop/restart ...`，默认认为当前进程一定已经带上 `XDG_RUNTIME_DIR` 和 `DBUS_SESSION_BUS_ADDRESS`。结果命令本身不是服务故障，却先失败在“Failed to connect to user scope bus”。
- **正确做法**: 只要运行 `systemctl --user`，就先判断当前 shell 是否具备 user bus 环境；在自动化脚本或非交互 shell 中，默认补齐 `XDG_RUNTIME_DIR=/run/user/$(id -u)` 与 `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus`，再执行服务控制命令。
- **适用场景**: 发布脚本、重启本机 user service、部署联调、AI 代理执行 `systemctl --user` 的任何场景。
- **相关文档**: `scripts/sync-edc-server.sh`, `scripts/publish-edc-web-and-asns.sh`

### 2026-03-27 后端测试执行目录：相对 SQLite 路径的 pytest 不能忽略当前 cwd

- **错误模式**: 后端配置使用相对 SQLite 路径（如 `sqlite+aiosqlite:///./data/asns.db`）时，从仓库根目录直接跑 `apps/server` 的 pytest，默认以为只要 `PYTHONPATH` 对了就够了。结果数据库路径相对到错误目录，测试初始化直接报 `sqlite3.OperationalError: unable to open database file`。
- **正确做法**: 只要后端测试依赖相对数据库路径，就必须保证测试从正确工作目录启动；优先在对应服务目录内执行 pytest，或把数据库 URL 显式改成当前命令上下文可解析的绝对路径，不要只修 import 路径却忽略 cwd。
- **适用场景**: FastAPI + SQLite 项目、本地 runtime DB 复用测试、仓库多子应用结构、AI 代理跨目录执行 pytest。
- **相关文档**: `apps/server/src/config.py`, `apps/server/tests/conftest.py`

### 2026-03-27 错误态语义：请求失败不能伪装成“未绑定 / 未配置 / 空数据”

- **错误模式**: 接口请求实际失败或超时后，前端把状态静默清空成默认值，再沿用“未绑定宿主通道”“暂无数据”这类业务空态或配置空态文案，导致用户看到的是假空页，真实的 transport / backend failure 被掩盖。
- **正确做法**: 请求失败必须优先展示真实失败原因；只有请求成功且业务上确实为空、未绑定或未配置时，才能显示对应空态文案。不要把“请求失败”降级成“业务为空”或“配置缺失”。
- **适用场景**: Dashboard 实时曲线、列表页首屏加载、详情页数据卡片、宿主来源信息、任何“失败态”和“空态”都可能共存的页面。
- **相关文档**: `apps/web/src/stores/dashboard.ts`, `apps/web/src/components/dashboard/RealtimeChart.vue`, `apps/web/src/views/DashboardView.vue`

### 2026-03-27 上游依赖联调：本地 happy path 不能外推为部署环境也可达

- **错误模式**: 用户本地部署或开发机上游依赖可达，就默认推断“部署机也应该一样”，把本地 happy path 当成公网 happy path 的替代证据。结果真实问题其实出在部署环境到上游服务的网络可达性，而不是应用代码本身。
- **正确做法**: 只要链路依赖外部上游，就分别验证“本地环境 -> 上游”和“部署环境 -> 上游”。当用户说“我本地可以”时，下一步不是继续猜前端，而是直接检查部署机到上游的连通性、超时、认证与返回时间。
- **适用场景**: EDC 上游、第三方 API、宿主反向代理、数据库/缓存等外部依赖联调，尤其是“本地正常、线上异常”的场景。
- **相关文档**: `docs/test-reports/2026-03-27-edc-realtime-timeout-investigation.md`

### 2026-03-27 shell 请求命令：带 `&` 的 URL 必须整体加引号

- **错误模式**: 在 shell 里直接执行带查询串的 URL，但没有给整条 URL 加引号；像 `&page_size=5` 这类参数会被 shell 当成后台分隔符，最终命令实际请求的 URL 和以为的 URL 不一致，导致观测结果失真。
- **正确做法**: 只要 URL 中包含 `&`、`?` 等 shell 敏感字符，就对整条 URL 加引号；不要凭“看起来能跑”就相信结果，必要时把实际请求 URL 明确打印出来再判断。
- **适用场景**: `curl`、`wget`、shell 脚本里的 HTTP 调试、手工接口复验、任何带 query string 的命令行请求。
- **相关文档**: `docs/progress.md`

### 2026-03-27 视觉验收闭环：截图文件存在不等于已回看 PNG 内容

- **错误模式**: 在图表页、Dashboard 或其它需要视觉验收的场景里，只要自动化已经生成截图文件，就把它当成“视觉闭环已完成”，继续依据 `API 200`、`series point count > 0`、`截图路径存在` 直接写“通过”，却没有重新打开 PNG 本身确认图里到底是可见曲线、明确错误态，还是误导性的假空态。
- **正确做法**: 只要结论依赖截图，视觉闭环必须包含最后一步“截图后回看 PNG 本身”。允许结合 DOM、接口和像素审计辅助判断，但不能用“文件存在”替代“内容已复核”。只有截图内容本身已确认且结论已明确写出，才允许写“视觉通过”。
- **适用场景**: `Dashboard` 实时曲线、`heat compare`、`炉次详情图表`、`baseline detail`、`preview-curves`、错误态截图验收、发布后 smoke 截图核验、任何需要用截图证明“页面真的长这样”的场景。
- **相关文档**: `docs/test-reports/2026-03-27-visual-evidence-audit.md`, `docs/test-reports/2026-03-27-edc-realtime-timeout-investigation.md`

### 2026-03-27 列表跳详情：展示编号不能替代 canonical 详情 ID

- **错误模式**: 在 Dashboard 最近炉次列表里直接把展示给用户的 `heat_no` 当成详情路由参数，导致页面跳到 `/heats/H20260327-0002` 这类展示编号 URL，而后端详情接口实际只认 canonical `heat.id`，最终详情页请求 `404`。
- **正确做法**: 任何列表跳详情都必须使用后端返回的 canonical 主键字段；展示编号、业务编号、炉次号只能用于显示，不能替代详情页路由参数。回归测试里也不能再偷懒把 `id` 和 `heat_no` 设成同一个值。
- **适用场景**: Dashboard 最近炉次、Heat list、Baseline list、任务列表、任何“页面展示编号”和“真实详情主键”可能不同的前端跳转场景。
- **相关文档**: `apps/web/src/components/dashboard/HeatList.vue`, `apps/web/e2e/full-review-acceptance.spec.ts`

### 2026-03-26 图表验收：heat compare / 炉次详情曲线必须走视觉闭环

- **错误模式**: 只看到 `compare API 200`、`data-series-count > 0`、tab/legend/source banner 正常、没有 console error，就直接把图表写成“正常/通过”，却没有证明前端最终 chart 入参仍有有效点，也没有提供肉眼可见折线截图。
- **正确做法**: 曲线类页面只能按视觉闭环判通过：先确认 compare API 至少一条 current 曲线和一条 baseline 曲线有有效点；再确认前端 transform 后喂给 chart 的 runtime series 仍有有效点；最后必须提供带标注截图，且截图里肉眼能看到有效折线。以上三项缺任一项，都不能写“通过”。
- **适用场景**: `heat compare`、`炉次详情图表`、`baseline detail`、`preview-curves`、任何需要证明“图表真的画出来了”的页面验收。
- **相关文档**: `docs/test-reports/2026-03-26-heat-compare-uat.md`, `apps/web/src/views/HeatDetailView.vue`

### 2026-03-25 设置表单取消动作：没有已保存快照时不要放“取消修改”

- **错误模式**: 在设置页或编辑表单里直接放出“取消 / 放弃修改”按钮，但 store 只有一份正在编辑的可变 `data`，没有“最近一次已加载/已保存”的快照；结果按钮不是 silent no-op，就是只能靠整页重拉才能回退。
- **正确做法**: 只要页面公开了取消/放弃修改动作，就必须为对应区块保留最近一次已加载或已保存的快照；保存成功后同步更新快照，取消时只回退该区块的未保存字段。若当前没有快照和回退语义，就不要把按钮做成可点击主交互。
- **适用场景**: 设置页、编辑抽屉、分区保存的配置卡片、任何“允许先改值、再决定保存还是取消”的表单。
- **相关文档**: `apps/web/src/stores/setting.ts`, `apps/web/src/views/SettingsView.vue`

### 2026-03-25 详情页状态机：不能只靠 `current === null` 区分“加载中”

- **错误模式**: 详情页只写“有数据则渲染正文，否则显示 loading”，把 `404/500`、路由切换中的空态和真正的请求中都折叠到同一个 `null` 分支里，结果接口失败后页面长期停留在 `pending / 加载中...`。
- **正确做法**: 详情页至少拆成成功 / loading / error 三态；store 要给详情请求单独维护 `detailLoading / detailError / requestToken`，不要复用列表页通用 `loading`。若路由参数可切换，还要用请求 token 或等价护栏避免过期响应回写。
- **适用场景**: 报表详情、任务详情、炉次详情、任何通过路由参数加载单条明细的页面。
- **相关文档**: `apps/web/src/views/ReportDetailView.vue`, `apps/web/src/views/TaskDetailView.vue`, `apps/web/src/stores/report.ts`, `apps/web/src/stores/task.ts`

### 2026-03-25 后端测试基座：共享 SQLite runtime state 不能跨用例直接复用

- **错误模式**: 只重置 FastAPI API 模块里的 in-memory store，却继续复用同一个 `apps/server/data/asns.db`；同时 pytest client fixture 没显式跑 startup 初始化。结果一部分用例先报 `no such table: settings`，补上 `init_db()` 后又会被上一条测试留下的 `runtime_*` 行重新污染，形成顺序相关。
- **正确做法**: 对依赖 FastAPI lifespan 的后端测试，client fixture 必须先显式执行 startup 所需的初始化；如果测试复用同一个 SQLite 文件，还要在每条测试前清掉 runtime 持久化行，再按当前默认 in-memory 状态重新 seed。对会写同一 SQLite runtime state 的 pytest，默认按串行执行处理，不要并发硬跑。
- **适用场景**: FastAPI + SQLAlchemy + SQLite 本地测试、会把运行态缓存持久化到数据库的 MVP 后端、AI 代理在同一机器上并行启动多条 pytest 时。
- **相关文档**: `apps/server/tests/conftest.py`, `apps/server/src/runtime_state.py`

### 2026-03-25 前端测试基座：不要假设 Node test 环境一定注入 `import.meta.env`

- **错误模式**: 在前端共享模块里直接于模块顶层读取 `import.meta.env.*` 并立刻派生 URL/常量，默认只有 Vite 浏览器运行时会执行，忽略了 Node test 也会 import 同一模块。
- **正确做法**: 对 `import.meta.env` 做一层安全读取包装；同时凡是依赖浏览器 origin 的 URL 推导，都要在无 `window` / 无 origin 时给出可拼接的相对路径回退，避免 Node test 在模块初始化阶段直接崩溃。
- **适用场景**: Vite 前端项目、Node 原生 `node:test`、Vitest、Playwright 以外的纯模块级单测，以及任何会在浏览器与 Node 双环境共享的 API/配置模块。
- **相关文档**: `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

### 2026-03-25 Python 测试环境：不要把残缺的 `site-packages` 目录误判成可运行虚拟环境

- **错误模式**: 看到仓库里存在 `apps/server/venv/lib/python3.11/site-packages`，就默认认为本地已经有完整 pytest 运行环境，随后直接尝试 `python -m pytest`、拼 `PYTHONPATH` 或借用系统解释器硬跑。
- **正确做法**: 对仓库内残留的 Python 环境，先核对三件事：是否存在匹配版本的解释器、是否存在 `bin/python` / `bin/pytest` 等可执行入口、包目录是否完整而不是只剩 `__pycache__`。只要缺任一项，就应视为“环境不完整”，优先记录阻塞并选择安全重建，而不是拿错误解释器继续硬跑。
- **适用场景**: `uv`/`venv`/`virtualenv` 项目，本地共享服务器，历史环境残留目录，AI 代理在陌生机器上接手 Python 测试任务时。
- **相关文档**: `apps/server/pyproject.toml`, `apps/server/README.md`

### 2026-03-25 搜索/筛选控件收口：正式页可输入过滤器必须真实影响结果

- **错误模式**: 在正式列表页放出可输入的“搜索名称 / 搜索订单号 / 合金号筛选”等控件，但不绑定 `v-model`、过滤计算或查询参数，导致用户能输入文字却看不到任何结果变化。
- **正确做法**: 正式页上的搜索/筛选控件必须满足二选一：要么接入最小可用的本地过滤或真实查询；要么明确禁用/隐藏并说明暂未开放，不能把可编辑但不生效的输入框直接上线。
- **适用场景**: 列表页搜索框、工具栏筛选输入、名称搜索、订单号筛选、任何用户输入后理应改变结果集的控件。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 i18n 收口：运行时 fallback 不能替代正式 locale 和控制台断言

- **错误模式**: 组件调用 `t('key', 'fallback')` 之类的运行时兜底文案后，页面肉眼看起来正常，就误以为国际化问题已经解决，结果控制台仍持续刷 missing-key 告警。
- **正确做法**: 先补齐正式 locale key，再把受影响调用点统一改回直接读取正式 key；同时补一条监听浏览器控制台的自动回归，确保 missing-key 告警真正消失。
- **适用场景**: Vue I18n / React Intl 等前端国际化场景，尤其是导航标题、搜索占位、按钮短文案这类容易用 fallback 临时兜底的壳层组件。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 单页设置导航：侧栏分类要么能定位真实区块，要么不要做成可切换导航

- **错误模式**: 单页设置页左侧做出“选中态 + 分类按钮”的导航样式，但点击后既不切换内容，也不滚动到对应区块，导致用户误以为页面支持模块切换。
- **正确做法**: 对单页设置页的侧栏分类，必须二选一：要么接到真实页内导航（滚动、聚焦、active 跟随当前区块），要么降级成普通说明列表，避免做成伪导航。
- **适用场景**: 设置页、帮助中心、后台配置页、任何“左侧目录 + 右侧单页内容”布局。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 占位按钮收口：正式页上的动作按钮必须要么可用、要么明确禁用

- **错误模式**: 把“刷新数据”这类动作按钮直接放到正式页面，但不绑定任何处理函数，也不给出禁用态或开发中提示，导致用户点击后毫无反馈。
- **正确做法**: 正式页上的动作按钮必须满足二选一：要么接到真实动作并提供最基本的 loading / disabled 反馈，要么明确显示为不可用状态并说明原因；不能把无行为占位按钮直接上线。
- **适用场景**: 刷新按钮、导出按钮、重试按钮、工具栏 CTA、任何会让用户预期触发请求或状态变化的操作入口。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 CTA 语义对齐：按钮文案必须和实际跳转目标一致

- **错误模式**: 为了先占一个入口，按钮文案写成“查看完整报告”这类更宽泛的说法，但点击后实际只是进入单对象详情页，导致用户对目标页面产生错误预期。
- **正确做法**: CTA 文案必须直接描述真实去向和动作；如果当前只会进入详情页，就应明确写成“查看详情 / 查看炉次详情”，不要借用“报告”“审计”等更高层业务词汇。
- **适用场景**: 列表行展开区、卡片底部 CTA、详情页跳转入口、任何用户点击后会切页的动作按钮。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 主页面文案收口：正式中文界面不能残留硬编码英文副标题

- **错误模式**: 页面标题区、副标题、标签徽标这类“最后一层展示文案”直接写死英文，即使默认语言已经是中文，也继续把 `Baseline Library`、`Action Orders`、`High Priority`、`Impact Warning`、`Heat:` 这类英文带进正式界面。
- **正确做法**: 对页面级副标题、卡片标签和列表前缀统一走 locale 或复用现有展示 key；如果是同一业务概念（如关联炉次），优先复用现有 key，避免再造一个新的硬编码别名。
- **适用场景**: PageHeader 副标题、状态标签、列表前缀、卡片辅助说明、任何正式页面最外层的展示文案。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 空指标展示：监控页不能把 `null` 数值直接包装成 `--%`

- **错误模式**: 后端尚未返回偏差百分比等核心数值时，前端仍按数值模板拼接 `%` 单位，最终在正式页面出现 `--%`、`Deviation --%` 这类“像算过但为空”的误导性展示。
- **正确做法**: 对 `null` 指标要先判断“这是缺数据还是待计算”；如果当前链路确实还没算出结果，应显示明确说明文案（如“待计算”），而不是继续套用数值格式和单位。
- **适用场景**: 偏差收件箱、列表指标列、Dashboard 指标卡、任何带单位的实时/准实时业务数值展示。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 列表状态计数：正式页宁可暂时不显示，也不要保留 `...` 占位

- **错误模式**: 页面顶部状态 Tab 只接了“全部”数量，其它状态为了先占位直接写成 `(...)`，导致正式界面长期停留在半成品状态。
- **正确做法**: 状态计数要么接真实数据，要么在未拿到数据前明确不显示数量；如果现有列表接口已经返回 `total`，优先复用同一接口做轻量统计，不要把占位字符串带到正式页面。
- **适用场景**: Tab 筛选条、分段控制、列表页顶部摘要、任何带数量徽标的前端状态切换组件。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 React 恢复逻辑：本地草稿恢复 effect 不能依赖每次重建的函数 props

- **错误模式**: 在页面初始化的 `useEffect` 里直接依赖父组件每次 render 都会新建的函数 props（例如翻译函数 `t`），同时 effect 内又会执行 `setConfig / setState` 这类恢复逻辑；一旦页面上有“测试连接 / 保存草稿”之类会触发父级刷新，就可能把恢复逻辑反复重新触发，最终出现 `Maximum update depth exceeded`。
- **正确做法**: 恢复本地草稿、rehydrate 会话这类“应只在挂载或特定依赖变化时执行一次”的 effect，必须只依赖稳定引用；若父组件需要把函数下传给子组件，应先用 `useCallback` 或等价方式稳定引用，再让子组件把它放进依赖数组。
- **适用场景**: React 宿主页、设置页、本地草稿恢复、localStorage rehydrate、任何 effect 内同时读取持久化数据并回写多处 state 的页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 复合列表头部交互：主切换按钮和次操作按钮必须拆成同级节点

- **错误模式**: 为了让整行都可点击折叠/展开，直接把整行包成一个 `<button>`，再把“整组添加 / 更多操作 / 删除”之类次操作按钮继续塞进里面，导致 `button` 套 `button`，页面持续输出 DOM 结构警告。
- **正确做法**: 复合列表头部应拆成同级交互节点，例如“左侧主切换按钮 + 右侧次操作按钮”，让每个按钮各自承担单一语义，并保证 HTML 结构合法。
- **适用场景**: React/Vue 折叠面板头部、设备组列表、树状目录、卡片头部带展开与附加操作的组件。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 UI 组件升级：第三方控件废弃告警要优先做等价 API 迁移

- **错误模式**: 页面表面还能用，就继续保留第三方组件的废弃 API 写法，让控制台长期刷 warning，后续升级时再一起处理。
- **正确做法**: 对这类“无业务语义变化”的第三方 API 废弃告警，优先做最小等价迁移，并用现有页面回归顺手加一条控制台断言，防止告警回流。
- **适用场景**: Element Plus、Vue、ECharts 等第三方 UI 组件 API 升级，尤其是 `props` 改名但行为不变的场景。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 真实模式文案：接口没有的业务对象不能拿示例值硬填

- **错误模式**: 在真实链路页面里沿用原型或演示期的示例业务号、示例版本号作为副标题文案，即使当前接口根本没有返回这些字段，也继续把示例值展示给用户。
- **正确做法**: 真实模式页面的辅助文案只能使用接口实际提供的字段；如果后端没有返回某个业务对象标识，就应降级成中性描述或来源说明，不能用示例值假装真实数据。
- **适用场景**: Dashboard 卡片副标题、图表说明、详情页摘要、任何“看起来像真实业务对象”的辅助说明区域。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 本地化收口：后端枚举值与前端展示文案之间必须有最后一层映射

- **错误模式**: 前端直接渲染后端透出的原因 code 或硬编码英文标签，导致页面在中文环境下混入 `live_inferred`、`time_offset_exceed`、`Deviation` 这类技术值或英文占位。
- **正确做法**: 枚举值、诊断原因和图表标签在进入 UI 前必须经过最终展示映射；即使后端已返回可读前缀，前端也要对尾部 code 做 locale 转换，避免技术 key 泄漏到正式界面。
- **适用场景**: 异常原因、状态原因、时间轴事件详情、图表卡片标签、任何由后端枚举值拼接出来的前端说明文案。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-25 详情页状态展示：不同业务维度不能共用一个“状态”口径

- **错误模式**: 同一页面同时展示“偏差判定状态”和“切割执行状态”，但标签命名不够明确，用户会把它们误解成同一个状态字段，进一步造成“列表异常、详情正常”的表面冲突。
- **正确做法**: 只要一个业务对象存在两个以上合法的状态维度，就必须在页面上显式命名并区分，例如“偏差状态”“切割执行状态”，不能把次级状态直接包装成唯一“状态”输出。
- **适用场景**: 列表与详情跨页面比对、流程状态与业务判定并存、工业监控页同时展示判定结果与处置结果的场景。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-24 compare 展示窗口回退：不能拿炉次本体短窗兜底

- **错误模式**: compare 详情同时维护“炉次本体窗口主曲线”和“展示窗口 metric_curves”。当展示窗口共享通道曲线偶发缺失时，后端直接拿 `response_item["power_curve"] / ["voltage_curve"]` 兜底，而这两个字段在 compare 路径里通常是炉次本体短窗，结果会把展示窗口图表错误压缩回 30 分钟左右。
- **正确做法**: compare 图表的任何 fallback 都必须坚持同一展示口径；如果 `metric_curves` 目标是“当前炉次前后各 60 分钟”，那缺通道时也只能回退到同一展示窗口的主曲线，不能混用炉次本体短窗。
- **适用场景**: 多时间窗并存的详情接口、图表接口同时返回 summary 曲线和 display 曲线、共享曲线缓存失败后的兜底路径。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-24 live inferred 详情深链：前端不能长期停留在旧推断 URL

- **错误模式**: 后端已把 `live_inferred` 炉次解析为稳定 canonical id，但前端详情页仍长期使用进入页面时的旧 `route.params.id`，加载成功后不把地址替换成后端返回的 canonical `heat_id`。这样同一个旧链接在刷新后会被重新解析到“当前最接近”的炉次，用户会误以为是 compare 图表随机变化。
- **正确做法**: 对运行时推断对象的详情页，前端在拉到详情后必须校准路由；如果接口返回的 canonical id 与当前 URL 不一致，应立即 `router.replace()` 到 canonical 详情地址，并让详情加载逻辑跟随路由参数变化统一重载。
- **适用场景**: 本地推断业务对象、legacy id 兼容 canonical id、live inferred 炉次详情、任何“后端会把旧深链解析到新稳定身份”的页面。
- **相关文档**: BACKEND_STRUCTURE.md

### 2024-02-09 项目初始化

- **错误模式**: 无（项目刚开始）
- **正确做法**: 建立完整的文档体系再开始编码
- **适用场景**: 任何新项目开始时
- **相关文档**: AGENTS.md

### 2026-03-11 UI 重构：Vite 与 Tailwind 类名加载失败

- **错误模式**: 新增了自定语义化的工具类 (如 `shadow-card`, `border-light`) 在 Vue 文件使用 `@apply` 导致 `[plugin:vite:css] The class does not exist`。
- **正确做法**: 在开发模式下，当向 `tailwind.config.js` 增加复杂的新主题或层配置时，有时候 Vite/PostCSS 服务器的缓存不会立刻刷新感知，需要停止 dev server 并重启。
- **适用场景**: 批量修改或重构项目 UI 的初期、调整设计令牌时。

### 2026-03-11 UI 重构：Typescript unused 报错导致 Build 失败

- **错误模式**: 在批量替换 Element 组件为原生 HTML/Tailwind 后，遗留的未使用 `import { ElComponent } from 'element-plus'` 或未使用的 `useRouter` 等钩子会直接触发 `TS6133` Error 阻断 Vite 构建。
- **正确做法**: Refactor 完成一个页面后，必须通过 `vue-tsc -b` 或至少肉眼审查 `<script setup>` 顶部的引入区，剔除不再使用的依赖。
- **适用场景**: 大规模的组件抽离/替换期。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-12 UI 联调：步骤条与时间选择状态不同步

- **错误模式**: 在 Element Plus `ElSteps` 中直接把 0 基索引传给 `active`，以及同时维护时间戳和 `Date` 两套选区状态，容易导致步骤高亮和时间输入框显示不同步。
- **正确做法**: 向导步骤统一维护 0 基业务状态，但传给 `ElSteps` 时转换为组件期望值；选点时间只保留一套单源状态（建议时间戳），图表、输入框、弹窗、滑块全部复用该状态。
- **适用场景**: 向导页、多步表单、图表选区、全屏弹窗共享状态的交互页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-12 UI 自动化：双向同步 watcher 容易触发递归更新

- **错误模式**: 同时监听滑块区间和起止时间两个响应式源，并在各自 watcher 中互相回写，容易在 Vue 中触发 `Maximum recursive updates exceeded`，导致弹窗打不开或页面局部失效。
- **正确做法**: 对双向同步状态建立单一归一化函数，并使用显式同步锁或守卫位，避免 watcher 在一次同步周期内重复回写自身依赖。
- **适用场景**: 时间区间选择器、range slider、双输入框联动、图表选区同步等交互。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-12 UI 自动化：表单内原生按钮默认会触发 submit

- **错误模式**: 在 `ElForm` 或原生 `<form>` 上下文里使用原生 `<button>` 却未声明 `type="button"`，点击保存类按钮时浏览器会默认 submit，导致当前路由附带 `?` 重载或意外跳转。
- **正确做法**: 表单中所有非提交语义的原生按钮必须显式写 `type="button"`；如果确实要提交，则统一走明确的 submit 处理逻辑。
- **适用场景**: 设置页、编辑弹窗、任意含原生按钮的表单容器。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-12 后端测试：全局 mock store 会造成顺序相关

- **错误模式**: FastAPI 路由模块内直接持有全局 in-memory store，测试里执行创建、更新、删除后，如果不恢复初始状态，后续用例会依赖执行顺序，出现偶发失败或断言漂移。
- **正确做法**: 在 `pytest` 中使用 `autouse` fixture 对全局 store 做快照与恢复；涉及计数器、自增索引时也要一并还原。
- **适用场景**: 使用模块级 mock 数据、内存仓库、全局缓存来承载 API 原型或 MVP demo 数据的后端项目。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-12 后端测试：主流程通过不代表状态机安全

- **错误模式**: 只验证 CRUD 主路径，容易漏掉“已发布不可编辑”“已完成不可取消”“非法枚举值应返回 422”这类状态机和校验边界，导致前端联调后才暴露问题。
- **正确做法**: 每个 API 模块除成功路径外，至少补一组非法状态转换、资源不存在、参数越界的测试，优先覆盖 400/404/422 分支。
- **适用场景**: 基于 FastAPI/Pydantic 的 CRUD 与工作流接口。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-12 测试工程化：缺少统一入口会削弱回归执行率

- **错误模式**: 前端和后端测试命令分散在不同目录，人工需要记忆多条命令，久而久之就只跑其中一部分，导致回归执行不完整。
- **正确做法**: 在仓库根目录提供统一的检查脚本，把常用 lint、build、unit、e2e、pytest 串成一条命令，并允许按场景跳过最重的步骤。
- **适用场景**: 多应用仓库、前后端分离仓库、需要频繁本地回归验证的项目。
- **相关文档**: docs/testing.md

### 2026-03-12 云端回归：CI 应与本地检查口径保持一致

- **错误模式**: 本地和云端分别维护两套不同的检查命令，容易出现“本地过了但 CI 挂了”或“CI 没覆盖本地关键回归”的偏差。
- **正确做法**: 先收敛本地统一检查入口，再让云端工作流复用同一批 lint、build、unit、e2e、pytest 约束；增加新测试时同步更新本地文档和 CI。
- **适用场景**: 需要把本地验证迁移到 GitHub Actions、GitLab CI 等云端执行环境的项目。
- **相关文档**: docs/testing.md

### 2026-03-12 云端 Codex：不要把 Windows 专用脚本当成默认入口

- **错误模式**: 只提供 `.ps1` 检查脚本，会让 Codex cloud 或 Linux runner 无法直接复用现有回归入口，必须临时拼接命令。
- **正确做法**: 为统一验证链路同时提供 Windows 和 Bash 两种入口，保证本地、GitHub Actions、Codex cloud 都能执行同一套检查。
- **适用场景**: Windows 本地开发、Linux 云端执行、需要把测试任务下放给 Codex cloud 的仓库。
- **相关文档**: docs/testing.md

### 2026-03-12 Bash 回归：浏览器测试容易被代理环境污染

- **错误模式**: 在 Bash 环境直接运行 Playwright 时继承了本机 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` 的 `socks5` 配置，导致浏览器协议初始化失败，即使项目本身并不依赖外网。
- **正确做法**: 对本地浏览器回归脚本显式清理代理环境变量，避免代理设置影响无外网依赖的 E2E 测试。
- **适用场景**: Git Bash、本地代理/VPN 环境、Codex cloud 或 Linux runner 中执行 Playwright 回归。
- **相关文档**: docs/testing.md

### 2026-03-13 国际化回归：只校验 key 不足以覆盖运行时风险

- **错误模式**: 仅检查多语言文件的 key 是否存在，无法发现 `{count}`、`{major}` 这类插值占位符在不同语言间不一致的问题，运行时会表现为文案变量丢失或原样泄漏。
- **正确做法**: locale 回归检查除 key 结构外，还应校验每条字符串的占位符集合是否与基准语言一致，并自动覆盖新增 locale 文件。
- **适用场景**: 使用 `vue-i18n`、`react-intl` 或其他基于 JSON 文案表和插值变量的前端项目。
- **相关文档**: docs/testing.md

### 2026-03-13 E2E 稳定性：优先等待测试锚点而不是文案细节

- **错误模式**: Playwright smoke test 直接等待对话框里的长文案或假设步骤按钮会瞬时可点击，容易在并行运行或异步渲染时偶发超时，即使功能本身没有回归。
- **正确做法**: 优先使用稳定的 `data-testid` 作为等待条件；跨步骤向导点击后，要显式等待下一步关键按钮或容器出现，再继续操作。
- **适用场景**: Vue/Element Plus 弹窗、向导、多步骤表单、并行执行的 Playwright UI 回归。
- **相关文档**: docs/testing.md

### 2026-03-13 UI 联调：展示问题常常需要补数据结构而不只是改模板

- **错误模式**: 看到“图上只有两根线”这类 UI 问题时，只在前端模板层补图例或切换逻辑，容易把问题修成假象，因为接口本身并没有把多指标曲线数据提供出来。
- **正确做法**: 先确认问题是视图渲染缺陷还是接口结构缺陷；像炉次详情这种多指标对比场景，需要前后端一起补齐可表达的数据结构，再让前端按定义渲染。
- **适用场景**: 多指标图表、对比分析页、依赖 mock/API 联调的数据可视化页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-13 后端回归：pytest 工作目录会影响 asyncio 模式

- **错误模式**: 在仓库根目录直接跑 `apps/server` 的 pytest，可能因为根级配置与插件默认模式不同，触发 async fixture 的严格模式告警，看起来像后端全量回归突然失效。
- **正确做法**: 后端 pytest 与 ruff 按 `apps/server` 目录作为工作目录执行，保证读取项目自己的 `pyproject.toml` 与 `pytest` 配置。
- **适用场景**: monorepo、多应用仓库、前后端共仓且各自拥有独立测试配置的项目。
- **相关文档**: docs/testing.md

### 2026-03-13 图表交互：选点与 dataZoom 不能共用一套点击语义

- **错误模式**: 在 ECharts 长时间轴图表上直接用普通 `click + dataIndex` 做选点，同时开启 `inside dataZoom` 的拖动/缩放，会把“点击选点”和“拖动平移”混在一起，表现为按钮看起来能切换，但起止时间并不稳定更新，或者拖动后误触发选点。
- **正确做法**: 对选点和拖动建立明确的事件边界。选点应根据坐标系位置反算最近时间点；拖动/缩放只更新 zoom 状态，不应回写起止时间。遇到这类 canvas 图表问题时，先补足隐藏测试锚点，把当前边界、选区值、zoom 窗口暴露出来，再写 Playwright 验收。
- **适用场景**: ECharts 或其他 canvas 图表中同时存在点选、全屏、dataZoom、时间输入框联动的交互页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-16 宿主层设计：不要把系统级连线页做成应用字段配置页

- **错误模式**: 在 ASNS 宿主层的 `连线设置` 中直接放入 `EDC electricity` 的业务字段槽位（如功率、电压、炉温、炉压），把系统级连接、平台级资源整理、应用级字段映射混成一个页面。
- **正确做法**: 宿主层只负责后台连接、通道同步、原始通道目录和平台级标准点位绑定；具体应用再在 `应用商店 -> 已安装应用 -> 应用配置` 中完成自己的业务字段映射。
- **适用场景**: 宿主-插件式架构、多应用商店、系统连接页、平台级数据资源管理设计。
- **相关文档**: docs/ASNS_INTEGRATION_PLAN.md, docs/ASNS_HOST_CONNECTIVITY_REDESIGN.md

### 2026-03-19 默认黄金基线：跨页面口径不能只靠前端局部状态

- **错误模式**: 把“当前默认黄金基线”只当成某个页面或某个 store 的局部状态处理，导致炉次列表、炉次详情、对比接口、分析接口各自拿到不同基线；新增基线后，tab 顺序、偏离度和默认选中结果也会彼此漂移。
- **正确做法**: 在后端维护唯一的 `active_baseline_id` 作为默认黄金基线源头，并让热次列表、详情、对比、分析都复用同一个解析函数；发布、激活、停用时同步维护默认值与回退策略。
- **适用场景**: 任何存在“当前激活版本 / 默认方案 / 全局口径对象”的跨页面业务系统。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-19 E2E 回归：不要把可选提示或瞬时文案当成 smoke 前置条件

- **错误模式**: 在 Playwright smoke 用例里把 `baseline-wizard-binding-warning` 这类依赖测试桩数据的可选提示，或 `ElMessage` 这类瞬时提示文案，直接当作必现断言，导致功能实际正常时仍会误报失败。
- **正确做法**: smoke 断言应优先锚定稳定且必现的结构或业务结果，比如 `data-testid`、下一步关键容器、列表中新增的业务实体；需要覆盖“未绑定警告 / 发布成功提示”这类分支时，应单独用明确数据桩驱动该场景。
- **适用场景**: Vue/Element Plus 弹窗、向导流程、依赖接口 mock 数据的 Playwright 回归。
- **相关文档**: docs/testing.md

### 2026-03-20 原型后端：模块级 in-memory store 不适合作为跨刷新真源

- **错误模式**: 继续把基线定义、基线实例、宿主通道、设置、炉次修改状态都放在路由模块级全局变量里，只要 dev reload、服务重启或页面刷新重走初始化，就会表现成“刚创建的数据消失”“页面突然暂无数据”“筛选结果像换了个环境”。
- **正确做法**: 原型阶段即便还没做完整仓储层，也要把这些运行态统一落到可恢复存储（本项目先落 SQLite `settings` JSON）；所有写入口必须同步持久化，启动时统一恢复。
- **适用场景**: FastAPI MVP、模块级 mock store、多页面共享同一批运行态对象、开发期频繁 reload 的后端原型项目。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 联调整体验收：数据暂未切真时必须先把来源标清

- **错误模式**: 页面上既展示了演示台账又挂接了部分真实曲线，但界面没有明确区分，用户只能凭曲线形态猜“这到底是不是真实数据”，最终把“来源不透明”误判成“功能坏了”。
- **正确做法**: 在真实替换尚未完成前，接口和页面都要显式返回/展示来源字段，至少区分“主记录来源”“当前曲线来源”“对比基线曲线来源”，不要让 demo 数据伪装成真实数据。
- **适用场景**: 原型系统、分阶段替换真实数据源、前后端联调期的可视化页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-20 真数据替换：先验证上游接口能力，再决定是否继续下沉实现

- **错误模式**: 看到“炉次台账还不是真实数据”就直接往代码里冲，默认上游一定有现成热次接口，结果花大量时间在猜测 request 名、拼假适配层，最后才发现基座只支持设备清单和历史曲线。
- **正确做法**: 在做真实数据替换前，先用文档和现网做一次最小能力探测，确认上游到底提供的是“业务对象接口”还是“原始时序接口”；如果只提供原始曲线，就要把方案切换成“本地推断”或“等待上游补接口”，不要把不存在的上游能力当成实现前提。
- **适用场景**: 第三方平台接入、工业网关、只读 API 联调、分阶段替换 mock/demo 数据源。
- **相关文档**: docs/ASNS_INTEGRATION_PLAN.md

### 2026-03-20 阶段替换：一旦引入推断炉次 ID，所有下游时间窗入口都要一起兼容

- **错误模式**: 只把炉次列表替换成真实曲线推断结果，却忘了基线 preview、基线实例取时间窗、炉次详情/分析这些后续链路仍只认 `_HEAT_STORE` 里的 demo id，最终会出现“列表能看见真实炉次，但创建基线时又提示来源炉次不存在”。
- **正确做法**: 如果炉次主记录不是持久化真表，而是运行时推断对象，就要先抽出统一的炉次解析函数，让列表、详情、分析、基线 preview、基线实例时间窗都走同一套 `resolve_heat_*` 入口，不要让不同模块各自直读内存 store。
- **适用场景**: 本地推断业务对象、虚拟记录 ID、从原始时序临时生成列表对象的原型系统。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-21 推断对象身份：不要把波动边界当成业务主键

- **错误模式**: 直接把推断炉次段的 `start/end timestamp` 拼成主键，导致重新推断时只要边界秒级抖动，同一逻辑炉次就会拿到新 ID，进而把详情链接、基线 `source_heat_id`、分析结果缓存全部打断。
- **正确做法**: 对运行时推断对象使用稳定 canonical identity，把时间边界只作为匹配线索而不是主键本身；同时保留 legacy ID 解析层，保证旧链接和旧持久化引用能被映射回当前 canonical 记录。
- **适用场景**: 本地启发式切割、时序数据推断对象、缓存 TTL 内会重复重算的虚拟业务记录。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 宿主联调：不能只测直开业务页，必须走“宿主恢复 -> 宿主配置页 -> 宿主内嵌应用”整链路

- **错误模式**: 只验证 `3000` 业务前端和 `8000` 后端接口，以及已有自动化用例，没重新走一遍 `3001` 宿主恢复流程，结果漏掉了“宿主 localStorage 草稿”和“业务后端持久化设置”启动后没有自动对齐的问题。
- **正确做法**: 只要改动涉及宿主状态、嵌入式入口、共享连接或共享通道集合，就必须补一轮完整联调：重开宿主、查看连线设置状态、再从宿主打开业务应用，确认宿主显示、后端持久化状态和业务页实时数据三者一致。
- **适用场景**: 宿主-业务应用架构、嵌入式 iframe 入口、连接配置与业务数据源分层保存的系统。
- **相关文档**: docs/ASNS_INTEGRATION_PLAN.md

### 2026-03-20 真实数据联调：不要把“实时曲线通了”误当成“炉次浏览链路也通了”

- **错误模式**: 先修通了 Dashboard 的真实实时曲线或宿主同步，就默认“真实数据已经接好了”，但炉次浏览 / 基线向导 Step 2 其实走的是另一条链路：它依赖真实炉次推断开关、炉次列表接口和基线 hydrate 逻辑，和 Dashboard 不是同一个调用面。
- **正确做法**: 把“真实数据”拆成最少三条独立链路分别验证：实时曲线、炉次主记录、基线 preview。只要其中一条仍有持久化开关关闭、慢查询或错误语义混淆，就不能宣称“真实数据已打通”。
- **适用场景**: 一套系统同时存在实时接口、推断对象列表、预览接口，且不同页面共享“真实数据”表述的联调阶段。
- **相关文档**: docs/ASNS_INTEGRATION_PLAN.md, BACKEND_STRUCTURE.md

### 2026-03-20 前端告警语义：超时不能直接归类成“后端未连接”

- **错误模式**: 在 Axios 拦截器里只要 `error.response` 为空，就统一提示“后端服务未连接”；当接口其实是慢查询、超时、网关问题或跨域异常时，用户会被带偏去排查“服务没起”，而不是真正的性能或链路问题。
- **正确做法**: 区分至少三类失败：后端真的未启动/拒连、请求超时、后端返回业务错误；联调时先记录接口真实耗时，再决定该修后端性能、代理层，还是提示文案。
- **适用场景**: Axios/Fetch 全局拦截器、联调期前端统一错误提示、存在 10 秒级以上慢接口的管理后台。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-20 Mock 治理：不能让前端和后端各自决定要不要回退假数据

### 2026-03-24 炉次列表性能优化：轻量视图不能和筛选口径脱节

- **错误模式**: 为了把 `/api/heats` 做轻量化，只保留炉次列表最小字段，却继续直接用旧 `status` 做“异常/待处理”筛选；一旦列表页未按当前 active baseline 重算偏离度，前端切到“异常”就会误以为“炉次浏览没数据了”。
- **正确做法**: 只要页面允许按 `status`、偏离度等派生字段筛选，列表接口就必须先按当前业务口径把这些派生字段算出来，再做过滤。可以压缩曲线和子面板数据，但不能让筛选依赖过期或未 hydrate 的状态。
- **适用场景**: 列表接口轻量化、偏差监控列表、任何“列表页快速返回 + 详情页重计算”并存的场景。
- **相关文档**: BACKEND_STRUCTURE.md

- **错误模式**: 后端有 `enable_mock_dataset`，前端又有 `VITE_ENABLE_MOCK_DATASET`，再加上各个 store 各写一套 `catch -> fallback mock`，最终同一个系统里不同页面会出现完全不同的失败语义：有的报错、有的空态、有的偷偷出现假数据。
- **正确做法**: mock 决策权必须收口到后端，并且普通业务接口与专用 mock 接口要分开。前端只负责展示接口结果，不负责本地拼业务数据；普通接口真实失败时就返回错误/空态，显式 mock 只能通过专用接口进入。
- **适用场景**: 管理后台、工业监控系统、存在演示数据与真实数据双模式的前后端分离项目。
- **相关文档**: BACKEND_STRUCTURE.md, FRONTEND_GUIDELINES.md

### 2026-03-20 测试夹具：不要把 demo seed 默认当成普通业务真源

- **错误模式**: 后端测试直接复用模块里的 demo seed 炉次，久而久之会把 `heat-001`、`demo_seed` 变成普通接口的隐式前提；一旦开始做“源头切真”，测试会反向绑架实现，逼着代码继续把 demo 数据暴露给正式链路。
- **正确做法**: 测试如果需要稳定炉次样本，应显式造测试专用夹具，例如 `historical_import` 或 `live_inferred`；mock stream 也要走单独 store 和单独接口，不要和普通 `/api/heats` 共用一份种子数据。
- **适用场景**: 逐步把 demo/mock 数据替换成真实数据源、存在显示层与显式演示接口双轨并行的后端原型项目。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 列表接口：不要在列表请求里做详情级 hydrate

- **错误模式**: 把 `/api/heats` 这类列表接口写成“分页后再逐条 hydrate 基线、拉曲线、算偏差”的重接口，结果单页 50 条就能拖到 30 秒级，前端只会看到超时，像是“没有拿到真实数据”。
- **正确做法**: 列表接口只返回列表必需字段和本地可得的轻计算结果；需要实时曲线、完整 compare、多指标水合的逻辑应留在详情或专用接口。性能优化的第一刀应先拆掉列表级 hydrate，再看剩余慢点。
- **适用场景**: 管理后台列表页、工业时序系统、同一对象同时存在列表/详情/对比三种读取深度的后端 API。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 详情性能：先砍重复请求，再拆单接口重链路

- **错误模式**: 炉次详情页同时请求 `get / getCurve / getCompare / getCuttingTimeline`，展开预览又再打一轮 `getCurve + getCompare`；即使单个接口还能接受，页面整体也会因为重复 IO 和重复计算显著变慢。
- **正确做法**: 先从调用面去重，优先复用信息量最大的接口结果，例如用 `getCompare` 覆盖基础信息与曲线，再单独补时间轴；只有在去重后仍然慢，才继续拆后端 `compare` 的内部重链路。
- **适用场景**: 前端详情页、展开区预览、一个领域对象存在多个高度重叠接口的管理后台。
- **相关文档**: FRONTEND_GUIDELINES.md, BACKEND_STRUCTURE.md

### 2026-03-20 短 TTL 缓存：cache key 不能绑定 hydrate 过程中会变化的字段

- **错误模式**: 给重接口加响应缓存时，把 `curve_source`、`updated_at` 这类会在 hydrate 过程中被刷新或补写的运行态字段塞进 cache key，结果第一次请求执行完后对象状态变了，第二次请求计算出的 key 也跟着变，表面上“已经加了缓存”，实际上永远打不到。
- **正确做法**: cache key 只使用稳定身份字段和必要的版本边界；对会在请求过程中变化的字段，改用显式失效策略而不是直接拼进 key。像炉次 compare 这种场景，更适合用 `heat_id + 时间窗 + baseline_ids` 这类稳定组合，再在更新/分析后手动失效。
- **适用场景**: 后端响应缓存、短 TTL 内存缓存、请求过程中会 hydrate/补写对象字段的聚合接口。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 预览口径：当图表按整天取数时，必须把口径和选区变化说清楚

- **错误模式**: 基线向导里切换不同炉次会重新请求 preview，但后端实际按“所选炉次所在自然日整天”返回曲线；如果前端不提示这个口径，也没有加载态，用户就会把“同一天内图形主体几乎不变”误判成“没刷新”或“请求卡住”。
- **正确做法**: 只要预览图不是严格按所选对象窗口取数，就必须在界面上显式展示当前口径和当前对象时间窗；同时补 loading 状态与请求防抖/防旧结果覆盖，避免正确行为看起来像没反应。
- **适用场景**: 选列表对象驱动大图预览、整日时序图、窗口选点向导、同一天不同对象共用一张主曲线的交互页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-20 多指标时序图：不要先按完全相同的 timestamp 强行合并

- **错误模式**: 功率、电压、温度等多条真实曲线采样频率不同、时间戳也不完全对齐，却先按“timestamp 完全相同”硬合并成一个 `pointMap` 再绘图，结果大量点位对不上，页面看起来像只有零星数据或只有某一条主曲线有值。
- **正确做法**: 多指标时序图应让每条 series 直接使用自己的原始 `[timestamp, value]`，共用时间轴即可；只有在业务上明确约定了重采样/聚合规则时，才做分钟级或秒级统一对齐。
- **适用场景**: ECharts 多折线图、工业实时曲线、不同设备/不同采样频率通道共图展示的前端页面。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-20 Mock 切换：用请求级模式切数据集，不要让前端页面自己决定

- **错误模式**: 把 mock 入口分散在页面按钮、本地 store 和后端全局配置里，结果用户虽然只是在 URL 上切了一次演示模式，实际却会出现“有的接口还是实时、有的接口还是演示、有的页面跳转后丢模式”的混搭状态。
- **正确做法**: 让 `showtime=true` 成为唯一用户入口，并在前端统一透传为请求级 header；后端按每个请求判断是否允许 mock，普通接口默认真实 only，只有显式 showtime 请求才切换到 mock 数据集。页面内部不要再自行决定“这次要不要演示数据”。
- **适用场景**: 同一套业务 API 需要支持真实/演示双模式、并要求默认真实、演示模式可通过 URL 一键切换的企业软件。
- **相关文档**: BACKEND_STRUCTURE.md, FRONTEND_GUIDELINES.md

### 2026-03-20 系统连接真源：宿主和业务页不能同时保留系统连接写入口

- **错误模式**: 宿主已经负责系统连接与通道同步，但业务应用自己的设置页仍能直接修改 `edc-connection`，结果系统里出现两个写入口，后续任何“谁是上游真源”的讨论都会被双写结构破坏。
- **正确做法**: 系统连接配置只能由宿主写入；业务应用只读展示当前宿主连接摘要，必要时引导用户返回宿主设置页修改。后端负责提供统一读取视图，而不是允许每个业务页重新写系统连接。
- **适用场景**: 宿主 + 子应用架构、嵌入式业务应用、系统级连接与应用级业务参数并存的工业软件。
- **相关文档**: docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md, docs/ASNS_INTEGRATION_PLAN.md

### 2026-03-20 宿主同步：不能只同步配置和通道，连接摘要也必须一起回写

- **错误模式**: 宿主只把 `edc-connection` 和 `host-channels` 写进后端，却把“当前在线/离线、最近同步、节点摘要”留在本地 localStorage。结果 EDC 业务页虽然能读到配置和通道，却拿不到统一的宿主连接状态，只能继续猜或自己补逻辑。
- **正确做法**: 宿主每次保存/恢复/测试连接/同步通道后，都应把 `配置 + 已选通道 + 连接摘要` 一起回写到后端；后端提供独立只读视图，例如 `host-connectivity-status`，供业务页统一读取。
- **适用场景**: 宿主 + 子应用架构、需要把系统级连接状态同步给多个业务应用共享的工业软件。
- **相关文档**: docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md

### 2026-03-20 真源收口：不能只在 UI 上隐藏双写入口，接口层也要限制写权限

- **错误模式**: 页面上把“保存 EDC 连接”按钮藏掉了，但后端写接口仍对普通业务前端开放。这样双写问题只是被 UI 暂时遮住，任何旧代码、调试脚本或后续页面回归都还能继续改系统连接。
- **正确做法**: 当某类状态被重新定义为“只允许宿主写入”时，后端必须同步把写接口收成宿主专用，例如要求专用 header 或独立宿主端点；业务前端只保留只读读取面。
- **适用场景**: 宿主 + 子应用架构、系统级配置与业务级参数混在同一后端时、需要彻底消除双写源头的企业软件。
- **相关文档**: docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md, BACKEND_STRUCTURE.md

### 2026-03-20 E2E 前置：异步默认值加载完成前不要抢点“下一步”

- **错误模式**: 像基线向导这类弹窗会在 `onMounted` 后异步拉定义列表并补默认值，E2E 如果只填一个名称就立刻点“下一步”，有可能在默认 `definitionId` 尚未写入前被前端校验拦下，表现成“测试偶发失败”。
- **正确做法**: 对这种依赖异步默认值的表单，先等待具体字段值或选中态出现，再触发下一步动作；不要把“弹窗已经打开”误当成“表单默认值已经就绪”。
- **适用场景**: 弹窗向导、多步表单、依赖接口回填默认下拉值的 Playwright 用例。
- **相关文档**: docs/testing.md

### 2026-03-20 演示模式扩展：默认页不能残留硬编码演示块，必须统一走请求级 showtime

- **错误模式**: 虽然底层接口已经支持真实数据或请求级 `showtime`，但 Dashboard、任务、报表页面仍保留硬编码演示卡片、合成日报或 seeded 任务，导致用户在默认模式下仍会看到“像是真的”的演示内容。
- **正确做法**: 演示能力必须统一收口到请求级 `showtime=true`；默认模式下，页面只能展示真实接口结果或空态。凡是“演示收件箱”“演示任务待办”“合成日报”这类内容，都不能继续在视图层硬编码保留。
- **适用场景**: 企业软件联调后期、真实/演示双模式系统、同一套业务 API 需要在默认模式保持真实 only 的前后端分离项目。
- **相关文档**: docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md, BACKEND_STRUCTURE.md

### 2026-03-21 Playwright 回归：只 mock 局部接口时，后端基础服务必须先起来

- **错误模式**: 在 Playwright 用例里只拦截本轮新增或重点接口，默认以为其余请求会“无关紧要”；但像基线定义列表、Dashboard 统计这类未被 mock 的基础接口仍会走 Vite 代理到 `8000`，一旦本地后端没启动，测试会以超时或页面缺元素的方式间接失败，看起来像新改动引起回归。
- **正确做法**: 对“部分 mock、部分走真实后端”的 E2E 套件，执行前必须先确认 `127.0.0.1:8000` 已启动；如果不想依赖后端常驻，则要把该用例实际会命中的基础接口一并拦截掉。
- **适用场景**: Playwright 前端回归、Vite proxy 指向本地 FastAPI、测试中只对局部接口打桩的联调项目。
- **相关文档**: docs/testing.md

### 2026-03-21 Playwright 页面回归：新增统一运行态轮询后，要把列表 GET 也一并 mock 完整

- **错误模式**: 页面接入统一运行态后，会在进入页面时固定请求 `runtime-status`，但像基线定义页这类页面本身还会额外触发列表 GET；如果 E2E 只 mock 了 POST/编辑接口，没有把基础列表 GET 一并拦截，就会在后端未启动时表现成“按钮不存在”或“元素超时”，定位上很绕。
- **正确做法**: 对页面级 coverage/spec，用例里必须把“页面首屏必打的 GET 请求”和“当前操作触发的写接口”一起 mock 完整，确保测试完全自洽，不依赖本地后端常驻。
- **适用场景**: 接入统一运行态轮询后的 Vue 页面、Playwright 页面回归、Vite proxy + 部分接口打桩的前端项目。
- **相关文档**: docs/testing.md

### 2026-03-21 命令编排：有前后依赖的命令不能并行执行

- **错误模式**: 把存在明确先后依赖的命令放进并行工具一起跑，例如 `git add` 和 `git commit` 同时执行，结果 `commit` 先启动时看不到暂存改动，表面上像“提交没生效”。
- **正确做法**: 只有彼此独立的读操作或验证命令才并行；凡是存在状态依赖、写入顺序或前置条件的命令，必须串行执行。典型例子包括 `git add -> git commit`、`build -> e2e`、`migrate -> test`。
- **适用场景**: 使用并行工具批量跑命令、需要暂存/提交代码、依赖前一步产物的构建与测试链路。
- **相关文档**: AGENTS.md

### 2026-03-21 本地进程操作：不要把工具策略误判成用户不允许

- **错误模式**: 看到一次命令被策略拦截，就直接把“不能停本地进程”当成事实，提前收手，没有先向用户确认是否允许重启当前联调服务。
- **正确做法**: 区分“当前命令写法/工具策略被拦截”和“用户明确不允许操作进程”两件事；只要任务本身需要冷启动验证，应先确认用户是否允许停止并重启本地服务，再继续排查。
- **适用场景**: 本地联调、性能冷启动验证、需要重启 `uvicorn` / `vite` / 数据服务才能复现问题的排障场景。
- **相关文档**: AGENTS.md

### 2026-03-21 首屏轮询去重：全局运行态不要在深链首屏短时间内连打两次

- **错误模式**: App 级运行态刷新同时挂在 `onMounted` 和路由监听上，直达详情页时会在 1 秒内连续打两次 `runtime-status`；这种请求虽然轻，但会污染首屏请求面，也让“是否存在前端重复请求回归”的判断变得不干净。
- **正确做法**: 全局轮询类状态应只有一个首屏触发源；如果仍可能因路由抖动或重定向产生近邻重复调用，store 侧再补 `in-flight` 或短窗 TTL 去重，保证首屏只发一轮。
- **适用场景**: Vue/Pinia 单页应用、App 级运行态/权限/用户信息读取、需要在直达深链与路由切换时维持稳定请求面的后台系统。
- **相关文档**: FRONTEND_GUIDELINES.md, docs/testing.md

### 2026-03-22 基线时间窗解析：旧 source_heat_id miss 不要回退到 live inference

- **错误模式**: 基线实例仍带着历史 seed `source_heat_id`（如 `heat-ref-002`），但这些 ID 既不在当前 heat store，也不是可解析的 `live-heat-*`。如果时间窗解析在 miss 后仍去跑 `resolve_heat_record()` 的 live inference 兜底，就会把 baseline hydrate 和 heat compare 冷态平白放大到秒级。
- **正确做法**: 默认真实模式下，若 `source_heat_id` 既不在本地 heat store、也不是 live heat ID，应直接回退到保底时间窗，不要为了一个不可能命中的旧 ID 触发 live inference；只有真实 live id 或本地存在的持久化 heat 才值得进入解析链。
- **适用场景**: 运行态虚拟炉次、历史 seed 数据逐步替换为真实推断对象、基线实例仍保留旧来源 ID 的工业时序系统。
- **相关文档**: BACKEND_STRUCTURE.md, docs/ASNS_INTEGRATION_PLAN.md

### 2026-03-22 compare 子链路缓存：先缓存会重复复用的取数层，不要只缓存整份响应

- **错误模式**: 只给 `/api/heats/{id}/compare` 整份响应加短 TTL，觉得“已经有缓存了”；但 baseline hydrate 和按通道批量取当前曲线这两层仍然每次独立打 EDC，导致一旦跨炉次 compare、并发 compare，底层重 IO 还是会重复发生。
- **正确做法**: 对 compare 这类聚合接口，要先识别“会被多个请求复用的子链路”，例如 baseline hydrate 和同窗口通道批量取数；这两层应各自有短 TTL 共享缓存，并补 in-flight 去重。整份响应缓存只能兜完全相同的二次请求，不能替代子链路缓存。
- **适用场景**: 聚合型详情接口、工业时序系统、同一接口下层会复用基线 hydrate / 通道曲线取数 / 外部服务批量读取的后端 API。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-22 compare 失效口径：共享缓存不能只靠 TTL，配置变更要主动失效

- **错误模式**: compare 子链路缓存加上后，只在 heat 自身修改时清缓存，忽略了 baseline 发布/编辑、宿主通道更新、EDC 连接更新这些“会改变 compare 真实曲线和基线曲线口径”的写操作。结果短 TTL 窗口内仍可能读到旧 compare。
- **正确做法**: compare 缓存的失效口径要覆盖所有会改变曲线来源或基线集合的写入口。heat 维度变更可以按 heat 精确失效；baseline 和 host/edc 配置变更则应直接清整组 compare caches，不要指望 TTL 自己兜底。
- **适用场景**: 带短 TTL 内存缓存的聚合详情接口、会受宿主配置/基线发布影响的数据可视化接口、工业时序系统的 compare 或 preview API。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-22 compare 口径：默认详情 compare 不要把额外 draft baseline 混进去

- **错误模式**: compare baseline 列表默认把“主基线 + 所有已发布 + 所有 draft”都返回，虽然看起来信息更多，但会把详情接口做重，也会让默认详情页混入未发布草稿口径，影响用户理解。
- **正确做法**: 默认 compare 只返回“主基线 + 其他已发布基线”。draft baseline 只有在它本身被显式选为主基线时，才应进入 compare 结果；不要把额外 drafts 当成默认对比面的一部分。
- **适用场景**: 存在草稿/已发布双状态的基线系统、详情页默认 compare、聚合型比对接口。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-20 演示模式文案：默认模式不能把用户引到 mock 开关

- **错误模式**: 底层数据链路已经切成“默认真实 only、`showtime=true` 才 mock”，但默认页面的错误文案仍提示“检查 mock 开关”或“显式开启 mock 数据集”，会把用户带回演示思路，也让人误判当前失败是正常 fallback 场景。
- **正确做法**: 默认模式的文案只能围绕真实链路表达，例如宿主连接、通道绑定、后端数据源；只有在显式 `showtime` 演示模式下，页面和接口才可以露出 mock 相关提示与标签。
- **适用场景**: 真实/演示双模式系统、请求级 `showtime` 控制 mock 的企业软件、联调整体验收阶段的错误提示与来源说明。
- **相关文档**: FRONTEND_GUIDELINES.md, docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md

### 2026-03-20 请求级演示曲线：不要把 showtime hydrate 结果写回共享 store

- **错误模式**: 在基线详情这类接口里，为了给 `showtime=true` 请求补 demo 曲线，直接把 hydrate 结果写回模块级共享 store。这样一次 showtime 请求就可能把 `demo_curve` 留在内存里，后续默认模式请求也会读到演示数据，形成“模式串味”。
- **正确做法**: 请求级 showtime 数据必须按请求临时组装后返回，不得回写共享 store；共享 store 里只保留稳定主记录，`curve_source`、`power_curve`、`curves_data` 这类可切换来源字段应在读取时派生。
- **适用场景**: 同一业务对象同时支持默认真实模式与 URL/请求级 showtime 演示模式，且后端仍使用模块级内存 store 或运行态缓存的项目。
- **相关文档**: BACKEND_STRUCTURE.md, docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md

### 2026-03-21 详情页状态机：不能把“无数据对象”直接当成“仍在加载”

- **错误模式**: 报表详情这类页面只用 `detail ? 成功态 : loading` 两个分支渲染；一旦接口失败、字段映射抛错，或成功返回的是空数组场景，页面就会永久显示 `pending / 加载中...`，把“错误/空态”伪装成“还没加载完”。
- **正确做法**: 详情页至少拆出 `loading / success / error` 三态；如果接口存在空列表但仍属成功响应，还要补显式空态。store 中不要只靠 `current = null` 表达全部状态，必要时增加 `detailError`、请求 token 等辅助状态。
- **适用场景**: Vue/Pinia 详情页、依赖异步详情接口的管理后台、列表页跳详情页且接口可能返回空数组或 404 的业务页面。
- **相关文档**: FRONTEND_GUIDELINES.md, docs/testing.md

### 2026-03-22 偶发超时排障：不要只记点击，要把 request_id 串到前后端和 EDC 子调用

- **错误模式**: 只想在前端记录“用户点了哪个按钮”，但没有把点击触发的请求、后端聚合接口和下游 EDC 子调用串起来。结果超时复现后只能看到“点了详情页”，仍然不知道慢在前端超时、后端 compare 聚合，还是 `get_local_datas` 首枪。
- **正确做法**: 最小追踪链路应该包含统一 `request_id`、前端慢请求/超时诊断、后端请求级耗时日志，以及关键下游调用的子步骤耗时。只有这样偶发超时才能从页面一路追到具体接口和 EDC 子调用。
- **适用场景**: 前后端分离系统、偶发请求超时、需要定位聚合接口和外部时序服务哪个环节变慢的工业监控或后台系统。
- **相关文档**: BACKEND_STRUCTURE.md, FRONTEND_GUIDELINES.md

### 2026-03-23 宿主部署：不能把带 `host-api` 的宿主参考工程当纯静态站点上线

- **错误模式**: 看到宿主前端能 `vite build` 出 `dist/`，就直接把静态文件发布到 `/asns/`，同时保留代码里的 `127.0.0.1` 默认地址和根路径资源引用。结果线上会同时出现三类问题：`/asns/` 资源 404、浏览器去访问用户自己机器的 `127.0.0.1`、宿主 `host-api` 被静态站点 fallback 吃掉。
- **正确做法**: 宿主这类既有前端又有宿主专用 API 的工程，部署时必须同时收口“子路径 base + 同域 API 默认值 + 宿主 Node 进程”。如果站点结构是 `/asns/ + /edc/ + /api`，就要在构建时设置子路径 base，并用 Node 服务承接 `/asns/host-api/*`，不能只发静态文件。
- **适用场景**: Vite 宿主应用、前端内嵌业务页、浏览器侧要回写业务后端、同时还带宿主专用中间层 API 的部署场景。
- **相关文档**: docs/DEPLOYMENT.md, docs/HOST_EDC_STATE_CONSOLIDATION_PLAN.md

### 2026-03-23 compare 曲线：聚合接口里不要假设运行态曲线点永远是对象实例

- **错误模式**: 在 `/api/heats/{id}/compare` 里直接把 `response_item["power_curve"]` 当成 `CurvePoint` 对象访问 `.timestamp` / `.value`。一旦运行态或下游返回的是 `dict` 结构，接口就会偶发 500，而且这种问题常常只在真实联调数据下出现。
- **正确做法**: compare/preview 这类聚合接口在进入偏差计算或序列拼装前，要先把曲线统一归一化成同一种结构；对于会混用内存态、SQLite 运行态、Pydantic 模型和 JSON dict 的链路，任何一步都不要跳过 `coerce`。
- **适用场景**: 工业时序曲线聚合接口、缓存或运行态持久化后再读取的曲线数据、后端需要同时消费模型对象与 JSON-like dict 的场景。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-23 compare 重合态：当前炉次与基线完全重合时必须给显式提示

- **错误模式**: 详情页只管把“基线线”和“当前线”都画上去，却不考虑两条曲线可能完全重合。结果视觉上只剩一条线，用户会误以为“当前炉次没显示”。
- **正确做法**: 当 compare 主指标的 baseline/current 时间戳和值完全一致时，页面要明确告知“当前炉次与该基线完全重合”，并同时把两类曲线样式拉开，避免把真实重合误判成渲染缺失。
- **适用场景**: 基于当前炉次反向生成基线、模板对比页、任何可能出现两条完全相同曲线的时序对比图。
- **相关文档**: FRONTEND_GUIDELINES.md

### 2026-03-23 live inferred alias：别名合并不能只看 ID 解析命中，必须同时校验时间窗

- **错误模式**: 为了兼容旧 `live-heat-*` ID，把持久化 live 炉次和当前推断 live 炉次做 alias 合并时，只要 `_resolve_live_heat_candidate()` 能命中就直接合并。对于 canonical live id，这会让“同一 context hash 但完全不同时段”的 live 炉次也被误判成同一条记录，最终在列表页出现多行不同 ID 却显示同一个 `heat_no / start_time / deviation_percent`。
- **正确做法**: live inferred alias 合并至少要同时满足“ID 语义可解析”与“时间窗真实重叠”两层约束。旧 ID 兼容只应该用于同一炉次的小幅边界漂移或 legacy/canonical 迁移，不能跨天、跨段把不同时窗的 live 炉次套到同一条持久化记录上。
- **适用场景**: 实时推断对象使用 canonical ID、运行态会持久化 live 炉次、并且需要兼容旧 live id 或轻微边界漂移的工业时序系统。
- **相关文档**: BACKEND_STRUCTURE.md

### 2026-03-23 compare 展示口径：不要把基线来源炉次的绝对时间戳直接画到当前炉次详情上

- **错误模式**: 新建基线来自历史真实炉次时，compare 图表直接使用基线来源炉次的绝对时间戳作为 x 轴数据。只要当前炉次和来源炉次不在同一天，图表就会被拉成跨天范围，视觉上像“基线和当前炉次完全对不上”。
- **正确做法**: compare 展示层要把基线曲线时间戳重映射到“当前炉次核心窗口”，并把当前曲线展示窗口按当前炉次前后各 `60` 分钟扩展。偏差计算可以继续基于对齐后的核心窗口，但展示层不能裸用来源炉次的原始绝对时间戳。
- **适用场景**: 基于历史炉次创建黄金基线、后续在另一条实时/历史炉次详情中做 compare、前端时序图直接共用 `time` 轴的工业对比页面。
- **相关文档**: BACKEND_STRUCTURE.md, FRONTEND_GUIDELINES.md

<!-- 后续错误记录将添加在此处 -->

### 2026-03-30 UAT 监督：心跳纠偏策略不能和 agent 执行串行冲突

- **错误模式**: 心跳每轮检查发现不合规（API替代视觉确认、隐式验证、截图引用错误）就立刻要求 Gemini 返回修正。Gemini 执行速度慢，心跳每 20 分钟一轮，Gemini 还没改完上一轮的问题，下一轮心跳又来新纠偏指令，形成串行阻塞。结果 7 小时只跑完了 S01-S02（6 条用例），S05-S07 完全未启动。
- **正确做法**: 监督心跳应分两个阶段。第一阶段：全量推进，只记录不合规，不打断 agent 执行。第二阶段：全量完成后，统一汇报不合规清单，再开启修正轮，让 agent 集中修正。
- **适用场景**: 用心跳 cron job 监督 AI agent 执行长时任务（UAT、重构、批量操作），agent 执行速度慢于心跳频率的场景。
- **相关文档**: docs/test-reports/2026-03-30-UAT-S01-S06.md

### 2026-03-30 UAT 监督：视觉确认要求必须在任务开始前明确给 agent，不能靠心跳事后纠偏

- **错误模式**: UAT 规则要求「截图必须描述视觉内容，不能只靠 API 200 判定」，但这个要求没有在任务 prompt 里写清楚，只靠心跳发现后纠偏。Gemini 的默认习惯是 API 验证 + 文件存在 = PASS，心跳纠偏只能事后补救，已经写错的结论需要返工。
- **正确做法**: 视觉确认口径、截图命名规范、判定标准（PASS/FAIL/BLOCKED 条件）必须在任务 prompt 里完整写明，作为 agent 执行的前置约束，而不是靠监督层事后发现再纠正。
- **适用场景**: 让 AI agent 执行需要视觉证据的 UAT 测试、UI 验收、截图类验证任务。
- **相关文档**: docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md

### 2026-03-30 UAT 监督：tmux session/window 目标必须在心跳配置前核实，不能假设

- **错误模式**: 心跳 job 最初配置监控 `codex:1`，实际执行 agent 在 `codex:2`，导致心跳抓错 pane，push 指令发到空 session，监督完全失效数轮。
- **正确做法**: 配置心跳前先用 `tmux ls` + `tmux capture-pane` 核实目标 session/window 名称，确认 agent 在跑后再写入心跳 payload。session 切换时必须同步更新心跳配置。
- **适用场景**: 用心跳 cron job 监督 tmux 内运行的 AI agent（Gemini CLI、Codex、Claude Code 等）。
- **相关文档**: checkpoints/edc-asns-heartbeat-board.md

### 2026-03-31 本机 ASNS 宿主嵌入 EDC：不能只设置进程环境变量，必须确认宿主页真的拿到了 runtime 配置

- **错误模式**: 本机启动 `3001` 时给 Node 进程设置了 `ASNS_EDC_APP_URL=http://localhost:3000/edc/`，但宿主页 `index.html` 没有把这个值注入到浏览器侧。前端实际仍走 fallback `/edc/`，而本机又没配置 `ASNS_EDC_WEB_ROOT`，结果 `/edc/` 被宿主 catch-all 回退成 ASNS 自己的壳页，点击 `EDC electricity` 变成“宿主里再嵌一层宿主”。
- **正确做法**: 宿主 `server.mjs` 这类 Node 入口如果依赖运行时 URL，必须把 `ASNS_EDC_APP_URL`、`ASNS_APP_API_BASE`、`ASNS_HOST_API_BASE` 明确注入到返回的 HTML；同时本机启动脚本要校验首页响应中确实包含这些 runtime 变量，不能只看 `3001` 端口起来了。
- **适用场景**: Node 托管的 Vite/React 宿主页面、浏览器端要消费运行时环境变量、宿主内嵌业务应用或 iframe 的联调环境。
- **相关文档**: docs/DEPLOYMENT.md, docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs

### 2026-04-02 黄金基线向导：不能把 warming 当 empty，也不能让前后端各自解释日期时区

- **错误模式**: 基线向导第二步按日期查询炉次时，前端传的是 ISO UTC 时间串，后端却直接拿它与本地 naive datetime 做比较；同时 UI 在 `snapshot_status=warming/refreshing_history` 时直接展示“当天没有炉次”。结果是明明存在运行态炉次，用户仍看到空态并误判为后端没数据。
- **正确做法**: 列表 API 必须先把查询时间统一归一到业务时区再过滤；UI 必须把 `warming/refreshing_history/ready` 当成不同状态机处理，只有 `ready + empty` 才能渲染真正空态，`warming` 应提示“准备中”并自动重试或触发刷新。
- **适用场景**: 前端按日筛选、浏览器使用 `toISOString()`、后端内部存本地时间、以及任何“后台异步准备快照，前台同步读结果”的页面。
- **相关文档**: apps/server/src/api/heats.py, apps/web/src/components/baseline/BaselineWizard.vue

### 2026-04-03 炉次台账：不要把可重算运行态直接当成历史台账

- **错误模式**: 后端每轮都从实时曲线整批重推最近炉次，然后把这些结果直接当历史列表返回。结果是“已经过去的炉次”时间和编号仍会漂移，详情页还会因为旧运行态 ID 在下一轮重算后失效而偶发 404。
- **正确做法**: 运行态必须与历史固化分层。只保留 `当前炉次 + 前一个炉次` 作为动态运行态，其余一旦退出缓冲区就封口为稳定历史；同时保留旧运行态 ID 到当前有效记录的 alias，避免列表点击与后台重算窗口撞车。
- **适用场景**: 任何通过实时曲线推断业务台账、且用户会把列表记录当成正式历史记录查看与追溯的工业监控系统。
- **相关文档**: BACKEND_STRUCTURE.md, apps/server/src/api/heats.py, docs/testing.md

### 2026-04-07 公网真源重连：`source-switch` 不是完整上线动作，`deploy-refresh` 后还必须重启后端

- **错误模式**: 只调用 `POST /api/settings/source-switch` 把 EDC 地址和账号密码写进后端，就以为公网已经“接上真源”。实际上这一步只更新来源边界和持久化设置，运行中的后端内存态仍可能保持 `host_disconnected / no_enabled_channels`，宿主通道、角色绑定和连接摘要也不会自动变成当前真源的最终运行态。
- **正确做法**: 公网 blank 后重新接真实源，必须按完整顺序执行：`source-switch -> runtime_state_admin --mode deploy-refresh -> restart edc-backend.service -> 再看 runtime-status`。只有重启后，后端才会从 SQLite 重新加载 `runtime_host_channels / runtime_channel_role_bindings / runtime_host_connectivity_status`，真正进入 `overall_code = ready`。
- **适用场景**: 服务器 blank 部署后重新接 EDC 真源、切换数据源、需要让宿主通道目录和角色绑定自动重建的运维场景。
- **相关文档**: docs/DEPLOYMENT.md, docs/session_handoff.md, apps/server/src/runtime_state.py, apps/server/src/runtime_state_admin.py

### 2026-04-08 runtime 统一分析：必须先 hydrate 真源再算 binding

- **错误模式**: 在 `compile_runtime_candidates()` 里先根据旧 `power_curve` 做 binding 分析，再去 hydrate `runtime_metric_series`。这样“分析只吃 runtime/formal 真源”在代码上并不成立，运行态仍然会偷吃旧快照。
- **正确做法**: 先按 definition metrics hydrate 完整 `runtime_metric_series`，再执行统一分析策略，最后再生成 `baseline_bindings / preseal_payload / birth_context`。分析层不得回退到固定 `power/voltage` 字段。
- **适用场景**: 任何 runtime 实时分析、formal 固化前回填、以及需要保证分析输入真源可审计的工业监控链路。
- **相关文档**: docs/BACKEND_STRUCTURE.md, apps/server/src/services/formal_heat_service.py, apps/server/src/services/heat_deviation_analysis_service.py

### 2026-04-09 SQLite 结构调整：默认直接清库重建，不做数据移行方案

- **错误模式**: 一看到表结构或字段语义变化，就默认补 Alembic migration、历史数据兼容和移行方案，导致实现和评审长期背着并不需要的历史包袱。
- **正确做法**: 当前项目的 SQLite 结构调整默认口径是“删除现有数据 / 重建库 / 按最新模型初始化”。后续方案和实现不要再把数据移行作为默认必选项；只有用户明确要求保留历史数据时，才单独设计迁移方案。
- **适用场景**: 本地开发库、测试库、可整体重置的数据环境，以及本项目当前明确允许清空重建的后端结构调整。
- **相关文档**: AGENTS.md, docs/BACKEND_STRUCTURE.md

### 2026-04-09 runtime 多指标分析：分析前必须先把 definition metric snapshots 放进 candidate

- **错误模式**: `compile_runtime_candidates()` 里虽然已经先 hydrate 了 `runtime_metric_series`，但在调用统一分析服务前没有把 `definition_metric_snapshots` 放入 candidate，导致非 frozen runtime 在分析器里拿不到指标定义，统一退化成 `metric_inputs_missing -> pending`。
- **正确做法**: 非 frozen runtime 在进入 `HeatDeviationAnalysisService.analyze_candidate_bindings()` 前，必须先把当前 definition 对应的 metric snapshots 一并写回 candidate。统一分析依赖的是“runtime_metric_series + definition_metric_snapshots + baseline curve payloads”三件套，缺一不可。
- **适用场景**: runtime 实时分析、seal 前统一分析、以及任何先 hydrate 真源再做策略分析的批处理链路。
- **相关文档**: apps/server/src/services/formal_heat_service.py, apps/server/src/services/heat_deviation_analysis_service.py

### 2026-04-09 SQLite 测试库：pytest 子集不能并发跑共享 drop/create 测试库

- **错误模式**: 为了提速同时起多个 pytest 进程，但测试夹具会对同一个 SQLite 文件执行 `drop_all/create_all`。并发执行时会互相打断，出现 `no such table`、重复 seed、唯一键冲突这类假失败。
- **正确做法**: 当前后端测试使用共享 SQLite 文件时，pytest 子集必须串行执行；如果未来要并发跑，必须先把测试库隔离到独立文件或独立进程级目录。
- **适用场景**: 使用 SQLite 作为测试库、fixture 内会重建 schema、并且同一工作区会并发执行多个 pytest 命令的场景。
- **相关文档**: docs/testing.md, apps/server/tests/conftest.py

## [2026-04-10] replay 后 runtime 重建语义不能误写成“一次性重建完就结束”
- **错误模式**: 把 replay 后的 `previous_runtime/current_runtime` 理解成 replay 自己独立重切并一次性产出最终运行态，忽略了它在业务上只是“从 replay 结果重新创建 runtime 起点模板”，后续仍要回到正常 live runtime 增量续接链路。
- **正确做法**: replay 应直接使用 replay 最终结果里的头部两炉去替代 `previous_runtime` 与 `current_runtime` 模板；完成模板重建后，再交还给日常 live runtime 逻辑继续吃新点、更新当前炉次与后续轮换。
- **适用场景**: 任何“历史 replay/批量初始化”之后还要把运行态重新接回实时刷新链路的工业监控系统，尤其是 `current_runtime` 可能尚未完整、需要继续增量补点的场景。

## [2026-04-11] 时间相关测试数据不能混用 `datetime.timestamp()` 与项目内 `to_timestamp_ms()`
- **错误模式**: 在测试里直接对 naive `datetime` 调 `datetime.timestamp()` 构造毫秒值，而项目后端内部时间语义是“UTC naive + `to_timestamp_ms()`”。两套口径一混，replay/live 刷新窗口会在非 UTC 本机时区下整体错位，表现成“明明有点但筛出来是空窗口”。
- **正确做法**: 只要测试数据、请求参数、窗口过滤要和后端内部时间语义对齐，就统一使用 `src.time_utils.to_timestamp_ms()` 与 `from_timestamp_ms()`；不要在测试里直接把 naive `datetime` 交给 `datetime.timestamp()`。
- **适用场景**: replay 测试、live runtime 刷新测试、任何需要构造毫秒时间戳并和后端 UTC naive 时间窗口逐点对齐的场景。

## [2026-04-17] 炉次列表显示层不能越权用时间重叠吞掉 `previous_runtime`
- **错误模式**: `/api/heats` 列表组装阶段把“live 身份续接用的时间窗容差”复用成“formal 是否覆盖 previous”的判断，导致 `previous_runtime` 仅因与 `sealed_history` 首尾相接或时间接近，就在显示层被误吞。
- **正确做法**: 列表显示层只做真源拼接、排序、筛选和 DTO 映射；`formal DB / previous_runtime / active_runtime` 都应按当前真源状态原样进入列表，不在显示阶段做 overlap 去重、覆盖裁决或 alias 写入。
- **适用场景**: 任何 runtime 与 formal 历史混合展示的台账、列表页、浏览页，尤其是同一接口需要同时暴露 `current / previous / sealed_history` 的场景。
