import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {runCheck,handleStatus,isFresh,nextCheck,reserveAttempt} from '../cloudflare/watchdog/worker.mjs';
const NOW=Date.parse('2026-10-18T22:12:00+08:00');
const TOKEN='github_pat_'+'test_secret_'.repeat(4);
const fresh={status:'ok',generated_at:'2026-10-18T14:01:00Z'};
const stale={status:'ok',generated_at:'2026-10-18T13:49:00Z'};
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
function environment(t) {
  const sqlite=new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../cloudflare/watchdog/schema.sql',import.meta.url),'utf8'));
  t.after(()=>sqlite.close());
  const db={prepare(sql){return {params:[],bind(...params){this.params=params;return this;},async run(){return {meta:{changes:Number(sqlite.prepare(sql).run(...this.params).changes)}};},async first(){return sqlite.prepare(sql).get(...this.params)||null;}};}};
  return {PUBLIC_HOST:'headline.infinitas.top',WATCHDOG_ENABLED:'true',GITHUB_ACTIONS_TOKEN:TOKEN,WATCHDOG_DB:db};
}
test('current Beijing slot, midnight and next independent check use the two-hour cadence',()=> {
  assert.ok(isFresh(fresh,NOW));assert.ok(!isFresh(stale,NOW));assert.ok(!isFresh({...fresh,status:'partial'},NOW));
  assert.ok(!isFresh({...fresh,generated_at:'2099-01-01T00:00:00Z'},NOW));
  assert.equal(nextCheck(NOW),'2026-10-18T14:32:00.000Z');
  assert.equal(nextCheck(Date.parse('2026-10-18T23:59:00+08:00')),'2026-10-18T16:02:00.000Z');
  assert.ok(!isFresh(stale,Date.parse('2026-10-19T00:02:00+08:00')));
});
test('disabled, missing or broad OAuth credentials never cause an outgoing request',async t=> {
  for(const patch of [{WATCHDOG_ENABLED:'false'},{GITHUB_ACTIONS_TOKEN:''},{GITHUB_ACTIONS_TOKEN:'gho_broad_oauth_token'}]){
    const env=Object.assign(environment(t),patch);
    const result=await runCheck(env,{now:NOW,fetcher:()=>assert.fail('must not fetch')});
    assert.ok(['disabled','missing_token'].includes(result.last_result));
  }
});
test('fresh published receipt avoids GitHub and never sends the key to the news site',async t=> {
  const env=environment(t);let calls=0;
  const result=await runCheck(env,{now:NOW,fetcher:async(url,options)=>{
    calls++;assert.ok(url.startsWith('https://headline.infinitas.top/data/status.json?watchdog='));
    assert.equal(options.headers.Authorization,undefined);return json(fresh);
  }});
  assert.equal(result.last_result,'healthy');assert.equal(calls,1);
});
test('missing slot dispatches only the fixed workflow and main branch with safe inputs',async t=> {
  const env=environment(t),requests=[];
  const result=await runCheck(env,{now:NOW,fetcher:async(url,options)=>{
    requests.push([url,options]);
    if(url.includes('/data/status.json'))return json(stale);
    assert.ok(url.startsWith('https://api.github.com/repos/Suesone/headline/actions/workflows/update.yml/'));
    assert.equal(options.headers.Authorization,'Bearer '+TOKEN);assert.equal(options.redirect,'manual');
    if(url.includes('/runs?'))return json({workflow_runs:[]});
    assert.deepEqual(JSON.parse(options.body),{ref:'main',inputs:{trigger_source:'cloudflare-watchdog',requested_slot:'2026-10-18T14:00:00.000Z'}});
    return new Response(null,{status:204});
  }});
  assert.equal(result.last_result,'dispatched');assert.equal(requests.length,3);
});
test('recent executing or queued workflows suppress duplicate dispatch',async t=> {
  for(const status of ['in_progress','queued','waiting']){
    const env=environment(t);
    const result=await runCheck(env,{now:NOW,fetcher:async(url,options)=>{
      assert.notEqual(options.method,'POST');return json(url.includes('/data/status.json')?stale:{workflow_runs:[{status,created_at:new Date(NOW-60000).toISOString()}]});
    }});assert.equal(result.last_result,'running');
  }
});
test('atomic SQLite reservation prevents concurrent duplicates, enforces cooldown and caps four attempts',async t=> {
  const env=environment(t);
  const race=await Promise.all([reserveAttempt(env,NOW),reserveAttempt(env,NOW)]);
  assert.equal(race.filter(x=>x.allowed).length,1);
  assert.equal((await reserveAttempt(env,NOW+60000)).allowed,false);
  for(let i=1;i<4;i++)assert.equal((await reserveAttempt(env,NOW+i*10*60000)).allowed,true);
  assert.equal((await reserveAttempt(env,NOW+40*60000)).allowed,false);
});
test('public status is read only; wrong host, paths and POST cannot trigger GitHub',async t=> {
  const env=environment(t);
  await runCheck(env,{now:NOW,fetcher:async()=>json(fresh)});
  const status=await handleStatus(new Request('https://headline.infinitas.top/api/watchdog/status'),env);
  assert.equal(status.status,200);const body=await status.text();assert.ok(!body.includes(TOKEN));assert.ok(!body.includes('GITHUB_ACTIONS_TOKEN'));
  for(const [url,method] of [['https://evil.example/api/watchdog/status','GET'],['https://headline.infinitas.top/api/watchdog/trigger','POST'],['https://headline.infinitas.top/api/watchdog/status','POST']]){
    assert.equal((await handleStatus(new Request(url,{method}),env)).status,404);
  }
});
test('enabling a configured watchdog replaces the previous disabled receipt with pending',async t=> {
  const env=environment(t);
  env.WATCHDOG_ENABLED='false';
  await runCheck(env,{now:NOW,fetcher:()=>assert.fail('must not fetch')});
  env.WATCHDOG_ENABLED='true';
  const body=await (await handleStatus(new Request('https://headline.infinitas.top/api/watchdog/status'),env)).json();
  assert.equal(body.enabled,true);assert.equal(body.last_result,'pending');
});
test('GitHub permission failures and raw upstream errors cannot leak the secret',async t=> {
  const env=environment(t);
  const denied=await runCheck(env,{now:NOW,fetcher:async url=>url.includes('/data/status.json')?json(stale):json({message:TOKEN},401)});
  assert.equal(denied.last_result,'credentials');assert.ok(!JSON.stringify(denied).includes(TOKEN));
  const failed=await runCheck(env,{now:NOW,fetcher:async()=>{throw new Error(TOKEN);}});
  assert.equal(failed.last_result,'github_unavailable');assert.ok(!JSON.stringify(failed).includes(TOKEN));
});
test('rate limiting, site failure and old stuck runs get bounded recovery instead of silent success',async t=> {
  const env=environment(t);
  const limited=await runCheck(env,{now:NOW,fetcher:async url=>url.includes('/data/status.json')?json(stale):new Response('{}',{status:403,headers:{'x-ratelimit-remaining':'0'}})});
  assert.equal(limited.last_result,'github_unavailable');
  const recovered=await runCheck(env,{now:NOW,fetcher:async(url,options)=>{
    if(url.includes('/data/status.json'))throw new Error('site offline');
    if(options.method==='POST')return new Response(null,{status:204});
    return json({workflow_runs:[{status:'queued',created_at:new Date(NOW-30*60000).toISOString()}]});
  }});assert.equal(recovered.last_result,'dispatched');
});
