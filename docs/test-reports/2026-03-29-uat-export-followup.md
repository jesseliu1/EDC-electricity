# 2026-03-29 本地 UAT 导出复核续跑（S07-TC02 / S07-TC03）

## 测试说明

- **目的**: 正式重跑 `S07-TC02 / S07-TC03`，确认当前修复已形成真实下载闭环
- **环境**:
  - EDC 前端: `http://127.0.0.1:3000/edc/`
  - EDC API: `http://127.0.0.1:8000/api/`
- **主清单编号**: `S07-TC02`、`S07-TC03`
- **执行时间**: `2026-03-29`
- **执行命令**: `pnpm exec playwright test e2e/uat-export-followup.spec.ts --project=chromium`

## 结果总览

| 主清单编号 | 结果 | 说明 |
|---|---|---|
| S07-TC02 | 通过 | 任务详情页触发真实下载事件，文件名校验为 `${task_no}.pdf` |
| S07-TC03 | 通过 | 日报详情页触发真实下载事件，文件名校验为 `daily-{report_date}.pdf` |

## S07-TC02 纠偏任务导出 PDF

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 通过 API 创建测试任务并打开任务详情页 | 任务详情页可正常加载 | 页面成功进入任务详情页，导出按钮可见 | [before-export](/D:/project/EDC%20electricity/docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc02-task-detail-before-export.png) | 通过 |
| 2 | 点击 `导出PDF` | 应触发真实下载事件并返回 PDF | Playwright 捕获到 download event，文件名校验通过 | [after-export](/D:/project/EDC%20electricity/docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc02-task-detail-after-export.png) | 通过 |

### 已核实事实

- 导出请求命中 `GET /api/tasks/{task_id}/pdf`
- 接口返回状态 `200`
- 浏览器触发真实 download event
- 下载文件名校验通过：`${task_no}.pdf`
- 因此 `S07-TC02` 当前正式结果为 `PASS`

## S07-TC03 日报生成与导出

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开日报详情页 | 日报详情页可正常加载 | 页面成功进入日报详情页，导出按钮可见 | [before-export](/D:/project/EDC%20electricity/docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc03-report-detail-before-export.png) | 通过 |
| 2 | 点击 `导出PDF` | 应触发真实下载事件并返回 PDF | Playwright 捕获到 download event，文件名校验通过 | [after-export](/D:/project/EDC%20electricity/docs/test-reports/assets/2026-03-29-uat-export-followup/s07-tc03-report-detail-after-export.png) | 通过 |

### 已核实事实

- 导出请求命中 `GET /api/reports/daily/{report_date}/pdf`
- 接口返回状态 `200`
- 浏览器触发真实 download event
- 下载文件名校验通过：`daily-{report_date}.pdf`
- 因此 `S07-TC03` 当前正式结果为 `PASS`

## 本轮结论

- `S07-TC02` 当前正式结果为 `PASS`
- `S07-TC03` 当前正式结果为 `PASS`
- 当前导出闭环已从“代码修复 + mock 回归通过”推进到“真实本地链路正式重跑通过”
- 仍需后续统一回写总账，因为历史 `26 / 19 / 17 / 2 / 7` 口径与 testcase 粒度存在未收敛项
