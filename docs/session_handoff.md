# 会话交接 (Session Handoff)

> 用于在新 session 中快速恢复上下文。开始新会话时，优先阅读本文件，再按需展开 `progress.md / lessons.md / ui_issues.md`。

---

## 当前状态

- 当前阶段：MVP 完成，进入联调整体验收与真实 EDC 替换收口阶段
- 主分支状态：`master` 比 `origin/master` 超前 `12` 个提交
- 当前工作区：仅保留 2 个未跟踪参考文件
- 未纳入版本控制的参考文件：
  - `docs/Ref/EDC AI通信基座API使用說明書.docx`
  - `docs/Ref/install_asns_server-m-1.sh`

---

## 已确认决策

### 宿主层 / 应用层边界

- ASNS 宿主层负责：
  - 后台连接
  - 通道同步
  - 通道清单整理与保存
- `EDC electricity` 应用层负责：
  - 从宿主已保存通道中选择来源
  - 给应用内指标命名、绑定、消费
- 不再强行引入“平台标准点位”作为第一版前置模型
- 当前第一版采用：
  - 宿主层：直接维护“已添加通道清单”
  - 应用层：引用宿主通道并允许应用内重命名

### 真实 EDC 替换范围

- 已优先切到真实 EDC 的链路：
  - Dashboard 实时曲线
  - 炉次详情对比
  - 手动调整图
  - 基线详情
  - 基线向导 preview
  - 炉次基础曲线与列表展开预览
- 仍保留 demo/mock 的部分：
  - 炉次对象本身的生成与切割源数据
  - 任务/报表等非本轮重点模块
  - 真实 EDC 读取失败时的回退逻辑

### 当前服务入口

- 宿主框架：`http://127.0.0.1:3001/`
- 智慧熔炉前端：`http://127.0.0.1:3000/edc/`
- 后端健康检查：`http://127.0.0.1:8000/health`

---

## 最近关键提交

- `3dbfd86` `fix(host): sync selected channels into app backend`
- `3e3e735` `feat(heat): lazy load live heat previews`
- `9dc42f9` `feat(heat): hydrate live heat curves in base flow`
- `0e94e0b` `feat(baseline): drive wizard preview from backend`
- `add1129` `feat(baseline): hydrate baseline curves from live edc`
- `a062007` `feat(server): bind dashboard and heats to live edc history`
- `ea34e94` `feat(dashboard): surface host channel sources in realtime view`
- `1ad5aa1` `feat(heat): surface host channel sources in compare flow`
- `8336102` `feat(baseline): surface host channel bindings in flow`
- `e20ac6d` `feat(baseline): tighten host channel binding flow`
- `a413402` `feat(baseline): bind metrics to host channels`
- `bc58b31` `feat(host): add asns connectivity milestone`

---

## 当前待办

### 待修改 issue（已记录，尚未开始改）

1. 新建基线 Step 2 候选炉次默认只显示 `6` 个，其余内部滚动
2. 向导底部左侧 `取消` 改成 `上一页`
3. 基线向导选点图横轴时间粒度改成按分钟显示
4. 炉次浏览移除 `模拟流入一炉` 按钮及对应功能入口
5. 炉次详情应显示新建黄金基线的 tab，并支持切换
6. 炉次详情移除 `指标来源` 模块
7. 新增“默认黄金基线”，炉次浏览偏离度统一按默认基线计算
8. 炉次浏览展开区方向已确认：
   - 左：功率微缩曲线
   - 中：温度微缩曲线
   - 右：关键摘要卡
9. ASNS 宿主框架相关功能入口补齐多语言匹配

### 当前最可能的实现顺序

1. 先做低风险 UI 收口：
   - issue 1 / 2 / 3 / 4 / 6 / 9
2. 再做炉次详情联动：
   - issue 5
3. 最后做带业务口径的新功能：
   - issue 7（默认黄金基线）
   - 同步调整展开区展示逻辑（issue 8）

---

## 关键文件

### 前端

- `apps/web/src/components/baseline/BaselineWizard.vue`
- `apps/web/src/views/HeatListView.vue`
- `apps/web/src/views/HeatDetailView.vue`
- `apps/web/src/views/BaselineDefinitionListView.vue`
- `apps/web/src/components/baseline/BaselineCard.vue`
- `apps/web/src/stores/baseline.ts`
- `apps/web/src/stores/heat.ts`
- `apps/web/src/api/baseline.ts`
- `apps/web/src/api/heat.ts`
- `apps/web/src/locales/zh-CN.json`

### 后端

- `apps/server/src/api/heats.py`
- `apps/server/src/api/baselines.py`
- `apps/server/src/api/baseline_definitions.py`
- `apps/server/src/api/settings.py`
- `apps/server/src/services/edc_client.py`
- `apps/server/src/schemas/baseline.py`

### 宿主框架

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`

### 过程文档

- `docs/progress.md`
- `docs/lessons.md`
- `docs/ui_issues.md`
- `docs/ASNS_INTEGRATION_PLAN.md`
- `docs/ASNS_HOST_CONNECTIVITY_REDESIGN.md`

---

## 启动与验证

### 常用启动

- 智慧熔炉前端：`pnpm --dir apps/web dev --host 127.0.0.1 --port 3000`
- 后端：`apps/server/.venv/Scripts/python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload`
- 宿主框架：在 `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統` 下运行 `npm run dev`

### 常用验证

- 前端 lint：`pnpm --dir apps/web lint`
- 前端 build：`pnpm --dir apps/web build`
- 前端 E2E：`pnpm --dir apps/web exec playwright test e2e/app.spec.ts`
- 后端 ruff：`apps/server/.venv/Scripts/ruff.exe check src tests`
- 后端 pytest：`apps/server/.venv/Scripts/pytest.exe tests/test_baselines_dashboard_api.py tests/test_heats_api.py`

---

## 新 session 建议开场

1. 先读：
   - `docs/session_handoff.md`
   - `docs/progress.md`
   - `docs/lessons.md`
2. 确认当前目标：
   - 先按已记录 issue 收口 UI/交互
3. 开工前先看：
   - `git status --short --branch`
   - `git log --oneline -12`
