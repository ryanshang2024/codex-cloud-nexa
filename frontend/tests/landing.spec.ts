import {test,expect} from '@playwright/test';
import {signIn} from './helpers';

test('public project introduction, login entry and usable installation guides',async({page,request})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const privateCalls:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))privateCalls.push(r.url())});
 await page.goto('/');
 await expect(page.getByRole('heading',{level:1})).toHaveText('让每一份工作，清晰向前。');
 await expect(page.getByRole('heading',{name:'我的任务',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'AI 工作助手',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'管理端 · 统一配置与分配',exact:true})).toBeVisible();
 await page.getByRole('navigation').getByRole('link',{name:'下载 App',exact:true}).click();
 await expect(page.locator('#download')).toBeInViewport();
 const button=page.getByRole('button',{name:/安装 NEXA App|查看设备安装方式/});
 await button.click();
 await expect(page.getByRole('status')).toContainText(/下方|安装请求/);
 await page.getByRole('tab',{name:'iPhone / iPad',exact:true}).click();
 await expect(page.getByRole('tabpanel')).toContainText('Safari');
 await expect(page.getByRole('tabpanel')).toContainText('添加到主屏幕');
 await page.getByRole('tab',{name:'iPhone / iPad',exact:true}).press('ArrowLeft');
 await expect(page.getByRole('tab',{name:'Android',exact:true})).toBeFocused();
 await expect(page.getByRole('tabpanel')).toContainText('Chrome');
 expect(privateCalls).toEqual([]);expect(errors).toEqual([]);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:'../.local/employee-landing-desktop.png',fullPage:true});
 await page.setViewportSize({width:1280,height:900});
 await page.screenshot({path:'../.local/employee-landing-hero.png'});
 await page.getByRole('link',{name:'登录员工工作端',exact:true}).click();
 await expect(page).toHaveURL(/\/login$/);
 await expect(page.getByRole('heading',{name:'登录企业工作空间',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'返回项目介绍'}).click();
 await expect(page).toHaveURL(/\/$/);
 expect((await request.get('/api/work/dashboard')).status()).toBe(401);
});

test('mobile public page and installation steps remain usable without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/work-assistant');
 await expect(page.getByRole('heading',{level:1})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.getByRole('button',{name:'打开导航',exact:true}).click();
 await expect(page.getByRole('button',{name:'关闭导航',exact:true})).toHaveAttribute('aria-expanded','true');
 await page.getByRole('navigation').getByRole('link',{name:'产品能力',exact:true}).focus();
 await page.getByRole('navigation').getByRole('link',{name:'产品能力',exact:true}).press('Escape');
 await expect(page.getByRole('button',{name:'打开导航',exact:true})).toBeFocused();
 await page.getByRole('button',{name:'打开导航',exact:true}).click();
 await page.getByRole('navigation').getByRole('link',{name:'下载 App',exact:true}).click();
 await expect(page.getByRole('button',{name:'打开导航',exact:true})).toHaveAttribute('aria-expanded','false');
 await page.getByRole('tab',{name:'iPhone / iPad',exact:true}).click();
 await expect(page.getByRole('tabpanel')).toContainText('添加到主屏幕');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:'../.local/employee-landing-mobile.png',fullPage:true});
 await page.setViewportSize({width:320,height:740});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('manifest, real PNG icons and registered worker expose a valid employee app entry',async({page,request})=>{
 await page.goto('/');
 await expect(page.locator('link[rel="manifest"]')).toHaveAttribute('href','/manifest.webmanifest');
 const response=await request.get('/manifest.webmanifest');expect(response.status()).toBe(200);
 const manifest=await response.json();
 expect(manifest.start_url).toBe('/employee');expect(manifest.display).toBe('standalone');
 for(const icon of manifest.icons){
  const image=await request.get(icon.src);expect(image.status()).toBe(200);expect(image.headers()['content-type']).toContain('image/png');
  const bytes=await image.body();const size=Number(icon.sizes.split('x')[0]);
  expect(bytes.subarray(0,8).toString('hex')).toBe('89504e470d0a1a0a');
  expect(bytes.readUInt32BE(16)).toBe(size);expect(bytes.readUInt32BE(20)).toBe(size);
 }
 const worker=await page.evaluate(async()=>{const registration=await navigator.serviceWorker.ready;return {url:registration.active?.scriptURL,scope:registration.scope}});
 expect(worker.url).toContain('/work-assistant-sw.js');
 expect(worker.scope).toBe('http://127.0.0.1:3000/');
 const session=await page.context().newCDPSession(page);const parsed=await session.send('Page.getAppManifest');
 expect(parsed.errors).toEqual([]);
 await page.goto(manifest.start_url);await expect(page).toHaveURL(/\/login$/);
});

test('installation prompt cancellation and acceptance report their actual states',async({page})=>{
 await page.goto('/#download');
 for(const outcome of ['dismissed','accepted'] as const){
  await page.evaluate(outcome=>{
   const event=new Event('beforeinstallprompt',{cancelable:true}) as Event&{prompt:()=>Promise<void>;userChoice:Promise<{outcome:string}>};
   event.prompt=async()=>{};event.userChoice=Promise.resolve({outcome});window.dispatchEvent(event);
  },outcome);
  await page.getByRole('button',{name:'安装 NEXA App',exact:true}).click();
  await expect(page.getByRole('status')).toContainText(outcome==='dismissed'?'已取消安装':'已提交安装请求');
  await expect(page.getByRole('button',{name:'打开已安装 App',exact:true})).toHaveCount(0);
 }
 await page.evaluate(()=>window.dispatchEvent(new Event('appinstalled')));
 await expect(page.getByRole('button',{name:'打开已安装 App',exact:true})).toBeVisible();
});

test('installed worker preserves session/RBAC, never caches customer data, and fails safely offline',async({page,context})=>{
 await signIn(page,'sales');
 await page.evaluate(()=>navigator.serviceWorker.ready);
 await page.reload();await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true);
 expect((await page.request.get('/api/dashboard')).status()).toBe(403);
 expect((await page.request.get('/api/export')).status()).toBe(403);
 expect(await page.evaluate(()=>caches.keys())).toEqual([]);
 await context.setOffline(true);
 await page.goto('/employee?offline-acceptance=1');
 await expect(page.getByRole('heading',{name:'连接网络，继续你的工作。'})).toBeVisible();
 await expect(page.getByText('此设备没有缓存客户资料。',{exact:false})).toBeVisible();
 await expect(page.locator('.work-fields')).toHaveCount(0);
 await context.setOffline(false);
 await page.getByRole('link',{name:'连接后重新打开'}).click();
 await expect(page.getByRole('heading',{name:'我的任务，清晰可见。'})).toBeVisible();
 await page.getByRole('button',{name:'退出登录'}).click();
 await expect(page).toHaveURL(/\/$/);
 expect((await page.request.get('/api/work/dashboard')).status()).toBe(401);
});
