# 2026-03-27 EDC/ASNS 实时曲线不显示调查

## 结论

- 当前“没有曲线”的直接根因，不是前端图表组件不会画，也不是这次发布把曲线渲染逻辑打坏了。
- 当前部署实例上的真实问题是：后端所在环境无法连通上游 EDC，`EDCClient.login()` 在连接阶段抛出 `httpx.ConnectTimeout`。
- 这解释了为什么用户自己本地部署能看到曲线，而当前部署实例看不到：两边对上游 EDC 的网络可达性不同。
- 这次修复后，`/api/dashboard/realtime` 不再长时间挂住，而是在约 8 秒内返回明确 `503`；前端也不再把失败伪装成“未绑定宿主通道”，而是直接显示“实时曲线当前不可用”。

## investigate 查到的具体原因

### 当前图不显示的具体原因

- 线上与本机运行副本现在都在同一台部署机环境内。
- 直接请求：
  - `http://127.0.0.1:8001/api/dashboard/realtime?duration=1h`
  - `https://hopeofthepantheon.me/api/dashboard/realtime?duration=1h`
- 两者都在约 `8.0s` 返回：

```json
{"detail":"实时曲线拉取失败：EDC 登录超时（ConnectTimeout），请检查当前环境到上游 EDC 的网络连通性"}
```

- 服务日志中的异常链为：
  - `apps/server/src/api/dashboard.py`
  - `apps/server/src/services/edc_client.py`
  - `httpx.ConnectTimeout`

### 之前测试为什么漏掉

- 更早一轮视觉闭环的流程缺陷已经确认：我把“截图文件已生成”误当成“截图内容已回看”。
- 对这次 EDC/ASNS 问题本身，旧代码还有第二层误导：
  - 后端 realtime 路径没有把 transport timeout 快速收敛成受控业务错误；
  - 前端 `fetchRealtime()` 失败后直接把 realtime store 清空成默认值；
  - `RealtimeChart` 又把空的 source label 渲染成“未绑定宿主通道”。
- 这会让真实的“EDC 连不上”在界面上看起来像“没有曲线 / 也许没绑定”，从而掩盖根因。

## 这次修改

### 后端

- `apps/server/src/services/edc_client.py`
  - 将 `httpx.TimeoutException` / `httpx.RequestError` 包装成 `EDCClientError`
  - 明确暴露 `ConnectTimeout` 类别
- `apps/server/src/api/dashboard.py`
  - Dashboard realtime 读取 EDC 时使用更短超时
  - 先登录，再并发拉取功率/电压曲线
  - transport failure 时直接返回明确 `503`

### 前端

- `apps/web/src/stores/dashboard.ts`
  - 新增 `realtimeError`
  - realtime 请求失败时不再静默回退为“空图 + 默认来源”
- `apps/web/src/components/dashboard/RealtimeChart.vue`
  - 新增明确 realtime 失败态
  - realtime 失败时来源文案改为“实时曲线请求失败，来源信息暂不可用”
- `apps/web/src/views/DashboardView.vue`
  - 将 realtime failure 纳入 dashboard warning

## 这次回看动作是怎么做的

- 不是只检查 PNG 文件存在。
- 这次对两张截图都执行了“截图文件重新读回浏览器 canvas，再做像素审计”的二次回看：
  - 首张通过图：
    - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/mocked-dashboard-pass-1.png`
  - 现网真实失败态图：
    - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/public-dashboard-realtime-error.png`
- 回看结果写入：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/visual-closure-evidence.json`

## 为什么确认这次回看是成功且正确的

### 首张通过图

- DOM 侧确认：
  - subtitle 为 `数据时间 2026-03-27 11:15 · 对比基线 标准基线 v2.1 · 1小时`
  - source label 为 `SSTW / 总有功功率 / kW`、`SSTW / A相电压 / V`
  - warning 不可见
- PNG 回看确认：
  - `curveBlue` 命中 `1735` 像素
  - `curveOrange` 命中 `751` 像素
  - 蓝线包围盒横向跨度 `964` 像素
- 结论：截图文件本身包含可见曲线，不是“只有文件，没有回看”。

### 现网失败态图

- DOM 侧确认：
  - 错误卡片标题为 `实时曲线当前不可用`
  - 详情文案明确写出 `EDC 登录超时（ConnectTimeout）`
  - 来源文案为 `实时曲线请求失败，来源信息暂不可用`
- PNG 回看确认：
  - `roseBg` 命中 `318764` 像素
  - `roseText` 命中 `1127` 像素
  - `curveBlue` / `curveOrange` 命中均为 `0`
- 结论：截图文件本身显示的是明确失败态，不是空白图，也不是“未绑定宿主通道”伪空态。

## 第一次通过对应的截图

- `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/mocked-dashboard-pass-1.png`

## 相关产物

- 调查证据：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/visual-closure-evidence.json`
- 首张通过图：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/mocked-dashboard-pass-1.png`
- 首张通过图全页：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/mocked-dashboard-pass-1-full.png`
- 现网失败态图：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/public-dashboard-realtime-error.png`
- 现网失败态全页：
  - `apps/web/docs/test-reports/assets/2026-03-27-edc-realtime-timeout-closure/public-dashboard-failure-full.png`
