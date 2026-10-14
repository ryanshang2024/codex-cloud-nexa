#!/usr/bin/env bash
# Repository-owned, reviewed setup; no external shell installers.
set -euo pipefail
nexa_project_root="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$nexa_project_root"
export UV_CACHE_DIR="$PWD/.local/uv-cache"
export npm_config_cache="$PWD/.local/npm-cache"
export NEXT_TELEMETRY_DISABLED=1
mkdir -p .local
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.12 .venv
fi
uv pip install --python .venv/bin/python --require-hashes --only-binary :all: -r requirements.lock
docker image inspect postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24 >/dev/null 2>&1 || docker pull postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
.venv/bin/python scripts/dev.py init
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run build
