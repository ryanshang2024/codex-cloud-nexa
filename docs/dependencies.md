# 依赖与复用清单

| 依赖 | 用途 | 许可证 / 决策 |
|---|---|---|
| Python 3.12 / FastAPI / Pydantic / Uvicorn | 受验证 API 与 schema | PSF / MIT / MIT / BSD；锁定 Python wheel hashes |
| psycopg 3 + binary | PostgreSQL 驱动、事务与队列 | LGPL；使用驱动而不是自建连接协议 |
| PostgreSQL 17 官方容器 | RLS、复合 FK、持久事务与 worker lease | PostgreSQL License；检查 docker-library entrypoint，再拉固定 digest |
| httpx | 有超时的固定 HTTPS provider client | BSD；不使用第三方 crawler 安装脚本 |
| OpenAI Python SDK | 受约束结构化草稿建议 | Apache-2.0；可选真实模型调用，无凭据保持关闭 |
| Next.js / React / TypeScript | UI 与服务端 API 代理 | MIT / MIT / Apache-2.0；npm lockfile，禁止依赖安装生命周期脚本 |
| pytest / Playwright | 业务/数据库/API 与浏览器验证 | MIT / Apache-2.0；现有成熟测试工具 |
| n8n | 可选内部编排，调用签名入站 webhook | Sustainable Use License，企业扩展另有许可；MVP 不安装或嵌入 |
| Firecrawl HTTP API | 授权官网丰富化 | 服务条款单独审；server AGPL-3.0，Python SDK MIT，均不复制服务器代码 |
| Apify HTTP API | 经过审查的已完成 Actor dataset 导入 | client Apache-2.0；每个 Actor 另审，不自动启动 Maps scraping Actor |
| Google Places API | 短期发现提示 / Place ID | 专有服务条款；不保存评分/评论，不凭 Maps 内容直接创建可导出的 CRM 主体 |
| Lead-Researcher | ICP、持久进度、阈值与 CSV 的设计借鉴 | README 声称 MIT，独立许可缺失，暂不复制或安装 |

生产库选 Postgres；本期测试也使用真实 Postgres，不用 SQLite 绕过 RLS。数据库生成配置、凭据和运行日志只存 ignored `.local/`。供应商凭据仅查名称与是否存在，不打印值、不提交仓库。

## API 限制策略

统一：来源用途+授权、显式启用、账户配额配置、每个 job ≤200 结果、有限重试、超时、429 backoff、预算预扣；403 不换身份绕过。目录/RBQ/STO/TSSA 无已核验通用开放 API，不编造端点；接受人工或授权数据包并保留官方查验链接。Firecrawl 禁用广泛 crawl，单个获准 URL scrape；Apify 只读取明确许可的 dataset，不运行任意 actor；OpenAI 不用于编造主体或联系资料。

现有云网络仅 package_managers preset；参考与供应商域名已添加到草稿，但保存草稿不代表运行时策略已更新。当前各供应商限额、价格、具体 Terms 页面均待可达后再次核验；产品应将这类 source policy 保持 disabled。
