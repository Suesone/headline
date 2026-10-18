"""Read-only news-source diagnostics; does not enable sources or collect full articles."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import feedparser

ROOT = Path(__file__).resolve().parents[1]
REUTERS_QUERY = urlencode({'query': json.dumps({'offset': 0, 'size': 5, 'section_id': '/world/', 'website': 'reuters'})})
CANDIDATES = [
    ('BBC World official RSS', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'rss'),
    ('BBC Business official RSS', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'rss'),
    ('Reuters website listing', 'https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?' + REUTERS_QUERY, 'json'),
    ('Reuters via RSSHub public instance', 'https://rsshub.app/reuters/world?limit=5&fulltext=false', 'rss'),
    ('AP official legacy index RSS', 'https://apnews.com/index.rss', 'rss'),
    ('AP mobile via RSSHub public instance', 'https://rsshub.app/apnews/mobile?limit=5&fulltext=false', 'rss'),
    ('Guardian World official RSS', 'https://www.theguardian.com/world/rss', 'rss'),
    ('AP World public page', 'https://apnews.com/hub/world-news', 'html'),
    ('AP topics via RSSHub public instance', 'https://rsshub.app/apnews/topics/world-news?limit=5&fulltext=false', 'rss'),
    ('Reuters via Google News RSS search', 'https://news.google.com/rss/search?' + urlencode({'q': 'site:reuters.com when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}), 'rss'),
    ('AP via Google News RSS search', 'https://news.google.com/rss/search?' + urlencode({'q': 'site:apnews.com when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}), 'rss'),
]


def probe(candidate):
    name, url, kind = candidate
    result = {'name': name, 'url': url, 'kind': kind}
    request = Request(url, headers={'User-Agent': 'Headline/1.0 (RSS compatibility research)', 'Accept': '*/*'})
    try:
        with urlopen(request, timeout=18) as response:
            result.update(http_status=response.status, content_type=response.headers.get('Content-Type', ''), final_url=response.url)
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            result['note'] = 'Response exceeds diagnostic limit; not parsed'
        elif kind == 'rss':
            feed = feedparser.parse(body)
            dates = [e for e in feed.entries if e.get('published_parsed') or e.get('updated_parsed')]
            result.update(valid_feed=bool(feed.get('version')), entries=len(feed.entries), dated_entries=len(dates),
                          missing_publication_date=sum(not e.get('published_parsed') for e in feed.entries),
                          publisher_names=sorted({e.get('source', {}).get('title', '') for e in feed.entries if e.get('source')}))
        elif kind == 'json':
            data = json.loads(body)
            articles = data.get('result', {}).get('articles', [])
            result.update(entries=len(articles), dated_entries=sum(bool(a.get('published_time')) for a in articles))
        else:
            # Inspect only metadata markers, never persist article HTML/text.
            text = body.decode('utf-8', errors='replace')
            result.update(json_ld_present='application/ld+json' in text,
                          publication_metadata_present='datePublished' in text,
                          note='HTML availability alone does not prove an extractable or licensed feed')
    except HTTPError as error:
        result.update(http_status=error.code, error='HTTP request rejected; no bypass attempted')
    except URLError:
        result['error'] = 'Network, DNS, or timeout failure'
    except Exception as error:
        result['error'] = type(error).__name__
    return result


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(probe, CANDIDATES))
    output = {'checked_at': datetime.now(timezone.utc).isoformat(), 'environment': 'Local development network; cloud results may differ',
              'results': results, 'note': 'Diagnostics only. HTTP success is not a content licence or uptime guarantee.'}
    path = ROOT / 'docs/news-source-probes.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    for result in results:
        print(result['name'], result.get('http_status', result.get('error')), 'items=', result.get('entries', '-'), 'dated=', result.get('dated_entries', '-'))
