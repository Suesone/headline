"""Keep a two-day observation log inside the existing free scheduled workflow."""
from datetime import timedelta
import os
from pathlib import Path
from scripts.collect import ROOT, dt, read_json, write_json

data = read_json(ROOT / 'public/data/news.json')
path = ROOT / 'state/health.json'
health = read_json(path, {'started_at': data['generated_at'], 'runs': []})
now = dt(data['generated_at'])
health['runs'] = [r for r in health['runs'] if dt(r['at']) >= now - timedelta(days=2) and r['at'] != data['generated_at']]
health['runs'].append({'at': data['generated_at'], 'status': data['status'], 'ai': data['ai']['status'],
                       'articles': len(data['articles']), 'failed_sources': [s['id'] for s in data['sources'] if s['status'] == 'error']})
health['observation_complete'] = now - dt(health['started_at']) >= timedelta(days=2)
health['healthy'] = all(r['status'] == 'ok' for r in health['runs'])
write_json(path, health)
summary = Path(os.environ.get('GITHUB_STEP_SUMMARY', '/tmp/headline-summary.md'))
summary.write_text('# Headline 更新记录\n\n'
                   f"- 抓取状态：{data['status']}\n- 新闻数：{len(data['articles'])}\n"
                   f"- AI：{data['ai']['status']}\n- 最近两天记录：{len(health['runs'])} 次\n"
                   f"- 两天观察：{'已完成' if health['observation_complete'] else '进行中'}\n\n"
                   '完整来源状态见网页底部；历史运行见 state/health.json。\n')
print('Two-day observation:', 'complete' if health['observation_complete'] else 'in progress')
