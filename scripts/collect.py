"""RSS → deterministic four-hour windows → optional cached AI → static JSON."""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import hashlib
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import feedparser

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Shanghai')
STOP = {'news', 'world', 'today', 'latest', 'live', 'report', 'reports', 'says', 'said',
        'watch', 'video', 'people', 'year', 'years', 'day', 'days', 'week', 'month',
        'story', 'stories', 'new', 'first', 'last', 'global voices', 'wikinews',
        'according', 'read', 'continue reading', 'breaking news', 'copyright', 'digital'}


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def dt(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.astimezone(timezone.utc)


def boundary(value):
    local = value.astimezone(TZ)
    return local.replace(hour=local.hour // 4 * 4, minute=0, second=0, microsecond=0)


def window_id(value):
    return boundary(value).strftime('%Y-%m-%dT%H:00+08:00')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def plain(value, limit=600):
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', value or '', flags=re.I | re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()[:limit]


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
    for entry in feed.entries:
        stamp = entry.get('published_parsed') or entry.get('updated_parsed')
        try:
            if not stamp:
                raise ValueError('No publication date')
            published = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc)
            if published > now + timedelta(minutes=5):
                raise ValueError('Future publication date')
            title = plain(entry.get('title'), 350)
            if not title:
                raise ValueError('No title')
            if any(title.casefold().startswith(prefix.casefold()) for prefix in source.get('exclude_title_prefixes', [])):
                skipped += 1
                continue
            url = canonical_url(entry.get('link', ''))
            identity = source['id'] + ':' + str(entry.get('id') or url)
            articles.append({
                'id': digest(identity), 'identities': [identity], 'source_id': source['id'],
                'publisher': source.get('publisher', source['name']), 'title': title, 'url': url,
                'summary': plain(entry.get('summary')), 'author': plain(entry.get('author', ''), 160),
                'published_at': iso(published), 'first_seen_at': iso(now), 'window_id': window_id(published),
                'topics': [],
            })
        except (ValueError, TypeError, OverflowError):
            skipped += 1
    return articles, skipped


def fetch_source(source, now):
    if not source.get('enabled'):
        return [], {'id': source['id'], 'status': 'disabled', 'message': source.get('note', '')}
    for attempt in range(3):
        try:
            articles, skipped = parse_feed(request_bytes(source['url']), source, now)
            return articles, {'id': source['id'], 'status': 'ok', 'checked_at': iso(now),
                              'last_success_at': iso(now), 'received': len(articles), 'skipped': skipped,
                              'message': f'已读取 {len(articles)} 条；跳过 {skipped} 条无效记录'}
        except Exception:
            # Do not expose URLs, request headers or credentials in data/logs.
            if attempt < 2:
                time.sleep(2 ** attempt)
    return [], {'id': source['id'], 'status': 'error', 'checked_at': iso(now),
                'message': '读取失败，已重试三次；保留先前记录'}


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
            if changed:
                match['topics'] = []
                match.pop('title_zh', None)
                match.pop('extracted', None)
        else:
            merged.append(article)
    return sorted(merged, key=lambda a: (a['published_at'], a['id']), reverse=True)


class TopicExtractor:
    def __init__(self, aliases):
        import spacy
        import yake
        self.nlp = spacy.load('en_core_web_sm', disable=['lemmatizer'])
        self.yake = yake.KeywordExtractor(lan='en', n=3, top=15, dedupLim=.8)
        self.aliases = {variant.casefold().strip(' .,'): name for name, variants in aliases.items() for variant in [name, *variants]}

    def normalize(self, name):
        name = re.sub(r"[’']s$", '', name.strip(' .,;:!?\"\'()'))
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'^the ', '', name, flags=re.I)
        return self.aliases.get(name.casefold(), name)

    def extract(self, article):
        text = article['title'] + '.\n' + article['summary']
        terms = {}
        doc = self.nlp(text)
        noun_phrases = [self.normalize(chunk.text).casefold() for chunk in doc.noun_chunks if '\n' not in chunk.text]
        for ent in doc.ents:
            if '\n' not in ent.text and ent.label_ in {'PERSON', 'GPE', 'ORG', 'EVENT', 'NORP', 'FAC', 'LOC'}:
                label = self.normalize(ent.text)
                if len(label) >= 2 and label.casefold() not in STOP and len(label.split()) <= 6:
                    terms[label.casefold()] = {'id': digest(label.casefold()), 'label': label, 'kind': 'entity'}
        for phrase, score in self.yake.extract_keywords(text):
            label = self.normalize(phrase)
            words = label.split()
            if not any(label.casefold() in chunk for chunk in noun_phrases) or re.search(r"[’']s\b", label):
                continue
            tags = self.nlp(label)
            if any(t.pos_ in {'VERB', 'AUX', 'ADV'} for t in tags) or not any(t.pos_ in {'NOUN', 'PROPN'} for t in tags):
                continue
            if (2 <= len(words) <= 3 and score < .10 and len(label) < 70
                    and not any(w.casefold() in STOP for w in words)
                    and not any(label.casefold() in key or key in label.casefold() for key in terms)):
                terms[label.casefold()] = {'id': digest(label.casefold()), 'label': label, 'kind': 'phrase'}
        return list(terms.values())[:25]


def rank_topics(articles, limit=None):
    topics = {}
    for article in articles:
        for term in {t['id']: t for t in article.get('topics', [])}.values():
            topic = topics.setdefault(term['id'], {**term, 'article_ids': set(), 'publishers': set(),
                                                  'first_seen_at': article['published_at']})
            topic['article_ids'].add(article['id'])
            topic['publishers'].add(article['publisher'])
            topic['first_seen_at'] = min(topic['first_seen_at'], article['published_at'])
    ranked = []
    for topic in topics.values():
        topic['article_ids'] = sorted(topic['article_ids'])
        topic['source_count'] = len(topic.pop('publishers'))
        topic['article_count'] = len(topic['article_ids'])
        ranked.append(topic)
    ranked.sort(key=lambda t: (-t['source_count'], -t['article_count'], t['kind'] != 'entity', t['label'].casefold()))
    return ranked[:limit] if limit is not None else ranked


def build_dataset(articles, sources, statuses, now, settings, previous=None):
    end = boundary(now)
    latest_start = end - timedelta(hours=4)
    cutoff = (now.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
              - timedelta(days=settings['retention_days'] - 1))
    articles = [a for a in articles if cutoff <= dt(a['published_at']) < now]
    complete = [a for a in articles if dt(a['published_at']) < end]
    windows = []
    cursor = cutoff
    while cursor < end:
        key = window_id(cursor)
        subset = [a for a in complete if a['window_id'] == key]
        topics = rank_topics(subset, settings['topics_per_window'])
        weights = {a['id']: max((t['source_count'] for t in topics if a['id'] in t['article_ids']), default=0)
                   for a in subset}
        subset.sort(key=lambda a: (weights[a['id']], a['published_at']), reverse=True)
        windows.append({'id': key, 'start': iso(cursor), 'end': iso(cursor + timedelta(hours=4)),
                        'date': cursor.date().isoformat(), 'article_ids': [a['id'] for a in subset], 'topics': topics})
        cursor += timedelta(hours=4)
    days = []
    for n in range(settings['retention_days']):
        date = (now.astimezone(TZ).date() - timedelta(days=n)).isoformat()
        day_windows = [w for w in windows if w['date'] == date]
        selected = {t['id'] for w in day_windows for t in w['topics']}
        subset = [a for a in complete if a['window_id'][:10] == date]
        days.append({'date': date, 'topics': [t for t in rank_topics(subset) if t['id'] in selected],
                     'article_count': len(subset)})
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
    return {'schema_version': 1, 'generated_at': iso(now), 'timezone': 'Asia/Shanghai',
            'latest_window_id': window_id(latest_start), 'today': now.astimezone(TZ).date().isoformat(),
            'last_success_at': iso(now) if successes else (previous or {}).get('last_success_at'),
            'status': status, 'sources': public_sources, 'articles': articles, 'windows': windows,
            'days': days, 'ai': {'status': 'disabled', 'message': '尚未配置免费 AI，英文新闻和热词正常可用'}}


def run(now, output, state_path, enable_ai=True):
    sources = read_json(ROOT / 'config/sources.json')
    settings = read_json(ROOT / 'config/settings.json')
    previous = read_json(state_path, {})
    cutoff = now.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=settings['retention_days'] - 1)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda s: fetch_source(s, now), sources))
    incoming = [a for articles, _ in results for a in articles]
    allowed = {s['id'] for s in sources if s.get('enabled')}
    old = [a for a in previous.get('articles', []) if a['source_id'] in allowed]
    articles = merge_articles(old, incoming, cutoff)
    aliases = read_json(ROOT / 'config/aliases.json')
    extraction_version = digest('topics-v4:' + json.dumps(aliases, sort_keys=True))
    pending = [a for a in articles if a.get('extraction_version') != extraction_version]
    if pending:
        extractor = TopicExtractor(aliases)
        for article in pending:
            article['topics'] = extractor.extract(article)
            article['extracted'] = True
            article['extraction_version'] = extraction_version
    data = build_dataset(articles, sources, [state for _, state in results], now, settings, previous)
    # Persist base data before AI so an API failure cannot destroy a successful RSS run.
    write_json(state_path, data)
    if enable_ai:
        from scripts.ai import enrich
        enrich(data, settings['ai'], state_path.parent / 'ai-cache.json', now)
        write_json(state_path, data)
    published = json.loads(json.dumps(data))
    for article in published['articles']:
        article.pop('identities', None)
        article.pop('extracted', None)
        article.pop('extraction_version', None)
    write_json(output, published)
    print(f"RSS: {data['status']}; {len(data['articles'])} articles; AI: {data['ai']['status']}")
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--now', help='ISO timestamp with timezone; for replay/testing')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data/news.json')
    parser.add_argument('--state', type=Path, default=ROOT / 'state/news.json')
    parser.add_argument('--no-ai', action='store_true')
    args = parser.parse_args()
    run(dt(args.now) if args.now else datetime.now(timezone.utc), args.output, args.state, not args.no_ai)
