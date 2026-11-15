// Execute the real shipped receiver script with a minimal browser boundary.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const elements = new Map();
const sockets = [];
const timers = new Map();
class Element {
 constructor(){this.value='pairing-code';this.children=[];this.raw='';this.style={};this.clientWidth=1920;this.clientHeight=1080;this.offsetHeight=60;this.attributes={};}
 get textContent(){return this.raw+this.children.map(child=>child.textContent).join('');}
 set textContent(value){this.raw=value;this.children=[];}
 appendChild(child){this.children.push(child);return child;}
 setAttribute(name,value){this.attributes[name]=value;}
}
let nextTimer = 1;
let resizeHandler;
let finishDiscovery;
const context = {
  document: {querySelector(selector) {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  },createElement(){return new Element();},createTextNode(text){const node=new Element();node.textContent=text;return node;}},
  location: {hostname: '127.0.0.1'},
  window: {addEventListener(name,fn){if(name==='resize')resizeHandler=fn;}},
  fetch(path){assert.equal(path,'/duplay.json');return new Promise(resolve=>finishDiscovery=resolve);},
  WebSocket: class {
    constructor(url) { this.url = url; sockets.push(this); }
    close() { if (this.onclose) this.onclose(); }
  },
  setTimeout(fn) { const id = nextTimer++; timers.set(id, fn); return id; },
  clearTimeout(id) { timers.delete(id); }
};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const get = selector => context.document.querySelector(selector);
get('#connect').onclick();
assert.match(sockets[0].url, /:9876\//);
sockets[0].onopen();
sockets[0].onmessage({data: JSON.stringify({type: 'subtitle', text: 'Merhaba', ttl_ms: 6000})});
assert.equal(get('#caption').textContent, 'Merhaba');
sockets[0].onmessage({data: JSON.stringify({type: 'hud', text: 'Kapıyı aç'})});
assert.equal(get('#hud').textContent, 'Kapıyı aç');
sockets[0].onclose();
assert.equal(get('#caption').textContent, '');
assert.equal(get('#hud').textContent, '');
assert.equal(timers.size, 1);
const retry = [...timers.values()][0]; timers.clear(); retry();
assert.equal(sockets.length, 2);
sockets[0].onmessage({data: JSON.stringify({type:'subtitle',text:'stale automatic retry',ttl_ms:5000})});
assert.equal(get('#caption').textContent, '');
get('#connect').onclick();
const current = sockets.at(-1);
sockets[1].onmessage({data: JSON.stringify({type: 'subtitle', text: 'stale'})});
assert.equal(get('#caption').textContent, '');
current.onmessage({data: JSON.stringify({type:'subtitle', text:'current', stack: {
  previous:{speaker:'John',text:'Merhaba'}, current:{speaker:'Mary',text:'Gel'}}, ttl_ms:5000})});
assert.equal(get('#caption').textContent, 'John: Merhaba\nMary: Gel');
// A timer already queued by the browser cannot clear a later caption.
const expireOldCaption=[...timers.values()][0];
current.onmessage({data:JSON.stringify({type:'subtitle',text:'Yeni satır',ttl_ms:5000})});
expireOldCaption();
assert.equal(get('#caption').textContent,'Yeni satır');
for (const data of ['null','{bad','[]']) current.onmessage({data});
assert.equal(get('#caption').textContent,'Yeni satır');
// Source-relative HUD placement stays inside the viewport, including its
// bottom/right edge, and reflows without another server message on resize.
current.onmessage({data:JSON.stringify({type:'hud',text:'<img src=x> Kapıyı aç',box:{x:.9,y:.9,w:.1,h:.1}})});
assert.equal(get('#hud').textContent,'<img src=x> Kapıyı aç');
assert.equal(get('#hud').style.display,'block');
function insideHud(){
 const hud=get('#hud'),surface=get('#surface');
 assert.ok(parseFloat(hud.style.left)>=0);
 assert.ok(parseFloat(hud.style.left)+parseFloat(hud.style.width)<=surface.clientWidth);
 assert.ok(parseFloat(hud.style.top)>=0);
 assert.ok(parseFloat(hud.style.top)+hud.offsetHeight<=surface.clientHeight);
}
insideHud();
get('#surface').clientWidth=800;get('#surface').clientHeight=450;resizeHandler();insideHud();
current.onmessage({data:JSON.stringify({type:'hud',text:'invalid geometry',box:{x:'0.1',y:.1,w:.2,h:.1}})});
assert.equal(get('#hud').textContent,'');
assert.equal(get('#hud').style.display,'none');
current.onmessage({data:JSON.stringify({type:'hud',text:'Eski alıcı biçimi',box:null})});
assert.equal(get('#hud').textContent,'Eski alıcı biçimi');
current.onmessage({data:JSON.stringify({type:'hud',text:'Bas {{RB}} ve {{SQR}} <img src=x>',box:null})});
assert.equal(get('#hud').textContent,'Bas RB ve □ <img src=x>');
const marks=get('#hud').children.filter(child=>child.className&&child.className.startsWith('badge '));
assert.equal(marks.length,2);assert.equal(marks[0].title,'RB');assert.equal(marks[1].title,'SQR');
current.onmessage({data:JSON.stringify({type:'clear',text:''})});
assert.equal(get('#caption').textContent,'');
assert.equal(get('#hud').textContent,'Bas RB ve □ <img src=x>');
// Five failed retries, then no additional automatic attempts. A queued retry
// from a manually abandoned generation must not create a new connection.
get('#edit').onclick();
get('#connect').onclick();
for(let index=0;index<5;index++){
 sockets.at(-1).onclose();
 assert.equal(timers.size,1);
 const retryCallback=[...timers.values()][0];timers.clear();retryCallback();
}
sockets.at(-1).onclose();
assert.equal(timers.size,0);
get('#connect').onclick();sockets.at(-1).onclose();
const abandonedRetry=[...timers.values()][0];
get('#edit').onclick();const count=sockets.length;abandonedRetry();
assert.equal(sockets.length,count);
get('#token').value='\ud800';
get('#connect').onclick();
assert.equal(sockets.length,count);
assert.match(get('#status').textContent,/geçersiz/);
get('#token').value='pairing-code';
(async()=>{
 const selectedCode=get('#token').value;
 finishDiscovery({ok:true,json:()=>Promise.resolve({name:'Duplay',token:'late-discovered-code'})});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(get('#token').value,selectedCode);
 assert.equal(sockets.length,count);
 console.log('Receiver discovery/manual priority, geometry, resize, malformed data, stale socket/TTL, dialogue and bounded reconnect tests passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
