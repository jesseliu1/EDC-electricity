# 2026-03-27 视觉闭环截图复核

## 背景

用户指出：此前我声称曲线链路“通过”，但当用户实际查看页面时反馈“没有曲线”，因此需要先回到原始视觉闭环证据，直接核查当时沉淀的截图文件本身，而不是继续停留在 API / runtime series / DOM 级判断。

本轮目标不是先修代码，而是先回答一个更基础的问题：

1. 当时的“视觉闭环”到底有没有留下截图？
2. 留下的截图里到底有没有曲线？
3. 如果截图里有曲线，为什么我之前没有把这个流程断点识别出来？

## 复核对象

### Heat compare 视觉验收

- `docs/test-reports/assets/2026-03-26-heat-compare/heat-compare-evidence.json`
- `docs/test-reports/assets/2026-03-26-heat-compare/cp03-heat-compare-visual.png`

### Dashboard / Settings smoke

- `docs/test-reports/assets/2026-03-26-dashboard-settings-smoke/dashboard-settings-smoke-evidence.json`
- `docs/test-reports/assets/2026-03-26-dashboard-settings-smoke/local-dashboard.png`
- `docs/test-reports/assets/2026-03-26-dashboard-settings-smoke/public-dashboard.png`

### 2026-03-27 发布前稳定性复验

- `docs/test-reports/assets/2026-03-27-release-stability/release-stability-evidence.json`
- `docs/test-reports/assets/2026-03-27-release-stability/local-dashboard-to-detail.png`
- `docs/test-reports/assets/2026-03-27-release-stability/public-dashboard-to-detail.png`

## 复核方法

因为本机没有 `Pillow` / 图像查看器工具链，本轮使用系统自带 `ffmpeg + ffprobe + python3` 对 PNG 做只读像素审计：

1. 读取截图尺寸与证据 JSON 对应关系。
2. 对截图全图或图表主区域做像素采样。
3. 检测与前端曲线主色接近的像素：
   - Dashboard 当前曲线蓝色 `#1152d4`
   - Dashboard 基线橙色 `#f59e0b`
   - Heat compare 主曲线蓝色 `#409eff`
   - Heat compare 第二指标绿色 `#67c23a`
4. 统计这些像素的数量与包围盒跨度。

判定原则：

- 如果只是按钮、图标、标签文字，颜色包围盒通常只会落在很小的局部。
- 如果是图表折线，颜色像素会沿图表主区域横向展开，包围盒宽度会明显拉长。

## 结果

### 1. Heat compare 的原始视觉截图里有曲线

`cp03-heat-compare-visual.png` 为 `814 x 320` 的图表截图。像素审计结果：

- `compare_blue` 命中 `9730` 像素
- 包围盒为 `(58,5)-(615,186)`，跨度 `558 x 182`

这说明截图里存在一条明显横向展开的蓝色曲线带，不是只有图表容器，没有数据线。

补充：该证据 JSON 同时记录了 runtime series 点数：

- `总有功功率-黄金基线`: `359`
- `总有功功率-当前生产`: `1471`
- `A相电压-黄金基线`: `360`
- `A相电压-当前生产`: `1471`

也就是说，这一组 heat compare 证据在“接口点数 / 前端 runtime series / 截图内容”三个层面是相互一致的。

### 2. 2026-03-27 稳定性复验里的详情截图里也有曲线

对 `local-dashboard-to-detail.png`、`public-dashboard-to-detail.png` 的图表主区域裁剪后审计：

- `local-dashboard-to-detail.png`
  - `compare_blue` 命中 `8819` 像素
  - 包围盒跨度 `789 x 333`
- `public-dashboard-to-detail.png`
  - `compare_blue` 命中 `8840` 像素
  - 包围盒跨度 `789 x 333`

这说明发布前稳定性复验里，从 Dashboard 点击最近炉次进入详情的截图，也确实抓到了实际曲线，不是空白图。

### 3. Dashboard smoke 的首页截图里也存在曲线颜色带

对 `local-dashboard.png` 与 `public-dashboard.png` 的实时曲线主区域裁剪后审计：

- `dashboard_blue` 命中 `2945` 像素
- `dashboard_orange` 命中 `1281` 像素
- 颜色包围盒横向跨度分别达到 `930` 与 `871` 像素量级

这说明 Dashboard 实时曲线卡片的留档截图里，同样不是“只有卡片框，没有线”。

## 结论

### 结论 A：之前的留痕截图本身并不缺

本轮复核后可以确认：

- `heat compare` 的视觉闭环截图里有曲线。
- `dashboard -> detail` 的稳定性复验截图里有曲线。
- `dashboard` 首页 smoke 截图里也有曲线。

所以，“我之前说通过”并不是因为根本没有截图，而是因为我没有把“截图内容已回看”这一步单独执行并写清楚。

### 结论 B：真正的流程断点在于，我把“截图存在”误当成了“截图已被复核”

此前结论依赖了三类证据：

1. API 返回 `200`
2. `data-runtime-series-summary` / point count 非空
3. 截图文件已生成

但这里缺少一个必须的动作：

- 重新打开 PNG 本身，确认“人眼可见折线”是否成立，并把这个判断明确写入验收结论。

也就是说，问题不在“当时完全没有视觉证据”，而在“我没有强制自己完成最后一步视觉证据复核”。

### 结论 C：这次流程闭环只能回答“我为什么没发现流程问题”，还不能直接解释用户当前看到的‘没有曲线’

因为当前复核显示：历史留档截图里确实有曲线，所以用户这次看到“没有曲线”，至少存在以下一种额外差异：

- 用户打开的不是当时留档的同一页面 / 同一路由 / 同一时间点
- 用户命中了不同构建产物、缓存或宿主嵌入上下文
- 用户遇到的是后续运行态变化，而不是当时留档那一刻的页面状态

这意味着：

- “视觉验收流程有断点”已经确认
- “用户现在为什么看不到曲线”仍需要继续查真实场景差异

## 本轮对后续调查的约束

后续再做曲线类验收或排障，必须把以下四件事绑在一起，缺一不可：

1. 接口原始点数
2. 前端 runtime series 点数
3. 对应截图路径
4. 截图内容已回看的明确结论

只有 1-4 全部成立，才允许写“曲线视觉闭环通过”。
