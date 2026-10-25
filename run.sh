#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'from PySide6.QtWebEngineWidgets import QWebEngineView' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ "${1:-launch}" = "stop" ]; then
  exec .venv/bin/python -m habit_garden.desktop stop
fi
log_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}/habit-garden
mkdir -p "$log_dir"
GARDEN_COMMAND=${1:-launch} GARDEN_LOG="$log_dir/app.log" .venv/bin/python - <<'PY'
import os
import subprocess
import sys

with open(os.environ["GARDEN_LOG"], "ab", buffering=0) as log:
    subprocess.Popen(
        [sys.executable, "-m", "habit_garden.desktop", os.environ["GARDEN_COMMAND"]],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
PY
