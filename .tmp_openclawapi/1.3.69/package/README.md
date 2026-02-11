# openclawapi - AI 模型配置

配置 OpenClaw 连接 AI 模型（Claude、GPT 等），一条命令搞定。

## 快速开始

**方式一：交互式（推荐新手）**
```bash
npx openclawapi@latest
```
按提示选择节点和模型即可。
主菜单已简化为：激活 Claude / 激活 Codex / 测试连接 / 查看配置 / 恢复 / 退出。

**方式二：一键配置 Claude**
```bash
# macOS/Linux
OPENCLAW_CLAUDE_KEY="你的Key" npx openclawapi@latest preset-claude

# Windows PowerShell
$env:OPENCLAW_CLAUDE_KEY="你的Key"; npx openclawapi@latest preset-claude

# Windows CMD
set OPENCLAW_CLAUDE_KEY=你的Key && npx openclawapi@latest preset-claude
```

**方式三：一键配置 Codex**
```bash
# macOS/Linux
OPENCLAW_CODEX_KEY="你的Key" npx openclawapi@latest preset-codex

# Windows PowerShell
$env:OPENCLAW_CODEX_KEY="你的Key"; npx openclawapi@latest preset-codex

# Windows CMD
set OPENCLAW_CODEX_KEY=你的Key && npx openclawapi@latest preset-codex
```

**方式四：完全自动化（无交互）**
```bash
# macOS/Linux
OPENCLAW_CLAUDE_KEY="你的Key" npx openclawapi@latest preset-claude --model claude-opus-4-5 --set-primary true --force --test true

# Windows PowerShell
$env:OPENCLAW_CLAUDE_KEY="你的Key"; npx openclawapi@latest preset-claude --model claude-opus-4-5 --set-primary true --force --test true

# Windows CMD
set OPENCLAW_CLAUDE_KEY=你的Key && npx openclawapi@latest preset-claude --model claude-opus-4-5 --set-primary true --force --test true

# macOS/Linux
OPENCLAW_CODEX_KEY="你的Key" npx openclawapi@latest preset-codex --model gpt-5.2 --set-primary true --force --test true

# Windows PowerShell
$env:OPENCLAW_CODEX_KEY="你的Key"; npx openclawapi@latest preset-codex --model gpt-5.2 --set-primary true --force --test true

# Windows CMD
set OPENCLAW_CODEX_KEY=你的Key && npx openclawapi@latest preset-codex --model gpt-5.2 --set-primary true --force --test true
```

## 重要说明

- 一键激活/预设会默认只保留一个中转配置，避免写入过多节点导致混乱
- 若检测到已有中转配置，会提示确认；使用 `--force` 将直接覆盖

---

## 配置入口（无需记忆）

节点/模型/API 类型配置在：

`Service/OpenClawApi/config/API节点设置.md`

CLI 会自动读取该文件内的 JSON5 配置块。只需修改这个文件即可。

如需自定义路径，可设置：

`OPENCLAW_PRESET_PATH=/path/to/你的配置.md`

## 文档入口

更详细说明在：

`Service/OpenClawApi/docs/README.md`
