"""Record unattended observations without an extra paid monitoring service."""
from datetime import timedelta
import os
from pathlib import Path
from scripts.collect import ROOT, WINDOW_HOURS, boundary, dt, read_json, window_id, write_json

data = read_json(ROOT / 'public/data/news.json')
path = ROOT / 'state/health.json'
health = read_json(path, {'started_at': data['generated_at'], 'runs': []})
now = dt(data['generated_at'])
if health.get('window_hours', 4) != WINDOW_HOURS:
    health = {'started_at': data['generated_at'], 'runs': [],
              'note': '更新频率变更为两小时，重新开始覆盖观察'}
health['window_hours'] = WINDOW_HOURS
slot = window_id(now)
runs = {}
for run in health['runs']:
    if dt(run['at']) >= now - timedelta(days=2):
        run['slot'] = window_id(dt(run['at']))
        runs[run['slot']] = run
runs[slot] = {'at': data['generated_at'], 'slot': slot, 'status': data['status'], 'ai': data['ai']['status'],
              'articles': len(data['articles']), 'failed_sources': [s['id'] for s in data['sources'] if s['status'] == 'error']}
health['runs'] = sorted(runs.values(), key=lambda r: r['at'])
health['observation_complete'] = now - dt(health['started_at']) >= timedelta(days=2)
expected = set()
cursor = boundary(max(dt(health['started_at']), now - timedelta(days=2)))
while cursor <= boundary(now):
    expected.add(window_id(cursor))
    cursor += timedelta(hours=WINDOW_HOURS)
health['missing_slots'] = sorted(expected - set(runs))
health['healthy'] = not health['missing_slots'] and all(r['status'] == 'ok' for r in health['runs'])
write_json(path, health)
summary = Path(os.environ.get('GITHUB_STEP_SUMMARY', '/tmp/headline-summary.md'))
summary.write_text('# Headline 更新记录\n\n'
                   f"- 抓取状态：{data['status']}\n- 新闻数：{len(data['articles'])}\n"
                   f"- AI：{data['ai']['status']}\n- 最近两天覆盖：{len(health['runs'])} 个两小时时段\n"
                   f"- 缺失时段：{len(health['missing_slots'])}\n"
                   f"- 两天观察：{'已结束' if health['observation_complete'] else '进行中'}\n"
                   f"- 观察健康状态：{'正常' if health['healthy'] else '有失败或缺失记录'}\n\n"
                   '完整来源状态见网页底部；历史运行见 state/health.json。\n')
print('Two-day observation:', 'complete' if health['observation_complete'] else 'in progress')
