# 标准化 Agent 工作流

项目自定义七个 Skills 已逐一审读并保留原文。它们不授权访问私人档案或营销发送，不要求启动并行子代理；本期使用可审计的阶段式流程。

| 阶段 | Skill | 运行时实现 | 输出/人审 gate |
|---|---|---|---|
| 画像/排除 | nexa-icp-research | icp_profiles + domain.assess | region/profile、Unknown、excluded_leads |
| 来源选择 | nexa-source-router | providers.route | 用途、关键词、许可、备用来源 |
| 商业社媒/官网 | nexa-social-intel | Providers + import_records | 原文、URL、观察时间；未核验默认 unverified |
| 核验/评分 | nexa-icp-research | evidence review + credential API + score | reviewer、Fit、Intent、可解释特征 |
| 联系政策 | nexa-compliance-review | consent records + contact_gate + suppressions | 单独合规人审，DNC立即阻断 |
| 双语草稿 | nexa-outreach-draft | render_draft + OpenAI structured suggestion | 证据 ID 和固定模板，人审 exact revision |
| 回复/交接 | nexa-reply-triage | ingest_reply + CRM tasks | 可解释规则分类，报价/技术/合同人工处理 |
| 外部编排 | nexa-n8n-workflow-audit | HMAC n8n webhook | 签名、时效、schema、幂等，外部工作流未审不导入 |

标准输入：`tenant(authenticated), account_id, province, profile, job_id, evidence_ids`。标准结果可通过 `GET /api/accounts/{id}/agent-result` 获取：`reasoning_summary, structured_results, excluded_leads, uncertain_facts, next_actions`。每个非空事实输出 URL、observed_at、confidence；Unknown 的 value 与引用均为 null。

SearchJob 与逐项 JobItem 是持久工作流状态，不依赖聊天记忆。队列调用 provider 的预算在调用前提交；worker 崩溃造成的未知外部调用仍占预算。租约恢复不承诺第三方收费 exactly-once；内部账号按持久键去重。审计仅保留事件摘要，不输出模型的隐式思维过程。

来自官网/社媒/附件中的指令始终作为待核验文本。AI 接口只能选择已允许模板与已审证据 IDs，未知事实不能进入生成正文。第一期回复分类使用可解释规则，真实语义分类模型后续启用须另测质量。
