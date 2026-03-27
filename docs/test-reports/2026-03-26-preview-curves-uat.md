# 2026-03-26 Preview Curves UAT

## 结论

- **结论**: PASS
- **验收口径**: 视觉闭环验收
- **环境**: `http://127.0.0.1:3001/edc/`

## 目标对象

- **definition id**: `def-788f8b8e-2285-47fc-8e15-b47e1e41a493`
- **heat id**: `live-heat-0ef1bbda-1774523100000-30`
- **页面 URL**: `http://127.0.0.1:3001/edc/baselines`

## 数据摘要

### Preview API 各 series 点数摘要

- `GET /api/baseline-definitions/def-788f8b8e-2285-47fc-8e15-b47e1e41a493/preview-curves?heat_id=live-heat-0ef1bbda-1774523100000-30` 返回 `200`
- `rangeStart=2026-03-26T00:00:00`
- `rangeEnd=2026-03-27T00:00:00`
- `总有功功率`: `10074` 点
- `A相电压`: `10074` 点

### 前端最终喂给图表的 series 点数摘要

- `总有功功率`: `10073` 点
- `A相电压`: `10073` 点

### 最终视觉判断

- **用户肉眼是否能看到有效折线**: 能
- **可见性说明**: 最终截图中可肉眼看到有效折线，预览图表非空白，曲线位于红框标注区域内。

## Checkpoints

### Checkpoint 01

- **操作步骤**: 从 `/edc/` 应用内导航进入 `黄金基线库 -> 新建基线`，选择固定 definition 与目标 heat，进入 preview-curves 页面
- **预期结果**: 目标 definition 和 heat 可被稳定选中，预览页成功打开并显示图表区域
- **实际结果**: 已使用真实 `heat id` 精确选中目标候选炉次，向导预览页与图表区域成功加载
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-preview-curves/preview-curves-overview.png`

### Checkpoint 02

- **操作步骤**: 读取 preview-curves API 点数、读取前端最终 chart runtime series 摘要，并截取图表区域
- **预期结果**:
  - preview-curves API 返回有效曲线点
  - 前端最终 chart 入参 series 保留有效点
  - 最终截图中可肉眼看到有效折线
- **实际结果**:
  - API 返回 `总有功功率 10074` 点、`A相电压 10074` 点
  - 前端 runtime series 为 `10073 / 10073`
  - 图表截图中可肉眼看到有效折线
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-preview-curves/preview-curves-chart.png`

## 证据文件

- **截图目录**: `docs/test-reports/assets/2026-03-26-preview-curves/`
- **结构化证据**: `docs/test-reports/assets/2026-03-26-preview-curves/preview-curves-evidence.json`
