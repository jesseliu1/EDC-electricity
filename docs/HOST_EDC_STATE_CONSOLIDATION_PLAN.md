# ASNS 宿主入口与 EDC 统一状态收敛计划

## 1. 目标

最终目标固定为以下 5 条：

1. 宿主是入口和容器
2. 宿主连接状态是上游真源
3. 宿主把连接配置和通道集合同步到后端
4. EDC 业务页只消费后端统一状态
5. 前端演示模式统一走请求级 `showtime`

这不是“页面改造”问题，而是“状态真源收敛”问题。

---

## 2. 当前状态源审计

## 2.1 宿主层（ASNS React 原型）

### 宿主本地持久化

文件：
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivityState.ts`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`

当前宿主通过 `localStorage['asns-host-connectivity-draft']` 保存：

- `endpoint`
- `username`
- `password`
- `addedChannelIds`
- `savedAt`
- `connection`
  - `isConnected`
  - `machineName`
  - `lastSyncLabel`
  - `meta`

这是一份“宿主草稿态 + 最近连接摘要”的本地副本。

### 宿主运行时内存态

文件：
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/App.tsx`
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/SettingsView.tsx`

宿主 React 当前还维护一套运行时状态：

- `config`
- `isConnected`
- `machineName`
- `lastSyncLabel`
- `meta`
- `channelCatalog`
- `addedChannelIds`
- `openWindowIds`
- `activeWin`

其中：
- `config / isConnected / machineName / lastSyncLabel / meta / addedChannelIds`
  属于业务集成相关状态
- `openWindowIds / activeWin`
  属于纯宿主 UI 状态

### 宿主对后端的写入口

文件：
- `docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統/src/hostConnectivitySync.ts`

当前宿主会写后端两类状态：

1. `PUT /api/settings/edc-connection`
   - `base_url`
   - `username`
   - `password`

2. `PUT /api/settings/host-channels`
   - 已选通道集合

结论：

- 宿主已经是“系统连接配置”的主要写入口
- 宿主已经能把通道集合推到后端
- 但“连接是否在线”的最终摘要目前仍主要停留在宿主本地状态，没有后端统一只读视图

---

## 2.2 后端（FastAPI）

文件：
- `apps/server/src/api/settings.py`
- `apps/server/src/runtime_state.py`

### 后端 `_SETTINGS_STORE`

当前后端持有系统级设置：

- `edc_base_url`
- `edc_username`
- `edc_password`
- `edc_api_key`
- `active_baseline_id`
- `time_tolerance_percent`
- `major_issue_duration_minutes`
- `work_start_time`
- `work_end_time`
- `break_periods`
- `live_heat_inference_enabled`
- `baseline_length_scope_mode`

### 后端宿主通道相关状态

当前后端还持有：

- `_HOST_CHANNEL_STORE`
  - 宿主已选通道集合
- `_HOST_CHANNEL_CATALOG_CACHE`
  - 宿主同步回来的全量通道目录缓存
- `_HOST_CHANNEL_LAST_SYNC_AT`
  - 最近同步时间

### 后端运行态持久化

文件：
- `apps/server/src/runtime_state.py`

当前会把以下运行态落到 SQLite：

- `runtime_settings_store`
- `runtime_host_channels`
- `runtime_host_channel_catalog`
- `runtime_host_channel_last_sync_at`
- 以及业务态 `runtime_baselines / runtime_heats / runtime_mock_heats ...`

结论：

- 后端已经是 EDC 业务页的统一读取面
- 后端已经有足够的数据做“系统统一状态”聚合
- 但目前缺一个明确的“宿主同步状态 / 连接摘要只读接口”

---

## 2.3 EDC 业务前端（Vue）

### 业务页主要读取后端

文件：
- `apps/web/src/stores/heat.ts`
- `apps/web/src/stores/setting.ts`
- 各业务页面 `views/*.vue`

当前 EDC 前端核心链路已主要通过后端读取：

- Dashboard
- 炉次浏览 / 炉次详情
- 黄金基线定义 / 基线向导
- 系统设置页

### 当前仍存在的重复写入口

文件：
- `apps/web/src/views/SettingsView.vue`
- `apps/web/src/stores/setting.ts`
- `apps/web/src/api/setting.ts`

EDC 业务前端当前仍能直接调用：

- `PUT /api/settings/edc-connection`

也就是说，业务页还保留着“自己修改系统连接配置”的入口。

这是当前最明显的真源冲突之一。

### Showtime 模式

文件：
- `apps/web/src/utils/showtime.ts`
- `apps/web/src/api/client.ts`
- `apps/web/src/router/index.ts`

当前已具备：

- 从 URL 读取 `showtime=true`
- 请求统一透传 `X-Showtime: true`
- 路由跳转保持 `showtime`

但目前只完成了“链路骨架”和炉次页口径收口，还没有覆盖全部页面和全部演示 UI。

---

## 3. 当前真源冲突

目前主要有 4 个冲突点。

### 冲突 1：系统连接配置存在双写

当前两边都能写：

- 宿主设置页写 `PUT /api/settings/edc-connection`
- EDC 设置页也能写 `PUT /api/settings/edc-connection`

目标态不应该这样。

目标应改成：

- 只有宿主负责写系统连接配置
- EDC 设置页最多只读展示，或引导跳回宿主设置

### 冲突 2：连接“是否在线”的摘要只存在宿主本地

当前：

- 宿主本地有 `isConnected / machineName / lastSyncLabel / meta`
- 后端只持有连接配置和通道集合
- 业务页通常只能通过“接口能不能拿到数据”间接判断

结果就是：

- 宿主显示在线/离线
- 后端是否真的可用
- 业务页是否真的能消费

这三者容易出现语义错位。

### 冲突 3：宿主草稿态与后端运行态可能漂移

当前：

- 宿主本地保存一份草稿
- 后端 SQLite 也保存一份设置与通道集合

如果宿主恢复草稿但未完整同步，后端和宿主可能短时间不一致。

### 冲突 4：showtime 只完成部分页面收口

当前：

- 请求级 `showtime` 已建立
- 普通 `/api/heats` 已按 `showtime` 切换真实或 mock

但：

- Dashboard
- 基线详情
- 系统设置
- 其它演示提示/来源标签

还没有全部按 `showtime` 收完。

---

## 4. 当前状态归类：哪些已经对了

## 4.1 已经基本对齐

- 宿主是系统入口和容器
- 宿主能把连接配置同步到后端
- 宿主能把通道集合同步到后端
- EDC 核心业务页已经优先消费后端统一状态
- `showtime` 已经是新的请求级 mock 骨架

## 4.2 部分对齐

- 宿主连接状态接近上游真源
  - 但还缺“后端统一只读连接摘要”
- EDC 前端主要消费后端
  - 但设置页仍保留系统连接写入口
- 演示模式已有统一方向
  - 但还没覆盖全部页面

## 4.3 还未完成

- 宿主连接状态成为全系统唯一权威摘要
- 后端对外暴露统一的“宿主连接/同步状态视图”
- EDC 设置页改为只读宿主状态入口
- 全系统所有 mock/demo UI 只在 `showtime=true` 下可见

---

## 5. 目标态设计

目标态应收敛成：

```text
宿主（唯一系统连接写入口）
  ├── 写：EDC 连接配置
  ├── 写：宿主已选通道集合
  ├── 写：宿主同步摘要
  └── 本地只保存“草稿”和“窗口 UI 状态”

后端（统一读取面）
  ├── 保存：系统连接配置
  ├── 保存：宿主通道集合
  ├── 保存：宿主同步摘要 / 最近同步状态
  ├── 提供：业务统一读取接口
  └── 按请求级 showtime 决定真实 / mock 数据集

EDC 业务前端（只读消费）
  ├── 读：后端统一状态
  ├── 不再直接写系统连接配置
  ├── 不再决定 mock/real
  └── 只通过 URL showtime 进入演示模式
```

---

## 6. 推进计划

## 阶段 1：状态真源整理（本轮）

目标：

- 列清当前状态源
- 明确每类状态谁能写、谁只能读
- 标出重复入口和冲突点

产出：

- 本文档

## 阶段 2：补后端统一“宿主状态视图”

建议新增只读接口，例如：

- `GET /api/settings/host-connectivity-status`

返回：

- 是否在线
- 最近测试时间
- 最近同步时间
- 当前节点摘要
- 当前使能通道数
- 宿主是否已完成同步
- 数据来自宿主恢复还是实时验证

这样 EDC 前端不必再靠业务接口成功/失败猜系统状态。

## 阶段 3：收掉 EDC 设置页的系统连接双写

建议改造：

- EDC 设置页不再允许直接改 `edc-connection`
- 改为：
  - 只读显示当前宿主连接来源
  - 提示“请到宿主设置页修改”
  - 业务页只保留与本应用相关的业务参数

这是最关键的一刀。

## 阶段 4：把 `showtime` 扩到全系统

范围：

- Dashboard
- 炉次浏览 / 炉次详情
- 基线定义 / 基线详情 / 基线向导
- 任务 / 报表
- 所有 demo/mock banner、标签、入口

原则：

- 默认模式完全真实 only
- `showtime=true` 才允许 mock

## 阶段 5：补联调整体回归

至少覆盖：

1. 重开宿主
2. 恢复宿主草稿
3. 宿主自动同步到后端
4. 从宿主打开 EDC
5. EDC 各页面读取统一状态
6. 切换 `showtime=true` 后整站进入演示模式

---

## 7. 下一步建议执行顺序

建议按这个顺序推进：

1. 先做阶段 2：补后端统一宿主状态视图
2. 再做阶段 3：收掉 EDC 设置页双写
3. 再做阶段 4：扩展 `showtime`
4. 最后做阶段 5：整链路自动化与人工验收

原因：

- 不先补统一状态视图，业务页永远只能猜
- 不先收掉 EDC 设置页双写，真源就永远不干净
- `showtime` 扩站应该建立在真源已单写的前提上

---

## 8. 当前结论

结论不是“方向错了”，而是：

- 主干方向已经对了
- 宿主 -> 后端 -> EDC 这条主链已经存在
- 当前最大的残留问题不是技术不可行，而是状态写入口还没有完全收口

因此现在继续推进这件事是合适的，而且优先级高。
