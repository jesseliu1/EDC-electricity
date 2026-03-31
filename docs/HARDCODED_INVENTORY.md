# 项目硬编码盘点清单

> 复核时间：2026-03-31
> 复核范围：`apps/server/src`、`apps/web/src`、`apps/web/vite.config.ts`、`docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`
> 说明：本文件基于 `origin/codex/hardcode-remediation` 的盘点结果重新按当前代码状态复核，不直接沿用旧时点结论。

## 结论摘要

当前最危险、会把旧来源或旧运行态重新带回生产路径的硬编码，已经收口：

- ASNS 宿主生产 bundle 不再内置旧 EDC 来源快照参与默认启动
- EDC 业务前端不再保留系统连接写入口，也不再用本地 `edcBaseUrl` 兜底展示
- 后端、EDC 前端、宿主参考工程的关键运行地址已改为环境可配置
- 任务单已补运行态持久化，不再是纯内存易失状态

当前仍存在的硬编码，大多属于两类：

- 产品默认值，例如默认容差、日报时间、切割参数
- demo / seeded 数据，例如基线、炉次、任务示例数据

这两类仍需要后续结构治理，但已不再是本轮 UAT 的主要阻塞项。

## 本轮已修复的关键硬编码

### 1. 宿主旧来源快照已从生产路径剥离

- 已删除：
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/edcChannelSnapshot.ts`
- 已收口为后端真源优先：
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`
- 当前宿主启动口径：
  - 先读后端 `GET /api/settings/host-bootstrap`
  - 只在 `sourceIdentity + baseSourceRevision` 一致时恢复本地草稿
  - 草稿不一致时直接清空，不再把旧源自动写回后端

### 2. EDC 业务前端已移除系统连接写入口残留

- 已删除前端 API 写入口：
  - `apps/web/src/api/setting.ts`
  - `updateEdc`
  - `testEdc`
- 已删除前端 store 中的系统连接残留字段：
  - `apps/web/src/stores/setting.ts`
  - `edcBaseUrl`
  - `edcApiKey`
- 已删除设置页本地旧值兜底：
  - `apps/web/src/views/SettingsView.vue`

### 3. 关键运行地址改为环境可配置

- 后端：
  - `apps/server/src/config.py`
  - `DEFAULT_EDC_BASE_URL` 已改为空字符串，避免把 `localhost:8080` 当成新部署默认真源
  - 新增 `cors_allowed_origins`
- 后端 CORS：
  - `apps/server/src/main.py`
  - 改为读取 `settings.cors_allowed_origin_list`
- EDC 前端构建：
  - `apps/web/vite.config.ts`
  - 支持 `VITE_EDC_BASE_PATH`
  - 支持 `VITE_EDC_DEV_PORT`
  - 支持 `VITE_EDC_API_TARGET`
- 宿主参考工程：
  - `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs`
  - 支持 `PORT` / `ASNS_PORT`
  - 支持 `ASNS_EDC_API_BASE`
  - 支持 `ASNS_EDC_API_PROTOCOL` / `ASNS_EDC_API_HOST` / `ASNS_EDC_API_PORT`

### 4. 任务单不再是纯内存硬编码运行态

- 已补持久化：
  - `apps/server/src/api/tasks.py`
  - `apps/server/src/runtime_state.py`
- 当前新增运行态键：
  - `runtime_tasks`
- 已补回归：
  - `apps/server/tests/test_tasks_reports_settings_api.py::test_tasks_persist_across_runtime_reload`

## 当前仍保留、但不作为本轮阻塞项的硬编码

### 1. 系统默认参数

以下内容仍是代码内默认值，但它们表达的是系统默认策略，不是旧来源污染：

- `apps/server/src/api/settings.py`
  - 默认容差
  - 默认报表时间
  - 默认切割参数
  - 默认作息时间
- `apps/web/src/stores/setting.ts`
  - 与后端对应的默认 UI 回填值

后续如果要继续治理，方向应是“默认值配置集中化”，不是简单删字面量。

### 2. Demo / seeded 数据

以下文件仍保留示例数据：

- `apps/server/src/api/baseline_definitions.py`
- `apps/server/src/api/baselines.py`
- `apps/server/src/api/heats.py`
- `apps/server/src/api/tasks.py`

这些数据当前主要承担本地演示、测试初始化、showtime/mock 支撑。它们不是“旧来源快照”问题，但长期仍建议与正式业务落库进一步拆开。

### 3. 固定协议常量

以下常量仍是固定字符串或枚举值：

- `apps/server/src/request_mode.py`
- `apps/web/src/utils/showtime.ts`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

这类更接近协议常量，不属于本轮“污染运行态”的硬编码。

## 对 UAT 的影响判断

当前与 UAT 直接相关的高风险硬编码已关闭：

- 不再把旧测试源快照打进宿主生产启动路径
- 不再让 EDC 业务前端误导性地保留系统连接写面
- 不再让新服务器默认带着 `localhost:8080` 作为真源
- 不再让任务单因服务重启直接丢失

当前剩余项主要是结构债，不阻塞本轮按现状进入 UAT。
