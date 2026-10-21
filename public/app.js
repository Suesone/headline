'use strict';
const $ = id => document.getElementById(id);
const el = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
const format = stamp => new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(stamp));
function safeUrl(value) { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; } catch { return null; } }
function link(text, value, className) { const n = el('a', text, className); const url = safeUrl(value); if (url) { n.href = url; n.target = '_blank'; n.rel = 'noopener noreferrer'; } return n; }
function option(value, text) { const n = el('option',text); n.value = value; return n; }
let data, busy = false, controller = null, rendering = 0, translationsVisible = true;
const expandedSources = new Set(), selected = new Set(), hiddenArticleTranslations = new Set();
const translator = new HeadlineLocal.LocalTranslator();
translator.setEngine('gemini');
const engineLabel = () => translator.engine === 'gemini' ? 'Gemini 云端' : '本机';
const engineNote = () => translator.engine === 'gemini' ? '原文发送 Google；本项目仅在本页保存译文，不上传 GitHub。Google 可能按其条款处理输入与输出。' : '译文只在此页面，未发送云端翻译服务。';
function sourceClass(s) { return 'tile-' + ({BBC:'bbc',NPR:'npr',CNBC:'cnbc','The Guardian':'guardian',NHK:'nhk'}[s.publisher] || 'all'); }
function sourceIcon(s) {
  const wrap = el('span', s.id === 'all' ? '榜' : ({'The Guardian':'G'}[s.publisher] || s.publisher), 'source-tile ' + sourceClass(s));
  const filename = {BBC:'bbc',NPR:'npr',CNBC:'cnbc','The Guardian':'guardian',NHK:'nhk'}[s.publisher];
  if (filename) {
    const img = el('img'); img.src = `./icons/${filename}.${filename === 'cnbc' ? 'ico' : 'png'}`; img.alt = ''; img.width = 40; img.height = 40;
    img.addEventListener('error', () => img.remove(), {once:true}); wrap.append(img);
  }
  return wrap;
}
function sourceInfo(id) { return data.sources.find(s => s.id === id); }
function rankSetting(key, fallback, max = 30) { const value = data.ranking?.[key]; return Number.isInteger(value) && value > 0 && value <= max ? value : fallback; }
function retainedArticles() {
  const cutoff = Date.now() - 72 * 3600000;
  return data.articles.filter(a => Date.parse(a.published_at) >= cutoff && sourceInfo(a.source_id)?.enabled);
}
function archiveDate(article) {
  return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date(article.published_at));
}
function initArchive() {
  for (const s of data.sources.filter(s => s.enabled)) $('archive-source').append(option(s.id,s.name));
  $('archive-date').addEventListener('change',renderArchive);
  $('archive-source').addEventListener('change',renderArchive);
  renderArchive();
}
function renderArchive() {
  const articles = retainedArticles(), dates = [...new Set(articles.map(archiveDate))].sort().reverse();
  const chosen = $('archive-date').value;
  $('archive-date').replaceChildren(option('all','最近 72 小时'),...dates.map(date => option(date,date)));
  $('archive-date').value = dates.includes(chosen) ? chosen : 'all';
  const grid = $('archive-list'); grid.replaceChildren();
  for (const source of data.sources.filter(s => s.enabled && ($('archive-source').value === 'all' || s.id === $('archive-source').value))) {
    const items = articles.filter(a => a.source_id === source.id && ($('archive-date').value === 'all' || archiveDate(a) === $('archive-date').value));
    const card = el('section',undefined,'source-card');
    card.append(el('h3',source.name,'archive-source-heading'));
    const rows = el('div',undefined,'source-card-list'), key = 'archive:' + source.id;
    const expanded = expandedSources.has(key);
    if (!items.length) rows.append(el('p','该日期暂无存档。','empty-state'));
    items.slice(0,expanded ? items.length : 5).forEach((a,i) => rows.append(articleNode(a,i+1,true)));
    card.append(rows);
    if (items.length > 5) {
      const more = el('button',expanded ? '收起' : '更多','archive-expand');
      more.type = 'button'; more.setAttribute('aria-expanded',String(expanded));
      more.addEventListener('click',() => { if (busy) return; expanded ? expandedSources.delete(key) : expandedSources.add(key); renderArchive(); });
      card.append(more);
    }
    grid.append(card);
  }
}
function pool() {
  const id = $('window-select').value;
  let all = retainedArticles();
  if (id === 'recent') all = all.filter(a => Date.parse(a.published_at) >= Date.now() - 24 * 3600000);
  else if (id !== 'all') { const window = data.windows.find(w => w.id === id); const ids = new Set(window?.article_ids || []); all = all.filter(a => ids.has(a.id)); }
  const source = $('source-select').value;
  return all.filter(a => source === 'all' || a.source_id === source);
}
function shortcuts() {
  const list = $('source-shortcuts'); list.replaceChildren();
  const sources = [{id:'all',name:'全部来源',publisher:'全部',enabled:true}, ...data.sources.filter(s => s.enabled)];
  for (const s of sources) {
    const button = el('button',undefined,'source-shortcut' + (s.id === $('source-select').value ? ' active' : ''));
    button.type = 'button'; button.setAttribute('aria-pressed',String(s.id === $('source-select').value));
    button.setAttribute('aria-label',s.name); button.append(sourceIcon(s),el('span',s.id === 'all' ? '全部来源' : s.name.replace(' · 社区 RSS','')),el('span',s.id === 'all' ? '新闻总览' : s.relay_name === 'Google News 聚合' ? (s.using_fallback ? 'Google News 备用' : '日语 · Google News') : s.relay_name ? '社区RSS' : '官方 RSS','shortcut-subtitle'));
    button.addEventListener('click',() => { if (busy) return; $('source-select').value = s.id; render(); }); list.append(button);
  }
}
function textBlock(text, article, part, tag, className) {
  const n = el(tag,text,className); n.lang = sourceInfo(article.source_id)?.language || 'en'; n.dataset.translation = text; n.dataset.article = article.id; n.dataset.part = part;
  const translated = el('p',undefined,'translated-text'); translated.lang = 'zh-CN'; translated.hidden = true;
  const cached = translator.getCached(text);
  if (cached) { translated.textContent = cached; translated.hidden = !translationsVisible || hiddenArticleTranslations.has(article.id); }
  const wrap = el('div',undefined,'translation-pair'); wrap.append(n,translated); return wrap;
}
function updateSelection() { $('translate-selected').textContent = `翻译所选报道（${selected.size}）`; }
function articleNode(article, rank, featured, board = null) {
  const source = sourceInfo(article.source_id);
  const wrap = el('article',undefined,'article' + (featured ? ' featured' : '') + (board ? ' board-article' : ''));
  wrap.dataset.articleId = article.id;
  wrap.append(el('span',String(rank),'article-index'));
  const body = el('div',undefined,'article-body');
  const title = textBlock(article.title,article,'title','h3','article-title');
  const heading = title.querySelector('h3'); heading.replaceChildren(link(article.title,article.url,'article-link'));
  body.append(title);
  const meta = el('div',undefined,'article-meta');
  const credit = source.publisher === 'BBC' ? 'BBC News' : source.publisher;
  meta.append(link(credit,source.homepage),el('span',(article.time_basis === 'feed_publication' ? '订阅 ' : '') + format(article.published_at)));
  if (board && board.publisher_count > 1) meta.append(el('span',`${board.publisher_count} 家媒体 · 同标题`,'cross-source'));
  if (board) meta.append(el('span',`来源榜第 ${Math.min(...board.positions.map(p=>p.position))} 位`));
  if (article.time_basis === 'feed_publication' && new URL(article.url).hostname === 'news.google.com') meta.append(el('span','经 Google News 跳转'));
  body.append(meta);
  const actions = el('div',undefined,'article-actions');
  const label = el('label',undefined,'selection-label'); const check = el('input'); check.type = 'checkbox'; check.checked = selected.has(article.id); check.dataset.selectArticle = article.id; check.setAttribute('aria-label','选择报道：' + article.title);
  check.addEventListener('change',() => { if (check.checked) selected.add(article.id); else selected.delete(article.id); for (const other of document.querySelectorAll('input[data-select-article]')) if (other.dataset.selectArticle === article.id) other.checked = check.checked; updateSelection(); }); label.append(check,document.createTextNode('选择'));
  const one = el('button','翻译','text-button article-translate'); one.type = 'button'; one.dataset.toggleArticle = article.id;
  one.setAttribute('aria-label','翻译报道：' + article.title);
  const showing = !title.querySelector('.translated-text').hidden;
  one.setAttribute('aria-pressed',String(showing)); if (showing) one.textContent = '隐藏译文';
  one.addEventListener('click',() => {
    if (busy) return;
    if ([...body.querySelectorAll('.translated-text')].some(n => !n.hidden && n.textContent)) {
      hiddenArticleTranslations.add(article.id); setTranslationVisibility(translationsVisible);
      $('translation-status').textContent = '已隐藏这条报道的译文，缓存仍保留；再次点击“翻译”即可恢复。';
    } else {
      hiddenArticleTranslations.delete(article.id);
      translateNodes([...body.querySelectorAll('[data-translation]')]);
    }
  });
  const full = el('button','全文 →','text-button article-fulltext'); full.type = 'button'; full.setAttribute('aria-label','全文翻译：' + article.title); full.addEventListener('click',() => openFulltext(article));
  actions.append(label,one,full); body.append(actions); wrap.append(body); return wrap;
}
function render() {
  rendering++; selected.clear(); updateSelection(); shortcuts();
  const articles = pool(), now = Date.parse(data.generated_at);
  const board = HeadlineRanking.buildBoard(articles,now,rankSetting('board_limit',10));
  const list = $('board-list'); list.replaceChildren();
  if (!board.length) list.append(el('p','当前时段没有报道，请切换到最近 24 小时或历史时段。','empty-state'));
  board.forEach((entry,i) => list.append(articleNode(entry.article,i + 1,true,entry)));
  const window = data.windows.find(w => w.id === $('window-select').value);
  $('period-caption').textContent = window ? `${format(window.start)} — ${format(window.end)} · 北京时间` : $('window-select').value === 'recent' ? `最近 24 小时 · 所有标题加大` : `最近 72 小时存档 · 所有标题加大`;
  const grid = $('news-list'); grid.replaceChildren();
  for (const s of data.sources.filter(s => s.enabled && ($('source-select').value === 'all' || s.id === $('source-select').value))) {
    const items = HeadlineRanking.rankSources(articles.filter(a => a.source_id === s.id),now);
    const card = el('section',undefined,'source-card'); card.setAttribute('aria-label',s.name + ' 新闻榜单');
    const header = el('div',undefined,'source-card-header'); const icon = sourceIcon(s); icon.className = 'source-card-icon ' + sourceClass(s);
    const sourceHeading = el('div'); sourceHeading.append(el('h3',s.name));
    if (s.time_basis === 'community_collection') sourceHeading.append(el('span','社区RSS','shortcut-subtitle'));
    header.append(icon,sourceHeading); card.append(header);
    const rows = el('div',undefined,'source-card-list');
    if (!items.length) { rows.append(el('p','所选时段暂无报道。可前往“新闻存档”查看历史。','empty-state')); }
    const collapsedLimit = rankSetting('per_source_limit',5);
    const expanded = expandedSources.has(s.id);
    const limit = expanded ? items.length : collapsedLimit;
    items.slice(0,limit).forEach((a,i) => rows.append(articleNode(a,i + 1,true)));
    card.append(rows);
    const footer = el('div',undefined,'source-card-footer');
    if (items.length > collapsedLimit) {
      const more = el('button',expanded ? '收起' : '更多','text-button source-expand'); more.type = 'button';
      more.setAttribute('aria-expanded',String(expanded)); more.setAttribute('aria-label',`${expanded ? '收起' : '更多'}：${s.name}`);
      more.addEventListener('click',() => { if (busy) return; if (expanded) expandedSources.delete(s.id); else expandedSources.add(s.id); render(); }); footer.append(more);
    }
    else if (s.time_basis !== 'community_collection') footer.append(el('span',s.relay_name ? `${s.relay_name}${s.relay_name === 'Google News 聚合' ? (s.using_fallback ? ' · 备用' : '') : ' 社区 RSS'}` : s.community_name ? '社区目录 · 官方 RSS' : '官方 RSS'));
    footer.append(link(s.publisher === 'BBC' ? 'BBC News ↗' : '来源网站 ↗',s.homepage)); card.append(footer); grid.append(card);
  }
}
function setBusy(value) {
  busy = value;
  for (const n of document.querySelectorAll('.article-actions button,.source-shortcut,.source-card-footer button,.archive-expand,#archive-date,#archive-source,#translate-selected,#translation-engine,#window-select,#source-select,#translate-fulltext,#clear-translations')) n.disabled = value;
  $('cancel-translation').hidden = !value;
  $('cancel-fulltext').hidden = !value;
}
function setTranslationVisibility(show, announce = false) {
  translationsVisible = show;
  if (show && announce) hiddenArticleTranslations.clear();
  for (const node of document.querySelectorAll('.translated-text')) node.hidden = !show || !node.textContent || hiddenArticleTranslations.has(node.previousElementSibling.dataset.article);
  for (const button of document.querySelectorAll('[data-toggle-article]')) {
    const showing = [...button.closest('article').querySelectorAll('.translated-text')].some(n => !n.hidden && n.textContent);
    button.textContent = showing ? '隐藏译文' : '翻译'; button.setAttribute('aria-pressed',String(showing));
  }
  $('fulltext-output').hidden = !show || !$('fulltext-output').textContent;
  const hasTranslations = translator.cache.size > 0 || Boolean($('fulltext-output').textContent);
  for (const id of ['toggle-translations','toggle-translations-dock']) {
    const button = $(id); button.textContent = show ? '隐藏译文' : '显示译文';
    button.setAttribute('aria-pressed',String(show)); button.disabled = !hasTranslations;
  }
  if (announce) $('translation-status').textContent = show ? '已显示缓存译文，没有调用 AI。' : '已隐藏译文，缓存仍保留在本页；再次显示或翻译相同文字时复用缓存。';
}
async function translateNodes(nodes) {
  if (busy) return;
  const unique = [...new Set(nodes.map(n => n.dataset.translation))].filter(Boolean);
  if (!unique.length) { $('translation-status').textContent = '当前屏幕没有新闻文字。请先选择报道，或滚动到新闻处点击“翻译”。'; return; }
  for (const node of nodes) hiddenArticleTranslations.delete(node.dataset.article);
  setTranslationVisibility(true);
  // Reopening a cached translation needs neither login/status checks nor inference.
  const missing = unique.filter(text => !translator.getCached(text));
  const generation = rendering; controller = new AbortController(); setBusy(true);
  $('translation-status').textContent = `正在连接${engineLabel()}翻译接口…`;
  try {
    translator.setEngine($('translation-engine').value); if (missing.length) await translator.prepare();
    for (const [i,text] of unique.entries()) {
      controller.signal.throwIfAborted();
      $('translation-status').textContent = `正在通过${engineLabel()}翻译 ${i + 1}/${unique.length} 段，共 ${unique.reduce((sum,t)=>sum+t.length,0)} 个原文字符；重复文字复用缓存。`;
      const result = await translator.translate(text,{signal:controller.signal});
      if (generation !== rendering) continue;
      // Update only already rendered text, including its duplicated board/source occurrence.
      for (const node of document.querySelectorAll('[data-translation]')) if (node.dataset.translation === text) { const out = node.nextElementSibling; out.textContent = result; out.hidden = !translationsVisible || hiddenArticleTranslations.has(node.dataset.article); }
    }
    setTranslationVisibility(translationsVisible);
    $('translation-status').textContent = missing.length ? `已通过${engineLabel()}翻译 ${unique.length} 段。${engineNote()}` : `已显示 ${unique.length} 段缓存译文，没有调用 AI。`;
  } catch (error) { $('translation-status').textContent = error.name === 'AbortError' ? '已停止后续翻译，已完成的译文保留在本页。' : error.message; }
  finally { setBusy(false); controller = null; setTranslationVisibility(translationsVisible); }
}
function openFulltext(article = {title: '自选新闻文本', url: ''}) {
  if (busy) return;
  $('fulltext-article').textContent = article.title;
  const url = safeUrl(article.url); $('fulltext-original').hidden = !url; if (url) $('fulltext-original').href = url; else $('fulltext-original').removeAttribute('href');
  $('fulltext-input').value = ''; $('fulltext-output').textContent = ''; $('fulltext-output').hidden = true; $('fulltext-status').textContent = ''; $('fulltext-size').textContent = '0 字符'; $('fulltext-file').value = '';
  $('fulltext-dialog').showModal();
}
async function translateFulltext() {
  if (busy) return;
  const text = $('fulltext-input').value.trim(); if (!text) { $('fulltext-status').textContent = '请先粘贴正文或导入 .txt。'; return; }
  setTranslationVisibility(true);
  controller = new AbortController(); setBusy(true); $('fulltext-input').disabled = true; $('fulltext-file').disabled = true;
  $('fulltext-output').textContent = ''; $('fulltext-output').hidden = true;
  $('fulltext-status').textContent = `正在准备${engineLabel()}翻译引擎…`;
  try {
    translator.setEngine($('translation-engine').value); await translator.prepare();
    const result = await translator.translate(text,{signal:controller.signal,progress:(done,total)=> { $('fulltext-status').textContent = `${engineLabel()}全文翻译：${done}/${total} 段。${text.length} 字符。${engineNote()}`; }});
    $('fulltext-output').textContent = result; $('fulltext-output').hidden = !translationsVisible;
    setTranslationVisibility(translationsVisible);
    $('fulltext-status').textContent = `全文翻译完成。${engineNote()}`;
  } catch (error) { $('fulltext-status').textContent = error.name === 'AbortError' ? '已停止全文翻译。' : error.message; }
  finally { setBusy(false); $('fulltext-input').disabled = false; $('fulltext-file').disabled = false; controller = null; setTranslationVisibility(translationsVisible); }
}
function clearTranslations() {
  if (busy) return;
  translator.clear(); hiddenArticleTranslations.clear(); for (const n of document.querySelectorAll('.translated-text')) { n.textContent = ''; n.hidden = true; }
  $('fulltext-input').value = ''; $('fulltext-output').textContent = ''; $('fulltext-output').hidden = true; $('fulltext-file').value = ''; $('fulltext-status').textContent = ''; $('fulltext-size').textContent = '0 字符';
  setTranslationVisibility(true);
  $('translation-status').textContent = '已清除本页译文和缓存。下次翻译需要重新调用 AI。';
}
function initTranslation() {
  $('cloud-login').hidden = !HeadlineLocal.isCloudHost(location);
  $('translate-selected').addEventListener('click',() => translateNodes([...document.querySelectorAll('[data-translation]')].filter(n=>selected.has(n.dataset.article))));
  $('cancel-translation').addEventListener('click',() => controller?.abort());
  $('cancel-fulltext').addEventListener('click',() => controller?.abort());
  $('open-manual-fulltext').addEventListener('click',() => openFulltext());
  new MutationObserver(() => { $('translation-toast').textContent = $('translation-status').textContent; $('translation-toast').hidden = false; }).observe($('translation-status'),{childList:true,subtree:true,characterData:true});
  $('clear-translations').addEventListener('click',clearTranslations);
  for (const id of ['toggle-translations','toggle-translations-dock']) $(id).addEventListener('click', () => {
    if (translationsVisible) controller?.abort();
    setTranslationVisibility(!translationsVisible,true);
  });
  setTranslationVisibility(translationsVisible);
  $('translation-engine').addEventListener('change',() => { translator.setEngine($('translation-engine').value); $('translation-location').textContent = translator.engine === 'gemini' ? 'GOOGLE CLOUD API' : 'LOCAL ONLY'; $('translation-status').textContent = `已切换${engineLabel()}引擎，点击后才翻译。${engineNote()}`; });
  $('close-fulltext').addEventListener('click',() => { controller?.abort(); $('fulltext-dialog').close(); });
  $('fulltext-dialog').addEventListener('cancel',()=>controller?.abort());
  $('translate-fulltext').addEventListener('click',translateFulltext);
  $('fulltext-input').addEventListener('input',()=> { $('fulltext-size').textContent = `${$('fulltext-input').value.length} 字符`; });
  $('fulltext-file').addEventListener('change',async () => {
    const file = $('fulltext-file').files[0]; if (!file) return;
    if (!file.name.toLowerCase().endsWith('.txt') || file.size > 240000) { $('fulltext-status').textContent = '请选择不超过 240 KB 的 .txt 文本。'; return; }
    try { const text = await file.text(); if (text.length > 60000) throw new Error('最多 60,000 字符，请分次粘贴。'); $('fulltext-input').value = text; $('fulltext-size').textContent = `${text.length} 字符`; $('fulltext-status').textContent = '已从本机读取文本，尚未翻译。'; } catch(error) { $('fulltext-status').textContent = error.message; }
  });
}
function renderStatus() {
  const enabled = data.sources.filter(s=>s.enabled);
  const ok = enabled.filter(s=>s.status==='ok').length;
  const slotStart = Math.floor(Date.now() / (2 * 3600000)) * 2 * 3600000;
  const missedSlot = Date.parse(data.generated_at) < slotStart && Date.now() - slotStart > 45 * 60000;
  const outdated = missedSlot || Date.now() - Date.parse(data.generated_at) > 3 * 3600000;
  $('run-status').textContent = `${ok}/${enabled.length} 个订阅流读取成功 · 实际更新时间 ${format(data.generated_at)}${outdated ? ' · 本时段尚未更新，调度可能延迟' : ''}${data.status==='error' ? ' · 本次失败，保留旧新闻' : data.status==='partial' ? ' · 部分来源读取失败，保留旧记录' : ''}`;
  const trigger = data.trigger || {};
  const triggerLabel = trigger.event === 'schedule' ? (trigger.schedule === '0 */2 * * *' ? '整点定时' : '定时补抓') : trigger.event === 'workflow_dispatch' && trigger.source === 'cloudflare-watchdog' ? 'Cloudflare 补抓' : ({workflow_dispatch:'手动更新',push:'代码发布',local:'本机更新'}[trigger.event]);
  if (triggerLabel) $('run-status').append(document.createTextNode(' · 触发：' + triggerLabel));
  if (trigger.run_url && /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/actions\/runs\/\d+$/.test(trigger.run_url)) {
    $('run-status').append(document.createTextNode(' · '),link('查看运行 ↗',trigger.run_url));
  }
  $('run-status').classList.toggle('warning',outdated || data.status !== 'ok');
  const states = {ok:'读取正常',error:'读取失败',disabled:'未启用'};
  for (const s of data.sources) {
    const row = el('div',undefined,'source-item'); row.append(el('strong',s.name),el('span',states[s.status] || s.status,'source-state ' + s.status),el('p',s.note),el('p',s.message));
    if (s.last_success_at) row.append(el('p','上次成功：' + format(s.last_success_at)));
    if (s.community_url) row.append(link(s.community_name + ' ↗',s.community_url),document.createTextNode(' · '));
    if (s.relay_url) row.append(link(s.relay_name + ' ↗',s.relay_url),document.createTextNode(' · '));
    row.append(link('使用条件 ↗',s.license_url || s.terms_url)); $('sources-list').append(row);
  }
}
async function loadWatchdogStatus() {
  const node = $('watchdog-status');
  if (!HeadlineLocal.isCloudHost(location)) { node.hidden = true; return; }
  try {
    const response = await fetch('/api/watchdog/status',{cache:'no-store',credentials:'omit',signal:AbortSignal.timeout(6000)});
    if (!response.ok) throw new Error();
    const status = await response.json();
    const heartbeatMissing = status.enabled && (!status.last_checked_at || Date.now() - Date.parse(status.last_checked_at) > 135 * 60000);
    node.textContent = '独立定时兜底：' + (heartbeatMissing ? '尚未取得近期检查记录' : status.message || '暂不可用') + (status.last_checked_at ? ' · 上次检查 ' + format(status.last_checked_at) : '') + (status.enabled && status.next_check_at ? ' · 下次检查 ' + format(status.next_check_at) : '');
    node.classList.toggle('warning',!status.enabled || heartbeatMissing || ['credentials','github_unavailable','unavailable','capped'].includes(status.last_result));
  } catch { node.textContent = '独立定时兜底：暂时无法读取状态；新闻更新状态见上方。'; }
}
async function load() {
  initTranslation();
  loadWatchdogStatus();
  try {
    const response = await fetch('./data/news.json',{cache:'no-cache'}); if (!response.ok) throw new Error('Data unavailable');
    data = await response.json(); if (data.schema_version !== 1 || !Array.isArray(data.articles)) throw new Error('Invalid data');
    const select = $('window-select'); select.replaceChildren(option('recent','最近 24 小时'),option('all','最近 72 小时存档'));
    for (const w of [...data.windows].reverse()) if (w.article_ids.length) select.append(option(w.id,`${format(w.start)} — ${format(w.end)}`));
    select.value = 'recent'; select.disabled = false;
    for (const s of data.sources.filter(s=>s.enabled)) $('source-select').append(option(s.id,s.name)); $('source-select').disabled = false;
    select.addEventListener('change',render); $('source-select').addEventListener('change',render);
    renderStatus(); render(); initArchive();
    let retainedCount = retainedArticles().length;
    setInterval(() => {
      const count = retainedArticles().length;
      if (!busy && count !== retainedCount) { retainedCount = count; render(); renderArchive(); }
    },60000);
  } catch { $('run-status').textContent = '新闻数据暂时不可用，请稍后刷新；翻译仍可用于手动粘贴的文字。'; $('board-list').replaceChildren(el('p','暂时无法加载榜单。','empty-state')); }
}
load();
