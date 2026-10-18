'use strict';
const statusNode = document.getElementById('login-status');
const message = value => {statusNode.textContent=value;};
const post = (path,body) => fetch(path,{method:'POST',credentials:'same-origin',redirect:'error',headers:{'Content-Type':'application/json','X-Headline-Cloud':'1'},body:JSON.stringify(body)});
async function signIn(result) {
  message('正在验证 Google 身份…');
  try {
    const response=await post('/api/cloud/session',{credential:result.credential});
    const data=await response.json();if(!response.ok)throw new Error(data.message||'登录失败');
    location.replace('/#local-tools');
  } catch(error){message(error.message||'登录暂时不可用，请重试');}
}
document.getElementById('logout').addEventListener('click',async()=>{
  try {const response=await post('/api/cloud/logout',{});if(!response.ok)throw new Error();window.google?.accounts.id.disableAutoSelect();message('已退出本站翻译登录。');}
  catch {message('退出暂时失败，请稍后重试。');}
});
window.addEventListener('load',async()=>{
  if(location.protocol!=='https:' || location.hostname!=='headline.infinitas.top'){message('请从 https://headline.infinitas.top/ 打开登录页。');return;}
  try {
    const response=await fetch('/api/cloud/config',{cache:'no-store',credentials:'same-origin',redirect:'error'});
    if(!response.ok)throw new Error('云端 Google 登录尚未配置完成。');
    const config=await response.json();if(!window.google?.accounts?.id)throw new Error('Google 登录组件加载失败，请检查网络后刷新。');
    google.accounts.id.initialize({client_id:config.client_id,callback:signIn,auto_select:false,cancel_on_tap_outside:true});
    google.accounts.id.renderButton(document.getElementById('google-button'),{type:'standard',theme:'outline',size:'large',text:'signin_with',shape:'rectangular'});
    message('请选择获准的 Google 账号，完成登录后返回新闻页。');
  }catch(error){message(error.message||'登录暂时不可用。');}
});
