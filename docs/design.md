# VI 应用记录

新增 [Employee Landing Page](employee-landing.md)：对外介绍四项员工能力、工作流程与企业分工，提供独立个人登录及设备安装指引。页面没有客户资料、虚构销售数字或未经接入的功能承诺。公开介绍页已按用户指定的 NEXA Energy 页面统一视觉与头部动画，具体公开页面 token 见下文；工作端与后台沿用既有 VI。

依据用户提供 NEXA_VI_Guidelines_CN.pdf，第7/10/12/17/18页。此 PDF 是栅格化指南，没有可抽取的正文；已逐页渲染并视觉核对。品牌标识从第7页母版区域提取，保持比例与留白，非字体重绘；可在正式发布时替换为用户提供的原始 SVG。

设计 token：NEXA Green #22C55E、Energy Green #10B981、Deep Space #0B1F38、Sky Blue #38BEFB、Mist Gray #E5E7EB、Cloud White #FAFBFC、Mint Glow #CFFADD、Forest #071A14。白底、薄荷焦点卡、深色数据、24px圆角、8/16/24/32间距。正文指定 Noto Sans / Noto Sans SC，离线系统缺字时使用系统回退；品牌字标用原图。按钮采用深色字配绿色底；状态同时给文本，不只依赖颜色；键盘焦点明显，触控目标至少44px，尊重 reduced-motion。

字体通过 @fontsource/noto-sans 与 @fontsource/noto-sans-sc 5.3.0 离线打包，许可 OFL-1.1；不访问外部字体 CDN。所有演示数据明确显示 DEMO；图表与指标不能被称为真实业务结果。界面主流程保持业务语言，凭据/网络配置放在来源管理中。


## V3.3 双端界面

管理后台保留研究、画像、来源、线索审核、分配、CRM 和授权分析；企业管理集中设置个人功能权限、省份分析范围、模型价格、角色配额、企业预算和提额审批。员工端只显示我的任务、待跟进、授权工作助手和工作汇报。菜单之外，API 与 Agent Tool 都实施身份/记录/字段授权。

实际浏览器截图：[Admin 管理工作台](previews/v3.3-admin-console.png)、[Employee AI 工作助手](previews/v3.3-employee-app.png)、[员工移动端](previews/v3.3-employee-mobile.png)。保留 NEXA 绿色/深蓝、低干扰卡片和清晰任务动作；示例客户使用 DEMO 标识。旧 V3.2 视频和画册不能证明 V3.3 权限或真实转化效果。


## 公开介绍页与 NEXA Energy 统一

用户选定 [Energy Overview](https://nexa-energy.voltwok.com/#overview) 为公开页面的设计依据。`employee-landing.css` 统一 `/`、`/work-assistant` 与安装卡片：品牌绿 #00A651、行动绿 #007D43、墨色 #08131C、Cloud White #FAFBFC、轻边框 #DEEBE3；保持现有官方 NEXA 标识和离线中文字体。统一居中首屏、半透明固定导航、胶囊 CTA、玻璃工作台和阅读层级。样式仅作用于公开页面组件，不改变工作端的数据权限或引入其他 UI 库。

`LandingHero.tsx` 管理原森林/飞鸟视频、0.5–0.8 秒错开入场、动画暂停、减少动态效果及视口/页面可见性。`LandingHeader.tsx` 管理移动菜单的键盘行为。背景视频随网站同站发布，正文不是视频画面的一部分，仍可选择、朗读和操作；无 JavaScript 时项目文本和登录入口仍显示。具体来源和验证见 [介绍页说明](employee-landing.md) 与 [验收证据](employee-landing-evidence.json)。
