import {test,expect} from '@playwright/test';

const domain='nexa-mk.voltwok.com';
const authorization='Basic '+Buffer.from('TEST_ONLY_operator:TEST_ONLY_private_demo_password').toString('base64');
const base='http://127.0.0.1:3011';

test('public workspace and every administrative route reject anonymous access',async({request})=>{
 for(const path of ['/','/api/dashboard','/nexa-logo.png']){
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
 const dashboard=await request.get(base+'/api/dashboard',{headers});
 expect(dashboard.status()).toBe(200);
 const data=await dashboard.json();
 expect(data.accounts.length).toBeGreaterThan(0);
 expect(data.accounts.every((a:{is_demo:boolean})=>a.is_demo)).toBeTruthy();
 expect(data.auto_send).toBe(false);
});

test('public writes reject the local-development Origin exception and foreign Origin',async({request})=>{
 for(const origin of ['http://localhost:3000','https://untrusted.example']){
  const response=await request.post(base+'/api/accounts',{
   headers:{Host:domain,Authorization:authorization,Origin:origin},data:{name:''}});
  expect(response.status()).toBe(403);
 }
 // No mutation: invalid account body proves the legitimate domain passed the Origin check.
 const response=await request.post(base+'/api/accounts',{
  headers:{Host:domain,Authorization:authorization,Origin:'https://nexa-mk.voltwok.com'},data:{name:''}});
 expect(response.status()).toBe(422);
});

test('production defaults deny publication when access credentials are missing',async({request})=>{
 for(const path of ['/','/api/dashboard']){
  const response=await request.get('http://127.0.0.1:3012'+path,{headers:{Host:domain}});
  expect(response.status()).toBe(503);
 }
});
