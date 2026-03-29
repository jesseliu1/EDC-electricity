# UAT 执行摘要

**执行日期**：2026-03-28  
**执行人**：Codex  
**环境**：local  
**范围**：`S01-TC03 验证后端已接收配置`、`S02-TC02 选择并绑定通道`、`S02-TC03 验证通道绑定写入后端`、`S04-TC01 记录切源前的旧绑定状态`、`S04-TC02 切换到 source B 并验证连接结果`、`S06-TC03 偏差收件箱展示新链路偏差记录`、`S07-TC02 纠偏任务导出 PDF`、`S07-TC03 日报生成与导出`、`S07-TC05 EDC 连接异常时的错误态展示`、`S07-TC06 无基线时 Dashboard 引导展示`  
**总体结论**：FAIL

## 用例结论

| 用例 | 结论 | 备注 |
|------|------|------|
| S01-TC03 | PASS | `edc_base_url=http://60.251.229.32`，`host-connectivity-status.is_connected=true`，`runtime-status.overall_code=ready` |
| S02-TC02 | PASS | 宿主设置页完成整组添加并保存绑定，后续后端写入结果已核实 |
| S02-TC03 | PASS | `host-channels total=7`，`host-connectivity-status.is_connected=true` |
| S04-TC01 | PASS | 已记录切源前宿主绑定通道清单与 Dashboard 状态，`host-channels total=7`，`runtime-status.overall_code=ready` |
| S04-TC02 | FAIL | 基于当前唯一已核实的 source B 口径 `http://61.216.55.133 / admin / admin` 复跑后，保存已写入，但 `host-connectivity-status.is_connected=false`，`runtime-status.overall_code=host_disconnected` |
| S06-TC03 | PASS | 正式复核时页面显示 `5 异常需要处理`，并可从收件箱进入对应炉次详情 |
| S07-TC02 | FAIL | 导出后浏览器仅打开空白 popup，未形成 PDF 下载成功或预览成功证据 |
| S07-TC03 | FAIL | 导出后浏览器仅打开空白 popup，未形成 PDF 下载成功或预览成功证据 |
| S07-TC05 | PASS | 无效地址触发 `host_disconnected`，Dashboard 显示明确异常提示，历史数据页仍可访问；环境已额外恢复 |
| S07-TC06 | PASS | `active_baseline=null` 时 Dashboard 显示 `待重新配置`，快捷入口可跳转到 `/edc/baselines` |

## 已补齐文件

- 测试报告：`docs/test-reports/2026-03-28-uat-followup.md`
- 执行摘要：`docs/test-reports/assets/2026-03-28-uat-followup/uat-summary.md`
- 结构化证据：`docs/test-reports/assets/2026-03-28-uat-followup/evidence.json`
- 截图回看：`docs/test-reports/assets/2026-03-28-uat-followup/screenshot-review.json`
