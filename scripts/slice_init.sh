#!/usr/bin/env bash
set -euo pipefail

# 1) Go to repo root
cd "$(dirname "${BASH_SOURCE[0]}")/.." || {
  echo "ERROR: cannot cd to repo root"; exit 1;
}

# 2) Ensure venv exists
if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found. Create it with:"
  echo "  python -m venv .venv"
  exit 1
fi

# 3) Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 4) Load .env into env
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 5) Python path
export PYTHONPATH=src

# 6) DB sanity
python - << 'PYEOF'
from slice.db import ping
ping()
print("Slice DB ping OK")
PYEOF

echo "Slice environment initialized."
