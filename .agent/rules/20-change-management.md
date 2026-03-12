# 变更管理（始终生效）

## 计划先行
- 超过 3 个文件的改动：必须先产出 **Implementation Plan**（使用 Planning mode）
- 每个任务必须包含**验收方式**（命令、截图、或录屏 Artifact）
- 不确定的需求标记为"未指定"，并给出默认值与可选项

## 文档优先
- 功能范围确认 → 读 `docs/PRD.md`
- 页面流程设计 → 读 `docs/APP_FLOW.md`
- 技术选型问题 → 读 `docs/TECH_STACK.md`
- 前端样式实现 → 读 `docs/FRONTEND_GUIDELINES.md`
- 后端架构设计 → 读 `docs/BACKEND_STRUCTURE.md`
- 开发顺序确认 → 读 `docs/IMPLEMENTATION_PLAN.md`
- UI 实现参考 → 读 `material/UI/stitch_dashboard/` 对应目录的设计稿

## 禁止操作
1. **不要添加未批准的依赖** — 只使用 TECH_STACK.md 中列出的包
2. **不要超出 PRD 范围** — 只构建 PRD.md 中定义的功能
3. **不要跳过开发步骤** — 严格按照 IMPLEMENTATION_PLAN.md 顺序
4. **不要忽略 UI 原型** — 参考 material/UI/ 目录下的设计稿
5. **不要随意修改数据库结构** — 必须先更新 BACKEND_STRUCTURE.md
