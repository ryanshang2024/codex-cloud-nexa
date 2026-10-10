# 数据库 Schema

完整可执行 DDL：[db/001_initial.sql](../db/001_initial.sql)。PostgreSQL 17；UTC timestamptz，ID 为应用生成 UUID 字符串；可演进领域属性存在 `data jsonb`，身份/租户/省份/状态/评分/幂等/引用为数据库约束列。后续迁移新增文件，不重写已有版本。

[002_suppression_keys.sql](../db/002_suppression_keys.sql) 保留单向哈希的商业域名/注册号/外部ID抑制键；删除账户及联系资料后重新发现同一商业主体，仍不能绕过其拒绝联系。该表没有姓名、邮箱、电话或原始标识，保留用途仅限执行 opt-out；生产保留期限仍须合规确认。

| 表 | 关键列/约束 | 目的 |
|---|---|---|
| tenants / users | tenant、角色、DEMO | 隔离与 RBAC 身份 |
| industry_templates / icp_profiles | code H01–H10、keywords、weights | 配置版本与两省画像 |
| source_policies | provider、enabled、purposes、terms_url、license、expiry、quota | 来源授权与 API 限制 |
| accounts / account_keys | QC/ON、profile、roles、domain/registry/external unique | 商业主体、多角色、精确去重 |
| contacts | account、business email、evidence_id、basis | 商业联系人与账户分离 |
| partners | account unique、application→review→approved→activated | 安装伙伴资格与首个合作动作 |
| projects / project_participants | account、project、role | 项目与物业/安装/顾问/采购关系 |
| leads | account unique、Fit/Intent 0–100、state、breakdown、evidence_ids | 销售资格及可解释分数 |
| evidence | URL、observed_at、confidence、verification、DEMO、event/expiry/license/purpose | 字段与信号溯源，不允许空来源 |
| credential_verifications | province、status、work_class、authority、evidence_ids | 分省/工作类别核验，Unknown 明确保存 |
| search_jobs / job_items | 幂等键、cursor、calls、lease、retry 时间、ordinal unique | 持久任务与断点 |
| source_attempts | job、provider、status、cost、error | 调用费用、失败与备用来源审计 |
| consent_records | account/contact、reviewer、basis、expiry、evidence | 合法联系依据的独立人审 |
| outreach_drafts | account/contact、FR/EN、revision、status、approved hash | 待审批内容与审阅版本 |
| interactions | external_id unique、category、received_at、evidence | 幂等入站回复与分类 |
| opportunities / tasks | stage、owner、due、reason、requires_human | CRM 商机与责任人任务 |
| suppressions | account unique、reason、time | 退订和拒绝联系立即抑制 |
| audit_events | immutable JSON event、actor、target、reason | 不可变、不含秘密或原始回复的审计 |
| webhook_events | external_id unique | HMAC 入站去重 |
| schema_migrations | version unique | 可重复迁移 |

每个租户表 `(tenant_id,id)` UNIQUE；所有实体关系使用同租户复合 FK。应用身份仅授予 SELECT/INSERT/UPDATE/DELETE，Audit 仅 SELECT/INSERT；RLS FORCE + transaction-local `app.tenant_id`。删除 Account 时级联删除个人/研究实体，审计仅保留 ID 和事件摘要，不保留个人内容。

Evidence JSON 契约：`fact_type, value, signal_type|null, event_date|null, raw_excerpt, provenance_license, permitted_purposes, expires_at, source_provider, independent, reviewer_id|null, work_class|null`。未知值 JSON null；声明/未核验内容不能直接变成事实。
# 验收整改中的证据值契约

2026-10-10 六项验收复查新增字段使用现有 Evidence JSONB，数据库表/外键/RLS 无需改变。

- `service_capabilities`、`market_segments`、`business_models` 的 value 为受控标签列表或 null；标签来自 `backend/domain.py` 的 CAPABILITY_VALUES，指定画像条件来自 `config/hvac-qc-on.json` 的 profile_qualification。证据必须按现有流程独立核验才能满足条件。
- 真实 `credential` value 必须明确包含 `status`、`province`、`work_class`，verified 还必须匹配 `authority`。例如字段形状为 `{"status":"verified","province":"QC","work_class":"<人工核实的实际类别>","authority":"RBQ"}`；此处仅示例 schema，不是任何真实客户的资格结论。
- `not_required` 仍需官方来源、明确工作类别和人工核验的依据，不根据热泵行业推断豁免。DEMO 兼容裸 true；真实客户不接受裸 true 推断具体资质。
- Account / Lead 的持久 state 仍作为最后一次评分记录。dashboard GET 返回最新资格状态及评分的只读投影，证据/来源到期不会延用旧的 qualified 展示；它不创建新审计事件或写评分。

第二轮仍沿用 JSONB，无 DDL 迁移。`search_jobs.data.request_hash` 是规范化创建请求的 SHA-256，同幂等键不同请求返回 409；老任务从原有字段和按 ordinal 排序的 JobItem payload 核对。`source_policies.purposes` 显式允许 reply，但只有负责人启用并审核后才适用。`first_cooperation` 的 value 必须严格为 true，event_date 必须已发生且不晚于 observed_at，才能支持 activated；Unknown、申请、未来计划不能替代完成证明。草稿 approval 复查当前 evidence_ids 的 outreach 用途与事实支持，编辑清除 approved_revision 和旧 AI 建议。
