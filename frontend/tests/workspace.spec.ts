import {test,expect} from '@playwright/test';
import {signIn} from './helpers';

test('DEMO research → evidence → consent review → bilingual draft → approval → reply → CRM',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await signIn(page);await expect(page.getByRole('heading',{name:'让每一次连接，更有依据。'})).toBeVisible();
 await expect(page.getByText('正在连接工作台…',{exact:true})).toHaveCount(0);
 await page.screenshot({path:'../.local/workspace-desktop.png',fullPage:true});
 await page.getByRole('navigation').getByRole('button',{name:'客户研究'}).click();
 await page.getByLabel('目标省份').selectOption('ON');await page.getByLabel('客户画像').selectOption('H06');
 await page.getByRole('button',{name:'运行 DEMO 研究'}).click();
 await expect(page.getByRole('status')).toContainText('DEMO 研究任务已创建');
 const account=page.getByRole('button',{name:'DEMO ON H06 HVAC 1',exact:true});
 await expect(account).toBeVisible({timeout:20000});await account.click();
 const modal=page.getByRole('dialog');await expect(modal.getByRole('heading',{name:'可追溯证据'})).toBeVisible();
 await expect(modal).toContainText('DEMO_ONLY');
 await modal.getByRole('button',{name:'草稿与审批',exact:true}).click();
 await modal.getByRole('button',{name:'提交 DEMO 联系依据'}).click();
 await expect(modal.getByRole('button',{name:'合规人审通过'}).last()).toBeVisible();
 await modal.getByRole('button',{name:'合规人审通过'}).last().click();
 await expect(modal.getByText('联系依据已审批',{exact:true}).last()).toBeVisible();
 await modal.getByRole('button',{name:'生成 英语 草稿'}).click();
 await expect(modal.getByText('A conversation about your HVAC services').last()).toBeVisible();
 await modal.getByRole('button',{name:'人工审批此版本'}).last().click();
 await expect(modal.getByText('草稿已审批').last()).toBeVisible();
 await modal.getByRole('button',{name:'切换为 法语'}).last().click();
 await expect(modal.getByText('Échange au sujet de votre activité CVAC').last()).toBeVisible();
 await expect(modal.getByText('待审批').last()).toBeVisible();
 await modal.getByRole('button',{name:'回复与 CRM',exact:true}).click();
 await modal.getByRole('button',{name:'索要价格',exact:true}).click();
 await expect(modal.getByText('PRICE_REQUEST').first()).toBeVisible();
 await modal.getByRole('button',{name:'关闭客户详情'}).click();
 await page.getByRole('navigation').getByRole('button',{name:'商机管理'}).click();
 await expect(page.getByRole('heading',{name:'商机进度'})).toBeVisible();
 await expect(page.getByText('DEMO ON H06 HVAC 1 (FICTIONAL)').first()).toBeVisible();
 await page.screenshot({path:'../.local/workspace-crm.png',fullPage:true});
 expect(errors).toEqual([]);
});

test('mobile navigation, no horizontal viewport overflow, source authorization status',async({page})=>{
 await page.setViewportSize({width:390,height:844});await signIn(page);
 await expect(page.getByRole('heading',{name:'让每一次连接，更有依据。'})).toBeVisible();
 await expect(page.getByText('正在连接工作台…',{exact:true})).toHaveCount(0);
 await page.screenshot({path:'../.local/workspace-mobile.png',fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.getByRole('navigation').getByRole('button',{name:'客户画像'}).click();
 const residential=page.locator('section.profile').filter({has:page.getByRole('heading',{name:'住宅热泵安装公司',exact:true})});
 await expect(residential).toContainText('热泵安装');
 await expect(residential).toContainText('目标市场：住宅');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.local/workspace-icp-mobile.png',fullPage:true});
 await page.getByRole('navigation').getByRole('button',{name:'数据来源'}).click();
 await expect(page.getByRole('heading',{name:'Source Router'})).toBeVisible();
 await page.getByRole('button',{name:'查看路由',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('路由策略已读取');
 await expect(page.getByText('真实接入关闭。需要条款核验、凭据与数据用途授权。').first()).toBeVisible();
});

test('workspace rejects cross-origin writes',async({request})=>{
 const response=await request.post('/api/jobs',{headers:{Origin:'https://untrusted.example'},data:{province:'QC',profile:'H01',mode:'demo',idempotency_key:'csrf-blocked'}});
 expect(response.status()).toBe(403);
 expect((await response.json()).detail).toBe('Cross-origin request rejected');
});

test('blocked draft review explains the evidence problem inside the open dialog',async({page})=>{
 await page.route('**/api/drafts/*/approve',route=>route.fulfill({status:409,contentType:'application/json',
  body:JSON.stringify({detail:{blocked_by:['draft_citations_invalid']}})}));
 await signIn(page);
 await expect(page.getByText('正在连接工作台…',{exact:true})).toHaveCount(0);
 await page.getByRole('navigation').getByRole('button',{name:'客户研究'}).click();
 await page.getByRole('button',{name:'DEMO ON H06 HVAC 1',exact:true}).click();
 const modal=page.getByRole('dialog');
 await modal.getByRole('button',{name:'草稿与审批',exact:true}).click();
 await modal.getByRole('button',{name:'人工审批此版本'}).last().click();
 await expect(modal.getByRole('alert')).toContainText('引用证据已失效');
 await expect(modal.getByRole('alert')).toContainText('重新生成草稿');
 await expect(modal.getByRole('alert')).toBeInViewport();
 await modal.screenshot({path:'../.local/workspace-approval-error.png'});
});
