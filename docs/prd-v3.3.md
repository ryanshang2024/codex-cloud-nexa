# NEXA V3.3：企业集中管理的 AI 工作平台

版本：3.3。本文替代 V3.2 中员工自主获客及共享管理员工作台的设计；原 V3.2 输入保留作历史资料。NEXA AI Work Assistant 是员工执行端，NEXA AI Sales Engine 是管理端的获客及客户资产模块，两者共用企业身份、授权、配额、费用账本和审计。

产品硬要求：线索归企业；管理层控制发现、研究、筛选与分配；员工只能处理分配任务及明确授权的必要字段。服务端授权覆盖 API、AI/语音、Agent Tool、n8n、导出和异步 Worker。自然语言、模型输出和网页指令都不能创建权限。第一阶段营销发送继续关闭，真实来源及模型仍需合法授权与凭据。

## 1. 权限矩阵与身份迁移

“授权”是超级管理员存入服务端的显式权限，前端不能提供角色或租户授权。经理的公司分析另受授权的省份范围限制；范围为空时无公司分析。员工即使被写入管理权限也不能使用它。

| 能力 / 权限 | 超级管理员 | 销售经理 | 普通员工 |
| --- | --- | --- | --- |
| ICP 配置 `icp.configure` | 允许 | 显式授权后 | 固定禁止 |
| 来源策略 `sources.configure` | 允许 | 禁止 | 固定禁止 |
| 批量研究 `research.start` | 允许 | 显式授权后 | 固定禁止 |
| 线索分析 `research.analyze` | 允许 | 显式授权后 | 固定禁止 |
| 完整线索池 `leads.read` | 允许 | 允许 | 固定禁止 |
| 线索 / 资质审核 `leads.review` | 允许 | 允许 | 固定禁止 |
| 分配客户或任务 `leads.assign` | 允许 | 允许 | 固定禁止 |
| 导出 `leads.export` | 允许 | 显式授权后 | 固定禁止 |
| 公司分析 `analytics.company` | 允许 | 显式授权 + 省份范围 | 固定禁止 |
| 模型、费用及配额策略 | 允许 | 禁止 | 固定禁止 |
| 用户与权限管理 `users.manage` | 允许 | 禁止 | 固定禁止 |
| 草稿审批 `drafts.approve` | 允许 | 允许 | 固定禁止 |
| 我的任务 / 更新状态 / 工作记录 | 允许 | 允许 | 仅本人当前分配 |
| 分配客户的必要资料 | 允许 | 允许 | 授权字段 + 指定联系人 |
| 任务查询 / 工作摘要 / 语音录入 | 可配置 | 可配置 | 默认授权低风险功能，调用受配额控制 |
| 客户跟进草稿 | 允许 | 允许 | 本人任务、指定联系人、独立工作/AI 功能授权 |
| 全租户审计 `audit.read` | 允许 | 允许 | 禁止 |
| n8n Webhook | 独立服务身份 | 独立服务身份 | 固定禁止 |

规范角色：`super_admin / manager / employee / service`。现有 `admin` 转 super_admin，`sales` 转 employee，`researcher / compliance` 转 manager，但不自动继承研究、导出和 ICP 配置权限。旧绑定只用于验证凭据和定位身份，运行时角色以 users 为准。新增用户不允许自助注册或选择管理角色。员工主页永不请求管理 dashboard。

服务身份不能网页登录，只获得单独的 `n8n.webhook` 和 `research.start` 范围。签名密钥按服务身份配置，不能复用浏览器会话或前端凭据。

## 2. 数据库 Schema（增量迁移 003）

沿用 PostgreSQL FORCE RLS、租户复合外键、不可变 audit_events。所有新表均包含 `id, tenant_id, created_at, data`，以及以下受约束列；运行时应用角色不能绕过 RLS。迁移不将历史客户或任务自动分配给员工。

| 表 / 变更 | 键与关键字段 | 用途 |
| --- | --- | --- |
| users | canonical role；data.active、display_name、password_hash | 服务端权威身份；密码哈希不返回 API |
| auth_sessions | user_id FK、token_hash 唯一、expires_at、revoked | 每人独立会话；只保存令牌哈希 |
| user_grants | user_id FK、permission、唯一 tenant/user/permission；data.enabled、provinces | 显式授权、关闭工作能力及分析范围；员工权限硬上限 |
| tasks.owner_id | 可空、同租户 user FK | 权威任务负责人，不能信任旧展示 owner 字符串 |
| work_assignments | account_id、task_id、user_id、contact_id 同租户 FK；status；唯一 tenant/task | 当前分配与撤销、可读字段 allowlist；联系人必须属于同一 Account |
| work_notes | task_id、user_id 同租户 FK | 工作记录、项目进展与工作汇报；不让员工写证据核验结论 |
| ai_policies | 唯一 tenant；data 企业预算、预警、熔断、角色配额、模型价目及启用状态 | 企业集中策略；配置权限仅 super_admin |
| user_quotas | user_id 同租户唯一；每日请求、Token、语音、并发额度 | 明确用户限额；仍受角色及企业上限 |
| usage_ledger | user_id FK、唯一 tenant/idempotency_key；state、reserved_until；成本/Token/语音/数据源计数、task_id、provider | 付费调用前预留、实际结算、失败保守记账、请求幂等 |
| quota_requests | user_id FK、status、requested limits、审批人及理由 | 提额申请 / 审批；审批与使用审计 |
| search_jobs.data | actor_id、cost_budget、max_retries | Worker 每次外部调用重新验证当前身份、权限与费用策略 |

权限与字段拆分：管理端用 Account / Lead 全记录；员工用 `/work` 投影。仅已核验合格客户可分配，默认只开放企业名、省份与任务内容；email / website 需显式勾选，email 必须来自指定、仍有效的已核验联系人；资格失效时收起联系方式并提示管理复核。撤销分配立即失去 API、会话助手和草稿访问能力，历史 notes 不为员工提供客户池入口。

## 3. API 权限清单

每个受保护请求验证服务端身份 active、租户、权限；对象 ID 查找使用同租户限制。员工记录访问另验证任务 owner、active assignment 及字段 allowlist。跨租户 / 非本人记录返回 404；禁止的功能返回 403；额度超限返回 429；熔断 / 未启用接入返回明确关闭状态。

| API | 需要权限 / 数据范围 |
| --- | --- |
| POST `/api/auth/login` | 登录凭证；返回服务端会话，BFF 写 HttpOnly/SameSite cookie |
| POST `/api/auth/logout`、GET `/api/identity` | 当前个人身份；注销撤销会话 |
| GET `/api/dashboard` | `leads.read`；公司 analytics 另检查 `analytics.company` 和授权范围 |
| GET `/api/router`、PATCH `/api/profiles/{code}` | `icp.configure` |
| PUT `/api/policies/{provider}` | `sources.configure` |
| POST `/api/accounts`、POST `/api/jobs`、POST `/api/jobs/{id}/{action}` | `research.start`；任务限制及预算，后续 Worker 不继承管理员万能权 |
| GET `/api/jobs/{id}` | `leads.read` |
| GET `/api/accounts/{id}`、GET `/api/accounts/{id}/agent-result` | `leads.read` / `research.analyze` |
| evidence、credentials、score、override | `leads.review` / `research.analyze` / `leads.override`；覆盖单独授权，硬核验条件保持 |
| contacts、consents、人审 | `leads.review`；不同审批的证据约束保持 |
| 管理草稿、回复、DNC、CRM 更新 | 管理权限；员工使用独立 `/work` 接口，不能复用全记录响应 |
| POST `/api/drafts/{id}/approve` | `drafts.approve` |
| POST `/api/drafts/{id}/send` | 权限核验后仍 423，第一阶段永久锁定 |
| GET `/api/export` | `leads.export`；导出审计与原有来源许可规则 |
| GET `/api/audit`、DELETE `/api/accounts/{id}` | `audit.read` / `leads.review` |
| GET `/api/admin/users` | `leads.assign`；仅返回分配所需的用户目录及授权状态，不返回密码/凭据 |
| POST `/api/admin/users`、PATCH `/api/admin/users/{id}`、PUT `/api/admin/users/{id}/grants` | `users.manage`；员工管理权限不可授予，保留至少一个有效超级管理员 |
| POST `/api/admin/assignments`、POST `/api/admin/assignments/{id}/revoke` | `leads.assign`；目标用户、客户、任务、联系人同租户 |
| GET `/api/work/dashboard`、`/api/work/tasks/{id}` | 自己的 active 分配；最小字段投影 |
| PATCH `/api/work/tasks/{id}`、POST `/notes`、POST `/drafts`、POST `/replies` | 对应工作权限 + 当前分配；只能改工作状态，不得更换负责人或授权字段 |
| GET/PUT `/api/admin/ai-policy` | `ai.policy.manage`；模型、价格、日限额、企业预算、暂停 |
| GET `/api/admin/usage` | `ai.policy.manage`；公司级费用 / 预警 / 并发 |
| GET `/api/work/usage` | 本人的使用量与限额 |
| POST `/api/work/quota-requests`、POST `/api/admin/quota-requests/{id}/review` | 本人申请 / `ai.budget.approve`；审批不改变员工固定禁用能力 |
| POST `/api/assistant/actions`、POST `/api/assistant/tools/{tool}` | 功能权限 + 同一当前用户的数据权限 + 四级额度；工具逐次鉴权 |
| POST `/api/webhooks/n8n` | 独立 service 身份 + `n8n.webhook` + `research.start` + 身份专属 HMAC、时间窗、重放去重 |

BFF 移除共享 `NEXA_API_TOKEN` 回退；浏览器会话由每个用户登录创建。BFF 不转发任意客户端 tenant / role / 管理 token，Webhook 不经员工 BFF。跨站写请求拒绝，无会话请求 401。生产会话 cookie 为 Secure；本地开发仅 loopback 可使用非 Secure cookie。

## 4. 用量、计费及熔断规则

初始配置是管理默认值，不是实际费用承诺。金额以整数 micro-USD 计账（1 USD = 1,000,000），时间窗使用 UTC，自定义模型价格需负责人核实，不将价目示例视为供应商最新价格。

| 层级 | 默认及执行点 |
| --- | --- |
| 企业 | 300 USD/月；80% 预警；月预算、月 Token、语音分钟、数据源调用、总并发均在数据库锁内检查；支持手动熔断 |
| 角色 | employee 仅工作 Agent；manager 研究/导出需 grant；员工 max_leads 固定 0；角色限制每日请求、Token、语音、单调用成本和任务并发 |
| 用户 | employee 默认 20 次付费请求/UTC 日；单用户可配置限额，但不能超过角色/企业限制；额度不影响免费工作记录、任务状态、CRM 普通操作 |
| 任务 | 最大 200 条结果（现有硬上限）、单任务成本及同时任务数；每次重试重新预留费用，默认最多 3 次失败尝试（含首次）；0 表示不重复失败请求；未知费用不得免费重试 |

计账流程：权限 / 字段检查 → 计算可信的 Token、语音或来源费用上界 → 租户策略行锁 → 企业月用量 + 用户日用量 + 角色/用户/任务限制检查 → 写 usage_ledger 幂等预留并提交 → 实际外部调用 → 根据供应商 usage 结算。Token 请求量来自服务端上界及供应商回执，不信任客户端声明的“零 Token / 零费用”。

输入/输出 Token 分开定价；语音按服务端核验的音频时长和配置价格；数据源按已审核 policy.cost_per_call。预留也占预算与并发。已发起但失败/超时且没有可靠账单时保留上界费用与用量，释放执行并发；每日请求次数不退款。回执超过预留时记录真实费用并熔断，不能截断账本掩盖超支。长失联预留仍占预算，执行租约到期释放并发但不退款。

助手和所有付费入口共享账本。成功缓存重放也重新核验工具权限和当前投影；删除客户清除相关缓存内容而不删除费用与请求计数。全局 API 费用监控汇总 OpenAI、语音及数据源；达到企业预算或手动暂停后不能调用供应商。voice 接入未配置时明确关闭，不能偷偷走浏览器外部语音服务。规则查询/普通工作摘要可以作为零外部调用功能继续使用，标明其处理方式。

提额：员工申请 → super_admin 审批并写 user_quotas → 审计；提高研究能力必须另走管理角色 grant，永远不能给 employee 批量研究能力。配额调整不重置已发生用量；月预算提高须显式审批操作，不自动扩费。

## 5. 两套用户旅程与界面

**Admin Console**：个人登录 → 配置行业 ICP、QC/ON 区域、授权渠道与预算 → 发起受控研究 → 审查来源/核验/评分 → 选择销售员工及必要字段 / 联系人 → 分配任务 → 跟踪回复、任务与商机 → 授权范围内分析及员工执行报表。超级管理员另有用户权限、AI 模型/价格、配额、预警、熔断及提额审批。

**Employee App**：个人登录 → 我的任务 / 待跟进 → 打开自己当前任务及明确授权的必要客户资料 → 授权 AI 工作助手查询任务 / 摘要 / 跟进草稿（语音接入按策略开放）→ 执行联系与记录结果 → 更新进度 → 工作汇报 → 结果写回统一 CRM。员工不见完整潜客库、ICP、批量研究、导出、全公司经营分析；直接调用这些 API 也禁止。

两套界面共用品牌 VI，独立路由 `/admin` 与 `/employee`。员工首页显示“我的任务 / 待跟进 / AI 工作助手 / 工作汇报”。管理员不能通过前端角色切换绕过登录；演示也使用独立身份。下一版宣传图及视频应分别展示两套旅程，旧 V3.2 宣传素材不作为 V3.3 权限证明。

## 6. 上线验收与交付顺序

1. 先交付本矩阵、Schema、API 清单、计费规则及双端旅程，再写代码。
2. 增量数据库迁移及用户身份初始化，独立会话、统一授权、最小字段投影、管理分配、n8n 服务身份。
3. 集中费用预留 / 结算、四级限制、重复失败、并发、预警、熔断及审批提额；已配置的真实调用入口必须纳入账本。
4. 两套界面、授权助手及管理设置，保持真实/DEMO 资料标识与第一阶段发送锁。
5. 必须通过：未登录、员工直接 API、跨用户/跨租户、撤销分配、隐私字段、提示词/Tool 提权、导出、员工 n8n 调用、服务错签名/过期/重放、预算/Token/语音/数据源/并发/任务上限、费用失败重试、配额审批、免费工作在额度耗尽后继续、浏览器双端及跨站写测试。

开发通过不替代供应商许可、真实公司资料、50 家真实主体复核、正式 HTTPS/备份和上线身份运营验收；这些外部 gate 继续保留。禁止为了宣传或测试通过而声称真实 AI、语音或营销发送已经开放。
