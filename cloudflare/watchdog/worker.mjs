// Independent scheduler only. No news text, Gemini secret, or public trigger endpoint.
const HOST = 'headline.infinitas.top';
const API = 'https://api.github.com/repos/Suesone/headline/actions/workflows/update.yml';
const HOUR = 3600000, SLOT = 2 * HOUR;
const ACTIVE = new Set(['queued','in_progress','waiting','pending','requested']);
export const RESULTS = {
  pending:'独立兜底已启用，等待首次定时检查',
  disabled:'Cloudflare 兜底尚未开启', missing_token:'尚未配置专用 GitHub 凭据',
  healthy:'本时段新闻已成功发布，无需补抓', running:'已有更新任务执行或排队中',
  dispatched:'已请求 GitHub 补抓，等待任务完成发布', cooldown:'已请求补抓，等待下一次检查',
  capped:'本时段已达到 4 次补抓上限', credentials:'GitHub 凭据过期或权限不足，请检查 Secret',
  github_unavailable:'GitHub 接口暂不可用，下一次检查重试',
  unavailable:'检查暂不可用，下一次检查重试'
};
const reply = (status, value) => new Response(JSON.stringify(value), {status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
export const slotStart = now => Math.floor(now / SLOT) * SLOT;
export function nextCheck(now) {
  const start=slotStart(now);
  for(const base of [start,start+SLOT]) for(const minutes of [2,12,32,52]) {
    const stamp=base+minutes*60000; if(stamp>now) return new Date(stamp).toISOString();
  }
}
export function isFresh(data,now) {
  const stamp=Date.parse(data?.generated_at);
  return data?.status==='ok' && Number.isFinite(stamp) && stamp>=slotStart(now) && stamp<=now+300000;
}
async function boundedJson(response,limit) {
  if(Number(response.headers.get('Content-Length'))>limit) throw new Error('size');
  const reader=response.body?.getReader();if(!reader) throw new Error('body');
  let size=0;const chunks=[];
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw new Error('size');}chunks.push(value);}
  const raw=new Uint8Array(size);let offset=0;for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.length;}
  return JSON.parse(new TextDecoder().decode(raw));
}
function configured(env) {return env.WATCHDOG_ENABLED==='true' && env.PUBLIC_HOST===HOST;}
function tokenReady(env) {return /^github_pat_[A-Za-z0-9_]{20,}$/.test(env.GITHUB_ACTIONS_TOKEN?.trim() || '');}
async function readHealth(env) {
  const row=await env.WATCHDOG_DB.prepare('SELECT payload FROM watchdog_health WHERE id = 1').first();
  return row ? JSON.parse(row.payload) : {};
}
async function saveHealth(env,value) {
  await env.WATCHDOG_DB.prepare('INSERT INTO watchdog_health(id,payload) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=json_patch(watchdog_health.payload,excluded.payload)').bind(JSON.stringify(value)).run();
  return value;
}
export async function reserveAttempt(env,now) {
  const slot=slotStart(now);
  await env.WATCHDOG_DB.prepare('DELETE FROM watchdog_attempts WHERE slot < ?').bind(now-3*24*HOUR).run();
  await env.WATCHDOG_DB.prepare('INSERT OR IGNORE INTO watchdog_attempts(slot,attempts,last_attempt) VALUES (?,0,0)').bind(slot).run();
  const result=await env.WATCHDOG_DB.prepare('UPDATE watchdog_attempts SET attempts=attempts+1,last_attempt=? WHERE slot=? AND attempts<4 AND last_attempt<=?').bind(now,slot,now-10*60000).run();
  const state=await env.WATCHDOG_DB.prepare('SELECT attempts,last_attempt FROM watchdog_attempts WHERE slot=?').bind(slot).first();
  return {allowed:result.meta.changes===1,attempts:state.attempts};
}
export async function runCheck(env,{now=Date.now(),fetcher=(...args)=>fetch(...args)}={}) {
  await readHealth(env);
  const health={last_checked_at:new Date(now).toISOString(),slot:new Date(slotStart(now)).toISOString()};
  const finish=result=>saveHealth(env,{...health,last_result:result,message:RESULTS[result]});
  if(!configured(env))return finish('disabled');
  if(!tokenReady(env))return finish('missing_token');
  try {
    const published=await fetcher(`https://${HOST}/data/status.json?watchdog=${now}`,{redirect:'manual',headers:{'Cache-Control':'no-cache'},signal:AbortSignal.timeout(12000)});
    if(published.ok && isFresh(await boundedJson(published,32000),now))return finish('healthy');
  } catch {} // A failed site check should allow recovery, subject to GitHub and atomic limits.
  const headers={'Authorization':`Bearer ${env.GITHUB_ACTIONS_TOKEN.trim()}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Headline schedule watchdog'};
  try {
    const response=await fetcher(`${API}/runs?per_page=10`,{headers,redirect:'manual',signal:AbortSignal.timeout(12000)});
    if(response.status===401 || response.status===403 && response.headers.get('x-ratelimit-remaining')!=='0')return finish('credentials');
    if(!response.ok)return finish('github_unavailable');
    const data=await boundedJson(response,200000);
    if(!Array.isArray(data.workflow_runs))return finish('github_unavailable');
    if(data.workflow_runs.some(run=>ACTIVE.has(run.status) && Date.parse(run.created_at)>=now-20*60000))return finish('running');
    const reservation=await reserveAttempt(env,now);
    if(!reservation.allowed)return finish(reservation.attempts>=4?'capped':'cooldown');
    const dispatch=await fetcher(`${API}/dispatches`,{method:'POST',headers:{...headers,'Content-Type':'application/json'},redirect:'manual',signal:AbortSignal.timeout(12000),
      body:JSON.stringify({ref:'main',inputs:{trigger_source:'cloudflare-watchdog',requested_slot:new Date(slotStart(now)).toISOString()}})});
    if([401,403].includes(dispatch.status))return finish('credentials');
    if(![200,204].includes(dispatch.status))return finish('github_unavailable');
    health.last_dispatch_at=new Date(now).toISOString();
    health.dispatch_count=reservation.attempts;
    return finish('dispatched');
  } catch {return finish('github_unavailable');} // No raw upstream errors or credentials in logs/status.
}
export async function handleStatus(request,env) {
  const url=new URL(request.url);
  if(url.protocol!=='https:' || url.hostname!==HOST || url.pathname!=='/api/watchdog/status' || request.method!=='GET')return reply(404,{message:'接口不存在'});
  try {
    const stored=await readHealth(env);
    const last_result=!configured(env)?'disabled':!tokenReady(env)?'missing_token':
      !stored.last_result || ['disabled','missing_token'].includes(stored.last_result)?'pending':stored.last_result;
    return reply(200,{enabled:configured(env)&&tokenReady(env),last_result,message:RESULTS[last_result]||RESULTS.unavailable,
      last_checked_at:stored.last_checked_at||null,last_dispatch_at:stored.last_dispatch_at||null,
      dispatch_count:stored.dispatch_count||0,next_check_at:nextCheck(Date.now())});
  } catch {return reply(503,{enabled:false,last_result:'unavailable',message:RESULTS.unavailable});}
}
export default {
  fetch:handleStatus,
  scheduled(event,env,ctx){ctx.waitUntil(runCheck(env).catch(()=>{}));}
};
