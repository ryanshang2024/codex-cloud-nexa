#!/usr/bin/env bash
set -euo pipefail
nexa_project_root="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$nexa_project_root"
if [ ! -x .venv/bin/python ]; then
  echo "This folder has not been initialized; no project services to stop."
  exit 0
fi
.venv/bin/python scripts/dev.py down
