# V3.2 DEMO 源码发布记录

日期：2026-10-10。用户确认发布目标为 `ryanshang2024/codex-cloud-nexa` 的 GitHub `main` 分支。仓库为公开仓库；本次交付是源码和开发验证记录，不是公开网站部署或正式业务验收通过。

## 本次发布前验证

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
