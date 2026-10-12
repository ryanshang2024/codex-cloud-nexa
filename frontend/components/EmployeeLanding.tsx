import InstallApp from './InstallApp';
import LandingHero from './LandingHero';
import LandingHeader from './LandingHeader';

function Arrow(){return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>}
function Mark({kind}:{kind:'task'|'spark'|'reply'|'report'|'shield'}){
 const paths={task:'M7 4h10v3H7z M5 6H3v15h18V6h-2 M7 12h10 M7 16h6',spark:'m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z',reply:'M21 11a8 8 0 0 1-8 8H8l-5 3V11a8 8 0 0 1 18 0z M7 10h10 M7 14h6',report:'M5 3h10l4 4v14H5z M14 3v5h5 M9 12h6 M9 16h6',shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-6'};
 return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[kind]}/></svg>;
}
const features=[
 {kind:'task' as const,title:'我的任务',subtitle:'清楚知道，下一步做什么。',body:'查看企业分配的工作、必要客户资料和执行要求。把注意力放在当前最需要推进的事情上。'},
 {kind:'spark' as const,title:'AI 工作助手',subtitle:'围绕你的工作，辅助执行。',body:'查询任务信息、整理工作摘要，使用企业开放的跟进草稿能力。每次辅助，都围绕已授权的工作。'},
 {kind:'reply' as const,title:'客户跟进',subtitle:'让每一次进展，都有记录。',body:'记录联系结果和项目进展，更新任务状态。客户回复报告回到管理端审核，团队协作有据可查。'},
 {kind:'report' as const,title:'工作汇报',subtitle:'执行结果，回到同一个平台。',body:'从自己的任务与记录整理工作汇报，让管理员掌握进度，也让下一步协作更加清晰。'},
];

export default function EmployeeLanding(){return <div className="employee-landing">
 <a className="lp-skip" href="#landing-main">跳到项目介绍</a>
 <LandingHeader/>
 <main id="landing-main" className="lp-main">
  <LandingHero><div className="lp-hero-copy"><p className="lp-pill"><span/> 企业 AI 工作平台 · Employee App</p><p className="lp-hero-eyebrow">INTELLIGENCE. CONNECTED.</p><h1 id="hero-title">让每一份工作，<br/><em>清晰向前。</em></h1><p className="lp-lead">从企业分配的任务开始，连接工作信息、<br className="lp-desktop-break"/>客户跟进与个人汇报。你的工作，始终有方向。</p><div className="lp-actions"><a className="lp-button lp-button-primary" href="/login">登录员工工作端 <Arrow/></a><a className="lp-button lp-button-outline" href="#download">安装到我的设备 <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg></a></div><p className="lp-hero-note"><Mark kind="shield"/> 企业统一授权 · 个人工作空间 · 结果统一回写</p></div>
  <figure className="lp-work-visual" aria-label="员工工作流程概览">
   <div className="lp-app-preview">
    <div className="lp-preview-top"><div className="lp-preview-brand"><img src="/nexa-logo.png" width="126" height="36" alt="NEXA"/><span>Employee App</span></div><span className="lp-preview-badge">企业授权 · 个人工作空间</span><span className="lp-preview-profile"><Mark kind="shield"/>我的工作</span></div>
    <div className="lp-preview-body">
     <div className="lp-preview-menu"><span className="active"><Mark kind="task"/>我的任务</span><span><Mark kind="spark"/>工作助手</span><span><Mark kind="reply"/>客户跟进</span><span><Mark kind="report"/>工作汇报</span><small>INTELLIGENCE.<br/>CONNECTED.</small></div>
     <div className="lp-preview-content">
      <div className="lp-preview-heading"><div><h2>工作有方向。协作有记录。</h2><p>从分配到执行，连接工作的每一步。</p></div><span className="lp-task-tag">按企业授权开放</span></div>
      <div className="lp-preview-capabilities">{features.map(f=><div key={f.kind}><Mark kind={f.kind}/><span>{f.title}</span><strong>{({task:'任务有分配',spark:'辅助有边界',reply:'进展有记录',report:'协作有依据'})[f.kind]}</strong></div>)}</div>
      <div className="lp-preview-panels">
       <div className="lp-preview-work"><p className="lp-mini-label">ONE CONNECTED WORKFLOW</p><div className="lp-preview-task"><span className="lp-task-check">1</span><div><strong>接收企业分配的工作</strong><small>任务要求与必要资料，清晰可见</small></div><Mark kind="task"/></div><div className="lp-preview-task"><span className="lp-task-check">2</span><div><strong>使用授权助手，推进执行</strong><small>查询信息 · 记录进展 · 整理摘要</small></div><Mark kind="spark"/></div><div className="lp-preview-task"><span className="lp-task-check">3</span><div><strong>提交工作结果，连接协作</strong><small>个人记录与工作汇报，回到统一平台</small></div><Mark kind="report"/></div></div>
       <div className="lp-preview-assistant"><span className="lp-assistant-symbol"><Mark kind="spark"/></span><strong>围绕任务，辅助执行。</strong><p>你的信息和能力，<br/>来自企业授权。</p><span className="lp-assistant-boundary"><Mark kind="shield"/>企业资源，集中管理</span></div>
      </div>
      <div className="lp-preview-progress"><span/><p>工作结果回到统一平台</p><Mark kind="shield"/></div>
     </div>
    </div>
   </div>
  </figure></LandingHero>
  <div className="lp-principles"><div className="lp-container"><span>一套平台，连接团队执行</span><strong>任务有分配</strong><strong>信息有授权</strong><strong>结果有记录</strong></div></div>
  <section id="features" className="lp-section lp-container" aria-labelledby="feature-title"><div className="lp-section-heading"><div><p className="lp-eyebrow">BUILT FOR EVERY WORKDAY</p><h2 id="feature-title">把工作连接起来。<br/><span>把精力留给执行。</span></h2></div><p>无需在零散的信息间来回切换。<br/>在自己的工作空间，推进任务的每一步。</p></div><div className="lp-feature-grid">{features.map(f=><article className="lp-feature-card" key={f.kind}><span className="lp-feature-icon"><Mark kind={f.kind}/></span><h3>{f.title}</h3><strong>{f.subtitle}</strong><p>{f.body}</p></article>)}</div><p className="lp-feature-note">功能按企业授权开放。外部 AI 模型与语音能力由企业接入后启用；工作记录与进度更新可独立使用。</p></section>
  <section id="journey" className="lp-section lp-journey" aria-labelledby="journey-title"><div className="lp-container"><p className="lp-eyebrow">ONE CONNECTED WORKFLOW</p><h2 id="journey-title">从一项任务，到一次推进。</h2><p className="lp-section-intro">四个步骤，让个人执行与企业协作自然连接。</p><ol className="lp-steps">{[['企业开通账号','使用管理员为你创建的个人账号登录。'],['接收分配任务','查看自己的工作要求与明确开放的资料。'],['执行与工作辅助','按授权查询信息、跟进客户、记录进展。'],['结果回到平台','更新任务状态，形成记录与个人工作汇报。']].map(([title,body],i)=><li key={title}><span className="lp-step-number">0{i+1}</span><h3>{title}</h3><p>{body}</p></li>)}</ol></div></section>
  <section className="lp-section lp-container lp-governance" aria-labelledby="governance-title"><div><p className="lp-eyebrow">ENTERPRISE-MANAGED. TEAM-FOCUSED.</p><h2 id="governance-title">企业掌握资源。<br/><span>团队专注执行。</span></h2><p>客户资产与 AI 资源由企业集中管理。<br/>管理后台分配工作，员工在授权范围内协作。</p><a className="lp-text-link" href="/login">进入企业工作空间 <Arrow/></a></div><div className="lp-role-cards"><article><span className="lp-role-icon"><Mark kind="shield"/></span><div><small>ADMIN CONSOLE</small><h3>管理端 · 统一配置与分配</h3><p>客户研究与审核、销售分配、AI 配额及企业资源管理。</p></div></article><article><span className="lp-role-icon"><Mark kind="task"/></span><div><small>EMPLOYEE APP</small><h3>员工端 · 授权工作与执行</h3><p>我的任务、必要客户信息、工作助手与个人工作汇报。</p></div></article></div></section>
  <section id="download" className="lp-section lp-download" aria-labelledby="download-title"><div className="lp-container lp-download-grid"><div><p className="lp-eyebrow">YOUR WORKSPACE. YOUR DEVICE.</p><h2 id="download-title">把 NEXA，<br/>放进你的工作日。</h2><p>电脑上打开，手机上随行。<br/>登录网页版，或将 NEXA 安装到设备主屏幕。</p><div className="lp-device-tags"><span>电脑</span><span>Android</span><span>iPhone / iPad</span></div><a className="lp-button lp-button-outline" href="/login">直接登录网页版 <Arrow/></a></div><InstallApp/></div></section>
  <section className="lp-section lp-container lp-faq" aria-labelledby="faq-title"><div><p className="lp-eyebrow">BEFORE YOU START</p><h2 id="faq-title">开始之前，<br/>你可能想了解。</h2></div><div className="lp-faq-list"><details><summary>如何获得登录账号？</summary><p>由你的企业管理员创建个人账号并开放相关功能。使用管理员提供的企业空间、账号和密码登录。</p></details><details><summary>员工可以自主搜索完整客户库吗？</summary><p>员工工作端只开放本人被分配的任务及必要资料。客户发现、完整线索池、批量研究和导出由管理端掌握。</p></details><details><summary>下载 App 需要安装包或应用商店吗？</summary><p>当前提供可安装的网页版 App。支持的浏览器可直接安装；iPhone 和 iPad 使用 Safari 的“添加到主屏幕”。也可以一直使用网页版。</p></details><details><summary>没有网络时可以使用吗？</summary><p>登录、读取任务和保存工作结果需要网络连接。安装后仍使用企业账号，客户资料不会作为离线内容缓存到设备。</p></details></div></section>
  <section className="lp-final-cta lp-container"><div><p className="lp-eyebrow">INTELLIGENCE. CONNECTED.</p><h2>让今天的工作，<br/>从一个清晰的入口开始。</h2></div><a className="lp-button lp-button-primary" href="/login">登录 NEXA App <Arrow/></a></section>
 </main><footer className="lp-footer lp-container"><a className="lp-brand" href="/" aria-label="返回 NEXA 首页"><img src="/nexa-logo.png" width="145" height="41" alt="NEXA"/><span>Intelligence. Connected.</span></a><p>NEXA AI Work Assistant<br/><small>企业统一管理 · 员工授权使用</small></p><a href="/login">企业账号登录 <Arrow/></a></footer>
</div>}
