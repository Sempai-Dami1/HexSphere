const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('../babylon/node_modules/@playwright/test');
(async () => {
 const browser = await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 try {
  const page = await browser.newPage({viewport:{width:1600,height:1100}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://127.0.0.1:8514');
  await page.locator('.hexsphere-plot[data-ready=true] canvas').first().waitFor({timeout:60000});
  await page.getByText('PictureSphere',{exact:true}).click();
  const nameInput=page.locator('.st-key-picture_sphere_tile_name input');
  await nameInput.waitFor();
  await page.waitForFunction(()=>{const p=document.querySelector('.hexsphere-plot');return p?.dataset.ready==='true' && p.data?.[0].facecolor?.length>0;});
  await page.getByText('Show tile names',{exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.hexsphere-plot')?.data?.some(t=>t.name==='Tile names'));
  await nameInput.fill('North tile');await nameInput.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.hexsphere-plot')?.data?.some(t=>t.meta?.tile_names?.includes('North tile')));
  // AppTest exercises both selected-Unicode actions and the Unicode grid.
  // This browser check focuses on real glyph rendering and name-view restoration.
  const character=page.locator('.st-key-picture_sphere_paint_character input');
  await character.fill('ß');await character.press('Enter');
  await page.getByRole('button',{name:'Paint Selected Tile',exact:true}).click();
  await page.getByText('Show tile names',{exact:true}).click();
  await page.waitForFunction(()=>{
   const p=document.querySelector('.hexsphere-plot');
   return document.querySelector('.st-key-picture_sphere_paint_character input')?.value==='ß' && p?.dataset.ready==='true' && p.data?.length===3 && !p.data.some(t=>t.name==='Tile names');
  });
  await page.locator('.hexsphere-plot').evaluate(p=>{
   const glyph=p.data.find(t=>t.name==='Tile Labels');
   const center=['x','y','z'].map(axis=>glyph[axis].reduce((a,b)=>a+b,0)/glyph[axis].length);
   const distance=Math.hypot(...center);
   return Plotly.relayout(p,{'scene.camera.eye':{x:center[0]/distance*1.8,y:center[1]/distance*1.8,z:center[2]/distance*1.8}});
  });
  const read=()=>page.locator('.hexsphere-plot').evaluate(p=>({colors:p.data[0].facecolor,traces:p.data.map(t=>({name:t.name,x:t.x,y:t.y,z:t.z,type:t.type,meta:t.meta})),camera:p._fullLayout.scene.camera}));
  const original=await read();
  await page.locator('.hexsphere-plot').screenshot({path:'diagnostics/picture_sphere_unicode.png'});
  await page.getByText('Show tile names',{exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.hexsphere-plot')?.data?.some(t=>t.name==='Tile names'));
  const named=await read();
  assert.deepEqual(named.colors,original.colors);
  assert(named.traces.at(-1).meta.tile_names.includes('North tile'));
  assert.equal(named.traces.at(-1).type,'mesh3d');
  assert.deepEqual(named.camera,original.camera);
  await page.locator('.hexsphere-plot').screenshot({path:'diagnostics/picture_sphere_names.png'});
  await nameInput.fill('North tile revised');await nameInput.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.hexsphere-plot')?.data?.some(t=>t.meta?.tile_names?.includes('North tile revised')));
  await page.getByText('Show tile names',{exact:true}).click();
  await page.waitForFunction(()=>{const p=document.querySelector('.hexsphere-plot');return p?.dataset.ready==='true' && p.data?.length===3 && !p.data.some(t=>t.name==='Tile names');});
  const restored=await read();
  assert.deepEqual(restored.colors,original.colors);
  assert(JSON.stringify(restored.traces)===JSON.stringify(original.traces),'Unicode trace geometry must be restored exactly');
  assert.deepEqual(restored.camera,original.camera);
  assert.equal(await page.locator('.st-key-picture_sphere_paint_character input').inputValue(),'ß');
  assert.deepEqual(errors,[]);
  const result={exact_character:'ß',tile_count:named.traces.at(-1).meta.tile_names.length,editable_name:true,tile_surface_name_mesh:true,background_restored:true,unicode_mesh_restored:true,camera_preserved:true,errors};
  fs.writeFileSync('diagnostics/picture_sphere_authoring_results.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
