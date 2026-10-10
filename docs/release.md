# V3.2 DEMO 源码发布记录

日期：2026-10-10。用户确认发布目标为 `ryanshang2024/codex-cloud-nexa` 的 GitHub `main` 分支。仓库为公开仓库；本次交付是源码和开发验证记录，不是公开网站部署或正式业务验收通过。

## 首次发布前验证

| 验证 | 结果 |
|---|---|
| 后端 / 真 PostgreSQL | 85 passed，0 failed，0 skipped；18:25:23 UTC，11.526 秒 |
| Next.js 生产构建 / TypeScript | passed |
| 浏览器完整工作流、手机 ICP、跨站写入拦截 | 3 passed，0 unexpected，0 flaky；18:26:40 UTC 开始 |
| 项目服务重启 / HTTP 就绪 | passed，保留 PostgreSQL 数据 |
| QC H01 法语 / ON H06 英语 DEMO | passed；发送请求始终 HTTP 423 |
| 真实账户 / 真实供应商调用 / 消息发送 | 0 / 0 / 0 |

可复现命令与源码范围见 [README](../README.md)，只读数据见 [acceptance-evidence.json](acceptance-evidence.json)。用户给定 0/100 是保留的验收基线；本次源码发布不改变该分数。

## 发布内容与排除项

发布应用源码、数据库迁移、画像配置、七个项目 Skills、依赖锁文件、自动化测试、自有初始化/启动脚本、架构/验收/参考审查文档和 DEMO 截图。

不发布 `.local` 的凭据/数据库/日志、`.venv`、node_modules、构建缓存、`.env` 文件、原始上传附件、PRD 提取全文或原始 Starter 文档。它们继续留在当前工作区；`.gitignore` 明确排除。提交前检查 staged 文件与本地生成的运行凭据，不能仅凭未跟踪状态认为已隔离。

## 发布后仍需完成

真实多源研究串联、完整 AI 语义研究、50 家真实主体独立人工验收、生产登录/部署、来源与业务合规签核仍未完成，详见 [六项验收对照](acceptance-scorecard.md)。所有真实来源默认关闭，营销发送器不存在。GitHub 源码发布不应用或发布 Codex 云环境配置草稿，也不证明新任务快照恢复通过。

发布提交可在 [main 提交记录](https://github.com/ryanshang2024/codex-cloud-nexa/commits/main)查看。推送不使用 force；发布后核对本地 HEAD 与远端 refs/heads/main，确认一致。

## 第二轮验收与修复发布

2026-10-10，按用户“继续验收”复查回复、草稿审批、伙伴激活及队列授权边界。修复前 29 项新增后端检查有 27 项失败；审批错误展示也在浏览器和截图中复现。触发条件与最终行为见 [整改对照](acceptance-scorecard.md)。

- 后端：**124 passed / 0 failed / 0 skipped**，18:41:23 UTC 开始，14.202 秒；新增 39 项有正例、负例与旧任务兼容性检查。
- 前端生产构建和 TypeScript：通过。浏览器：**4 passed / 0 unexpected / 0 flaky**，包括审批错误在弹窗视口内显示和两类审批标签区分；精确时间见证据 JSON。
- 数据保留的服务重启、QC H01 / ON H06 HTTP DEMO：通过；发送仍为 423，真实客户 / 供应商调用 / 消息发送仍为 0 / 0 / 0。
- 本轮继续发布到既定 GitHub main 源码目标。没有新增依赖、DDL 迁移、外部安装脚本或发送器；SearchJob 请求指纹和第一合作事件约束使用既有 JSONB，旧任务支持精确重试。

规则回复分类和固定模板仍有能力边界；真实多源自动研究串联、完整 AI 语义研究、生产身份与独立 50 家试点仍未完成。本轮通过的是受控开发检查，用户基线 0/100 保留，复评分数和真实准确率仍为 null。

## 指定域名的发布准备（域名尚未上线）

用户随后指定 `https://nexa-mk.voltwok.com/`。已在源码中补充私有 DEMO 的 HTTP Basic 访问保护和标准化域名配置，防止匿名访客获得 BFF 共享后台身份；未配置登录默认 503，未登录 401，公开模式不接受 localhost Origin 例外。本地启动器明确选择 loopback local 模式，公开运行默认 private_demo。没有新增软件依赖或数据库迁移。

部署访问检查先复现 4 failed / 1 passed，修复后 **5 passed**；PostgreSQL **124 passed**，本地浏览器 **4 passed**，构建/TypeScript、重启和禁发 DEMO 通过。5 项访问检查使用本地 HTTP 服务和 TEST_ONLY 登录，不证明目标域名 DNS、HTTPS 证书或源站上线。

目标域名目前被云环境代理 CONNECT 403 拒绝；没有配置托管平台、服务器或 DNS 身份，实际部署步骤 unrun。已保留原配置并追加域名到云环境网络草稿 revision 4，尚未应用/发布。具体变量、当前状态和所需平台信息见 [域名部署记录](domain-deployment.md)。源码更新和网络草稿保存均不能称为域名发布完成。
