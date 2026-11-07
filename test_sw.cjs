const vm = require('node:vm');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const handlers = {}, deleted = [], calls = [];
  const context = {URL, Response, Set, Promise,
    self: {location:{origin:'https://mp3z.test'}, addEventListener:(n,f)=>handlers[n]=f,
      skipWaiting:async()=>{}, clients:{claim:async()=>{}}},
    caches:{keys:async()=>['mp3z-shell-v1','mp3z-art-v1','other-app','mp3z-public-v2'],
      delete:async k=>deleted.push(k), open:async()=>({match:async()=>null,put:async()=>{}})},
    fetch:async(r,o)=>{calls.push([r,o]);return new Response('OK');}
  };
  vm.runInNewContext(fs.readFileSync('sw.js','utf8'),context);
  await new Promise((resolve,reject)=>handlers.activate({waitUntil:p=>p.then(resolve,reject)}));
  assert.deepEqual(deleted,['mp3z-shell-v1','mp3z-art-v1']);
  for(const [path,method] of [['/api/verify','POST'],['/api/art?apikey=secret','GET'],['/agent/mcp','POST']]){
    let intercepted=false;
    handlers.fetch({request:{url:'https://mp3z.test'+path,method},respondWith:()=>intercepted=true});
    assert.equal(intercepted,false);
  }
  let response;
  handlers.fetch({request:{url:'https://mp3z.test/',method:'GET'},respondWith:p=>response=p});
  await response;
  assert.equal(calls.at(-1)[1].cache,'no-store');
  console.log('PASS: scoped cache cleanup, auth/API bypass, network-only HTML');
})().catch(e=>{console.error(e);process.exit(1);});
