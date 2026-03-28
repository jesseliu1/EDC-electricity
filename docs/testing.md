# 测试说明

## 当前覆盖

### 前端

- `pnpm --dir apps/web test`
  - Vitest 组件/设计令牌单测
- `pnpm --dir apps/web test:i18n`
  - 多语言 key 结构一致性检查
  - 多语言占位符（如 `{count}`）一致性检查
- `pnpm --dir apps/web test:e2e`
  - Playwright 浏览器回归
  - 覆盖 Dashboard、基线定义、基线向导、炉次列表、炉次详情手动调整、任务、报表、收件箱、系统设置
- `pnpm --dir apps/web build`
  - 类型检查与生产构建验证
- `pnpm --dir apps/web lint`
  - 目前无 error，仍有历史 Vue warning

### 后端

- `apps/server/.venv/Scripts/pytest.exe`
  - 当前 21 条测试
  - 覆盖 Dashboard、基线定义、基线实例、炉次、任务、报表、设置、偏差服务
- `apps/server/.venv/Scripts/ruff.exe check tests`
  - 测试目录静态检查

## 一键执行

仓库根目录可直接运行：

```powershell
.\scripts\check-all.ps1
```

Linux / macOS / Codex cloud 可运行：

```bash
./scripts/check-all.sh
```

如果只想跳过前端 E2E：

```powershell
.\scripts\check-all.ps1 -SkipE2E
```

```bash
./scripts/check-all.sh --skip-e2e
```

## 云端 CI

仓库已新增 GitHub Actions 工作流：

- `.github/workflows/ci.yml`
- 触发时机：
  - 推送到 `master`
  - 推送到 `codex/**` 分支
  - 任意 Pull Request

云端会自动执行以下检查：

### 前端

- `pnpm lint`
- `pnpm test:i18n`
- `pnpm build`
- `pnpm test`
- `pnpm test:e2e`

失败时会上传 Playwright 产物：

- `apps/web/playwright-report`
- `apps/web/test-results`

### 后端

- `uv sync --all-extras`
- `uv run ruff check tests`
- `uv run pytest`

## 接入步骤

如果仓库还没有放到 GitHub，需要先完成以下操作：

1. 在 GitHub 创建远程仓库
2. 把本地仓库关联到远程
3. 推送当前分支
4. 打开仓库的 `Actions` 页面确认 `CI` 工作流开始运行

常用命令示例：

```powershell
git remote add origin <你的仓库地址>
git push -u origin master
```

如果后续使用功能分支，可直接推送对应分支并发起 PR，CI 会自动运行。

## Codex Cloud

如果要把测试任务交给 Codex cloud，建议为仓库环境配置以下 setup script：

```bash
set -e

corepack enable
corepack prepare pnpm@10 --activate

cd apps/web
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps chromium

cd ../server
python -m pip install --upgrade pip
python -m pip install uv
uv sync --all-extras
```

环境准备完成后，Codex cloud 可直接执行：

```bash
./scripts/check-all.sh
```

如果只想先做快速回归，可执行：

```bash
./scripts/check-all.sh --skip-e2e
```

## 维护约定

- 新增页面主流程时，优先补 Playwright 用例
- 新增或修改国际化文案 key、占位符时，必须保证 `pnpm --dir apps/web test:i18n` 通过
- 新增 API 时，至少补成功路径和一组 400/404/422 边界路径
- 使用全局 in-memory store 的后端模块，测试必须保证状态隔离
- 云端 CI 与本地 `.\scripts\check-all.ps1` / `./scripts/check-all.sh` 保持同一套检查口径，新增测试时两边都要同步

## UAT 留档规则

- UAT 必须产出一份统一留档文件，单个文件内同时包含：
  - 测试步骤
  - 预期结果
  - 实际结果
  - 截图证据路径
  - 步骤结论（通过 / 失败 / 阻塞）
- UAT 执行过程中，只要发生一次点击操作，就必须截图，不限于“关键页面”。
- 截图证据必须和具体步骤一一对应，不能只保留截图文件名或单独堆放图片目录。
- 截图完成后，执行人必须重新打开截图文件，核对图中内容是否与该步骤记录的实际结果一致。
- 若截图内容与步骤记录不一致，该步骤不得记为通过，必须改记为失败、阻塞或重新执行。
- 建议截图按 `用例编号-步骤编号-动作` 命名，保证回溯时可直接定位到对应步骤。
