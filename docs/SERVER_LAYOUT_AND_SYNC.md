# 服务器目录与同步方法

> 适用范围：当前这台服务器上的 EDC 与 ASNS。
> 当前基线：主仓已对齐 `origin/master`，后续默认以 GitHub 为唯一代码真源。

## 1. 当前目录布局

### 代码真源

- 主仓根目录：`/home/openclaw/projects/EDC-electricity`
- EDC 前端源码：`/home/openclaw/projects/EDC-electricity/apps/web`
- EDC 后端源码：`/home/openclaw/projects/EDC-electricity/apps/server`
- ASNS 源码：`/home/openclaw/projects/EDC-electricity/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`

### 运行库 / 发布面

- EDC 后端运行副本：`/home/openclaw/edc-electricity-server`
- EDC 后端运行数据库：`/home/openclaw/edc-electricity-server/data/asns.db`
- EDC 前端发布目录：`/var/www/edc-electricity`
- ASNS 宿主运行副本：`/home/openclaw/asns-host-runtime`

### systemd service

- EDC 后端 service：`/home/openclaw/.config/systemd/user/edc-backend.service`
- ASNS 宿主 service：`/home/openclaw/.config/systemd/user/asns-host.service`

仓库内已固化的模板 / 脚本：

- `deploy/systemd/edc-backend.service.example`
- `deploy/systemd/asns-host.service.example`
- `scripts/sync-edc-server.sh`
- `scripts/publish-edc-web-and-asns.sh`
- `scripts/redeploy-public-blank.sh`

当前指向关系：

- `edc-backend.service`
  - `WorkingDirectory=/home/openclaw/edc-electricity-server`
  - 从运行副本启动 uvicorn
- `asns-host.service`
  - `WorkingDirectory=/home/openclaw/asns-host-runtime`
  - 从运行副本启动 `node server.mjs`

## 2. 现在谁是“真源”

以后默认只认这一条同步方向：

`GitHub origin/master -> 主仓 /home/openclaw/projects/EDC-electricity -> 运行副本 / 发布目录`

不要反向把运行库当真源：

- 不要把 `/home/openclaw/edc-electricity-server/src` 的临时修改当作最终代码
- 不要把 `/var/www/edc-electricity` 里的静态文件改动当作源码
- 如果线上有应急改动，必须回写到主仓，然后再重新同步

## 3. 需要长期记住的特殊点

### EDC 后端数据库不要被仓库里的占位文件覆盖

仓库里的：

- `apps/server/data/asns.db`

当前只是占位文件，不是运行中的真实数据库。

真实运行数据在：

- `/home/openclaw/edc-electricity-server/data/asns.db`

以后同步 EDC 后端代码时，必须保留：

- `data/`
- `.logs/`
- `backups/`

说明：

- `venv/` 不再视为“要保留的运行态”
- 当前部署脚本会在同步后用系统 `python3` 重新创建 `/home/openclaw/edc-electricity-server/venv`
- 当前部署脚本还会在同步后按数据库里的当前 EDC 配置执行一次 source-bound 运行态修复
- 这一步的目标不是“每次重建默认绑定”，而是“修掉失效旧源绑定，同时保留当前仍有效的现场选择”

### EDC 前端发布目录里有 legacy `assets/`

`/var/www/edc-electricity/assets` 目前是旧的 root 拥有目录，普通同步时不要强行覆盖它。

当前安全做法是：

1. 每次发布新建一个版本化资产目录，例如 `assets-github-<timestamp>`
2. 把新的 `index.html` 改写为引用这个新目录
3. 保留旧目录做回滚

也就是说，当前 EDC 前端发布是“版本化 assets + 切换 index”的模式，不是直接覆盖固定 `/assets/`

### ASNS 构建 base 和运行 base 不是一回事

当前 nginx 对 `/asns/` 的代理会剥离路径前缀，所以：

- 构建时：`VITE_ASNS_BASE_PATH=/asns/`
- 运行时 service：`ASNS_BASE_PATH=/`

不要把这两个值改成同一个，否则公网 `/asns/` 容易出现 `Cannot GET /` 或资源路径错位。

## 4. 以后如何同步

### 0. 先用仓库内模板恢复 service

如果用户态 service 丢失，优先从仓库模板恢复：

```bash
cd /home/openclaw/projects/EDC-electricity
mkdir -p ~/.config/systemd/user
cp deploy/systemd/edc-backend.service.example ~/.config/systemd/user/edc-backend.service
cp deploy/systemd/asns-host.service.example ~/.config/systemd/user/asns-host.service
systemctl --user daemon-reload
systemctl --user enable --now edc-backend.service asns-host.service
```

说明：

- 模板就是按当前这台服务器的实际路径写的，不是泛化示例
- ASNS 仍然要保持“构建 `/asns/`、运行 `/`”这组值

### A. 先把主仓同步到 GitHub

如果你明确要丢弃本地临时改动，以 GitHub 为准：

```bash
cd /home/openclaw/projects/EDC-electricity
git fetch origin --prune
git reset --hard origin/master
git clean -fd
```

如果你还要保留本地临时工作，不要直接执行这组命令，先备份。

### B. 同步 EDC 后端

优先直接使用仓库脚本：

```bash
cd /home/openclaw/projects/EDC-electricity
./scripts/sync-edc-server.sh
```

原则：

- 源：`/home/openclaw/projects/EDC-electricity/apps/server`
- 目标：`/home/openclaw/edc-electricity-server`
- 保留运行态目录：`data/`、`.logs/`、`backups/`
- `venv/` 每次同步后重新创建，不再沿用旧运行库
- 同步后会自动执行 `src.runtime_state_admin --mode deploy-refresh`，修复 source-bound 脏状态

推荐流程：

```bash
src=/home/openclaw/projects/EDC-electricity/apps/server
rt=/home/openclaw/edc-electricity-server
ts=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$rt/backups/$ts"
tar -C /home/openclaw -czf "$rt/backups/$ts/runtime-pre-sync.tgz" \
  --exclude='edc-electricity-server/backups' \
  edc-electricity-server

systemctl --user stop edc-backend.service

find "$rt" -maxdepth 1 -mindepth 1 \
  ! -name data \
  ! -name .logs \
  ! -name backups \
  -exec rm -rf {} +

cp -a "$src/README.md" "$rt/"
cp -a "$src/alembic.ini" "$rt/"
cp -a "$src/pyproject.toml" "$rt/"
cp -a "$src/uv.lock" "$rt/"
cp -a "$src/alembic" "$rt/"
cp -a "$src/src" "$rt/"
cp -a "$src/tests" "$rt/"

python3 -m venv "$rt/venv"
"$rt/venv/bin/pip" install --upgrade pip setuptools wheel
"$rt/venv/bin/pip" install "$rt"

"$rt/venv/bin/python" -m src.runtime_state_admin \
  --db "$rt/data/asns.db" \
  --mode deploy-refresh

"$rt/venv/bin/python" -m py_compile \
  "$rt/src/api/heats.py"

systemctl --user start edc-backend.service
curl -sS http://127.0.0.1:8001/health
```

补充说明：

- `deploy-refresh` 会先拉当前源的最新 catalog
- 如果宿主已添加通道或 `baseline_definitions.metrics[*].edc_channel_id` 仍存在于当前 catalog，则保持不动
- 只有失效的旧源 ID 才会被剔除 / 重绑
- 如需跳过这一步，可临时设置 `EDC_SERVER_SKIP_SOURCE_REFRESH=1`
- 如需只修宿主 catalog 与连接状态、不重绑定义，可设置 `EDC_SERVER_REBIND_DEFINITIONS=0`

### C. 同步 EDC 前端

优先直接使用仓库脚本：

```bash
cd /home/openclaw/projects/EDC-electricity
./scripts/publish-edc-web-and-asns.sh
```

原则：

- 源：`/home/openclaw/projects/EDC-electricity/apps/web`
- 目标：`/var/www/edc-electricity`
- 发布方式：新建版本化 assets 目录，然后切换 `index.html`

先构建：

```bash
cd /home/openclaw/projects/EDC-electricity/apps/web
pnpm install --frozen-lockfile
pnpm build
```

再发布：

```bash
webroot=/var/www/edc-electricity
ts=$(date -u +%Y%m%dT%H%M%SZ)
new_assets="assets-github-$ts"
archive="$webroot/.publish-$ts"

mkdir -p "$archive"

current_assets=$(sed -n 's#.*src=\"/edc/\\([^/]*\\)/index-.*#\\1#p' "$webroot/index.html" | head -n1)

if [ -n "$current_assets" ] && [ -e "$webroot/$current_assets" ]; then
  mv "$webroot/$current_assets" "$archive/$current_assets"
fi

if [ -e "$webroot/index.html" ]; then
  mv "$webroot/index.html" "$archive/index.html"
fi

mkdir -p "$webroot/$new_assets"
cp -a /home/openclaw/projects/EDC-electricity/apps/web/dist/assets/. "$webroot/$new_assets/"
cp /home/openclaw/projects/EDC-electricity/apps/web/dist/index.html "$webroot/index.html"
sed -i "s#/edc/assets/#/edc/$new_assets/#g" "$webroot/index.html"
cp /home/openclaw/projects/EDC-electricity/apps/web/dist/vite.svg "$webroot/vite.svg"

curl -I --max-time 10 https://hopeofthepantheon.me/edc/
```

说明：

- 这套流程不依赖直接覆盖旧的 root 拥有 `/var/www/edc-electricity/assets`
- 如果后续要清理 legacy `assets/`，需要单独安排带权限的清理窗口

### D. 同步 ASNS

如果只需要重建并重启 ASNS，也可以复用同一个脚本；它会：

- 构建 EDC 前端并按版本化 assets 发布
- 用 `/asns/` base 构建 ASNS
- 备份 `/home/openclaw/asns-host-runtime`
- 清空旧 ASNS runtime 与旧 `node_modules`
- 从源码复制 `package.json / package-lock.json / server.mjs / dist`
- 在 runtime 目录执行 `npm ci --omit=dev`
- 重启 `asns-host.service`
- 校验 `https://hopeofthepantheon.me/edc/` 与 `https://hopeofthepantheon.me/asns/`

ASNS 现在和后端一样使用独立运行副本，不再直接从主仓运行。

先构建：

```bash
ASNS=/home/openclaw/projects/EDC-electricity/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統
cd "$ASNS"
npm ci
VITE_ASNS_BASE_PATH=/asns/ \
VITE_ASNS_EDC_APP_URL=/edc/ \
VITE_ASNS_APP_API_BASE=/api \
npm run build
```

运行时发布后的 service 目录为：

```bash
/home/openclaw/asns-host-runtime
```

再重启服务：

```bash
systemctl --user daemon-reload
systemctl --user restart asns-host.service

curl -I --max-time 10 https://hopeofthepantheon.me/asns/
curl -sS -H 'content-type: application/json' -d '{}' \
  https://hopeofthepantheon.me/asns/host-api/edc/test-connection
```

## 5. 推荐的完整同步顺序

以后如果要把整台机器都切到 GitHub 最新版，建议固定按这个顺序：

1. 备份主仓、运行副本、webroot
2. 主仓同步到 GitHub
3. 构建 EDC 前端
4. 构建 ASNS
5. 同步 EDC 后端运行副本
6. 发布 EDC 前端
7. 重启 EDC 后端和 ASNS
8. 做验收

如果目标不是“普通同步”，而是“删库重建 + blank 重部署”，优先直接执行：

```bash
cd /home/openclaw/projects/EDC-electricity
./scripts/redeploy-public-blank.sh
```

当前脚本会一次性完成：

- `sync-edc-server.sh` 的 runtime 同步，但强制 `EDC_SERVER_SKIP_START=1`
- 跳过 `deploy-refresh`，避免 blank 重建前重新灌回旧 source-bound 状态
- 备份当前运行库数据库文件
- 写入 `edc-backend.service.d/blank-bootstrap.conf`
- 对运行库执行 `factory-reset`
- 启动 blank 后端
- 发布 EDC 前端与 ASNS

## 6. 最小验收命令

```bash
git -C /home/openclaw/projects/EDC-electricity rev-parse HEAD

systemctl --user status edc-backend.service --no-pager -l
systemctl --user status asns-host.service --no-pager -l

curl -sS http://127.0.0.1:8001/health
curl -sS http://127.0.0.1:8001/api/settings/runtime-status

curl -I --max-time 10 https://hopeofthepantheon.me/edc/
curl -I --max-time 10 https://hopeofthepantheon.me/asns/
curl -sS -H 'content-type: application/json' -d '{}' \
  https://hopeofthepantheon.me/asns/host-api/edc/test-connection
```

## 7. 一句话规则

- 改代码：只改主仓
- 同步后端：主仓 `apps/server` -> `edc-electricity-server`
- 同步前端：主仓 `apps/web/dist` -> `/var/www/edc-electricity`
- 同步 ASNS：主仓 ASNS 目录构建后，发布到 `asns-host-runtime` 再重启 `asns-host.service`
- 永远不要把运行库反向当成代码真源
