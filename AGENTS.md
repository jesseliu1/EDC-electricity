# ASNS AI老师傅智慧熔炼系统

## 项目概述
基于黄金基线的生产偏差监控与纠偏系统，用于中频炉熔炼过程的智能监控。

## 技术栈
- **前端**: Vue 3 + Element Plus + ECharts
- **后端**: FastAPI (Python 3.11.x)
- **数据库**: SQLite (L2层存储)
- **格式化**: ruff (Python), prettier (Vue)
- **包管理**: pnpm (前端), uv (Python)

## 项目结构
```
├── apps/
│   ├── web/              # Vue 前端应用
│   └── server/           # FastAPI 后端服务
├── packages/
│   ├── core/             # 核心模块（必装）
│   ├── plugin-baseline/  # 插件：老师傅系统（黄金基线管理）
│   ├── plugin-report/    # 插件：日报周报系统
│   └── plugin-correction/# 插件：纠偏任务系统
├── docs/                 # 规范文档
└── material/             # 参考资料（UI原型、会议纪要等）
```

## 代码规范

### 通用规则
- 使用中文注释，英文变量名
- 所有文件使用 UTF-8 编码
- 禁止使用 `any` 类型（TypeScript）
- 禁止使用 `# type: ignore`（Python）

### 前端规范
- Vue 组件使用 Composition API + `<script setup>`
- 样式使用 Element Plus + Tailwind CSS
- 组件文件名使用 PascalCase：`DashboardCard.vue`
- 禁止内联样式

### 后端规范
- 使用 async/await 异步编程
- API 路由使用 RESTful 风格
- 使用 Pydantic 进行数据验证
- 数据库操作使用 SQLAlchemy

## 外部文档引用

CRITICAL: 当遇到以下任务时，必须先用 Read 工具读取对应文档：

| 任务类型 | 参考文档 |
|---------|---------|
| 功能范围确认 | @docs/PRD.md |
| 页面流程设计 | @docs/APP_FLOW.md |
| 技术选型问题 | @docs/TECH_STACK.md |
| 前端样式实现 | @docs/FRONTEND_GUIDELINES.md |
| 后端架构设计 | @docs/BACKEND_STRUCTURE.md |
| 开发顺序确认 | @docs/IMPLEMENTATION_PLAN.md |
| 测试策略与验证口径 | @docs/testing.md |
| 正式 UAT 范围与脚本 | @docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md |
| 进度状态查看 | @docs/progress.md |
| 历史经验教训 | @docs/lessons.md |

## 禁止操作

1. **不要添加未批准的依赖** - 只使用 TECH_STACK.md 中列出的包
2. **不要超出 PRD 范围** - 只构建 PRD.md 中定义的功能
3. **不要跳过开发步骤** - 严格按照 IMPLEMENTATION_PLAN.md 顺序
4. **不要忽略 UI 原型** - 参考 material/UI/ 目录下的设计稿
5. **不要使用内联样式** - 始终使用 Tailwind 或 Element Plus
6. **不要随意修改数据库结构** - 必须先更新 BACKEND_STRUCTURE.md

## 会话管理

### 会话开始时
1. 读取 `docs/progress.md` 了解当前进度
2. 读取 `docs/lessons.md` 了解历史经验
3. 确认当前在 IMPLEMENTATION_PLAN.md 的哪个步骤

### 会话结束时
1. 更新 `docs/progress.md` 记录完成的工作
2. 如有新发现的问题模式，更新 `docs/lessons.md`

### 代码修改完成后
1. 按 `docs/testing.md` 的“完整用户路径验证规则”验证本轮改动
2. 不允许只按代码路径验证，必须按真实用户路径验证：入口、操作、请求参数、中间态、成功态、空态、错误态
3. 只要改动影响用户可见流程、页面状态、跨系统联动、图表、提示文案、筛选条件、时间语义或 UAT 结论，就必须检查是否同步更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
4. 如未完成上述验证与文档联动，不得声称“已验证完成”“可开始 UAT”或“已通过 UAT”

### 错误纠正时
当用户纠正你的错误时：
1. 立即停止当前操作
2. 询问："是否需要将这个经验记录到 lessons.md？"
3. 如果是，使用以下格式记录：
```markdown
## [日期] 问题简述
- **错误模式**: 描述导致问题的行为
- **正确做法**: 描述应该如何做
- **适用场景**: 何时应用这个规则
```

## 模块化架构

本系统采用可插拔架构，按模块分层销售：

| 模块 | 说明 | 依赖 |
|------|------|------|
| core | 核心模块（EDC API客户端、数据模型） | 无 |
| plugin-baseline | 老师傅系统（黄金基线管理、偏差比对） | core |
| plugin-report | 日报周报系统（报表生成） | core |
| plugin-correction | 纠偏任务系统（任务单管理） | core, plugin-baseline |

开发时确保模块间解耦，通过接口通信。

## UI 参考

UI 原型位于 `material/UI/stitch_dashboard/` 目录：
- `总览_dashboard/` - 主仪表盘
- `黄金基线库_baseline_library/` - 基线管理
- `炉次浏览_heat_browser_*/` - 炉次详情
- `纠偏任务单_action_orders/` - 任务单
- `日报与审计_report_&_audit_*/` - 报表

每个目录包含 `screen.png`（设计图）和 `code.html`（HTML原型）。
