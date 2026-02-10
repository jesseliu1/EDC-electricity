# 实施计划 (IMPLEMENTATION_PLAN)

## 总体时间线

| 阶段 | 时间 | 目标 |
|------|------|------|
| Phase 1 | Week 1-2 | 项目基础 + Dashboard |
| Phase 2 | Week 3-4 | 基线管理 |
| Phase 3 | Week 5-6 | 炉次浏览 + 偏差分析 |
| Phase 4 | Week 7-8 | 纠偏任务 + 日报 |

---

## Phase 1: 项目基础 + Dashboard (Week 1-2)

### Step 1.1 项目初始化 ⬜
- [ ] 创建前端项目 (Vue 3 + Vite + TypeScript)
- [ ] 创建后端项目 (FastAPI + SQLAlchemy)
- [ ] 配置 ESLint、Prettier、Ruff
- [ ] 配置 Tailwind CSS + Element Plus
- [ ] 创建 Git 仓库，初始提交

### Step 1.2 基础布局 ⬜
- [ ] 实现 AppLayout 组件（顶部栏 + 侧边栏 + 主内容区）
- [ ] 实现侧边栏导航（可收起）
- [ ] 实现路由配置
- [ ] 实现页面容器组件

### Step 1.3 后端基础 ⬜
- [ ] 配置数据库连接（SQLite）
- [ ] 创建基础模型（Baseline, Heat, Task, Setting）
- [ ] 配置 Alembic 迁移
- [ ] 创建 API 路由框架
- [ ] 实现健康检查接口

### Step 1.4 Dashboard 页面 ⬜
- [ ] 创建统计卡片组件 (StatCard)
- [ ] 实现 Mock 数据服务
- [ ] 创建实时曲线图组件 (RealtimeChart)
- [ ] 实现时间范围选择（5分钟/1小时/6小时/全天）
- [ ] 创建最近炉次列表组件

### Step 1.5 Dashboard API ⬜
- [ ] GET /api/dashboard/stats
- [ ] GET /api/dashboard/realtime
- [ ] GET /api/dashboard/recent-heats
- [ ] 前后端联调

---

## Phase 2: 基线管理 (Week 3-4)

### Step 2.1 基线列表页 ⬜
- [ ] 创建基线卡片组件 (BaselineCard)
- [ ] 实现基线列表页面
- [ ] 实现状态筛选（草稿/已发布/已停用）
- [ ] 实现基线 CRUD API

### Step 2.2 新建基线向导 ⬜
- [ ] 创建向导组件框架 (BaselineWizard)
- [ ] Step 1: 选择候选炉次
  - [ ] 日期选择器
  - [ ] 炉次列表
  - [ ] 曲线预览
- [ ] Step 2: 预览对比
  - [ ] 曲线对比图
  - [ ] 统计信息
- [ ] Step 3: 设置参数
  - [ ] 基线名称输入
  - [ ] 容许误差设置
  - [ ] 描述输入
- [ ] Step 4: 发布确认
  - [ ] 保存草稿
  - [ ] 发布

### Step 2.3 基线详情页 ⬜
- [ ] 基线信息展示
- [ ] 曲线图展示
- [ ] 版本历史
- [ ] 编辑/停用/创建新版本操作

### Step 2.4 基线 API ⬜
- [ ] GET /api/baselines
- [ ] GET /api/baselines/{id}
- [ ] POST /api/baselines
- [ ] PATCH /api/baselines/{id}
- [ ] POST /api/baselines/{id}/publish
- [ ] POST /api/baselines/{id}/disable
- [ ] DELETE /api/baselines/{id}

---

## Phase 3: 炉次浏览 + 偏差分析 (Week 5-6)

### Step 3.1 炉次列表页 ⬜
- [ ] 创建炉次列表组件
- [ ] 实现日期范围筛选
- [ ] 实现偏差状态筛选（正常/异常/待分析）
- [ ] 实现分页

### Step 3.2 炉次详情页 ⬜
- [ ] 炉次基本信息
- [ ] 曲线对比图（与黄金基线叠加）
- [ ] 异常区间红色高亮
- [ ] 偏差分析结果展示
- [ ] 生成纠偏任务入口

### Step 3.3 偏差分析服务 ⬜
- [ ] 实现曲线对齐算法
- [ ] 实现偏差计算逻辑
- [ ] 实现异常区间识别
- [ ] 单元测试

### Step 3.4 炉次 API ⬜
- [ ] GET /api/heats
- [ ] GET /api/heats/{id}
- [ ] GET /api/heats/{id}/curve
- [ ] GET /api/heats/{id}/compare
- [ ] POST /api/heats/{id}/analyze

### Step 3.5 Mock 数据完善 ⬜
- [ ] 生成模拟炉次数据
- [ ] 生成模拟曲线数据
- [ ] 包含正常和异常案例

---

## Phase 4: 纠偏任务 + 日报 (Week 7-8)

### Step 4.1 任务列表页 ⬜
- [ ] 创建任务卡片组件
- [ ] 实现任务列表
- [ ] 实现状态筛选（待处理/处理中/已完成）

### Step 4.2 任务详情页 ⬜
- [ ] 关联炉次信息
- [ ] 偏差曲线对比
- [ ] 原因分析表单
- [ ] 改善方法表单
- [ ] 预防对策表单
- [ ] 保存/提交操作

### Step 4.3 任务 PDF 导出 ⬜
- [ ] 设计 PDF 模板
- [ ] 实现 PDF 生成服务
- [ ] GET /api/tasks/{id}/pdf

### Step 4.4 任务 API ⬜
- [ ] GET /api/tasks
- [ ] GET /api/tasks/{id}
- [ ] POST /api/tasks
- [ ] PATCH /api/tasks/{id}
- [ ] POST /api/tasks/{id}/complete

### Step 4.5 日报系统 ⬜
- [ ] 日报数据聚合服务
- [ ] 日报列表页
- [ ] 日报详情页
- [ ] 日报 PDF 导出
- [ ] GET /api/reports/daily
- [ ] GET /api/reports/daily/{date}
- [ ] GET /api/reports/daily/{date}/pdf

### Step 4.6 系统设置 ⬜
- [ ] 设置页面
- [ ] 容许误差设置
- [ ] EDC 连接配置（预留）
- [ ] 报表生成时间设置
- [ ] GET /api/settings
- [ ] PATCH /api/settings

### Step 4.7 偏差收件箱（简化版） ⬜
- [ ] 偏差收件箱列表页
- [ ] 查看偏差详情（跳转炉次详情）

---

## 完成标准

每个 Step 完成后需要：
1. ✅ 代码通过 lint 检查
2. ✅ 关键功能有测试覆盖
3. ✅ 更新 progress.md
4. ✅ 提交 Git

---

## 风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| EDC API 不可用 | 无法获取真实数据 | 使用 Mock 数据 |
| PDF 生成复杂 | 延期 | 先实现简化版 |
| 曲线数据量大 | 性能问题 | 实现数据降采样 |

---

## 当前状态

**当前步骤**: Step 3.3 偏差分析服务

**下一步**: 炉次 API（Step 3.4）
