# 服务器部署 / Bug 修复 / UAT 接力提示词

把下面整段提示词直接发给后续执行者使用。

```text
你现在接手 `D:\project\EDC electricity` 的服务器部署、线上回归、bug 修复和正式 UAT。不要先凭印象操作，先按仓库文档恢复上下文，然后在服务器完成“拉最新代码 -> 重部署 -> 验活 -> 修 bug -> 回归 -> 正式 UAT 留证”的完整闭环。

一、开始前必须先读
1. `D:\project\EDC electricity\AGENTS.md`
2. `D:\project\EDC electricity\docs\progress.md`
3. `D:\project\EDC electricity\docs\lessons.md`
4. `D:\project\EDC electricity\docs\testing.md`
5. `D:\project\EDC electricity\docs\DEPLOYMENT.md`
6. `D:\project\EDC electricity\docs\session_handoff.md`
7. `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`

二、先同步代码，不要直接测旧版本
1. 本地与服务器都切到 `master`
2. 执行 `git pull origin master`
3. 先记录当前 commit，后续所有测试结论都必须带 commit
4. 如果服务器工作树不干净，不要直接覆盖，先记录现状并说明

三、服务器部署必须先做完，再开始正式测试
1. 以 `docs/DEPLOYMENT.md` 为准，不要自创部署入口
2. 当前服务器优先入口：
   - `./scripts/sync-edc-server.sh`
   - `./scripts/publish-edc-web-and-asns.sh`
3. 部署后必须同时核对：
   - 后端服务已重启并加载最新代码
   - EDC 前端静态资源已切到新版本
   - ASNS 宿主已切到新版本，不是旧 dist / 旧 runtime
4. 至少完成以下验活：
   - `GET /health`
   - `GET /api/health`
   - `https://<host>/edc/` 可打开
   - `https://<host>/asns/` 可打开
5. 不能只看 health 就说“部署成功”，必须至少再核对：
   - 页面实际能打开
   - 静态资源路径/指纹已更新
   - 宿主页注入和宿主 host-api 正常

四、宿主神经网络 / 连线设置默认测试源 A
如果宿主连线设置页为空、掉线、要求重新填写，默认先填这组：

- EDC 地址：`http://60.251.229.32/`
- 用户名：`volapu`
- 密码：`admin`

执行顺序：
1. 打开宿主连线设置页
2. 填入上面的测试源 A
3. 执行“测试连接”
4. 执行“同步通道”
5. 执行“保存设置”
6. 再进入 EDC 页面继续验证

注意：
1. 这组值是默认测试源 A，不是切源场景里的测试源 B
2. 如果执行 `S04 / S05` 切源用例，测试源 B 仍按当次 release/dev 提供值执行

五、部署后先做一轮线上回归，不要一上来就修代码
至少先验证以下主路径：
1. 宿主首页可打开
2. 宿主连线设置页可打开
3. 测试连接成功
4. 同步通道成功
5. 从宿主进入 EDC 页面成功
6. Dashboard 正常
7. Heats 列表正常
8. Baselines / Baseline Definitions 页面正常
9. Settings 页面能看到正确运行态摘要

六、如果发现 bug，按这个顺序处理
1. 先写清：
   - 复现路径
   - 当前环境
   - 当前 commit
   - 预期
   - 实际
2. 如果是用户可见问题，先截图留证
3. 再定位根因
4. 修复后必须回归原路径，不能只补单测
5. 如果 bug 影响正式验收路径、中间态、错误态、图表、筛选、时间语义、状态机，必须检查并必要时更新：
   - `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`

七、测试与回归规则，必须严格遵守
1. 任何用户可见流程都必须按 `docs/testing.md` 的“完整用户路径验证规则”执行
2. 不允许只按代码路径验证
3. 必须覆盖：
   - 入口
   - 用户操作
   - 请求参数
   - 中间态
   - 成功态
   - 空态
   - 错误态
4. 只看 API 200、DOM 存在、按钮出现，不足以判定通过
5. 图表类问题必须肉眼确认图真的画出来

八、正式 UAT 必须按文档执行
1. 严格按 `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`
2. 每个交互步骤都要截图
3. 截图后必须回看
4. 必须输出 `PASS / FAIL / BLOCKED`
5. 不能把“后台测试通过”写成“UAT 通过”

九、本轮必须重点关注的链路
1. 宿主配置 EDC 源
2. 同步通道与业务角色绑定
3. 宿主 -> 通道 -> 数据 -> EDC -> 智慧熔炉链路是否打通
4. Dashboard 统计与运行态摘要
5. Heats 列表 / 详情 / freshness 状态机
6. Baseline Definitions / Baselines / 基线向导
7. 切源后旧配置、旧数据是否真正清空
8. 使用新源后是否重新采集、重新恢复业务链路

十、交付物要求
完成后必须给出：
1. 服务器环境
2. 测试使用的 commit
3. 是否已完成重部署
4. 重部署使用的命令
5. 验活结果
6. 修了哪些 bug
7. 回归覆盖了哪些路径
8. UAT 哪些用例 PASS / FAIL / BLOCKED
9. 截图目录和正式留证路径

十一、完成后必须更新的文档
1. `D:\project\EDC electricity\docs\progress.md`
2. `D:\project\EDC electricity\docs\session_handoff.md`
3. 如有新问题模式，更新 `D:\project\EDC electricity\docs\lessons.md`
4. 如正式验收路径或判定标准发生变化，更新 `D:\project\EDC electricity\docs\test-reports\UAT-EDC-ASNS-commercial-acceptance.md`

十二、禁止事项
1. 不要跳过服务器重部署，直接测旧版本
2. 不要只看 health 就宣称部署完成
3. 不要只做后台测试就宣称 UAT 通过
4. 不要漏掉截图和回看
5. 不要改了正式验收路径却不更新 UAT 文档
6. 不要忘记默认测试源 A：
   - `http://60.251.229.32/`
   - `volapu`
   - `admin`
```
