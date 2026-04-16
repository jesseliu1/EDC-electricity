# Runtime `current -> previous -> db` 改造计划

## 1. 目标

本轮 runtime 改造的目标只有一个：

- 把 live / replay 的运行态主链收敛成 `source -> active_runtime(current) -> previous_runtime -> db`

并明确以下业务语义：

- `active_runtime`
  - 表示当前正在发生的炉次
  - 偏离分析只认当前炉次自己的 `start_time ~ end_time`
  - 冷启动首次识别时允许只有当前炉次 `N`，不强求已有 `N-1`
- `previous_runtime`
  - 表示上一条炉次
  - 继承它在 `active_runtime` 阶段已经算好的偏离分析结果
  - 后续只继续补 `N+1` 显示上下文，不重新计算偏离分析
  - 是正式入库的唯一直接上游
- `metric_series(owner_type='heat')`
  - 正式保存该炉次自己的 `N-1 / N / N+1` 上下文曲线包
- `heat_baseline_bindings`
  - 继续作为 `heat + baseline` 粒度分析结果真相源

## 2. 不做的事

- 不修改 DB 结构
- 不重新设计 processor 切割算法
- 不让 `N-1 / N+1` 参与偏离度重算
- 不为 sealed/history 再单独开一条取数与分析主链

## 3. 当前问题

当前实现的主要偏差有 4 个：

1. `sealed_segments` 同时承担“可封口信号”和“正式入库数据源”两种职责
2. `previous_runtime` 不是正式 history 的唯一上游
3. `previous_runtime` 补上下文时仍可能触发一次新的偏离分析
4. `runtime_metric_series` 默认只围绕候选炉次本体窗口，不会自然形成 `N-1 / N / N+1`

## 4. 目标数据流

### 4.1 live 刷新

1. 从 EDC 拉本轮源数据增量
2. processor 只负责产出：
   - `active_segment`
   - `previous_segment`
   - `sealed_signals`
3. `active_runtime`
   - 吃当前炉次自己的增量
   - 正常续跑时尽量覆盖 `N-1 / N`
4. `previous_runtime`
   - 从上一轮 `active_runtime` 升格而来
   - 继承已有 `baseline_bindings`
   - 继续吸收来自当前 `active_runtime` 的 `N+1`
5. 当 `previous_runtime` 达到封口条件时
   - 从 `previous_runtime` 生成 preseal payload
   - 落 `heats / metric_series / heat_baseline_bindings`

### 4.2 replay

1. replay 最终仍由 processor 判定 `previous_segment / active_segment`
2. replay 重建的 runtime aggregate 也遵守：
   - `active_runtime`
   - `previous_runtime`
   - `processor_snapshot`
3. replay 后续 live 续接继续沿同一条 `current -> previous -> db` 链路运行

## 5. 生命周期规则

### 5.1 冷启动 / 首次识别

- 允许 `previous_runtime == null`
- 允许 `active_runtime.context_start_time == active_runtime.start_time`
- 这属于正常状态，不视为刷新失败

### 5.2 `active -> previous`

- 当新一条 `active_runtime` 出生时，旧 `active_runtime` 升格为 `previous_runtime`
- 升格时直接继承：
  - `baseline_bindings`
  - `deviation_score`
  - `avg_deviation_score`
  - `abnormal_duration_minutes`
- 升格后不重新计算偏离分析

### 5.3 `previous -> db`

- `previous_runtime` 只要满足封口条件，就由它自己生成正式 payload
- 不再直接用 raw `sealed_candidate` 重新编译另一份正式 heat

### 5.4 最后一炉

- 如果迟迟拿不到完整 `N+1`
- 允许 `previous_runtime` 只带部分 `N+1`
- 达到超时/封口条件后仍可入库

## 6. 运行态对象边界

### 6.1 `active_runtime`

- 保留：
  - `facts`
  - `birth_context`
  - `bindings`
  - `metric_series`
  - `baseline_views`
  - `baseline_curve_snapshots`
  - `definition_metric_snapshots`
  - `preseal_payload`
- 语义：
  - 当前炉次分析真源
  - 当前炉次曲线真源

### 6.2 `previous_runtime`

- 结构与 `active_runtime` 相同
- 语义：
  - 上一炉次的正式入库前真源
  - 保留已冻结的偏离分析结果
  - 曲线继续吸收 `N+1`

### 6.3 `processor_snapshot`

- 只保存切割辅助状态
- 不保存业务分析真相

## 7. 文件级改造清单

### 7.1 `apps/server/src/api/heats.py`

职责调整：

- `_refresh_heat_runtime_state_from_context(...)`
  - 把 `sealed_segments` 仅视作 seal signal
  - 不再直接把 `prepared_sealed_candidates` 作为正式入库真源
  - 显式走 `active -> previous -> db`
- `_hydrate_candidate_from_existing_runtime(...)`
  - 继续负责已有 runtime 快照的字段继承
  - 需要补齐对上下文相关字段的继承口径
- `_choose_next_previous_runtime(...)`
  - 从“选一个 previous item”改成“决定 previous 的来源策略”
  - active rollover 时，优先基于旧 `active_runtime` 升格

### 7.2 `apps/server/src/services/heat_runtime_updater.py`

职责调整：

- 新增“仅补上下文，不重算分析”的更新模式
- 支持：
  - 更新 `context_start_time / context_end_time`
  - 更新 `runtime_metric_series`
  - 更新 `baseline_views[].current_metric_series`
- 禁止在 `previous_runtime` 补 `N+1` 时重新计算 binding 分析

### 7.3 `apps/server/src/services/formal_heat_service.py`

职责调整：

- `compile_runtime_candidates(...)`
  - 保留当前 runtime candidate 编译职责
  - 但不再成为 live sealed history 的唯一真源入口
- `build_runtime_preseal_payload(...)`
  - 要支持直接从 `previous_runtime` 生成正式 payload
- `append_sealed_heats(...)`
  - 入参语义改成“已确认可入库的 runtime 对象”
  - 不再默认等价于 raw `sealed_candidate`

### 7.4 `apps/server/src/services/heat_deviation_analysis_service.py`

职责调整：

- 保持“偏离分析只认当前炉次 `start_time ~ end_time`”
- 新增明确约束：
  - `previous_runtime` 补 `N+1` 时不重算
- 允许外部调用方显式选择：
  - `recompute`
  - `preserve_existing`

### 7.5 `apps/server/src/services/heat_runtime_types.py`

职责调整：

- 保持 `CurrentHeatRuntime` / `RuntimeBaselineView` 结构
- 补充 runtime item 字段说明与序列化口径
- 确保 `context_start_time / context_end_time`、`baseline_views.current_metric_series` 可以承载上下文扩展

### 7.6 新增服务

建议新增两个服务文件：

- `apps/server/src/services/heat_runtime_transition_service.py`
  - 负责 `active -> previous` 升格
  - 负责继承已有 binding 分析结果
- `apps/server/src/services/heat_runtime_seal_service.py`
  - 负责根据 seal signal 找到可入库的 `previous_runtime`
  - 负责从 `previous_runtime` 生成正式入库对象

## 8. 分阶段实施

### Phase 1

- 固化文档
- 新增 transition / seal 服务骨架
- 调整 `heats.py` 的生命周期分支，不动具体曲线补齐

### Phase 2

- 实现 `active -> previous` 升格时继承分析结果
- 让 `previous_runtime` 成为正式入库直接上游

### Phase 3

- 实现 source 增量同步更新 `active_runtime` 和 `previous_runtime`
- previous 只补 `N+1`，不重算偏离分析

### Phase 4

- replay 接到同一条 lifecycle
- 补完整回归测试

## 9. 回归测试

必须新增或调整以下后端回归：

1. 冷启动首次识别
   - `active_runtime != null`
   - `previous_runtime == null`
   - `active` 允许只有 `N`

2. active rollover
   - 旧 active 升格为 previous
   - previous 继承已有分析结果

3. previous 补 `N+1`
   - `context_end_time` 后推
   - `runtime_metric_series` 点增加
   - `baseline_bindings` 不重算

4. sealed 入库
   - 正式入库真源来自 `previous_runtime`
   - `metric_series(owner_type='heat')` 保存 `N-1 / N / N+1`
   - `heat_baseline_bindings` 继承 previous 分析结果

5. 最后一炉
   - 缺完整 `N+1` 仍可最终 seal

## 10. 验收标准

- live runtime 生命周期符合 `source -> current -> previous -> db`
- sealed history 不再绕过 `previous_runtime`
- `metric_series(owner_type='heat')` 不再退化成只存 `N`
- 补显示上下文不会触发新的偏离分析
- replay 与 live 共用同一套 runtime 生命周期语义
