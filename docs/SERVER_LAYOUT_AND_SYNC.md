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
- ASNS 当前运行目录：直接使用主仓中的 ASNS 源码目录，不再单独复制一份

### systemd service

- EDC 后端 service：`/home/openclaw/.config/systemd/user/edc-backend.service`
- ASNS 宿主 service：`/home/openclaw/.config/systemd/user/asns-host.service`

仓库内已固化的模板 / 脚本：

- `deploy/systemd/edc-backend.service.example`
- `deploy/systemd/asns-host.service.example`
- `scripts/sync-edc-server.sh`
- `scripts/publish-edc-web-and-asns.sh`

当前指向关系：

- `edc-backend.service`
  - `WorkingDirectory=/home/openclaw/edc-electricity-server`
  - 从运行副本启动 uvicorn
- `asns-host.service`
  - `WorkingDirectory=/home/openclaw/projects/EDC-electricity/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統`
  - 直接从主仓源码目录启动 `node server.mjs`

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
- `venv/`
- `.logs/`
- `backups/`

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
- 保留运行态目录：`data/`、`venv/`、`.logs/`、`backups/`

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
  ! -name venv \
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

/home/openclaw/edc-electricity-server/venv/bin/python -m py_compile \
  /home/openclaw/edc-electricity-server/src/api/heats.py

systemctl --user start edc-backend.service
curl -sS http://127.0.0.1:8001/health
```

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
- 重启 `asns-host.service`
- 校验 `https://hopeofthepantheon.me/edc/` 与 `https://hopeofthepantheon.me/asns/`

ASNS 不再使用独立运行副本，直接从主仓运行。

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
- 同步 ASNS：主仓 ASNS 目录构建后，直接重启 `asns-host.service`
- 永远不要把运行库反向当成代码真源
