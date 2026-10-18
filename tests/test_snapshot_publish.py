"""Reproduce a real non-fast-forward push without any network access."""
from pathlib import Path
import os
import shutil
import subprocess

from scripts.collect import ROOT


def test_publish_recollects_on_latest_main_when_another_commit_arrives(tmp_path):
    def git(*args, cwd=tmp_path):
        return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)
    remote = tmp_path / 'remote.git'
    git('init', '--bare', '--initial-branch=main', str(remote))
    local = tmp_path / 'local'
    git('clone', str(remote), str(local))
    git('config', 'user.name', 'Test', cwd=local)
    git('config', 'user.email', 'test@example.test', cwd=local)
    (local / 'config.txt').write_text('old-config')
    (local / 'state').mkdir(); (local / 'public/data').mkdir(parents=True)
    (local / 'state/news.json').write_text('old-history')
    (local / 'public/data/news.json').write_text('old-snapshot')
    git('add', '.', cwd=local); git('commit', '-m', 'initial', cwd=local)
    git('push', 'origin', 'main', cwd=local)
    other = tmp_path / 'other'; git('clone', str(remote), str(other))
    git('config', 'user.name', 'Other', cwd=other)
    git('config', 'user.email', 'other@example.test', cwd=other)
    (other / 'config.txt').write_text('latest-config')
    git('add', '.', cwd=other); git('commit', '-m', 'maintainer update', cwd=other)
    git('push', 'origin', 'main', cwd=other)
    (local / 'public/data/news.json').write_text('stale-collected-data')
    bins = tmp_path / 'bin'; bins.mkdir()
    python = bins / 'python'
    python.write_text('#!/bin/sh\nif [ "$*" = "-m scripts.collect" ]; then cp config.txt public/data/news.json; cp config.txt state/news.json; fi\n')
    python.chmod(0o755)
    for command in ['node', 'npm']:
        stub = bins / command; stub.write_text('#!/bin/sh\nexit 0\n'); stub.chmod(0o755)
    script = tmp_path / 'save.sh'; shutil.copy(ROOT / 'scripts/save_snapshots.sh', script)
    result = subprocess.run(['bash', str(script)], cwd=local,
                            env={**os.environ, 'PATH': str(bins) + os.pathsep + os.environ['PATH']},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'rejected' in result.stderr
    assert (local / 'config.txt').read_text() == 'latest-config'
    assert (local / 'public/data/news.json').read_text() == 'latest-config'
    assert git('rev-parse', 'HEAD', cwd=local).stdout == git('rev-parse', 'main', cwd=remote).stdout
