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
- 当前已验证通过：
  - `apps/server` 定向 pytest：`75 passed`
  - `apps/web`：`pnpm build` 通过
  - 宿主：`node --import tsx --test src/hostConnectivityState.test.ts src/hostApiServer.test.ts` -> `13 passed`
  - 宿主：`npm run build` 通过

## 当前系统状态

| 服务 | 端口 | PID | 状态 |
|------|------|-----|------|
| ASNS 后端（uvicorn，edc-electricity-server） | 8001 | 2145878 | ✅ 运行中 |
| ASNS 后端（uvicorn，旧实例） | 8000 | 2129768 | ✅ 运行中 |
| ASNS 宿主前端（node server.mjs） | 3001 | 2159066 | ✅ 运行中 |
| EDC 前端（nginx /edc/） | 443 | — | ✅ 运行中 |
| ASNS 界面（nginx /asns/） | 443 | — | ✅ 运行中（base path 已修复）|
| 真实 EDC 硬件设备 | 8080 | — | ❌ 未接入（外部依赖）|

## 已完成工作（本轮 commits）

- `1cee4f3` — fix: 补 /api/health 别名路由，联通测试5/5全通
- `591ad97` — 第四十四批集成冒烟测试留痕（Playwright 7/7全通）
- `efdfb6f` — docs: 架构认知纠偏，ASNS负责连接8080真实硬件设备
- `c4923d3` — fix: ASNS 重新构建设置 base path /asns/，页面资源路径修复

## 未完成工作（新 session 需要继续）

1. **验证 ASNS 界面功能**：打开 https://hopeofthepantheon.me/asns/，确认页面正常加载，连接入口可操作
2. **ASNS 宿主前端确保使用 systemd 管理**：当前 PID 2159066 是手动启动的，需确认 asns-host.service 是否正确管理
3. **清理 8000 端口旧 uvicorn 实例**：PID 2129768 是多余的，只需保留 8001
4. **确保 ASNS_EDC_BASE_URL 环境变量配置**：等真实设备 IP 就位后配置并重启 ASNS 后端
5. **真实数据联调**：在 ASNS 界面填入真实 EDC 设备地址和账密，验证端到端数据流
6. **最终 UAT 验收报告**：整理所有测试结果，给出是否可上线结论

## 已知问题和注意事项

- **架构认知**：ASNS（apps/server）负责连接 8080 真实硬件设备，8080 不是我们的服务
- **PM agent 不直接改代码**：所有代码修改必须通过 Codex 执行
- **pytest 串行跑**：`-p no:randomly`，必须在 `/home/openclaw/edc-electricity-server` 目录执行
- **ASNS 构建必须设置 base path**：`VITE_ASNS_BASE_PATH=/asns/ npm run build`
- **ASNS 宿主启动环境变量**：`ASNS_BASE_PATH=/ PORT=3001 node server.mjs`

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
