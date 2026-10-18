"""Check the published site before a fallback schedule; standard library only."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

PRIMARY = '0 */2 * * *'
BACKUPS = {'17 */2 * * *', '37 */2 * * *'}
TZ = ZoneInfo('Asia/Shanghai')


def slot_start(now):
    local = now.astimezone(TZ)
    return local.replace(hour=local.hour // 2 * 2, minute=0, second=0, microsecond=0)


def needs_update(now, event, schedule, published=None):
    if event != 'schedule' or schedule not in BACKUPS:
        return True, '整点、手动或代码发布任务正常更新'
    if not isinstance(published, dict) or published.get('status') != 'ok':
        return True, '未取得成功发布的数据，执行补抓'
    try:
        stamp = datetime.fromisoformat(published['generated_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Timestamp without timezone')
    except (KeyError, AttributeError, TypeError, ValueError):
        return True, '发布时间无效，执行补抓'
    if slot_start(now) <= stamp <= now + timedelta(minutes=5):
        return False, '本两小时时段已有成功发布，跳过重复抓取'
    return True, '本两小时时段尚未成功发布，执行补抓'


def main():
    now = datetime.now(timezone.utc)
    event, schedule = os.getenv('TRIGGER_EVENT', ''), os.getenv('TRIGGER_SCHEDULE', '')
    external = event == 'workflow_dispatch' and os.getenv('TRIGGER_SOURCE') == 'cloudflare-watchdog'
    effective_event, effective_schedule = ('schedule', '17 */2 * * *') if external else (event, schedule)
    published = None
    if effective_event == 'schedule' and effective_schedule in BACKUPS:
        try:
            url = 'https://headline.infinitas.top/data/status.json?check=' + str(int(now.timestamp()))
            request = Request(url, headers={'User-Agent': 'Headline schedule recovery', 'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=15) as response:
                raw = response.read(32_001)
            if len(raw) <= 32_000:
                published = json.loads(raw)
        except Exception:
            pass  # Fail open: a failed check must never suppress recovery.
    update, reason = needs_update(now, effective_event, effective_schedule, published)
    output = os.getenv('GITHUB_OUTPUT')
    if output:
        with Path(output).open('a') as handle:
            handle.write('should_update=' + str(update).lower() + '\n')
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a') as handle:
            handle.write('# 调度检查\n\n' + reason + '\n')
    print(reason)


if __name__ == '__main__':
    main()
