const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('../babylon/node_modules/@playwright/test');
(async () => {
 const browser = await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 try {
  const page = await browser.newPage({viewport:{width:1600,height:1100}});
  await page.goto('http://127.0.0.1:8514');
  await page.locator('.hexsphere-plot[data-ready=true] canvas').first().waitFor({timeout:60000});
  await page.getByText('Attach visualization controls',{exact:true}).click();
  await page.locator('[data-testid=stColumn] .hexsphere-plot[data-ready=true] canvas').first().waitFor();
  await page.evaluate(() => {
   window.stability={resizes:0,samples:[]};
   const resize=Plotly.Plots.resize;
   Plotly.Plots.resize=(...args)=>{stability.resizes++;return resize(...args);};
   window.sampleTimer=setInterval(()=>{
    const p=document.querySelector('.hexsphere-plot'), r=p.getBoundingClientRect();
    stability.samples.push({width:r.width,height:r.height,left:r.left,fullWidth:p._fullLayout.width,camera:JSON.stringify(p._fullLayout.scene._scene.getCamera()),x:p.data[0].x[0]});
   },50);
  });
  const modes=await page.locator('.modebar-btn').evaluateAll(es=>es.map(e=>e.getAttribute('data-title')));
  for(const mode of ['Pan','Pan','Zoom','Orbital rotation','Turntable rotation','Pan']) {
   const button=page.locator(`.modebar-btn[data-title="${mode}"]`);
   if(await button.count()) await button.click();
   await page.waitForTimeout(700);
  }
  const idle=await page.evaluate(()=>{clearInterval(sampleTimer);return stability;});
  if(process.argv.includes('--sizes')) {
   const samples=[];
   for(const width of [1366,1280,1440,1000,1001,1600]) {
    await page.setViewportSize({width,height:1100});
    for(let i=0;i<12;i++){await page.waitForTimeout(100);samples.push(await page.locator('.hexsphere-plot').evaluate(p=>{const r=p.getBoundingClientRect();return {left:r.left,width:r.width,fullWidth:p._fullLayout.width,canvas:p.querySelector('canvas').width,camera:p._fullLayout.scene._scene.getCamera()};}));}
   }
   const result={idle,samples,resizes:await page.evaluate(()=>stability.resizes)};
   assert(samples.every(s=>s.fullWidth===Math.floor(s.width)),'canvas layout must track whole-pixel host width');
   await page.getByText('Attach visualization controls',{exact:true}).click();
   await page.waitForFunction(()=>{const p=document.querySelector('.hexsphere-plot');return p && !p.closest('[data-testid=stColumn]') && p.dataset.ready==='true';});
   await page.locator('.hexsphere-plot[data-ready=true] canvas').first().waitFor();
   result.detached=await page.locator('.hexsphere-plot').evaluate(p=>({width:p.getBoundingClientRect().width,fullWidth:p._fullLayout.width,spins:p.dataset.spins}));
   assert.equal(result.detached.spins,'0,0,0');
   assert.equal(result.detached.fullWidth,Math.floor(result.detached.width));
   fs.writeFileSync('diagnostics/viewer_sizing_results.json',JSON.stringify(result,null,2));
   console.log(JSON.stringify({resizes:result.resizes,sizes:[...new Set(samples.map(s=>`${s.left},${s.width},${s.fullWidth},${s.canvas}`))]}));
   return;
  }
  await page.locator('.st-key-xy_inc button').click();
  await page.waitForFunction(()=>{const p=document.querySelector('.hexsphere-plot');return p?.dataset.spins==='1,0,0' && p.dataset.ready==='true';});
  const active=[];
  for(let i=0;i<20;i++){active.push(await page.locator('.hexsphere-plot').evaluate(p=>({camera:p._fullLayout.scene._scene.getCamera(),width:p.getBoundingClientRect().width,x:p.data[0].x[0]})));await page.waitForTimeout(100);}
  await page.locator('.st-key-xy_stop button').click();
  await page.waitForFunction(()=>document.querySelector('.hexsphere-plot')?.dataset.spins==='0,0,0');
  await page.locator('.modebar-btn[data-title="Orbital rotation"]').click();
  const canvas=page.locator('.hexsphere-plot canvas').first();
  const box=await canvas.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
  await page.mouse.down();await page.mouse.move(box.x+box.width/2+80,box.y+box.height/2+20,{steps:8});await page.mouse.up();
  const orbit=[];
  for(let i=0;i<40;i++){orbit.push(await page.locator('.hexsphere-plot').evaluate(p=>p._fullLayout.scene._scene.getCamera()));await page.waitForTimeout(100);}
  const sizes=[];
  for(const width of [1000,1001,1200,1600]){await page.setViewportSize({width,height:1100});await page.waitForTimeout(600);sizes.push(await page.locator('.hexsphere-plot').evaluate(p=>({width:p.getBoundingClientRect().width,fullWidth:p._fullLayout.width,camera:p._fullLayout.scene._scene.getCamera()})));}
  const result={modes,idle,orbit,active,sizes};
  fs.writeFileSync('diagnostics/viewer_stability_results.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify({modes,resizes:idle.resizes,dimensions:[...new Set(idle.samples.map(s=>`${s.left},${s.width},${s.fullWidth}`))],cameras:new Set(idle.samples.map(s=>s.camera)).size,coordinates:new Set(idle.samples.map(s=>s.x)).size,orbitCameras:new Set(orbit.map(JSON.stringify)).size,activeCameras:new Set(active.map(s=>JSON.stringify(s.camera))).size,sizes},null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
