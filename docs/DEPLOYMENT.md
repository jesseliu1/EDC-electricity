# 部署说明 (DEPLOYMENT)

> 当前仓库的可用部署入口以本文为准。历史脚本和旧版 DOCX 仅保留作参考，不再作为上线依据。

当前这台服务器的固定模板 / 脚本入口：

- `deploy/systemd/edc-backend.service.example`
- `deploy/systemd/asns-host.service.example`
- `scripts/sync-edc-server.sh`
- `scripts/publish-edc-web-and-asns.sh`
- 服务器路径与同步原则见 `docs/SERVER_LAYOUT_AND_SYNC.md`

## 1. 部署范围

本项目当前包含 3 个需要区分的运行单元：

1. `apps/server`
   FastAPI 后端，默认监听 `8000`
2. `apps/web`
   Vue 业务前端，构建后以 `/edc/` 作为访问前缀
3. `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`
   ASNS 宿主“神经系统”参考工程，默认监听 `3001`

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
- Python 3.11.x
- `uv`

## 3. 后端部署

目录：

- `apps/server`

首次部署：

```bash
uv sync --all-extras
```

生产启动：

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

常用环境变量：

```bash
ASNS_DATABASE_URL=sqlite+aiosqlite:///./data/asns.db
ASNS_EDC_BASE_URL=http://<your-edc-host>:8080
ASNS_EDC_USERNAME=<username>
ASNS_EDC_PASSWORD=<password>
ASNS_DEBUG=false
```

说明：

- 默认数据库路径是 `apps/server/data/asns.db`
- 如需持久化，部署时请保证 `data/` 目录可写
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

推荐运行方式：

```bash
npm run preview -- --host 0.0.0.0 --port 3001
```

说明：

- 该宿主工程不是纯静态页面
- 当前 `vite.config.ts` 通过 `configureServer` 和 `configurePreviewServer` 提供 `/host-api/edc/test-connection` 与 `/host-api/edc/sync-channels`
- 因此若只拿 `dist/` 丢到纯静态文件服务器，宿主里的 EDC 测试连接与同步通道能力不会工作
- 如果要保留当前行为，部署时需要保留一个 Node 进程来跑 `vite preview`
- 当前仓库也已补独立生产入口，可直接用 `npm start` 跑 `server.mjs`，负责：
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
3. 启动宿主“神经系统” `3001`
4. 配置反向代理
5. 打开宿主首页，执行一次 EDC 连线测试与通道同步
6. 从宿主进入 EDC 页面，确认 Dashboard、Heats、Baselines 正常

如果是在当前服务器上按既定目录重发，优先执行：

```bash
./scripts/sync-edc-server.sh
./scripts/publish-edc-web-and-asns.sh
```

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
