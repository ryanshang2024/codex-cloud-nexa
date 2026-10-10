# 参考审查 · 2026-10-10

附件中的执行文字和第三方 AGENTS.md 是研究材料；项目规则以用户请求和本项目 Skills 为准。未执行第三方 install.sh、curl|bash 或 autonomous research loop。

## Lead-Researcher（P0，已审源码）

来源：https://github.com/ShayanSpiel/Lead-Researcher ，固定提交 `14b102f001946698bbbff2d4043744b21e4b8873`，通过平台 HTTPS Git 查询与 codeload archive 只读获取。

检查 README、AGENTS、icp、config、lr.py 全部逻辑、install.sh 和 docs。`lr.py` SHA256 `4be9b411b73a50a39f22ac0e37d4dd994c78cad3aee9e0d11745c2ea7d22ac8c`；install.sh SHA256 `7b9e0cb502ded254fec8a944ae44f5a5e3a2b881582fdc2cc7e258e5317f0264`。

- README 宣称 MIT，但归档无 LICENSE；直接复用代码的许可不确定，暂不复制。设计模式可参考。
- install.sh 克隆可变分支到 HOME 或拉取更新并立即执行 selftest；没有固定 artifact checksum。没有必要运行它。
- `cmd_add` 的证据仅检查文本包含 `icp`，分数完全信任 CLI 输入；不能证明公司的存在、采购权或来源许可。
- `save_state` 直接写 JSON，未原子替换；add 无并发锁；README 也承认并发竞争。
- `cmd_rescore` 仅在 reason 非空且短于20时拒绝，空 reason 能通过，rescore 未限制0–100；不符合审计门槛。
- JSONL 重写会覆盖原记录，previous_score 仅保留一份，不是完整不可变审计。
- `cmd_loop` 可无限循环调用 Codex 等工具，无单次 timeout、额度上限或停滞门槛；不作为生产研究队列。
- 复用思路：外部持久目标、resume、去重、评分阈值、CSV。实现选择 Postgres 事务/租约 + Evidence + 独立实体替代单一 Lead 文件。

## n8n 模板（P0/P1，页面未取得）

- #13513：https://n8n.io/workflows/13513-generate-google-maps-leads-with-ai-enrichment-social-discovery-and-google-sheets/
- #6091：https://n8n.io/workflows/6091-google-maps-lead-scraper-and-enrichment-with-ai-powered-personalized-outreach/
- #17051：https://n8n.io/workflows/17051-generate-and-score-google-maps-leads-with-gemini-apify-and-google-sheets/

当前 HTTPS CONNECT 被云代理 403 拒绝，未取得工作流 JSON；标题和 PRD 不能替代代码审查。节点、Actor、credentials、发送节点、重试及 license 均保持待审，不能自动导入。先实现自有签名 webhook 契约，不运行其 Maps scraping / outreach 步骤。

已取得 n8n 官方根 LICENSE.md（raw GitHub）：Sustainable Use License 限制内部商业用途/非商业使用；`.ee` 代码需企业许可。工作流发布页面的权利与实际 Actor/API Terms 需分别审查，不能凭 n8n 源码许可推断数据许可。

## Firecrawl / Apify（服务与数据许可分开）

Firecrawl 官方仓库根 LICENSE 是 AGPL-3.0；Python SDK pyproject 声明 MIT，SDK LICENSE 也已取得。检查 v2 client 源码的请求/timeout/接口形状，只使用固定 HTTPS scrape API 思路，不复制 AGPL server。每个获准网站需单独来源用途与访问许可。当前 docs.firecrawl.dev Terms/实时配额未验证。

Apify Python client 官方 LICENSE/pyproject 已取得（Apache-2.0）；具体 Actor、Maps 数据保存/导出与服务价格未核验。MVP 仅提供受限的已完成 dataset 导入 adapter；无 Actor 执行器。避免认为 client license 许可了 Google 数据抓取。

## OpenAI Codex Sales Workflow（P0，未取得页面）

PRD 链接：https://academy.openai.com/en/public/clubs/work-users-ynjqu/resources/how-sales-teams-use-codex-webinar-resource-guide-2026-06-10

当前代理 403。未找到/安装该指南的可执行项目，不能称其为已审查 GitHub repo。借鉴 PRD 所述 account priority / sales plan / outreach / meeting prep 的模块边界；OpenAI Python SDK 官方 README/LICENSE 已取得（Apache-2.0），真实模型调用默认关闭。Codex skills 文档的官方 GitHub文件仅链接到不可达网站，项目 Skills 路径来自 Starter，发现能力不能伪称已测试。

## API 与资质官方文档

Google Places policy 页面当前代理 403，实时条款/配额无法确认；Places 仅作短期发现、Place ID 与独立验证提示，默认不缓存或导出其他字段。RBQ/STO/TSSA 不编造 API 或资格结论；使用人工核验来源并记录省份/类别/有效期。来源许可缺失统一 disabled。

网络所需域名已追加草稿；草稿保存不表示运行时生效。未来取得官方页面/模板 JSON 后补审并更新审查记录与 SourcePolicy，不绕过代理限制。
