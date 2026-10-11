import {expect,Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
export async function signIn(page:Page,role='admin'){
 const logins=JSON.parse(readFileSync(resolve(process.cwd(),'../.local/demo-logins.json'),'utf8'));
 const credential=logins['nexa-demo:'+role];
 if(!credential)throw new Error('Local personal test account not initialized; run reviewed setup.');
 await page.goto('/');
 await page.getByLabel('企业空间',{exact:true}).fill(credential.tenant_id);
 await page.getByLabel('账号',{exact:true}).fill(credential.user_id);
 await page.getByLabel('密码',{exact:true}).fill(credential.password);
 await page.getByRole('button',{name:'登录工作空间',exact:true}).click();
 await expect(page).toHaveURL(role==='sales'?/\/employee$/:/\/admin$/);
}
