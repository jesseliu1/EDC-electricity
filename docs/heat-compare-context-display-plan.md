# 炉次详情 Compare 上下文显示改造计划

## 1. 问题定义

当前“炉次详情 -> 与基线对比”图表的目标语义，已经从“只看当前炉次核心窗口”变成：

- 显示当前炉次 `N`
- 同时保留前一炉次 `N-1` 与后一炉次 `N+1` 的上下文曲线
- 图表上仍能明确看出当前炉次核心窗口的真实起止边界

但当前实现仍停留在旧口径：

- 后端 compare 已能返回更宽的 `metric_curves[*].current_curve`
- 前端 `HeatDetailView` 又把这些曲线裁回当前炉次 `start_time / end_time`
- compare 图最终只剩当前炉次本体

这会造成两类问题：

1. 用户在详情 compare 图里看不到前后文，无法按设计观察炉次前后衔接
2. compare 契约里“核心窗口”和“展示上下文窗口”混在一起，后续很容易再次回归

## 2. 当前实现分层

### 2.1 数据真源层

- `heats.start_time / end_time`
  - 表示当前炉次核心窗口
- `heats.context_start_time / context_end_time`
  - 表示当前炉次对应的上下文窗口
- `metric_series(owner_type='heat')`
  - 保存该炉次上下文范围内的指标点

当前 formal/runtime 的目标语义，已经是“核心窗口 + 上下文窗口 + 上下文曲线”。

### 2.2 compare API 组装层

当前 `GET /api/heats/{id}/compare` 里同时存在两套窗口语义：

- `heat.power_curve / heat.voltage_curve`
  - 当前仍更偏向核心窗口
- `baselines[*].metric_curves[*].current_curve`
  - 当前作为 compare 展示曲线
  - live 路径下默认使用 `±60 分钟` 的 display window 查询

这导致 compare 响应是“同一份 payload 里混了核心窗口和展示窗口”。

### 2.3 前端详情页渲染层

`apps/web/src/views/HeatDetailView.vue` 当前又做了第二次收缩：

- 把 `metric.current_curve` 裁回当前炉次窗口
- 把 `xAxis.min/max` 也锁到当前炉次窗口
- fallback 时还会退回 `current.value.powerCurve`

结果是后端传到前端的上下文曲线再次丢失。

## 3. 主要耦合点

### 3.1 compare 契约没有显式暴露上下文窗口

前端现在只能从：

- `heat.start_time / end_time`
- `metric_curves[*].current_curve` 的点范围

反推展示窗口。

这不稳定，也让 UI 很容易误把核心窗口当展示窗口。

### 3.2 前端把“比较逻辑”和“图表显示逻辑”混在一起

当前的裁剪既被用于：

- “是否完全重叠”的摘要判断
- 图表真正渲染

前者可以只对核心窗口做局部比对，后者不应该再裁整段上下文曲线。

### 3.3 live compare 仍带有旧 display window 兜底语义

当前 live compare 在没有显式 context 时，会走 `_resolve_compare_display_window()` 的 `±60 分钟` 逻辑。

这条路径仍然是历史展示策略，不是数据真源策略。

## 4. 真正配置入口

本次改造的真实入口只有两个：

1. 后端 compare 响应契约
   - `apps/server/src/schemas/heat.py`
   - `apps/server/src/api/heats.py`
2. 前端详情页 compare 图渲染
   - `apps/web/src/api/heat.ts`
   - `apps/web/src/stores/heat.ts`
   - `apps/web/src/views/HeatDetailView.vue`

不再把“展示上下文”继续散落在 fallback、clip、xAxis 推断里。

## 5. 阻塞点

如果只做“删掉前端 clip”这一个改动，仍然有两个问题：

1. 前端没有显式 context 边界，后续只能继续猜展示窗口
2. live compare 仍可能继续按旧 `±60 分钟` 逻辑取数，与 formal/runtime 已存 context 语义不一致

所以本次不能只做表面 UI 补丁，必须至少把 compare 的 context 口径显式化。

## 6. 修改目标

### 6.1 目标行为

- compare 图默认显示当前炉次上下文曲线
- 图上明确高亮当前炉次核心窗口
- 不再把上下文曲线裁回核心窗口
- formal 与 runtime 都走同一套“context-aware compare”契约

### 6.2 保留行为

- `start_time / end_time` 继续表示当前炉次核心窗口
- 摘要区如果需要做“是否完全重叠”判断，允许只对核心窗口做局部比对
- `heat.power_curve / voltage_curve` 暂不在本轮改写语义，避免扩大 blast radius

### 6.3 非目标

- 不在本轮重写 manual adjust 逻辑
- 不在本轮重做 baseline detail / preview 的窗口语义
- 不在本轮整体替换所有 compare 缓存策略
- 不在本轮把所有 `±60 分钟` 相关历史代码一次性清空，只收口当前 compare 主路径

## 7. 实施方案

### 7.1 后端：显式输出 context 窗口

修改：

- `apps/server/src/schemas/heat.py`
- `apps/server/src/api/heats.py`

动作：

1. 在 `HeatResponse / HeatWithCurve` 中显式增加：
   - `context_start_time`
   - `context_end_time`
2. `_to_heat_response()` 统一从 item 填充这两个字段
   - 若 item 未提供，则回退为 `start_time / end_time`
3. `get_heat_compare()` 的 live compare 路径优先使用：
   - `item.context_start_time`
   - `item.context_end_time`
   作为 display current curve 的查询窗口
4. 仅在 item 没有 context 信息时，才回退 `_resolve_compare_display_window()`

目标：

- compare API 的“展示上下文窗口”不再靠前端猜
- live/formal 更靠近同一套 context 真源

### 7.2 前端：拆分核心窗口与展示窗口

修改：

- `apps/web/src/api/heat.ts`
- `apps/web/src/stores/heat.ts`
- `apps/web/src/views/HeatDetailView.vue`

动作：

1. API type 与 store 显式透传：
   - `context_start_time`
   - `context_end_time`
2. 在详情页中拆分两个概念：
   - `heatCoreWindow`
   - `compareContextWindow`
3. compare 图渲染时：
   - `metric.current_curve` 直接按原始上下文曲线渲染
   - `xAxis.min/max` 使用 `compareContextWindow`
   - 不再对显示曲线执行 `clipCurveToWindow()`
4. 图上增加当前炉次核心窗口高亮
   - 作为视觉引导
   - 不再靠裁掉上下文来表达当前炉次范围
5. `selectedComparisonOverlap` 这类摘要逻辑保留局部裁剪
   - 仅用于“核心窗口比对”
   - 不影响图表显示

### 7.3 前端：去掉错误 fallback

动作：

1. compare 图不再把 `current.value.powerCurve` 当作上下文曲线 fallback
2. 当 compare metric curve 缺失时：
   - 显式空态
   - 或显示“当前缺少上下文曲线”
3. 避免把“缺上下文数据”伪装成“只有当前炉次本体”

## 8. 测试计划

### 8.1 后端测试

文件：

- `apps/server/tests/test_heats_api.py`

覆盖：

1. compare 响应包含 `context_start_time / context_end_time`
2. live compare 若 item 已有 context，优先按 item.context 查询 display current curve
3. formal compare 继续保留更宽 `metric_curves[*].current_curve` 语义

### 8.2 前端测试

文件：

- `apps/web/e2e/issue-acceptance.spec.ts`

覆盖：

1. 现有“extended current curve”用例改口径
   - 不再断言被裁回 46 个点
   - 改为断言 compare 图能保留完整上下文点数
2. 若补测试锚点：
   - 同时断言 `display_start / display_end`
   - 以及 `core_start / core_end`

### 8.3 最小验证顺序

1. `python3 -m pytest -q tests/test_heats_api.py -k compare`
2. `pnpm --dir apps/web test:e2e --grep "heat detail compare"`
3. `pnpm --dir apps/web build`

## 9. UAT 联动

本次改动影响用户可见图表与 compare 契约，属于 `docs/testing.md` 的强制联动场景。

因此需要同步更新：

- `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

更新点：

- 炉次详情 compare 图的预期不再是“只能看到核心炉次窗口”
- 改为“显示上下文窗口，并明确可识别核心炉次窗口”
- 同时保留“不得退化成全天污染”的约束

## 10. 风险与回避

### 风险 1

删除裁剪后，图表容易看起来“变长”，用户可能误以为又回到了全天污染。

回避：

- 显式使用 context 窗口而不是任意点范围
- 增加核心炉次窗口高亮
- UAT 与测试锚点都按 context 口径验证

### 风险 2

某些缺失 compare metric curve 的路径，过去依赖 `powerCurve` fallback 才不至于空图。

回避：

- 本轮明确转成空态/缺数提示
- 不再 silent fallback

### 风险 3

只改前端不改契约，后续仍可能再次被误改回核心窗口。

回避：

- 本轮同步把 context 作为 compare 显式字段输出

## 11. Step 0 工程审查结论（plan-eng-review）

### 11.1 Scope Challenge

- 现有代码已经能返回更宽的 `metric_curves[*].current_curve`
- 因此不需要重做整个 compare 服务
- 最小正确方案是：
  - 显式输出 context 窗口
  - 前端停止裁剪
  - 图上高亮核心窗口

这是比“重写 compare 全链路”更小、更稳的方案。

### 11.2 Architecture Review

- 推荐保留现有 formal/runtime 数据真源，不新增 service
- 本次不引入新模型、不改 DB schema、不新建缓存层
- 只收口 compare API 契约和详情页显示边界

### 11.3 Code Quality Review

- 需要拆开“摘要判断裁剪”和“图表显示裁剪”
- 需要移除错误 fallback，避免继续隐藏缺数问题

### 11.4 Test Review

- 后端需要覆盖 compare context 字段与 live context 优先级
- 前端需要回归“extended curve 不再被裁掉”
- UAT 需要同步更新 compare 口径

### 11.5 Performance Review

- 本次不会新增额外 EDC 查询轮次
- live compare 只是把原 display window 从固定 `±60` 改成优先读 item context
- 复杂度与当前量级一致

## 12. NOT in Scope

- manual adjust 图表口径统一
  - 原因：这是另一条用户路径，当前不阻塞 compare 图恢复上下文显示
- `heat.power_curve` 在所有接口中的统一语义重构
  - 原因：会扩大 blast radius，本轮先保持兼容
- compare 全量缓存键重构
  - 原因：当前问题主因不在缓存键，而在契约与前端裁剪
