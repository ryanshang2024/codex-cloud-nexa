#!/usr/bin/env bash
# Reviewed project launcher; dependencies are installed from the repository locks.
set -euo pipefail
nexa_project_root="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$nexa_project_root"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This shortcut is for macOS. Linux: bash scripts/install.sh then .venv/bin/python scripts/dev.py up."
  exit 1
fi
for nexa_tool in uv node npm docker; do
  if ! command -v "$nexa_tool" >/dev/null 2>&1; then
    echo "Missing $nexa_tool. See docs/macos-local-run.md for prerequisites."
    exit 1
  fi
done
if ! docker info >/dev/null 2>&1; then
  echo "Start Docker Desktop and wait for its engine to be ready, then run this shortcut again."
  exit 1
fi
node -e 'if(Number(process.versions.node.split(".")[0])<24){console.error("Use Node.js 24 or later for this package.");process.exit(1)}'
bash scripts/install.sh
.venv/bin/python scripts/dev.py up
echo "NEXA is running locally. Private sign-in details: .local/demo-logins.json. Do not upload that file."
open 'http://127.0.0.1:3000/'
