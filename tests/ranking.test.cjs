const test = require('node:test');
const assert = require('node:assert/strict');
const {buildBoard,rankSources,sourceHeadlines} = require('../public/ranking.js');
const now = Date.parse('2026-10-18T04:00:00Z');
const article = (id,publisher='BBC',source_id='bbc',rank=1,hours=1,title=id) => ({id,publisher,source_id,feed_rank:rank,title,published_at:new Date(now-hours*3600000).toISOString(),rank_observed_at:new Date(now).toISOString()});
test('source cards cap mixed historical windows at ten without truncating archive input',()=> {
 const articles=Array.from({length:36},(_,i)=>article(String(i),'BBC','bbc',i%10+1,1+i/2));
 const ranked=rankSources(articles,now);
 assert.deepEqual(sourceHeadlines(articles,now),ranked.slice(0,10));
 assert.equal(articles.length,36);
 assert.equal(sourceHeadlines(articles.slice(0,3),now).length,3);
 assert.equal(sourceHeadlines([],now).length,0);
});
test('same publisher channels never inflate board score',()=> {
 const one=article('a','BBC','bbc-world',1,1,'Same headline');
 const duplicate=article('b','BBC','bbc-business',1,1,'Same headline!');
 const baseline=buildBoard([one],now)[0];
 const grouped=buildBoard([one,duplicate],now)[0];
 assert.equal(grouped.publisher_count,1); assert.equal(grouped.score,baseline.score); assert.equal(grouped.reports.length,2);
 const third=article('c','NPR','npr',1,1,'Same headline');
 assert.equal(buildBoard([one,duplicate,third],now)[0].publisher_count,2);
});
test('fresh source head ranks before old item and board is bounded',()=> {
 const articles=Array.from({length:20},(_,i)=>article(String(i),'BBC','bbc',i+1));
 articles.push(article('old','NPR','npr',1,80));
 assert.equal(rankSources([articles.at(-1),articles[0]],now)[0].id,'0');
 assert.equal(buildBoard(articles,now,3).length,3);
 assert.equal(buildBoard(articles,now)[0].article.id,'0');
 assert.ok(buildBoard(articles,now).every(g=>g.positions.every(p=>p.position<=5)));
});
test('unrelated titles are retained, no semantic or keyword clustering',()=> {
 const a=article('a','BBC','bbc',1,1,'Trump signs a new deal');
 const b=article('b','NPR','npr',1,1,'Trump rejects a new deal');
 assert.equal(buildBoard([a,b],now).length,2);
});
