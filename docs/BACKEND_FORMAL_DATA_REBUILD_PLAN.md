# 后端正式数据重构计划

> 生命周期：本文件为本轮“后端正式数据重构”的主线文档；重构完成前持续有效，完成后保留为实现与回溯依据，不删除。

## 1. 背景

当前系统的核心问题不是单点 bug，而是主业务数据长期以 `settings.runtime_*` 的运行态 JSON 形式存在，导致：

- 历史炉次与运行态边界不清
- 已结束炉次仍可能被运行态重算覆盖
- 新基线可能错误作用到更早历史数据
- 偏离度计算依赖请求期 hydrate，稳定性差
- 历史详情与历史列表仍可能受实时 EDC 链路影响

本轮计划的目标，是把系统重构到“正式业务表为主、运行态只服务当前炉次”的结构。

## 2. 目标

### 2.1 总体目标

建立两类主表：

- 主数据主表：`baseline_definitions`
- 业务主表：`heats`

并以此为根，建立正式的后端主读写链路。

### 2.2 结果目标

重构完成后应达到：

- 历史炉次一旦入库，不再漂移
- 基线只影响生效时间之后的数据
- 历史详情和历史列表优先读正式表
- 偏离度结果稳定落库，不再主要依赖请求期计算
- UI 不再是业务正确性的前提，后台本身可独立测试

## 3. 核心设计原则

### 3.1 主表与从表

- `baseline_definitions` 是主数据根
- `heats` 是业务根
- 其余表均作为从表/外部表存在

### 3.2 运行态与历史态分离

- 当前正在发生的炉次允许保留运行态缓存
- 除当前炉次外，其余炉次都应进入正式 `heats`
- 正式历史不应再由运行态重算覆盖

### 3.3 不允许未经确认的回退

以下行为不允许进入正式业务链路：

- 自动补全通道
- 自动换绑业务角色
- 自动回退到其它基线
- 自动用旧快照冒充当前态
- 自动跳转到“看起来最像”的其它记录

正确做法是显式暴露：

- `missing`
- `invalid`
- `stale`
- `unbound`
- `failed`

等待人工确认或显式修订动作。

### 3.4 历史数据允许保留上下文窗口

正式历史中的指标值不只保存炉次真实区间，也保留：

- 前 30 分钟
- 当前炉次区间
- 后 30 分钟

目的：

- 后续人工查看和单炉次调整时，不需要立即回源 EDC
- 当前炉次缓存结构可以尽量与正式表同构

## 4. 目标表结构

### 4.1 主表

- `baseline_definitions`
- `heats`

### 4.2 从表 / 外部表

- `baseline_definition_metrics`
- `baselines`
- `metric_series`
- `tasks`
- `settings`

### 4.3 字段语义约束

- `baseline_definition_metrics.item` = 指标项号，如 `001 / 002 / 003`
- `baselines.item` = 基线版本项，如 `001 / 002 / 003`
- `metric_series.item` = 指标项号，对齐 `baseline_definition_metrics.item`
- `metric_series` 统一存放：
  - 基线版本的指标值
  - 炉次的指标值

## 5. 当前炉次运行态设计

### 5.1 当前炉次缓存

当前炉次仍允许保留运行态缓存，但缓存结构应尽量与正式表同构。

推荐运行态缓存字段：

- `id`
- `heat_no`
- `start_time`
- `end_time`
- `context_start_time`
- `context_end_time`
- `baseline_definition_id`
- `baseline_item`
- `deviation_status`
- `last_point_at`
- `runtime_status`

### 5.2 当前炉次指标缓存

当前炉次的指标缓存结构应尽量与 `metric_series` 相同：

- `owner_key`
- `item`
- `metric_key`
- `metric_name`
- `unit`
- `series_json`
- `stat_json`

### 5.3 缓存语义

缓存只用于：

- 当前炉次展示
- 当前炉次人工调整
- 当前炉次结束时直接入正式表

缓存不应继续承担：

- 历史主读链路
- 历史详情主数据来源
- 历史偏离度主要来源

## 6. API 主链路目标

### 6.1 基线定义

- `GET /api/baseline-definitions`
- `GET /api/baseline-definitions/{id}`
- `POST /api/baseline-definitions`
- `PATCH /api/baseline-definitions/{id}`
- `DELETE /api/baseline-definitions/{id}`

### 6.2 定义指标项

- `GET /api/baseline-definitions/{id}/metrics`
- `POST /api/baseline-definitions/{id}/metrics`
- `PATCH /api/baseline-definitions/{id}/metrics/{item}`
- `DELETE /api/baseline-definitions/{id}/metrics/{item}`

### 6.3 基线版本

- `GET /api/baselines`
- `GET /api/baselines/{definition_id}/{item}`
- `POST /api/baselines`
- `PATCH /api/baselines/{definition_id}/{item}`
- `POST /api/baselines/{definition_id}/{item}/publish`
- `POST /api/baselines/{definition_id}/{item}/disable`

### 6.4 炉次

- `GET /api/heats`
- `GET /api/heats/{id}`
- `GET /api/heats/{id}/compare`
- `GET /api/heats/{id}/cutting-timeline`

### 6.5 指标值

- `GET /api/baselines/{definition_id}/{item}/series`
- `GET /api/heats/{heat_id}/series`
- `GET /api/heats/{heat_id}/compare`

## 7. 实施阶段

### Phase 1：落正式表结构

- 更新 SQLAlchemy models
- 更新 `models/__init__.py`
- 建 Alembic migration
- 当前测试数据允许丢弃，不做复杂迁移兼容

当前状态：

- [x] 正式 SQLAlchemy 模型已按目标结构落地
- [x] `models/__init__.py` 已按新模型导出
- [x] 初始 Alembic schema 已重写为正式表结构
- [ ] API / service 主读写链路尚未切到正式表

### Phase 2：基线主数据链路

- `baseline_definitions`
- `baseline_definition_metrics`
- `baselines`
- `metric_series(owner_type=baseline)`

目标：

- 定义、定义指标、基线版本、基线指标值正式入表

当前状态：

- [x] `baseline_definitions` CRUD 已切到正式表
- [x] `baseline_definition_metrics` CRUD 已切到正式表
- [x] `baselines` 列表 / 详情 / 创建 / 发布 / 停用 / 激活 / 删除已切到正式表
- [x] 仍保留 `_DEFINITION_STORE / _BASELINE_STORE` 内存镜像，仅作为 `heats` 旧链路过渡兼容
- [ ] `metric_series(owner_type=baseline)` 仍未真正落到正式表写入

### Phase 3：炉次业务链路

- `heats`
- `metric_series(owner_type=heat)`

目标：

- 当前炉次结束后正式入库
- 历史列表和详情从正式表读取
- 历史不再依赖运行态 JSON

当前状态：

- [x] 已新增 `apps/server/src/services/formal_heat_service.py`
- [x] 历史列表开始从 `heats + metric_series` 读取
- [x] 历史详情开始从 `heats + metric_series` 读取
- [x] 历史曲线接口对 `sealed_history` 已可直接读正式表曲线
- [x] 运行态刷新已开始把 `runtime_candidates[2:]` 封口写入正式 `heats`
- [x] 当前缓存边界已收口为只保留 `n-1 / n`
- [x] 历史修改接口已开始直接写正式 `heats`
- [x] 历史恢复切割接口已开始直接写正式 `heats`
- [x] 历史分析接口已开始直接写正式 `heats`
- [ ] `compare / cutting-timeline` 仍处于过渡态
- [ ] 旧 `tests/test_heats_api.py` 及部分 baseline/task/report 测试仍主要验证旧 runtime/样板链路，需要后续按正式表口径重写或补正式表 seed

### Phase 4：偏离度与任务

- 偏离度计算结果写回 `heats`
- 任务快照绑定正式历史炉次

### Phase 5：UI 切换

- UI 改读新 API
- 去除旧 runtime 主读依赖
- 最后再做完整 UAT

## 8. 测试策略

### 8.1 后台优先

本轮优先级：

1. 数据模型测试
2. 服务层测试
3. API 测试
4. 最后才是 UI 测试

### 8.2 必测规则

- 新基线不得作用到 `effective_from` 之前的历史炉次
- 历史炉次入库后不再漂移
- 历史详情不依赖实时 EDC hydrate
- 偏离度结果能够稳定落库
- 删除通道或绑定失效时，不允许自动补全/自动换绑

### 8.3 当前已通过的实现侧验证

- [x] `uv --directory apps/server run pytest tests/test_formal_baseline_api.py -q`
- [x] `uv --directory apps/server run ruff check src/models/baseline.py src/models/heat.py src/models/metric_series.py src/models/task.py src/models/__init__.py alembic/versions/26998facdffe_initial_schema.py src/api/baseline_definitions.py src/api/baselines.py src/services/formal_baseline_service.py src/services/__init__.py tests/conftest.py tests/test_formal_baseline_api.py`

## 9. 当前不做的内容

以下内容当前不进入本轮开发：

- PostgreSQL 迁移
- 时序点表拆分
- 批量炉次修订功能实现
- 新 UI 重做
- 复杂历史迁移兼容

说明：

- 批量修订功能后续可以做，但本轮只保留结构设计，不实现功能

## 10. 当前结论

当前已具备进入开发的条件：

- 目标结构已明确
- API 主链路已明确
- 主表与从表边界已明确
- 运行态与历史态边界已明确
- 测试策略已明确

下一步应直接进入：

1. 更新 SQLAlchemy models
2. 建 Alembic migration
3. 实现后端主读写链路
4. 补测试
