---
description: 启动前后端开发服务器
---

## 步骤

1. 启动后端开发服务器：

```bash
cd d:\project\EDC electricity\apps\server && uv run uvicorn app.main:app --reload --port 8000
```

2. 启动前端开发服务器：

```bash
cd d:\project\EDC electricity\apps\web && pnpm run dev
```

3. 确认两个服务都启动成功
4. 输出：前端和后端服务的访问地址
