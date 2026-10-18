/* Feed-order recommendations, without NLP or invented audience metrics. */
(function (root) {
  'use strict';
  const titleKey = a => a.title.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  function rankSources(articles, now) {
    const latest = new Map();
    for (const a of articles) latest.set(a.source_id, Math.max(latest.get(a.source_id) || 0, Date.parse(a.rank_observed_at || a.published_at)));
    return [...articles].sort((a, b) => {
      const score = a => {
        const age = Math.max(0, (now - Date.parse(a.published_at)) / 3600000);
        const rank = Number.isInteger(a.feed_rank) && a.feed_rank > 0 ? a.feed_rank : 100;
        const observed = Date.parse(a.rank_observed_at || a.published_at);
        const current = observed >= latest.get(a.source_id) - 60000;
        return (current ? 1 : .35) * Math.pow(.5, age / 24) / (60 + rank);
      };
      return score(b) - score(a) || b.published_at.localeCompare(a.published_at) || a.id.localeCompare(b.id);
    });
  }
  function buildBoard(articles, now, limit = 12) {
    const bySource = new Map();
    for (const a of articles) { if (!bySource.has(a.source_id)) bySource.set(a.source_id, []); bySource.get(a.source_id).push(a); }
    const groups = new Map();
    for (const list of bySource.values()) {
      rankSources(list, now).slice(0, 5).forEach((article, index) => {
        const key = titleKey(article) || article.id;
        if (!groups.has(key)) groups.set(key, {article, reports: [], votes: new Map(), positions: []});
        const group = groups.get(key);
        group.reports.push(article); group.positions.push({source_id: article.source_id, position: index + 1});
        const age = Math.max(0, (now - Date.parse(article.published_at)) / 3600000);
        const vote = Math.pow(.5, age / 24) / (60 + index + 1);
        group.votes.set(article.publisher, Math.max(group.votes.get(article.publisher) || 0, vote));
        if (article.published_at > group.article.published_at) group.article = article;
      });
    }
    return [...groups.values()].map(g => ({article: g.article, reports: g.reports, positions: g.positions,
      publisher_count: g.votes.size, score: [...g.votes.values()].reduce((a, b) => a + b, 0)}))
      .sort((a, b) => b.score - a.score || b.article.published_at.localeCompare(a.article.published_at) || a.article.id.localeCompare(b.article.id)).slice(0, limit);
  }
  const api = {rankSources, buildBoard, titleKey};
  if (typeof module !== 'undefined') module.exports = api;
  root.HeadlineRanking = api;
})(globalThis);
