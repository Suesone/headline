"""Probe configured major feeds plus the unconfirmed AFP candidate; no article text saved."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from scripts.collect import ROOT, read_json
from scripts.probe_community import probe

if __name__ == '__main__':
    sources = read_json(ROOT / 'config/sources.json')
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(probe, [(s['name'], s['url']) for s in sources]))
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'environment': 'Local network; GitHub Actions must be checked separately', 'results': results}
    (ROOT / 'docs/major-rss-probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for result in results:
        print(result)
