# 测试说明

## 当前覆盖

### 前端

- `pnpm --dir apps/web test`
  - Vitest 组件/设计令牌单测
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

如果只想跳过前端 E2E：

```powershell
.\scripts\check-all.ps1 -SkipE2E
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

## 维护约定

- 新增页面主流程时，优先补 Playwright 用例
- 新增 API 时，至少补成功路径和一组 400/404/422 边界路径
- 使用全局 in-memory store 的后端模块，测试必须保证状态隔离
- 云端 CI 与本地 `.\scripts\check-all.ps1` 保持同一套检查口径，新增测试时两边都要同步
