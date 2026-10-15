const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../animated_viewer.js'), 'utf8');
const modulePromise = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('viewport uses stable whole-pixel host dimensions at fractional column widths', async () => {
  const {viewportSize} = await modulePromise;
  const element = {getBoundingClientRect: () => ({width:671.5, height:900})};
  assert.deepEqual(viewportSize(element), {width:671, height:680});
  element.getBoundingClientRect = () => ({width:671.75});
  assert.deepEqual(viewportSize(element), {width:671, height:680});
  element.getBoundingClientRect = () => ({width:672});
  assert.deepEqual(viewportSize(element), {width:672, height:680});
});

test('observer ignores unchanged host sizes and resizes without enabling Plotly responsiveness', async () => {
  const {default: render} = await modulePromise;
  const names = ['window','ResizeObserver','requestAnimationFrame','cancelAnimationFrame'];
  const saved = names.map(name => globalThis[name]);
  const frames = new Map();
  let width = 671.5, nextFrame = 0, observer, config;
  const resized = [];
  const plot = {dataset:{},isConnected:true};
  const host = {querySelector:()=>plot,getBoundingClientRect:()=>({width})};
  globalThis.requestAnimationFrame = fn => {frames.set(++nextFrame,fn);return nextFrame;};
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  globalThis.ResizeObserver = class {
    constructor(fn) {observer=fn;}
    observe(element) {assert.equal(element,host);}
    disconnect() {}
  };
  globalThis.window = {Plotly:{
    react:async (_p,_traces,layout,options)=>{plot._fullLayout=layout;config=options;},
    relayout:async (_p,size)=>resized.push(size),
    restyle:async()=>{},purge:()=>{},
  }};
  const flush = async () => {
    for(const [id,fn] of [...frames]) {frames.delete(id);fn();}
    await new Promise(resolve=>setImmediate(resolve));
  };
  try {
    render({parentElement:host,data:{figure:{data:[{x:[1],y:[0],z:[0]}],layout:{scene:{}}},source_revision:'a',camera_revision:0,angles:[0,0,0],spins:[0,0,0],epoch:0,degrees_per_second:1,framing_scale:1}});
    await flush();
    assert.equal(config.responsive,false);
    assert.equal(plot._fullLayout.width,671);
    observer();await flush();
    width=671.75;observer();await flush();
    assert.deepEqual(resized,[]);
    width=672.1;observer();observer();await flush();
    assert.deepEqual(resized,[{width:672,height:680}]);
    observer();await flush();
    assert.equal(resized.length,1);
    assert.equal(frames.size,0,'idle viewer must not schedule animation frames');
  } finally {names.forEach((name,index)=>{if(saved[index]===undefined) delete globalThis[name];else globalThis[name]=saved[index];});}
});

test('rotation matches the Python XY then YZ then ZX order and preserves wire breaks', async () => {
  const {rotateCoordinates} = await modulePromise;
  const trace = {x:[1,null,0], y:[0,null,1], z:[0,null,0]};
  const result = rotateCoordinates(trace, [90,90,90]);
  const expected = {x:[1,null,0], y:[0,null,0], z:[0,null,1]};
  for (const axis of ['x','y','z']) for (let n=0; n<3; n++) {
    if (expected[axis][n] === null) assert.equal(result[axis][n], null);
    else assert(Math.abs(result[axis][n] - expected[axis][n]) < 1e-12);
  }
  assert.deepEqual(trace.x, [1,null,0]);
});

test('elapsed-time animation preserves speed without accumulating frame drift', async () => {
  const {anglesAt} = await modulePromise;
  const command = {angles:[175,-175,42], spins:[1,-1,0], degrees_per_second:10, epoch:100};
  assert.deepEqual(anglesAt(command,102), [-165,165,42]);
  assert.deepEqual(anglesAt(command,99), [175,-175,42]);
});

test('long off-center geometry stays within the fixed rotation envelope', async () => {
  const {rotateCoordinates} = await modulePromise;
  const trace = {x:[-2,2], y:[-3,3], z:[0,40]};
  const radius = Math.max(...trace.x.map((x,n)=>Math.hypot(x,trace.y[n],trace.z[n]))) * 1.05;
  for (const angles of [[90,0,0],[0,90,0],[0,0,90],[23,-137,78]]) {
    const rotated = rotateCoordinates(trace,angles);
    for (const axis of ['x','y','z']) assert(rotated[axis].every(value=>Math.abs(value)<radius));
  }
});
