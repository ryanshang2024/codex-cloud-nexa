'use client';

import {useEffect,useRef,useState,type ReactNode} from 'react';

// Same forest/birds loop as the selected NEXA Energy overview, compressed and
// served locally without audio, third-party requests or customer information.
const HERO_VIDEO='/nexa-hero-forest.mp4';

export default function LandingHero({children}:{children:ReactNode}){
 const root=useRef<HTMLElement>(null),video=useRef<HTMLVideoElement>(null);
 const entered=useRef(false),entrances=useRef<Animation[]>([]);
 const [paused,setPaused]=useState(false),[reduced,setReduced]=useState(false),[ready,setReady]=useState(false);
 const [playing,setPlaying]=useState(false);

 useEffect(()=>{
  const section=root.current,media=video.current;
  if(!section||!media)return;
  let visible=true,disposed=false;
  const preference=matchMedia('(prefers-reduced-motion: reduce)');
  const sync=()=>{
   if(disposed)return;
   setReduced(preference.matches);
   const run=!paused&&!preference.matches&&!document.hidden&&visible;
   section.dataset.motion=preference.matches?'reduced':run?'running':'paused';
   if(!run){media.pause();entrances.current.forEach(a=>{if(a.playState!=='finished')a.finish()});return}
   const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
   if(!connection?.saveData){
    if(!media.hasAttribute('src'))media.src=HERO_VIDEO;
    media.play().catch(()=>{/* The gradient remains visible when media is unavailable. */});
   }
  };
  if(!entered.current){
   entered.current=true;
   if(!preference.matches){
    const cues:[string,number,number,number][]=[['.lp-pill',0,500,10],['.lp-hero-eyebrow',100,600,16],['#hero-title',160,600,16],['.lp-lead',200,600,16],['.lp-actions',300,600,16],['.lp-work-visual',500,800,30]];
    entrances.current=cues.flatMap(([selector,delay,duration,y])=>{
     const el=section.querySelector(selector);
     return el?[el.animate([{opacity:0,transform:`translateY(${y}px)`},{opacity:1,transform:'translateY(0)'}],{delay,duration,easing:'cubic-bezier(.22,1,.36,1)',fill:'backwards'})]:[];
    });
   }
  }
  const observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync()},{threshold:.01});
  observer.observe(section);preference.addEventListener('change',sync);document.addEventListener('visibilitychange',sync);
  setReady(true);sync();
  return ()=>{disposed=true;observer.disconnect();preference.removeEventListener('change',sync);document.removeEventListener('visibilitychange',sync);media.pause()};
 },[paused]);

 useEffect(()=>()=>entrances.current.forEach(a=>a.cancel()),[]);
 const label=reduced?'已启用减少动态效果':paused?'继续动画':'暂停动画';
 return <section ref={root} id="overview" className="lp-hero" aria-labelledby="hero-title" data-motion="paused">
  <div className="lp-hero-atmosphere" aria-hidden="true">
   <video ref={video} className={'lp-hero-video'+(playing?' is-playing':'')} muted loop playsInline preload="none" tabIndex={-1} onPlaying={()=>setPlaying(true)} onError={()=>setPlaying(false)}/>
   <div className="lp-hero-wash"/>
  </div>
  {children}
  <button className="lp-motion-control" hidden={!ready} disabled={reduced} aria-pressed={paused||reduced} onClick={()=>setPaused(value=>!value)}>
   <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paused&&!reduced?'m9 5 11 7-11 7V5Z':'M8 5v14M16 5v14'}/></svg>{label}
  </button>
 </section>;
}
