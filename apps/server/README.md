# ASNS Server

ASNS AI老师傅智慧熔炼系统后端服务

统一部署说明见：

- `../../docs/DEPLOYMENT.md`

当前运行态里与 EDC 相关的两层状态已经拆开：

- `host channels`
  宿主同步到后端的可选通道清单
- `channel role bindings`
  业务链路显式使用的角色绑定，当前包含 `dashboard_primary / dashboard_secondary / live_heat_inference`

部署后的 `deploy-refresh` 会同时 reconcile 这两层状态，以及基线定义上的历史通道绑定。

## 开发

```bash
# 安装依赖
uv sync --all-extras

# 运行开发服务器
uv run uvicorn src.main:app --reload --port 8000

# 运行测试
uv run pytest

# 代码检查
uv run ruff check src tests
uv run ruff format src tests
```

## 生产启动

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

常用环境变量前缀为 `ASNS_`，例如：

```bash
ASNS_DATABASE_URL=sqlite+aiosqlite:///./data/asns.db
ASNS_EDC_BASE_URL=http://localhost:8080
ASNS_EDC_USERNAME=<username>
ASNS_EDC_PASSWORD=<password>
```
