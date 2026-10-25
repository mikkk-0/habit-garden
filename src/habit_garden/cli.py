"""Start or stop the local app and open its desktop window."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from .db import HabitStore, default_database_path
from .server import serve


PORT = 8765
URL = f"http://127.0.0.1:{PORT}"


def health() -> dict | None:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=0.5) as response:
            data = json.load(response)
            return data if data.get("app") == "habit-garden" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def start_background() -> None:
    if health():
        return
    data_dir = default_database_path().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    log = open(data_dir / "app.log", "ab", buffering=0)
    try:
        subprocess.Popen(
            [sys.executable, "-m", "habit_garden.cli", "serve"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log.close()
    for _ in range(40):
        if health():
            return
        time.sleep(0.1)
    raise RuntimeError(f"Сервер не запустился. Проверьте {data_dir / 'app.log'}")


def open_window() -> None:
    browser = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if browser:
        subprocess.Popen([browser, f"--app={URL}", "--class=HabitGarden"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif not webbrowser.open(URL):
        print(f"Откройте {URL}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Сад привычек — локальный трекер привычек")
    parser.add_argument("command", choices=("launch", "serve", "stop"), nargs="?", default="launch")
    args = parser.parse_args(argv)
    if args.command == "serve":
        store = HabitStore(default_database_path())
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            serve(store, PORT)
        finally:
            store.close()
    elif args.command == "stop":
        status = health()
        if status:
            os.kill(int(status["pid"]), signal.SIGTERM)
            print("Сад привычек остановлен")
        else:
            print("Сад привычек уже остановлен")
    else:
        start_background()
        open_window()


if __name__ == "__main__":
    main()
