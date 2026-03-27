# 2026-03-26 Heat Compare UAT

## 结论

- **结论**: PASS
- **验收口径**: 视觉闭环验收
- **环境**: `http://127.0.0.1:3001/edc/`

## 目标对象

- **heat id**: `live-heat-0ef1bbda-1774525500000-30`
- **页面 URL**: `http://127.0.0.1:3001/edc/heats/live-heat-0ef1bbda-1774525500000-30`
- **涉及 baseline id**:
  - `baseline-3c06ba5d-185b-48b3-a40d-9e4ace627851` (`test1`)
  - `baseline-4674a3e3-3d3d-4237-b2e0-ea2b2cc1a388` (`UAT发布闭环-1774523955793`)
  - `baseline-7be8ab5d-1e22-47f5-8b56-413b8a9f8971` (`legacy source baseline`)
  - `baseline-001` (`标准基线 v2.1`)
- **本轮选中 baseline id**: `baseline-3c06ba5d-185b-48b3-a40d-9e4ace627851`
- **本轮选中 baseline 名称**: `test1`

## 数据摘要

### Compare API 各 series 点数摘要

- `总有功功率`: baseline `359` 点，current `1471` 点
- `A相电压`: baseline `360` 点，current `1471` 点

### 前端最终喂给图表的 series 点数摘要

- `总有功功率-黄金基线`: `359` 点
- `总有功功率-当前生产`: `1471` 点
- `A相电压-黄金基线`: `360` 点
- `A相电压-当前生产`: `1471` 点

### 最终视觉判断

- **用户肉眼是否能看到有效折线**: 能
- **可见性说明**: 最终截图中可肉眼看到至少一条当前曲线和一条 baseline 曲线；图表非空白，曲线位于红框标注区域内。

## Checkpoints

### Checkpoint 01

- **操作步骤**: 打开 `炉次浏览` 列表，定位目标 `heat-row-live-heat-0ef1bbda-1774525500000-30`
- **预期结果**: 目标炉次在列表中可见，可作为后续详情页验收入口
- **实际结果**: 目标炉次行存在并已用红框标注
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-heat-compare/cp01-heat-list-entry.png`

### Checkpoint 02

- **操作步骤**: 打开目标炉次详情页，检查 source banner、baseline tab、图表区域
- **预期结果**: 页面成功进入详情页；source banner、活动 baseline tab 与图表区域均可见
- **实际结果**: 详情页成功加载；source banner、活动 baseline tab `test1`、图表区域已全部用红框标注
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-heat-compare/cp02-heat-detail-overview.png`

### Checkpoint 03

- **操作步骤**: 读取 compare API 点数、读取前端最终 chart runtime series 摘要，并截取图表区域
- **预期结果**:
  - compare API 至少一条当前曲线和一条 baseline 曲线有有效点
  - 前端最终 chart 入参 series 保留有效点
  - 最终截图里肉眼可见当前曲线和 baseline 曲线
- **实际结果**:
  - compare API 返回 `总有功功率 359/1471`、`A相电压 360/1471`
  - 前端 runtime series 共 `4` 条，点数分别为 `359 / 1471 / 360 / 1471`
  - 图表截图中可肉眼看到 baseline 与 current 折线，legend 区域已用红框标注
- **结论**: PASS
- **对应截图路径**: `docs/test-reports/assets/2026-03-26-heat-compare/cp03-heat-compare-visual.png`

## 证据文件

- **截图目录**: `docs/test-reports/assets/2026-03-26-heat-compare/`
- **结构化证据**: `docs/test-reports/assets/2026-03-26-heat-compare/heat-compare-evidence.json`

