# nexa-mk.voltwok.com 私有 DEMO 发布准备

用户指定目标：`https://nexa-mk.voltwok.com/`。**目前尚未部署到该域名。** 已准备和验证访问保护与域名变量；现有 GitHub main 仅是源码发布，不能代替运行服务器、DNS 或 HTTPS。

## 当前阻塞与检查结果

- 当前云环境代理对目标 HTTPS 请求返回 CONNECT 403；没有取得源站 HTTP 响应，不能判断域名网站、DNS 指向或证书状态。环境 DNS 查询失败也不代表域名不存在。
- 运行配置和非秘密身份清单均没有托管平台身份、SSH/TCP 授权或 DNS 管理权限。关联 GitHub 仓库没有 deployments 或 Actions workflows。不能仅凭域名创建或接管服务器。
- 保留原有网络设置，将 `nexa-mk.voltwok.com` 追加到云环境配置草稿 revision 4，并已读回确认。保存草稿不应用网络规则、不部署网站；工具返回 requires_publish=true，需在环境设置审核、保存并发布才能生效。
- 还需要用户提供现有托管平台/项目或服务器，以及 DNS 管理平台，并在环境设置中绑定部署身份。确认平台后才能补齐该平台的 API 网络范围；不默认新建付费云资源或选择新供应商。

## 已完成的应用适配

复用 Next.js Proxy 和标准 HTTP Basic Auth，为受邀人员访问 DEMO 提供临时保护；使用 Node crypto 定长摘要比较，覆盖页面、静态资源和全部 BFF API。没有登录凭据时返回 503，未登录/错误登录返回 401，不会获得后端共享 DEMO 身份。公开域名必须配置 HTTPS origin；BFF 校验规范化的同源地址，移除公开模式下 localhost 的例外。

这是共享的演示访问控制，不是生产每用户身份、角色或会话系统。部署必须仅连接独立 DEMO 租户，保留虚构资料标识和 `.example` 地址，真实来源和模型默认关闭，全部发送仍为 423。真实客户模式仍需要生产身份、业务资料和独立验收，不能因发布 DEMO 而自动启用。

变量示例：[deploy/nexa-mk.env.example](../deploy/nexa-mk.env.example)。在选定主机/平台设置：

| 变量 | 要求 |
|---|---|
| NEXA_WORKSPACE_MODE | private_demo；默认也是 private_demo |
| NEXA_WORKSPACE_ORIGIN | https://nexa-mk.voltwok.com，允许输入末尾斜线并规范化 |
| NEXA_DEMO_AUTH_USERNAME / NEXA_DEMO_AUTH_PASSWORD | 部署平台秘密存储中的演示登录；用户名不含冒号，密码使用独立强随机值 |
| NEXA_API_URL | 可达的私有 FastAPI 地址；不能把无保护的 API 或数据库端口直接公开 |
| NEXA_API_TOKEN | 仅属于隔离 DEMO 租户的服务器凭据；不是浏览器变量 |
| NEXA_AI_ENABLED | false；不要为发布演示配置真实供应商调用 |

`scripts/dev.py up` 仍绑定 loopback，并默认设置 local 模式；它是本地启动器，不是域名发布命令。公开服务由选定平台配置 private_demo，保留 API / worker / PostgreSQL 持久化与迁移，使用该平台的 HTTPS 入口。发布文件不包含 .local、.env.local、数据库、原始附件或凭据。网络配置和秘密由环境设置管理，不写入 Git。

## 可复现的开发验证与实际发布门槛

生产构建：`cd frontend && npm run build`。部署访问检查：`npm run test:e2e -- --config=playwright.deployment.config.ts`。它启动两个 loopback Next 实例，使用明确 TEST_ONLY 凭据和 Host 头测试目标域名配置，**不访问真实域名、不验证 DNS/真实 TLS、不构成线上部署**。

修复前部署访问检查 4 failed / 1 passed：匿名、错误登录、缺配置仍能访问；公开写入仍接受 localhost Origin。修复后 5 passed。完整后台 PostgreSQL 与本地浏览器工作流也重新验证，精确结果见 [acceptance-evidence.json](acceptance-evidence.json)。

实际发布需在平台身份和网络生效后完成：部署可恢复的应用/API/worker/数据库，配置目标子域名并取得可信 HTTPS 证书，验证未登录拒绝、登录工作流、同源写入、禁发和隔离 DEMO 数据。届时才记录 DNS、证书、源站版本和线上验收结果；当前这些步骤均 unrun。
