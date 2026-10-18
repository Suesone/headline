import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {generateKeyPair,exportJWK,SignJWT} from '../cloudflare/node_modules/jose/dist/webapi/index.js';
import {createHandler,verifyAccess} from '../cloudflare/worker.mjs';
function environment(){
 const db=new DatabaseSync(':memory:');db.exec(readFileSync(new URL('../cloudflare/schema.sql',import.meta.url),'utf8'));
 return {PUBLIC_HOST:'infinitas.top',ACCESS_ISSUER:'https://headline-test.cloudflareaccess.com',ACCESS_AUD:'test-audience',ALLOWED_EMAIL:'owner@example.com',GEMINI_API_KEY:'fake-key-not-real',FREE_TIER_CONFIRMED:'true',DAILY_REQUEST_LIMIT:'2',RATE_LIMITER:{limit:async()=>({success:true})},BUDGET:{prepare(sql){return {bind(...args){return {async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};}};}}};
}
const request=(text='Headline',options={})=>new Request('https://infinitas.top/api/cloud/translate',{method:'POST',headers:{Origin:'https://infinitas.top','Content-Type':'application/json','X-Headline-Cloud':'1',...options.headers},body:JSON.stringify({text}),...options});
const authenticate=async()=>({sub:'owner'});
test('Access JWT cryptographically validates signature, issuer, audience, expiration and allowed email',async()=>{
 const env=environment(); const {privateKey,publicKey}=await generateKeyPair('RS256');const key=await exportJWK(publicKey);key.kid='headline-key';
 const original=globalThis.fetch;globalThis.fetch=async()=>Response.json({keys:[key]});
 const sign=async(overrides={})=>new SignJWT({email:env.ALLOWED_EMAIL,...overrides}).setProtectedHeader({alg:'RS256',kid:key.kid}).setIssuedAt().setIssuer(overrides.iss||env.ACCESS_ISSUER).setAudience(overrides.aud||env.ACCESS_AUD).setSubject('owner').setExpirationTime(overrides.exp||'5m').sign(privateKey);
 const verify=token=>verifyAccess(new Request('https://infinitas.top/api/cloud/status',{headers:{'Cf-Access-Jwt-Assertion':token}}),env);
 try {
  assert.equal((await verify(await sign())).email,env.ALLOWED_EMAIL);
  for(const overrides of [{email:'other@example.com'},{aud:'wrong'},{iss:'https://evil.example'},{exp:1}]) await assert.rejects(()=>sign(overrides).then(verify));
  const valid=await sign();await assert.rejects(()=>verify(valid.slice(0,-20)+'AAAAAAAAAAAAAAAAAAAA'));
 } finally {globalThis.fetch=original;}
});
test('missing configuration and unauthenticated requests never invoke Google',async()=>{
 const env=environment();let calls=0;const handler=createHandler({fetcher:async()=>{calls++;throw Error();}});
 assert.equal((await handler(request(),{...env,GEMINI_API_KEY:''})).status,503);
 assert.equal((await handler(request(),env)).status,401);assert.equal(calls,0);
});
test('public assets never forward credentials and unknown paths cannot proxy arbitrary URLs',async()=>{
 const calls=[];const handler=createHandler({fetcher:async(...args)=>{calls.push(args);return new Response('public');}});const env=environment();
 assert.equal((await handler(new Request('https://infinitas.top/',{headers:{Cookie:'secret','Cf-Access-Jwt-Assertion':'private'}}),env)).status,200);
 assert.equal(calls[0][0],'https://suesone.github.io/headline/');assert.deepEqual(calls[0][1].headers,{Accept:'*/*'});
 assert.equal((await handler(new Request('https://infinitas.top/private'),env)).status,404);assert.equal(calls.length,1);
});
test('origin checks, payload limit, rate limiter and atomic daily budget guard the Gemini secret',async()=>{
 const env=environment();let calls=0;
 const handler=createHandler({authenticate,fetcher:async(url,options)=>{calls++;assert.match(url,/^https:\/\/generativelanguage.googleapis.com\//);assert.equal(options.headers['x-goog-api-key'],env.GEMINI_API_KEY);assert.deepEqual(JSON.parse(options.body).contents[0].parts,[{text:'Headline'}]);return Response.json({candidates:[{finishReason:'STOP',content:{parts:[{text:'标题'}]}}]});}});
 assert.equal((await handler(request('Headline',{headers:{Origin:'https://evil.example'}}),env)).status,403);
 assert.equal((await handler(request('x'.repeat(2001)),env)).status,400);
 assert.equal((await handler(request(),{...env,RATE_LIMITER:{limit:async()=>({success:false})}})).status,429);
 const statuses=await Promise.all(Array.from({length:8},async()=> (await handler(request(),env)).status));
 assert.equal(statuses.filter(x=>x===200).length,2);assert.equal(calls,2);
});
test('Google 429 pauses all later calls and raw upstream errors never reach the client',async()=>{
 const env=environment();let calls=0;const handler=createHandler({authenticate,fetcher:async()=>{calls++;return new Response('fake-key-not-real private raw error',{status:429});}});
 const first=await handler(request(),env);assert.equal(first.status,429);assert.doesNotMatch(await first.text(),/fake-key-not-real|private raw/);
 assert.equal((await handler(request(),env)).status,429);assert.equal(calls,1);
});
