from copy import deepcopy
from datetime import timedelta
import json

import pytest

from scripts import collect as c
from archive import cloud_ai as ai

NOW = c.dt('2026-10-18T08:07:00+08:00')
SETTINGS = {'retention_days': 30, 'topics_per_window': 15}
SOURCES = [{'id': 'a', 'name': 'A', 'publisher': 'A', 'enabled': True, 'url': 'https://example.org/a'},
           {'id': 'b', 'name': 'B', 'publisher': 'B', 'enabled': True, 'url': 'https://example.org/b'}]
STATES = [{'id': s['id'], 'status': 'ok', 'last_success_at': c.iso(NOW)} for s in SOURCES]
TERM = {'id': c.digest('united states'), 'label': 'United States', 'kind': 'entity'}


def article(id='one', source='a', stamp='2026-10-18T05:00:00+08:00', title='United States announces new climate agreement with Japan'):
    return {'id': id, 'identities': [source + ':' + id], 'source_id': source,
            'publisher': source.upper(), 'title': title, 'url': 'https://example.org/' + id,
            'summary': 'Negotiations in Japan.', 'author': '', 'published_at': c.iso(c.dt(stamp)),
            'first_seen_at': c.iso(NOW), 'window_id': c.window_id(c.dt(stamp)), 'topics': [TERM], 'extracted': True}


def dataset(articles=None, now=NOW, states=None, previous=None):
    return c.build_dataset(articles if articles is not None else [article()], SOURCES, states or STATES, now, SETTINGS, previous)


@pytest.mark.parametrize(('stamp', 'expected'), [
    ('2026-10-18T00:00:00+08:00', '2026-10-18T00:00+08:00'),
    ('2026-10-18T03:59:59+08:00', '2026-10-18T00:00+08:00'),
    ('2026-10-18T04:00:00+08:00', '2026-10-18T04:00+08:00'),
    ('2026-10-17T20:00:00Z', '2026-10-18T04:00+08:00'),
])
def test_window_boundary(stamp, expected):
    assert c.window_id(c.dt(stamp)) == expected


def test_midnight_assigns_previous_day_and_excludes_open_window():
    now = c.dt('2026-10-18T00:05:00+08:00')
    d = dataset([article(stamp='2026-10-17T23:00:00+08:00'), article('open', stamp='2026-10-18T00:01:00+08:00')], now)
    assert d['latest_window_id'] == '2026-10-17T20:00+08:00'
    assert d['days'][0]['topics'] == []
    assert d['days'][1]['topics'][0]['article_count'] == 1
    assert all('open' not in w['article_ids'] for w in d['windows'])


def test_late_article_updates_original_window_not_current():
    d = dataset([article(stamp='2026-10-17T21:00:00+08:00')])
    assert next(w for w in d['windows'] if w['id'] == '2026-10-17T20:00+08:00')['article_ids'] == ['one']
    assert next(w for w in d['windows'] if w['id'] == d['latest_window_id'])['article_ids'] == []


def test_daily_union_counts_articles_once_and_independent_publishers():
    a, b, extra = article(), article('two', 'b'), article('three', 'a', '2026-10-18T01:00:00+08:00')
    a['topics'].append(TERM)
    t = dataset([a, b, extra])['days'][0]['topics'][0]
    assert t['article_count'] == 3
    assert t['source_count'] == 2
    assert t['first_seen_at'] == extra['published_at']
    b['publisher'] = a['publisher']
    assert c.rank_topics([a, b])[0]['source_count'] == 1


def test_retention_cutoff():
    d = dataset([article('old', stamp='2026-09-18T01:00:00+08:00'), article()])
    assert [a['id'] for a in d['articles']] == ['one']
    assert len(d['days']) == 30


def test_canonical_url_and_unsafe_url():
    assert c.canonical_url('https://example.org/story?utm_source=x&b=2&a=1#top') == 'https://example.org/story?a=1&b=2'
    for bad in ['javascript:alert(1)', 'data:text/html,test', 'https://user:secret@example.org/']:
        with pytest.raises(ValueError):
            c.canonical_url(bad)


def test_rss_parse_date_html_and_invalid_entries():
    xml = b'''<rss version="2.0"><channel><title>Test</title><item><title>Japan &amp; US talks</title><link>https://example.org/story?utm_source=x</link><guid>story1</guid><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate><description>&lt;script&gt;bad()&lt;/script&gt;&lt;b&gt;A summary&lt;/b&gt;</description></item><item><title>No date</title></item><item><title>Unsafe</title><link>javascript:alert(1)</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    articles, skipped = c.parse_feed(xml, SOURCES[0], NOW)
    assert skipped == 2
    assert articles[0]['summary'] == 'A summary'
    assert articles[0]['window_id'] == '2026-10-18T08:00+08:00'


def test_atom_uses_published_before_updated():
    xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Feed</title><entry><id>1</id><title>Story</title><link href="https://example.org/story"/><published>2026-10-17T23:00:00+08:00</published><updated>2026-10-18T05:00:00+08:00</updated></entry></feed>'''
    entries, skipped = c.parse_feed(xml, SOURCES[0], NOW)
    assert skipped == 0
    assert entries[0]['window_id'] == '2026-10-17T20:00+08:00'


def test_repeat_guid_url_revision_near_titles_and_cross_source():
    original = article()
    revision = article('changed-guid', title=original['title'] + '!')
    revision['url'] = original['url']
    items = c.merge_articles([original], [revision], NOW - timedelta(days=30))
    assert len(items) == 1 and items[0]['id'] == original['id']
    assert items[0]['published_at'] == original['published_at']
    assert len(items[0]['identities']) == 2
    assert not items[0].get('extracted')
    assert len(c.merge_articles([original], [article('new-url', title=original['title'])], NOW - timedelta(days=30))) == 1
    assert len(c.merge_articles([original], [article('b', source='b')], NOW - timedelta(days=30))) == 2


def test_partial_and_total_failure_preserve_previous_success():
    previous = dataset()
    states = [{'id': 'a', 'status': 'error'}, STATES[1]]
    assert dataset(states=states)['status'] == 'partial'
    all_failed = [{'id': s['id'], 'status': 'error'} for s in SOURCES]
    d = dataset(states=all_failed, previous=previous)
    assert d['status'] == 'error' and d['articles'][0]['id'] == 'one'
    assert d['last_success_at'] == previous['last_success_at']
    assert d['sources'][0]['last_success_at'] == STATES[0]['last_success_at']


def test_retry_and_disabled_sources(monkeypatch):
    calls = []
    def fail(*args):
        calls.append(1)
        raise ValueError('server error')
    monkeypatch.setattr(c, 'request_bytes', fail)
    monkeypatch.setattr(c.time, 'sleep', lambda n: None)
    assert c.fetch_source(SOURCES[0], NOW)[1]['status'] == 'error'
    assert len(calls) == 3
    assert c.fetch_source({'id': 'off', 'enabled': False}, NOW)[1]['status'] == 'disabled'
    assert len(calls) == 3


def test_extractor_merges_aliases_and_ignores_dates():
    pytest.importorskip('spacy')
    pytest.importorskip('yake')
    import spacy
    if not spacy.util.is_package('en_core_web_sm'):
        pytest.skip('Archived NLP model is not installed')
    extractor = c.TopicExtractor(c.read_json(c.ROOT / 'config/aliases.json'))
    a = article(title='Donald Trump meets United Nations officials in Japan')
    a['summary'] = 'Trump discussed sanctions with the UN on Monday.'
    topics = extractor.extract(a)
    labels = [t['label'] for t in topics]
    assert 'Donald Trump' in labels and 'United Nations' in labels
    assert 'Monday' not in labels
    assert len({t['id'] for t in topics}) == len(topics)
    assert extractor.normalize('U.S.') == extractor.normalize('US') == 'United States'
    assert extractor.normalize('the United Nations') == 'United Nations'


def ai_settings():
    return {'enabled': True, 'free_plan_confirmed': True, 'model': '@cf/qwen/qwen3-30b-a3b-fp8',
            'max_titles_per_run': 40, 'max_topics_per_run': 10}


def ai_env(monkeypatch):
    monkeypatch.setenv('CF_ACCOUNT_ID', 'a' * 32)
    monkeypatch.setenv('CF_API_TOKEN', 'test-token')


def test_missing_credentials_never_call_api(monkeypatch, tmp_path):
    monkeypatch.delenv('CF_API_TOKEN', raising=False)
    monkeypatch.setattr(ai, 'cloudflare_json', lambda *a, **k: pytest.fail('Must not call API'))
    d = dataset()
    ai.enrich(d, ai_settings(), tmp_path / 'cache.json', NOW)
    assert d['ai']['status'] == 'disabled'


def test_paid_plan_and_unverified_plan_block_calls(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'cloudflare_json', lambda *a: [{'rate_plan': {'id': 'workers_paid', 'public_name': 'Workers Paid'}, 'state': 'active'}])
    monkeypatch.setattr(ai, 'generate', lambda *a: pytest.fail('Paid plan cannot generate'))
    d = dataset()
    ai.enrich(d, ai_settings(), tmp_path / 'cache.json', NOW)
    assert d['ai']['status'] == 'unavailable'
    settings = ai_settings(); settings['free_plan_confirmed'] = False
    ai.enrich(d, settings, tmp_path / 'cache.json', NOW)
    assert d['ai']['status'] == 'disabled'


def test_free_ai_cache_and_context_references(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *a: None)
    calls = []
    def generate(account, token, model, task, payload):
        calls.append(task)
        if task == 'translation':
            return {'translations': [{'id': 'one', 'text': '美国宣布气候协议'}, {'id': 'invented', 'text': '错误'}]}
        return {'contexts': [{'id': TERM['id'], 'text': '美国宣布新协议。', 'article_ids': ['one']}]}
    monkeypatch.setattr(ai, 'generate', generate)
    path = tmp_path / 'cache.json'
    d = dataset(); ai.enrich(d, ai_settings(), path, NOW)
    assert d['articles'][0]['title_zh'] == '美国宣布气候协议'
    topic = next(w for w in d['windows'] if w['id'] == d['latest_window_id'])['topics'][0]
    assert topic['context_article_ids'] == ['one']
    d = dataset(); ai.enrich(d, ai_settings(), path, NOW)
    assert calls == ['translation', 'context']
    assert d['ai']['status'] == 'ok'


def test_ai_exhaustion_preserves_news(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *a: None)
    def exhausted(*args):
        raise ai.AIUnavailable('免费额度用尽')
    monkeypatch.setattr(ai, 'generate', exhausted)
    d = dataset(); ai.enrich(d, ai_settings(), tmp_path / 'cache.json', NOW)
    assert d['ai']['status'] == 'unavailable' and len(d['articles']) == 1


def test_hallucinated_context_reference_rejected(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *a: None)
    monkeypatch.setattr(ai, 'generate', lambda *a: {'contexts': [{'id': TERM['id'], 'text': 'unsupported', 'article_ids': ['made-up']}]})
    d = dataset(); ai.enrich(d, ai_settings(), tmp_path / 'cache.json', NOW)
    assert all('context_zh' not in t for w in d['windows'] for t in w['topics'])


def test_invalid_feed_and_naive_timestamp_rejected():
    with pytest.raises(ValueError):
        c.parse_feed(b'<html>not a feed</html>', SOURCES[0], NOW)
    with pytest.raises(ValueError):
        c.dt('2026-10-18T08:00:00')


def test_community_links_only_strips_content_and_checks_publisher_domain():
    source = {'id': 'reuters-community', 'name': 'Reuters', 'mode': 'links_only',
              'time_basis': 'feed_publication', 'allowed_link_domains': ['reuters.com']}
    xml = b'''<rss version="2.0"><channel><title>Community</title><item><title>Japan talks</title><link>https://www.reuters.com/world/example/</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate><description>Do not republish this body</description></item><item><title>Wrong publisher</title><link>https://reuters.com.attacker.example/story</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    entries, skipped = c.parse_feed(xml, source, NOW)
    assert len(entries) == 1 and skipped == 1
    assert entries[0]['summary'] == '' and not entries[0]['analysis_allowed']
    assert entries[0]['time_basis'] == 'feed_publication'
    old = article(); old['title_zh'] = '旧译文'
    c.apply_source_policy(old, source)
    assert old['topics'] == [] and 'title_zh' not in old


def test_links_only_never_receive_ai_or_cached_translation(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *args: None)
    monkeypatch.setattr(ai, 'generate', lambda *args: pytest.fail('Link-only articles must not call AI'))
    item = article(); c.apply_source_policy(item, {'mode': 'links_only'})
    data = dataset([item])
    path = tmp_path / 'cache.json'
    key = c.digest(ai_settings()['model'] + ':title:' + item['title'])
    c.write_json(path, {key: {'text': 'A cached translation', 'created_at': c.iso(NOW)}})
    ai.enrich(data, ai_settings(), path, NOW)
    assert 'title_zh' not in data['articles'][0]
    assert all(not w['topics'] for w in data['windows'])


def test_stale_community_feed_is_not_reported_as_healthy(monkeypatch):
    xml = b'''<rss version="2.0"><channel><title>Community</title><item><title>Old story</title><link>https://example.org/story</link><pubDate>Wed, 14 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    monkeypatch.setattr(c, 'request_bytes', lambda *args: xml)
    entries, status = c.fetch_source({**SOURCES[0], 'max_feed_age_hours': 36}, NOW)
    assert entries == [] and status['status'] == 'error'
    assert '36' in status['message']


def test_read_only_display_and_topic_ai_controls_are_independent():
    item = article()
    c.apply_source_policy(item, {'mode': 'read_only', 'topics_enabled': True, 'ai_enabled': False})
    assert item['summary'] and item['topics']
    assert item['analysis_allowed'] and not item['ai_allowed']
    item['title_zh'] = 'old translation'
    c.apply_source_policy(item, {'mode': 'read_only'})
    assert item['summary'] and not item['topics'] and 'title_zh' not in item
    assert 'extraction_version' not in item


def test_original_author_gate_rejects_agencies_and_unknown_authors():
    source = {'allowed_authors': ['VOA Reporter'], 'exclude_credit_patterns': ['Reuters', 'Associated Press', 'AFP']}
    item = article(); item['author'] = 'VOA Reporter'
    assert c.author_allowed(item, source)
    item['summary'] = 'Reporting by Reuters'
    assert not c.author_allowed(item, source)
    item['summary'] = ''; item['author'] = 'Unknown Reporter'
    assert not c.author_allowed(item, source)


def test_mixed_topic_never_leaks_read_only_news_to_ai(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *a: None)
    read_only, allowed = article(), article('two', 'b')
    read_only['ai_allowed'] = False
    calls = []
    def generate(account, token, model, task, payload):
        calls.append(task)
        if task == 'translation':
            assert [a['id'] for a in payload] == ['two']
            return {'translations': [{'id': 'two', 'text': '测试'}]}
        assert all([a['id'] for a in t['articles']] == ['two'] for t in payload)
        return {'contexts': [{'id': TERM['id'], 'text': '不应保留', 'article_ids': ['one']}]}
    monkeypatch.setattr(ai, 'generate', generate)
    d = dataset([read_only, allowed]); ai.enrich(d, ai_settings(), tmp_path / 'cache.json', NOW)
    assert calls == ['translation', 'context']
    assert 'title_zh' not in d['articles'][0]
    assert all('context_zh' not in t for w in d['windows'] for t in w['topics'])


def test_topic_only_source_never_calls_ai_even_for_context(monkeypatch, tmp_path):
    ai_env(monkeypatch)
    monkeypatch.setattr(ai, 'verify_free_account', lambda *a: None)
    monkeypatch.setattr(ai, 'generate', lambda *a: pytest.fail('Topic-only content cannot enter AI'))
    item = article(); item['ai_allowed'] = False
    ai.enrich(dataset([item]), ai_settings(), tmp_path / 'cache.json', NOW)


def test_revised_rss_content_invalidates_extraction_version():
    old = article(); old['extraction_version'] = 'current-model'
    updated = deepcopy(old); updated['summary'] = 'A revised report about Korea.'
    merged = c.merge_articles([old], [updated], NOW - timedelta(days=30))
    assert len(merged) == 1 and merged[0]['id'] == old['id']
    assert 'extraction_version' not in merged[0] and merged[0]['topics'] == []


def test_current_collection_disables_nlp_cloud_and_published_translations(monkeypatch, tmp_path):
    root = tmp_path
    (root / 'config').mkdir()
    c.write_json(root / 'config/sources.json', SOURCES)
    c.write_json(root / 'config/settings.json', {**SETTINGS, 'topics_enabled': False})
    c.write_json(root / 'config/aliases.json', {})
    old = article('old'); old['title_zh'] = '旧云端译文'
    c.write_json(root / 'state/news.json', {'articles': [old]})
    monkeypatch.setattr(c, 'ROOT', root)
    monkeypatch.setattr(c, 'TopicExtractor', lambda *a: pytest.fail('Archived NLP must not run'))
    monkeypatch.setattr(c, 'fetch_source', lambda source, now: ([article(source['id'], source['id'])], {'id': source['id'], 'status': 'ok'}))
    monkeypatch.setenv('CF_API_TOKEN', 'test-secret-never-used')
    d = c.run(NOW, root / 'public/data/news.json', root / 'state/news.json')
    assert all(a['topics'] == [] and 'title_zh' not in a for a in d['articles'])
    assert all(w['topics'] == [] for w in d['windows'])
    assert all(day['topics'] == [] for day in d['days'])
    assert d['ai']['status'] == 'local_only'
    assert 'test-secret' not in (root / 'public/data/news.json').read_text()


def test_feed_rank_follows_feed_order_and_updates_on_repeat():
    body = b'<rss version="2.0"><channel><title>Feed</title><item><title>First</title><guid>1</guid><link>https://example.org/one</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate></item><item><title>Second</title><guid>2</guid><link>https://example.org/two</link><pubDate>Sat, 17 Oct 2026 23:00:00 GMT</pubDate></item></channel></rss>'
    items, _ = c.parse_feed(body, SOURCES[0], NOW)
    assert [a['feed_rank'] for a in items] == [1, 2]
    old = deepcopy(items[0]);old['feed_rank'] = 10
    updated = c.merge_articles([old], items, NOW-timedelta(days=30))
    assert next(a for a in updated if a['id'] == old['id'])['feed_rank'] == 1
