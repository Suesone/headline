"""Probe a bounded list of source-backed community RSS candidates."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import calendar
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import feedparser
from scripts.collect import ROOT

CANDIDATES = [
    ('Feedseek Reuters', 'https://raw.githubusercontent.com/trvny/feedseek/main/feeds/feed_reuters.xml'),
    ('RSSHub Blackcat Reuters', 'https://rsshub.blackcat.group/reuters/world?limit=10&fulltext=false'),
    ('RSSHub Blackcat AP', 'https://rsshub.blackcat.group/apnews/mobile?limit=10&fulltext=false'),
    ('RSS-Bridge Reuters', 'https://rss-bridge.org/bridge01/?' + urlencode({'action': 'display', 'bridge': 'Reuters', 'feed': 'world', 'format': 'Atom'})),
    ('RSS-Bridge AP', 'https://rss-bridge.org/bridge01/?' + urlencode({'action': 'display', 'bridge': 'AssociatedPressNews', 'context': 'Standard Category', 'category': '/world-news', 'limit': 10, 'format': 'Atom'})),
]


def probe(candidate):
    name, url = candidate
    result = {'name': name, 'url': url}
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Headline/1.0 personal RSS reader'}), timeout=20) as response:
            result['http_status'] = response.status
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('Response too large')
        feed = feedparser.parse(body)
        dates = [datetime.fromtimestamp(calendar.timegm(e.published_parsed), timezone.utc) for e in feed.entries if e.get('published_parsed')]
        result.update(valid_feed=bool(feed.get('version')), entries=len(feed.entries), dated_entries=len(dates),
                      latest_published_at=max(dates).isoformat() if dates else None,
                      link_domains=sorted({urlsplit(e.get('link', '')).hostname or '' for e in feed.entries}))
    except HTTPError as error:
        result['http_status'] = error.code
    except Exception as error:
        result['error'] = type(error).__name__
    return result


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(probe, CANDIDATES))
    output = {'checked_at': datetime.now(timezone.utc).isoformat(), 'environment': 'Local network; cloud may differ', 'results': results}
    (ROOT / 'docs/community-rss-probes.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    for result in results:
        print(result)
