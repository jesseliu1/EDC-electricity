# 部署说明 (DEPLOYMENT)

> 当前仓库的可用部署入口以本文为准。历史脚本和旧版 DOCX 仅保留作参考，不再作为上线依据。

当前这台服务器的固定模板 / 脚本入口：

- `deploy/systemd/edc-backend.service.example`
- `deploy/systemd/asns-host.service.example`
- `scripts/sync-edc-server.sh`
- `scripts/publish-edc-web-and-asns.sh`
- 服务器路径与同步原则见 `docs/SERVER_LAYOUT_AND_SYNC.md`

本机 Windows 联调入口：

- `scripts/start-local-edc-stack.sh`

补充说明：

- 当前两个发布脚本已内建 `systemctl --user` 的 user bus 环境补齐逻辑
- 在非交互 shell / agent / CI 中执行时，会自动补 `XDG_RUNTIME_DIR=/run/user/$(id -u)` 与 `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus`
- 当前后端部署刷新不只会修 `runtime_host_channels`，还会同步 reconcile `runtime_channel_role_bindings` 与 `runtime_baseline_definitions`
- 如果旧环境里还残留“目录里仍合法、但当前 5 分钟读空”的基波类角色绑定，`deploy-refresh` 会优先替换成当前源下真实可读的 live 通道
- 当前 `python -m src.runtime_state_admin --mode factory-reset` 已升级为“删除目标 SQLite 及其 `-wal/-shm/-journal`，再按当前代码 schema 重建空库”
- 因此 `factory-reset + ASNS_BOOTSTRAP_MODE=blank` 的当前语义已经不是“只清表数据”，而是“删旧库、重建当前 schema、再以 blank 空白运行态启动”
- 只要用户口头要求“公网部署 / 公网重部署”，且没有明确要求保留旧业务数据，默认按上述“彻底删除干净并重建”的口径执行

## 1. 部署范围

本项目当前包含 3 个需要区分的运行单元：

1. `apps/server`
   FastAPI 后端，默认监听 `8000`
2. `apps/web`
   Vue 业务前端，构建后以 `/edc/` 作为访问前缀
3. `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`
   ASNS 宿主“神经系统”参考工程，默认监听 `3001`

当前生产运行目录：

- EDC 后端 runtime：`/home/openclaw/edc-electricity-server`
- ASNS 宿主 runtime：`/home/openclaw/asns-host-runtime`
- EDC 前端发布目录：`/var/www/edc-electricity`

推荐的同机部署访问关系：

- `/` -> 宿主“神经系统” `3001`
- `/edc/` -> EDC 前端静态文件
- `/api/` -> FastAPI `8000`

如果站点根路径还要承载额外门户页，也可以改成：

- `/` -> 门户页
- `/asns/` -> 宿主“神经系统”
- `/edc/` -> EDC 前端静态文件
- `/api/` -> FastAPI `8000`

## 2. 环境要求

- Node.js 20 LTS
- `pnpm` 8+
- Python 3.11 - 3.13

## 3. 后端部署

目录：

- `apps/server`

首次部署 / 手工重建环境：

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install .
```

生产启动：

```bash
.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
```

常用环境变量：

```bash
ASNS_DATABASE_URL=sqlite+aiosqlite:///./data/asns.db
ASNS_EDC_BASE_URL=http://<your-edc-host>:8080
ASNS_EDC_USERNAME=<username>
ASNS_EDC_PASSWORD=<password>
ASNS_BOOTSTRAP_MODE=demo
ASNS_DEBUG=false
```

说明：

- 默认数据库路径是 `apps/server/data/asns.db`
- 如需持久化，部署时请保证 `data/` 目录可写
- `ASNS_BOOTSTRAP_MODE=demo` 是当前默认值
- 如果是新服务器首次部署，且希望启动后就是空白系统，不要写入 demo 基线/炉次/宿主绑定，应显式设置 `ASNS_BOOTSTRAP_MODE=blank`
- 如果目标是 blank 重部署，不要复用旧 `asns.db`；应先执行 `factory-reset`，让脚本删除旧库并按当前代码重建
- 如果目标是“公网 blank 重部署”，推荐先用 `EDC_SERVER_SKIP_START=1` 同步 runtime，避免后端在删库前先带着旧 SQLite 短暂启动一次：

```bash
EDC_SERVER_SKIP_SOURCE_REFRESH=1 EDC_SERVER_SKIP_START=1 ./scripts/sync-edc-server.sh
systemctl --user stop edc-backend.service
/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin \
  --db /home/openclaw/edc-electricity-server/data/asns.db \
  --mode factory-reset
systemctl --user start edc-backend.service
./scripts/publish-edc-web-and-asns.sh
```

- 上述顺序的目标是：先把代码同步到 runtime，但在 SQLite 仍是旧库时不让后端先起来；真正的第一次启动应发生在 `factory-reset` 之后
- 当前仓库部署口径已不再要求保留旧 `venv/`，而是每次同步后从源码重建运行环境
- 当前项目没有额外的 Redis、MQ、对象存储前置要求

## 4. EDC 前端部署

目录：

- `apps/web`

安装与构建：

```bash
pnpm install --frozen-lockfile
pnpm build
```

构建产物：

- `apps/web/dist`

部署要求：

- 需要把 `dist` 发布到 `/edc/` 路径下
- Vite 配置里的 `base` 已固定为 `/edc/`
- 前端开发态通过 Vite 代理把 `/api` 转发到 `http://localhost:8000`
- 生产环境需要由反向代理或网关把 `/api` 转发到后端，不会自动代理

## 5. 宿主“神经系统”部署

目录：

- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`

安装与构建：

```bash
npm install
npm run build
```

源码目录构建：

```bash
npm ci
VITE_ASNS_BASE_PATH=/asns/ \
VITE_ASNS_EDC_APP_URL=/edc/ \
VITE_ASNS_APP_API_BASE=/api \
npm run build
```

运行时发布：

- 部署脚本会把源码目录构建产物发布到 `/home/openclaw/asns-host-runtime`
- 每次发布前会备份 runtime，并清空除 `.logs/` / `backups/` 外的内容
- `node_modules/` 不再保留，统一通过 `npm ci --omit=dev` 重新安装
- systemd 只从 runtime 目录启动 `node server.mjs`

说明：

- 该宿主工程不是纯静态页面
- 当前 `vite.config.ts` 通过 `configureServer` 和 `configurePreviewServer` 提供 `/host-api/edc/test-connection` 与 `/host-api/edc/sync-channels`
- 因此若只拿 `dist/` 丢到纯静态文件服务器，宿主里的 EDC 测试连接与同步通道能力不会工作
- 当前生产入口统一为 `npm start` / `node server.mjs`，负责：
  - 提供宿主静态文件
  - 提供宿主 `host-api`
  - 支持 `/asns/` 这类子路径部署

当前已知限制：

- 若部署到子路径，例如 `/asns/`，构建前需显式设置：

```bash
VITE_ASNS_BASE_PATH=/asns/
VITE_ASNS_EDC_APP_URL=/edc/
VITE_ASNS_APP_API_BASE=/api
```

- 这不是“建议项”，而是后续构建回归必须检查的硬项。
  - 如果 ASNS 要挂在 `/asns/` 子路径下，构建产物里的资源路径必须是 `/asns/assets/...`，不能回退成根路径 `/assets/...`
  - 一旦回退成 `/assets/...`，公网 `https://<host>/asns/` 会出现白屏，因为浏览器会去站点根路径抓 JS/CSS 并收到 `404`
  - 因此每次 ASNS 构建 / 发布后，至少要补做以下回归检查：

```bash
curl -s https://<host>/asns/ | rg '/asns/assets/'
curl -I https://<host>/asns/assets/<entry>.js
```

  - 判定标准：
    - `/asns/` 返回的 HTML 中必须引用 `/asns/assets/...`
    - 对应 JS/CSS 资源必须返回 `200`
  - 当前仓库这一点的已知回归案例：曾因构建产物引用 `/assets/...`，导致 `/asns/` 白屏；后续发布不得跳过这条检查

- 若使用 `npm start` / `node server.mjs`，运行时 `ASNS_BASE_PATH` 取决于反向代理是否剥离前缀：

1. 如果反向代理会把 `/asns/` 剥掉后再转发到 `3001`
   当前这台服务器就是这种模式，应使用：

```bash
ASNS_BASE_PATH=/
PORT=3001
```

2. 如果反向代理保留 `/asns/` 前缀原样转发给 Node
   才应使用：

```bash
ASNS_BASE_PATH=/asns/
PORT=3001
```

- 当前服务器的正式口径以 `docs/SERVER_LAYOUT_AND_SYNC.md` 和 `deploy/systemd/asns-host.service.example` 为准
- 宿主前端现已默认优先走“同域 `/api` + 同域 `/edc/` + 按 base 推导 `host-api`”
- 只有在跨域或特殊网关结构下，才需要额外设置 `VITE_ASNS_HOST_API_BASE`

## 6. 推荐上线顺序

1. 启动后端 `apps/server`
2. 发布 `apps/web/dist` 到 `/edc/`
3. 发布并启动宿主 runtime `3001`
4. 配置反向代理
5. 打开宿主首页，执行一次 EDC 连线测试与通道同步
6. 从宿主进入 EDC 页面，确认 Dashboard、Heats、Baselines 正常

如果是在当前服务器上按既定目录重发，优先执行：

```bash
./scripts/sync-edc-server.sh
./scripts/publish-edc-web-and-asns.sh
```

如果这次是公网 blank 重部署，标准顺序改为：

```bash
./scripts/sync-edc-server.sh
systemctl --user stop edc-backend.service
/home/openclaw/edc-electricity-server/venv/bin/python -m src.runtime_state_admin \
  --db /home/openclaw/edc-electricity-server/data/asns.db \
  --mode factory-reset
systemctl --user start edc-backend.service
./scripts/publish-edc-web-and-asns.sh
```

其中第 3 步当前会直接删除旧 SQLite 并按最新 schema 重建空库，所以这是“真正重建”，不是“保留旧库后清空数据”。

其中 `scripts/sync-edc-server.sh` 当前还会在同步完成后自动执行：

```bash
./venv/bin/python -m src.runtime_state_admin --db "$runtime_dir/data/asns.db" --mode deploy-refresh
```

当前语义：

- 按 `runtime_settings_store` 里的当前 EDC 配置重新拉取 channel catalog
- 修复已经失效的 source-bound 宿主通道和基线定义绑定
- 保留当前 catalog 中仍然有效的宿主通道选择和 `edc_channel_id`

可选环境开关：

```bash
EDC_SERVER_SKIP_SOURCE_REFRESH=1
EDC_SERVER_REBIND_DEFINITIONS=0
```

- `EDC_SERVER_SKIP_SOURCE_REFRESH=1`
  完全跳过部署后的 source-bound 运行态修复
- `EDC_SERVER_REBIND_DEFINITIONS=0`
  只刷新宿主 catalog / 已添加通道 / 连接状态，不自动修定义绑定

`scripts/publish-edc-web-and-asns.sh` 当前还会自动执行：

- 构建 EDC 前端并发布到版本化 assets 目录
- 构建 ASNS
- 备份 `/home/openclaw/asns-host-runtime`
- 清空 ASNS runtime 旧运行库
- 从源码复制最小运行文件并执行 `npm ci --omit=dev`
- 重启 `asns-host.service`

## 6.1 本机 Windows 联调启动

如果是在当前 Windows 开发机上恢复本机联调，优先使用：

```bash
./scripts/start-local-edc-stack.sh
```

当前脚本语义：

- 先停止本机 `8000 / 3000 / 3001`
- 先对本机 SQLite 执行 `factory-reset`
- 再以 `ASNS_BOOTSTRAP_MODE=blank` 启动后端
- 先重建 ASNS 宿主 `dist`
- 再启动：
  - FastAPI 后端 `127.0.0.1:8000`
  - EDC 前端 `http://localhost:3000/edc/`
  - ASNS 宿主 `http://localhost:3001/`
- 最后自动检查：
  - `http://127.0.0.1:8000/health`
  - `http://localhost:3000/edc/`
  - `http://localhost:3000/api/health`
  - `http://localhost:3001/`
  - `http://localhost:3001/api/health`
- 额外校验：
  - 后端启动后 `runtime_baseline_definitions` / `runtime_baselines` / `active_baseline_id` 必须为空白态
  - `http://localhost:3001/` 首页必须包含 `window.__ASNS_EDC_APP_URL__ = "http://localhost:3000/edc/";`
  - 这一步用于确认宿主页真的拿到了浏览器侧 runtime 配置，而不是只把环境变量留在 Node 进程里

目的：

- 避免旧 runtime 数据在本机重启后继续恢复
- 避免“只重启 3001，但宿主仍服务旧 `dist`”的本地假部署
- 把“先 factory-reset，再 blank 启动后端，再 build ASNS，再起宿主”固化成标准顺序

## 7. 最小验收清单

- `http://<host>:8000/health` 返回 `200`
- 访问 `http://<host>/edc/` 能加载 EDC 前端
- 访问宿主页能打开“EDC electricity”
- 宿主“测试连接”成功
- 宿主“同步通道”成功
- EDC 设置页能看到统一运行态
- Dashboard 能拿到 `/api/dashboard/stats` 与 `/api/settings/runtime-status`

## 8. 历史资料处理规则

以下资料仅作为历史参考，不再作为当前部署依据：

- `old/ASNS Master Studio V3.1 完整部署指南.docx`
- `old/ASNS AI老師傅系統 完整軟體設計規格書.docx`
- `old/ASNS黃金基線管理系統(1).docx`
- `old/非監督式工業行為理解：一種基於基線的數位經驗傳承 .docx`

另外，旧单体安装脚本 `docs/Ref/install_asns_server-m-1.sh` 不适用于当前 `Vue + FastAPI + 宿主参考工程` 结构，已不再保留在当前工作区。
