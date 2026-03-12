---
description: 对当前变更进行安全审查
---

## 步骤

1. 获取当前变更的 diff：

```bash
cd d:\project\EDC electricity && git diff
```

2. 对 diff 做安全审查，检查以下维度：
   - **Secrets 泄露**：是否有 API Key、Token、Password 被硬编码
   - **命令注入**：是否有未验证的用户输入拼接到命令行
   - **路径遍历**：是否有未验证的路径输入可能导致任意文件读写
   - **不安全反序列化**：是否有未验证的数据直接反序列化
   - **依赖风险**：新增的包是否安全、版本是否在批准范围内
   - **SQL 注入**：是否有原生 SQL 拼接（应使用 SQLAlchemy ORM）

3. 输出分级报告：
   - **High**：必须修复后才能合并
   - **Medium**：建议修复
   - **Low**：可选改进
