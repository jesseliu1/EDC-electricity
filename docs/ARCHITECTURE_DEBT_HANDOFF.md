# 架构问题交接单（待处理）

> 更新时间：2026-04-01
> 目的：记录本轮已确认、但尚未处理的架构问题，供后续 session / 接手人继续推进。

## 一句话结论

当前系统已经基本做到：

- 系统连接真源主要收口在后端
- EDC 业务前端不再直接承担系统连接写入口

但当前还没有做到：

- 前端只负责展示，后端只负责提供标准化数据
- 后端内部真正按 `API -> service -> repository -> persistence` 分层
- `core / plugin-*` 插件边界真实落地

更准确地说，当前状态是：

> 前后端边界方向大体正确，但后端仍是“运行态快照单体”，前端仍承担了一部分数据推导和展示兜底。

---

## 本轮确认但未处理的问题

### 1. 后端内部耦合过高，API 层直接互相依赖私有实现

**现状**

- `apps/server/src/runtime_state.py` 直接 `import` 各 API 模块并读写它们的 `_STORE`
- `apps/server/src/api/dashboard.py` 直接依赖 `heats / baselines / settings` 的模块级状态
- `apps/server/src/api/tasks.py` 创建任务时直接调用 `heats` 内部函数
- `apps/server/src/services/source_switch_service.py` 虽名为 service，但仍直接修改 `settings / baseline_definitions` API 模块内部状态

**代表文件**

- `apps/server/src/runtime_state.py`
- `apps/server/src/api/dashboard.py`
- `apps/server/src/api/tasks.py`
- `apps/server/src/api/baselines.py`
- `apps/server/src/services/source_switch_service.py`

**问题本质**

- 现在不是“API 调 service，service 调数据层”
- 而是“多个 API 模块共享并互改一组全局 store”
- 这会让任何一处调整都带来较大的回归半径

**影响**

- 难以拆模块
- 难以做插件化
- 难以引入更清晰的测试边界
- 缓存、持久化、业务逻辑、副作用边界混在一起

---

### 2. 业务实体没有真正落到各自正式持久化层

**现状**

- 仓库中已经有 SQLAlchemy 模型：
  - `apps/server/src/models/baseline.py`
  - `apps/server/src/models/heat.py`
  - `apps/server/src/models/task.py`
- 但主运行路径并未真正使用这些模型进行 CRUD
- 当前真实持久化主路径仍是：
  - API 模块级 `_BASELINE_STORE / _HEAT_STORE / _TASK_STORE`
  - `runtime_state.py` 将这些对象整体序列化后写入 `settings` 表的 `runtime_*`

**问题本质**

- “后端是唯一真源”基本成立
- 但“真源是什么”目前仍是运行态快照，而不是清晰的业务表

**影响**

- `settings` 表承担了过多职责
- 后续做迁移、审计、增量更新、并发写入控制都会越来越重
- 与 `BACKEND_STRUCTURE.md` 中声明的目标结构并不一致

---

### 3. 前端还没有完全退回到纯展示层

**现状**

- `apps/web/src/views/HeatListView.vue` 在拿不到 preview 时，会本地生成功率/温度微缩曲线
- `apps/web/src/views/HeatDetailView.vue` 承担了较重的曲线裁剪、补点、选区推导、手工调整窗口推导
- `apps/web/src/components/baseline/BaselineWizard.vue` 也承担了较多 preview 选择态和图表交互推导逻辑

**问题本质**

- 这些不全是“纯显示格式化”
- 其中一部分已经属于数据解释或展示口径决策

**影响**

- 前后端展示口径更难统一
- 后端若要调整 compare / preview 规则，前端也容易同步改动
- 局部页面会继续演化成“半业务层”

**特别注意**

- `HeatListView` 当前的微缩图本地兜底曲线，容易让页面在“无真实 preview 数据”时仍显示一张看起来合理的图
- 这不利于真实链路问题暴露，也不利于 UAT 判断

---

### 4. 插件化架构目前还停留在目标层，没有真实落地

**现状**

- `AGENTS.md` 和项目说明里写了：
  - `core`
  - `plugin-baseline`
  - `plugin-report`
  - `plugin-correction`
- 但当前仓库实际实现仍集中在：
  - `apps/server`
  - `apps/web`
- `packages/` 目录当前没有形成真实运行中的模块边界

**问题本质**

- 当前系统更接近“单体应用 + 文档中的目标插件架构”
- 还不能认为已经实现“模块间解耦，通过接口通信”

**影响**

- 未来按模块销售、按插件裁剪能力时，实际拆分成本会比当前文档预期更高

---

## 当前对“前后台是否真正分开”的判断

### 已经做到的部分

- 系统连接真源主要在后端
- EDC 业务前端设置页当前主要是读后端统一摘要
- 宿主草稿已不再是系统权威真源

### 还没做到的部分

- 前端仍有部分数据推导和兜底造图
- 后端返回给前端的还不是完全稳定、最小、标准化的视图模型
- 后端内部更像“共享运行态单体”，而不是清晰分层服务

### 当前更准确的口径

- 前端：`展示 + 一部分视图级数据加工`
- 后端：`API + 业务逻辑 + 运行态缓存/持久化 + 配置中心`

---

## 建议后续处理顺序

### 第一优先级：先拆后端内部边界

建议先做：

1. 抽离 `runtime state repository / service`
2. 禁止 API 模块直接访问其它 API 模块的私有 `_STORE`
3. 将 `source switch / runtime status / dashboard / task create` 的跨模块逻辑收口到明确 service

**原因**

- 这是当前最大耦合源
- 不先拆这层，后面迁 ORM 或做插件化都会越改越乱

### 第二优先级：将 `baselines / heats / tasks` 迁到正式持久化层

建议目标：

1. `settings` 表只保留真正的系统设置和少量运行时元数据
2. 业务实体走各自业务表
3. `runtime_*` 仅保留确实属于缓存/临时摘要的内容

### 第三优先级：把前端重数据推导下沉到后端

建议目标：

1. 列表微缩图由后端直接提供简化序列或 preview 元数据
2. 手工调整和 compare 所需的窗口元信息尽量由后端给出
3. 删除前端假曲线兜底

### 第四优先级：再谈插件边界落地

建议在前 3 项完成后，再评估：

- 哪些能力真的适合下沉到 `packages/core`
- 哪些页面/API/数据模型属于 `plugin-baseline / report / correction`

---

## 不建议现在直接做的事

- 不建议先做大规模“插件化目录搬家”
- 不建议先做“前端组件继续拆分”来假装解耦
- 不建议继续在 `runtime_*` 上叠更多业务逻辑

原因：

- 当前主问题不是目录不够漂亮
- 而是运行时边界和数据真源还没彻底收口

---

## 这份交接单对应的证据文件

- `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
- `docs/progress.md`
- `docs/session_handoff.md`
- `apps/server/src/runtime_state.py`
- `apps/server/src/api/dashboard.py`
- `apps/server/src/api/tasks.py`
- `apps/server/src/api/baselines.py`
- `apps/server/src/services/source_switch_service.py`
- `apps/web/src/views/HeatListView.vue`
- `apps/web/src/views/HeatDetailView.vue`
- `apps/web/src/components/baseline/BaselineWizard.vue`

---

## 交接说明

本轮只完成了：

- 架构问题盘点
- 前后台边界现状判断
- 后续处理顺序整理

本轮没有完成：

- 任一架构问题的代码修复
- 持久化层迁移
- 前端展示层收缩
- 插件边界重构

因此后续接手时，应将本文件视为：

> “已确认、未处理”的架构债清单，而不是“已经进入实施”的改造结果。
