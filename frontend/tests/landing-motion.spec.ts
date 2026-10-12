import {test,expect} from '@playwright/test';
import path from 'node:path';

const mediaURL='**/nexa-hero-forest.mp4';

test('hero media actually plays, pauses by keyboard, resumes, and stops outside the viewport',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 // A tiny, self-generated green clip bounds this lifecycle test; the actual forest asset is verified separately.
 await page.route(mediaURL,route=>route.fulfill({path:path.join(__dirname,'fixtures/hero-motion.mp4'),contentType:'video/mp4'}));
 await page.goto('/');
 const hero=page.locator('#overview'),media=hero.locator('video');
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>el.currentTime>0&&!el.paused)).toBe(true);
 await expect(page.getByRole('heading',{level:1})).toBeVisible();
 await expect(media).toHaveCSS('opacity','1');
 const pause=page.getByRole('button',{name:'暂停动画',exact:true});
 await pause.focus();await pause.press('Space');
 await expect(page.getByRole('button',{name:'继续动画',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>el.paused)).toBe(true);
 const frame=await media.evaluate((el:HTMLVideoElement)=>el.currentTime);
 await expect.poll(()=>hero.evaluate(el=>el.getAnimations({subtree:true}).every(a=>a.playState!=='running'))).toBe(true);
 expect(await media.evaluate((el:HTMLVideoElement)=>el.currentTime)).toBe(frame);
 await page.getByRole('button',{name:'继续动画',exact:true}).click();
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>!el.paused)).toBe(true);
 await page.locator('#download').scrollIntoViewIfNeeded();
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>el.paused)).toBe(true);
 await page.evaluate(()=>scrollTo(0,0));
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>!el.paused)).toBe(true);
 await page.emulateMedia({reducedMotion:'reduce'});
 await expect(page.getByRole('button',{name:'已启用减少动态效果',exact:true})).toBeDisabled();
 await expect.poll(()=>media.evaluate((el:HTMLVideoElement)=>el.paused)).toBe(true);
 await expect(media).toHaveCSS('display','none');
 expect(errors).toEqual([]);
});

test('reduced motion never requests the decorative video and media failure preserves usable content',async({page})=>{
 let mediaCalls=0;await page.route(mediaURL,route=>{mediaCalls++;return route.abort()});
 await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/work-assistant');
 await expect(page.getByRole('button',{name:'已启用减少动态效果',exact:true})).toBeDisabled();
 await expect(page.getByRole('heading',{level:1})).toBeVisible();
 await expect(page.getByRole('link',{name:'登录员工工作端',exact:true})).toBeVisible();
 expect(mediaCalls).toBe(0);
 await expect(page.locator('.lp-hero-video')).not.toHaveAttribute('src',/.+/);
 expect(await page.locator('#overview').evaluate(el=>el.getAnimations({subtree:true}).length)).toBe(0);
 await page.emulateMedia({reducedMotion:'no-preference'});
 await expect.poll(()=>mediaCalls).toBe(1);
 await expect(page.locator('.lp-hero-atmosphere')).toBeVisible();
 await expect(page.getByRole('button',{name:'暂停动画',exact:true})).toBeEnabled();
 await page.getByRole('link',{name:'登录员工工作端',exact:true}).click();
 await expect(page).toHaveURL(/\/login$/);
 await expect(page.getByRole('heading',{name:'登录企业工作空间',exact:true})).toBeVisible();
});
