# ASNS Server

ASNS AI老师傅智慧熔炼系统后端服务

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
