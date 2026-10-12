/* NEXA Work: network-only navigation; no task/customer/API/credential cache. */
self.addEventListener('install',event=>{event.waitUntil(self.skipWaiting())});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim())});
self.addEventListener('fetch',event=>{
 const request=event.request;const url=new URL(request.url);
 if(request.mode!=='navigate'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
 event.respondWith(fetch(request).catch(()=>new Response(
  '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>连接网络 · NEXA</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fafbfc;color:#0b1f38;font:16px/1.8 system-ui,sans-serif}main{max-width:460px;padding:32px}a{display:inline-block;margin-top:20px;background:#cffadd;color:#0b1f38;padding:12px 24px;border-radius:12px;text-decoration:none}h1{font-size:28px}</style><main><p>NEXA AI WORK ASSISTANT</p><h1>连接网络，继续你的工作。</h1><p>读取任务和保存结果需要网络连接。此设备没有缓存客户资料。</p><a href="/employee">连接后重新打开</a></main></html>',
  {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})));
});
