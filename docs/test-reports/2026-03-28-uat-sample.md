# 2026-03-28 UAT 样品

## 样品说明

- **目的**: 提供一份最小可审阅的 UAT 留档样品，确认后再按同一格式全面展开
- **环境**:
  - 宿主 ASNS: `http://127.0.0.1:3001/`
  - EDC 前端: `http://127.0.0.1:3001/edc/`
  - EDC 后端: `http://127.0.0.1:8000/health`
- **执行方式**:
  - 浏览器人工可复核
  - Playwright 样品脚本辅助留图
- **样品范围**:
  - `UAT-SAMPLE-001 Dashboard 导航到炉次浏览`

## UAT-SAMPLE-001 Dashboard 导航到炉次浏览

- **模块**: Dashboard / 炉次浏览
- **业务目标**: 用户可以从系统首页通过左侧导航进入炉次浏览页面
- **前置条件**:
  - 本地宿主、前端、后端均已启动
  - 浏览器可访问 `http://127.0.0.1:3001/edc/`
- **执行脚本**: [uat-sample.spec.ts](</D:/project/EDC electricity/apps/web/e2e/uat-sample.spec.ts>)

| 步骤 | 操作 | 预期结果 | 实际结果 | 截图证据 | 步骤结论 |
|---|---|---|---|---|---|
| 1 | 打开 `http://127.0.0.1:3001/edc/` | 页面进入 Dashboard，总览标题可见，左侧存在“炉次浏览”导航项 | 页面成功进入 Dashboard；顶部显示“总览”，左侧导航存在“炉次浏览”入口 | [uat-sample-001-step-01-dashboard-entry.png](</D:/project/EDC electricity/docs/test-reports/assets/2026-03-28-uat-sample/uat-sample-001-step-01-dashboard-entry.png>) | 通过 |
| 2 | 点击左侧导航“炉次浏览” | 页面跳转到 `/edc/heats`，标题显示“炉次浏览”，并出现筛选区与导出按钮 | 页面成功跳转到 `http://127.0.0.1:3001/edc/heats`；顶部标题显示“炉次浏览 / Heat Browser”，筛选区与“导出 Excel”按钮可见；本次执行截图中列表区为空态“当前暂无炉次数据” | [uat-sample-001-step-02-click-heat-browser.png](</D:/project/EDC electricity/docs/test-reports/assets/2026-03-28-uat-sample/uat-sample-001-step-02-click-heat-browser.png>) | 通过 |

## 截图预览

### 步骤 1 截图

![步骤 1 截图](</D:/project/EDC electricity/docs/test-reports/assets/2026-03-28-uat-sample/uat-sample-001-step-01-dashboard-entry.png>)

### 步骤 2 截图

![步骤 2 截图](</D:/project/EDC electricity/docs/test-reports/assets/2026-03-28-uat-sample/uat-sample-001-step-02-click-heat-browser.png>)

## 执行结论

- **当前状态**: 已执行完成
- **脚本执行命令**: `pnpm --dir apps/web exec playwright test e2e/uat-sample.spec.ts --project=chromium`
- **脚本执行结果**: `1 passed`
- **截图回看结果**:
  - 第 1 张截图已确认显示 Dashboard 首页，和步骤 1 实际结果一致
  - 第 2 张截图已确认显示炉次浏览页、筛选区、导出按钮和空态区域，和步骤 2 实际结果一致
- **样品结论**: 这份样品已经满足“步骤、预期、实际、截图、结论写在同一文件”和“点击后截图并回看 PNG”的规则，可作为全面展开前的评审样板
