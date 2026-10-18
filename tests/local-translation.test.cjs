const test = require('node:test');
const assert = require('node:assert/strict');
const {LocalTranslator,splitText,isLoopback} = require('../public/local-translation.js');
test('no inference until explicitly prepared and requested; duplicate text uses RAM cache',async()=> {
 let calls=0,creates=0;
 const client=new LocalTranslator({Translator:{availability:async()=> 'available',create:async()=> { creates++;return {translate:async t=> {calls++;return '译文 '+t;}}; }}});
 assert.equal(calls,0); assert.equal(creates,0);
 await client.prepare(); const [a,b]=await Promise.all([client.translate('Example headline'),client.translate('Example headline')]);
 assert.equal(a,b); assert.equal(calls,1);
 await client.translate('Example headline');assert.equal(calls,1);
 client.clear();await client.translate('Example headline');assert.equal(calls,2);
});
test('large text is chunked without dropping words, enforces fulltext limit',()=> {
 const text=Array.from({length:1000},(_,i)=> 'word'+i).join(' ');
 const chunks=splitText(text);assert.ok(chunks.every(c=>c.length<=1800));assert.equal(chunks.join(' '),text);
 assert.throws(()=>splitText('x'.repeat(60001)));
});
test('unsupported browser never silently falls back to cloud',async()=> {
 const client=new LocalTranslator({fetch:()=> assert.fail('No network fallback')});
 await assert.rejects(()=>client.prepare(),/没有内置本地翻译/);
});
test('Ollama is blocked on public sites and lookalike hosts',async()=> {
 for (const hostname of ['suesone.github.io','127.0.0.1.attacker.example','localhost.example','192.168.1.10']) {
  assert.equal(isLoopback(hostname),false);
  const client=new LocalTranslator({location:{hostname},fetch:()=>assert.fail('Must not fetch')}); client.setEngine('ollama');
  await assert.rejects(()=>client.prepare(),/仅在本地阅读器/);
 }
});
test('local model only uses same-origin endpoints and server-controlled model',async()=> {
 const requests=[];
 const client=new LocalTranslator({location:{hostname:'127.0.0.1'},fetch:async(url,opts)=> {
  requests.push([url,opts]);return {ok:true,json:async()=>url.endsWith('status')?{ready:true,local_only:true,model:'qwen3:4b'}:{text:'中文译文'}};
 }});client.setEngine('ollama');await client.prepare();assert.equal(await client.translate('Example'),'中文译文');
 assert.deepEqual(requests.map(r=>r[0]),['/api/local/status','/api/local/translate']);
 assert.deepEqual(JSON.parse(requests[1][1].body),{text:'Example'});
 assert.equal(requests[1][1].headers['X-Headline-Local'],'1');
});
test('cancellation prevents later chunks and does not cache partial output',async()=> {
 const controller=new AbortController();let calls=0;
 const client=new LocalTranslator({Translator:{availability:async()=> 'available',create:async()=>({translate:async()=> {calls++;controller.abort();return '译';}})}});
 await client.prepare();await assert.rejects(()=>client.translate('x'.repeat(3000),{signal:controller.signal}),{name:'AbortError'});
 assert.equal(calls,1);assert.equal(client.cache.size,0);
});
test('Gemini needs an explicitly matching Google gateway; no direct browser key or remote call',async()=> {
 const requests=[];
 const client=new LocalTranslator({location:{hostname:'127.0.0.1'},fetch:async(url,options)=> {
  requests.push([url,options]);return {ok:true,json:async()=>url.endsWith('status')?{ready:true,provider:'gemini',cloud_provider:'Google',local_only:false,model:'gemini-2.5-flash-lite'}:{text:'中文'}};
 }});client.setEngine('gemini');await client.prepare();assert.equal(await client.translate('Selected headline'),'中文');
 assert.deepEqual(requests.map(r=>r[0]),['/api/local/status','/api/local/translate']);
 assert.deepEqual(JSON.parse(requests[1][1].body),{text:'Selected headline'});
 const mismatch=new LocalTranslator({location:{hostname:'127.0.0.1'},fetch:async()=>({ok:true,json:async()=>({ready:true,provider:'gemini',local_only:false,cloud_provider:'Google'})})});
 mismatch.setEngine('ollama');await assert.rejects(()=>mismatch.prepare(),/不匹配/);
 const publicClient=new LocalTranslator({location:{hostname:'suesone.github.io'},fetch:()=>assert.fail('No public gateway')});publicClient.setEngine('gemini');await assert.rejects(()=>publicClient.prepare(),/仅在本地阅读器/);
});
test('custom domain Gemini uses authenticated same-origin endpoints without exposing keys',async()=>{
 const requests=[];
 const client=new LocalTranslator({location:{hostname:'headline.infinitas.top',protocol:'https:'},fetch:async(url,options)=>{requests.push([url,options]);return {ok:true,json:async()=>url.endsWith('status')?{ready:true,provider:'gemini',cloud_provider:'Google',local_only:false,model:'gemini-2.5-flash-lite'}:{text:'译文'}};}});
 client.setEngine('gemini');await client.prepare();await client.translate('Headline');
 assert.deepEqual(requests.map(r=>r[0]),['/api/cloud/status','/api/cloud/translate']);
 assert.equal(requests[1][1].credentials,'same-origin');assert.equal(requests[1][1].headers['X-Headline-Cloud'],'1');
 assert.deepEqual(JSON.parse(requests[1][1].body),{text:'Headline'});
});
