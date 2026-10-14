# macOS 本地运行与完整操作流程

下载 ZIP 并解压，在这个项目文件夹中运行。可以放在 Downloads、Documents 或其他目录；启动脚本会找到自己的项目目录，无需创建 `/workspace`。

## 1. 准备

- 启动 Docker Desktop，等待 Docker Engine 正常运行。数据库以本机 Docker 容器运行。
- 安装 Node.js 24、Python 3.12 和 uv。使用 Homebrew 的 Mac 可执行 `brew install node@24 python@3.12 uv`；Docker Desktop 使用其官方 Mac 安装包。
- 若 Node.js 24 未加入终端路径，先执行 `export PATH="$(brew --prefix node@24)/bin:$PATH"`。这仅影响当前终端。
- 首次安装需要网络，以下载锁定的 Python/npm 依赖和 PostgreSQL 镜像。压缩包包含源码、锁文件、品牌资源及森林动画，不包含依赖、数据库或任何现成账号密码。

## 2. 启动

在 Terminal 输入 `cd `（末尾空格），把解压后的项目文件夹拖入终端，再按回车。

```bash
bash START_MAC.command
```

脚本检查工具与 Docker，通过仓库锁文件安装依赖、构建网页，初始化本机 PostgreSQL，启动 API、研究 Worker、网页服务，并自动打开浏览器。首次构建较慢，之后保留本地数据库。成功后访问本机 `http://127.0.0.1:3000/`；这不是已发布的公网地址。

## 3. 登录

```bash
open -a TextEdit .local/demo-logins.json
```

只在自己的 Mac 上查看该文件，不分享它。每台电脑首次启动时生成独立随机密码。登录页填写：

| 输入 | 管理员 | 员工 |
| --- | --- | --- |
| 企业空间 | `nexa-demo` | `nexa-demo` |
| 账号 | `nexa-demo:admin` | `nexa-demo:sales` |
| 密码 | 文件中对应账号的 password | 文件中对应账号的 password |

管理员登录进入 `/admin`。退出后使用员工账号进入 `/employee`；需要同时体验两个角色时，可用两个浏览器或一个普通窗口和一个无痕窗口。

## 4. 完整走一遍

1. 管理员查看客户画像与来源路由，选择 QC / H01 或 ON / H06，运行明确标注的 DEMO 研究。
2. 打开研究结果，查看证据、资质、评分与排除原因；DEMO 中的企业与联系人都是虚构资料。
3. 在“草稿与审批”提交 DEMO 联系依据并人审，生成 FR/EN 草稿，再审批当前版本。第一阶段没有实际发送，审批不等于发送。
4. 在“企业管理”中将合格客户与工作要求分配给员工，只勾选其工作所需的字段。
5. 使用员工账号查看“我的任务”，打开分配任务、记录跟进结果并更新进度。员工不拥有完整线索池或批量研究/导出权限。
6. 回到管理员界面审核员工结果；也可在“回复与 CRM”中录入 DEMO 回复分类，检查任务和商机阶段。
7. 查看审批与操作审计、AI 配额策略；真实模型与获客供应商默认关闭，不需要付费 API Key 即可跑 DEMO 流程。

若只想快速生成一次完整开发演示记录，启动后在项目目录执行 `.venv/bin/python scripts/demo.py`；输出在 `.local/demo-results.json`，仍是明确标注的 DEMO，包含发送被拒绝的检查。不要同时运行此脚本与会修改同一 DEMO 数据的浏览器测试。

## 5. 停止与再次打开

```bash
bash STOP_MAC.command
# 下次启动（已有依赖与构建时）：
.venv/bin/python scripts/dev.py up
```

停止仅针对匹配项目命令、进程组及启动时间的 API/Worker/网页进程，保留数据库。默认端口：网页 3000、API 8000、数据库 54329；都绑定本机。同一台电脑请在同一个项目副本中重复启动。

如失败，查看 `.local/api.log`、`.local/worker.log`、`.local/frontend.log`；不要发送密码/令牌文件。Mac 进程识别使用原生 `ps`，保留原有进程组与启动时间验证；云端验证覆盖该兼容路径及 Linux 的重复启动/停止，同时检查 Python 3.12 的 Intel / Apple Silicon 锁定依赖解析和已固定摘要的数据库镜像架构。实体 Mac 与 Docker Desktop 上的完整安装尚未实测。


## 打包前验证（2026-10-14，America/Toronto）

- 从项目外目录运行安装脚本，依赖校验与生产构建成功；无需云端固定目录。
- 8 项进程识别检查通过，覆盖命令、独立进程组、PID 启动时间与过期 PID；macOS 的 `ps` 接口兼容路径在 Linux 上验证。
- Linux 上重复启动不创建新的项目进程；现有 API、Worker 与网页进程通过 Linux / macOS 兼容路径均识别为本项目。
- 两项管理员分配 → 员工执行 → CRM 回写/撤回，以及匿名/移动端权限浏览器旅程通过。
- Apple Silicon / Intel 的 Python 3.12 依赖分别使用锁文件、二进制限定及 require-hashes 完成 dry-run 解析；不是实体 Mac 安装。Next 锁文件包含 darwin arm64/x64 编译依赖。
- PostgreSQL 镜像清单原文 SHA-256 与固定摘要相符，包含 Linux amd64 / arm64，供 Docker Desktop 使用。
