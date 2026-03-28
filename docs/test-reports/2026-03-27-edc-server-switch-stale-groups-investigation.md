# 2026-03-27 切换 EDC 服务器后组信息未清空 + 进入智慧熔炉提示数据没有取到

## 结论

- 当前 issue 已查实，不是单点现象，而是一条前后端串起来的根因链。
- 当前公网运行态已经处在“新 EDC 服务器配置 + 旧宿主通道残留”的坏状态。
- 宿主侧的问题是：切换 EDC 服务器后，旧组信息没有被清空；旧通道仍留在宿主已添加通道清单里。
- 业务侧的问题是：智慧熔炉使用当前新 EDC 配置取数，但宿主通道仍是旧服务器的通道 ID，导致实时取数失败，页面显示“未获取到真实实时数据，请检查宿主连接和通道绑定”。

## 复现路径

1. 进入 ASNS 宿主页
2. 打开宿主连线设置
3. 查看“已添加通道清单”
4. 再进入智慧熔炉 `EDC electricity`
5. 查看总览页实时曲线和仪表盘 warning

## 预期行为

- 切换到新 EDC 服务器后，宿主层应清空或重建与旧服务器不兼容的组信息 / 通道信息。
- “已添加通道清单”应只保留当前服务器有效的通道。
- 进入智慧熔炉后，应基于当前服务器的有效宿主通道正常取数；如果当前服务器确实没有对应通道，也应显示与当前服务器一致的空态或绑定态，而不是沿用旧服务器残留状态。

## 当前行为

- 当前公网后端运行态显示：
  - `edc_base_url = http://61.216.55.133`
  - `host_channel_total = 6`
- 但宿主已添加通道清单仍是旧服务器通道：
  - `2349-199`
  - `2349-128`
  - `2054-128`
  - `2066-128`
  - `769-128`
  - `769-129`
- 当前新 EDC 服务器只返回 3 台设备，设备 ID 为：
  - `2752`
  - `2755`
  - `300000000000000000001`
- 智慧熔炉首页当前实际显示：
  - `部分仪表盘数据暂未成功返回`
  - `未获取到真实实时数据，请检查宿主连接和通道绑定`
  - `实时曲线当前不可用`

## investigate 查到的具体原因

### 1. 宿主前端默认从旧快照启动，切换服务器后不会自动清空

文件：

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:51`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:59`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:60`

现象：

- `channelCatalog` 初始值直接来自 `edcChannelSnapshot`
- `addedChannelIds` 初始值直接来自旧快照默认选择

结果：

- 即使已经切到新服务器，宿主设置页仍会先带着旧服务器的组信息和通道信息启动

### 2. “测试连接”只更新连接状态，不刷新通道目录

文件：

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:278`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:295`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:316`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx:333`

现象：

- `handleConnect()` 会调用 `/host-api/edc/test-connection`
- 但它不会替换 `channelCatalog`
- 真正会刷新目录的是 `handleSyncChannels()`

结果：

- 切换新服务器后，如果只做连接测试而没有同步通道，旧组信息会继续残留

### 3. 宿主 bootstrap 会把旧快照重新推给后端

文件：

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx:724`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx:742`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx:747`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx:757`

现象：

- 宿主启动时会从 `edcChannelSnapshot` 恢复 `restoredChannelIds`
- 然后直接执行 `syncSelectionToBackend(restored.config, selectedChannels, connectionState)`

结果：

- 旧快照通道会在启动时再次被同步到后端

### 4. 后端更新 EDC 连接配置时没有清空宿主已添加通道

文件：

- `apps/server/src/api/settings.py:468`
- `apps/server/src/api/settings.py:475`
- `apps/server/src/api/settings.py:515`
- `apps/server/src/api/settings.py:526`

现象：

- `PUT /settings/host-channels` 会清空并重写 `_HOST_CHANNEL_STORE`
- `PUT /settings/edc-connection` 只清空 `_HOST_CHANNEL_CATALOG_CACHE`
- `PUT /settings/edc-connection` 不会清空 `_HOST_CHANNEL_STORE`

结果：

- 新服务器配置写入后，旧服务器的宿主通道仍可能继续保留在运行态

### 5. 为什么进入智慧熔炉后会提示“数据没有取到”

实证：

- 当前公网 `runtime-status` 已是新服务器 `http://61.216.55.133`
- 当前公网 `host-channels` 仍是旧服务器通道 ID
- 当前公网 `dashboard/realtime?duration=1h` 返回 `503`
  - `{"detail":"未获取到真实实时数据，请检查宿主连接和通道绑定"}`

推断链：

- 智慧熔炉按当前新 EDC 连接配置请求上游
- 但它解析和映射使用的宿主通道仍指向旧服务器的 `suid/cuid`
- 这些通道 ID 在当前新服务器上不存在
- 因此实时数据链路无法取到有效数据，最终页面显示“未获取到真实实时数据”

## 正式 UAT 与留存产物

- 测试脚本：
  - `apps/web/e2e/asns-edc-host-switch-investigation.spec.ts`
- 截图目录：
  - `docs/test-reports/assets/2026-03-27-edc-server-switch-stale-groups/public`
- 结构化证据：
  - `docs/test-reports/assets/2026-03-27-edc-server-switch-stale-groups/evidence.json`
- 截图回看：
  - `docs/test-reports/assets/2026-03-27-edc-server-switch-stale-groups/screenshot-review.json`

## 这次回看动作是怎么做的

- 不是只检查截图文件存在。
- 对 6 张正式截图逐张打开 PNG 本身回看。
- 在第一次回看时，发现 `03-settings-old-groups-still-visible.png` 没有真正滚到旧组区域，因此先修正脚本、重跑，再重新回看全部截图。
- 这说明本次“回看”不是形式动作，而是能发现证据缺口并要求重新取证的正式步骤。

## 为什么确认这次回看是成功且正确的

- 截图本身可见宿主首页、连线设置窗口、旧组残留、智慧熔炉壳层、智慧熔炉错误态。
- 回看结论与 `evidence.json` 中的接口证据一致：
  - 新服务器：`61.216.55.133`
  - 旧宿主通道：`2349 / 2054 / 2066 / 769`
  - 当前服务器设备：`2752 / 2755 / 300000000000000000001`
  - 仪表盘错误：`未获取到真实实时数据，请检查宿主连接和通道绑定`
- `screenshot-review.json` 已逐张写明“看到了什么 / 没看到什么”

## PASS / FAIL 判断

- 调查脚本执行：`PASS`
  - 含义：问题已被稳定复现并成功留证
- 当前产品行为：`FAIL`
  - 原因：切换 EDC 服务器后旧组信息未清空，智慧熔炉实际仍处于无数据错误态

## 当前状态

- 根因链已查清
- 复现路径已形成正式 UAT 证据
- 截图与回看已闭环
- 当前阶段仍为 investigate，尚未开始修复
