"""RSS → bounded two-hour windows → rolling 72-hour archive → static JSON."""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import feedparser

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Shanghai')
WINDOW_HOURS = 2
MAX_ITEMS_PER_SOURCE = 10


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def dt(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.astimezone(timezone.utc)


def boundary(value):
    local = value.astimezone(TZ)
    return local.replace(hour=local.hour // WINDOW_HOURS * WINDOW_HOURS, minute=0, second=0, microsecond=0)


def window_id(value):
    return boundary(value).strftime('%Y-%m-%dT%H:00+08:00')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def plain(value, limit=600):
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', value or '', flags=re.I | re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()[:limit]


def apply_source_policy(article, source):
    for suffix in source.get('title_suffixes', []):
        if article['title'].rstrip().endswith(suffix):
            article['title'] = article['title'].rstrip()[:-len(suffix)].rstrip()
    # Strip retired analysis and cloud-enrichment fields from retained snapshots.
    for key in ('topics', 'analysis_allowed', 'topics_title_only', 'ai_allowed',
                'extraction_version', 'extracted', 'title_zh'):
        article.pop(key, None)
    article['time_basis'] = article.get('time_basis', source.get('time_basis', 'publication'))
    if source.get('mode') == 'links_only':
        article['summary'] = ''
    return article


def author_allowed(article, source):
    """Conservative gate for feeds mixing original and agency material."""
    allowed = source.get('allowed_authors')
    if allowed is not None and article.get('author', '') not in allowed:
        return False
    credit = '\n'.join(article.get(k, '') for k in ('author', 'title', 'summary'))
    return not any(re.search(r'\b' + re.escape(word) + r'\b', credit, re.I)
                   for word in source.get('exclude_credit_patterns', []))


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme not in {'https', 'http'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Unsafe article URL')
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid', 'ref', 'cmp'}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', urlencode(sorted(query)), ''))


def read_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def request_bytes(url, timeout=25):
    request = Request(url, headers={'User-Agent': 'Headline/1.0 (personal noncommercial RSS reader)',
                                   'Accept': 'application/rss+xml,application/atom+xml,application/xml'})
    with urlopen(request, timeout=timeout) as response:
        content = response.read(3_000_001)
    if len(content) > 3_000_000:
        raise ValueError('Feed exceeds 3 MB')
    return content


def parse_feed(content, source, now):
    feed = feedparser.parse(content)
    if not feed.entries and feed.get('bozo'):
        raise ValueError('Feed is not valid RSS/Atom')
    if not feed.entries and not feed.get('version'):
        raise ValueError('Response is not RSS/Atom')
    articles, skipped = [], 0
    requested = source.get('max_items', MAX_ITEMS_PER_SOURCE)
    limit = min(requested, MAX_ITEMS_PER_SOURCE) if type(requested) is int and requested > 0 else MAX_ITEMS_PER_SOURCE
    seen_ids, seen_urls = set(), set()
    for position, entry in enumerate(feed.entries, 1):
        stamp = entry.get('published_parsed') or entry.get('updated_parsed')
        try:
            if not stamp:
                raise ValueError('No publication date')
            published = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc)
            if published > now + timedelta(minutes=5):
                raise ValueError('Future publication date')
            # Aggregators can include unrelated publishers: verify their RSS source tag.
            source_domains = source.get('entry_source_domains', [])
            if source_domains:
                origin = urlsplit(entry.get('source', {}).get('href', '')).hostname or ''
                if not any(origin == d or origin.endswith('.' + d) for d in source_domains):
                    raise ValueError('Unrelated aggregator publisher')
            title = plain(entry.get('title'), 350)
            if source_domains:
                credit = plain(entry.get('source', {}).get('title', ''), 100)
                if credit and title.endswith(' - ' + credit):
                    title = title[:-len(' - ' + credit)].strip()
            if source.get('english_titles_only') and re.search(r'[\u3040-\u30ff\u3400-\u9fff]', title):
                raise ValueError('Not an English headline')
            if source.get('japanese_titles_only') and not re.search(r'[\u3040-\u30ff]', title):
                raise ValueError('Not a Japanese headline')
            if not title:
                raise ValueError('No title')
            if any(title.casefold().startswith(prefix.casefold()) for prefix in source.get('exclude_title_prefixes', [])):
                skipped += 1
                continue
            url = canonical_url(entry.get('link', ''))
            allowed = source.get('allowed_link_domains', [])
            host = urlsplit(url).hostname
            if allowed and not any(host == domain or host.endswith('.' + domain) for domain in allowed):
                raise ValueError('Article URL outside configured publisher')
            identity = source['id'] + ':' + str(entry.get('id') or url)
            article = apply_source_policy({
                'id': digest(identity), 'identities': [identity], 'source_id': source['id'],
                'publisher': source.get('publisher', source['name']), 'title': title, 'url': url,
                'summary': plain(entry.get('summary')), 'author': plain(entry.get('author', ''), 160),
                'published_at': iso(published), 'first_seen_at': iso(now), 'window_id': window_id(published),
                'feed_rank': position, 'rank_observed_at': iso(now),
            }, source)
            if not author_allowed(article, source):
                skipped += 1
                continue
            if identity in seen_ids or url in seen_urls:
                skipped += 1
                continue
            seen_ids.add(identity); seen_urls.add(url)
            articles.append(article)
            if len(articles) >= limit:
                break
        except (ValueError, TypeError, OverflowError):
            skipped += 1
    return articles, skipped


def fetch_source(source, now):
    if not source.get('enabled'):
        return [], {'id': source['id'], 'status': 'disabled', 'message': source.get('note', '')}
    candidates = [source, *[{**source, **fallback} for fallback in source.get('fallbacks', [])]]
    for index, candidate in enumerate(candidates):
        attempts = 1 if index < len(candidates) - 1 else 3
        for attempt in range(attempts):
            try:
                articles, skipped = parse_feed(request_bytes(candidate['url']), candidate, now)
                max_age = source.get('max_feed_age_hours')
                if not articles or (max_age and max(dt(a['published_at']) for a in articles) < now - timedelta(hours=max_age)):
                    raise ValueError('Empty or stale feed')
                state = {'id': source['id'], 'status': 'ok', 'checked_at': iso(now),
                         'last_success_at': iso(now), 'received': len(articles), 'skipped': skipped,
                         'fetch_limit': MAX_ITEMS_PER_SOURCE,
                         'message': f'已读取 {len(articles)} 条；跳过 {skipped} 条无效记录',
                         'active_feed_url': candidate['url'], 'using_fallback': index > 0}
                if index > 0:
                    state.update(relay_name=candidate['relay_name'], relay_url=candidate['relay_url'])
                    state['message'] += '；主源不可用，正在使用 Google News 备用标题聚合'
                return articles, state
            except Exception:
                # Do not expose URLs, request headers or credentials in data/logs.
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)
    return [], {'id': source['id'], 'status': 'error', 'checked_at': iso(now),
                'message': f"订阅读取失败、无有效内容或超过 {source.get('max_feed_age_hours', 96)} 小时未更新；重试后保留先前记录"}


def merge_articles(previous, incoming, cutoff):
    merged = [dict(a) for a in previous if dt(a['published_at']) >= cutoff]
    for article in incoming:
        if dt(article['published_at']) < cutoff:
            continue
        match = None
        for old in merged:
            if old['source_id'] != article['source_id']:
                continue
            same_identity = bool(set(old.get('identities', [])) & set(article['identities']))
            same_url = old['url'] == article['url']
            near_date = abs((dt(old['published_at']) - dt(article['published_at'])).total_seconds()) < 86400
            a, b = old['title'].casefold(), article['title'].casefold()
            similar = len(a) > 30 and len(b) > 30 and SequenceMatcher(None, a, b).ratio() >= .94
            if same_identity or same_url or (near_date and (a == b or similar)):
                match = old
                break
        if match:
            # Publication time and record ID stay stable across RSS revisions.
            changed = match['title'] != article['title'] or match['summary'] != article['summary']
            match['identities'] = sorted(set(match.get('identities', [])) | set(article['identities']))
            match.update({k: article[k] for k in ('title', 'summary', 'author', 'url')})
            for key in ('feed_rank', 'rank_observed_at'):
                if key in article:
                    match[key] = article[key]
            if changed:
                match.pop('title_zh', None)
                match.pop('extracted', None)
                match.pop('extraction_version', None)
        else:
            merged.append(article)
    return sorted(merged, key=lambda a: (a['published_at'], a['id']), reverse=True)


def retain_articles(articles, sources, now, retention_days=3):
    """Rolling retention and a cumulative, stable source/window quota across retries."""
    allowed = {source['id'] for source in sources if source.get('enabled')}
    cutoff = now - timedelta(days=retention_days)
    groups, seen = {}, set()
    for article in sorted(articles, key=lambda a: (a.get('first_seen_at', a['published_at']),
                                                   a.get('feed_rank', 100), a['id'])):
        if article['id'] in seen:
            continue
        seen.add(article['id'])
        if article['source_id'] not in allowed or not cutoff <= dt(article['published_at']) < now:
            continue
        article['window_id'] = window_id(dt(article['published_at']))
        group = groups.setdefault((article['source_id'], article['window_id']), [])
        if len(group) < MAX_ITEMS_PER_SOURCE:
            group.append(article)
    return sorted([a for group in groups.values() for a in group],
                  key=lambda a: (a['published_at'], a['id']), reverse=True)


def run_metadata(now):
    event = os.getenv('HEADLINE_TRIGGER_EVENT', 'local')
    if event not in {'schedule', 'workflow_dispatch', 'push'}:
        event = 'local'
    schedule = os.getenv('HEADLINE_TRIGGER_SCHEDULE', '') if event == 'schedule' else ''
    if schedule not in {'0 */2 * * *', '17 */2 * * *', '37 */2 * * *'}:
        schedule = ''
    metadata = {'event': event, 'schedule': schedule, 'slot': window_id(now)}
    if event == 'workflow_dispatch' and os.getenv('HEADLINE_TRIGGER_SOURCE') == 'cloudflare-watchdog':
        metadata['source'] = 'cloudflare-watchdog'
        requested = os.getenv('HEADLINE_REQUESTED_SLOT', '')
        try:
            if abs((now - dt(requested)).total_seconds()) <= 86400:
                metadata['requested_slot'] = iso(dt(requested))
        except (ValueError, TypeError):
            pass
    repository, run_id = os.getenv('GITHUB_REPOSITORY', ''), os.getenv('GITHUB_RUN_ID', '')
    if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) and run_id.isdigit():
        metadata['run_url'] = f'https://github.com/{repository}/actions/runs/{run_id}'
    return metadata


def build_dataset(articles, sources, statuses, now, settings, previous=None):
    end = boundary(now)
    latest_start = end - timedelta(hours=WINDOW_HOURS)
    cutoff = now - timedelta(days=settings['retention_days'])
    articles = retain_articles(articles, sources, now, settings['retention_days'])
    complete = [a for a in articles if dt(a['published_at']) < end]
    windows = []
    cursor = boundary(cutoff)
    while cursor < end:
        key = window_id(cursor)
        subset = [a for a in complete if a['window_id'] == key]
        windows.append({'id': key, 'start': iso(cursor), 'end': iso(cursor + timedelta(hours=WINDOW_HOURS)),
                        'date': cursor.date().isoformat(), 'article_ids': [a['id'] for a in subset]})
        cursor += timedelta(hours=WINDOW_HOURS)
    days = [{'date': date} for date in sorted({dt(a['published_at']).astimezone(TZ).date().isoformat()
                                               for a in articles}, reverse=True)]
    enabled = [s for s in statuses if s['status'] != 'disabled']
    successes = sum(s['status'] == 'ok' for s in enabled)
    status = 'ok' if enabled and successes == len(enabled) else 'partial' if successes else 'error'
    old_status = {s['id']: s for s in (previous or {}).get('sources', [])}
    public_sources = []
    for source, state in zip(sources, statuses):
        state = dict(state)
        if state['status'] != 'ok':
            state['last_success_at'] = old_status.get(state['id'], {}).get('last_success_at')
        public_sources.append({**source, **state})
    return {'schema_version': 1, 'generated_at': iso(now), 'trigger': run_metadata(now), 'timezone': 'Asia/Shanghai', 'window_hours': WINDOW_HOURS,
            'latest_window_id': window_id(latest_start), 'today': now.astimezone(TZ).date().isoformat(),
            'last_success_at': iso(now) if successes else (previous or {}).get('last_success_at'),
            'status': status, 'sources': public_sources, 'articles': articles, 'windows': windows,
            'days': days, 'retention_days': settings['retention_days'], 'features': {'translation': 'on_demand'},
            'ranking': settings.get('ranking', {}),
            'ai': {'status': 'on_demand', 'message': '定时流程不调用 AI；网页默认选中 Gemini，点击后才翻译标题'}}


def run(now, output, state_path):
    sources = read_json(ROOT / 'config/sources.json')
    settings = read_json(ROOT / 'config/settings.json')
    previous = read_json(state_path, {})
    cutoff = now - timedelta(days=settings['retention_days'])
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda s: fetch_source(s, now), sources))
    incoming = [a for articles, _ in results for a in articles]
    allowed = {s['id'] for s in sources if s.get('enabled')}
    source_map = {s['id']: s for s in sources}
    old = [a for a in previous.get('articles', []) if a['source_id'] in allowed
           and author_allowed(a, source_map[a['source_id']])]
    articles = merge_articles(old, incoming, cutoff)
    for article in articles:
        apply_source_policy(article, source_map[article['source_id']])
    data = build_dataset(articles, sources, [state for _, state in results], now, settings, previous)
    # No cloud enrichment: public snapshots contain English RSS content only.
    write_json(state_path, data)
    published = json.loads(json.dumps(data))
    for article in published['articles']:
        article.pop('identities', None)
        article.pop('extracted', None)
        article.pop('extraction_version', None)
    write_json(output, published)
    # Small published receipt for the independent watchdog (no article text or secrets).
    write_json(output.with_name('status.json'), {
        'generated_at': data['generated_at'], 'status': data['status'],
        'last_success_at': data['last_success_at'], 'trigger': data['trigger'],
        'sources': [{k: source.get(k) for k in ('id', 'status', 'received')} for source in data['sources']],
    })
    print(f"RSS: {data['status']}; {len(data['articles'])} articles; AI: {data['ai']['status']}")
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--now', help='ISO timestamp with timezone; for replay/testing')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data/news.json')
    parser.add_argument('--state', type=Path, default=ROOT / 'state/news.json')
    parser.add_argument('--no-ai', action='store_true', help='Legacy flag; cloud AI is always disabled')
    args = parser.parse_args()
    run(dt(args.now) if args.now else datetime.now(timezone.utc), args.output, args.state)
