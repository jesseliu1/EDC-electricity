---
description: 运行项目测试（前端+后端）
---

// turbo-all

## 步骤

1. 运行后端测试：

```bash
cd 'd:\project\EDC electricity\apps\server' && uv run pytest -q
```

2. 如果前端有测试脚本，运行前端测试：

```bash
cd 'd:\project\EDC electricity\apps\web' && pnpm run test
```

3. 如果测试失败：
   - 定位失败原因
   - 最小改动修复
   - 确保所有测试通过

4. 输出：测试命令、关键日志片段、最终结果摘要
