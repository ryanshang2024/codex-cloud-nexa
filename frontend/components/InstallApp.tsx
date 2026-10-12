'use client';
import {useEffect,useId,useRef,useState} from 'react';

type Platform='desktop'|'android'|'ios';
type InstallPrompt=Event&{prompt:()=>Promise<void>;userChoice:Promise<{outcome:'accepted'|'dismissed'}>};
const guides:{id:Platform;label:string;steps:string[]}[]=[
 {id:'desktop',label:'电脑',steps:['用 Chrome 或 Edge 打开 NEXA 网站。','点击上方安装按钮，或使用浏览器地址栏的安装图标。','确认安装后，从桌面或应用列表打开 NEXA。']},
 {id:'android',label:'Android',steps:['用 Chrome 打开 NEXA 网站。','点击上方安装按钮；也可打开浏览器菜单，选择“安装应用”或“添加到主屏幕”。','确认后，从主屏幕打开 NEXA 并登录企业账号。']},
 {id:'ios',label:'iPhone / iPad',steps:['用 Safari 打开 NEXA 网站。','点击“共享”按钮，选择“添加到主屏幕”。','确认添加，再从主屏幕打开 NEXA 并登录企业账号。']},
];

export default function InstallApp(){
 const [platform,setPlatform]=useState<Platform>('desktop');const [ready,setReady]=useState(false);const [installed,setInstalled]=useState(false);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
 const deferred=useRef<InstallPrompt|null>(null);const guideRef=useRef<HTMLDivElement>(null);const uid=useId();
 useEffect(()=>{
  const media=window.matchMedia('(display-mode: standalone)');
  const update=()=>setInstalled(media.matches||Boolean((navigator as Navigator&{standalone?:boolean}).standalone));update();
  if(/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1))setPlatform('ios');
  else if(/Android/.test(navigator.userAgent))setPlatform('android');
  const prompt=(event:Event)=>{event.preventDefault();deferred.current=event as InstallPrompt;setReady(true)};
  const complete=()=>{deferred.current=null;setReady(false);setInstalled(true);setNotice('NEXA 已安装，可从设备主屏幕或应用列表打开。')};
  window.addEventListener('beforeinstallprompt',prompt);window.addEventListener('appinstalled',complete);media.addEventListener('change',update);
  return()=>{window.removeEventListener('beforeinstallprompt',prompt);window.removeEventListener('appinstalled',complete);media.removeEventListener('change',update)};
 },[]);
 async function install(){
  if(busy)return;
  if(installed){location.assign('/employee');return}
  if(!deferred.current){setNotice('请按下方与你的设备对应的步骤安装，也可以直接登录网页版。');guideRef.current?.focus();return}
  const event=deferred.current;deferred.current=null;setReady(false);setBusy(true);setNotice('');
  try{await event.prompt();const choice=await event.userChoice;setNotice(choice.outcome==='accepted'?'已提交安装请求，完成后可从设备打开 NEXA。':'已取消安装，你仍可直接登录网页版。')}
  catch{setNotice('浏览器暂时无法启动安装，请使用下方的设备安装步骤。')}
  finally{setBusy(false)}
 }
 const guide=guides.find(g=>g.id===platform)!;
 function changePlatform(event:React.KeyboardEvent<HTMLButtonElement>,index:number){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;
  setPlatform(guides[next].id);document.getElementById(uid+'-'+guides[next].id)?.focus();
 }
 return <div className="lp-install-card"><div className="lp-install-heading"><img src="/nexa-symbol.png" width="58" height="56" alt=""/><div><strong>NEXA AI Work Assistant</strong><p>你的企业工作空间</p></div><span className="lp-web-badge">网页版 App</span></div><button className="lp-button lp-button-primary lp-install-button" disabled={busy} onClick={install}>{busy?'正在启动安装…':installed?'打开已安装 App':ready?'安装 NEXA App':'查看设备安装方式'}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg></button><p className="lp-install-description">使用企业账号登录。安装可用性取决于设备与浏览器；无需另行下载安装包。</p>{notice&&<p className="lp-install-status" role="status">{notice}</p>}<div ref={guideRef} tabIndex={-1} className="lp-install-guide"><div role="tablist" aria-label="选择安装设备">{guides.map((g,index)=><button key={g.id} id={uid+'-'+g.id} role="tab" aria-selected={platform===g.id} aria-controls={uid+'-panel'} tabIndex={platform===g.id?0:-1} onClick={()=>setPlatform(g.id)} onKeyDown={e=>changePlatform(e,index)}>{g.label}</button>)}</div><div id={uid+'-panel'} role="tabpanel" aria-labelledby={uid+'-'+platform}><ol>{guide.steps.map(step=><li key={step}>{step}</li>)}</ol></div></div><p className="lp-install-footnote">任务读取和工作结果保存需要网络连接。</p></div>
}
