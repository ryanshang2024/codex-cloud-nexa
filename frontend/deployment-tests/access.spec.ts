import {test,expect,APIRequestContext} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const domain='nexa-mk.voltwok.com';
const authorization='Basic '+Buffer.from('TEST_ONLY_operator:TEST_ONLY_private_demo_password').toString('base64');
const base='http://127.0.0.1:3011';
async function personalHeaders(request:APIRequestContext){
 const credential=JSON.parse(readFileSync(resolve(process.cwd(),'../.local/demo-logins.json'),'utf8'))['nexa-demo:admin'];
 const response=await request.post(base+'/api/auth/login',{headers:{Host:domain,Authorization:authorization,Origin:'https://'+domain},data:credential});
 expect(response.status()).toBe(200);expect((await response.json()).access_token).toBeUndefined();
 const cookie=response.headers()['set-cookie'];expect(cookie).toContain('HttpOnly');expect(cookie).toContain('Secure');expect(cookie).toContain('SameSite=lax');
 return {Host:domain,Authorization:authorization,Cookie:cookie.split(';')[0]};
}

test('employee/admin/login and APIs keep private-demo invitation protection',async({request})=>{
 for(const path of ['/login','/employee','/admin','/api/dashboard','/api/work/dashboard']){
  const response=await request.get(base+path,{headers:{Host:domain}});
  expect(response.status()).toBe(401);
  expect(response.headers()['www-authenticate']).toContain('Basic');
  expect(response.headers()['cache-control']).toContain('no-store');
 }
 const write=await request.post(base+'/api/accounts',{headers:{Host:domain},data:{name:''}});
 expect(write.status()).toBe(401);
});

test('wrong and malformed credentials never gain the server-side API identity',async({request})=>{
 for(const value of ['Basic !!!!','Bearer TEST_ONLY_fake',
  'Basic '+Buffer.from('TEST_ONLY_operator:wrong').toString('base64')]){
  expect((await request.get(base+'/api/dashboard',{headers:{Host:domain,Authorization:value}})).status()).toBe(401);
 }
});

test('configured private demo login permits rendering and isolated DEMO data',async({request})=>{
 const headers={Host:domain,Authorization:authorization};
 expect((await request.get(base+'/',{headers})).status()).toBe(200);
 expect((await request.get(base+'/nexa-logo.png',{headers})).status()).toBe(200);
 expect((await request.get(base+'/api/dashboard',{headers})).status()).toBe(401);
 const individual=await personalHeaders(request);
 const dashboard=await request.get(base+'/api/dashboard',{headers:individual});
 expect(dashboard.status()).toBe(200);
 const data=await dashboard.json();
 expect(data.accounts.length).toBeGreaterThan(0);
 expect(data.accounts.every((a:{is_demo:boolean})=>a.is_demo)).toBeTruthy();
 expect(data.auto_send).toBe(false);
});

test('public writes reject the local-development Origin exception and foreign Origin',async({request})=>{
 const individual=await personalHeaders(request);
 for(const origin of ['http://localhost:3000','https://untrusted.example']){
  const response=await request.post(base+'/api/accounts',{
   headers:{...individual,Origin:origin},data:{name:''}});
  expect(response.status()).toBe(403);
 }
 // No mutation: invalid account body proves the legitimate domain passed the Origin check.
 const response=await request.post(base+'/api/accounts',{
  headers:{...individual,Origin:'https://nexa-mk.voltwok.com'},data:{name:''}});
 expect(response.status()).toBe(422);
});

test('production defaults deny publication when access credentials are missing',async({request})=>{
 for(const path of ['/login','/employee','/admin','/api/dashboard']){
  const response=await request.get('http://127.0.0.1:3012'+path,{headers:{Host:domain}});
  expect(response.status()).toBe(503);
 }
});

test('project landing and exact installation assets are public while app data stays protected',async({request})=>{
 for(const port of [3011,3012]){
  const url='http://127.0.0.1:'+port;
  for(const path of ['/','/work-assistant','/manifest.webmanifest','/work-assistant-sw.js','/nexa-logo.png','/nexa-symbol.png','/app-icons/192','/app-icons/512']){
   const response=await request.get(url+path,{headers:{Host:domain}});expect(response.status()).toBe(200);
  }
  expect((await request.get(url+'/api/export',{headers:{Host:domain}})).status()).toBe(port===3011?401:503);
  expect((await request.get(url+'/work-assistant-admin',{headers:{Host:domain}})).status()).toBe(port===3011?401:503);
 }
});

test('SaaS uses individual login without Basic admin fallback and rejects a foreign host',async({request})=>{
 const url='http://127.0.0.1:3013';
 expect((await request.get(url+'/',{headers:{Host:domain}})).status()).toBe(200);
 expect((await request.get(url+'/api/dashboard',{headers:{Host:domain}})).status()).toBe(401);
 expect((await request.get(url+'/',{headers:{Host:'untrusted.example'}})).status()).toBe(400);
});
