# AI 超时追踪使用说明

> 目标：当页面偶发出现“请求后台数据超时”时，让新 session 的 AI 能在 3-5 分钟内接上排查，而不是重新猜是前端、后端还是 EDC 变慢。

---

## 先读哪些文件

1. `docs/session_handoff.md`
2. `docs/progress.md`
3. `docs/lessons.md`
4. 本文档

---

## 当前最小追踪链路

### 前端

- 文件：`apps/web/src/api/client.ts`
- 行为：
  - 每个请求都会带 `X-Request-ID`
  - 前端会记录以下诊断事件：
    - 慢请求：`>= 4s`
    - 超时：`ECONNABORTED`
    - 网络错误：无响应
    - `5xx` 响应
- 诊断记录会写到浏览器内存：
  - `window.__ASNS_NETWORK_DIAGNOSTICS__`

### 后端

- 文件：`apps/server/src/observability.py`
- 文件：`apps/server/src/main.py`
- 行为：
  - 后端会读取或生成 `X-Request-ID`
  - 响应头会回传同一个 `X-Request-ID`
  - 慢请求和重点接口会输出 JSON 结构化日志

### 热点接口和子步骤

- `apps/server/src/api/heats.py`
  - `api_heats_list`
  - `api_heat_compare`
  - `compare_hydrate_baselines`
  - `compare_shared_curves`
- `apps/server/src/api/dashboard.py`
  - `api_dashboard_realtime`
- `apps/server/src/services/edc_client.py`
  - `edc_get_local_datas`

---

## 实际怎么用

### 1. 先在浏览器抓前端诊断

页面复现慢请求或超时后，在浏览器控制台执行：

```js
window.__ASNS_NETWORK_DIAGNOSTICS__
```

重点看这些字段：

- `requestId`
- `route`
- `url`
- `durationMs`
- `outcome`
- `statusCode`

常见 `outcome`：

- `slow`
- `timeout`
- `network_error`
- `http_error`

如果列表很长，可以先筛超时：

```js
(window.__ASNS_NETWORK_DIAGNOSTICS__ || []).filter(item => item.outcome === 'timeout')
```

### 2. 再用 request_id 去后端日志里搜

拿到 `requestId` 后，去后端终端日志里搜索同一个值。

应能看到一组 JSON 事件，例如：

- `http_request`
- `api_heat_compare`
- `compare_hydrate_baselines`
- `compare_shared_curves`
- `edc_get_local_datas`

判断方式：

- 只有 `http_request` 慢，没有更细事件
  - 先看该接口是否还没加子步骤日志
- `api_heat_compare` 慢，同时 `compare_hydrate_baselines` 慢
  - baseline hydrate 是主要瓶颈
- `api_heat_compare` 慢，同时 `compare_shared_curves` 慢
  - 当前曲线批量取数是主要瓶颈
- `compare_shared_curves` 慢，同时出现多个 `edc_get_local_datas`
  - EDC 下游读取慢
- `api_dashboard_realtime` 慢
  - 重点看 realtime 聚合本身，而不是误判成前端重复请求

### 3. 典型页面对应的关键链路

#### Dashboard 首屏

重点接口：

- `GET /api/dashboard/realtime?duration=1h`
- `GET /api/heats?page=1&page_size=50`

重点事件：

- `api_dashboard_realtime`
- `api_heats_list`
- 如走真实链路，再看 `edc_get_local_datas`

#### 炉次详情首屏

重点接口：

- `GET /api/heats/{id}/compare`

重点事件：

- `api_heat_compare`
- `compare_hydrate_baselines`
- `compare_shared_curves`
- `edc_get_local_datas`

---

## 现在这套链路能回答什么问题

它适合回答：

- 是哪个页面、哪个接口超时
- 是慢在前端等待，还是后端聚合
- `compare` 是慢在 baseline hydrate，还是慢在 EDC 曲线取数
- Dashboard 慢是不是又回到了前端重复请求

它暂时不直接回答：

- 用户点击了哪个具体按钮
- 单个业务动作的完整埋点漏斗
- 后端日志文件持久化和日志轮转

---

## 已知限制

- 前端只记录慢请求、超时、网络错误、`5xx`
  - 普通 `4xx` 不会进入诊断 buffer
- 前端诊断只存在浏览器内存，刷新页面会丢
- 后端日志目前默认打到 stdout
  - 还没有独立日志文件 sink
- 当前 `apps/server/.venv/pyvenv.cfg` 指向失效的 `uv` Python 3.11 路径
  - `pytest` 在当前环境下可能跑不起来
  - 静态检查和类型检查是可用的

---

## 当前验证状态

已通过：

- `apps/server/.venv/Scripts/ruff.exe check src/observability.py src/main.py src/services/edc_client.py src/api/heats.py src/api/dashboard.py tests/test_tasks_reports_settings_api.py`
- `npm.cmd exec eslint src/api/client.ts`
- `npm.cmd exec vue-tsc --noEmit`
- `py -3.13 -m py_compile apps/server/src/observability.py apps/server/src/main.py apps/server/src/services/edc_client.py apps/server/src/api/heats.py apps/server/src/api/dashboard.py`

未完成：

- 后端 `pytest`
  - 原因不是本轮代码失败，而是本地 3.11 venv 解释器路径失效

---

## 新 session 推荐动作

如果用户继续反馈“偶发超时”，优先按这个顺序：

1. 让用户复现一次
2. 读取 `window.__ASNS_NETWORK_DIAGNOSTICS__`
3. 取其中一个 `requestId`
4. 对照后端日志确认慢在哪个事件
5. 再决定是修前端超时表现、后端聚合逻辑，还是 EDC 下游链路

不要一上来就把“超时”直接等同成“后端没连上”。
