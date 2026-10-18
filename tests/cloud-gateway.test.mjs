import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {generateKeyPair,exportJWK,SignJWT} from '../cloudflare/node_modules/jose/dist/webapi/index.js';
import {createHandler} from '../cloudflare/worker.mjs';
import {verifyGoogleCredential,issueSession,verifySession,sessionCookie,COOKIE} from '../cloudflare/auth.mjs';
function environment(){
 const db=new DatabaseSync(':memory:');db.exec(readFileSync(new URL('../cloudflare/schema.sql',import.meta.url),'utf8'));
 return {PUBLIC_HOST:'headline.infinitas.top',GOOGLE_CLIENT_ID:'123-test.apps.googleusercontent.com',SESSION_SECRET:'test-random-secret-with-more-than-thirty-two-characters',LOGIN_RATE_LIMITER:{limit:async()=>({success:true})},ALLOWED_EMAIL:'owner@example.com',GEMINI_API_KEY:'fake-key-not-real',FREE_TIER_CONFIRMED:'true',DAILY_REQUEST_LIMIT:'2',RATE_LIMITER:{limit:async()=>({success:true})},BUDGET:{prepare(sql){return {bind(...args){return {async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};}};}}};
}
const request=(text='Headline',options={})=>new Request('https://headline.infinitas.top/api/cloud/translate',{method:'POST',headers:{Origin:'https://headline.infinitas.top','Content-Type':'application/json','X-Headline-Cloud':'1',...options.headers},body:JSON.stringify({text}),...options});
const authenticate=async()=>({sub:'owner'});
test('Google ID token validates signature, issuer, audience, expiration and verified owner email',async()=>{
 const env=environment(); const {privateKey,publicKey}=await generateKeyPair('RS256');const key=await exportJWK(publicKey);key.kid='headline-key';
 const original=globalThis.fetch;globalThis.fetch=async()=>Response.json({keys:[key]});
 const sign=async(overrides={})=>new SignJWT({email:env.ALLOWED_EMAIL,email_verified:true,...overrides}).setProtectedHeader({alg:'RS256',kid:key.kid}).setIssuedAt().setIssuer(overrides.iss||'https://accounts.google.com').setAudience(overrides.aud||env.GOOGLE_CLIENT_ID).setSubject('owner').setExpirationTime(overrides.exp||'5m').sign(privateKey);
 const verify=token=>verifyGoogleCredential(token,env);
 try {
  assert.equal((await verify(await sign())).email,env.ALLOWED_EMAIL);
  for(const overrides of [{email:'other@example.com'},{email_verified:false},{aud:'wrong'},{azp:'wrong'},{iss:'https://evil.example'},{exp:1}]) await assert.rejects(()=>sign(overrides).then(verify));
  const valid=await sign();await assert.rejects(()=>verify(valid.slice(0,-20)+'AAAAAAAAAAAAAAAAAAAA'));
 } finally {globalThis.fetch=original;}
});
test('signed session is HttpOnly, Secure, API-only and rejects forged or expired tokens',async()=>{
 const env=environment();const token=await issueSession({sub:'owner',email:env.ALLOWED_EMAIL},env);const cookie=sessionCookie(token);
 assert.match(cookie,/Path=\/api\/cloud; HttpOnly; Secure; SameSite=Strict; Max-Age=3600/);
 const verify=value=>verifySession(new Request('https://headline.infinitas.top/api/cloud/status',{headers:{Cookie:COOKIE+'='+value}}),env);
 assert.equal((await verify(token)).sub,'owner');await assert.rejects(()=>verify(token+'x'));
 const expired=await new SignJWT({email:env.ALLOWED_EMAIL}).setProtectedHeader({alg:'HS256'}).setSubject('owner').setIssuer('https://'+env.PUBLIC_HOST).setAudience('headline-translation').setIssuedAt().setExpirationTime(1).sign(new TextEncoder().encode(env.SESSION_SECRET));
 await assert.rejects(()=>verify(expired));await assert.rejects(()=>verifySession(new Request('https://headline.infinitas.top/api/cloud/status'),env));
});
test('Google login creates a private cookie, logout clears it, and public config never exposes secrets',async()=>{
 const env=environment();let verified=0;const handler=createHandler({verifyGoogle:async()=>{verified++;return {sub:'owner',email:env.ALLOWED_EMAIL};},fetcher:()=>assert.fail('No Gemini during login')});
 const post=(path,body,origin='https://headline.infinitas.top')=>new Request('https://headline.infinitas.top/api/cloud/'+path,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','X-Headline-Cloud':'1'},body:JSON.stringify(body)});
 assert.equal((await handler(post('session',{credential:'token'},'https://evil.example'),env)).status,403);assert.equal(verified,0);
 const login=await handler(post('session',{credential:'token'}),env);assert.equal(login.status,200);assert.match(login.headers.get('Set-Cookie'),/HttpOnly/);assert.equal(verified,1);
 const logout=await handler(post('logout',{}),env);assert.match(logout.headers.get('Set-Cookie'),/Max-Age=0/);
 const config=await handler(new Request('https://headline.infinitas.top/api/cloud/config'),env);assert.deepEqual(await config.json(),{client_id:env.GOOGLE_CLIENT_ID});
});
test('missing configuration and unauthenticated requests never invoke Google',async()=>{
 const env=environment();let calls=0;const handler=createHandler({fetcher:async()=>{calls++;throw Error();}});
 assert.equal((await handler(request(),{...env,SESSION_SECRET:''})).status,503);
 assert.equal((await handler(request(),env)).status,401);assert.equal(calls,0);
});
test('redirect login requires matching CSRF cookie, allowed origin and valid Google identity',async()=>{
 const env=environment();let verified=0;
 const handler=createHandler({verifyGoogle:async()=>{verified++;return {sub:'owner',email:env.ALLOWED_EMAIL};},fetcher:()=>assert.fail('No Gemini during login')});
 const callback=(body='credential=token&g_csrf_token=random',cookie='g_csrf_token=random',origin='https://accounts.google.com')=>new Request('https://headline.infinitas.top/api/cloud/google/callback',{method:'POST',headers:{Origin:origin,Cookie:cookie,'Content-Type':'application/x-www-form-urlencoded'},body});
 for(const req of [callback(undefined,''),callback(undefined,'g_csrf_token=wrong'),callback(undefined,undefined,'https://evil.example'),callback('credential=token&g_csrf_token=random&g_csrf_token=random')]) assert.equal((await handler(req,env)).status,403);
 assert.equal(verified,0);
 const response=await handler(callback(),env);assert.equal(response.status,303);assert.equal(response.headers.get('Location'),'https://headline.infinitas.top/#local-tools');assert.match(response.headers.get('Set-Cookie'),/HttpOnly; Secure; SameSite=Strict/);assert.equal(verified,1);
 const invalid=createHandler({verifyGoogle:async()=>{throw Error('invalid identity');}});assert.equal((await invalid(callback(),env)).status,401);
});
test('Worker never proxies public pages or unknown routes',async()=>{
 const handler=createHandler({fetcher:()=>assert.fail('No public proxy')});const env=environment();
 for(const path of ['/','/private','/api/other']) assert.equal((await handler(new Request('https://headline.infinitas.top'+path),env)).status,404);
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
