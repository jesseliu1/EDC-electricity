# Runtime 真源重构计划

## 1. 问题定义

当前系统已经有了 `CurrentHeatRuntime（当前炉次运行态对象）`、`HeatStreamProcessor（炉次点流处理器）`、`compile_runtime_candidates（运行态候选编译）` 这些新结构，但它们还没有形成真正的唯一业务真源。

当前最核心的问题不是“没有 runtime”，而是：

1. `runtime（运行态对象）` 里混入了旧的 `live baseline resolution（实时基线解析）` 语义
2. `active runtime（当前运行炉次）` 不是在炉次出生时冻结绑定，而是在刷新链里继续被外部状态影响
3. `processor state（处理器状态）` 同时承担了“切割辅助状态”和“业务固定配置”两种职责
4. `compare / deviation analysis（对比 / 偏差分析）` 仍然会在运行过程中回查外部 `baseline（黄金基线）` 真源

这导致当前实现呈现出一种危险状态：

- 结构上看起来像 `runtime（运行态对象）` 已经是主真源
- 语义上却仍是“每轮 refresh 重新编译一次业务事实”

这不符合当前业务要求。

---

## 2. 本轮目标

本轮目标不是局部修一个 `no_runtime_heats_inferred（未推断出运行炉次）`。

本轮要完成的是：

1. 让 `runtime（运行态对象）` 在运行过程中成为当前炉次的唯一业务真源
2. 让新发布的 `baseline（黄金基线）` 只影响下一条新炉次，不回写正在进行中的当前炉次
3. 让 `processor state（处理器状态）` 回归“点流处理辅助状态”，不再承担业务绑定真源
4. 让 `live_incremental（实时增量）` 和 `replay_batch（批量回放）` 共用同一套“出生即冻结、运行中只增量更新”的 runtime 语义
5. 让 `compare / deviation analysis（对比 / 偏差分析）` 优先只读 runtime 内部快照，不再在主路径里靠请求时临时补查业务真源

---

## 3. 业务语义基线

本轮所有代码修改，都必须满足以下业务语义。

### 3.1 `NewBaselineAffectsNextHeatOnly（新基线只影响下一条新炉次）`

- 新发布的 `baseline（黄金基线）` 不允许立刻影响正在进行中的当前炉次
- 当前炉次一旦出生，其：
  - `expected_duration_minutes（预期炉次时长）`
  - `primary_baseline_id（主黄金基线ID）`
  - `baseline_bindings（基线绑定列表）`
  - `baseline_curve_snapshots（基线曲线快照）`
  都应冻结在该炉次自己的 runtime 对象里

### 3.2 `CurrentHeatOwnsItsBusinessSnapshot（当前炉次自带业务快照）`

- 当前炉次在初始化时就应带上它后续 compare / analyze / persist 需要的业务真源
- 之后运行中允许追加：
  - 当前曲线点
  - 当前结束时间
  - 实时分析结果
- 不允许重新向外部 `baseline（黄金基线）` 真源决定“我到底绑定谁”

### 3.3 `ProcessorIsHelperNotTruth（处理器是辅助器，不是业务真源）`

- `HeatStreamProcessor（炉次点流处理器）` 只负责识别点流里的炉次边界
- `HeatProcessorState（炉次处理器状态）` 只保存切割辅助状态
- 业务事实属于 `CurrentHeatRuntime（当前炉次运行态对象）`

---

## 4. 当前实现偏差

### 4.1 `live inference context（实时推断上下文）` 仍按全局当前基线重算

问题位置：

- `apps/server/src/api/heats.py`

现状：

- `_resolve_live_heat_inference_context()（实时推断上下文解析）` 每轮 refresh 都重新从当前已发布 / 默认黄金基线里选 context
- context 内部仍直接携带：
  - `baseline_id（基线ID）`
  - `expected_duration_minutes（预期炉次时长）`

结果：

- 新默认黄金基线会提前影响当前炉次的推断尺子

### 4.2 `compile_runtime_candidates（运行态候选编译）` 仍按 refresh 时刻重算适用基线

问题位置：

- `apps/server/src/services/formal_heat_service.py`

现状：

- 当前实现每次编译 runtime candidate，都会重新：
  - 读取 `published baselines（已发布基线）`
  - 依据 `candidate.start_time（候选炉次开始时间）` 计算适用基线
  - 重新选主黄金基线
  - 重新加载基线曲线

结果：

- 当前 runtime 对象不是“冻结快照”，而是“可重编译对象”

### 4.3 `processor state（处理器状态）` 混了固定配置和运行状态

问题位置：

- `apps/server/src/services/heat_stream_processor.py`

现状：

- 当前 `HeatProcessorState（炉次处理器状态）` 同时保存：
  - `baseline_id（基线ID）`
  - `expected_duration_minutes（预期炉次时长）`
  - `cutting_config_token（切割配置签名）`
- 也保存：
  - `bootstrapped（是否完成首轮预热）`
  - `activity_threshold（活跃阈值）`
  - `last_point_timestamp（最后处理点时间）`
  - `points_buffer（点缓冲区）`

结果：

- 业务配置和流处理状态没有分层

### 4.4 `runtime（运行态对象）` 还没有完整内嵌基线业务快照

问题位置：

- `apps/server/src/services/heat_runtime_types.py`
- `apps/server/src/api/heats.py`
- `apps/server/src/services/heat_deviation_analysis_service.py`

现状：

- runtime 内已经有：
  - `bindings（绑定列表）`
  - `metric_series（当前炉次指标序列）`
  - `preseal_payload（待固化载荷）`
- 但还缺少：
  - `baseline_curve_snapshots（基线曲线快照）`
  - `definition_metric_snapshots（定义指标模板快照）`
  - 明确冻结的 `HeatBirthContext（炉次出生上下文）`

结果：

- compare / analyze 仍会在主路径回查外部 baseline 真源

---

## 5. 目标分层

本轮改造后，后端运行时边界应收敛为以下结构。

### 5.1 `HeatBirthContext（炉次出生上下文）`

职责：

- 只在新炉次诞生时创建一次
- 表示这个炉次从出生起冻结的业务解释上下文

建议字段：

- `heat_id（炉次ID）`
- `channel_key（推断通道）`
- `cutting_mode（切割模式）`
- `expected_duration_minutes（预期炉次时长）`
- `plant_timezone（工厂时区）`
- `primary_baseline_id（主黄金基线ID）`
- `baseline_bindings_snapshot（基线绑定快照）`
- `definition_metric_snapshots（定义指标模板快照）`
- `baseline_curve_snapshots（基线曲线快照）`

### 5.2 `HeatProcessorConfig（处理器固定配置）`

职责：

- 仅保存切割器所需的固定配置
- 由 `HeatBirthContext（炉次出生上下文）` 派生

建议字段：

- `heat_id（炉次ID）`
- `channel_key（推断通道）`
- `cutting_mode（切割模式）`
- `expected_duration_minutes（预期炉次时长）`
- `gap_minutes（闭合间隔分钟数）`
- `cutting_config_token（切割配置签名）`

### 5.3 `HeatProcessorState（处理器运行状态）`

职责：

- 只保存点流推进过程中的可变状态

建议字段：

- `processor_phase（处理阶段）`
- `bootstrapped（是否完成首轮预热）`
- `activity_threshold（活跃阈值）`
- `last_point_timestamp（最后处理点时间）`
- `points_buffer（未决点缓冲）`
- `current_segment_start_timestamp（当前候选段开始时间）`
- `current_segment_end_timestamp（当前候选段结束时间）`
- `current_heat_id（当前跟踪炉次ID）`
- `pending_seal_heat_id（待固化炉次ID）`

### 5.4 `CurrentHeatRuntime（当前炉次运行态对象）`

职责：

- 当前炉次唯一业务真源

必须内嵌：

- `facts（炉次事实）`
- `bindings（基线绑定列表）`
- `metric_series（当前炉次指标序列）`
- `baseline_curve_snapshots（基线曲线快照）`
- `definition_metric_snapshots（定义指标模板快照）`
- `preseal_payload（待固化载荷）`
- `processing_meta（处理上下文）`

---

## 6. 实施阶段

### 阶段 1：收口对象边界

目标：

- 把 `processor state（处理器状态）` 和 `runtime truth（运行态真源）` 分开

改动：

1. 新增 `HeatBirthContext（炉次出生上下文）`
2. 拆分 `HeatProcessorConfig（处理器固定配置）` 与 `HeatProcessorState（处理器运行状态）`
3. 为 `CurrentHeatRuntime（当前炉次运行态对象）` 补齐快照字段定义

阶段完成后必须检查：

- `docs/BACKEND_STRUCTURE.md`
- `docs/runtime-layering-design-draft.md`
- 本文档

然后执行一次 `review` skill 口径的差异审查。

### 阶段 2：收口新炉次出生链

目标：

- 让新炉次在出生时一次性冻结业务快照

改动：

1. 新增 `HeatRuntimeFactory（炉次运行态工厂）`
2. 让 `live_incremental（实时增量）` 在“新炉次确认生成”时调用工厂
3. 当前炉次一旦创建，后续 refresh 不再重算其绑定与固定业务属性

阶段完成后必须检查：

- `docs/runtime-layering-design-draft.md`
- `docs/heat-baseline-binding-refactor-plan.md`
- 本文档

然后执行一次 `review` skill 口径的差异审查。

### 阶段 3：收口运行中刷新链

目标：

- 让 refresh 只更新当前炉次自身增量状态

改动：

1. 新增 `HeatRuntimeUpdater（炉次运行态更新器）`
2. `refresh_heat_runtime_state()（刷新炉次运行态）` 不再通过 `compile_runtime_candidates（运行态候选编译）` 重算当前炉次业务绑定
3. 区分：
   - `no_new_heat_born（当前没有新炉次出生）`
   - `active_heat_continues（当前炉次仍在继续）`
   - `runtime_refresh_failed（运行态刷新失败）`

阶段完成后必须检查：

- `docs/runtime-layering-design-draft.md`
- `docs/testing.md`
- 本文档

然后执行一次 `review` skill 口径的差异审查。

### 阶段 4：收口 compare / analysis / persist

目标：

- compare / analysis / persist 统一消费 runtime 真源

改动：

1. 限制 `BaselineCurveLoad（基线曲线加载）` 时机
   - 只允许发生在：
     - `HeatRuntimeFactory（炉次运行态工厂）`
     - `ReplayBatch（批量回放）`
     - `RuntimeRebuild（运行态重建）`
2. `compare / deviation analysis（对比 / 偏差分析）` 不再在主路径临时决定当前炉次绑定谁
3. `preseal_payload（待固化载荷）` 改为真正的最终写库形态

阶段完成后必须检查：

- `docs/BACKEND_STRUCTURE.md`
- `docs/heat-baseline-binding-refactor-plan.md`
- 本文档

然后执行一次 `review` skill 口径的差异审查。

### 阶段 5：回归与部署

目标：

- 做后端主链回归，之后再做 blank 重建和真实源验证

后端最小回归：

- `python3 -m pytest -q tests/test_heat_stream_processor.py`
- `python3 -m pytest -q tests/test_heat_replay_api.py`
- `python3 -m pytest -q tests/test_heats_api.py`
- `python3 -m pytest -q tests/test_formal_heat_api.py`

完成后必须：

- 更新 `docs/progress.md`
- 若运行态边界或验收口径有变化，更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

---

## 7. 明确禁止

1. 不允许继续在 `active_runtime（当前运行炉次）` 已存在时，重新按全局当前基线决定它的 `expected_duration_minutes（预期炉次时长）`
2. 不允许 `processor state（处理器状态）` 继续作为当前炉次业务绑定真源
3. 不允许 `compare（对比）` 页面请求再把“缺少 runtime 快照”伪装成“去外面补一下就好了”
4. 不允许“先把功能跑通，后面再收语义”，本轮先收语义，再逐层落代码

---

## 8. 当前判断

当前系统还没有真正做到：

- `runtime（运行态对象）` 在运行过程中是唯一真源

本轮改造的验收标准也应围绕这句话展开。
