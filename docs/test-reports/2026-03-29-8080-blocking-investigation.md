# 2026-03-29 `127.0.0.1:8080` 阻塞调查

## 调查目标

- 查清 `S05-TC01 / S05-TC02 / S05-TC03` 过去被记为“受 `127.0.0.1:8080` 阻塞”的真实原因
- 判断 `8080` 是否仍是当前 UAT 的有效阻塞项

## 现场事实

### 1. 本机 `8080` 当前无监听进程

执行结果：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8080
curl.exe -v --max-time 8 http://127.0.0.1:8080/
```

结论：

- `TcpTestSucceeded=False`
- `curl` 返回 `connection refused`
- `netstat -ano | findstr :8080` 无有效监听记录

这说明当前机器上没有本地服务在监听 `127.0.0.1:8080`。

### 2. 仓库内没有对应 `8080` 的本地服务定义

已核对：

- `apps/server/README.md`
- `apps/server/src/config.py`
- `apps/web/vite.config.ts`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/server.mjs`

结论：

- `apps/server/src/config.py` 的 `DEFAULT_EDC_BASE_URL` 仍是 `http://localhost:8080`
- 但这只是默认占位值，不代表仓库内存在一个应由本项目启动的 `8080` 服务
- 前端 `3000` 开发代理实际转发到 `http://localhost:8000`
- ASNS 宿主 `3001` 默认代理到 `http://127.0.0.1:8001`

### 3. 当前运行中的真实链路已不依赖 `8080`

实际查询：

- `GET http://127.0.0.1:8000/api/settings/runtime-status`
- `GET http://127.0.0.1:8001/api/settings/runtime-status`
- `GET http://127.0.0.1:8000/api/settings`
- `GET http://127.0.0.1:8000/api/settings/host-connectivity-status`

结论：

- `8000` 当前 `edc.base_url = http://61.216.55.133`
- `8001` 当前 `edc.base_url = http://60.251.229.32`
- `8000` 当前宿主连通状态仍为 `is_connected=true`
- `8000` 当前已存在 `6` 条宿主通道绑定

这说明当前真实运行环境已经直接连到远端 EDC 源，不再走 `localhost:8080`。

## 调查结论

- `127.0.0.1:8080` 不是“本仓内应启动但未启动”的服务
- 过去把 `S05` 记为“受 `8080` 阻塞”，本质上是沿用了历史默认值 / 旧联调口径
- 在 2026-03-29 当前环境下，`8080` 已不应继续作为 `S05` 的主阻塞原因保留

## 新发现的真实后续阻塞

虽然 `8080` 不是当前主阻塞，但 `S05-TC03` 所需的“新源实时数据开始采集”仍未自然成立。

实际查询：

```powershell
GET http://127.0.0.1:8000/api/dashboard/realtime?duration=5m
```

返回：

- `detail = 未获取到真实实时数据，请检查宿主连接和通道绑定`

补充现象：

- `GET http://127.0.0.1:8000/api/dashboard/stats` 可返回 200
- `GET http://127.0.0.1:8000/api/dashboard/recent-heats?page=1&page_size=3` 当前返回空列表

因此，若 `S05` 仍无法整体判通，当前更像是卡在“新源实时数据尚未被业务页消费出来”，而不是卡在 `8080`。

## 建议口径

- `S05-TC01 / S05-TC02`：不再按 `127.0.0.1:8080` 外部阻塞描述
- `S05-TC03`：若继续失败，应转为调查“实时数据链路/通道绑定/业务页取数”问题
- 历史文档中凡是把 `8080` 写成当前唯一主阻塞的条目，后续应统一修正为“历史默认口径，当前已不成立”
