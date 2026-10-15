const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('../babylon/node_modules/@playwright/test');
(async () => {
 const browser = await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 try {
  const page = await browser.newPage({viewport:{width:1600,height:1100}});
  await page.goto('http://127.0.0.1:8514');
  await page.getByText('Attach visualization controls',{exact:true}).click();
  await page.locator('.st-key-xy_inc button').waitFor();
  await page.locator('[data-testid=stColumn] .hexsphere-plot[data-ready=true] canvas').first().waitFor();
  // This diagnostic checks native controls and CSS, not animation throughput.
  // Avoid spending software-renderer time on coordinate draws during assertions.
  await page.evaluate(()=>{Plotly.restyle=async()=>{};});
  const button=(axis,direction)=>page.locator(`.st-key-${axis}_${direction} button`);
  const color=locator=>locator.evaluate(el=>getComputedStyle(el).backgroundColor);
  const normal=await color(button('xy','inc'));
  const green='rgb(21, 128, 61)';
  const expectColor=async (axis,direction,expected)=>{
   try { await page.waitForFunction(({axis,direction,expected})=>{
    const el=document.querySelector(`.st-key-${axis}_${direction} button`);
    return el && getComputedStyle(el).backgroundColor===expected;
   },{axis,direction,expected}); } catch(error) {
    console.log(await page.evaluate(()=>({buttons:[...document.querySelectorAll('.st-key-xy_inc button,.st-key-xy_dec button')].map(el=>({kind:el.getAttribute('kind'),html:el.outerHTML,color:getComputedStyle(el).backgroundColor})),style:[...document.querySelectorAll('style')].filter(el=>el.textContent.includes('st-key-xy_dec')).map(el=>el.textContent)})));
    throw error;
   }
  };
  const results=[];
  for(const axis of ['xy','yz','zx']) {
   await button(axis,'inc').click();
   await expectColor(axis,'inc',green);
   await expectColor(axis,'dec',normal);
   await button(axis,'dec').click();
   await expectColor(axis,'dec',green);
   await expectColor(axis,'inc',normal);
   await button(axis,'stop').click();
   await expectColor(axis,'dec',normal);
   await expectColor(axis,'inc',normal);
   assert.equal(await button(axis,'stop').getAttribute('kind'),'secondary');
   results.push({axis,forward_green:true,reverse_green:true,previous_direction_restored:true,stop_restored:true});
  }
  // Concurrent axes should each retain their own direction indicator.
  await button('xy','inc').click();await expectColor('xy','inc',green);
  await button('yz','dec').click();await expectColor('yz','dec',green);
  await expectColor('xy','inc',green);
  await page.screenshot({path:'diagnostics/animation_buttons_active.png',fullPage:true});
  await page.locator('.st-key-vis_default_btn button').click();
  for(const axis of ['xy','yz','zx']) for(const direction of ['inc','dec']) await expectColor(axis,direction,normal);
  await page.screenshot({path:'diagnostics/animation_buttons.png',fullPage:true});
  fs.writeFileSync('diagnostics/animation_buttons_results.json',JSON.stringify({normal,green,results,independent_axes:true,default_restored:true},null,2));
  console.log(JSON.stringify({results,independent_axes:true,default_restored:true}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
