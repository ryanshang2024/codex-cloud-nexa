# 第一阶段实施与验证记录

验证日期：2026-10-10，当前云工作区 `/workspace/codex-cloud-nexa`。对象为 HVAC QC/ON MVP 的本地开发与 DEMO 闭环；不是生产部署或真实企业试点。

## 首次交付验证（本轮复验见文末）

| 检查 | 结果 | 证据与范围 |
|---|---|---|
| 后端 / PostgreSQL | **60 passed，0 failed，0 skipped** | `.local/pytest-results.xml`；最新运行 17:36 UTC，9.207 秒；真实 PostgreSQL、非超级用户应用角色、FORCE RLS |
| 浏览器 | **3 passed，0 failed，0 flaky** | `.local/browser-results.json`；DEMO 研究至 CRM、390px 手机布局、跨站写入拦截；已有 Chromium |
| 前端构建 | **passed** | `npm run build`，生产编译及 TypeScript 检查；独立 `npm run typecheck` 也通过 |
| 生产 npm 依赖检查 | **0 reported vulnerabilities** | `npm audit --omit=dev`；仅代表当日 advisory 数据库结果 |
| 可重复 DEMO | **passed，连续重复通过** | `.local/demo-results.json`；真实 HTTP + PostgreSQL；同 job / reply 幂等，不重复创建商机 |
| 初始化与启动 | **passed** | 实际执行 `scripts/install.sh`；`scripts/dev.py init/up/down/up`，迁移与 HTTP 就绪检查；保留数据库 |
| 云配置草稿 | **已保存并读回确认** | revision 3，安装脚本 / start skill 与已验证文本一致；保留仓库与 package_managers 网络 preset，追加参考/API 域名 |
| 发送锁定 | **passed** | DEMO / API 请求始终 HTTP 423；不存在自动营销发送器 |

自动检查包括 20 种画像/省份组合、Unknown/过期/错误省份、评分理由与覆盖、H10、退订、独立联系人依据、FR/EN、审批失效、重复研究后的证据复用、数据库隔离与不可变审计、队列租约与限额、供应商失败/回退、签名/重放、结构化 AI 输出拒绝、CSV 公式防护、删除后退订抑制保持。供应商契约和故障测试使用可控响应，不能计为真实 API 成功。

测试日志有 Starlette TestClient 的 httpx 弃用提示和浏览器工具的颜色环境提示；没有测试失败。未来升级测试依赖时应复查兼容性。

## 实际演示

- QC / H01：已核验 **DEMO** 样本 Fit 100，法语草稿，模拟人审，PRICE_REQUEST → 报价任务与商机。
- ON / H06：已核验 **DEMO** 样本 Fit 100，英语草稿，PROJECT_AVAILABLE → 待人工核实的 Project、任务与商机。
- 每组还包含资质 Unknown 与仅雇员样本，用于展示 Review / Excluded。
- 导出 6 个 DEMO 主体；它们的虚构资料和 `.example` 地址不代表真实客户。
- **真实供应商调用 0；发送消息 0。** 演示审批由脚本模拟，不构成真实业务/合规审批。

VI 工作台截图：[桌面](previews/workspace-desktop.png)、[手机](previews/workspace-mobile.png)、[CRM](previews/workspace-crm.png)。截图反映模拟数据，重复研究/演示会改变草稿、任务计数；计数不是业务 KPI。

## 源码和许可审查

Lead-Researcher 固定提交源码审查完成，缺独立 LICENSE，因此未复制代码或执行 installer/loop。Firecrawl server/SDK、Apify client、n8n 根许可及基础依赖已按 [审查记录](reference-audit.md)检查。没有运行未审查的外部安装脚本。n8n JSON、OpenAI Academy Sales Workflow 和 Google 当前政策页面被运行时代理拦截，保持 **unverified**。

## 尚未执行的外部验收

1. 发布/应用新网络配置后，取得 n8n 工作流 JSON、官方 Terms/实时价格/配额，并完成 SourcePolicy 的合规审批。
2. 通过环境设置绑定可选 `GOOGLE_PLACES_API_KEY`、`FIRECRAWL_API_KEY`、`APIFY_API_TOKEN`、`NEXA_OPENAI_API_KEY`；当前无已保存密钥绑定。全部真实来源默认禁用，OpenAI 开关建议值为 false。
3. 各供应商真实授权操作、真实 OpenAI 模型输出质量与费用核对；DEMO 不调用付费接口。
4. NEXA 产品、价格/合作政策、发件主体、CASL 依据、QC/ON 工作类别资质规则和隐私保留政策；未知内容没有生成事实声明。
5. QC/ON 各两城、合计 50 家真实企业人工抽样；生产 OIDC/每用户会话、部署、监控和备份恢复。
6. 环境配置发布后在新任务中恢复验证；当前只确认本工作区和草稿，不能宣称已发布快照或新任务验证通过。

源码尚未提交/推送 GitHub。原远端为空，尚无 main commit；草稿仓库绑定显示 HEAD。用户发布环境快照与将源码推送仓库是不同操作。源代码归档包含必要源文件、锁文件、项目 Skills、文档和截图，不包含 `.local`、数据库、运行凭据或依赖目录。

完整验收门槛见 [acceptance.md](acceptance.md)，可复用启动说明见 [cloud-start.md](cloud-start.md)。第一阶段交付状态为 **可运行 DEMO MVP；真实接入和上线验收待外部前提**。

## 用户 0/100 反馈后的整改复验

按 [六项验收对照](acceptance-scorecard.md)复查，发现并修复具体画像证据缺失、未知采购权绕过、负面/错类别资质证明、到期状态展示及手机画像页溢出。修复前真实观察到 12 + 3 个后端回归用例失败，以及手机 ICP 溢出检查失败；上一轮测试没有覆盖这些条件。

补充 25 项后端验收回归用例后，**85 passed / 0 failed / 0 skipped**（18:15 UTC，11.641 秒）；前端生产构建再次通过。浏览器 3 项的最终状态及精确时间以 [只读证据快照](acceptance-evidence.json)为准，手机测试包含画像条件展示与页面宽度检查。DEMO HTTP 演示再次通过，真实 API 调用与营销发送均为 0。

真实工作租户账户数为 0，各真实来源关闭；独立人工验收样本尚未提供。用户评分保留 **0/100**，复评总分、ICP 精准率、数据准确率、真实 AI 研究准确率均为 null。只有真实验收数据与明确判分规则能够决定业务得分，测试数量不转换为分数。

## 发布前复验

用户随后确认“验证完后发布到 GitHub main 源码”。已再次运行 85 项后端测试、Next 生产构建、3 项浏览器测试、服务重启和 DEMO，均通过；最新证据时间与公开发布范围见 [release.md](release.md)。首次交付时尚未提交/推送的历史记录不代表本次发布状态。原始附件和 PRD 提取文本不纳入公开 GitHub 版本。

## 第二轮验收（继续验收）

起点为已发布的 cf7f359。在隔离租户中添加 29 项边界检查，观察 27 failed / 2 passed，再修复：退订语句优先级、入站证据/来源用途、冲突事件/任务幂等、草稿精确引用、完成合作证明、预调用策略/费用复查。正负例、旧任务兼容性与默认预算规范化扩展后，新后端用例为 39 项，完整 **124 passed / 0 failed / 0 skipped**，18:41:23 UTC 开始，14.202 秒。

浏览器先复现审批提示不在弹窗，再用截图及 `toBeInViewport` 复现长草稿列表使提示不可见。现在提示使用中文、出现在弹窗内、失败时滚回可视位置；联系依据审批标签与草稿审批分开。完整浏览器 **4 passed / 0 unexpected / 0 flaky**，生产构建/TypeScript、服务重启、QC FR / ON EN 演示均通过；时间戳见 [acceptance-evidence.json](acceptance-evidence.json)。

[审批错误截图](previews/workspace-approval-error.png)使用控制的 409 响应展示已通过后端回归检查的失效引用情形。截图、浏览器和供应商故障响应均不能计为真实来源或真实客户证据。发送仍 HTTP 423，用户评分保持 0/100，正式业务验收待真实样本与完整能力验证。

## 域名发布准备检查

新增 Next Proxy 标准 HTTP Basic 保护，默认 private_demo 未配置凭据时拒绝访问；域名规范化、公开同源检查及本地显式 local 启动模式已验证。部署访问检查在改动前 4 failed / 1 passed，改动后 **5 passed**；全部 PostgreSQL **124 passed**、本地浏览器 **4 passed**，生产构建/TypeScript、保留数据的服务重启与 DEMO 通过。没有实际外部 API 或营销发送。

这些是本地构建的 HTTP/Host/认证检查，不是域名 HTTPS 验收。目标站点访问被当前代理 CONNECT 403 拦截；DNS、证书及远端运行版本未取得证据，托管/DNS 身份未配置。[实际部署](domain-deployment.md)保持待执行，网络草稿保存后还需要环境设置的审核、保存和发布才能应用。
