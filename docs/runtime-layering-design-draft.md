# Runtime 分层设计草案

## 1. 背景

当前系统里有三件事还没有完全分开：

- `EDC` 实时采集
- 后端当前炉次的业务运行态
- 前端页面显示与交互草稿态

现状的问题不是“没有 runtime”，而是 runtime 的职责还不够清晰：

- 一部分 runtime 在承担真实业务状态
- 一部分 runtime 更像接口视图缓存
- 炉次固化时，后端仍会在持久化阶段补做一轮业务组装
- 前端列表 / 详情 / compare 的部分计算，仍会在请求阶段现场重算

这会带来几个直接问题：

- 运行态和正式表结构不够同构
- 落库链路偏重，SQLite 更容易在高频刷新下出锁冲突
- 页面实时显示和正式历史读取的口径还没有完全统一
- 后续继续加切割策略、对比策略、分析字段时，耦合会继续升高

---

## 2. 设计目标

本草案的目标不是新增更多缓存，而是把 runtime 拆成职责清楚的三层。

### 2.1 目标

1. 明确 `EDC` 实时采集、后端业务运行态、前端本地显示态三层边界
2. 让“当前炉次”运行态尽量与正式表结构同构
3. 让炉次固化从“持久化时临时补算”收敛为“运行态先准备好，落库时只做校验和提交”
4. 让前端页面显示更稳定，不直接受 `EDC` 抖动和后端长链计算影响
5. 为后续增加新的切割模式、分析策略、实时告警字段保留低耦合入口

### 2.2 非目标

1. 不把前端本地状态升级为业务真源
2. 不让 UI 直接改采集层数据
3. 不让“专门为了显示的 runtime”反向覆盖后端业务 runtime
4. 不追求用 UI runtime 提升 `EDC` 取数速度

---

## 3. 总体分层

建议拆成三层 runtime：

1. `collection runtime（采集运行态）`
2. `business runtime（业务运行态）`
3. `ui runtime（前端显示/交互态）`

核心原则：

- 真正的权威运行态在后端
- 前端只能消费后端运行态，或提交“意图型修改”
- 固化前的待入库 payload 应在后端业务 runtime 内提前准备

---

## 4. 第一层：采集运行态

### 4.1 职责

只负责承接 `EDC` 原始实时数据，不承担业务解释。

### 4.2 真源

- 外部真源：`EDC`

### 4.3 典型内容

- 当前 source 配置
- 通道目录与角色绑定解析结果
- 原始点窗口缓存
- 最近同步时间
- 最近成功/失败状态
- 通道级 watermark
- 采集错误信息

### 4.4 规则

- 只允许后端采集链更新
- UI 不得直接修改
- 换源时整层按 source-bound 语义失效
- 这一层的数据结构可以偏向采集效率，不必强行贴近正式表

### 4.5 作用

- 隔离 `EDC` 访问抖动
- 避免每个页面请求都直接打 `EDC`
- 为业务运行态提供稳定输入

---

## 5. 第二层：业务运行态

### 5.1 职责

这是系统真正的“当前炉次业务真源”。

它基于采集运行态、系统设置、黄金基线主数据，持续产出：

- 当前活跃炉次
- 前一个炉次
- 待固化炉次
- 当前适用的基线集合
- 当前主黄金基线
- 偏离度、连续不一致时间等业务分析结果
- 与正式表近似同构的待入库 payload

### 5.2 真源

- 输入真源：`collection runtime + baselines/baseline_definitions/settings`
- 运行真源：后端 `business runtime`

### 5.3 建议结构

建议后端业务 runtime 以“当前炉次聚合对象”的方式承载，内部包含几类子结构，而不是继续散落成多份平行 dict。

示意：

```text
CurrentHeatRuntime
  ├─ facts
  ├─ bindings[]
  ├─ metric_series[]
  ├─ preseal_payload
  └─ refresh_meta
```

其中对象内部至少要覆盖这几块业务内容：

#### `runtime_heat_facts（当前炉次事实）`

- `heat_id（炉次ID）`
- `heat_no（炉次编号）`
- `furnace_id（设备ID）`
- `start_time（开始时间）`
- `end_time（当前结束时间）`
- `context_start_time（上下文开始时间）`
- `context_end_time（上下文结束时间）`
- `is_manually_adjusted（是否已被用户手动修改）`
- `status（状态）`
- `cut_reason（切割原因）`
- `cut_status（切割状态）`
- `record_source（来源）`

#### `runtime_heat_bindings（当前炉次绑定关系）`

- `heat_id（炉次ID）`
- `baseline_definition_id（基线定义ID）`
- `baseline_item（基线版本号）`
- `is_primary（是否主黄金基线）`
- `effective_from_snapshot（生效时间快照）`
- `tolerance_percent_snapshot（容差快照）`
- `analysis_status（分析状态）`
- `deviation_percent（最大偏离度）`
- `avg_deviation_percent（平均偏离度）`
- `time_offset_percent（时间偏移比例）`
- `mismatch_duration_minutes（连续不一致分钟数）`

#### `runtime_metric_series（当前炉次指标序列）`

- `owner_type='heat'`
- `owner_key=heat_id（炉次ID）`
- `metric_key（指标键）`
- `series_json（序列）`
- `stat_json（统计）`

#### `runtime_preseal_payload（待固化 payload）`

这是最关键的一层。

建议业务 runtime 在炉次接近固化时，就提前准备出一份接近正式落库形态的 payload：

- `heat_payload`
- `binding_payloads[]`
- `metric_series_payloads[]`

也就是：

- `heats（炉次表）` 要写什么
- `heat_baseline_bindings（炉次-黄金基线绑定表）` 要写什么
- `metric_series（指标序列表）` 要写什么

都先在 runtime 里准备好。

#### `runtime_processing_meta（处理上下文）`

这部分不是正式业务数据，但本轮 runtime 设计要预留位置。

目的：

- 让同一套“炉次识别 -> 组装 runtime -> 生成 preseal payload -> 写正式表”的后端处理链，后续既能服务当前实时刷新，也能服务批量回放/补算

建议至少预留：

- `processing_mode（处理模式）`
  - `live_incremental`
  - `replay_batch`
- `trigger_source（触发来源）`
  - `background_refresh`
  - `manual_heat_adjust`
  - `bootstrap_backfill`
- `request_anchor_time（请求起点时间）`
- `batch_cursor（批处理游标，可为空）`
- `last_processed_heat_id（最近处理炉次，可为空）`

注意：

- 这部分本轮只预留 runtime 定义与处理链位置
- 不代表本轮就实现批量回放入口
- 也不建议把它写进正式表主业务模型

### 5.4 规则

- 用户可影响的是“业务解释参数”，不是采集原始值
- 实时分析结果应在这一层持续计算，而不是主要依赖接口现场拼
- 这层应尽量与正式表同构，但允许保留少量 runtime 专用字段
- 所有“即将写库”的业务值，应优先在这一层定型
- 当前炉次事实窗口默认仍来自自动切割；若用户手动保存修改，则该炉次自身标记 `is_manually_adjusted=1`
- 手动保存后允许当前炉次与相邻炉次在 `start_time / end_time` 上出现 overlap，它们仍是彼此独立的业务数据包
- 后端处理链必须从一开始就按“同一套核心逻辑可复用到 live 和 replay”设计，不能把实时刷新逻辑写死在只适用于单次增量推断的分支里

### 5.5 运行意义

这层是后续页面显示、告警判定、炉次固化、历史对齐的共同中心。

如果这层收干净，前台与正式表的口径就更容易统一。

---

## 6. 第三层：前端显示/交互态

### 6.1 职责

只负责页面显示和交互，不承担业务真源职责。

### 6.2 典型内容

- 当前选中的对比基线（仅影响显示，不改业务绑定）
- 图表缩放范围
- 当前分页与筛选条件
- 表单草稿
- 弹窗开关
- 尚未保存的用户输入

### 6.3 规则

- UI runtime 可以基于后端 business runtime 派生
- UI runtime 可以做局部缓存、乐观显示、草稿暂存
- UI runtime 不能反向覆盖后端完整 runtime
- UI 修改必须通过 API 提交“意图”或“字段 patch”

### 6.4 推荐交互方式

推荐：

- `手动修正当前炉次开始/结束时间`
- `保存当前炉次人工调整`
- `触发重新分析`

不推荐：

- 前端拿整坨 runtime JSON 回写后端覆盖

---

## 7. 三层之间的数据流

建议的单向数据流如下：

```text
EDC
  ↓
collection runtime（采集运行态）
  ↓
business runtime（业务运行态）
  ↓
runtime view API（后端投影给页面的视图）
  ↓
ui runtime（前端显示/交互态）
```

用户操作的回流应是：

```text
用户操作
  ↓
意图型 API / patch API
  ↓
后端 business runtime 更新
  ↓
重新计算视图
  ↓
前端重新拉取或增量同步
```

不是：

```text
前端整对象覆盖后端 runtime
```

---

## 8. 炉次固化设计

### 8.1 目标语义

炉次真正入正式表之前，业务 runtime 已经拥有接近最终态的 payload。

### 8.2 建议流程

1. 采集运行态持续刷新原始点
2. 业务运行态持续更新当前炉次、候选切割结果、适用基线集合、实时分析结果
3. 当某个炉次从 `active / previous` 转为 `sealed candidate` 时
4. 在业务 runtime 内生成 `runtime_preseal_payload`
5. 持久化层只做：
   - 主键/身份校验
   - 主键/唯一性检查
   - 外键与存在性检查
   - 一个事务内写入 `heats + heat_baseline_bindings + metric_series`
6. 写入成功后，该炉次后续读取统一走正式表

补充约束：

- 以上处理链后续应同时支持：
  - 实时刷新场景：沿当前时间向后滚动
  - 批量回放场景：从某个用户指定时间点开始，异步重算后续炉次并覆盖正式表
- 两类入口应共用同一套 runtime 组装与正式落库逻辑，只允许“取数步长 / 处理批次大小 / 调度方式”不同

### 8.3 这样做的价值

- 持久化更薄
- 事务更短
- SQLite 锁冲突更少
- 运行态和正式态的口径更接近
- 历史详情不再需要“现场猜当时绑定了什么”

---

## 9. 是否需要单独的 UI runtime

需要，但要明确它的作用。

### 9.1 会不会加快显示

会让页面显示更顺、更稳，但不会让 `EDC` 取数本身变快。

它提升的是：

- 页面响应速度
- 局部交互的即时反馈
- 图表和表单的流畅度
- 页面在后端抖动时的稳定性

它不能提升的是：

- `EDC` API 返回速度
- 后端采集链路速度

### 9.2 真正提速的位置

真正能降低页面等待的，是这两点：

1. 后端把重计算前移到 `business runtime`
2. 前端只消费已经成型的 runtime view，而不是每次请求都触发后端临时组装

---

## 10. 变更边界与权限

### 10.1 UI 可改

- 业务配置
- 当前选中的显示对象
- 分析触发动作
- 切割模式与参数
- 表单草稿

### 10.2 UI 不可改

- 原始采集点
- 采集 watermark
- 采集错误计数
- 已同步通道的原始值
- 后端内部待固化 payload

### 10.3 后端应保证

- `collection runtime` 只由采集链更新
- `business runtime` 只由业务规则更新
- `ui runtime` 只是前端消费层，不是业务主数据层

---

## 11. 与当前实现的主要差距

当前实现离目标结构还差几步：

1. 当前 live runtime 仍偏向接口视图 dict，不是显式的 `heat / bindings / metric_series / preseal_payload` 结构
2. 当前 runtime 绑定基线仍以单主基线字段为主，没有把当前炉次的 `1:N` binding 运行态先准备完整
3. 当前偏离度等分析结果，仍有一部分在列表/详情请求阶段现场计算
4. 当前炉次固化时，持久化层仍会再查正式表并组装 `heat_baseline_bindings` 和 `metric_series`
5. 当前持久化函数内部仍存在嵌套 session 查询，SQLite 容易自锁
6. 当前设计尚未正式表达“人工保存后允许合法 overlap”的表语义与标记字段
7. 当前 live 处理链和未来 replay/batch 处理链还没有共享抽象，后续若直接新增批处理分支，容易复制逻辑

---

## 12. 建议的实现顺序

### 阶段 1

先修正持久化链的 SQLite 锁问题。

目标：

- 持久化事务内部不再开嵌套 session
- 先把“能稳定写库”这件事收住

### 阶段 2

把当前炉次运行态收敛为显式结构：

- `runtime_heat_facts`
- `runtime_heat_bindings`
- `runtime_metric_series`
- `runtime_preseal_payload`
- `runtime_processing_meta`

### 阶段 3

把实时分析计算前移到业务 runtime，减少列表/详情现场重算，并把 live / replay 共用的核心处理链抽出来。

### 阶段 4

把前端页面改为尽量只消费 runtime view / formal view 两类明确接口，减少运行态字段直拼。

### 阶段 5

基于前面已抽出的 runtime 处理链，再增加下一轮的批量重算入口：

- 炉次详情页“批量调整后续炉次”
- 系统初始化时按时间范围回放几天数据

本轮不实现这一步，只要求当前 runtime 结构为此留好位置。

---

## 13. 结论

这套设计的核心不是“多做一层缓存”，而是把三层语义彻底拆清：

- `collection runtime（采集运行态）` 负责接数据
- `business runtime（业务运行态）` 负责解释数据、准备待固化 payload
- `ui runtime（前端显示/交互态）` 负责展示和草稿，不碰采集真值

最终目标是：

- 当前炉次实时显示稳定
- 用户交互不直接污染采集层
- 炉次固化时不再临时补大段业务组装
- 历史表与运行态口径越来越统一

这更符合工业化系统设计常理，也更适合后续继续扩展切割、分析、对比和告警能力。
