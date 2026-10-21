from copy import deepcopy
from datetime import timedelta
import json

import pytest

from scripts import collect as c

NOW = c.dt('2026-10-18T08:07:00+08:00')
SETTINGS = {'retention_days': 3}
SOURCES = [{'id': 'a', 'name': 'A', 'publisher': 'A', 'enabled': True, 'url': 'https://example.org/a'},
           {'id': 'b', 'name': 'B', 'publisher': 'B', 'enabled': True, 'url': 'https://example.org/b'}]
STATES = [{'id': s['id'], 'status': 'ok', 'last_success_at': c.iso(NOW)} for s in SOURCES]
TERM = {'id': c.digest('united states'), 'label': 'United States', 'kind': 'entity'}


def article(id='one', source='a', stamp='2026-10-18T07:00:00+08:00', title='United States announces new climate agreement with Japan'):
    return {'id': id, 'identities': [source + ':' + id], 'source_id': source,
            'publisher': source.upper(), 'title': title, 'url': 'https://example.org/' + id,
            'summary': 'Negotiations in Japan.', 'author': '', 'published_at': c.iso(c.dt(stamp)),
            'first_seen_at': c.iso(NOW), 'window_id': c.window_id(c.dt(stamp)), 'topics': [TERM], 'extracted': True}


def dataset(articles=None, now=NOW, states=None, previous=None):
    return c.build_dataset(articles if articles is not None else [article()], SOURCES, states or STATES, now, SETTINGS, previous)


@pytest.mark.parametrize(('stamp', 'expected'), [
    ('2026-10-18T00:00:00+08:00', '2026-10-18T00:00+08:00'),
    ('2026-10-18T01:59:59+08:00', '2026-10-18T00:00+08:00'),
    ('2026-10-18T02:00:00+08:00', '2026-10-18T02:00+08:00'),
    ('2026-10-18T03:59:59+08:00', '2026-10-18T02:00+08:00'),
    ('2026-10-18T04:00:00+08:00', '2026-10-18T04:00+08:00'),
    ('2026-10-17T20:00:00Z', '2026-10-18T04:00+08:00'),
])
def test_window_boundary(stamp, expected):
    assert c.window_id(c.dt(stamp)) == expected


def test_midnight_assigns_previous_day_and_excludes_open_window():
    now = c.dt('2026-10-18T00:05:00+08:00')
    d = dataset([article(stamp='2026-10-17T23:00:00+08:00'), article('open', stamp='2026-10-18T00:01:00+08:00')], now)
    assert d['latest_window_id'] == '2026-10-17T22:00+08:00'
    assert d['days'][0]['date'] == '2026-10-18'
    assert d['days'][1]['date'] == '2026-10-17'
    assert all('open' not in w['article_ids'] for w in d['windows'])


def test_late_article_updates_original_window_not_current():
    d = dataset([article(stamp='2026-10-17T21:00:00+08:00')])
    assert next(w for w in d['windows'] if w['id'] == '2026-10-17T20:00+08:00')['article_ids'] == ['one']
    assert next(w for w in d['windows'] if w['id'] == d['latest_window_id'])['article_ids'] == []



def test_retention_cutoff():
    d = dataset([article('old', stamp='2026-09-18T01:00:00+08:00'), article()])
    assert [a['id'] for a in d['articles']] == ['one']
    assert len(d['days']) == 1


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
    assert entries[0]['window_id'] == '2026-10-17T22:00+08:00'


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
    assert entries[0]['summary'] == '' and 'topics' not in entries[0]
    assert entries[0]['time_basis'] == 'feed_publication'
    old = article(); old['title_zh'] = '旧译文'
    c.apply_source_policy(old, source)
    assert 'topics' not in old and 'title_zh' not in old



def test_stale_community_feed_is_not_reported_as_healthy(monkeypatch):
    xml = b'''<rss version="2.0"><channel><title>Community</title><item><title>Old story</title><link>https://example.org/story</link><pubDate>Wed, 14 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    monkeypatch.setattr(c, 'request_bytes', lambda *args: xml)
    entries, status = c.fetch_source({**SOURCES[0], 'max_feed_age_hours': 36}, NOW)
    assert entries == [] and status['status'] == 'error'
    assert '36' in status['message']



def test_original_author_gate_rejects_agencies_and_unknown_authors():
    source = {'allowed_authors': ['VOA Reporter'], 'exclude_credit_patterns': ['Reuters', 'Associated Press', 'AFP']}
    item = article(); item['author'] = 'VOA Reporter'
    assert c.author_allowed(item, source)
    item['summary'] = 'Reporting by Reuters'
    assert not c.author_allowed(item, source)
    item['summary'] = ''; item['author'] = 'Unknown Reporter'
    assert not c.author_allowed(item, source)



def test_revised_rss_content_preserves_id_and_strips_legacy_fields():
    old = article(); old['extraction_version'] = 'current-model'
    updated = deepcopy(old); updated['summary'] = 'A revised report about Korea.'
    merged = c.merge_articles([old], [updated], NOW - timedelta(days=30))
    assert len(merged) == 1 and merged[0]['id'] == old['id']
    c.apply_source_policy(merged[0], SOURCES[0])
    assert merged[0]['summary'] == updated['summary']
    assert 'extraction_version' not in merged[0] and 'topics' not in merged[0]


def test_current_collection_disables_nlp_cloud_and_published_translations(monkeypatch, tmp_path):
    root = tmp_path
    (root / 'config').mkdir()
    c.write_json(root / 'config/sources.json', SOURCES)
    c.write_json(root / 'config/settings.json', {**SETTINGS, 'topics_enabled': False})
    c.write_json(root / 'config/aliases.json', {})
    old = article('old'); old['title_zh'] = '旧云端译文'
    c.write_json(root / 'state/news.json', {'articles': [old]})
    monkeypatch.setattr(c, 'ROOT', root)
    monkeypatch.setattr(c, 'fetch_source', lambda source, now: ([article(source['id'], source['id'])], {'id': source['id'], 'status': 'ok'}))
    monkeypatch.setenv('CF_API_TOKEN', 'test-secret-never-used')
    d = c.run(NOW, root / 'public/data/news.json', root / 'state/news.json')
    assert all('topics' not in a and 'title_zh' not in a for a in d['articles'])
    assert all('topics' not in w for w in d['windows'])
    assert all('topics' not in day for day in d['days'])
    assert d['ai']['status'] == 'on_demand'
    receipt = c.read_json(root / 'public/data/status.json')
    assert receipt['generated_at'] == d['generated_at'] and receipt['status'] == d['status']
    assert 'articles' not in receipt and len(json.dumps(receipt)) < 32000
    assert all('title' not in source for source in receipt['sources'])
    assert 'test-secret' not in (root / 'public/data/news.json').read_text()


def test_feed_rank_follows_feed_order_and_updates_on_repeat():
    body = b'<rss version="2.0"><channel><title>Feed</title><item><title>First</title><guid>1</guid><link>https://example.org/one</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate></item><item><title>Second</title><guid>2</guid><link>https://example.org/two</link><pubDate>Sat, 17 Oct 2026 23:00:00 GMT</pubDate></item></channel></rss>'
    items, _ = c.parse_feed(body, SOURCES[0], NOW)
    assert [a['feed_rank'] for a in items] == [1, 2]
    old = deepcopy(items[0]);old['feed_rank'] = 10
    updated = c.merge_articles([old], items, NOW-timedelta(days=30))
    assert next(a for a in updated if a['id'] == old['id'])['feed_rank'] == 1


def test_retained_history_is_rebucketed_without_duplicate_articles():
    old = article(stamp='2026-10-18T03:30:00+08:00')
    old['window_id'] = '2026-10-18T00:00+08:00'  # Previous four-hour cadence.
    d = dataset([old])
    window = next(w for w in d['windows'] if w['id'] == '2026-10-18T02:00+08:00')
    assert window['article_ids'] == ['one']
    assert sum('one' in w['article_ids'] for w in d['windows']) == 1
    assert all(c.dt(w['end']) - c.dt(w['start']) == timedelta(hours=2) for w in d['windows'])


def test_google_aggregation_rejects_other_publishers_and_preserves_attribution():
    xml = b'''<rss version="2.0"><channel><title>Search</title>
    <item><title>Japan holds talks - NHK</title><link>https://news.google.com/rss/articles/one</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate><source url="https://www3.nhk.or.jp">NHK</source></item>
    <item><title>NHK documentary - Other</title><link>https://news.google.com/rss/articles/two</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate><source url="https://evil.nhk.or.jp.attacker.test">Other</source></item>
    </channel></rss>'''
    source = {**SOURCES[0], 'allowed_link_domains': ['news.google.com'],
              'entry_source_domains': ['nhk.or.jp'], 'mode': 'links_only', 'time_basis': 'feed_publication'}
    items, skipped = c.parse_feed(xml, source, NOW)
    assert len(items) == 1 and skipped == 1
    assert items[0]['title'] == 'Japan holds talks' and items[0]['summary'] == ''
    c.apply_source_policy(items[0], SOURCES[0])
    assert items[0]['time_basis'] == 'feed_publication'


def test_failed_primary_uses_configured_backup_without_claiming_official_success(monkeypatch):
    source = {**SOURCES[0], 'fallbacks': [{'url': 'https://backup.example/rss',
               'relay_name': 'Google News 聚合', 'relay_url': 'https://news.google.com/'}]}
    calls = []
    def fetch(url):
        calls.append(url)
        if url == source['url']:
            raise ValueError('primary unavailable')
        return b'feed'
    monkeypatch.setattr(c, 'request_bytes', fetch)
    monkeypatch.setattr(c, 'parse_feed', lambda *a: ([article()], 0))
    items, state = c.fetch_source(source, NOW)
    assert calls == [source['url'], 'https://backup.example/rss']
    assert state['status'] == 'ok' and state['using_fallback'] is True
    assert state['relay_name'] == 'Google News 聚合' and items


@pytest.mark.parametrize('configured,expected', [(None, 10), (100, 10), (7, 7)])
def test_feed_limit_counts_valid_unique_articles_only(configured, expected):
    source = {**SOURCES[0]}
    if configured is not None:
        source['max_items'] = configured
    def item(n):
        return f'<item><title>Headline {n}</title><guid>{n}</guid><link>https://example.org/story/{n}</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate></item>'
    entries = '<item><title>No date</title></item>' + item(0) + item(0) + ''.join(item(n) for n in range(1, 30))
    xml = ('<rss version="2.0"><channel><title>Test</title>' + entries + '</channel></rss>').encode()
    items, skipped = c.parse_feed(xml, source, NOW)
    assert len(items) == expected
    assert skipped == 2
    assert len({a['url'] for a in items}) == expected
    assert items[-1]['title'] == f'Headline {expected - 1}'


def test_rolling_72_hour_cutoff_and_current_window_archive():
    before = c.iso(NOW - timedelta(hours=72, seconds=1))
    exact = c.iso(NOW - timedelta(hours=72))
    d = dataset([article('expired', stamp=before), article('edge', stamp=exact),
                 article('open', stamp=c.iso(NOW-timedelta(minutes=1)))])
    assert {a['id'] for a in d['articles']} == {'edge', 'open'}
    assert all('open' not in w['article_ids'] for w in d['windows'])
    assert 'edge' in {id for w in d['windows'] for id in w['article_ids']}
    assert d['retention_days'] == 3


def test_source_window_quota_survives_repeat_and_late_arrivals():
    old = [article(str(i), title=f'Distinct story number {i}') for i in range(9)]
    new = [article(str(i), title=f'Distinct story number {i}') for i in range(9, 20)]
    for item in new:
        item['first_seen_at'] = c.iso(NOW+timedelta(minutes=1))
    others = [article('other', source='b'), article('past', stamp='2026-10-18T03:00:00+08:00')]
    retained = c.retain_articles(old+new+others, SOURCES, NOW)
    assert len(retained) == 12
    assert {a['id'] for a in old} <= {a['id'] for a in retained}
    assert c.retain_articles(retained+new, SOURCES, NOW) == retained


def test_removed_and_disabled_sources_do_not_enter_archive():
    assert not dataset([article(source='removed')])['articles']
    assert not c.retain_articles([article()], [{**SOURCES[0], 'enabled':False}], NOW)


def test_japanese_aggregation_rejects_english_and_unrelated_publishers():
    def item(title, domain, key):
        return f'<item><guid>{key}</guid><title>{title} - NHKニュース</title><link>https://news.google.com/rss/articles/{key}</link><pubDate>Sun, 18 Oct 2026 00:00:00 GMT</pubDate><source url="https://{domain}">NHKニュース</source></item>'
    xml = ('<rss version="2.0"><channel><title>NHK</title>' +
           item('政府が新たな方針を発表', 'news.web.nhk', 'ja') +
           item('Japan announces policy', 'news.web.nhk', 'en') +
           item('政府が新たな方針を発表', 'news.web.nhk.attacker.test', 'fake') +
           item('政府が新たな方針を発表', 'another.example', 'other') + '</channel></rss>').encode()
    source = {**SOURCES[0], 'mode':'links_only', 'allowed_link_domains':['news.google.com'],
              'entry_source_domains':['news.web.nhk'], 'japanese_titles_only':True}
    articles, skipped = c.parse_feed(xml, source, NOW)
    assert skipped == 3 and len(articles) == 1
    assert articles[0]['title'] == '政府が新たな方針を発表'
    assert articles[0]['summary'] == ''


def test_japanese_community_rdf_has_direct_links_and_collection_dates():
    xml = '''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel rdf:about="https://b.hatena.ne.jp/site/news.web.nhk/"><title>NHK community</title></channel>
      <item rdf:about="https://news.web.nhk/newsweb/na/test"><title>政府が方針を発表</title><link>https://news.web.nhk/newsweb/na/test</link><dc:date>2026-10-18T00:00:00Z</dc:date><description>Unwanted community comments</description></item>
      <item rdf:about="https://news.web.nhk.attacker.example/test"><title>政府が方針を発表</title><link>https://news.web.nhk.attacker.example/test</link><dc:date>2026-10-18T00:00:00Z</dc:date></item>
      <item rdf:about="https://news.google.com/test"><title>政府が方針を発表</title><link>https://news.google.com/test</link><dc:date>2026-10-18T00:00:00Z</dc:date></item>
      <item rdf:about="https://news.web.nhk/english"><title>English story</title><link>https://news.web.nhk/english</link><dc:date>2026-10-18T00:00:00Z</dc:date></item>
    </rdf:RDF>'''
    source = {'id':'nhk-hatena', 'name':'NHK', 'enabled':True, 'mode':'links_only',
              'allowed_link_domains':['news.web.nhk'], 'japanese_titles_only':True,
              'time_basis':'community_collection'}
    items, skipped = c.parse_feed(xml.encode(), source, NOW)
    assert len(items) == 1 and skipped == 3
    assert items[0]['url'] == 'https://news.web.nhk/newsweb/na/test'
    assert items[0]['time_basis'] == 'community_collection'
    assert items[0]['published_at'] == '2026-10-18T00:00:00Z'
    assert items[0]['summary'] == ''
    old = article(source='nhk-japanese')
    old['url'] = 'https://news.google.com/test'
    assert c.retain_articles([old,*items], [source], NOW) == items
