from scripts import schedule_guard as guard
from scripts import collect
import pytest

NOW = collect.dt('2026-10-18T22:17:00+08:00')


def published(stamp='2026-10-18T22:01:00+08:00', status='ok'):
    return {'generated_at': stamp, 'status': status}


@pytest.mark.parametrize('schedule', sorted(guard.BACKUPS))
def test_backup_skips_only_current_successfully_published_slot(schedule):
    assert guard.needs_update(NOW, 'schedule', schedule, published())[0] is False
    assert guard.needs_update(NOW, 'schedule', schedule, published('2026-10-18T21:49:00+08:00'))[0] is True
    assert guard.needs_update(NOW, 'schedule', schedule, published(status='partial'))[0] is True
    assert guard.needs_update(NOW, 'schedule', schedule, published(status='error'))[0] is True


@pytest.mark.parametrize('event,schedule', [('schedule', guard.PRIMARY), ('push',''), ('workflow_dispatch','')])
def test_primary_manual_and_code_updates_are_not_suppressed(event, schedule):
    assert guard.needs_update(NOW, event, schedule, published())[0] is True


@pytest.mark.parametrize('data', [None, [], {}, {'status':'ok'}, published('not-a-time'),
                                 published('2026-10-18T22:01:00'), published('2099-10-18T22:01:00+08:00')])
def test_unreachable_invalid_or_future_data_never_suppresses_recovery(data):
    assert guard.needs_update(NOW, 'schedule', '17 */2 * * *', data)[0] is True


def test_midnight_uses_beijing_day_and_two_hour_boundary():
    now = collect.dt('2026-10-19T00:17:00+08:00')
    assert guard.slot_start(now).isoformat() == '2026-10-19T00:00:00+08:00'
    assert guard.needs_update(now, 'schedule', '17 */2 * * *', published('2026-10-18T23:59:59+08:00'))[0] is True
    assert guard.needs_update(now, 'schedule', '17 */2 * * *', published('2026-10-18T16:01:00Z'))[0] is False


def test_guard_checks_published_site_and_skips_duplicate_without_reading_repo_state(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timezone
    from io import BytesIO
    output, summary = tmp_path/'output', tmp_path/'summary'
    monkeypatch.setenv('TRIGGER_EVENT', 'schedule'); monkeypatch.setenv('TRIGGER_SCHEDULE', '37 */2 * * *')
    monkeypatch.setenv('GITHUB_OUTPUT', str(output)); monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    seen = []
    def response(request, timeout):
        seen.append(request.full_url)
        return BytesIO(json.dumps(published(datetime.now(timezone.utc).isoformat())).encode())
    monkeypatch.setattr(guard, 'urlopen', response)
    guard.main()
    assert output.read_text() == 'should_update=false\n'
    assert seen[0].startswith('https://headline.infinitas.top/data/status.json?check=')
    assert '跳过重复抓取' in summary.read_text()


def test_guard_network_failure_runs_recovery(monkeypatch, tmp_path):
    monkeypatch.setenv('TRIGGER_EVENT','schedule'); monkeypatch.setenv('TRIGGER_SCHEDULE','17 */2 * * *')
    monkeypatch.setenv('GITHUB_OUTPUT',str(tmp_path/'output')); monkeypatch.delenv('GITHUB_STEP_SUMMARY',raising=False)
    monkeypatch.setattr(guard,'urlopen',lambda *a,**kw: (_ for _ in ()).throw(OSError('offline')))
    guard.main()
    assert (tmp_path/'output').read_text() == 'should_update=true\n'


def test_run_metadata_distinguishes_automatic_from_manual_and_links_workflow(monkeypatch):
    monkeypatch.setenv('HEADLINE_TRIGGER_EVENT','schedule')
    monkeypatch.setenv('HEADLINE_TRIGGER_SCHEDULE','17 */2 * * *')
    monkeypatch.setenv('GITHUB_REPOSITORY','Suesone/headline'); monkeypatch.setenv('GITHUB_RUN_ID','123')
    meta = collect.run_metadata(NOW)
    assert meta == {'event':'schedule','schedule':'17 */2 * * *','slot':'2026-10-18T22:00+08:00',
                    'run_url':'https://github.com/Suesone/headline/actions/runs/123'}
    monkeypatch.setenv('HEADLINE_TRIGGER_EVENT','workflow_dispatch')
    assert collect.run_metadata(NOW)['schedule'] == ''


def test_cloudflare_dispatch_rechecks_receipt_to_prevent_a_duplicate_run(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timezone
    from io import BytesIO
    monkeypatch.setenv('TRIGGER_EVENT', 'workflow_dispatch')
    monkeypatch.setenv('TRIGGER_SOURCE', 'cloudflare-watchdog')
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path/'output'))
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    monkeypatch.setattr(guard, 'urlopen', lambda *a, **k: BytesIO(json.dumps(published(datetime.now(timezone.utc).isoformat())).encode()))
    guard.main()
    assert (tmp_path/'output').read_text() == 'should_update=false\n'


def test_cloudflare_metadata_records_the_requested_slot_but_rejects_arbitrary_input(monkeypatch):
    monkeypatch.setenv('HEADLINE_TRIGGER_EVENT','workflow_dispatch')
    monkeypatch.setenv('HEADLINE_TRIGGER_SOURCE','cloudflare-watchdog')
    monkeypatch.setenv('HEADLINE_REQUESTED_SLOT','2026-10-18T14:00:00.000Z')
    metadata = collect.run_metadata(NOW)
    assert metadata['source'] == 'cloudflare-watchdog'
    assert metadata['requested_slot'] == '2026-10-18T14:00:00Z'
    monkeypatch.setenv('HEADLINE_REQUESTED_SLOT','untrusted arbitrary input')
    assert 'requested_slot' not in collect.run_metadata(NOW)
