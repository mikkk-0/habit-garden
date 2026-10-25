"""Compatibility entry point for the local API and the desktop application."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import urllib.error
import urllib.request

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сад привычек — локальный трекер привычек")
    parser.add_argument("command", choices=("launch", "background", "stop", "serve"), nargs="?", default="launch")
    args = parser.parse_args(argv)
    if args.command != "serve":
        from .desktop import main as desktop_main
        return desktop_main([args.command])

    # Kept for transitioning a running instance from the earlier browser version.
    store = HabitStore(default_database_path())
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        serve(store, PORT)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
