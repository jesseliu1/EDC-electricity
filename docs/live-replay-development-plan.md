# Live / Replay 开发计划

## 1. 计划目标

本计划是 `docs/live-replay-refactor-plan.md` 的执行版。

目标不是继续修旧 `72h` 主链，而是按最小可验证阶段，完成以下替换：

1. 下线旧 `72h` 整窗历史重算逻辑
2. 落地统一的 `HeatStreamProcessor`
3. 把实时链切到 `live_incremental`
4. 把历史初始化 / 历史重算切到 `replay_batch`
5. 让正式表写入分成：
   - `append`，实时链
   - `replace_range`，批量链

本计划默认：

- 不新增 Redis / Celery / MQ
- 不新增第二个后台进程
- 不先改 UI 主流程
- 先把后端主链收干净，再给 UI 加 replay 入口

---

## 2. 工程审查后的 scope 收缩

原始方案如果一次性全做，会明显超过“单轮安全改造”的复杂度。

审查后的收缩建议：

1. 第一轮不新建独立 `RuntimeStoreService`
   - 先复用 `runtime_state.py`
   - 只把 runtime 持久化封成 helper
   - 避免同时引入过多 service

2. 第一轮不新增 `/api/heats/runtime`
   - 先保持现有 `/api/heats` 契约
   - 只修内部主链
   - 等 replay backend 稳定后再决定是否补 runtime 专用接口

3. 第一轮 replay job 不引入外部队列
   - 采用“单进程 `asyncio.create_task` + SQLite job 状态表”方案
   - 这是当前最 boring、最可控的实现

4. 第一轮 persistence 不拆独立 package
   - 继续落在 `formal_heat_service.py`
   - 但方法语义必须拆开
   - 后续再视复杂度拆文件

结论：

- 先控制新增核心模块数量
- 先把主链切干净
- 不在第一轮同时追求所有结构最理想

---

## 3. 固定决策

这些点在实施前先锁死，不再边做边摇摆。

### 3.1 废弃旧逻辑

以下逻辑本轮必须废弃：

1. 后台 loop 每轮回拉最近 `72h` 原始点整窗切割
2. 实时链自动补整段历史正式炉次
3. 用一条链同时承担：
   - 实时 runtime 刷新
   - 历史初始化
   - 历史重算

### 3.2 统一处理内核

`live_incremental` 和 `replay_batch` 必须共用一个状态机内核：

- `HeatStreamProcessor`

### 3.3 写库语义

正式表写入固定分成两种：

1. `append_sealed_heats`
2. `replace_heat_range`

禁止再做“智能混合 upsert”。

### 3.4 replay 任务调度方式

第一轮采用：

- SQLite `heat_replay_jobs` 表记录任务状态
- 进程内 `asyncio.create_task` 执行实际 batch

不采用：

- FastAPI `BackgroundTasks`
- Celery
- Redis 队列
- 新 worker 进程

原因：

- FastAPI 官方文档对 `BackgroundTasks` 的 caveat 是更适合小任务，同进程小副作用任务；重计算任务更适合别的机制
- 但当前项目又明确不希望先引入外部队列基础设施
- 因此第一轮最合适的是“同进程 task + 可查询 job 状态表”

参考：

- FastAPI Background Tasks: <https://fastapi.tiangolo.com/tutorial/background-tasks/>
- Python `asyncio.create_task()`: <https://docs.python.org/3/library/asyncio-task.html>

---

## 4. 目标架构

```text
                 +-------------------+
                 |   EDC raw points   |
                 +---------+---------+
                           |
                           v
                +----------------------+
                | HeatStreamProcessor   |
                | stateful core         |
                +----+-----------+------+
                     |           |
        active/prev  |           | sealed_heats
                     |           v
                     |   +----------------------+
                     |   | compile preseal      |
                     |   | payloads             |
                     |   +----------+-----------+
                     |              |
                     |              v
                     |   +----------------------+
                     |   | persistence          |
                     |   | append / replace     |
                     |   +----------------------+
                     |
                     v
          +--------------------------+
          | runtime snapshot         |
          | active / previous / meta |
          +--------------------------+
```

两条主链：

```text
live_incremental
  watermark -> new points -> processor -> runtime update -> append sealed heats

replay_batch
  anchor -> chunk loop -> processor -> collect sealed heats -> replace range
```

---

## 5. 模块边界

## 5.1 新增模块

### A. `apps/server/src/services/heat_stream_processor.py`

负责：

1. `HeatProcessorState`
2. `HeatStreamProcessor`
3. 与切割策略层对接

边界：

- 只关心点流转炉次
- 不直接写 DB
- 不直接打 EDC
- 不直接操作 API 响应

### B. `apps/server/src/services/live_heat_runtime_service.py`

负责：

1. 增量拉点
2. 恢复 / 更新 processor state
3. 更新当前 runtime snapshot
4. 追加已确认炉次

### C. `apps/server/src/services/heat_replay_batch_service.py`

负责：

1. replay job 编排
2. 历史 chunk loop
3. 调 processor
4. 最终触发 `replace_heat_range`

### D. `apps/server/src/models/heat_replay_job.py`

负责：

1. replay job 状态持久化
2. UI / API 查询
3. 重启后最少保留历史任务记录

## 5.2 继续复用 / 收敛的模块

### `apps/server/src/services/heat_cutting_service.py`

保留：

- 切割策略注册与执行

要求：

- `HeatStreamProcessor` 只调用它，不再让 API 直接驱动历史切割

### `apps/server/src/services/formal_heat_service.py`

第一轮继续保留在此文件中，但新增并明确分开：

1. `compile_runtime_candidates(...)`
2. `append_sealed_heats(...)`
3. `replace_heat_range(...)`

禁止继续把 replay / live 混在 `persist_sealed_heat_candidates(...)` 里。

### `apps/server/src/runtime_state.py`

第一轮继续保留，但只做：

1. processor state 持久化 helper
2. runtime snapshot 持久化 helper

不在第一轮单独拆新 service 文件。

---

## 6. 分阶段实施

## 阶段 1：抽出统一处理器

### 目标

把“点流 -> 炉次状态推进”从 `api/heats.py` 里抽出来，形成可单测的状态机内核。

### 改动范围

1. 新增 `heat_stream_processor.py`
2. 抽出现有 live 切割推进逻辑
3. 保留现有 API 契约不变
4. 暂不切 live 主链，不上 replay

### 验证

必须新增 processor 级单测：

1. 连续点流能稳定生成：
   - `active_heat`
   - `previous_heat`
   - `sealed_heats`
2. 分块输入与整段输入结果一致
3. `signal_inference` / `fixed_interval` 在相同 fixture 下结果稳定
4. final flush 规则明确

### 完成判定

可以在不依赖 API 和 DB 的情况下，单独证明 processor 对同一组点流结果稳定。

---

## 阶段 2：切实时链到 `live_incremental`

### 目标

替换旧后台 `72h` refresh loop，使其只处理 watermark 之后的增量点。

### 改动范围

1. 新增 `live_heat_runtime_service.py`
2. 重写 `refresh_heat_runtime_state(...)` 内部实现
3. 删除旧 `72h` lookback 逻辑
4. 实时链改为：
   - 读取 processor state
   - 拉增量点
   - 喂 processor
   - 更新 runtime
   - append 已确认炉次

### 验证

1. blank 接回真实 EDC 后：
   - 恢复 runtime
   - 不自动补历史正式炉次
2. 当前炉次 / 前一炉次仍能在列表正确显示
3. 已确认闭合的最新炉次能成功 append
4. 不再出现旧历史被重切后写库

### 完成判定

线上即使持续运行，也不会再因为后台 loop 回扫历史而触发 `heat_no` 唯一键冲突。

---

## 阶段 3：补 replay backend

### 目标

引入显式历史初始化 / 重算能力，替代旧自动历史补算。

### 改动范围

1. 新增 `heat_replay_job.py`
2. 新增 `heat_replay_batch_service.py`
3. 新增 replay job API
4. 新增 `replace_heat_range(...)`

### replay job 最小字段

1. `id`
2. `job_kind`
3. `status`
4. `anchor_time`
5. `end_time`
6. `channel_key`
7. `cutting_config_snapshot_json`
8. `progress_cursor`
9. `processed_chunk_count`
10. `generated_heat_count`
11. `error_message`
12. `created_at / started_at / completed_at / updated_at`

### 验证

1. blank 初始化历史可显式启动
2. replay job 可查询状态
3. replay 结果不会与旧正式记录逐条 merge
4. replace range 后：
   - `heats`
   - `heat_baseline_bindings`
   - `metric_series`
   三者保持一致

### 完成判定

历史初始化和历史重算已经不再依赖后台实时 loop。

---

## 阶段 4：前端接入 replay

### 目标

让 UI 可以显式发起历史初始化 / 历史重算，并看到进度。

### 改动范围

第一轮只做最小入口，不做复杂调度 UI。

建议最小入口：

1. 设置页增加“初始化历史”入口
2. 炉次详情页增加“从此处重算后续炉次”入口
3. 增加 job 状态轮询显示

### 验证

1. 用户可明确知道系统当前是：
   - blank 未初始化
   - replay 运行中
   - replay 完成
   - replay 失败
2. 不再把“后台自动补历史”当默认行为

---

## 7. API 计划

## 7.1 第一轮保持不变

先不改：

1. `GET /api/heats`
2. `GET /api/heats/{heat_id}`

这样先降低前端改动面。

## 7.2 新增 replay API

### `POST /api/heats/replay-jobs`

创建任务。

参数：

1. `job_kind`
2. `anchor_time`
3. `end_time`
4. `force_replace`

### `GET /api/heats/replay-jobs/{job_id}`

返回：

1. `status`
2. `progress_cursor`
3. `processed_chunk_count`
4. `generated_heat_count`
5. `error_message`

### `POST /api/heats/replay-jobs/{job_id}/cancel`

取消任务。

---

## 8. 关键实现细则

## 8.1 replay 用什么 loop

`replay_batch` 不是重复调用旧 live refresh。

它应该：

1. 使用同一个 `HeatStreamProcessor`
2. 按 chunk 喂历史点流
3. 跨 chunk 携带 state
4. 只在最终落库阶段做 `replace_range`

也就是：

- 复用的是“增量处理器内核”
- 不是复用旧 `72h` loop 壳子

## 8.2 为什么不用 FastAPI `BackgroundTasks`

官方文档更倾向把它用于较小的同进程后台任务。  
本项目的 replay 是重计算任务，而且需要：

1. 查询状态
2. 支持取消
3. 明确 job 生命周期

因此第一轮采用：

- `asyncio.create_task`
- SQLite job 表

这比 `BackgroundTasks` 更贴近需求，同时又比 Celery 简单很多。

## 8.3 range replace 规则

`replace_heat_range(...)` 必须做到：

1. 先删从属表：
   - `metric_series`
   - `heat_baseline_bindings`
2. 再删主表：
   - `heats`
3. 再插入新结果

并且只删“受影响正式范围”。

### 受影响范围第一轮规则

第一轮建议简单明确：

1. replay 从 `anchor_time` 开始
2. 找到首条 `end_time >= anchor_time` 的正式炉次
3. 从这条炉次开始到 `end_time` 全量替换

先不用做更复杂的“局部热边界保护”。

## 8.4 并发规则

必须限制同一 `channel_key` 同时只有一个 replay job。

并且 replay 执行期间：

1. live runtime 仍可继续刷新当前 runtime
2. 但 live append 正式炉次必须避免写入 replay 正在替换的范围

第一轮建议最简单规则：

- replay 运行期间，暂停同 `channel_key` 的 live formal append
- 只保留 live runtime 更新

这样最稳。

---

## 9. 文件变更清单

## 9.1 后端核心

预计涉及：

1. `apps/server/src/api/heats.py`
2. `apps/server/src/api/router.py`
3. `apps/server/src/models/heat.py`
4. `apps/server/src/models/__init__.py`
5. `apps/server/src/services/formal_heat_service.py`
6. `apps/server/src/runtime_state.py`
7. `apps/server/src/services/heat_cutting_service.py`
8. `apps/server/src/main.py`

## 9.2 新增文件

建议新增：

1. `apps/server/src/services/heat_stream_processor.py`
2. `apps/server/src/services/live_heat_runtime_service.py`
3. `apps/server/src/services/heat_replay_batch_service.py`
4. `apps/server/src/models/heat_replay_job.py`
5. `apps/server/src/schemas/heat_replay.py`

## 9.3 测试

至少新增：

1. `apps/server/tests/test_heat_stream_processor.py`
2. `apps/server/tests/test_live_heat_runtime_service.py`
3. `apps/server/tests/test_heat_replay_batch_service.py`
4. `apps/server/tests/test_heat_replay_api.py`

---

## 10. 测试计划

## 10.1 Processor 级

1. chunk 输入与整窗输入结果一致
2. seal delay 规则一致
3. flush 规则一致
4. fixed / signal 两种模式 fixture 回归

## 10.2 Live 级

1. blank 接回真实 EDC 不自动补历史
2. 只 append 最新确认炉次
3. 旧历史不再被回切
4. 不再触发 `heat_no` 唯一键冲突

## 10.3 Replay 级

1. replay job 可启动 / 查询 / 取消
2. replace range 后三张正式表一致
3. replay 后正式炉次列表与详情一致
4. replay 与 live 在相同配置下结果一致

## 10.4 UAT 路径

正式 UAT 需覆盖：

1. blank 环境接回真实 EDC 后仍为空历史
2. 用户显式初始化历史
3. 初始化完成后列表可见正式炉次
4. 从炉次详情触发“从此处重算后续炉次”
5. replay 中 loading / success / error / cancel 状态

---

## 11. 风险与回滚

## 11.1 最大风险

1. live / replay 结果不一致
2. replace range 误删范围过大
3. replay 与 live 并发写库冲突
4. processor state 与 runtime snapshot 不一致

## 11.2 回滚策略

实施阶段按 milestone 切，不做一把梭大切换。

回滚顺序：

1. replay API 可先不上 UI
2. live cutover 先在测试环境验证
3. 每阶段完成后再部署 blank 环境验证

如果某阶段失败：

1. 保留 plan 文档与测试
2. 回退该阶段代码
3. 不把 replay 半成品暴露到 UI

---

## 12. 工程审查结论

**状态**：建议按计划推进，但必须分阶段，不允许一次性大改直接上线。

本次 `plan-eng-review` 口径下的主要结论：

1. 方向是对的
   - `72h` 主链确实应该整体废弃
   - 共用一个增量处理器是正确方向

2. 第一轮不能同时追求所有结构理想化
   - 必须先收 scope
   - 否则很容易变成“重写一半、验证不足”

3. 最安全的执行方式是四阶段：
   - 先抽 processor
   - 再切 live
   - 再补 replay backend
   - 最后再接 UI

4. 这轮不建议引入新基础设施
   - 不上 Redis
   - 不上 Celery
   - 不上第二 worker

5. 这轮必须把测试当主交付物之一
   - 否则 live / replay 很容易分叉
