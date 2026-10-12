'use client';
import {useEffect} from 'react';

export default function RegisterWorkApp(){
 useEffect(()=>{
  if('serviceWorker' in navigator&&window.isSecureContext){
   navigator.serviceWorker.register('/work-assistant-sw.js',{scope:'/',updateViaCache:'none'}).catch(()=>{
    // Installation support is optional; ordinary login remains available.
   });
  }
 },[]);
 return null;
}
