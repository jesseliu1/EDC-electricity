---
name: ui-regression-fix
description: 当用户要求修复本项目的 UI 联调问题、交互回归、页面错位、步骤状态不同步、列表展开、图表选点或前端请求报错噪音时使用。适用于 Vue 3 + Element Plus + Tailwind CSS 页面回归修复与联调整体验收。
---

# UI 联调修复技能

按以下顺序执行：

1. 先读 `docs/progress.md`、`docs/lessons.md`、`docs/FRONTEND_GUIDELINES.md`，确认当前阶段与已知坑。
2. 再读用户给出的缺陷清单或验收文档，按“阻断 > 数据错误 > 交互错误 > 视觉问题”排序。
3. 优先复用现有 store、API 模块和页面结构，不新增依赖，不重做无关页面。
4. 修改前先建立基线：
   - 查看 `git status --short`
   - 运行前端构建或类型检查
   - 必要时读取相关原型 `material/UI/stitch_dashboard/.../code.html`
5. 修复交互问题时遵循：
   - 状态单源化，避免同一份时间值同时维护 `Date` 和时间戳两套状态
   - 图表选区、弹窗、全屏态复用同一组响应式数据
   - 列表展开、弹窗、二级操作按钮必须阻止误触发行跳转
   - 前端存在 mock 回退时，避免全局错误提示刷屏
6. 修改后必须验证：
   - `pnpm --dir apps/web build`
   - `pnpm --dir apps/web test`（如果已有测试）
   - 必要时补充最小可维护测试
7. 会话结束前更新 `docs/progress.md`；若发现新的稳定问题模式，再更新 `docs/lessons.md`。

额外约束：

- 使用中文注释，英文变量名。
- 禁止内联样式；优先 Tailwind，其次少量 scoped 样式。
- 不要为了修一个 UI 问题引入新的状态库、图表库或工具库。
