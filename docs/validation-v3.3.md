# V3.3 企业集中管理：交付与开发验收

界面预览：[Admin 企业管理](previews/v3.3-admin-console.png) / [Employee 我的任务](previews/v3.3-employee-app.png) / [员工移动端](previews/v3.3-employee-mobile.png)。这是浏览器实际运行截图，使用独立身份，并保留虚构资料标识。

本版将 NEXA AI Sales Engine 定位为管理端客户资产模块，将 AI Work Assistant 定位为员工工作端。规范见 [统一 PRD](prd-v3.3.md)：权限矩阵、增量 Schema、API 权限、计费规则及两套用户旅程在应用修改前交付。

## 已实现

- `/admin` 与 `/employee` 独立界面、个人密码登录及 8 小时可撤销 HttpOnly 会话；BFF 移除共享管理员 token，匿名请求不获得管理身份。
- 权威角色 super_admin / manager / employee / service。经理的 ICP、研究、分析、覆盖、导出及省份分析范围显式授权；员工即使出现非法管理 grant，仍不能超过角色上限。
- 管理员先核验客户再分配。员工验证 active assignment、owner_id、同租户及 allowed_fields，默认只有企业名/省份；联系方式需指定有效联系人。资料失效收起联系方式，工作记录仍可提交。员工不能直接读取 Account 全记录或企业线索池。
- 管理端查看员工回写的工作记录、任务状态及回复报告，并撤回/转交分配。员工回复报告需管理端核验，不自动变成真实入站证据、采购信号或商机。员工跟进草稿和 AI 跟进能力分别授权，草稿仍需人审，营销发送锁定。
- 企业月预算、预警、Token、语音、来源调用、总并发；角色/用户日限额；研究任务数量、费用、并发及有限失败尝试。整数 micro-USD 预留在调用前提交，回执结算；失败保留上界，同键不重复付费，异常回执触发熔断。免费任务操作不受付费预算暂停影响。
- 模型选择的工具和任务 ID 重新鉴权；成功缓存重放也复查功能权限与当前投影，撤回字段后不返回旧敏感内容。删除客户清除相关 AI 内容缓存，保留费用总额及幂等记录。
- n8n 采用默认无权限的独立服务身份、专属 HMAC、时间窗、重放检查及研究权限。Worker 继承原始用户，并重新检查当前权限/限额；暂停再恢复不能绕过任务并发。服务凭据不经浏览器 BFF。
- 敏感读取、拒绝、分配、权限/账号变更、审批、导出、AI 调用/费用及提额均写不可变审计。新表 FORCE RLS 与同租户复合外键；旧角色迁移不自动授予研究/导出。

## 实际验证（2026-10-11 UTC）

| 验证 | 结果 | 范围 |
| --- | --- | --- |
| PostgreSQL / FastAPI pytest | 163 passed | 原 HVAC 核验/草稿/CRM 回归 + 39 项 V3.3 参数化安全/计费用例 |
| 草稿授权及锁顺序调整后补测 | 1 passed | 分配客户的联系依据、工作/AI 双授权、人审与发送锁 |
| TypeScript + production build | 通过 | 两套路由、BFF、管理配置与员工界面 |
| Chromium 用户旅程 | 6 passed | 管理分配、员工最小字段/跟进/助手、权限 UI、回写、撤回、直接 API/Agent 拒绝、移动端、原 CRM 流程 |
| 部署访问配置 | 6 passed | 可选 Basic 外层仍需个人登录、Secure cookie、同源、缺配置关闭、SaaS 匿名 API 拒绝与 Host 校验 |
| HTTP 功能演示 | 完成 | QC 法语 / ON 英语、审批/回复/CRM、发送 423；零真实供应商调用、零消息发送 |

测试使用本地 PostgreSQL、真实 API/BFF 和 Chromium；模型/供应商失败、提权及计费回执用受控替身，不调用外部付费接口。原子预算/并发用两个独立数据库连接同时争用额度，验证仅一个成功。此结果不替代真实供应商、真实语音或真实客户质量验收。

pytest 有一条现有 Starlette/httpx 弃用提示，不影响测试结果；本次没有修改锁定依赖或安装新包。详细原始日志/XML/JSON 保存在 ignored `.local/`，公开只发布脱敏的 [验收证据](acceptance-v3.3.json) 与截图。

## 本地使用与升级

1. 现有环境先用 `scripts/dev.py down` 停止项目自有服务，保留数据。
2. 运行 `.venv/bin/python scripts/dev.py init`，按 schema_migrations 应用新增 003，不改写 001/002。
3. `cd frontend && npm run build`，再运行 `.venv/bin/python scripts/dev.py up`。
4. 访问 http://127.0.0.1:3000/ 并个人登录；首次初始化密码只在服务器 `.local/demo-logins.json`，权限 600，不提交或打印。管理员账号 `nexa-demo:admin`，员工 `nexa-demo:sales`；新员工可在管理端创建。
5. 在企业管理中配置功能权限与 AI 策略，选择已核验客户、员工和必要字段后分配；员工进入自己的工作端。经理的批量研究默认关闭，由管理员显式开放。
6. n8n 独立凭据在 `.local/service-identities.json`，默认无权限。仅服务器负责人运行 `scripts/service_identity.py <tenant> enable/disable`；每次操作有审计，凭据仅交给受管的服务端 n8n。

旧 V3.2 队列若没有 actor_id，Worker 暂停并审计，不猜测管理员身份；需以当前获授权身份重建研究任务。既有客户不自动开放给员工。旧独立 API 绑定仍从数据库读取当前角色；生产应仅保留经过负责人审查的服务绑定，人员使用个人会话。

## 尚待真实接入的门槛

真实 Google/Firecrawl/Apify/OpenAI 的当前条款、配额与凭据仍须审核启用；模型价格须在管理端核实，不以默认值宣称最新价目。语音供应商、外部 PTT、SSO/OIDC、MFA、账号恢复尚未连接。50 家 QC/ON 真实企业复核、HTTPS 域名、备份恢复及生产运营验收尚未完成。既有用户业务评分不自动因开发测试通过而改变。

第一阶段自动营销发送持续关闭；本次源码发布不代表 nexa-mk.voltwok.com 已部署。两套截图为运行中界面的开发验收资料，DEMO 企业保留虚构标识，不作为真实客户或销售转化证明。
