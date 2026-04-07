# Runtime 改造实施计划

## 1. 本轮目标

本轮只做 runtime 与正式落库主链改造，不做批量回放入口。

本轮要完成的目标：

1. 把当前炉次 runtime 收敛成明确的聚合对象结构
2. 为后续 `live_incremental / replay_batch` 共用处理链预留 `processing_meta`
3. 修掉正式炉次固化链中的 SQLite 自锁问题
4. 让正式炉次支持“用户手动修改后保存”
5. 在正式表中增加 `heats.is_manually_adjusted`
6. 明确正式炉次允许合法 overlap，且不再用 overlap 当去重依据

本轮不做：

1. 不做“批量调整后续炉次”按钮
2. 不做系统初始化几天数据的批量回放
3. 不做新的批处理队列/任务系统
4. 不做前端页面交互扩展，只保证现有保存入口契约正确

---

## 2. 设计前提

### 2.1 炉次正式数据语义

- `heats.start_time / end_time` 是该炉次自己的主业务区间
- `heats.context_start_time / context_end_time` 是该炉次自己的上下文窗口
- `metric_series(owner_type='heat')` 存的是该炉次自己的 `N-1 / N / N+1` 曲线包
- 不同炉次之间允许时间窗口 overlap
- overlap 不等于重复

### 2.2 手动修改语义

- 用户保存炉次时间调整时，只改当前炉次
- 不联动改前后炉次
- 修改后的当前炉次允许与相邻炉次 overlap
- 保存成功后 `heats.is_manually_adjusted = 1`

### 2.3 去重语义

- 不再用“时间重叠”作为正式炉次重复判定
- 正式固化链必须改为“明确身份去重”
- 本轮建议的 identity 规则：
  - live 固化路径以 `candidate.id -> heat.id` 作为唯一身份
  - 若相同 `heat.id` 已存在，则视为同一条炉次
  - 若 `heat.id` 不同，即使时间窗口 overlap，也视为不同炉次

### 2.4 任务快照语义

- `tasks` 继续视为创建时快照
- 若后续手动调整炉次时间，不自动回写历史任务快照
- 本轮只保证后续新读取的 `heat / compare` 口径正确，不追溯重写既有任务

### 2.5 正式表写入边界

- 正式表更新必须统一走业务 service 入口
- `api` 层只负责参数校验、调用 service、返回响应
- 其他业务模块不得绕过 service 直接写 `Heat / HeatBaselineBinding / MetricSeries`
- 后续凡新增正式表更新动作，都应先补对应 service 方法，再接 API 或调度入口

---

## 3. 本轮实施范围

### 3.1 模型与契约

涉及文件：

- `apps/server/src/models/heat.py`
- `apps/server/src/schemas/heat.py`
- `apps/server/src/services/formal_heat_service.py`
- `apps/server/src/api/heats.py`
- `apps/server/tests/test_formal_heat_api.py`
- `apps/server/tests/test_heats_api.py`

改动内容：

1. `Heat` 模型增加 `is_manually_adjusted: bool`
2. `HeatResponse` 增加 `is_manually_adjusted`
3. 正式炉次读取链返回该字段
4. 正式炉次保存修改时写入该字段

备注：

- 因为当前部署语义已是 `factory-reset + blank = 删库重建 schema`，本轮不做旧库迁移兼容

### 3.2 runtime 聚合对象

建议新增文件：

- `apps/server/src/services/heat_runtime_types.py`
- `apps/server/src/services/heat_runtime_pipeline.py`

目标：

- 不再让 `apps/server/src/api/heats.py` 继续堆运行态结构组装细节
- 用一个明确的 runtime 聚合对象承载当前炉次状态

建议结构：

- `CurrentHeatRuntime`
  - `facts`
  - `bindings`
  - `metric_series`
  - `preseal_payload`
  - `processing_meta`
  - `refresh_meta`

说明：

- 运行时内存对象可用 dataclass 或内部类型对象表达
- 写入 `runtime_*` 时统一转成 dict/JSON
- 不要求把对象直接持久化成 Python 对象

### 3.3 正式固化链重构

涉及文件：

- `apps/server/src/api/heats.py`
- `apps/server/src/services/formal_heat_service.py`

改动目标：

1. 当前 runtime 刷新链先组装 `preseal_payload`
2. `persist_sealed_heat_candidates()` 改为消费预组装 payload，而不是在事务里临时补大段业务逻辑
3. 持久化链内部不再开嵌套 session

必须处理的具体问题：

1. 去掉基于时间重叠的 existing heat 判定
2. 改成基于 `heat.id` 的 identity 查重
3. `_list_applicable_published_baselines()` 不能再在持久化事务里开新 session
4. `get_formal_heat_record(existing.id)` 不能再在持久化事务里开新 session

建议做法：

- 把“查适用基线、选主基线、挑模板、生成 binding payload、生成 metric_series payload”前移到 runtime/preseal 阶段
- `persist_sealed_heat_candidates()` 只负责：
  - identity 查重
  - 事务写 `heats`
  - 事务写 `heat_baseline_bindings`
  - 事务写 `metric_series`
  - commit
- 增加 sealed candidate identity 稳定性回归测试，防止 live refresh 在 seal 边界重复产出不同 id

### 3.4 手动保存修改链

涉及文件：

- `apps/server/src/api/heats.py`
- `apps/server/src/services/formal_heat_service.py`

当前入口：

- `PATCH /api/heats/{heat_id}` [heats.py](/home/openclaw/projects/EDC-electricity/apps/server/src/api/heats.py#L2858)

本轮需要补齐的行为：

1. 正式炉次修改 `start_time / end_time` 成功后：
  - 写回 `Heat.start_time / end_time`
  - 写回 `Heat.is_manually_adjusted = True`
  - 保持 `context_start_time / context_end_time` 不变
2. 同步更新该炉次 `metric_series.series_json` 里的：
  - `heat_start_time`
  - `heat_end_time`
3. compare/cache 失效
4. 不联动修改相邻炉次

保留约束：

- 调整后的 `start_time / end_time` 仍必须落在当前炉次 `context_start_time / context_end_time` 内

### 3.5 `heat_no` 处理策略

这是本轮必须先定下的实现口径。

建议：

- 本轮先让 `heat_no` 保持不变，视为炉次业务编号，不因人工微调时间自动重算

原因：

1. 当前模型里 `heat_no` 有唯一约束 [heat.py](/home/openclaw/projects/EDC-electricity/apps/server/src/models/heat.py#L29)
2. 人工调整时间后如果立即重算 `heat_no`，会引入编号冲突和历史链路变更
3. UI 真实时间仍以 `start_time / end_time` 展示，不依赖 `heat_no` 推导

---

## 4. 分步执行计划

### 步骤 1：加正式字段与 API 契约

改动：

- `Heat.is_manually_adjusted`
- `HeatResponse.is_manually_adjusted`
- 正式炉次读链透传

验证：

- 模型测试
- `GET /api/heats`
- `GET /api/heats/{id}`

### 步骤 2：抽 runtime 类型与组装器

改动：

- 新增 runtime 聚合对象类型
- 新增 runtime -> preseal payload 组装器
- 先接入 live 刷新链，不改批量入口

验证：

- 现有 live runtime 刷新相关测试
- runtime state 持久化/恢复不崩

### 步骤 3：重构正式固化链

改动：

- `persist_sealed_heat_candidates()` 改成薄事务
- 去掉 overlap 去重
- 去掉 nested session

验证：

- 原有正式炉次 API 测试
- 增加 SQLite lock 回归测试
- 增加 overlap 合法存在的回归测试

### 步骤 4：补正式炉次手动保存链

改动：

- `update_formal_heat_record()` 增加：
  - `is_manually_adjusted=True`
  - `metric_series.series_json.heat_start_time / heat_end_time` 同步更新
- `PATCH /api/heats/{id}` 返回更新后的正式数据

验证：

- 手动保存后：
  - `is_manually_adjusted = true`
  - `start_time / end_time` 更新
  - `metric_series.series_json` 内 heat 时间同步更新
  - compare 缓存失效

### 步骤 5：完整回归

后端：

- `pytest -q tests/test_formal_heat_api.py tests/test_heats_api.py tests/test_runtime_state_admin.py`
- 视改动范围补 `tests/test_tasks_reports_settings_api.py`

前端最小回归：

- 炉次详情保存时间调整
- 保存后详情刷新
- compare 仍可打开

---

## 5. 必补测试

### 5.1 正式炉次 overlap 合法

新增断言：

- 两条正式炉次 `start_time / end_time` 可 overlap
- 系统不把后一条当成前一条重复

### 5.2 手动保存标记

新增断言：

- `PATCH /api/heats/{id}` 修改起止时间后，`is_manually_adjusted = true`

### 5.3 `metric_series` 时间同步

新增断言：

- 手动保存后，`series_json.heat_start_time / heat_end_time` 同步更新

### 5.4 SQLite lock 回归

新增断言：

- runtime seal 正式炉次时，不再因为内部嵌套 session 触发 `database is locked`

### 5.5 runtime 处理链扩展位

新增断言：

- 当前 runtime 聚合对象包含 `processing_meta`
- `processing_mode='live_incremental'` 是当前默认路径

---

## 6. 工程审查重点

本计划实施前要特别注意这几件事：

1. **重复判定不能再依赖 overlap**
   - 当前实现仍在 `persist_sealed_heat_candidates()` 里用时间重叠查 existing heat [formal_heat_service.py](/home/openclaw/projects/EDC-electricity/apps/server/src/services/formal_heat_service.py#L635)
   - 这和“正式炉次允许 overlap”直接冲突

2. **手动保存不能只改 `heats`**
   - `metric_series.series_json` 已经存了 `heat_start_time / heat_end_time`
   - 如果不一起改，详情页和对比页会出现主记录时间与曲线元信息不一致

3. **`heat_no` 不能临时边实现边决定**
   - 要么冻结不变
   - 要么设计完整重编号规则
   - 本轮建议冻结

4. **runtime 对象和 `runtime_*` 持久化要分层**
   - 内存里可以是对象
   - SQLite `settings.runtime_*` 里仍建议落序列化 payload

5. **批量回放不要混进本轮**
   - 本轮只保留 `processing_meta`
   - 不能一边重构 runtime，一边把异步批处理入口也塞进来

6. **`heat.id` 稳定性要被测试证明**
   - 如果 live seal 边界会给同一条炉次算出不同 id，那么去掉 overlap 去重后会真实产生重复炉次
   - 所以不能只“相信不会重复”，必须补回归测试

---

## 7. 预期交付物

本轮结束后应得到：

1. 一个明确的当前炉次 runtime 聚合对象
2. 一个薄化后的正式炉次固化事务
3. 一个支持人工保存并标记 `is_manually_adjusted` 的正式炉次更新链
4. 一套允许正式炉次 overlap 的正式表读写口径
5. 为未来批量回放保留好的 `processing_meta`
