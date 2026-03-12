# 编码规范（始终生效）

本项目技术栈：Vue 3 + Element Plus + ECharts（前端）、FastAPI + SQLAlchemy（后端）、SQLite（数据库）。

## 通用规则
- 使用**中文注释**，**英文变量名**
- 所有文件使用 UTF-8 编码
- 禁止使用 `any` 类型（TypeScript）
- 禁止使用 `# type: ignore`（Python）

## 前端规范
- Vue 组件使用 **Composition API** + `<script setup lang="ts">`
- 样式使用 **Element Plus** 组件 + **Tailwind CSS** 原子类
- 组件文件名使用 **PascalCase**：`DashboardCard.vue`
- **禁止内联样式**（始终使用 Tailwind 或 Element Plus）
- 使用 **TypeScript** 进行类型约束
- 状态管理使用 **Pinia**，路由使用 **Vue Router**
- HTTP 请求使用 **axios**
- 图表使用 **ECharts** + **vue-echarts**

## 后端规范
- 使用 **async/await** 异步编程
- API 路由使用 **RESTful** 风格
- 使用 **Pydantic** 进行数据验证（请求/响应模型）
- 数据库操作使用 **SQLAlchemy**（async session）
- 数据库迁移使用 **Alembic**

## 格式化工具
- Python：**ruff**（linting + formatting）
- Vue/TypeScript/CSS：**prettier**

## 包管理
- 前端：**pnpm**（禁止 npm/yarn）
- 后端：**uv**（禁止 pip）

## 新增依赖
- 只使用 `docs/TECH_STACK.md` 中已批准的包
- 新增依赖必须说明原因，并经用户批准后方可添加
