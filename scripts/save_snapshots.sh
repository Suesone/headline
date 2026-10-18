#!/usr/bin/env bash
set -euo pipefail
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
# A maintainer may push while feeds are being collected. Never force push.
for attempt in 1 2 3; do
  git add state public/data
  if git diff --cached --quiet; then
    break
  fi
  git commit -m 'Update news snapshots [skip ci]'
  if git push origin HEAD:main; then
    break
  fi
  if [ "$attempt" = 3 ]; then
    echo 'Remote changed repeatedly; stopping before deploying stale code.' >&2
    exit 1
  fi
  # Recollect with the latest code/config/history instead of overwriting it.
  git fetch origin main
  git reset --hard origin/main
  python -m pip install -r requirements.txt
  python -m pytest -q
  node --test tests/*.test.cjs
  npm ci --prefix cloudflare --ignore-scripts
  npm test --prefix cloudflare
  python -m scripts.collect
  python -m scripts.report
done
