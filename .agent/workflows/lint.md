---
description: 运行代码格式化与静态检查
---

// turbo-all

## 步骤

1. 运行后端 linting（ruff）：

```bash
cd d:\project\EDC electricity\apps\server && uv run ruff check . && uv run ruff format --check .
```

2. 运行前端 linting（eslint + prettier）：

```bash
cd d:\project\EDC electricity\apps\web && pnpm run lint
```

3. 仅做**无语义变更**的格式化修复
4. 如有语义问题，报告给用户但不自动修复
5. 输出：检查通过/失败项目的摘要
