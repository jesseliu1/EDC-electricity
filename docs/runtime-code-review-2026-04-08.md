# Runtime 架构代码审查（2026-04-08）

## 1. 审查范围

本次 review 以以下两份文档为主约束：

- `docs/runtime-layering-design-draft.md`
- `docs/heat-baseline-binding-refactor-plan.md`

同时交叉对照：

- `docs/runtime-source-of-truth-refactor-plan.md`
- `docs/runtime-implementation-plan.md`
- `docs/live-replay-refactor-plan.md`
- `docs/BACKEND_STRUCTURE.md`

审查目标：

1. 找出当前代码里仍然和 runtime 三层分工、runtime 真源、1:N baseline binding、live/replay 双主链相冲突的旧逻辑
2. 区分“主链仍在生效的冲突”与“已退居遗留代码但仍应清理的旧实现”
3. 给出按严重度排序的整改优先级

审查对象以当前工作树为准，重点查看：

- `apps/server/src/api/heats.py`
- `apps/server/src/services/formal_heat_service.py`
- `apps/server/src/services/heat_deviation_analysis_service.py`
- `apps/server/src/services/heat_runtime_factory.py`
- `apps/server/src/services/heat_runtime_types.py`
- `apps/server/src/services/heat_stream_processor.py`
- `apps/server/src/services/live_heat_runtime_service.py`
- `apps/server/src/services/heat_replay_batch_service.py`
- `apps/server/src/models/heat.py`
- `apps/server/src/models/heat_baseline_binding.py`
- `apps/server/src/models/baseline.py`

---

## 2. 总结结论

当前代码已经明显向目标架构收敛，但还没有完全达到“runtime 在运行过程中是唯一业务真源”的目标。

最核心的问题不是表结构没改，而是仍有几段旧主链语义残留在主路径里：

1. live / replay 的上下文仍会被“当前全局基线状态”影响
2. runtime candidate 仍允许在缺少出生快照时重新绑定基线
3. compare 仍在请求期直接回源 EDC，甚至为部分指标生成伪曲线
4. runtime / formal 的多指标落库和快照并未真正落地，主链仍是 `power / voltage` 双指标思维

如果不继续收口，用户最直接会看到三类不稳定现象：

- 同一条当前炉次在重启、refresh、切基线后语义漂移
- compare 页面结果取决于“这次请求现场取到了什么”，而不是 runtime / formal 里已经冻结的业务事实
- 文档里定义的多指标 runtime/binding 架构，在代码里仍有一部分只是接口表象，不是真正的后端真源

---

## 3. 已基本对齐的部分

这些点说明改造方向是对的，不需要再回到旧方案：

### 3.1 正式表主模型方向已对齐

- `apps/server/src/models/heat.py`
  - `Heat` 已回归炉次事实主表，包含 `context_start_time / context_end_time / is_manually_adjusted`
- `apps/server/src/models/heat_baseline_binding.py`
  - `heat_baseline_bindings` 已作为正式 1:N binding 表存在
- `apps/server/src/models/baseline.py`
  - `Baseline.is_default` 已成为默认黄金基线正式字段

### 3.2 `POST /api/heats/{id}/analyze` 已经下线

- `apps/server/src/api/heats.py`
  - 当前已不存在 `POST /api/heats/{id}/analyze`

这点与“compare / analyze 不再作为业务真源补算入口”的方向一致。

### 3.3 sealed history compare 已不再直接回源 EDC

- `apps/server/src/api/heats.py:3891-3905`
  - `record_source == sealed_history` 时，当前曲线来自 formal 已存曲线并裁到核心窗口

这点符合“历史 compare 优先读正式表，不再全天污染”的要求。

### 3.4 processor state 已基本从业务真源里退出

- `apps/server/src/services/heat_stream_processor.py:61-122`
  - `HeatProcessorConfig` 只保留切割相关固定配置
- `apps/server/src/services/heat_stream_processor.py:125-173`
  - `HeatProcessorState` 不再持有 `baseline_id`
- `apps/server/src/services/heat_stream_processor.py:190-205`
  - `baseline_id` 入参已被显式丢弃

这和“Processor is helper, not truth”方向一致。

---

## 4. 主要冲突项

以下按严重度排序。

### 4.1 阻断级：live / replay 上下文仍然会被当前全局基线状态影响

**证据**

- `apps/server/src/api/heats.py:964-1015`
  - `_iter_live_heat_inference_contexts()` 仍按 `_resolve_active_baseline_item()` 和 `_BASELINE_STORE` 里当前 published baselines 构造 live inference context
  - `_resolve_live_heat_inference_context()` 直接取 contexts[0]
- `apps/server/src/api/heats.py:1493-1510`
  - `refresh_heat_runtime_state()` 在没有现成 active runtime 上下文时，会回退到 `_resolve_live_runtime_refresh_context()`，后者最终仍可能落回 `_resolve_live_heat_inference_context()`
- `apps/server/src/api/heats.py:3600-3624`
  - replay job 创建时也取 `_resolve_live_heat_inference_context()`，并把当下的 `baseline_id / expected_duration_minutes` 注入 replay context

**为什么与文档冲突**

- `runtime-source-of-truth-refactor-plan.md` 明确要求：
  - 新基线只影响下一条新炉次
  - 当前炉次一旦出生，其 `expected_duration_minutes / primary_baseline_id / baseline_bindings` 必须冻结
- 但当前 live/replay 的入口上下文仍然由“当前全局默认基线”驱动

**直接影响**

- 进程重启、runtime 重建、head rebuild 后，当前进行中的炉次可能被新默认基线重新解释
- replay job 的切割尺子和出生上下文，可能取的是“任务发起时当前默认基线”，而不是历史时间点应有语义

**结论**

这不是单纯技术债，这是当前 runtime 真源仍未完全落地的主链冲突。

---

### 4.2 阻断级：candidate 只要缺少 birth context，仍会在编译阶段重新绑定基线

**证据**

- `apps/server/src/services/formal_heat_service.py:886-979`
  - `compile_runtime_candidates()` 对没有 frozen birth context 的 candidate，会重新：
    - 枚举 published baselines
    - 计算 applicable baselines
    - 选 primary baseline
    - 加载 baseline curve payloads
    - 生成新的 birth snapshot
- `apps/server/src/api/heats.py:1541-1557`
  - 现有 runtime 快照只在 `candidate.id == existing_item.id` 时才尝试 hydration
  - 一旦 ID 不一致，旧 birth context 就不会被复用

**为什么与文档冲突**

- `runtime-source-of-truth-refactor-plan.md` 要求的是“出生即冻结，运行中只增量更新”
- 当前实现仍保留“缺快照就按当前外部状态重编译”的后门

**直接影响**

- 当前炉次/前一炉次在 ID rollover、重建、跨阶段恢复时，仍可能丢失冻结 binding
- 这样即使 `CurrentHeatRuntime` 结构存在，它也不是严格唯一真源

**结论**

`CurrentHeatRuntime` 的外形已经在，但语义上还不是硬冻结对象。

---

### 4.3 高：compare 主路径仍在请求期回源 EDC，且会为部分指标生成伪曲线

**证据**

- `apps/server/src/api/heats.py:3907-3955`
  - 对非 `sealed_history` 的 compare，请求期会：
    - `_load_channel_curves_from_edc(...)`
    - `_load_heat_curves_from_edc(...)`
    - `_load_heat_curves_from_edc_window(...)`
- `apps/server/src/api/heats.py:2169-2261`
  - `_build_metric_curve_series()` 在当前曲线缺失时会：
    - 对 `power / voltage` 使用传入曲线兜底
    - 对其他指标继续生成曲线
- `apps/server/src/api/heats.py:2190-2200`
  - 当 definition metrics 缺失时，甚至会硬造 `power / voltage / temperature / pressure` 默认指标集合

**为什么与文档冲突**

- `runtime-layering-design-draft.md` 要求重计算前移到 business runtime
- `runtime-source-of-truth-refactor-plan.md` 要求 compare 优先只读 runtime 内部快照
- `heat-baseline-binding-refactor-plan.md` / `BACKEND_STRUCTURE.md` 要求 `metric_series` 存实体自己的正式曲线，不是请求期生成的展示数据

**直接影响**

- 同一条当前炉次，compare 结果可能随请求时刻、EDC 抖动、缓存命中情况变化
- 某些指标即使后端没有正式曲线真源，前端仍会看到“像真的一样”的曲线

**结论**

这条链路还带着明显的“页面来请求，我现场拼一版给你”的旧思路。

---

### 4.4 高：runtime / formal 仍是 `power / voltage` 双指标主链，没有真正落到定义级多指标

**证据**

- `apps/server/src/services/formal_heat_service.py:27-44`
  - `DEFAULT_METRIC_SPECS` 只有 `power / voltage`
- `apps/server/src/services/formal_heat_service.py:795-833`
  - `_build_metric_series_payloads()` 只为 `power / voltage` 写正式 `metric_series`
- `apps/server/src/services/heat_deviation_analysis_service.py:118-183`
  - baseline curve payload 也只承载 `power / voltage`
- `apps/server/src/services/heat_runtime_factory.py:214-246`
  - `baseline_curve_snapshots` 也只冻结 `power / voltage`
- `apps/server/src/api/heats.py:2598-2615`
  - runtime metric series spec 只有 `power / voltage`
- `apps/server/src/api/heats.py:2936-2949`
  - `_build_current_heat_runtime()` 只把 `power / voltage` 放进 runtime `metric_series`

**为什么与文档冲突**

- `heat-baseline-binding-refactor-plan.md` 明确要求 `metric_series` 以 definition metric item 为准，不应退化回固定双指标
- `BACKEND_STRUCTURE.md` 也把 definition metrics、baseline metrics、heat metrics 建成了按 item 存储的通用结构

**直接影响**

- 当前所谓“多指标 compare”并没有统一真源
- `temperature / pressure / 其他定义指标` 目前更多是请求期拼装能力，不是 runtime / formal 主链能力
- 这也解释了为什么 compare 代码里还残留大量生成曲线和 fallback 逻辑

**结论**

表结构已经通用化了，但业务主链还停在双指标时代。

---

### 4.5 中：`time_offset_percent` 文档上已经是正式分析字段，但统一分析服务根本没有产出

**证据**

- `apps/server/src/services/heat_deviation_analysis_service.py:216-252`
  - `time_offset_percent` 初始化为 `None`
  - 整个分析过程中没有任何赋值
- `apps/server/src/services/deviation_service.py:20-52`
  - `calculate_deviation()` 返回值只有：
    - `max_deviation`
    - `avg_deviation`
    - `abnormal_ranges`
    - `status`

**为什么与文档冲突**

- `runtime-layering-design-draft.md`、`heat-baseline-binding-refactor-plan.md`、`BACKEND_STRUCTURE.md` 都把 `time_offset_percent` 列为 binding 级正式字段
- `docs/progress.md` 最新记录也把它描述成已统一进入主链分析结果

**直接影响**

- binding 级 `time_offset_percent` 现在没有统一后端真源
- 列表、详情、任务快照如果显示了这个字段，只能依赖历史存量或外部注入，不能依赖当前统一分析链

**结论**

这是一个很硬的语义落差，文档口径已经比代码实现走得更前了。

---

### 4.6 中：compare 仍允许在缺少 binding 时回退到“全部已发布基线”

**证据**

- `apps/server/src/api/heats.py:924-950`
  - `_resolve_compare_baseline_ids()` 在 item 没有 `baseline_ids` 时，会把所有 published baselines 拼进去

**为什么与文档冲突**

- `heat-baseline-binding-refactor-plan.md` 已明确：
  - compare 返回的 `baselines[]` 应来自该炉次全部 binding
  - 不是来自系统当前所有已发布基线

**直接影响**

- 如果某条 runtime/formal item 的 binding 丢了或没写好，compare 不会显式报 binding 数据坏了
- 它会静默退化成“给你比系统里所有已发布基线”，这会掩盖数据一致性问题

**结论**

这类 fallback 会把架构错误包装成“看起来还能用”，后续最难排查。

---

## 5. 遗留旧代码清单

这部分不一定还在主链生效，但已经和当前设计方向不一致，建议后续清理。

### 5.1 请求期 live inference 老链仍留在主模块中

**证据**

- `apps/server/src/api/heats.py:1089-1280`
  - `_get_live_inferred_heat_store()`
  - `_resolve_live_heat_candidate()`
  - `_merge_live_heat_with_persisted_state()`
  - `_find_persisted_live_heat_alias()`

**观察**

- 当前主读链 `resolve_heat_record()` 已优先走 `active_runtime / previous_runtime / formal_db`
- 这些 helper 现在更多像旧架构残片

**风险**

- 会继续误导后续维护者，以为“请求期实时推断 + alias merge”仍是受支持主路径
- 测试也仍覆盖了这些旧 helper，进一步抬高清理成本

### 5.2 `_HEAT_STORE` 仍作为运行态持久化 section 保留

**证据**

- `apps/server/src/api/heats.py:2507-2516`
- `apps/server/src/api/heats.py:3351-3361`
- `apps/server/src/runtime_state.py:207-220`

**观察**

- 目前它更像 formal 结果的内存镜像，而不是正式真源
- 但命名和持久化方式仍带有旧 runtime ledger 时代痕迹

**风险**

- 容易再次把“formal DB 读模型”和“runtime cache/mirror”混成一层

---

## 6. 测试缺口

当前测试已有不少 runtime/birth_context 覆盖，但以下冲突没有看到充分回归保护：

### 6.1 缺少“新默认基线发布后，不影响已出生当前炉次”的硬回归

建议新增：

- active runtime 已出生
- 期间切换 `baselines.is_default`
- 再次 refresh / 进程恢复 / head rebuild
- 断言当前 heat 的：
  - `birth_context.primary_baseline_id`
  - `expected_duration_minutes`
  - `baseline_bindings`
  均不变

### 6.2 缺少“candidate 丢失 birth_context 时不得静默重绑”的回归

建议新增：

- 模拟 active runtime 恢复时 `id` 变化或 snapshot 缺损
- 断言系统不会静默按当前 published baselines 重新生成另一套 binding

### 6.3 缺少“compare 不得 fallback 到全部 published baselines”的回归

建议新增：

- 构造无 `baseline_ids` 的异常 heat item
- 断言 compare 返回 binding 数据异常或空，而不是系统所有 published baselines

### 6.4 缺少“非 power/voltage 指标必须来自真实 snapshot / metric_series”的回归

建议新增：

- definition 中包含 `temperature / pressure`
- compare 时断言：
  - 不允许生成伪曲线
  - 不允许在 formal/runtime 中无真源时默默给出展示值

### 6.5 缺少 `time_offset_percent` 统一分析产出的回归

建议新增：

- `compile_runtime_candidates()` 后断言 binding 上 `time_offset_percent` 有明确语义
- 若暂不实现，也要断言接口层不再把它描述成已统一产出字段

---

## 7. 建议整改顺序

按风险和收益，建议这样排：

### 第一阶段，先收真源边界

1. 切掉 `_resolve_live_heat_inference_context()` 对当前全局默认基线的依赖
2. 让 live / replay 入口只使用：
   - 通道
   - 切割配置
   - 已冻结的 birth context
3. 禁止 `compile_runtime_candidates()` 在 active/previous 主链上做“缺快照就重绑”

### 第二阶段，收 compare 主路径

1. compare 对 active runtime 优先读 runtime snapshot
2. compare 对 sealed history 继续只读 formal
3. 删除“生成伪曲线”路径
4. 删除“全部 published baselines fallback”路径

### 第三阶段，补齐多指标正式主链

1. runtime `metric_series`
2. formal `metric_series`
3. birth snapshot `baseline_curve_snapshots`
4. deviation analysis 输入

都要真正按 definition metrics 通用化，而不是只保留 `power / voltage`

### 第四阶段，收文档与回归

1. 对齐 `docs/progress.md`
2. 对齐 `docs/BACKEND_STRUCTURE.md`
3. 对齐 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
4. 补上上面的回归缺口

---

## 8. 最终判断

当前代码已经完成了“表结构改造 + runtime 对象显式化”的前半段，但还没完成“旧主链语义退场”的后半段。

换句话说：

- 新对象已经有了
- 新表也有了
- 但主路径里还残留着几段旧时代的决定逻辑

真正还没收住的点，不在 UI，而在这三句话：

1. 当前炉次是不是出生即冻结
2. compare 是不是只读 runtime/formal 真源
3. 多指标是不是已经进入正式主链，而不是停在展示层

这三点收住后，runtime 架构才算真正落地。
