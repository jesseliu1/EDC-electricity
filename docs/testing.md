# 测试说明

## 目标

- 统一前后端测试口径
- 明确正式测试留存与临时调试证据的边界
- 为 EDC / ASNS 这类用户可见流程建立可追溯、可复盘、可回看的正式测试闭环

## UAT 定义

UAT = 用户接受测试。

本项目中的 UAT 不是只验证“页面能不能打开、按钮能不能点”，而是验证：

- 所有关键功能是否达到商业使用要求
- 关键用户流程是否能在真实业务链路下成立
- 系统在切源、重配、空态、错误态、重新采集等关键状态切换时是否仍符合预期

## 当前项目的最低 UAT 覆盖范围

凡声称“本轮已完成 UAT / 可商用验收 / 用户流程通过”，至少要覆盖以下范围：

1. 宿主系统相关配置与切源行为
2. 神经系统宿主通道绑定
3. 数据链路是否打通（宿主 -> 通道 -> 数据 -> EDC -> 智慧熔炉）
4. 切换 EDC 后台源后，旧配置是否清空
5. 切换 EDC 后台源后，前台旧数据是否清空
6. 是否基于新源重新收集、重新采集数据
7. 智慧熔炉相关功能是否基于新链路正常工作
8. 所有面向商业使用的关键用户流程是否符合预期

限制：

- 如果只覆盖了“页面可打开 / 可点击 / 某个 API 返回 200”，不能称为完整 UAT
- 如果只覆盖局部链路或中间态，应明确标注为“定向验证 / 子链路验证 / 非完整 UAT”

## 完整用户路径验证规则

本节是“改完代码后必须怎么测”的执行规则，不是建议项。

### 1. 适用触发条件

以下任一条件成立，本轮修改完成后必须执行完整用户路径验证：

- 改动影响用户可见页面
- 改动影响按钮、表单、弹窗、跳转、筛选、分页、图表、提示文案
- 改动影响前后端接口契约
- 改动影响时间、时区、状态机、中间态或空态/错误态
- 改动影响宿主 -> 通道 -> 数据 -> EDC -> 智慧熔炉链路中的任一环节
- 计划把本轮结果作为“可开始 UAT / 可验收 / 可交付”的依据

### 2. 强制执行顺序

每次验证都必须按以下顺序记录，不允许跳步：

1. 写清楚用户从哪里进入页面
2. 写清楚用户实际会执行哪些操作
3. 写清楚页面会发哪些关键请求
4. 写清楚用户在中间态应该看到什么
5. 写清楚用户在成功态应该看到什么
6. 写清楚用户在空态/失败态应该看到什么
7. 再开始实际验证

不允许先看代码、先看接口 200、先看组件渲染，再反推“用户应该没问题”。

### 3. 最低验证深度

完整用户路径验证至少要同时覆盖以下四层：

- 用户入口：页面入口、前置条件、导航路径
- 用户操作：点击、填写、切换、确认、刷新、等待
- 请求链路：实际请求参数、返回结果、关键状态字段
- 页面结果：用户肉眼可见的文案、图表、空态、错误态、进行中状态

以下做法都不足以作为完整验证：

- 只验证 API 200
- 只验证某个 store/函数返回值
- 只验证 DOM 存在
- 只验证按钮出现
- 只验证静态 UI 结构变了

### 4. 状态覆盖要求

只要页面存在异步取数或后台准备过程，必须至少覆盖：

- loading / warming / preparing
- success / ready
- empty
- error / failed

只有 `ready + empty` 才能判定为真实空态。
任何 `warming / refreshing / running` 都必须单独验证为“准备中”状态，不能直接当成“没有数据”。

### 5. 请求参数核对要求

对以下字段，必须把“前端实际发了什么”和“后端实际如何解释”对齐验证：

- 日期
- 时间
- 时区
- 分页
- 排序
- 状态筛选
- source / baseline / heat 等关键业务 ID

只要用户路径依赖这些字段，就不能只看最终页面结果，必须补请求级验证。

### 6. 回归要求

每次修复 bug 后，必须至少形成一条防回归结论：

- 本次修复覆盖的是哪条用户路径
- 之前错在哪个状态或参数
- 现在如何证明该路径不会按原方式再次失败

如果项目内已有正式 UAT 用例覆盖该路径，则应更新该用例；
如果没有，则必须新增 UAT 用例或明确登记为“非 UAT 路径”。

### 7. 文档联动规则

以下任一情况成立，必须同步更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`：

- 新增了用户可见主路径
- 修改了已有主路径步骤顺序
- 修改了主路径中的前置条件、页面状态、判定标准、证据要求
- 修复了正式 UAT 已覆盖路径中的缺陷
- 新增了中间态、空态、错误态，且这些状态需要成为正式验收内容

不允许出现“代码已变，UAT 脚本仍按旧路径判断”的状态。

### 8. 可执行检查清单

每次代码修改完成后，至少要自检以下项目：

- [ ] 是否写清楚了本轮要验证的完整用户路径
- [ ] 是否覆盖了入口、操作、请求、结果四层
- [ ] 是否覆盖了 loading / success / empty / error 或等价状态
- [ ] 是否核对了关键请求参数与后端解释方式
- [ ] 是否补了防回归验证
- [ ] 若影响正式 UAT，是否更新 `docs/test-reports/UAT-EDC-ASNS-commercial-acceptance.md`
- [ ] 是否在 `docs/progress.md` 记录了本轮验证口径或 UAT 变更

### 9. 推荐记录模板

```markdown
## 用户路径
1. 进入页面：
2. 执行动作：
3. 关键请求：
4. 预期中间态：
5. 预期成功态：
6. 预期空态/错误态：

## 实测记录
- 实际请求参数：
- 实际响应摘要：
- 页面实际展示：
- 与预期差异：

## 回归结论
- 是否完成完整路径验证：
- 是否覆盖关键状态：
- 是否需要更新 UAT：
```

## 测试分类判定规则

### 1. 纯后台测试

适用范围：

- API
- service
- 数据处理
- 后端单测 / 集成测试
- 非用户可见界面问题

要求：

- 不强制要求每一步留图
- 以测试脚本、断言、日志、结果摘要为主
- 如果结论不依赖视觉展示，不需要按 UAT 方式做截图回看

PASS 判定：

- 脚本执行通过
- 断言通过
- 日志与结果符合预期

### 2. 正式 UAT / 用户实际流程用例测试 / 前端交互 / 视觉相关测试

适用范围：

- 用户真实操作路径
- UAT
- 面向商业使用的关键流程验收
- 前端交互测试
- 页面跳转与流程联动
- 图表
- 状态展示
- 页面展示正确性
- 报错提示
- 用户可见主路径验收
- 宿主 -> 通道 -> 数据 -> EDC -> 智慧熔炉这类跨系统链路验收
- 涉及点击、提交、导航切换、弹窗开合、Tab 切换、筛选切换的用户操作链路

要求：

- 强制要求留图
- 强制要求截图后回看
- 强制要求所有交互操作都截图留存
- 不允许只截关键步骤或关键点击
- 截图序列必须能完整还原用户操作路径
- 强制要求测试脚本 + 截图目录 + 回看结论 + 留存文档
- 脚本通过与截图回看通过缺一不可

PASS 判定：

- 脚本执行通过 / 页面行为符合预期
- 截图回看通过
- 两层同时成立才可判定 PASS

### 3. 哪些场景必须判入正式 UAT

以下任一条件成立，必须归入正式 UAT，不能降级成普通前端回归：

- 用户报告的问题属于“页面看起来不对”“图没有出来”“提示不对”“跳转后页面不对”
- 结论依赖用户实际看到的界面，而不只是接口返回值
- 需要证明图表、状态色、错误态、空态、按钮反馈、布局或文案是否正确
- 复现路径包含多个用户交互步骤，且用户会按这个路径实际操作
- PM、QA、用户明确要求“留图”“回看”“逐步验证”“形成正式留存”
- 发布前 / 回归时要对视觉类 bug、UAT 类 bug 给出可审计证据

以下情况通常不强制归入正式 UAT：

- 纯 API
- 纯 service / 数据处理
- 后端单测 / 集成测试
- 结论完全由断言、日志、返回值决定且不依赖用户可见界面

### 4. 临时调试证据

适用范围：

- 临时排查
- 一次性日志抓取
- 临时脚本输出
- `/tmp` 下的中间文件
- 尚未整理成正式测试资产的探索性证据

要求：

- 可以用于分析
- 不能直接替代正式测试留存

限制：

- 不能把临时调试证据当作正式 PASS 依据
- 如需用于对外汇报，必须转存到正式测试目录并补齐脚本、截图、回看与摘要

## 正式 UAT 截图规范

适用范围：

- 当前与后续同类 EDC / ASNS 用户测试问题
- 尤其是“切换 EDC 服务器后组信息未清空”“智慧熔炉提示数据没有取到”“图表不显示”“页面提示是否正确”这类问题

### 1. 每个测试用例都必须留图

- 不允许只跑脚本不留图
- 不允许只留最终一张图
- 关键路径必须有过程图

### 2. 用户实际流程 / UAT / 前端交互 / 视觉相关测试中，所有交互操作都必须截图留存

“所有交互操作”包括但不限于：

- 点击
- 提交
- 导航切换
- Tab 切换
- 筛选切换
- 弹窗打开
- 弹窗确认 / 关闭
- 列表项展开 / 收起
- 用户显式触发的刷新或重试

要求：

- 不允许只截关键步骤
- 不允许只截关键点击
- 截图序列必须能完整还原用户操作路径
- 每次交互前后的页面状态都要可追溯
- 至少应覆盖进入前、每次交互后、页面跳转后、结果态、报错态
- 截图文件名必须反映步骤顺序与动作含义

### 3. 截图完成后必须回看

- “回看”是正式步骤，不是默认假设
- 不允许把“截图文件存在”视为“已回看”

必须记录：

- 回看结论：通过 / 不通过 / 异常
- 回看依据：图中看到了什么、没看到什么

### 4. 测试通过必须同时满足两层

- 脚本执行通过 / 页面行为符合预期
- 截图回看通过

任何一层不成立，都不能算 PASS。

### 5. 所有正式用户测试用例都要有正式测试脚本覆盖

- 不接受只靠临时手工操作作为最终留存
- 脚本必须对应用户真实操作路径

### 6. 正式测试文件必须同时包含

- 测试脚本
- 截图目录
- 必要的 evidence / 结果摘要
- 回看结论
- 用例说明：测什么、预期什么、实际结果什么

### 7. 测试产物命名与目录必须稳定可追溯

必须能从目录直接看出：

- 日期
- issue
- 环境
- 步骤

限制：

- 不允许只放 `/tmp` 作为正式留存

### 8. 视觉正确性问题必须把截图回看作为强制门槛

适用问题：

- 图表
- 状态展示
- 页面展示
- 报错提示

限制：

- 不能只用 API 200 替代视觉结论
- 不能只用 DOM 存在替代视觉结论
- 不能只用 `data-attr` 替代视觉结论
- 不能只用 runtime series count 替代视觉结论

### 9. 测试汇报必须同时给出

- 对应测试脚本路径
- 对应截图目录
- 回看结论
- 为什么确认回看是正确的
- 最终 PASS / FAIL 判断依据

### 10. 必须区分“临时调试证据”和“正式测试留存”

- 临时调试证据可以帮助定位问题
- 正式测试留存必须可长期回看、可用于追责与复盘

## screenshot-review.json 规范

### 1. 目的

- 把“截图回看”从口头描述变成可审计步骤
- 让每一张截图都能对应到具体交互、具体观察结果和最终判定

### 2. 最小 schema

正式 UAT 必须产出 `screenshot-review.json`，至少包含以下字段：

```json
{
  "version": "1.0",
  "issue": "edc-server-switch-stale-groups",
  "environment": "public",
  "script_path": "apps/web/e2e/asns-edc-server-switch-investigation.spec.ts",
  "screenshot_dir": "docs/test-reports/assets/2026-03-27-edc-server-switch-stale-groups/public",
  "reviewed_at": "2026-03-27T14:20:00Z",
  "overall_result": "fail",
  "review_method": "manual-image-review-plus-dom-cross-check",
  "screenshots": [
    {
      "file": "01-home-before-open-settings.png",
      "step": "进入宿主页",
      "action": "goto",
      "review_result": "pass",
      "observed": ["看到了宿主页入口和导航"],
      "missing": []
    },
    {
      "file": "02-after-click-settings.png",
      "step": "点击连线设置后",
      "action": "click",
      "review_result": "fail",
      "observed": ["当前 EDC 来源为新服务器", "已添加通道仍显示旧组信息"],
      "missing": ["未看到按新服务器重置后的通道组"]
    }
  ]
}
```

### 3. MUST 字段

- `version`
- `issue`
- `environment`
- `script_path`
- `screenshot_dir`
- `reviewed_at`
- `overall_result`
- `review_method`
- `screenshots`

每个 `screenshots[]` 项必须包含：

- `file`
- `step`
- `action`
- `review_result`
- `observed`
- `missing`

### 4. 字段约束

- `overall_result` 只能为 `pass` / `fail` / `exception`
- `review_result` 只能为 `pass` / `fail` / `exception`
- `action` 应使用可审计动作词，例如 `goto` / `click` / `submit` / `nav-switch` / `tab-switch` / `modal-open`
- `observed` 必须写明图中确实看到了什么
- `missing` 必须写明图中应看到但没有看到什么；若无缺失，允许为空数组
- 路径必须使用仓库内稳定路径，不得指向 `/tmp`

### 5. SHOULD 字段

可按需要补充：

- `expected`
- `actual`
- `why_correct`
- `dom_assertions`
- `api_context`
- `reviewer`

## 回归测试证据要求

### 1. 视觉 / UAT 相关 bug 的回归不能只靠接口通过

以下任一类 bug 的回归，不能只用 `curl`、API 200、日志正常或脚本断言通过代替 UAT 通过：

- 图表不显示
- 状态展示错误
- 页面提示错误
- 跳转后页面不对
- 用户明确以截图或页面观感报出的 bug

### 2. 视觉 / UAT 相关 bug 的回归必须同时提供

- 回归测试脚本
- 回归截图目录
- `screenshot-review.json`
- 留存文档 / 结果摘要
- PASS / FAIL 判定依据

### 3. 回归判定规则

- 如果 bug 定义本身是用户可见行为，则回归通过必须包含 UAT 证据
- `curl` / API / 日志 / DOM 断言可以作为辅助证据
- 这些辅助证据不能替代截图回看通过

## 正式测试资产核对清单

### MUST

- 有正式测试脚本
- 有正式测试报告或正式留存文档
- 有稳定截图目录
- 有 `screenshot-review.json`
- 所有交互操作均已截图留存
- 截图序列能完整还原用户路径
- 已执行截图回看
- 回看结论写明“看到了什么 / 没看到什么”
- 汇报时包含脚本路径、截图目录、回看结论、回看正确性依据、PASS / FAIL 依据
- 正式资产不存放在 `/tmp`

### SHOULD

- 结构化 evidence 单独存为 `evidence.json`
- 留存文档写明环境、预期、实际、根因或怀疑点
- 关键截图文件名能直接看出步骤和动作
- DOM / API / 日志辅助证据与截图回看交叉校验
- 回归测试沿用同一条正式测试脚本或其稳定变体

## 正式测试资产目录规范

正式测试留存统一放在：

- `docs/test-reports/`
- `docs/test-reports/assets/`

推荐结构：

```text
docs/test-reports/
  2026-03-27-edc-server-switch-stale-groups-investigation.md
  assets/
    2026-03-27-edc-server-switch-stale-groups/
      public/
        01-before-open-settings.png
        02-after-open-settings.png
        03-after-change-endpoint.png
        04-after-test-connection.png
        05-after-open-edc-app.png
      evidence.json
      screenshot-review.json
```

命名约定：

- 报告文件：`YYYY-MM-DD-issue-environment-purpose.md`
- 资产目录：`YYYY-MM-DD-issue-keywords/`
- 截图文件：`NN-action-result.png`
- 结构化证据：`evidence.json`
- 截图回看结果：`screenshot-review.json`

## 正式测试文件清单

一个正式测试问题至少应包含：

1. 测试脚本
2. 测试报告
3. 截图目录
4. 结构化 evidence
5. 截图回看结论

建议在测试报告中明确写出：

- 用例编号 / 用例名称
- 测试环境
- 复现路径
- 预期行为
- 实际行为
- 根因结论或当前怀疑点
- 关联脚本路径
- 关联截图目录
- 关联 evidence 路径

## 当前覆盖

### 前端

- `pnpm --dir apps/web test`
  - Vitest 组件/设计令牌单测
- `pnpm --dir apps/web test:i18n`
  - 多语言 key 结构一致性检查
  - 多语言占位符一致性检查
- `pnpm --dir apps/web test:e2e`
  - Playwright 浏览器回归
  - 覆盖 Dashboard、基线定义、基线向导、炉次列表、炉次详情手动调整、任务、报表、收件箱、系统设置
- `pnpm --dir apps/web build`
  - 类型检查与生产构建验证
- `pnpm --dir apps/web lint`
  - 前端静态检查

### 后端

- `uv --directory apps/server run pytest`
  - 后端单测 / 集成测试
- `uv --directory apps/server run ruff check tests`
  - 测试目录静态检查

## 后端 pytest 数据库隔离

- `apps/server/tests/conftest.py` 现在会在导入 `src.*` 之前，先把 pytest 进程的 `ASNS_DATABASE_URL` 切到独立 SQLite 测试库。
- 默认情况下，pytest 会自动生成独立测试库路径，不再落到 `apps/server/data/asns.db`。
- 如需固定测试库路径，使用环境变量 `ASNS_TEST_DB_PATH`；`conftest.py` 会把它转换成测试用 `ASNS_DATABASE_URL`。
- 如果有人显式把 pytest 指到共享联调库 `apps/server/data/asns.db`，pytest 会在加载 `conftest.py` 时直接失败，禁止继续执行。

安全命令：

- `uv run --directory apps/server pytest`
- `$env:ASNS_TEST_DB_PATH='D:\\project\\EDC electricity\\apps\\server\\.pytest-db\\local.db'; uv run --directory apps/server pytest`
- `uv run --directory apps/server pytest -q tests/test_api_edge_cases.py -k dashboard_invalid_duration_returns_422`

仍然禁止在联调环境跑的命令：

- `ASNS_DATABASE_URL=sqlite+aiosqlite:///./data/asns.db uv run --directory apps/server pytest`
- 任何把 pytest 直接指向 `D:\\project\\EDC electricity\\apps\\server\\data\\asns.db` 的命令
- 在联调环境直接执行会清空或重建共享库的命令，例如 `python -m src.runtime_state_admin --db apps/server/data/asns.db --mode factory-reset`

## 一键执行

仓库根目录可直接运行：

```powershell
.\scripts\check-all.ps1
```

Linux / macOS / Codex cloud 可运行：

```bash
./scripts/check-all.sh
```

如果只想跳过前端 E2E：

```powershell
.\scripts\check-all.ps1 -SkipE2E
```

```bash
./scripts/check-all.sh --skip-e2e
```

## 云端 CI

仓库已配置 GitHub Actions 工作流：

- `.github/workflows/ci.yml`

触发时机：

- 推送到 `master`
- 推送到 `codex/**` 分支
- 任意 Pull Request

云端会自动执行以下检查：

### 前端

- `pnpm lint`
- `pnpm test:i18n`
- `pnpm build`
- `pnpm test`
- `pnpm test:e2e`

失败时会上传 Playwright 产物：

- `apps/web/playwright-report`
- `apps/web/test-results`

### 后端

- `uv sync --all-extras`
- `uv run ruff check tests`
- `uv run pytest`

## Codex Cloud

如果要把测试任务交给 Codex cloud，建议为仓库环境配置以下 setup script：

```bash
set -e

corepack enable
corepack prepare pnpm@10 --activate

cd apps/web
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps chromium

cd ../server
python -m pip install --upgrade pip
python -m pip install uv
uv sync --all-extras
```

环境准备完成后，Codex cloud 可直接执行：

```bash
./scripts/check-all.sh
```

如果只想先做快速回归，可执行：

```bash
./scripts/check-all.sh --skip-e2e
```

## 维护约定

- 新增页面主流程时，优先补 Playwright 用例
- 新增或修改国际化文案 key、占位符时，必须保证 `pnpm --dir apps/web test:i18n` 通过
- 新增 API 时，至少补成功路径和一组边界路径
- 使用全局 in-memory store 的后端模块，测试必须保证状态隔离
- 云端 CI 与本地 `.\scripts\check-all.ps1` / `./scripts/check-all.sh` 保持同一套检查口径，新增测试时两边都要同步
- 对用户可见主路径的正式 UAT，不得只交付日志或命令输出，必须交付可回看的正式测试资产

## 2026-04-17 fixed_interval 锚点硬切回归

本轮炉次切割重构后，固定间隔模式的最小安全回归命令如下。

后端：

```powershell
$env:ASNS_TEST_DB_PATH='D:\project\EDC electricity\apps\server\.pytest-db\fixed-cutting.db'
& 'D:\project\EDC electricity\apps\server\.venv\Scripts\python.exe' -m pytest -q `
  'D:\project\EDC electricity\apps\server\tests\test_heat_cutting_service.py' `
  'D:\project\EDC electricity\apps\server\tests\test_heat_stream_processor.py'
```

```powershell
$env:ASNS_TEST_DB_PATH='D:\project\EDC electricity\apps\server\.pytest-db\fixed-cutting.db'
& 'D:\project\EDC electricity\apps\server\.venv\Scripts\python.exe' -m pytest -q `
  'D:\project\EDC electricity\apps\server\tests\test_heats_api.py' `
  -k 'supports_fixed_interval_cutting_mode_on_bootstrap or reuses_frozen_cutting_config_after_first_birth or live_heat_context_cache_key_changes_with_cutting_mode_and_fixed_interval'
```

```powershell
$env:ASNS_TEST_DB_PATH='D:\project\EDC electricity\apps\server\.pytest-db\fixed-cutting.db'
& 'D:\project\EDC electricity\apps\server\.venv\Scripts\python.exe' -m pytest -q `
  'D:\project\EDC electricity\apps\server\tests\test_heat_replay_api.py' `
  -k 'create_replay_job_runs_to_completion_and_replaces_range or replay_job_fixed_interval_uses_anchor_timeline_boundaries or replay_job_rebuilds_processor_snapshot_for_live_continuation'
```

前端：

```powershell
npm.cmd --prefix 'D:\project\EDC electricity\apps\web' run test -- src/__tests__/setting-store.test.ts
```

本组回归重点检查：

- `fixed_interval` 是否按显式 anchor_time 生成理想切点，而不是从活跃段首点起算
- 容忍窗口内是否会吸附到活跃结束点
- 容忍窗口内找不到候选时是否回退理想切点
- live runtime / replay batch / replay head rebuild 是否共用同一套 fixed 语义
- 设置页在空值或默认加载时是否展示 `fixed_interval + 30`
