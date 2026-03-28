# 2026-03-27 EDC 切源重置 UAT

## 结论

- 当前 issue 判定：`PASS`
- 判定范围：`切换 EDC 后台源后，旧组信息、旧通道绑定、旧激活基线与旧前台展示是否被正确清空，并进入“待重新采集”状态`

## 查到的具体原因

- ASNS 宿主此前会从本地 draft / snapshot 恢复旧来源的已选通道，切源后仍把旧服务器的通道清单重新写回后端运行态。
- 宿主“测试连接”之前只更新连线状态，不会按新来源重建通道目录，导致旧组信息继续留在 UI 与后端绑定里。
- 后端 `PUT /settings/edc-connection` 之前不会清空 `_HOST_CHANNEL_STORE`、通道目录缓存、连线状态与基线通道映射，导致“新服务器地址 + 旧服务器通道 ID”并存。
- 基线接口与 dashboard 之前还会把“最近发布的基线”隐式当作当前有效基线，即使 `active_baseline_id` 已被清空，也会让前台继续看起来像还有一条有效旧基线。

## 为什么会导致“组信息未清空 / 智慧熔炉取不到数据”

- 组信息未清空：
  - 因为宿主本地草稿、宿主 bootstrap 恢复逻辑和后端运行态都继续持有旧服务器的通道 ID，所以切源后 UI 仍展示旧组与旧通道。
- 智慧熔炉取不到数据：
  - 切源后前端与后端看到的是新 EDC 地址，但宿主仍绑定旧服务器的 suid/cuid。新服务器上不存在这些通道，实时数据链路自然拉不到数据。
- 前台旧数据未清空：
  - 即使 `active_baseline_id` 被清空，接口还会回退到最近发布基线，导致总览页看起来仍像保留了旧配置，掩盖了“当前应重新配置”的真实状态。

## 修复与发布

- 后端已改为：切源时清空宿主通道存储、通道目录缓存、最近同步状态、连接态、活动基线与基线 metric 的 `edc_channel_id`。
- ASNS 宿主已改为：按来源身份隔离本地 draft / snapshot；切源时清空旧 `addedChannels` 与目录，不再把旧来源选择回写后端。
- EDC 前端已改为：没有活动基线时显示“待重新配置”，不再把旧发布基线冒充成当前有效态。
- 本轮验证期间发现一个独立部署回归：
  - `https://hopeofthepantheon.me/asns/` 一度白屏，原因不是 React 崩溃，而是 ASNS 构建产物错误引用了根路径 `/assets/...`，导致 `/asns/` 子路径下 JS/CSS 404。
  - 现已用 `/asns/` base 重新构建，当前公网 HTML 已改为 `/asns/assets/...`，资源请求返回 `200`。

## 正式 UAT

- 正式测试脚本：
  - `apps/web/e2e/asns-edc-source-switch-reset-uat.spec.ts`
- 截图目录：
  - `docs/test-reports/assets/2026-03-27-edc-source-switch-reset-uat/public`
- 结构化证据：
  - `docs/test-reports/assets/2026-03-27-edc-source-switch-reset-uat/evidence.json`
- 截图回看：
  - `docs/test-reports/assets/2026-03-27-edc-source-switch-reset-uat/screenshot-review.json`
- 执行命令：
  - `pnpm --dir apps/web exec playwright test e2e/asns-edc-source-switch-reset-uat.spec.ts --project=chromium --workers=1`
- 执行结果：
  - `1 passed`

## 回看结论

- 第 3 张图现在已明确拍到“目前还没有加入任何硬件通道。”，并且未看到旧组 `SSTW 380V-220V電力 · 三相智能电表`。
- 第 6 张图明确拍到“宿主尚未同步真实连接状态”与“待重新配置”，说明旧前台状态已清空，系统进入等待重新采集的保护态。
- 这次回看不是只看文件存在；在首次重跑后，我发现第 3 张目标空态仍未进视口，于是补上 `scrollIntoViewIfNeeded + toBeInViewport` 后再次重跑，才把它计为合格证据。

## 当前运行态核对

- `https://hopeofthepantheon.me/asns/`：`200`
- `https://hopeofthepantheon.me/asns/assets/index-DDc7IN4a.js`：`200`
- `https://hopeofthepantheon.me/edc/`：`200`
- `http://127.0.0.1:8001/health`：`200 {"status":"ok"}`
- `http://127.0.0.1:8001/api/health`：`200 {"status":"ok"}`
- `https://hopeofthepantheon.me/api/settings/runtime-status`：
  - `overall_code = host_disconnected`
  - `host_channel_total = 0`
  - `active_baseline = null`
- `https://hopeofthepantheon.me/api/settings/host-channels`：
  - `total = 0`
- `https://hopeofthepantheon.me/api/dashboard/realtime?duration=1h`：
  - 当前仍为 `503`
  - 结论：这在“切源后已清空旧绑定、尚未重新绑定新源通道”阶段是符合当前保护逻辑的结果，不是旧问题复发。

## 风险与后续动作

- 当前 `PASS` 只覆盖“切源后必须清空旧配置 / 旧展示 / 旧绑定并进入待重采集状态”。
- 若要恢复真实实时数据，还需要按新 EDC 来源重新完成宿主通道绑定，再触发新的采集链路。
- `/api/health` 当前返回 `200`，因此它不是部署缺陷；现态下健康检查路由本身工作正常。
