# Runtime Dataflow

> 本文是 `current -> previous -> db` 这条 runtime 主链的专项说明。  
> 稳定版总述与正式字段口径见 [BACKEND_STRUCTURE.md](./BACKEND_STRUCTURE.md)。

## 1. 目标

本文只说明一件事：

- 炉次相关数据从 EDC 源进入系统后，如何流经 runtime，再落成正式历史

并回答两个问题：

- 每一层数据对象分别代表什么业务语义
- 每个模块各自应该负责什么，不应该负责什么

## 2. 主链总览

live 主链固定为：

`EDC source -> point loader -> processor -> active_runtime(current) -> previous_runtime -> heats/metric_series/heat_baseline_bindings -> API -> frontend`

业务语义如下：

1. EDC source 提供原始时序点。
2. point loader 按时间窗口读取点流。
3. processor 根据点流识别炉次边界。
4. `active_runtime` 表示当前炉次 `N`。
5. `previous_runtime` 表示上一炉次，是正式入库前的直接上游。
6. formal DB 保存稳定历史。
7. API 只组装和透传业务对象。
8. frontend 只展示后端已经定义好的业务语义。

## 3. 核心对象的业务语义

### 3.1 point loader

职责：

- 只负责按 `start_time / end_time` 取原始点
- 只返回“这个时间窗里采到了哪些点”

不负责：

- 不判断这些点属于哪一炉
- 不判断是 `N-1 / N / N+1`
- 不做偏离分析
- 不做正式入库

### 3.2 processor

职责：

- 从点流中识别炉次边界
- 产出：
  - `active_segment`
  - `previous_segment`
  - `sealed_signal`

不负责：

- 不直接生成正式 `heat`
- 不直接生成 `heat_baseline_bindings`
- 不负责上下文曲线包拼接

### 3.3 active_runtime

职责：

- 表示当前正在发生的炉次 `N`
- 是当前炉次分析真源和展示真源

业务规则：

- 偏离分析只认自己的 `start_time ~ end_time`
- 显示曲线目标是 `N-1 / N`
- 冷启动首次识别时允许只有当前炉次 `N`
- 如果对象存在，曲线不应为空；至少应覆盖自己的 `N`

### 3.4 previous_runtime

职责：

- 表示上一条炉次
- 是正式入库前的唯一直接上游

业务规则：

- 它由上一轮 `active_runtime` 升格而来
- 应继承自己在 `active_runtime` 阶段已经积累好的 `N-1 / N`
- 后续随着下一条当前炉次继续生长，再持续补 `N+1`
- 它保留上一轮已经得到的 `baseline_bindings` 分析结果
- 补 `N+1` 时不应触发一次新的偏离分析

允许与不允许：

- 允许 `previous_runtime == null`
  - 只限冷启动或当前只识别到一炉
- 不允许 `previous_runtime != null` 但连自己的 `N` 都没有
- 允许 `previous_runtime != null` 但 `N+1` 只补了一部分

### 3.5 formal DB

职责：

- `heats` 保存炉次事实
- `metric_series(owner_type='heat')` 保存该炉次正式曲线包
- `heat_baseline_bindings` 保存 `heat + baseline` 粒度分析结果

业务规则：

- DB 只保存稳定历史
- DB 不应该再承载“仍在变化的 runtime 语义”
- 正式 `metric_series(owner_type='heat')` 的目标口径是该炉次自己的 `N-1 / N / N+1`

### 3.6 API

职责：

- 把 runtime 或正式历史整理成接口对象
- 透传后端已经确定的业务语义

不负责：

- 不在详情请求阶段偷偷补分析
- 不在 compare 请求阶段重新定义业务真相
- 不临时拼一套与 runtime/DB 不一致的炉次事实

### 3.7 frontend

职责：

- 展示后端已经定义好的炉次对象
- 基于接口中的窗口与曲线结果呈现图表和状态

不负责：

- 不自己猜点属于 `N-1 / N / N+1`
- 不根据图上点的分布反推炉次边界
- 不自己决定一条炉次是否完整

## 4. 曲线真源如何传递

### 4.1 active_runtime 的曲线来源

`active_runtime` 的曲线由两部分组成：

- 来自上一炉尾部的继承数据，用来形成 `N-1`
- 来自当前增量点的新数据，用来形成 `N`

也就是说，`active_runtime` 不是只靠“本轮新拉的点”就能天然长出完整 `N-1 / N`。

### 4.2 previous_runtime 的曲线来源

`previous_runtime` 的曲线也由两部分组成：

- 它在 `active_runtime` 阶段已经形成的 `N-1 / N`
- 下一条当前炉次增长过程中贡献的后续点，用来形成 `N+1`

因此，`previous_runtime` 的曲线补齐不只是“把 fetch 时间改大”，而是：

- 继承旧 runtime 曲线
- 接上本轮新点
- 去重、排序、裁剪到目标窗口

## 5. 声明窗口与实际覆盖窗口

runtime 中必须明确区分两个概念：

- 声明窗口
  - `context_start_time / context_end_time`
  - 表示这条 runtime 在业务上希望展示到哪里
- 实际覆盖窗口
  - `actual_context_start_time / actual_context_end_time`
  - `runtime_metric_series.series_json.points` 实际最早点和最晚点
  - 表示当前曲线真源实际上已经长到了哪里

这两个概念不能混在一起。

正确语义：

- `active_runtime`
  - 声明窗口目标是 `N-1 / N`
  - 冷启动时实际覆盖窗口允许只有 `N`
- `previous_runtime`
  - 声明窗口目标是 `N-1 / N / N+1`
  - 实际覆盖窗口允许暂时只到 `N` 或部分 `N+1`

错误语义：

- 字段上声明已经覆盖 `N+1`
- 但实际曲线点仍然只停在自己的 `N`

## 6. 生命周期

### 6.1 冷启动

允许：

- `active_runtime != null`
- `previous_runtime == null`
- `active_runtime.context_start_time == active_runtime.start_time`

这属于正常状态，不应被当成刷新失败。

### 6.2 active -> previous

当新一条当前炉次出生时：

- 旧 `active_runtime` 升格为 `previous_runtime`
- 升格时应直接继承：
  - 已有曲线包
  - 已有 `baseline_bindings`
  - 已有 `deviation_score / avg_deviation_score / abnormal_duration_minutes`

这里的业务语义是：

- 上一炉已经在运行态里形成过业务真相
- 升格后只是身份变化，不应该把它重新算成另一条炉次

### 6.3 previous -> db

当 `previous_runtime` 达到封口条件时：

- 应由 `previous_runtime` 自己生成 preseal payload
- 再落入：
  - `heats`
  - `metric_series`
  - `heat_baseline_bindings`

不应：

- 再回头从 raw `sealed_segment` 重新编译另一份正式 heat

## 7. seal 时的完整度规则

seal 校验应分两层。

### 7.1 强校验：失败应报错

以下情况应拒绝 seal：

- `previous_runtime` 不存在，却尝试 seal
- `previous_runtime.runtime_metric_series` 为空
- 实际曲线覆盖连自己的 `start_time ~ end_time` 都没覆盖住

业务语义：

- 上一炉本体都没成立，不能当成正式历史

### 7.2 软校验：允许 seal

以下情况允许 seal，但语义上属于“部分上下文”：

- 自己的 `N` 已完整
- 已继承 `N-1 / N`
- `N+1` 还未完全补到声明窗口末端

业务语义：

- 炉次本体已成立，只是详情页想看的后文尚未补满

当前实现补充：

- runtime item 会持久化 `actual_context_start_time / actual_context_end_time`
- `/api/heats`、`/api/heats/{id}`、`/api/heats/{id}/compare` 会同时返回声明窗口与实际覆盖窗口
- `append_sealed_heats(...) / replace_heat_range(...)` 会在真正写正式表前执行“自己的 `N` 是否存在”强校验

## 8. live 与 replay 的关系

live 与 replay 共用同一条业务主链。

共同点：

- 都先经过 processor
- 都生成 `active_runtime / previous_runtime`
- 都通过 `previous_runtime -> formal DB` 入库

差异点：

- live 是增量调度
- replay 是批量调度

但差异只应体现在：

- 调度方式
- 批次大小
- 取数步长

不应体现在：

- 再造一套独立的业务判断逻辑
- 再造一套与 live 不同的 runtime 语义

## 9. 模块边界总结

模块职责压缩版：

- loader：只取点
- processor：只切炉
- runtime updater：只更新 runtime
- curve merge：只合并曲线
- analysis：只做偏离分析
- seal：只从 `previous_runtime` 生成正式 payload
- DB：只保存稳定历史
- API：只组装透传
- frontend：只展示结果

## 10. 文档归位

本文档负责：

- runtime 主链专项说明
- 生命周期规则
- 曲线真源如何传递
- 各层边界

稳定版正式口径在：

- [BACKEND_STRUCTURE.md](./BACKEND_STRUCTURE.md)

阶段性改造计划在：

- [runtime-current-previous-db-plan.md](./runtime-current-previous-db-plan.md)
