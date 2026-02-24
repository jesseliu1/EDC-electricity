# 项目进度跟踪 (Progress)

> 每次会话开始时读取此文件，完成功能后立即更新

---

## 当前状态

**当前阶段**: MVP 完成（待联调整体验收）

**当前步骤**: 联调与验收

**进度**: 100%

---

## 已完成

### 2026-02-23（基线向导调整）

- [x] 基线向导改为 3 步（选炉次+选点 / 参数设置 / 确认发布）
- [x] Step1 使用全天完整曲线并支持选点微调与全屏同步

### 2026-02-11（联调推进）

- [x] 黄金基线定义模块落地
  - [x] 新增黄金基线定义后端 API 与前端页面
  - [x] 新增定义级指标管理（名称/单位/颜色）
- [x] 黄金基线实例模型升级
  - [x] 实例关联定义（definition_id）
  - [x] 新增动态曲线结构（curves_data），保留旧字段兼容
  - [x] 新建基线向导支持“基线定义”选择
- [x] 炉次多黄金基线对比
  - [x] 对比接口支持返回多基线结果数组
  - [x] 炉次详情页支持 Tab 切换多基线对比
- [x] 炉次切割与重大事故演示能力
  - [x] 新增切割设置（时间容忍率、重大事故阈值、班次/休息）
  - [x] 新增 mock 实时流入接口
  - [x] 炉次列表/详情展示切割状态与时间偏移
  - [x] 手动编辑炉次时间并可选择自动调整后续炉次
  - [x] Demo 两组数据：时间偏移可控+数值偏差、重大事故后阻断
- [x] 联调性能优化（前端）
  - [x] vite manualChunks 分包（vue/elementPlus/echarts）
  - [x] 移除全量 Element Plus 图标全局注册
  - [x] 产物验证：分包生效，构建通过
- [x] 前端类型系统收敛
  - [x] API client 统一返回数据类型（消除 AxiosResponse 级联类型问题）
  - [x] 修复 baseline/heat/task/report 等模块 TS 类型错误
  - [x] 验证通过：`vue-tsc --noEmit`、`pnpm build`
- [x] 基线创建交互补全（图上选点）
  - [x] 向导支持图上点击选择起止点
  - [x] 支持秒级时间微调（±1s）
  - [x] 支持图表全屏选点
  - [x] 提交时携带选点起止时间到基线实例创建接口
- [x] 炉次切割恢复闭环补全
  - [x] 新增恢复切割接口 `POST /api/heats/{id}/resume-cutting`
  - [x] 炉次详情新增“恢复切割”操作并支持是否联动后续炉次
  - [x] 炉次列表新增重大事故/阻断提示信息

### 2026-02-12（连续迭代轮次）

- [x] 第1轮：后端切割判定增强
  - [x] 增加连续不一致分钟字段与切割原因字段
  - [x] 增加班次标签（作业/休息/班次外）
  - [x] 按切割配置阈值触发重大事故并锁定后续炉次
- [x] 第2轮：前端炉次切割可视化增强
  - [x] 炉次列表展示班次标签、连续不一致分钟、切割原因
  - [x] 炉次详情展示切割原因与班次窗口信息
  - [x] 四语种文案补齐
- [x] 第3轮：炉次详情到基线创建连贯性增强
  - [x] 炉次详情图上选择基线起止点
  - [x] 一键带着选区跳转到基线向导并自动预填
  - [x] 基线向导支持预填炉次、预填选区、预填实例名
- [x] 第4轮：切割可解释性增强
  - [x] 新增切割时间轴接口 `GET /api/heats/{id}/cutting-timeline`
  - [x] 切割状态新增连续不一致分钟/班次标签/切割原因字段
  - [x] 炉次详情展示切割判定时间轴
- [x] 第5轮：切割流程可操作增强
  - [x] 新增 mock 实时流入接口 `POST /api/heats/stream/mock/ingest`
  - [x] 炉次列表增加“模拟流入一炉”触发入口
  - [x] 设置页新增“基线等长校验范围”配置（定义/系统/生产线预留）

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
- [x] Step 3.2 炉次详情页
  - [x] 炉次基本信息
  - [x] 曲线对比图（与黄金基线叠加）
  - [x] 异常区间红色高亮
  - [x] 偏差分析结果展示
  - [x] 生成纠偏任务入口
- [x] Step 3.3 偏差分析服务
  - [x] 实现曲线对齐算法
  - [x] 实现偏差计算逻辑
  - [x] 实现异常区间识别
  - [x] 单元测试（3项通过）
- [x] Step 3.4 炉次 API
  - [x] GET /api/heats
  - [x] GET /api/heats/{id}
  - [x] GET /api/heats/{id}/curve
  - [x] GET /api/heats/{id}/compare
  - [x] POST /api/heats/{id}/analyze
- [x] Step 3.5 Mock 数据完善
  - [x] 生成模拟炉次数据（正常/异常/待分析）
  - [x] 生成模拟曲线数据
  - [x] API 测试覆盖（heats API + deviation service）
- [x] Step 4.1 任务列表页
  - [x] 任务列表
  - [x] 状态筛选（待处理/处理中/已完成/已取消）
  - [x] 分页
- [x] Step 4.2 任务详情页
  - [x] 关联炉次信息
  - [x] 偏差信息展示
  - [x] 原因分析/改善方法/预防对策表单
  - [x] 保存与完成提交流程
- [x] Step 4.3 任务 PDF 导出
  - [x] 后端任务 PDF 导出接口可下载
  - [x] 前端导出入口
- [x] Step 4.4 任务 API
  - [x] GET /api/tasks
  - [x] GET /api/tasks/{id}
  - [x] POST /api/tasks
  - [x] PATCH /api/tasks/{id}
  - [x] POST /api/tasks/{id}/complete
- [x] Step 4.5 日报系统
  - [x] 日报列表页
  - [x] 日报详情页
  - [x] 日报 PDF 导出接口与前端入口
  - [x] GET /api/reports/daily
  - [x] GET /api/reports/daily/{date}
  - [x] GET /api/reports/daily/{date}/pdf
- [x] Step 4.6 系统设置
  - [x] 设置页面
  - [x] 容许误差设置
  - [x] EDC 连接配置（含测试连接）
  - [x] 报表生成时间设置
  - [x] GET /api/settings
  - [x] PATCH /api/settings
- [x] Step 4.7 偏差收件箱（简化版）
  - [x] 偏差收件箱列表页
  - [x] 查看偏差详情（跳转炉次详情）
- [x] Step 1.5 Dashboard API 前后端联调验证
  - [x] /api/dashboard/stats
  - [x] /api/dashboard/realtime
  - [x] /api/dashboard/recent-heats

---

## 进行中

- [ ] 联调整体验收（跨页面走查）
- [ ] 生产线维度等长校验（当前为定义维度）
- [ ] 切割在线引擎进一步增强（真实数据接入后的持续判定参数自学习）

---

## 待开始

- 无（MVP 功能开发已完成）

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
