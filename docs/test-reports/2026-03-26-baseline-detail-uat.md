# 2026-03-26 Baseline Detail UAT

## 结论

- **结论**: PASS
- **验收口径**: 视觉闭环验收
- **环境**: `http://127.0.0.1:3001/edc/`

## 目标对象

- **baseline id**: `baseline-4674a3e3-3d3d-4237-b2e0-ea2b2cc1a388`
- **baseline 名称**: `UAT发布闭环-1774523955793`
- **页面 URL**: `http://127.0.0.1:3001/edc/baselines/baseline-4674a3e3-3d3d-4237-b2e0-ea2b2cc1a388`

## 数据摘要

### API / 数据源点数摘要

- `GET /api/baselines/baseline-4674a3e3-3d3d-4237-b2e0-ea2b2cc1a388` 返回 `200`
- `curve_source=live_edc`
- `总有功功率`: `350` 点
- `A相电压`: `350` 点

### 前端最终喂给图表的 series 点数摘要

- `总有功功率 (kW)`: `350` 点
- `A相电压 (V)`: `350` 点

### 最终视觉判断

- **用户肉眼是否能看到有效折线**: 能
- **可见性说明**: 最终截图中可肉眼看到两条有效折线，图表非空白，曲线位于红框标注区域内。

## Checkpoints

### Checkpoint 01

- **操作步骤**: 打开目标 baseline detail 页面，检查标题、来源信息与图表区域
- **预期结果**: 页面可正常打开，来源信息与图表区域可见
- **实际结果**: 目标 baseline detail 页面成功打开，页面主体和图表区域已完成截图留痕
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-baseline-detail/baseline-detail-overview.png`

### Checkpoint 02

- **操作步骤**: 读取 baseline detail API 点数、读取前端最终 chart runtime series 摘要，并截取图表区域
- **预期结果**:
  - baseline detail API 返回有效曲线点
  - 前端最终 chart 入参 series 保留有效点
  - 最终截图中可肉眼看到有效折线
- **实际结果**:
  - API 返回 `总有功功率 350` 点、`A相电压 350` 点
  - 前端 runtime series 为 `350 / 350`
  - 图表截图中可肉眼看到有效折线
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-baseline-detail/baseline-detail-chart.png`

## 证据文件

- **截图目录**: `docs/test-reports/assets/2026-03-26-baseline-detail/`
- **结构化证据**: `docs/test-reports/assets/2026-03-26-baseline-detail/baseline-detail-evidence.json`
