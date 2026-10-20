#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/projects"
for dir in */; do
  echo "== ${dir%/}"
  if [ -f "$dir/package.json" ]; then
    (cd "$dir" && node --test 2>&1 | grep -E "^# (pass|fail)")
  else
    (cd "$dir" && python3 -m unittest discover -s tests 2>&1 | tail -1)
  fi
done
