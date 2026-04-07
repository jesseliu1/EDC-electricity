# Live Incremental / Replay Batch 重构方案

## 1. 目标

本方案用于替换当前“后台每轮回拉最近 72 小时原始点，再整窗切割并自动固化历史炉次”的实现。

新的统一目标：

1. 废除当前 `72h` 整窗历史重算逻辑
2. 让 `live_incremental` 只负责实时运行态和单炉次确认固化
3. 让 `replay_batch` 成为唯一的历史初始化 / 历史重算入口
4. 让 `live_incremental` 和 `replay_batch` 共用同一个炉次增量处理器
5. 让正式表写入语义明确区分：
   - `append`，给实时链使用
   - `replace_range`，给批量链使用
6. 让 UI 只消费 API，不接触后端内部 service

本方案不是在旧 `72h` 逻辑上打补丁，而是替换主链语义。

---

## 2. 为什么必须替换旧逻辑

当前主问题不是某个 SQL 或唯一键的小 bug，而是主链职责错误。

当前实现的问题：

1. 后台 loop 每轮都对最近 `72h` 原始点做整窗切割
2. 历史炉次边界会随着：
   - 活跃阈值变化
   - 切割模式变化
   - 新点进入窗口
   发生漂移
3. 正式表去重当前主要按 `heat.id`
4. 但 `heats.heat_no` 又有唯一约束
5. 一旦历史炉次被重新切出新的 `heat.id`，却仍落在相同的起始分钟，就会触发 `UNIQUE heats.heat_no`

因此当前问题的真正根因是：

- 历史正式炉次不应该继续由实时后台 loop 反复重算

结论：

- `72h` 整窗刷新必须整体废除
- 历史重算必须迁移到显式 `replay_batch`

---

## 3. 核心设计原则

### 3.1 双主链

后端拆成两条主链：

1. `live_incremental`
2. `replay_batch`

### 3.2 一个共同内核

两条主链都不再直接操作“切割 + runtime + DB”细节。

统一使用同一个增量处理器：

- `HeatStreamProcessor`

它负责：

1. 接收一段点流
2. 根据当前切割配置推进炉次状态
3. 产出：
   - `active_heat`
   - `previous_heat`
   - `sealed_heats`
   - `next_processor_state`

### 3.3 写库语义分离

必须明确分成两种持久化语义：

1. `append_sealed_heats`
   - 给 `live_incremental`
   - 只追加已确认闭合的正式炉次
   - 不允许回头重写历史

2. `replace_range`
   - 给 `replay_batch`
   - 对指定范围先删旧正式数据，再整段写入新结果
   - 不做逐条 merge，不依赖旧 `heat.id`

### 3.4 UI 只消费 API

UI 只调用：

- `/api/...`

UI 不直接消费 backend service，不直接碰 runtime store。

---

## 4. 对象与 Service 边界

## 4.1 Processor 对象

建议新增：

- `apps/server/src/services/heat_stream_processor.py`

核心对象：

- `HeatStreamProcessor`

职责：

1. 持有处理状态
2. 按顺序消费点流
3. 根据切割策略推进炉次边界
4. 输出标准化的 runtime 候选炉次

建议方法：

1. `feed_points(points_chunk)`
2. `finalize_until(anchor_time)`
3. `flush_pending(final=False)`
4. `snapshot_state()`
5. `restore_state(snapshot)`

这个对象是真正有状态的业务核心，因此应做成对象，不应继续散落成一组无状态函数。

## 4.2 Processor State 对象

建议新增：

- `HeatProcessorState`

内部至少包含：

1. `channel_key`
2. `cutting_config_snapshot`
3. `last_point_timestamp`
4. `open_heat`
5. `previous_heat`
6. `pending_seal_queue`
7. `last_emitted_heat_id`
8. `request_anchor_time`
9. `processing_mode`

说明：

- `state` 是处理器内部真状态
- `runtime snapshot` 是对 UI / API 暴露的业务视图
- 两者不要混成同一个 JSON 结构

## 4.3 Live Runtime Service

建议新增：

- `apps/server/src/services/live_heat_runtime_service.py`

职责：

1. 从 watermark 之后拉取增量原始点
2. 把点喂给 `HeatStreamProcessor`
3. 更新当前 runtime snapshot
4. 把已确认 `sealed_heats` 通过 `append_sealed_heats` 写入正式表
5. 保存 processor state 与 runtime snapshot

边界：

- 不再扫描 72 小时整窗
- 不再负责历史回放
- 不再尝试修复旧历史正式炉次

## 4.4 Replay Batch Service

建议新增：

- `apps/server/src/services/heat_replay_batch_service.py`

职责：

1. 接收：
   - `anchor_time`
   - `end_time`
   - `channel`
   - `cutting_config_snapshot`
   - `trigger_source`
2. 按 chunk 拉取历史点
3. 复用同一个 `HeatStreamProcessor` 增量推进
4. 产出指定范围内新的正式炉次结果
5. 最终通过 `replace_range` 替换该范围旧正式数据

边界：

- 它是显式历史重算入口
- 不在后台 loop 中自动运行

## 4.5 Persistence Service

建议拆分现有正式炉次写入 service，形成：

- `apps/server/src/services/formal_heat_persistence_service.py`

至少暴露两个入口：

1. `append_sealed_heats(...)`
2. `replace_heat_range(...)`

说明：

- 这两个入口不能混在同一个“智能 upsert”里
- `live` 和 `replay` 的业务语义不同，必须明确区分

## 4.6 Runtime Store Service

建议新增：

- `apps/server/src/services/heat_runtime_store_service.py`

职责：

1. 保存 / 恢复 processor state
2. 保存 / 恢复 current runtime snapshot
3. 保存 refresh meta / replay meta

说明：

- 不再让各业务流程直接散写 `settings.runtime_*`
- runtime 持久化统一走 store service

---

## 5. 统一的数据处理内核

## 5.1 统一输入

无论是 live 还是 replay，进入核心处理器前都统一成：

1. `points_chunk`
2. `processor_state`
3. `cutting_config_snapshot`
4. `processing_mode`

## 5.2 统一输出

处理器统一输出：

1. `active_heat`
2. `previous_heat`
3. `sealed_heats`
4. `next_processor_state`

说明：

- `sealed_heats` 先产出为 runtime candidate
- 后续统一进入：
  - `CurrentHeatRuntime`
  - `RuntimePresealPayload`
  - 正式表写入 service

## 5.3 统一编译链

保留并抽稳现有这段能力：

- `candidate -> runtime object -> preseal_payload`

建议复用现有：

- `prepare_runtime_candidates_for_persist(...)`

但要把它从“live 固化链专用 helper”升级为通用编译器：

- `compile_runtime_candidates(...)`

职责：

1. 选适用已发布基线
2. 生成 binding payload
3. 生成 metric_series payload
4. 产出统一 `preseal_payload`

这部分是可复用资产，不需要推倒。

---

## 6. Live Incremental 新语义

## 6.1 处理范围

`live_incremental` 不再使用：

- `now - 72h -> now`

改成：

- `last_watermark -> now`
- 再加必要的边界缓冲

建议边界缓冲仅覆盖：

1. 当前打开炉次可能延续的尾部
2. 前一炉次确认所需的少量上下文

## 6.2 固化规则

`live_incremental` 只允许固化：

1. 已明确闭合的前一炉次
2. 或超过确认超时的待闭合炉次

不允许：

1. 回头重切更老历史
2. 改写已在正式表中的旧正式炉次

## 6.3 runtime 语义

`live_incremental` 持续维护：

1. `active_runtime`
2. `previous_runtime`
3. `refresh_meta`
4. `processor_state`

blank 接回真实 EDC 后：

1. 可以恢复实时连接
2. 可以出现当前 runtime
3. 但不应自动初始化整段历史正式炉次

---

## 7. Replay Batch 新语义

## 7.1 适用场景

`replay_batch` 统一承接：

1. blank 后历史初始化
2. 用户从某时刻开始重算后续炉次
3. 切割配置改变后的显式历史重算
4. 后续计划中的“批量调整后续炉次”

## 7.2 job 输入

建议 job 输入至少包含：

1. `anchor_time`
2. `end_time`
3. `channel_key`
4. `cutting_config_snapshot`
5. `plant_timezone`
6. `trigger_source`
7. `job_kind`

注意：

- job 开始后必须冻结配置快照
- 不允许任务执行中跟随设置页变化漂移

## 7.3 chunk 处理

建议 `replay_batch` 采用分块 loop：

1. `cursor -> chunk_end`
2. 对每个 chunk 拉原始点
3. 喂给同一个 `HeatStreamProcessor`
4. processor 跨 chunk 持续携带 state
5. 每轮只产出边界已确认的 `sealed_heats`

说明：

- 不是每块都从头重算
- 真正的缓冲来自 processor state carry，而不是大范围重复 overlap

## 7.4 尾部 flush

批量任务结束时需要明确 final flush 规则：

1. 若最后一段已明确闭合，可 seal
2. 若最后一段仍是未闭合运行态，应按任务类型决定：
   - 初始化历史时通常不写入未闭合段
   - 从某时刻重算到“当前实时”时，可只更新 runtime，不写正式表

这个规则需要在实现前写死，避免 live 与 replay 口径分叉。

## 7.5 持久化语义

`replay_batch` 不做逐条 merge。

建议流程：

1. 根据 job 计算“受影响正式范围”
2. 在事务内删除该范围旧正式数据：
   - `metric_series`
   - `heat_baseline_bindings`
   - `heats`
3. 插入新的批量结果

这就是：

- `replace_range`

理由：

- 历史重算后 `heat.id / heat_no / 边界` 都可能变化
- 因此 replay 不适合按旧记录逐条对齐修补

---

## 8. API 建议

UI 只走 API。

建议新增或重构以下接口：

## 8.1 runtime 查询

- `GET /api/heats/runtime`

返回：

1. 当前活跃炉次摘要
2. 前一炉次摘要
3. refresh 状态
4. 是否存在待初始化历史

## 8.2 replay job 创建

- `POST /api/heats/replay-jobs`

输入：

1. `anchor_time`
2. `end_time`
3. `job_kind`
4. 可选 `force_replace`

## 8.3 replay job 状态

- `GET /api/heats/replay-jobs/{job_id}`

返回：

1. 当前进度
2. 当前 cursor
3. 已处理 chunk 数
4. 已生成炉次数
5. 错误信息

## 8.4 replay job 取消

- `POST /api/heats/replay-jobs/{job_id}/cancel`

## 8.5 正式炉次读取

保留：

1. `GET /api/heats`
2. `GET /api/heats/{heat_id}`

它们继续只读正式表 + 当前 runtime 组合结果。

---

## 9. 现有逻辑的保留 / 废弃清单

## 9.1 直接保留

1. 切割策略层 `heat_cutting_service.py`
2. runtime 聚合对象 `heat_runtime_types.py`
3. 正式表 payload 编译方向
4. 基线绑定与 metric payload 组装逻辑

## 9.2 必须废弃

1. 后台 loop 每轮回拉最近 `72h` 原始点整窗切割
2. 实时链自动补整段历史正式炉次
3. 用同一条链同时承担：
   - 实时 runtime 刷新
   - 历史初始化
   - 历史重算

## 9.3 必须替换

1. `persist_sealed_heat_candidates(...)`
   - 保留其中可复用 payload 消费能力
   - 但对外语义拆成：
     - `append_sealed_heats`
     - `replace_range`
2. 现有 heat runtime refresh loop
   - 替换成只消费增量点的 live runtime loop

---

## 10. 实施顺序建议

### 步骤 1

抽出 `HeatStreamProcessor` 与 `HeatProcessorState`

目标：

- 先把“增量处理器”从现有 live 代码里抽出来

### 步骤 2

重写 `live_incremental`

目标：

- 去掉 `72h` 整窗
- 只保留实时增量 runtime
- live 只 append 已确认炉次

### 步骤 3

新增 `replay_batch`

目标：

- 建立 chunk loop
- 使用同一个 processor
- 输出批量重算结果

### 步骤 4

新增 `replace_range`

目标：

- 让 replay 有独立持久化语义

### 步骤 5

暴露 replay job API

目标：

- 给 UI 一个明确入口
- blank 初始化 / 批量重算都从这里走

### 步骤 6

删除旧 `72h` 主链

目标：

- 不再让旧后台 loop 参与正式历史生成

---

## 11. 测试要求

这次改造必须补以下回归：

1. `live_incremental` 不会回头改写已存在历史炉次
2. `replay_batch` 与 `live_incremental` 在相同配置下切割结果一致
3. `replace_range` 后不会出现：
   - `heat_no` 唯一键冲突
   - 悬挂 `metric_series`
   - 悬挂 `heat_baseline_bindings`
4. blank 接回真实 EDC 后：
   - 只恢复 runtime
   - 不自动生成历史正式炉次
5. 批量初始化历史后：
   - 炉次列表出现正式炉次
   - 详情和曲线来源统一

---

## 12. 最终结论

本轮应明确放弃旧语义：

- 后台实时 loop 不再承担历史初始化和历史重算

新的统一语义应为：

1. `live_incremental`
   - 只维护实时运行态
   - 只追加确认闭合的炉次

2. `replay_batch`
   - 负责历史初始化 / 历史重算
   - 通过显式 job 执行
   - 通过 `replace_range` 更新正式表

3. `HeatStreamProcessor`
   - 成为两条主链共同的状态机内核

这才符合后续工业化方向：

- 低耦合
- 高内聚
- live / replay 结果口径统一
- blank / 初始化 / 正式历史边界清楚
