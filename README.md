# NEXA AI Sales Engine · HVAC MVP V3.2

QC / ON、H01–H10、证据评分、可恢复研究、双语草稿人审、回复分类与 CRM。工作台按用户提供的 NEXA VI 设计。

**当前可运行范围：本地 DEMO + 受策略保护的 API 接口。没有自动营销发送器。真实供应商未接入，DEMO 企业、邮箱、资质、同意和回复都是虚构数据。**

## 设计与审查（先于应用代码交付）

- [技术架构](docs/architecture.md) / [数据库 Schema](docs/schema.md) / [DDL](db/001_initial.sql)
- [任务分解](docs/tasks.md) / [依赖与 API 限制](docs/dependencies.md) / [验收方案](docs/acceptance.md)
- [参考源码、许可证审查](docs/reference-audit.md) / [Agent 工作流](docs/agent-workflow.md) / [VI 应用](docs/design.md)
- 用户提供的 PRD / Starter / VI 已在当前工作区读取；原始上传文档及 PRD 提取文本不随公开源码发布。画像配置和七个项目 Skills 随源码交付。
- [实施与验证记录](docs/validation.md) / [云环境启动说明](docs/cloud-start.md) / [桌面截图](docs/previews/workspace-desktop.png) / [手机截图](docs/previews/workspace-mobile.png)
- [六项验收整改对照](docs/acceptance-scorecard.md) / [只读验收证据快照](docs/acceptance-evidence.json)：用户评分保持 0/100；测试通过不自动算作业务得分。

## 开发环境

已验证 Python 3.12、Node 24、npm 11、Docker 可用。所有命令在现有独立 checkout 中执行，无需 Git worktree。

```sh
cd /workspace/codex-cloud-nexa
UV_CACHE_DIR="$PWD/.local/uv-cache" uv venv .venv
UV_CACHE_DIR="$PWD/.local/uv-cache" uv pip install --python .venv/bin/python --require-hashes --only-binary :all: -r requirements.lock
.venv/bin/python scripts/dev.py init
cd frontend
npm_config_cache="$PWD/../.local/npm-cache" npm ci --ignore-scripts --no-audit --no-fund
NEXT_TELEMETRY_DISABLED=1 npm run build
cd ..
.venv/bin/python scripts/dev.py up
```

`init` 生成 ignored `.local/` 中的开发凭据，以固定 digest 的 PostgreSQL 17 官方容器启动数据库，应用迁移、非超级用户角色、FORCE RLS，并初始化三个租户。数据库仅绑定本机，数据 bind mount 在 `.local/pgdata`。`up` 启动 API、研究 worker 和 Next.js，并实际检查 API/页面响应。端口为 API 8000、工作台 3000、数据库 54329；都只绑定 loopback。不要将 BFF 的共享 DEMO 身份公开到 Internet。

开发时可用 `.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload` 和 `npm run dev` 替代对应服务。API 密钥不下发浏览器。`.local/tokens.json` 保存每租户每角色的本地 bearer，禁止打印/提交或发到聊天；frontend/.env.local 仅选择 DEMO 管理员。生产登录需要接 OIDC 与每用户会话；本期没有部署生产登录。

## 测试与演示

```sh
cd /workspace/codex-cloud-nexa
.venv/bin/python -m pytest -q --junitxml=.local/pytest-results.xml
.venv/bin/python scripts/demo.py
cd frontend
npm run typecheck
npm run test:e2e
```

浏览器测试使用已有 `/usr/bin/chromium`；无需下载浏览器或运行安装脚本。演示脚本通过真实 HTTP + PostgreSQL 演示 QC 企业与 ON owner-operator，确认 FR/EN 草稿、模拟审批、回复任务/商机、CSV/JSON 与发送始终返回 423；重复调用同一演示 job 和 reply 幂等。它自动执行的是 **DEMO 人审模拟**，不构成真实合规审批。

截图、结果 JSON/XML 和服务日志在 `.local/`。停止已启动的项目服务：`.venv/bin/python scripts/dev.py down`；保留数据库。运行前确认后台 worker 已启动，才能完成 DEMO job。

## 模块与接口

| 能力 | 入口 | 本期状态 |
|---|---|---|
| ICP / Source Router | profiles PATCH、router GET、policies PUT | 10画像、省份关键词、许可/凭据过滤和备用来源 |
| Research | jobs POST、pause/resume/step、job detail | Postgres lease/checkpoint、幂等键、结果/调用/费用限额、有限重试 |
| 企业发现 | accounts POST、授权目录/inbound import、Places | 支持规范化待核验导入；Places 仅 Place ID，不将 Maps 内容复制到 CRM |
| 官网丰富化 | Firecrawl `/v2/scrape` adapter | 固定 API、允许 URL、公共 DNS、重定向最终来源校验；原文待人审 |
| 商业社媒 | Apify reviewed dataset adapter | dataset allowlist + 商业内容过滤；不启动 Actor，不抓私人档案 |
| 资质/评分 | evidence/review、credentials、score/override | Unknown 明确、QC/ON与工作类别、两套 Fit、独立 Intent，人审有审计 |
| 草稿 | drafts POST/PATCH/approve | FR/EN、精确 revision、证据变化审批失效；无产品输入不生成产品声明 |
| AI | OpenAI Responses 结构化建议 | 仅模板/已审证据 ID；真实 API 未测试且默认关闭；正文有界渲染 |
| 回复/CRM | replies POST、opportunities/tasks/partners PATCH | 规则分类，报价/项目/技术/合同人审；退订立即抑制 |
| 导出/隐私 | export GET、accounts DELETE、audit GET | 仅经允许的已核验主体、CSV防公式、来源时间许可、个人资料级联删除 |
| 标准 Agent 输出 | account agent-result GET | 结构化结果、引用、排除、不确定事实与 next_actions |
| n8n | webhooks/n8n POST | bearer + HMAC + 5分钟时间窗 + replay rejection，接 ResearchJob；外部模板未导入 |

完整交互 schema 可通过运行中的 FastAPI OpenAPI 文档读取。供应商 adapter 调用需启用 reviewed SourcePolicy；记录出处与原文不代表事实已通过核验。真正 ContactBasis 还需要独立的已审 `contact_basis` 证据，不把公开邮箱当作同意。

指定画像另须核验 `service_capabilities`、`market_segments`、`business_models` 标签（以 `config/hvac-qc-on.json` 的 profile_qualification 为准）。未知进入 Review，明确不符进入 Excluded；企业采购决策权未知时，即使 Fit 80 也不合格。真实 `credential` 证据值须为匹配状态/省份/施工类别/主管来源的结构化事实；不能仅用 true 表示某类别资质有效。仪表盘状态实时复评，过期证据不沿用已合格展示。

## 真实接入与仍未完成的门槛

1. 参考页面被当前代理策略拦截：n8n #13513/#6091/#17051、OpenAI Academy、Google policy。所需域名已加入环境草稿，需用户在环境设置保存并发布后重查；未拿到 JSON 不能声称工作流代码审查完成。Lead-Researcher 源码审查已完成，但独立 LICENSE 缺失，未复制代码或运行其 installer/loop。
2. 真正接入时，在环境设置安全配置 `GOOGLE_PLACES_API_KEY`、`FIRECRAWL_API_KEY`、`APIFY_API_TOKEN`、`NEXA_OPENAI_API_KEY`。不要在聊天输入值。每个来源另行确认 Terms、许可、配额、缓存/导出目的并通过 SourcePolicy 合规人审。Apify Actor 许可不由 SDK Apache 许可代替。
3. OpenAI 还需显式设置 `NEXA_AI_ENABLED=true` 与启用经人审的 `openai` SourcePolicy（用途 `draft`、到期时间、总调用上限与每分钟限速）；配额在付费调用前提交，失败也占用配额。模型默认 `gpt-4.1-mini`，须按实际可用模型复核。DEMO 不调用付费 API。
4. NEXA 的实际公司/品牌、产品与合作政策、CASL 依据、RBQ/STO/TSSA 工作类别规则和隐私保留期限尚待业务/合规输入。Sender identity 当前是待补占位，审批仅是草稿审阅，不能发送。
5. 50 家真实企业人工抽样、QC/ON 各两城试点尚未执行；DEMO 与 mock 测试不能替代。生产 OIDC、来源合同、监控、备份/恢复与真实模型质量另需上线验收。

本版本发布范围为 GitHub `main` 源码与开发验证记录，详见 [发布记录](docs/release.md)。没有部署公开生产网站。云配置草稿保存、发布快照和新任务恢复是不同步骤；新任务恢复尚未独立验证。

删除账户会清除其联系/研究资料；为防止重新导入绕过退订，最小商业身份哈希抑制键单独保留，不保存原始姓名、邮箱或电话。真实运行前须确认该 opt-out 保留用途与期限。
