# 前后台分离现状调查

> 复核时间：2026-03-31
> 说明：本文件基于 `origin/codex/hardcode-remediation` 的调查结果，按当前代码状态重新整理。

## 一句话结论

当前系统已经基本做到：

- EDC 业务前端主要负责展示和操作
- 后端是系统连接与运行态的唯一真源
- 宿主本地草稿已降级为“同源同 revision 的未提交编辑态”

但还没有完全做到：

- `baseline / heat / task` 全部以正式 ORM 业务表作为唯一持久化来源

更准确地说，当前状态是：

> 系统连接真源已经收口到后端，业务数据持久化仍处于“运行态快照落库为主”的过渡阶段。

## 已经收口的部分

### 1. EDC 业务前端已不再写系统连接配置

- `apps/web/src/api/setting.ts`
  - 已移除 `updateEdc`
  - 已移除 `testEdc`
- `apps/web/src/stores/setting.ts`
  - 已移除 `edcBaseUrl`
  - 已移除 `edcApiKey`
- `apps/web/src/views/SettingsView.vue`
  - 系统连接摘要只读后端运行态，不再本地拼接旧值

当前 EDC 业务前端负责的是业务参数读写，不再承担系统连接真源。

### 2. 宿主 source truth 已改为后端优先

- 后端新增：
  - `GET /api/settings/host-bootstrap`
  - `PUT /api/settings/host-runtime-sync`
- 宿主正式写操作统一要求：
  - `source_revision`
- 宿主启动流程已改为：
  - 先读后端当前 source
  - 再判断本地草稿是否仍然有效
  - source 或 revision 不一致时直接清草稿

这意味着宿主本地草稿不再能压过后端当前真源。

### 3. 任务单已补到后端持久化闭环

旧调查里最明显的“前后台没分干净”问题之一，是任务单只在内存 `_TASK_STORE` 里。

当前已修复：

- `apps/server/src/runtime_state.py`
  - 新增 `runtime_tasks`
- `apps/server/src/api/tasks.py`
  - 创建、更新、完成、取消后都会持久化 `tasks`
- `apps/server/tests/test_tasks_reports_settings_api.py`
  - 已覆盖重载后恢复任务

虽然它还不是 ORM 表直写，但已经不再是“服务一重启就丢”的前端/内存态。

### 4. 系统连接与运行环境默认值已更清晰地后端化

- `apps/server/src/config.py`
  - 默认 EDC 地址改为空字符串
  - CORS 改为环境可配
- `apps/web/vite.config.ts`
  - base path、dev port、API target 环境化
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs`
  - 宿主端口与后端代理地址环境化

这部分减少了“前端构建参数就是运行态事实”的混淆。

## 仍未完全收口的部分

### 1. 业务实体仍主要走 runtime JSON 快照

当前后端虽然有业务表模型，但主运行路径仍主要依赖：

- `apps/server/src/runtime_state.py`
- `settings` 表中的 `runtime_*` 键

这表示系统已经从“前端持状态”往后端收，但还没有走到“每类业务实体都有自己正式表和 CRUD 真源”的终点。

### 2. 宿主本地仍保留草稿，但已不是权威状态

宿主前端仍会在浏览器保存本地草稿：

- endpoint
- username
- password
- addedChannelIds
- 最近一次连接摘要

但这份本地数据现在只表示：

- 当前浏览器的未提交编辑态

它不再具备：

- 启动时覆盖后端真源
- 自动回写后端
- 在 source/revision 已变化时继续复活旧配置

所以这里仍有“本地状态”，但已经不再是“双真源”问题。

## 当前判断

### 已成立

- 系统连接真源已收口到后端
- EDC 业务前端基本只读后端统一状态
- 宿主草稿已降为本地临时编辑态
- 任务单已不再是易失内存态

### 尚未成立

- `baseline / heat / task` 还没有全部迁到各自业务表作为正式真源
- `settings` 表仍承担较多运行态快照存储职责

## 对 UAT 的影响

当前这份“前后台未完全分离”的剩余问题，更多是结构演进问题，不是本轮 UAT 的直接阻塞项。

本轮 UAT 前必须关闭的问题，已经关闭：

- 宿主旧草稿压过后端真源
- 宿主旧来源快照参与生产启动
- EDC 前端仍假装可以改系统连接
- 任务单服务重启即丢失

## 后续建议

按优先级建议继续做：

1. 把 `tasks` 从 runtime JSON 进一步迁到正式业务表
2. 把 `heats / baselines` 从 `runtime_*` 快照逐步迁到各自表
3. 把 `settings` 表收缩回真正的系统设置，不再承载大块业务对象快照
4. 若未来要做多端草稿协同，再单独设计“后台草稿”，不要把浏览器本地草稿重新抬成事实真源
