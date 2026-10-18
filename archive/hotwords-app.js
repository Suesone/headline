'use strict';
const $ = (id) => document.getElementById(id);
let data, activeTopic = null;
function sourceTileClass(source) {
  if (source.id === 'all') return 'tile-all';
  if (source.publisher === 'NPR') return 'tile-npr';
  if (source.publisher === 'CNBC') return 'tile-cnbc';
  if (source.publisher === 'VOA') return 'tile-voa';
  if (source.id === 'reuters-community') return 'tile-reuters';
  if (source.id.startsWith('bbc')) return 'tile-bbc';
  if (source.id.startsWith('guardian')) return 'tile-guardian';
  return 'tile-generic';
}
function sourceInitials(source) {
  return ({all: '榜', 'reuters-community': 'R'})[source.id] || source.publisher;
}
function renderShortcuts() {
  const list = $('source-shortcuts'); list.replaceChildren();
  const seen = new Set();
  const sources = [{id: 'all', name: '全部来源', publisher: 'all', enabled: true}, ...data.sources];
  for (const source of sources) {
    if (seen.has(source.publisher)) continue; seen.add(source.publisher);
    const button = el('button', undefined, 'source-shortcut' + (source.id === $('source-select').value ? ' active' : ''));
    button.type = 'button';
    button.setAttribute('aria-pressed', String(source.id === $('source-select').value));
    button.setAttribute('aria-label', source.enabled ? source.name : source.name + ' 未启用，查看原因');
    button.append(el('span', sourceInitials(source), 'source-tile ' + sourceTileClass(source)), el('span', source.id === 'all' ? source.name : source.publisher), el('span', source.enabled ? (source.id === 'all' ? '新闻总览' : source.ai_enabled ? '热词 · 可选 AI' : source.topics_enabled ? '阅读 · 热词' : '英文阅读') : '未启用 · 查看原因', 'shortcut-subtitle'));
    if (!source.enabled) button.title = source.note;
    button.addEventListener('click', () => {
      if (!source.enabled) { $('source-details').open = true; $('source-details').scrollIntoView({behavior:'smooth', block:'start'}); return; }
      $('source-select').value = source.id; renderNews();
    });
    list.append(button);
  }
}
const format = (stamp, options = {}) => new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', ...options}).format(new Date(stamp));
const el = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
function safeUrl(value) { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; } catch { return null; } }
function link(text, url, cls) { const a = el('a', text, cls); const safe = safeUrl(url); if (safe) { a.href = safe; a.target = '_blank'; a.rel = 'noopener noreferrer'; } return a; }
function option(value, label) { const o = el('option', label); o.value = value; return o; }
function selectedWindow() { return data.windows.find(w => w.id === $('window-select').value); }
function topicPanel(topic, rank, daily = false) {
  const wrap = el('div');
  const button = el('button', undefined, 'topic-row' + (activeTopic?.id === topic.id ? ' active' : ''));
  button.type = 'button'; button.setAttribute('aria-expanded', 'false');
  const title = el('span', undefined, 'topic-title');
  title.append(el('span', String(rank + 1).padStart(2, '0'), 'topic-rank'), el('span', topic.label, 'topic-label'));
  button.append(title, el('span', `${topic.article_count} 篇报道\n${topic.source_count} 个来源`, 'topic-number'));
  const details = el('div', undefined, 'topic-context'); details.hidden = true;
  if (topic.context_zh) { details.append(el('p', topic.context_zh), el('p', 'AI 语境说明 · 请核对原文', 'context-note')); }
  else details.append(el('p', '以下是这个话题出现的新闻线索。' + (topic.kind === 'phrase' ? '事件短语由统计工具提取。' : '')));
  const related = topic.article_ids.map(id => data.articles.find(a => a.id === id)).filter(Boolean);
  for (const article of related.slice(0, 5)) details.append(link(article.title, article.url));
  if (daily) details.append(el('p', `首次出现：${format(topic.first_seen_at)}`, 'context-note'));
  button.addEventListener('click', () => {
    const opened = !details.hidden; details.hidden = opened; button.setAttribute('aria-expanded', String(!opened));
    activeTopic = opened ? null : {...topic, daily}; renderNews();
    for (const node of document.querySelectorAll('.topic-row.active')) node.classList.remove('active');
    button.classList.toggle('active', !opened);
  });
  wrap.append(button, details); return wrap;
}
function renderTopics() {
  const current = selectedWindow() || data.windows.find(w => w.id === data.latest_window_id);
  const eligible = current ? data.articles.filter(a => current.article_ids.includes(a.id) && a.analysis_allowed !== false).length : 0;
  $('realtime-caption').textContent = current ? `${format(current.start)} — ${format(current.end)} · ${eligible} 篇报道参与统计 · 点击话题查看报道` : '人物、地点与事件，点击展开相关报道。';
  const realtime = $('window-topics'); realtime.replaceChildren();
  if (!current) realtime.append(el('p', '选择一个四小时时段查看话题。', 'panel-description'));
  else if (!current.topics.length) realtime.append(el('p', current.article_ids.length && !eligible ? '本时段的报道来自仅供阅读的来源，未纳入热词。可切换较早时段查看。' : '本时段暂无可提炼的话题。', 'panel-description'));
  else current.topics.forEach((topic, i) => realtime.append(topicPanel(topic, i)));
  const day = data.days.find(d => d.date === $('day-select').value);
  const daily = $('day-topics'); daily.replaceChildren();
  if (!day?.topics.length) daily.append(el('p', '当天尚无入选话题，可切换日期查看。', 'panel-description'));
  else day.topics.forEach((topic, i) => daily.append(topicPanel(topic, i, true)));
}
function filterTopic(topic) {
  activeTopic = {...topic, daily: false}; renderNews();
  $('active-topic').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}
function renderNews() {
  renderShortcuts();
  const current = selectedWindow();
  let articles;
  if (activeTopic?.daily) articles = data.articles.filter(a => activeTopic.article_ids.includes(a.id));
  else if (current) { const byId = new Map(data.articles.map(a => [a.id, a])); articles = current.article_ids.map(id => byId.get(id)).filter(Boolean); }
  else articles = data.articles.filter(a => data.windows.some(w => w.article_ids.includes(a.id)));
  const source = $('source-select').value;
  if (source !== 'all') articles = articles.filter(a => a.source_id === source);
  if (activeTopic) articles = articles.filter(a => activeTopic.article_ids.includes(a.id));
  const list = $('news-list'); list.replaceChildren();
  $('article-count').textContent = `${articles.length} 篇报道`;
  $('news-heading').textContent = current ? '时段新闻榜' : '最近新闻榜';
  $('period-caption').textContent = activeTopic?.daily ? `当日话题 · ${$('day-select').value} · 北京时间` : current ? `${format(current.start)} — ${format(current.end)} · 北京时间 · 按来源提供的日期归档` : '最近 30 天已完成时段 · 最新时段无新增时自动展示历史记录';
  const topicBanner = $('active-topic'); topicBanner.replaceChildren(); topicBanner.hidden = !activeTopic;
  if (activeTopic) { topicBanner.append(el('span', `正在阅读：${activeTopic.label}`)); const clear = el('button', '清除筛选 ×'); clear.type = 'button'; clear.addEventListener('click', () => { activeTopic = null; renderNews(); renderTopics(); }); topicBanner.append(clear); }
  if (!articles.length) {
    const empty = el('div', undefined, 'empty-state');
    empty.append(el('div', activeTopic || source !== 'all' ? '当前筛选下没有报道，试试清除话题或切换来源。' : '这个四小时时段暂无新报道。新闻源发布频率不同，可以先翻阅最近的记录。'));
    if (!activeTopic && source === 'all') { const recent = el('button', '查看历史新闻 →'); recent.type = 'button'; recent.addEventListener('click', () => { $('window-select').value = 'all'; renderNews(); renderTopics(); }); empty.append(recent); }
    list.append(empty);
  }
  const bilingual = $('translation-toggle').checked;
  const groups = data.sources.filter(s => s.enabled && (source === 'all' || s.id === source)).map(s => ({source: s, articles: articles.filter(a => a.source_id === s.id)}));
  for (const group of groups) {
    const card = el('section', undefined, 'source-card');
    card.setAttribute('aria-label', group.source.name + ' 新闻榜单');
    const header = el('div', undefined, 'source-card-header');
    header.append(el('span', sourceInitials(group.source), 'source-card-icon ' + sourceTileClass(group.source)), el('h3', group.source.name), el('span', `${group.articles.length} 篇`, 'source-card-count'));
    const cardList = el('div', undefined, 'source-card-list');
    if (!group.articles.length) cardList.append(el('p', '当前筛选下暂无报道', 'panel-description'));
    card.append(header, cardList);
    group.articles.forEach((article, index) => {
      const node = $('article-template').content.cloneNode(true);
      const q = s => node.querySelector(s);
      const sourceInfo = data.sources.find(s => s.id === article.source_id);
      q('.article-index').textContent = String(index + 1);
      q('.article-time').textContent = (article.time_basis === 'feed_publication' ? '订阅日期 ' : '') + format(article.published_at);
      q('.article-topic-count').textContent = article.analysis_allowed === false ? '仅供阅读' : `${article.topics.length} 个关联话题`;
      if (article.analysis_allowed === false) q('.article-details summary').textContent = '来源与链接';
      q('.article-link').textContent = article.title;
      const url = safeUrl(article.url);
      if (url) { q('.article-link').href = url; q('.original-link').href = url; }
      q('.article-summary').textContent = article.summary;
      if (!article.summary) q('.article-summary').hidden = true;
      if (bilingual) { q('.article-translation').hidden = false; q('.article-translation').textContent = article.ai_allowed === false ? '此来源未启用 AI 翻译' : article.title_zh ? article.title_zh + ' · AI 译文' : '本条暂未生成译文'; }
      for (const topic of article.topics.slice(0, 3)) {
        const button = el('button', topic.label, 'article-tag'); button.type = 'button';
        button.addEventListener('click', () => {
          const pool = current ? data.articles.filter(a => current.article_ids.includes(a.id)) : data.articles;
          filterTopic({...topic, article_ids: pool.filter(a => a.topics.some(t => t.id === topic.id)).map(a => a.id)});
        }); q('.article-tags').append(button);
      }
      const credit = q('.article-credit');
      credit.append(el('span', (article.author ? `${article.author} · ` : '') + (sourceInfo?.license || '原文版权归来源所有')));
      if (sourceInfo?.license_url) credit.append(document.createTextNode(' · '), link('许可', sourceInfo.license_url));
      cardList.append(node);
    });
    const footer = el('div', undefined, 'source-card-footer');
    footer.append(el('span', group.source.relay_name ? `${group.source.relay_name} 社区 RSS · 按订阅日期排列` : group.source.community_name ? '社区目录收录 · 官方 RSS' : '官方 RSS · 英文报道'), link(group.source.publisher === 'BBC' ? 'BBC News ↗' : '来源网站 ↗', group.source.homepage));
    card.append(footer); list.append(card);
  }
}
function renderSources() {
  const list = $('sources-list'); list.replaceChildren();
  const states = {ok: '读取正常', error: '读取失败', disabled: '未启用'};
  for (const source of data.sources) {
    const row = el('div', undefined, 'source-item');
    row.append(el('strong', source.name), el('span', states[source.status] || source.status, 'source-state ' + source.status));
    row.append(el('p', source.message || source.note));
    if (source.status === 'ok' && source.note) row.append(el('p', source.note));
    if (source.last_success_at) row.append(el('p', `上次成功：${format(source.last_success_at)}`));
    if (source.enabled) row.append(el('p', `热词：${source.topics_enabled ? '参与' : '不参与'} · AI：${source.ai_enabled ? '可选（需配置免费密钥）' : '不参与'}`));
    if (source.community_url) row.append(link(source.community_name + ' ↗', source.community_url), document.createTextNode(' · '));
    row.append(link('来源网站 ↗', source.homepage), link(source.relay_name ? '社区项目 ↗' : '使用条件 ↗', source.terms_url)); list.append(row);
  }
  $('ai-status').textContent = `AI 状态：${data.ai.message}`;
}
async function load() {
  try {
    const response = await fetch('./data/news.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error('Data unavailable');
    data = await response.json();
    if (data.schema_version !== 1 || !Array.isArray(data.articles)) throw new Error('Invalid data');
    const outdated = Date.now() - Date.parse(data.generated_at) > 6 * 3600000;
    const ok = data.sources.filter(s => s.status === 'ok').length;
    $('run-status').classList.toggle('warning', data.status !== 'ok' || outdated);
    const last = data.last_success_at ? ` · 上次成功 ${format(data.last_success_at)}` : '';
    $('run-status').textContent = data.status === 'error' ? `本次读取失败，正在保留已有新闻${last}` : `${outdated ? '更新可能已延迟 · ' : ''}${ok} 个来源已更新 · 实际更新时间 ${format(data.generated_at)}${data.status === 'partial' ? ' · 部分来源读取失败' : ''}`;
    const windowSelect = $('window-select'); windowSelect.replaceChildren();
    windowSelect.append(option('all', '最近所有时段'));
    for (const w of [...data.windows].reverse()) if (w.article_ids.length || w.id === data.latest_window_id) windowSelect.append(option(w.id, `${format(w.start)} — ${format(w.end, {month: undefined, day: undefined})} · ${w.article_ids.length} 篇`));
    const latest = data.windows.find(w => w.id === data.latest_window_id);
    windowSelect.value = latest?.article_ids.length ? data.latest_window_id : 'all'; windowSelect.disabled = false;
    const sourceSelect = $('source-select');
    for (const s of data.sources.filter(s => s.enabled)) sourceSelect.append(option(s.id, s.name)); sourceSelect.disabled = false;
    const daySelect = $('day-select'); daySelect.replaceChildren();
    for (const [i, day] of data.days.entries()) daySelect.append(option(day.date, `${i === 0 ? '今天' : i === 1 ? '昨天' : day.date.slice(5)} · ${day.topics.length} 词`)); daySelect.disabled = false;
    try { $('translation-toggle').checked = localStorage.getItem('headline-bilingual') === 'true'; } catch {}
    windowSelect.addEventListener('change', () => { activeTopic = null; renderNews(); renderTopics(); });
    sourceSelect.addEventListener('change', renderNews);
    daySelect.addEventListener('change', () => { activeTopic = null; renderNews(); renderTopics(); });
    $('translation-toggle').addEventListener('change', () => { try { localStorage.setItem('headline-bilingual', String($('translation-toggle').checked)); } catch {} renderNews(); });
    renderNews(); renderTopics(); renderSources();
  } catch {
    $('run-status').textContent = '暂时无法读取新闻数据，请稍后刷新。'; $('run-status').classList.add('warning');
    $('news-list').replaceChildren(el('div', '新闻数据尚未发布或网络暂不可用。请稍后刷新页面。', 'empty-state'));
  }
}
$('dictionary-form').addEventListener('submit', event => {
  event.preventDefault(); const word = $('dictionary-word').value.trim(); if (!word) return;
  $('dictionary-links').replaceChildren(link('Cambridge ↗', 'https://dictionary.cambridge.org/dictionary/english/' + encodeURIComponent(word)), link('Merriam-Webster ↗', 'https://www.merriam-webster.com/dictionary/' + encodeURIComponent(word)));
});
load();
