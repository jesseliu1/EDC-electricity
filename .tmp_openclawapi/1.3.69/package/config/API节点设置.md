# API 节点设置

这是 OpenClawApi 的默认预设文件（节点 / 模型 / API 类型）。

- **CLI 会自动读取此文件**，无需记忆其他位置。
- 仅需修改下面的 **JSON5 配置块**。
- 保持字段结构不变，否则 CLI 会回退到内置默认值。

---

## 生效配置（JSON5）

```json5
{
  "endpoints": [
    { "name": "国内主节点", "url": "https://yunyi.rdzhvip.com" },
    { "name": "CF国外节点1", "url": "https://yunyi.cfd" },
    { "name": "CF国外节点2", "url": "https://cdn1.yunyi.cfd" },
    { "name": "CF国外节点3", "url": "https://cdn2.yunyi.cfd" }
  ],
  "fallbackEndpoints": [
    { "name": "备用节点1", "url": "http://47.99.42.193" },
    { "name": "备用节点2", "url": "http://47.97.100.10" }
  ],
  "models": {
    "claude": [
      { "id": "claude-opus-4-6", "name": "Claude Opus 4.6" },
      { "id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5" },
      { "id": "claude-haiku-4-5", "name": "Claude Haiku 4.5" }
    ],
    "codex": [
      { "id": "gpt-5.3-codex", "name": "GPT 5.3 Codex" },
      { "id": "gpt-5.2", "name": "GPT 5.2" }
    ]
  },
  "apiConfig": {
    "claude": {
      "urlSuffix": "/claude",
      "api": "anthropic-messages",
      "contextWindow": 200000,
      "maxTokens": 8192,
      "providerName": "claude-yunyi"
    },
    "codex": {
      "urlSuffix": "/codex",
      "api": "openai-responses",
      "contextWindow": 128000,
      "maxTokens": 32768,
      "providerName": "yunyi"
    }
  }
}
```

---

## 修改建议

- **换节点**：改 `endpoints` 列表
- **换模型**：改 `models.claude` 或 `models.codex`
- **换 API 类型/路径**：改 `apiConfig`

修改后直接运行：

```bash
npx openclawapi@latest
```
