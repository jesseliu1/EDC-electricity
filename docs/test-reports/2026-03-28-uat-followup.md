# 2026-03-28 本地 UAT 主线续跑（S01 / S02 / S04 / S06 / S07）

## 测试说明

- **目的**: 继续沿 EDC / ASNS UAT 主线正式核实 `S01-TC03 / S02-TC02 / S02-TC03 / S04-TC01 / S04-TC02 / S06-TC03 / S07-TC02 / S07-TC03 / S07-TC05 / S07-TC06`
- **环境**:
  - 宿主 ASNS: `http://127.0.0.1:3001/`
  - EDC 前端: `http://127.0.0.1:3001/edc/`
  - EDC API 代理: `http://127.0.0.1:3001/api/`
  - ASNS 后端: `http://127.0.0.1:8001/api/health`
- **主清单编号**: `S01-TC03`、`S02-TC02`、`S02-TC03`、`S04-TC01`、`S04-TC02`、`S06-TC03`、`S07-TC02`、`S07-TC03`、`S07-TC05`、`S07-TC06`
- **执行时间**: `2026-03-28 19:06 UTC`、`2026-03-28 23:21 UTC`、`2026-03-28 23:47 UTC`、`2026-03-29 02:15 UTC`

## 结果总览

| 主清单编号 | 结果 | 说明 |
|---|---|---|
| S01-TC03 | 通过 | 宿主同步后 `edc_base_url=http://60.251.229.32`，`host-connectivity-status.is_connected=true`，`runtime-status.overall_code=ready` |
| S02-TC02 | 通过 | 宿主设置页完成整组添加并保存绑定，绑定结果已写入当前宿主通道清单 |
| S02-TC03 | 通过 | `GET /api/settings/host-channels` 返回 `total=7`，`GET /api/settings/host-connectivity-status` 返回 `is_connected=true` |
| S04-TC01 | 通过 | 已记录切源前宿主绑定通道列表与 Dashboard 状态，`host-channels total=7`，`runtime-status.overall_code=ready` |
| S04-TC02 | 失败 | 基于当前唯一已核实的 source B 口径 `http://61.216.55.133 / admin / admin` 复跑后，保存已写入，但 `host-connectivity-status.is_connected=false`，`runtime-status.overall_code=host_disconnected` |
| S06-TC03 | 通过 | 正式复核时页面显示 `5 异常需要处理`，列表渲染 `5` 条异常炉次，并可从收件箱进入对应炉次详情 |
| S07-TC02 | 失败 | 导出后浏览器仅打开空白 popup（URL 为 `:`），截图未形成 PDF 预览或下载成功证据 |
| S07-TC03 | 失败 | 导出后浏览器仅打开空白 popup（URL 为 `:`），截图未形成 PDF 预览或下载成功证据 |
| S07-TC05 | 通过 | 无效 EDC 地址已触发 `host_disconnected` 异常态，Dashboard 出现明确提示，历史数据页仍可访问；环境已额外恢复 |
| S07-TC06 | 通过 | `active_baseline=null` 时 Dashboard 显示 `待重新配置`，快捷入口可跳转到 `/edc/baselines` |

## 2026-03-30 正式总账说明补充

- 本报告中的旧 `S04-TC02 FAIL / S07-TC02 FAIL / S07-TC03 FAIL` 结论已被后续正式重跑覆盖：
  - `S04-TC02`：见 `docs/test-reports/2026-03-29-s04-tc02-rerun.md`
  - `S07-TC02 / S07-TC03`：见 `docs/test-reports/2026-03-29-uat-export-followup.md`
- 因此，本文件中的 `已执行 23 / 通过 20 / 失败 3 / 剩余 3` 仅代表 `2026-03-28` 当次续跑时点，不再单独作为当前最终正式总账。
- 自 `2026-03-30` 起，`S04 / S05` 的正式总账说明还必须补记“换源确认”证据：
  - 切源前若存在旧来源状态，是否先出现换源确认弹窗
  - 用户点击的是 `确认` 还是 `取消`
  - 确认后继续进入的是 `测试连接`、`同步通道` 还是 `保存设置`
- 若旧来源状态存在但没有换源确认弹窗证据，则 `S04-TC02` 不得计为正式 `PASS`，`S05` 也不得直接计为正式恢复通过。
- 自 `2026-03-30` 起，`S02 / S03 / S05 / S06` 的正式总账还必须补记“业务角色绑定”证据：
  - `GET /api/settings/channel-role-bindings` 当前记录
  - `GET /api/settings/runtime-status.channel_roles.missing_required_role_keys`
  - `dashboard_primary / live_heat_inference` 是否已经指向当前源通道
- 因此，本文件中 `2026-03-28` 留下的 `host-channels total > 0`、`runtime-status.overall_code=ready` 之类旧证据，只能证明当时宿主通道层已恢复，不能单独作为当前“业务链路 ready”总账依据。

## S01-TC03 验证后端已接收配置

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 在宿主设置页点击 `同步通道` 并等待同步完成 | 保存/同步后可进入后端核对 | 本轮同步后宿主连接状态刷新为在线，截图已留存 | [step-01-sync-after](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s01-tc03-step-01-sync-after.png>) | 通过 |

### 已核实事实

- `GET /api/settings` 当前返回 `edc_base_url=http://60.251.229.32`
- `GET /api/settings/host-connectivity-status` 当前返回：
  - `is_connected=true`
  - `machine_name=EDC Gateway (60.251.229.32)`
  - `last_sync_label=2026/3/28 23:21:31`
- `GET /api/settings/runtime-status` 当前返回：
  - `overall_code=ready`
  - `edc.base_url=http://60.251.229.32`
  - `host.is_connected=true`
- 因此 `S01-TC03` 当前正式结果为 `PASS`

## S02-TC02 选择并绑定通道

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开宿主设置页并记录选择前状态 | 选择前状态可留档 | 已留选择前截图 | [step-01-before-select](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s02-tc02-step-01-before-select.png>) | 通过 |
| 2 | 点击 `整组添加` | 至少 1 组通道被加入绑定清单 | 本轮执行动作为 `add-group` | [step-02-after-select](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s02-tc02-step-02-after-select.png>) | 通过 |
| 3 | 点击 `保存设置` | 绑定操作提交成功 | 保存后截图已留存 | [step-03-save-after](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s02-tc02-step-03-save-after.png>) | 通过 |
| 4 | 回看结果态 | 应可见绑定后的结果态 | 结果态截图已留存；后续 API 已确认绑定写入后端 | [step-04-result-state](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s02-tc02-step-04-result-state.png>) | 通过 |

### 已核实事实

- 本轮宿主设置页实际执行动作为：`add-group`
- 绑定后已继续核对后端 `host-channels` 写入结果
- 因此 `S02-TC02` 当前正式结果为 `PASS`

## S02-TC03 验证通道绑定写入后端

### 已核实事实

- `GET /api/settings/host-channels` 当前返回 `total=7`
- 当前已写入的通道 id 为：
  - `2349-199`
  - `2349-128`
  - `2054-128`
  - `2066-128`
  - `769-128`
  - `769-129`
  - `901-128`
- `GET /api/settings/host-connectivity-status` 当前返回：
  - `is_connected=true`
  - `machine_name=EDC Gateway (60.251.229.32)`
  - `last_sync_label=2026/3/28 23:21:41`
- 补充口径说明：
  - 本次历史记录只覆盖了 `host-channels` 与宿主连接态
  - 本次未记录 `GET /api/settings/channel-role-bindings`
  - 本次未记录 `runtime-status.channel_roles.missing_required_role_keys`
  - 因此它可以证明“宿主通道已写入”，但不能单独证明按 `2026-03-30` 新口径的“业务链路 ready”
- 因此 `S02-TC03` 当前正式结果为 `PASS`

## S04-TC01 记录切源前的旧绑定状态

### 已核实事实

- 宿主设置页已留当前绑定通道截图：
  - [step-01-current-bound-channels](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc01-step-01-current-bound-channels.png>)
- Dashboard 当前状态已留图：
  - [step-02-dashboard-before-switch](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc01-step-02-dashboard-before-switch.png>)
- `GET /api/settings/host-channels` 当前返回 `total=7`
- 当前切源前通道 id 为：
  - `2349-199`
  - `2349-128`
  - `2054-128`
  - `2066-128`
  - `769-128`
  - `769-129`
  - `901-128`
- `GET /api/settings/runtime-status` 当前返回：
  - `overall_code=ready`
  - `edc.base_url=http://60.251.229.32`
  - `host.is_connected=true`
- 因此 `S04-TC01` 当前正式结果为 `PASS`

## S04-TC02 切换到 source B 并验证连接结果

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开宿主设置页并记录当前配置 | 可进入设置页并留当前状态 | 设置页已成功打开并留图 | [step-01-open-settings](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc02-step-01-open-settings.png>) | 通过 |
| 2 | 将 EDC 地址改为 source B：`http://61.216.55.133` | 地址输入成功 | 地址输入成功并留图 | [step-02-fill-new-endpoint](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc02-step-02-fill-new-endpoint.png>) | 通过 |
| 3 | 填入 source B 账户 `admin / admin` | 账户密码输入成功 | 账户密码输入成功并留图 | [step-03-fill-credentials](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc02-step-03-fill-credentials.png>) | 通过 |
| 4 | 点击 `测试连接` | 应出现连接成功或在线证据 | 页面仍显示 `系统状态=离线`、`等待验证`，未出现成功提示 | [step-04-test-connection-result](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc02-step-04-test-connection-result.png>) | 失败 |
| 5 | 点击 `保存设置` 后核对运行态 | 保存后应形成在线连接证据 | 设置已保存，但运行态仍未就绪 | [step-05-save-after](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s04-tc02-step-05-save-after.png>) | 失败 |

### 已核实事实

- 本轮正式复跑执行时间：`2026-03-29 02:15 UTC`
- 本轮唯一已核实的 source B 口径为：
  - `endpoint=http://61.216.55.133`
  - `username=admin`
  - `password=admin`
- 页面 `测试连接` 后正文仍可见：
  - `系统状态 = 离线`
  - `等待验证`
- `GET /api/settings` 保存后返回：
  - `edc_base_url=http://61.216.55.133`
  - `edc_username=admin`
- `GET /api/settings/host-connectivity-status` 保存后返回：
  - `is_connected=false`
  - `machine_name=--`
  - `meta.source=http://61.216.55.133`
- `GET /api/settings/runtime-status` 保存后返回：
  - `overall_code=host_disconnected`
  - `host.is_connected=false`
  - `edc.base_url=http://61.216.55.133`
- 因此 `S04-TC02` 本轮正式结果为 `FAIL`
- 失败原因已核实为：当前唯一已核实的 source B tuple 已成功写入设置，但宿主未建立连接，浏览器侧也未形成“连接测试成功 / 在线 / 连接就绪”证据
- 补充说明：若 source B 口径已变更，则需先更新前置，再重新正式执行本条

## S06-TC03 偏差收件箱展示新链路偏差记录

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开 `http://127.0.0.1:3001/edc/inbox` 并等待异常列表渲染 | 偏差收件箱列表非空，显示异常记录 | 页面顶部显示 `5 异常需要处理`，列表区域渲染 `5` 条异常炉次记录 | [step-01-rerun](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s06-tc03-step-01-inbox-list-rerun.png>) | 通过 |
| 2 | 点击首条异常炉次 | 进入对应炉次详情页 | 页面成功进入对应炉次详情页，正文可见 | [step-02-rerun](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s06-tc03-step-02-open-heat-detail-rerun.png>) | 通过 |

### 交叉核对

- `GET /api/heats?status=abnormal&page=1&page_size=10` 当前返回 `total=5`
- 页面请求 `/api/heats?page=1&page_size=10&status=abnormal` 返回 `200`
- 页面 `Pinia heat store` 当前持有 `5` 条 abnormal rows，`total=5`
- 前 5 条异常炉次为：
  - `H20260328-0216`
  - `H20260328-0108`
  - `H20260327-1247`
  - `H20260326-0108`
  - `H20260326-0000`
- 因此 `S06-TC03` 最终已核实为：当前真实链路可用，旧 `FAIL` 口径来自截图过早，不是产品当前失败

### 截图回看

![S06-TC03 Step 1](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s06-tc03-step-01-inbox-list-rerun.png>)

![S06-TC03 Step 2](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s06-tc03-step-02-open-heat-detail-rerun.png>)

## 本轮结论

- `S06-TC03` 当前正式结果为 `PASS`
- `S01-TC03` 当前正式结果为 `PASS`
- `S02-TC02` 当前正式结果为 `PASS`
- `S02-TC03` 当前正式结果为 `PASS`
- `S04-TC01` 当前正式结果为 `PASS`
- `S04-TC02` 当前正式结果为 `FAIL`
- 旧 `FAIL` 口径已撤销，不再计入当前正式总账或当前未收口 bug
- `S06-TC03` 当前正式结果为 `PASS`
- `S07-TC02` 当前正式结果为 `FAIL`
- `S07-TC03` 当前正式结果为 `FAIL`
- `S07-TC05` 当前正式结果为 `PASS`
- `S07-TC06` 当前正式结果为 `PASS`
- 当前正式总账已更新为：已执行 `23` / 通过 `20` / 失败 `3` / 阻塞 `0` / 剩余 `3`

## S07-TC02 纠偏任务导出 PDF

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开任务详情 `T20260328-162124` | 任务详情页正常显示 | 页面成功进入任务详情页，关联炉次 `H20260328-0216` 可见 | [step-01](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc02-step-01-task-detail.png>) | 通过 |
| 2 | 点击 `导出PDF` | 应触发 PDF 下载或预览 | 点击后浏览器未出现可见 PDF 预览或下载成功反馈 | [step-02](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc02-step-02-after-click-export.png>) | 失败 |
| 3 | 回看导出结果 | 应可见 PDF 下载成功或预览结果 | 截图仍停留在任务详情页；浏览器实际只打开空白 popup，URL 为 `:` | [step-03](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc02-step-03-export-result.png>) | 失败 |

### 已核实事实

- 浏览器点击导出后打开空白 popup，URL 为 `:`
- 本轮浏览器侧未形成 download event
- 先前已核实后端接口 `GET /api/tasks/task-fb7872d0-c86f-4220-8ddf-fba874fcb56e/pdf` 返回 `200`
- 先前已核实响应头：
  - `content-type: application/pdf`
  - `content-disposition: attachment; filename=T20260328-162124.pdf`
- 因此当前失败点已核实为：后端 PDF 端点可达，但浏览器侧未形成 UAT 要求的“下载成功或预览成功”闭环证据

## S07-TC03 日报生成与导出

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开日报列表 | 日报列表正常显示 | 页面显示日报列表入口 | [step-01](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc03-step-01-report-list.png>) | 通过 |
| 2 | 打开当日日报详情 | 日报详情页正常显示 | 页面成功进入 `2026-03-28` 日报详情 | [step-02](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc03-step-02-report-detail-entry.png>) | 通过 |
| 3 | 查看日报预览 | 应可见日报统计内容 | 页面可见 `总炉数 10 / 正常率 80% / 平均偏差 0% / 已完成 0` | [step-03](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc03-step-03-report-preview.png>) | 通过 |
| 4 | 点击 `导出PDF` 并回看结果 | 应可见 PDF 下载成功或预览结果 | 截图仍停留在日报详情页；浏览器实际只打开空白 popup，URL 为 `:` | [step-04](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc03-step-04-export-result.png>) | 失败 |

### 已核实事实

- 浏览器点击导出后打开空白 popup，URL 为 `:`
- 本轮浏览器侧未形成 download event
- 当前失败点已核实为：浏览器侧未形成 UAT 要求的“下载成功或预览成功”闭环证据

## S07-TC05 EDC 连接异常时的错误态展示

### 已核实事实

- 已将宿主 EDC 地址临时改为无效地址：`http://127.0.0.1:65535`
- 已留图：
  - [step-01-invalid-address](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc05-step-01-invalid-address.png>)
  - [step-02-dashboard-error-state](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc05-step-02-dashboard-error-state.png>)
  - [step-03-warning-banner](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc05-step-03-warning-banner.png>)
  - [step-04-history-still-visible](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc05-step-04-history-still-visible.png>)
- `GET /api/settings` 已确认无效地址写入成功：`edc_base_url=http://127.0.0.1:65535`
- `GET /api/settings/runtime-status` 当时返回：
  - `overall_code=host_disconnected`
  - `host.is_connected=false`
  - `edc.host_channel_total=0`
- Dashboard 页面已匹配到以下异常提示：
  - `宿主尚未同步真实连接状态`
  - `部分仪表盘数据暂未成功返回`
  - `实时曲线当前不可用`
  - `当前不是“没有曲线”，而是实时曲线请求失败`
- 历史数据页仍可打开并截图留存
- 已人工回看截图：
  - `s07-tc05-step-01-invalid-address.png` 可见无效地址已写入，系统状态为离线/等待验证
  - `s07-tc05-step-02-dashboard-error-state.png` 可见 Dashboard 异常态提示与实时曲线不可用提示
  - `s07-tc05-step-03-warning-banner.png` 可见顶部双横幅告警
  - `s07-tc05-step-04-history-still-visible.png` 可见炉次浏览页仍可打开
- 本条用例执行后，已额外重跑宿主同步恢复脚本；当前环境已恢复到：
  - `host-connectivity-status.is_connected=true`
  - `runtime-status.overall_code=ready`
- 因此 `S07-TC05` 当前正式结果为 `PASS`

## S07-TC06 无基线时 Dashboard 引导展示

### 已核实事实

- 已留图：
  - [step-01-no-baseline-dashboard](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc06-step-01-no-baseline-dashboard.png>)
  - [step-02-guidance-target](</home/openclaw/projects/EDC-electricity/docs/test-reports/assets/2026-03-28-uat-followup/s07-tc06-step-02-guidance-target.png>)
- `GET /api/settings/runtime-status` 当前返回：
  - `active_baseline.id=null`
  - `overall_code=ready`
- Dashboard 当前可见 `待重新配置`
- Dashboard 快捷入口跳转结果为：`http://127.0.0.1:3001/edc/baselines`
- 已人工回看截图：
  - `s07-tc06-step-01-no-baseline-dashboard.png` 可见基线状态卡 `待重新配置`
  - `s07-tc06-step-02-guidance-target.png` 已进入 `黄金基线库` 页面
- 因此 `S07-TC06` 当前正式结果为 `PASS`
