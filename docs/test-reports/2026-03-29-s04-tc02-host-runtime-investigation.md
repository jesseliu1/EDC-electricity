# 2026-03-29 S04-TC02 宿主运行态调查

## 调查目的

- 解释为什么 `S04-TC02` 的正式留档表现为：
  - 点击 `测试连接` 后页面仍显示 `离线 / 等待验证`
  - 保存后 `runtime-status.overall_code=host_disconnected`
- 区分这是“当前源码仍无法连接 source B”，还是“宿主 `3001` 运行口径 / 构建口径不一致”

## 当前链路结论

### 1. source B 当前并不是不可连

- 直接调用宿主 `host-api`：
  - `POST http://127.0.0.1:3001/host-api/edc/test-connection`
  - body: `endpoint=http://61.216.55.133`, `username=admin`, `password=admin`
- 返回：
  - `ok=true`
  - `nodeName=EDC Gateway (61.216.55.133)`
  - `sensorCount=3`
  - `channelCount=788`
  - `enabledChannelCount=739`

因此，`source B` 在当前环境下可成功登录并读取设备清单，`S04-TC02` 不是“当前源码连不上新源”的问题。

### 2. 本机 `3001` 一度确实在跑旧宿主构建

- 调查时发现 `3001` 宿主页面最初加载的构建入口为旧 bundle：
  - `dist/assets/index-zM_Fh_3t.js`
- 对该旧 bundle 的网络抓取结果显示，宿主 UI 在“测试连接”后会把业务后端写请求发到：
  - `http://127.0.0.1:8000/api/settings/edc-connection`
  - `http://127.0.0.1:8000/api/settings/host-channels`
  - `http://127.0.0.1:8000/api/settings/host-connectivity-status`
- 而不是当前正式联调口径的宿主同域 `/api`（再由 `3001 -> 8001` 代理）

这说明宿主 `3001` 运行面曾存在“旧 dist 与当前源码不一致”的环境分叉。仅这一点就足以让浏览器观感、`3001` 宿主 UI、本机 `8001` 运行态彼此不一致。

### 3. 重建宿主 dist 后，回写链路恢复到同域 `/api`

- 执行：
  - `npm run build`
- 新构建入口变为：
  - `dist/assets/index-DtLUiBmF.js`
- 重新打开 `http://127.0.0.1:3001/` 后，宿主页面网络请求已改为：
  - `GET http://127.0.0.1:3001/api/settings`
  - `POST http://127.0.0.1:3001/host-api/edc/test-connection`
  - `PUT http://127.0.0.1:3001/api/settings/edc-connection`
  - `PUT http://127.0.0.1:3001/api/settings/host-channels`
  - `PUT http://127.0.0.1:3001/api/settings/host-connectivity-status`

即：宿主 UI 已恢复为当前源码设计的“同域 `/api` + 同域 `host-api`”口径。

## 宿主行为复测

### A. 真实切源后直接点“保存设置”

从当前 `source B` 切回 `source A`（`http://60.251.229.32 / volapu / admin`）后，**不先点测试连接**，直接点 `保存设置`：

- 页面表现：
  - `系统状态 = 离线`
  - `等待验证`
- 后端运行态：
  - `host-connectivity-status.is_connected=false`
  - `runtime-status.overall_code=host_disconnected`

这表明：**切源后直接保存进入 `host_disconnected` 是当前设计行为**，不是随机故障。

### B. 真实切源后先点“测试连接”

同样从 `source B` 切回 `source A`，但先点 `测试连接`：

- 页面表现：
  - `系统状态 = 在线`
  - `EDC 连接就绪`
- 后端运行态：
  - `host-connectivity-status.is_connected=true`
  - `runtime-status.overall_code=no_enabled_channels`
  - `edc.base_url=http://60.251.229.32`

这说明：**当前源码下，切源后“测试连接”可以成功把连接状态拉回在线**。之所以不是 `ready`，是因为当前 `host_channel_total=0`，运行态缺的是“已添加通道”，不是“宿主断线”。

## 对 S04-TC02 的解释

结合正式 UAT 脚本定义与本次调查，当前更合理的解释是：

1. `S04-TC02` 不是“source B 当前不可连接”
2. `S04-TC02` 也不应继续笼统归因为“当前源码仍有宿主连接 bug”
3. 更可能的原因是以下两类之一：
   - 当时 `3001` 运行的是旧宿主构建 / 旧环境口径，导致宿主 UI 与正式联调后端不一致
   - 当时实际执行步骤没有形成“测试连接成功后再保存”的闭环，保存动作按设计把运行态写成了 `host_disconnected`

## 建议

- 正式 UAT 若要重跑 `S04-TC02`，应先确认：
  - `3001` 宿主已加载新构建（不是旧 dist）
  - 宿主页面写请求走的是同域 `3001/api/*`
- 执行步骤必须严格按 UAT 主脚本：
  - 先 `测试连接`
  - 页面出现 `连接成功 / 在线 / 连接就绪`
  - 再 `保存`
- 若业务预期是切源后 Dashboard 直接恢复可用，还需要继续执行：
  - `同步通道`
  - 再补宿主通道选择 / 绑定闭环
  - 否则当前源码只会到 `no_enabled_channels`，不会到业务 `ready`
