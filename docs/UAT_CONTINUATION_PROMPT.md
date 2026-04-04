# 后续测试 / UAT 接力提示词

把下面整段提示词直接发给后续执行者使用。

```text
你现在接手 EDC electricity 项目的后续测试与正式 UAT。先不要写代码，先按仓库规则恢复上下文、同步最新代码、完成服务器重部署，然后按“完整用户路径验证规则”执行全部测试与 UAT。除非发现明确根因并得到继续修改指令，否则先以测试、验证、留证和回归为主。

一、开始前必须先读这些文档
1. D:\project\EDC electricity\AGENTS.md
2. D:\project\EDC electricity\docs\progress.md
3. D:\project\EDC electricity\docs\lessons.md
4. D:\project\EDC electricity\docs\IMPLEMENTATION_PLAN.md
5. D:\project\EDC electricity\docs\testing.md
6. D:\project\EDC electricity\docs\session_handoff.md
7. D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md

二、先同步代码，再做任何测试
1. 在本地仓库执行 `git checkout master`
2. 执行 `git pull origin master`
3. 先确认本地工作树是否干净；如果不干净，不要覆盖已有改动，先记录并说明

三、如果测试目标包含服务器/线上环境，先完成重部署
1. 从 GitHub 拉到服务器上的最新 `master`
2. 按仓库当前部署方式完成前后端重新部署
3. 明确核对：
   - 前端静态资源已更新到本次最新版本
   - 后端服务已重启并加载最新代码
   - 宿主/反向代理指向的是这次新版本，而不是旧 dist 或旧 runtime
4. 至少验证：
   - `GET /health`
   - `GET /api/health`
   - 前端页面可正常打开
   - 宿主页面可正常打开
5. 不能只看 health，就判定“已部署成功”；要核对资源版本或页面实际行为

三点五、执行宿主神经网络/连线设置时，默认使用以下测试源 A
1. EDC 地址：`http://60.251.229.32/`
2. 用户名：`volapu`
3. 密码：`admin`
4. 若宿主连线设置页为空、未连接或要求重新登录，优先使用这组配置完成：
   - 测试连接
   - 同步通道
   - 保存设置
5. 若执行切源场景（S04 / S05），测试源 B 仍按当次 dev/release 提供值执行；不要把测试源 A 当成切源目标 B

四、测试执行规则，必须严格遵守
1. 不允许只按代码路径验证，必须按真实用户路径验证：
   - 入口
   - 操作
   - 请求参数
   - 中间态
   - 成功态
   - 空态
   - 错误态
2. 任何用户可见改动、状态机、图表、筛选、时间语义、跨系统联动，都必须按 `docs/testing.md` 执行
3. 任何影响正式验收结论的变化，都必须检查并必要时更新：
   - `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`
4. 如果没有完成这套验证，不得声称“已验证完成”或“已通过 UAT”

五、本轮测试重点，必须覆盖
1. 黄金基线向导 Step 2：
   - 整天真实曲线异步任务
   - 长耗时加载中提示
   - 禁止重复触发
   - 成功后出图
   - 失败后不可继续
2. 炉次浏览 freshness 状态机：
   - `ready / warming / refreshing_history / stale / error`
   - 旧快照不能再冒充“当前炉次实时态”
   - stale/error 时必须看到保护态提示
   - `realtime_current=true` 时才允许显示当前实时炉次语义
3. 进行中炉次：
   - 正常 freshness 下会自动刷新
   - stale/error 下改为旧快照提示，不继续伪装成当前实时

六、UAT 执行要求
1. 严格按 `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md` 执行
2. 每一步必须截图
3. 截图后必须回看，不接受“拍了但没检查”
4. 图表类用例必须肉眼确认曲线真的画出来，不能只看接口成功
5. stale/error 相关用例必须确认：
   - 页面是否有明确提示
   - 旧快照是否还在冒充“当前炉次实时态”
6. 若宿主链路未 ready，不要直接判页面 bug；先确认是否已按上面的测试源 A 完成宿主连线与通道同步

七、交付物要求
1. 输出测试结论时，必须说明：
   - 测试环境
   - 当前代码版本/commit
   - 是否已完成服务器重部署
   - 已执行哪些完整用户路径
   - 哪些 UAT 用例 PASS / FAIL / BLOCKED
2. 如果发现问题：
   - 写清复现路径
   - 写清预期 / 实际
   - 给出截图路径
   - 说明是否属于回归
3. 如有必要，更新：
   - `D:\project\EDC electricity\docs\progress.md`
   - `D:\project\EDC electricity\docs\session_handoff.md`
   - `D:\project\EDC electricity\docs\lessons.md`
   - `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`

八、如果你完成了修改或文档更新
1. 先自测
2. 再更新 progress / handoff / 必要的 UAT 文档
3. 然后提交到 `master`
4. 最后 `git push origin master`
```
