const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('../babylon/node_modules/@playwright/test');
(async () => {
 const browser = await chromium.launch({headless:true, args:process.argv.includes('--hardware')?['--enable-webgl','--ignore-gpu-blocklist']:['--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 try {
 const page = await browser.newPage({viewport:{width:1600,height:1100}});
 const errors = [];
 let messages=0; const sent=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('websocket',ws=>{ws.on('framereceived',()=>messages++);ws.on('framesent',frame=>sent.push(Buffer.from(frame.payload)));});
 await page.goto('http://127.0.0.1:8514');
 await page.locator('.hexsphere-plot canvas').first().waitFor({timeout:30000});
 await page.getByText('Attach visualization controls', {exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.st-key-xy_inc button').length===1);
 await page.locator('.st-key-xy_inc button').waitFor();
 await page.locator('[data-testid=stColumn] .hexsphere-plot[data-ready=true] canvas').first().waitFor();
 await page.evaluate(()=>{
   window.animationStats={restyle:[], react:0, keys:[]};
   const restyle=Plotly.restyle;
   Plotly.restyle=async (...args)=>{const start=performance.now();window.animationStats.keys.push(Object.keys(args[1]));const result=await restyle(...args);window.animationStats.restyle.push(performance.now()-start);return result;};
   const react=Plotly.react;
   Plotly.react=async (...args)=>{window.animationStats.react++;return react(...args)};
 });
 const plotState=()=>page.locator('.hexsphere-plot').evaluate(el=>({x:el.data[0].x.slice(0,8), y:el.data[0].y.slice(0,8), z:el.data[0].z.slice(0,8), camera:el._fullLayout.scene.camera, alpha:el.data[0].opacity, flat:el.data[0].flatshading, color:el.data[0].color, ranges:['xaxis','yaxis','zaxis'].map(a=>el.layout.scene[a].range)}));
 await page.locator('.hexsphere-plot').evaluate(el=>Plotly.relayout(el,{'scene.camera.eye':{x:2.1,y:0.7,z:1.1}}));
 const before=await plotState();
 await page.locator('.st-key-xy_inc button').click();
 await page.waitForFunction(()=>window.animationStats.restyle.length>=5);
 const messageStart=messages;
 const sample=await page.evaluate(async()=>{const start=animationStats.restyle.length;await new Promise(r=>setTimeout(r,3000));return {...animationStats,restyle:animationStats.restyle.slice(start)}});
 const after=await plotState();
 assert.notDeepEqual(after.x,before.x);
 assert.deepEqual(after.camera,before.camera);
 assert.deepEqual(after.ranges,before.ranges);
 assert.equal(after.color,before.color);
 assert.equal(after.alpha,before.alpha);
 assert(sample.keys.every(keys=>keys.join(',')==='x,y,z'));
 assert.equal(sample.react,0,'spin should not reconcile appearance');
 assert.equal(messages,messageStart,'animation should not require server messages');
 await page.locator('.st-key-xy_stop button').click();
 try { await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.spins==='0,0,0' && el.dataset.ready==='true';}); }
 catch(error) {
  console.log(await page.evaluate(()=>({plots:[...document.querySelectorAll('.hexsphere-plot')].map(p=>({spins:p.dataset.spins,ready:p.dataset.ready})),errors:[...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText)})));
  fs.writeFileSync('diagnostics/stop_message.bin',sent[sent.length-1]);
  await page.screenshot({path:'diagnostics/stop_timeout.png',fullPage:true});
  throw error;
 }
 const stopped=await plotState();
 await page.evaluate(()=>new Promise(r=>setTimeout(r,800)));
 assert.deepEqual((await plotState()).x,stopped.x);
 for (const axis of ['yz','zx']) {
   const previous=await plotState();
   const count=await page.evaluate(()=>animationStats.restyle.length);
   await page.locator(`.st-key-${axis}_dec button`).click();
   await page.waitForFunction(n=>window.animationStats.restyle.length>=n+5,count);
   const next=await plotState();assert.notDeepEqual([next.x,next.y,next.z],[previous.x,previous.y,previous.z]);
   await page.locator(`.st-key-${axis}_stop button`).click();
   await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.spins==='0,0,0' && el.dataset.ready==='true';});
 }

 const preScale=await plotState();
 await page.getByText('Auto-scale',{exact:true}).click();
 const scaleSlider=page.locator('.st-key-vis_scale').getByRole('slider');
 await scaleSlider.focus();await scaleSlider.press('ArrowRight');
 await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');const slider=document.querySelector('.st-key-vis_scale input[type=range]');return el?.dataset.ready==='true' && Number(slider?.getAttribute('aria-valuenow') ?? slider?.value)>1;});
 await page.waitForFunction(original=>{const el=document.querySelector('.hexsphere-plot');return Math.hypot(el.data[0].x[0],el.data[0].y[0],el.data[0].z[0])>original*1.04;},Math.hypot(preScale.x[0],preScale.y[0],preScale.z[0]));
 const manual=await plotState();
 assert(Math.abs(Math.hypot(manual.x[0],manual.y[0],manual.z[0])/Math.hypot(preScale.x[0],preScale.y[0],preScale.z[0])-1.05)<1e-9);
 for(let a=0;a<3;a++)for(let n=0;n<2;n++)assert(Math.abs(manual.ranges[a][n]-preScale.ranges[a][n])<1e-9);
 assert.deepEqual(manual.camera,preScale.camera);
 await page.locator('.st-key-vis_default_btn button').click();
 await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.ready==='true' && Math.abs(el._fullLayout.scene.camera.eye.x-1.5)<1e-9;});
 const ms=sample.restyle.sort((a,b)=>a-b);
 const result={default_sphere:{coordinate_updates:ms.length, window_seconds:3, median_update_ms:ms[Math.floor(ms.length/2)],p95_update_ms:ms[Math.floor(ms.length*.95)],server_messages:0,appearance_rebuilds:sample.react}, errors};

 result.graphics_backend=await page.evaluate(()=>{const gl=document.createElement('canvas').getContext('webgl');const ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'unavailable'});
 await page.getByText('PictureSphere',{exact:true}).click();
 await page.getByRole('button',{name:'Generate Test Pattern',exact:true}).click();
 await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.ready==='true' && el.data?.length===3 && el.data[2].x.length>50000;},{timeout:30000});
 const denseBefore=await page.locator('.hexsphere-plot').evaluate(el=>({colors:el.data[0].facecolor, labelColors:el.data[2].facecolor, alpha:el.data[0].opacity, labelVertices:el.data[2].x.length}));
 await page.locator('.st-key-xy_inc button').click();
 await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.spins==='1,0,0' && el.dataset.ready==='true';});
 const denseMessageStart=messages;
 const dense=await page.evaluate(async()=>{const count=animationStats.restyle.length;const reacts=animationStats.react;await new Promise(r=>setTimeout(r,3000));return {times:animationStats.restyle.slice(count),reacts:animationStats.react-reacts}});
 assert.equal(messages,denseMessageStart);
 assert.equal(dense.reacts,0);
 assert(dense.times.length>0);
 const denseAfter=await page.locator('.hexsphere-plot').evaluate(el=>({colors:el.data[0].facecolor,labelColors:el.data[2].facecolor,alpha:el.data[0].opacity,labelVertices:el.data[2].x.length}));
 assert.deepEqual(denseAfter,denseBefore);
 const times=dense.times.sort((a,b)=>a-b);
 result.picture_sphere_all_labels={label_vertices:denseBefore.labelVertices,coordinate_updates:times.length,window_seconds:3,median_update_ms:times[Math.floor(times.length/2)],p95_update_ms:times[Math.floor(times.length*.95)],appearance_rebuilds:dense.reacts,server_messages:0};
 console.log('dense measurement',JSON.stringify(result));
 fs.writeFileSync('diagnostics/animation_browser_results.json',JSON.stringify({...result,status:'dense stop check pending'},null,2));
 const sentBefore=sent.length;await page.locator('.st-key-xy_stop button').click();console.log('dense stop sent',sent.length-sentBefore);
 try { await page.waitForFunction(()=>{const el=document.querySelector('.hexsphere-plot');return el?.dataset.spins==='0,0,0' && el.dataset.ready==='true';}); } catch(error) {fs.writeFileSync('diagnostics/stop_message.bin',sent[sent.length-1]);console.log('stop diagnostics',await page.locator('.hexsphere-plot').evaluate(el=>({spins:el.dataset.spins,ready:el.dataset.ready,text:el.textContent.slice(0,100)})),errors);throw error;}
 await page.screenshot({path:'diagnostics/animation_viewer.png'});
 fs.writeFileSync('diagnostics/animation_browser_results.json',JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
 assert.deepEqual(errors,[]);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
