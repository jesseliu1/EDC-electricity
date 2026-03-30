# EDC 换源统一方案

> 目标：把“换源”从分散在宿主按钮与后端局部逻辑里的隐式副作用，收敛成一个明确、可复用、可测试的统一动作。

---

## 1. 问题背景

近期 `S04 / S05` 联调暴露出的根因不是单点接口失败，而是“换源后旧源绑定残留”：

- 用户把 EDC 源从 source A 切到 source B
- 宿主连接本身可能已经成功
- 但宿主已添加通道、基线指标 `edc_channel_id`、活动基线、运行态缓存仍然指向旧源的 `suid/cuid`
- 后续 Dashboard / 炉次 / 任务 / 报表继续拿旧绑定去读新源，结果就是空数据、假失败或混乱运行态

因此，“换源”必须被定义为一个独立的系统动作，而不是继续散落在：

- 宿主 `测试连接`
- 宿主 `同步通道`
- 宿主 `保存设置`
- 后端 `PUT /settings/edc-connection`
- 启动恢复时的环境变量覆盖

---

## 2. 调查结论

### 2.1 现状中哪些地方在各自处理“换源”

宿主侧：

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
  - `handlePersist`
  - `handleConnect`
  - `handleSyncChannels`
  - 这三个入口都各自判断 `sourceSwitched`，并分别清本地目录、已添加通道、连接态
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`
  - 负责把宿主当前选择同步回后端

后端侧：

- `apps/server/src/api/settings.py`
  - 原先在 `PUT /settings/edc-connection` 内部做局部清理
- `apps/server/src/runtime_state.py`
  - 启动恢复时如果显式环境变量覆盖连接配置，也需要重置旧运行态

这就是当前“换源行为”分散的根因。

### 2.2 什么属于“换源”，什么不属于

统一定义如下：

- `源身份（source identity） = base_url + username`
- `连接材料（connection material） = base_url + username + password + api_key`

含义：

- `base_url` 或 `username` 变化：视为真正换源
- 只改 `password` 或 `api_key`：不是换源，只是连接材料变化

这个区分很关键，因为：

- 真正换源必须清旧源绑定
- 仅密码变更不应该把宿主通道、基线绑定全清掉

---

## 3. 统一边界

### 3.1 换源必须清掉的状态

这些状态直接或间接绑定旧源 `suid/cuid`，属于 source-bound state：

- 宿主已添加通道清单 `host_channels`
- 宿主通道目录缓存 `host_channel_catalog`
- 宿主通道最近同步时间 `host_channel_last_sync_at`
- 宿主连通状态摘要 `host_connectivity_status`
- 当前激活基线 `active_baseline_id`
- 基线定义中的指标通道绑定 `baseline_definitions.metrics[].edc_channel_id`
- 比对/实时相关运行时缓存

### 3.2 换源不该清掉的状态

这些不依赖旧源 `suid/cuid`，不应被换源顺手清掉：

- 基线定义主体内容本身
- 已生成的基线实例
- 炉次、任务、报表历史记录
- 容差、切割、报表时间等通用业务设置
- 纯 UI 偏好与页面过滤条件

---

## 4. 后端统一入口

### 4.1 统一入口约束

后端统一收口为一个显式入口：

- `POST /api/settings/source-switch`

输入参数：

- `base_url`
- `username`
- `password`
- `api_key`

输出结果：

- 是否发生 `source_identity_changed`
- 是否发生 `connection_material_changed`
- 清掉了多少宿主通道
- 清掉了多少目录缓存
- 清掉了多少基线绑定
- 被解除的活动基线 ID
- 当前切换到的目标源

### 4.2 当前已落地的后端实现

已新增统一服务：

- `apps/server/src/services/source_switch_service.py`

统一入口路由：

- `apps/server/src/api/settings.py`
  - `POST /settings/source-switch`

统一 schema：

- `apps/server/src/schemas/source_switch.py`

当前统一行为：

1. 如果 `connection_material_changed = true`
   - 更新 EDC 连接配置
   - 清宿主通道目录缓存
   - 清宿主最近同步时间
   - 把宿主连接状态重置为 disconnected
   - 失效比对/实时缓存

2. 如果 `source_identity_changed = true`
   - 在上面基础上进一步清掉：
   - 宿主已添加通道
   - 当前活动基线
   - 基线定义中的 `edc_channel_id`

3. 启动恢复时的环境变量覆盖也走同一套服务
   - 避免运行时恢复又绕开统一逻辑

### 4.3 兼容策略

现有旧接口：

- `PUT /api/settings/edc-connection`

目前保留，但已经委托给同一套统一逻辑，避免再出现第二套换源规则。

后续原则：

- 新逻辑一律走 `source-switch`
- 旧接口只作为兼容壳，不再承载独立业务语义

---

## 5. 前端/宿主统一方案

### 5.1 交互原则

用户可以换源，但换源是破坏性操作，不能静默发生。

只要满足以下条件：

- 当前配置与上次已应用配置相比，`source identity` 发生变化
- 且当前存在 source-bound state

那么在以下入口前都必须先统一拦截：

- `测试连接`
- `同步通道`
- `保存设置`

### 5.2 弹窗文案语义

确认框不应泛泛提示，而应明确告诉用户：

- 你正在切换到新的 EDC 数据源
- 继续后将清除当前源相关配置
- 包括：已同步通道、已添加通道、基线通道绑定、当前激活基线、宿主连接状态与相关缓存
- 清除后需要重新同步并重新绑定通道

用户行为：

- 点确认：调用统一换源流程
- 点取消：本次操作中止，不改任何现有状态

### 5.3 宿主代码收敛目标

当前宿主 `SettingsView.tsx` 里 `handlePersist / handleConnect / handleSyncChannels` 仍各自处理一部分 `sourceSwitched` 分支，这只是过渡态。

下一步应收敛为宿主侧唯一编排方法，例如：

- `confirmAndApplySourceSwitch(action)`

职责：

- 统一判断是否真换源
- 统一判断当前是否存在需要确认的 source-bound state
- 统一弹窗确认
- 确认后调用后端 `POST /api/settings/source-switch`
- 成功后再继续执行本次动作：测试连接 / 同步通道 / 保存

这样前端也不会再把换源副作用散落在三个按钮各自的实现里。

---

## 6. 当前状态

已完成：

- 后端统一服务已落地
- 后端显式统一入口已落地
- 启动恢复路径已收口到同一服务
- 已补测试，确认“密码变更”和“真正换源”被正确区分

待完成：

- 宿主确认弹窗
- 宿主侧唯一编排方法
- 删除 `SettingsView.tsx` 中分散的 `sourceSwitched` 本地清理分支
- 补完整 E2E：取消 / 确认 / 确认后重绑闭环

---

## 7. 统一原则总结

一句话总结：

- 后端负责定义唯一真相和唯一重置入口
- 前端负责在用户触发换源前做一次明确确认
- 真正换源才清 source-bound state
- 仅密码/API Key 变化只重置连接验证态，不清业务绑定

这次收口后，系统不应再允许“新源地址 + 旧源通道绑定”这种半切换状态继续存在。
