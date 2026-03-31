# HANDOFF — 2026-03-26 00:23 UTC

> 本文档由 PM agent 在 Codex session context 耗尽时生成，供新 session 接续使用。

## 2026-03-31 更新

- 下面的大段内容已经不是最新状态，优先看：
  - `docs/session_handoff.md`
  - `docs/progress.md`
  - `docs/HARDCODED_INVENTORY.md`
  - `docs/FRONTEND_BACKEND_SEPARATION_AUDIT.md`
- 当前最新判断：
  - `origin/codex/hardcode-remediation` 是 docs-only 审计分支，不是代码修复分支
  - 当前真正阻塞 UAT 的硬编码/边界问题已经补到可验证状态
  - 当前下一步应进入完整 UAT，而不是继续围绕旧来源快照做调查
- 当前本地与公网状态：
  - 本地最新提交：`a38efd7 feat: consolidate host runtime source truth`
  - 该版本已经重新部署到公网
  - `/edc/` 当前资源目录：`assets-github-20260331T064047Z`
  - `runtime-status` 当前为 `ready`
  - 当前真源：`http://61.216.55.133`
  - 当前监听进程：
    - `127.0.0.1:8001` -> `uvicorn` PID `2475247`
    - `*:3001` -> `node server.mjs` PID `2475602`
    - 当前未发现 `8000` 监听实例
- 当前明确未完事项：
  - 需要基于公网最新版本做完整 UAT
  - 需要决定 4 个临时文件是否纳入版本库或删除
  - 本轮没有 push 远端仓库
- 当前已验证通过：
  - `apps/server` 定向 pytest：`75 passed`
  - `apps/web`：`pnpm build` 通过
  - 宿主：`node --import tsx --test src/hostConnectivityState.test.ts src/hostApiServer.test.ts` -> `13 passed`
  - 宿主：`npm run build` 通过

## 当前系统状态

| 服务 | 端口 | PID | 状态 |
|------|------|-----|------|
| ASNS 后端（uvicorn，edc-electricity-server） | 8001 | 2475247 | ✅ 运行中 |
| ASNS 后端（uvicorn，旧实例） | 8000 | — | ✅ 当前未监听 |
| ASNS 宿主前端（node server.mjs） | 3001 | 2475602 | ✅ 运行中 |
| EDC 前端（nginx /edc/） | 443 | — | ✅ 运行中 |
| ASNS 界面（nginx /asns/） | 443 | — | ✅ 运行中（base path 已修复）|
| 真实 EDC 数据源 | 外部 | — | ⚠️ 当前真源为 `http://61.216.55.133` |

## 已完成工作（当前应以 `a38efd7` 为准）

- `a38efd7` — feat: consolidate host runtime source truth
- 已完成来源真源收口、宿主旧快照清理、角色绑定拆层、runtime 发布模型统一
- 已完成本地提交并重新部署到公网
- 已完成定向验证：
  - `apps/server` 定向 pytest `75 passed`
  - `apps/web` 构建通过
  - 宿主测试 `13 passed`
  - 公网 `runtime-status=ready`

## 未完成工作（新 session 需要继续）

1. **完整 UAT 总验**：基于当前公网版本执行完整 UAT，重点做视觉确认、截图回看、业务链路留证
2. **形成最终放行结论**：把当前公网版本的 UAT 结果整理进正式验收总账
3. **处理 4 个临时文件**：决定 `asns_settings_html.txt`、`asns_settings_text.txt`、`asns_settings_text_final.txt`、`uat_s01_s02.sh` 是纳入版本库还是删除
4. **决定是否 push 远端仓库**：当前只有本地 commit `a38efd7`，本轮没有推远端
5. **后续结构治理（非当前 UAT 阻塞）**：继续评估 `tasks / heats / baselines` 从 `runtime_*` 快照迁到正式业务表的路径

## 已知问题和注意事项

- **架构认知**：当前 ASNS 后端负责对接外部 EDC 来源；这台机器上不是直接托管 `8080` 服务
- **PM agent 不直接改代码**：所有代码修改必须通过 Codex 执行
- **pytest 工作目录**：后端 pytest 需要在 `apps/server` 或对应 runtime 目录内执行，避免相对 SQLite 路径跑偏
- **ASNS 构建必须设置 base path**：`VITE_ASNS_BASE_PATH=/asns/ npm run build`
- **部署后必须核对资源指纹**：不能只看 `health`，还要检查公网 HTML 引用的 JS/CSS 是否已切到本次发布目录

## 关键文件路径

- 主项目仓：`/home/openclaw/projects/EDC-electricity`
- ASNS 后端运行副本：`/home/openclaw/edc-electricity-server`
- ASNS 宿主源码：`/home/openclaw/projects/EDC-electricity/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`
- EDC 前端源码：`/home/openclaw/projects/EDC-electricity/apps/web`
- ASNS 后端源码：`/home/openclaw/projects/EDC-electricity/apps/server`
- progress 文档：`/home/openclaw/projects/EDC-electricity/docs/progress.md`
- ui_issues 文档：`/home/openclaw/projects/EDC-electricity/docs/ui_issues.md`
- venv pytest：`/home/openclaw/edc-electricity-server/venv/bin/pytest`
- systemd services：`~/.config/systemd/user/edc-backend.service`、`~/.config/systemd/user/asns-host.service`
