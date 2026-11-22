// QR/link pairing: '#kod=' fragment connects without discovery and is removed from the address.
// Usage: node tests/test_receiver_link.js <receiver-script.js>  (script extracted from tv.PAGE, port 9876)
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
function run(hash) {
  const elements = new Map(), sockets = [], replaced = [];
  let fetched = 0;
  class Element {
    constructor(){this.value='';this.children=[];this.raw='';this.style={};this.clientWidth=1920;this.clientHeight=1080;this.offsetHeight=60;}
    get textContent(){return this.raw;} set textContent(value){this.raw=value;}
    appendChild(child){return child;} setAttribute(){}
  }
  const context = {
    document:{querySelector(selector){if(!elements.has(selector))elements.set(selector,new Element());return elements.get(selector);},
      createElement(){return new Element();},createTextNode(){return new Element();}},
    location:{hostname:'192.168.1.20',hash,pathname:'/'},
    history:{replaceState(state,title,url){replaced.push(url);}},
    window:{addEventListener(){}},
    fetch(){fetched++;return new Promise(()=>{});},
    WebSocket:class{constructor(url){this.url=url;sockets.push(this);}close(){}},
    setTimeout(){return 1;},clearTimeout(){},
  };
  vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
  return {sockets,replaced,fetched};
}
let result = run('#kod=0a1b2c3d');
assert.equal(result.sockets.length,1);
assert.equal(result.sockets[0].url,'ws://192.168.1.20:9876/?token=0a1b2c3d');
assert.deepEqual(result.replaced,['/']);
assert.equal(result.fetched,0);
for (const hash of ['', '#kod=XYZ', '#kod=0a1b2c3d&x=1', '#other']) {
  result = run(hash);
  assert.equal(result.sockets.length,0,hash);
  assert.equal(result.fetched,1,hash);
  assert.deepEqual(result.replaced,[],hash);
}
console.log('Receiver link pairing tests passed');
