'use strict';
const form = document.getElementById('controls'), status = document.getElementById('status'), frame = document.getElementById('preview');
let token, saved, defaults, timer, revision = 0, queue = Promise.resolve(), mobile = false;
function fitPreview() {
  const canvas = document.getElementById('preview-canvas'), width = mobile ? Math.min(390,canvas.clientWidth) : 1336;
  const scale = Math.min(1,canvas.clientWidth / width);
  frame.style.width = width+'px'; frame.style.height = (canvas.clientHeight / scale)+'px'; frame.style.transform = 'scale('+scale+')';
}
new ResizeObserver(fitPreview).observe(document.getElementById('preview-canvas'));
const numbers = ['titleSize','mobileSize','weight','spacing','width','columns','boardColumns'];
function read() { return Object.fromEntries(Object.keys(saved).map(key => [key,numbers.includes(key) ? Number(form.elements.namedItem(key).value) : form.elements.namedItem(key).value])); }
function fill(value) { for (const [key,item] of Object.entries(value)) form.elements.namedItem(key).value = item; outputs(); }
function outputs() { for (const key of ['titleSize','mobileSize','spacing','width']) document.getElementById(key+'-value').value = form.elements.namedItem(key).value+' px'; }
function refresh() {
  const doc = frame.contentDocument;
  if (!doc?.head) return;
  let sheet = doc.getElementById('local-editor-preview');
  if (!sheet) { sheet = doc.createElement('link'); sheet.id = 'local-editor-preview'; sheet.rel = 'stylesheet'; doc.head.append(sheet); }
  sheet.href = '/_draft.css?v='+(++revision);
  fetch('/_editor/draft-text').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(values=>{
    for (const node of doc.querySelectorAll('[data-editor-text]')) {
      const text = values[node.dataset.editorText]; if (typeof text === 'string') node.textContent = text;
    }
  }).catch(()=>{status.textContent='文案预览未更新，请重试。';});
}
async function request(path,value) {
  const response = await fetch('/_editor/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Editor-Token':token},body:JSON.stringify(value)});
  const result = await response.json(); if (!response.ok) throw new Error(result.error || '无法保存');
  refresh();
}
function preview() {
  clearTimeout(timer); const value = read();
  queue = queue.catch(()=>{}).then(()=>request('preview',value)).catch(error=>{status.textContent=error.message;});
}
frame.addEventListener('load',refresh);
form.addEventListener('input',()=>{ outputs(); status.textContent = '预览中，尚未保存。'; clearTimeout(timer); timer = setTimeout(preview,180); });
form.addEventListener('submit',async event=>{
  event.preventDefault(); clearTimeout(timer); const value = read();
  for (const button of form.querySelectorAll('button')) button.disabled = true;
  try { await queue; await request('save',value); saved = {...value}; status.textContent = '已保存到本地项目。公开网站尚未发布。'; }
  catch(error) { status.textContent = error.message; }
  finally { for (const button of form.querySelectorAll('button')) button.disabled = false; }
});
document.getElementById('reset').addEventListener('click',()=>{fill(defaults);preview();status.textContent='已预览默认样式，保存后才会覆盖本地设置。';});
document.getElementById('revert').addEventListener('click',()=>{fill(saved);preview();status.textContent='已恢复上次保存的外观。';});
for (const mode of ['desktop','mobile']) document.getElementById(mode).addEventListener('click',()=>{
  mobile = mode === 'mobile'; document.getElementById('preview-stage').classList.toggle('mobile',mobile); fitPreview();
  for (const name of ['desktop','mobile']) document.getElementById(name).setAttribute('aria-pressed',String(mode===name));
});
for (const input of form.elements) input.disabled = true;
fetch('/_editor/state').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(value=>{
  token=value.token;saved=value.settings;defaults=value.defaults;fill(saved);
  for (const input of form.elements) input.disabled = false;
  status.textContent='已加载本地外观。拖动滑块即可预览。';refresh();
}).catch(()=>{status.textContent='无法连接本机编辑器。请关闭此页，重新双击启动文件。';});
