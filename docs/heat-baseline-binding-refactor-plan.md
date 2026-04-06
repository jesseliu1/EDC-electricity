# 炉次 1:N 黄金基线绑定重构计划

## 1. 背景与目标

本轮要解决的不是单点 bug，而是把“黄金基线”和“炉次详情/对比/分析”的数据组织方式收敛成一套正式、统一、可扩展的结构。

当前主要问题：

- `heats` 同时承担“炉次事实数据”和“单条基线绑定结果”，天然只支持 `1 个炉次 -> 0/1 条基线`
- `metric_series` 当前只区分 `heat / baseline` 两类 owner，但上层业务已经需要 `1 个炉次 -> N 条基线`
- 默认黄金基线目前主要通过 `settings.active_baseline_id（当前激活基线ID）` 表达，不属于正式业务主数据
- 炉次列表、炉次详情、compare、analyze、任务快照存在“同一业务概念走不同来源”的风险
- 历史炉次与运行态/镜像 store 仍有混用痕迹，后续继续叠逻辑会越来越绕

本轮目标：

1. 让 `baselines（黄金基线版本表）` 正式存储“默认黄金基线”标记
2. 新增 `heat_baseline_bindings（炉次-黄金基线绑定表）`，正式支持 `1 个炉次 -> N 条基线`
3. 让 `heats（炉次表）` 回归只存炉次自身事实，不再承载单基线绑定结果
4. 明确 `metric_series（指标序列表）` 只存实体曲线，不存 binding 级重复曲线
5. 让历史炉次列表、详情、compare、analyze、任务创建统一只走正式表数据源

约束前提：

- 不做旧数据兼容
- 不做旧库迁移兜底
- 改完后通过 `factory-reset + blank` 删库重建验证

---

## 2. 设计原则

### 2.1 分层原则

- `heats（炉次表）` 只负责炉次事实
- `baselines（黄金基线版本表）` 只负责黄金基线版本主数据
- `heat_baseline_bindings（炉次-黄金基线绑定表）` 只负责“谁绑定谁”以及“这次绑定分析出了什么”
- `metric_series（指标序列表）` 只负责“某个实体自己的曲线”

### 2.2 数据源原则

- 历史正式炉次的真源统一为：`heats + heat_baseline_bindings + metric_series`
- 默认黄金基线的真源统一为：`baselines.is_default（默认黄金基线）`
- `settings.active_baseline_id（当前激活基线ID）` 不再作为正式黄金基线真源
- 运行态只负责“当前正在发生的炉次”；一旦固化，后续读取统一走正式表

### 2.3 曲线存储原则

- `metric_series` 只保留两类 owner：
  - `owner_type='heat'` + `owner_key=heat_id（炉次ID）`
  - `owner_type='baseline'` + `owner_key='{baseline_definition_id}:{baseline_item}'`
- 不新增 `owner_type='heat_baseline_binding'`
- 不为一条炉次绑定多条基线而复制多份炉次曲线

---

## 3. 目标数据模型

### 3.1 `baselines（黄金基线版本表）`

新增字段：

- `is_default（默认黄金基线）: bool`

业务语义：

- 表示该基线是否为系统当前默认黄金基线
- 暂按“全系统唯一”处理
- 如果后续需要改为“每个 definition 内唯一”，可再收窄唯一性范围，但本轮先不做复杂化设计

建议约束：

- 仅允许 `status='published'` 的基线为 `is_default=1`
- 同一时刻最多一条 `baselines` 记录满足 `is_default=1`

### 3.2 `heats（炉次表）`

保留字段：

- `id（炉次ID）`
- `heat_no（炉次编号）`
- `description（炉次备注）`
- `furnace_id（炉号/设备ID）`
- `start_time（开始时间）`
- `end_time（结束时间）`
- `context_start_time（上下文开始时间）`
- `context_end_time（上下文结束时间）`
- `sealed_at（固化时间）`
- `source_kind（来源类型）`
- `cut_reason（切割原因）`
- `cut_status（切割状态）`
- `status（炉次状态）`
- `created_by / updated_by / created_at / updated_at`

移出字段：

- `baseline_definition_id（绑定基线定义ID）`
- `baseline_item（绑定基线版本号）`
- `baseline_effective_from_snapshot（绑定时基线生效时间快照）`
- `deviation_status（偏离状态）`
- `deviation_percent（最大偏离度）`
- `avg_deviation_percent（平均偏离度）`
- `deviation_details_json（偏离详情）`
- `time_offset_percent（时间偏移比例）`
- `mismatch_duration_minutes（连续不一致时长）`

原因：

- 这些字段在 `1 个炉次 -> N 条基线` 下不再是炉次级唯一值
- 继续放在 `heats` 只会制造“到底是哪条基线的结果”歧义

### 3.3 `heat_baseline_bindings（炉次-黄金基线绑定表）`

新增表。

主键：

- `heat_id（炉次ID）`
- `baseline_definition_id（基线定义ID）`
- `baseline_item（版本号）`

建议字段：

- `heat_id（炉次ID）`
- `baseline_definition_id（基线定义ID）`
- `baseline_item（版本号）`
- `is_primary（主黄金基线）`
- `effective_from_snapshot（生效时间快照）`
- `tolerance_percent_snapshot（容许误差快照）`
- `analysis_status（分析状态）`
- `deviation_percent（最大偏离度）`
- `avg_deviation_percent（平均偏离度）`
- `deviation_details_json（偏离详情JSON）`
- `time_offset_percent（时间偏移比例）`
- `mismatch_duration_minutes（连续不一致分钟数）`
- `created_at（创建时间）`
- `updated_at（更新时间）`

业务语义：

- 一条记录代表“某个炉次绑定了某条黄金基线”
- 该记录同时保存该对比关系的分析结果
- `is_primary（主黄金基线）` 在炉次初始化绑定时确定，不由前端临时决定

`is_primary` 规则：

1. 炉次初始化时，先找出所有对该炉次生效的基线
2. 如果其中包含 `is_default=1` 的黄金基线，则该 binding 置为 `is_primary=1`
3. 其他 binding 置为 `is_primary=0`
4. 如果没有任何默认黄金基线命中，则按确定性规则选一条主基线
   - 暂定：`effective_from` 最新优先，其次 `published_at` 最新优先

### 3.4 `metric_series（指标序列表）`

本轮不新增第三类 owner。

关联方式：

- 炉次曲线：
  - `owner_type='heat'`
  - `owner_key=heat_id（炉次ID）`
- 基线曲线：
  - `owner_type='baseline'`
  - `owner_key='{baseline_definition_id}:{baseline_item（版本号）}'`

一条 `heat_id` 会在 `metric_series` 里对应多行，不是一行塞所有指标。

示意：

- `owner_type='heat', owner_key='heat-001', metric_key='power'`
- `owner_type='heat', owner_key='heat-001', metric_key='voltage'`
- `owner_type='heat', owner_key='heat-001', metric_key='temperature'`

对比时的读取方式：

1. 先查 `heat_baseline_bindings`
2. 用 `heat_id（炉次ID）` 查炉次曲线
3. 用 `baseline_definition_id（基线定义ID） + baseline_item（版本号）` 查基线曲线
4. 按 `metric_key（指标业务键）` 对齐组装 compare 结果

---

## 4. 模块边界与读取链路

### 4.1 基线管理链路

目标：

- 基线创建、更新、发布、默认黄金基线切换都落在 `baselines` 正式表

具体口径：

- 基线创建仍以 `selected_start_time + selected_end_time（图上选区）` 为真源
- `source_heat_id（来源炉次ID）` 仅保留为 UI 定位辅助，可为空
- 创建/更新/发布时允许携带 `is_default（默认黄金基线）`
- 若某条基线被设置为 `is_default=1`，需要清掉原先默认基线

### 4.2 炉次固化链路

目标：

- 炉次固化时，一次性把“适用基线绑定关系”落到正式表

具体口径：

1. 炉次切割完成并固化 `heats` 后
2. 根据炉次时间点和基线生效规则，找出全部适用的已发布基线
3. 为每条适用基线创建 `heat_baseline_bindings`
4. 根据默认黄金基线规则确定唯一 `is_primary（主黄金基线）`
5. 初始可先写 `analysis_status='pending'`
6. 分析完成后再回写该 binding 的偏离结果

### 4.3 炉次读取链路

目标：

- 历史炉次列表、详情、compare、analyze、任务都只从一套正式来源取值

统一读取原则：

- 历史炉次主记录：查 `heats`
- 炉次主黄金基线摘要：查 `heat_baseline_bindings where is_primary=1`
- 多基线详情：查该炉次全部 `heat_baseline_bindings`
- 炉次曲线：查 `metric_series(owner_type='heat')`
- 基线曲线：查 `metric_series(owner_type='baseline')`

明确禁止：

- 历史正式炉次详情再回退到旧 `_HEAT_STORE`
- 历史正式基线再靠 `_BASELINE_STORE` 当最终真源
- 列表与详情分别从不同层取“基线绑定结果”

---

## 5. API 改造计划

本轮按“先后端正式契约，再前端消费”的顺序推进。

### 5.1 `baselines` API

影响接口：

- `GET /api/baselines`
- `GET /api/baselines/{id}`
- `POST /api/baselines`
- `PATCH /api/baselines/{id}`
- `POST /api/baselines/{id}/publish`
- `POST /api/baselines/{id}/disable`
- `GET /api/baselines/active`

计划改动：

- 返回字段补 `is_default（默认黄金基线）`
- 创建/更新 schema 补 `is_default`
- 发布逻辑加入默认黄金基线唯一性处理
- `GET /api/baselines/active` 从 `baselines.is_default=1` 读取，不再依赖 `settings.active_baseline_id`

### 5.2 `heats` API

影响接口：

- `GET /api/heats`
- `GET /api/heats/{id}`
- `GET /api/heats/{id}/curve`
- `GET /api/heats/{id}/compare`
- `POST /api/heats/{id}/analyze`
- `PATCH /api/heats/{id}`
- `POST /api/heats/{id}/resume-cutting`

计划改动：

- 列表摘要中的 `baseline_id / baseline_effective_from / deviation_percent / avg_deviation_percent / mismatch_duration_minutes` 改为从主 binding 投影
- 详情页使用的默认基线改为该炉次 `is_primary=1` 的 binding
- compare 接口返回的 `baselines[]` 改为由该炉次全部 binding 组装
- analyze 接口不再写回 `heats`，而是写回指定的 `heat_baseline_bindings`
- 如果 analyze 请求没显式给 `baseline_id`，默认分析 `is_primary=1` 那条 binding

### 5.3 `tasks` API

影响接口：

- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{id}`

计划改动：

- 任务快照来源改为“当前选中的 binding”
- 现有 `baseline_definition_id_snapshot（基线定义ID快照）`、`baseline_item_snapshot（版本号快照）` 可继续沿用
- 不需要新增绑定表外键，任务仍以快照方式留存即可

### 5.4 `settings` API

目标：

- 把“默认黄金基线”从设置项真源中移出

计划改动：

- `settings.active_baseline_id（当前激活基线ID）` 不再作为正式业务主链读写字段
- blank/factory-reset 仍可清这个历史 runtime 键，但不再依赖它决定默认黄金基线

---

## 6. 前端改造计划

### 6.1 基线相关页面

影响页面：

- `BaselineListView`
- `BaselineDetailView`
- `BaselineWizard`

计划改动：

- 基线列表与详情展示 `is_default（默认黄金基线）`
- 创建/编辑/发布流程支持设置或切换默认黄金基线
- 基线向导继续支持“可选来源炉次 + 全天预览选点”，不恢复对来源炉次的强依赖

### 6.2 炉次详情页

影响页面：

- `HeatDetailView`

计划改动：

- 默认展示 `is_primary=1` 的黄金基线
- 如果该炉次绑定多条黄金基线，前端只负责切换展示，不再自行推断哪条是主基线
- 详情页曲线数据只消费后端统一 compare 结果，不再自己拼旧来源

### 6.3 炉次列表/收件箱/看板

影响范围：

- 炉次浏览列表
- Dashboard 最近炉次
- 偏差相关摘要卡片

计划改动：

- 所有“基线ID / 偏离度 / 连续不一致时间”等摘要字段都从主 binding 口径输出
- 不再读取已经从 `heats` 移出的旧字段

---

## 7. 实施顺序

### Phase A：数据库与模型层

1. 修改 ORM 模型
2. 新增 `HeatBaselineBinding` 模型
3. 给 `Baseline` 增加 `is_default（默认黄金基线）`
4. 从 `Heat` 模型移除单基线绑定与分析结果字段
5. 更新 `docs/BACKEND_STRUCTURE.md`
6. 更新 schema 重建链路需要的测试与初始化逻辑

交付判定：

- 空库按当前模型可直接重建
- `factory-reset + blank` 后新库结构与当前代码一致

### Phase B：服务与持久化层

1. 增加 `heat_baseline_bindings` 的 CRUD/查询服务
2. 炉次固化时生成多条 binding
3. 默认黄金基线切换时收口唯一性
4. analyze 结果改写 binding，不再写 `heats`
5. compare 查询改为显式 join/拼装三张正式表

交付判定：

- 一条炉次可稳定绑定多条基线
- 主 binding 可稳定确定且唯一

### Phase C：API 层

1. 调整 baseline schema 与 endpoint
2. 调整 heat schema 与 endpoint
3. 调整 task 快照来源
4. 移除对 `settings.active_baseline_id` 的正式主链依赖

交付判定：

- 接口契约完整切到新表结构
- 历史炉次列表/详情/compare 返回口径一致

### Phase D：前端页面层

1. 基线页面展示/编辑默认黄金基线
2. 炉次详情默认展示主 binding
3. 多基线切换只消费后端返回
4. 列表/摘要页适配新的字段来源

交付判定：

- UI 不再依赖旧单基线字段
- 多基线详情默认显示逻辑清晰

### Phase E：重建验证与回归

1. 本地测试通过
2. `factory-reset + blank` 重建空库
3. 验证空白态与 schema
4. 再跑目标用户路径回归

---

## 8. 测试计划

### 8.1 后端测试

至少补以下测试：

- `baselines.is_default（默认黄金基线）` 的唯一性
- 仅 `published` 基线可设为默认黄金基线
- 炉次固化后可生成多条 `heat_baseline_bindings`
- `is_primary（主黄金基线）` 选择规则正确
- `GET /api/heats` 列表摘要从主 binding 投影正确
- `GET /api/heats/{id}` 与 `GET /api/heats/{id}/compare` 数据源一致
- `POST /api/heats/{id}/analyze` 结果写回 binding
- `POST /api/tasks` 快照取自当前选择的 binding
- `factory-reset + blank` 后 schema 为新结构

### 8.2 前端/用户路径验证

按 `docs/testing.md` 执行完整用户路径验证，重点覆盖：

1. 基线创建并发布为默认黄金基线
2. 历史炉次进入详情页后默认看到主黄金基线
3. 炉次绑定多条基线时可手动切换
4. 偏离度、连续不一致时间等摘要与详情一致
5. 空态、未分析态、错误态的展示正确

如本轮改动影响正式 UAT 判定路径，再更新：

- `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

---

## 9. 风险与注意事项

### 9.1 默认黄金基线唯一性

风险：

- 如果仍保留 `settings.active_baseline_id` 并继续参与读逻辑，会和 `baselines.is_default` 双真源冲突

控制：

- 本轮必须把正式读取统一收口到 `baselines.is_default`

### 9.2 历史炉次与运行态混读

风险：

- 如果历史详情仍允许回退旧 runtime / mirror store，会再次出现列表和详情不一致

控制：

- 历史正式炉次只允许查正式表

### 9.3 多基线后的缓存键

风险：

- `compare` 缓存如果仍按单 `baseline_id` 组织，会出现串缓存

控制：

- compare cache key 必须纳入 binding 集合与主 binding 信息

### 9.4 文档与测试同步

风险：

- 表结构和契约改了，但 `BACKEND_STRUCTURE / tests / UAT` 没同步，后续很快再漂

控制：

- 本轮必须把文档、单测、用户路径验证一起收口

---

## 10. 本轮执行清单

- [ ] 完成数据库模型重构
- [ ] 完成 `heat_baseline_bindings` 正式表
- [ ] 完成 `baselines.is_default（默认黄金基线）`
- [ ] 完成 `heats` 去单基线字段
- [ ] 完成服务层和持久化层改造
- [ ] 完成 `baselines / heats / tasks / settings` API 改造
- [ ] 完成前端页面适配
- [ ] 完成测试与 `factory-reset + blank` 验证
- [ ] 更新 `docs/BACKEND_STRUCTURE.md`
- [ ] 更新 `docs/progress.md`
- [ ] 如影响正式 UAT，则更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`

