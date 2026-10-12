'use client';

import {useRef,useState} from 'react';

export default function LandingHeader(){
 const [open,setOpen]=useState(false);const toggle=useRef<HTMLButtonElement>(null);
 return <header className="lp-header" onKeyDown={event=>{if(event.key==='Escape'&&open){setOpen(false);toggle.current?.focus()}}}>
  <div className="lp-header-inner">
   <a className="lp-brand" href="/" aria-label="NEXA AI Work Assistant 首页"><img src="/nexa-logo.png" width="170" height="48" alt="NEXA"/><span>AI WORK ASSISTANT</span></a>
   <nav id="landing-navigation" aria-label="项目介绍导航" data-open={open} onClick={()=>setOpen(false)}><a href="#features">产品能力</a><a href="#journey">使用流程</a><a href="#download">下载 App</a></nav>
   <a className="lp-header-login" href="/login">登录 App <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
   <button ref={toggle} className="lp-menu-toggle" aria-label={open?'关闭导航':'打开导航'} aria-controls="landing-navigation" aria-expanded={open} onClick={()=>setOpen(value=>!value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={open?'m6 6 12 12M6 18 18 6':'M4 7h16M4 12h16M4 17h16'}/></svg></button>
  </div>
 </header>;
}
