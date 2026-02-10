# 项目进度跟踪 (Progress)

> 每次会话开始时读取此文件，完成功能后立即更新

---

## 当前状态

**当前阶段**: Phase 3 - 炉次浏览 + 偏差分析

**当前步骤**: Step 3.2 炉次详情页

**进度**: 82%

---

## 已完成

### 2026-02-09

- [x] 创建项目目录结构
- [x] 创建 AGENTS.md 主配置文件
- [x] 创建 opencode.json 配置
- [x] 创建规范文档体系
  - [x] PRD.md - 产品需求文档
  - [x] TECH_STACK.md - 技术栈文档
  - [x] APP_FLOW.md - 应用流程文档
  - [x] FRONTEND_GUIDELINES.md - 前端规范
  - [x] BACKEND_STRUCTURE.md - 后端结构
  - [x] IMPLEMENTATION_PLAN.md - 实施计划
  - [x] progress.md - 进度跟踪（本文件）
  - [x] lessons.md - 经验教训
- [x] Step 1.1 项目初始化
  - [x] 安装 pnpm 包管理器 (v10.29.2)
  - [x] 创建前端项目 (Vue 3.5 + Vite 7 + TypeScript 5.9)
  - [x] 配置 Tailwind CSS 3.4 + Element Plus 2.13
  - [x] 配置 vue-i18n 11.2 (zh-CN/en-US/zh-TW/ja-JP)
  - [x] 配置 ESLint 9 + Prettier 3.8
  - [x] 创建后端项目 (FastAPI 0.114 + SQLAlchemy 2.0)
  - [x] 配置 Ruff 0.15 (Python linter/formatter)
  - [x] 配置 Python 3.11.13 虚拟环境 (uv)
  - [x] 初始化 Git 仓库
  - [x] 创建路由配置和视图占位文件
  - [x] 前端构建验证通过
- [x] Step 1.2 基础布局
  - [x] 更新 tailwind.config.js 添加设计令牌（颜色、间距、阴影）
  - [x] 创建 AppSidebar.vue（可折叠导航菜单，7个导航项）
  - [x] 创建 AppHeader.vue（页面标题、系统状态、搜索、通知）
  - [x] 创建 PageContainer.vue（页面内容容器）
  - [x] 创建 AppLayout.vue（主布局组件，响应式支持）
  - [x] 更新 App.vue 使用 AppLayout
  - [x] 前端构建验证通过
- [x] Step 1.3 后端基础
  - [x] 配置数据库连接（SQLite）
  - [x] 创建基础模型（Baseline, Heat, Task, Setting）
  - [x] 配置 Alembic 迁移
  - [x] 创建 API 路由框架
  - [x] 实现健康检查接口
- [x] Step 1.4 Dashboard 页面
  - [x] 创建统计卡片组件 (StatCard)
  - [x] 实现 Mock 数据服务
  - [x] 创建实时曲线图组件 (RealtimeChart)
  - [x] 实现时间范围选择（5分钟/1小时/6小时/全天）
  - [x] 创建最近炉次列表组件
- [x] Step 2.1 基线列表页
  - [x] 创建基线卡片组件 (BaselineCard)
  - [x] 实现基线列表页面
  - [x] 实现状态筛选（草稿/已发布/已停用）
  - [x] 前端基线 API 模块与 Store（含 Mock 回退）
- [x] Step 2.2 新建基线向导
  - [x] 创建向导组件框架 (BaselineWizard)
  - [x] Step 1: 候选炉次选择（日期范围、炉次选择、曲线预览）
  - [x] Step 2: 预览对比（基线与当前曲线、统计信息）
  - [x] Step 3: 设置参数（名称、容许误差、描述）
  - [x] Step 4: 发布确认（保存草稿/发布）
- [x] Step 2.3 基线详情页
  - [x] 基线信息展示
  - [x] 曲线图展示
  - [x] 版本历史
  - [x] 编辑/停用/创建新版本操作
- [x] Step 2.4 基线 API
  - [x] GET /api/baselines
  - [x] GET /api/baselines/{id}
  - [x] POST /api/baselines
  - [x] PATCH /api/baselines/{id}
  - [x] POST /api/baselines/{id}/publish
  - [x] POST /api/baselines/{id}/disable
  - [x] DELETE /api/baselines/{id}
- [x] Step 3.1 炉次列表页
  - [x] 创建炉次列表组件
  - [x] 实现日期范围筛选
  - [x] 实现偏差状态筛选（正常/异常/待分析）
  - [x] 实现分页

---

## 进行中

- [ ] Step 3.2 炉次详情页

---

## 待开始

- Step 1.5 Dashboard API 前后端联调验证

---

## 已知问题

- `material/UI/` 参考画面风格不统一，后续实现需统一视觉风格
- 前端构建包体积较大 (1.2MB)，后续需要配置代码分割
- ESLint 仍有多项 Vue 样式类警告（不阻断构建）

---

## 笔记

- MVP 先使用 Mock 数据，后续对接 EDC API
- 单台 EDC 设备，架构预留多台扩展能力
- 模块化设计，支持按插件销售
