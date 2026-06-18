#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 is required but was not found on PATH." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if ! python - <<'PY' >/dev/null 2>&1
import streamlit  # noqa: F401
import yt_dlp  # noqa: F401
PY
then
  python -m ensurepip --upgrade >/dev/null
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r "$ROOT_DIR/requirements.txt"
fi

exec python -m streamlit run "$ROOT_DIR/app.py"
