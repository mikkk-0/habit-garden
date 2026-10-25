"""Event-driven desktop reminder scheduler."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from .db import HabitStore


log = logging.getLogger(__name__)


def desktop_notify(name: str) -> None:
    executable = shutil.which("notify-send")
    if not executable:
        log.warning("notify-send не найден; уведомление для %s не показано", name)
        return
    try:
        icon = str(Path(__file__).parent / "static" / "icon.svg")
        subprocess.run(
            [executable, "-a", "Сад привычек", "-i", icon, "Время для привычки", f"«{name}» ещё не выполнено сегодня"],
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        log.exception("Не удалось показать уведомление для %s", name)


class ReminderScheduler:
    def __init__(
        self,
        store: HabitStore,
        notify: Callable[[str], None] = desktop_notify,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.store = store
        self.notify = notify
        self.clock = clock
        self._changed = threading.Event()
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, name="habit-reminders", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def wake(self) -> None:
        self._changed.set()

    def stop(self) -> None:
        self._stopping.set()
        self._changed.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3)

    def process_due(self) -> int:
        reminders = self.store.claim_due_reminders(self.clock())
        for reminder in reminders:
            self.notify(reminder["name"])
        return len(reminders)

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                self.process_due()
                now = self.clock()
                upcoming = self.store.next_reminder(now)
                # Check at most hourly for system clock and daylight-saving changes.
                timeout = min(3600, max(0, (upcoming - now).total_seconds())) if upcoming else 3600
                self._changed.wait(timeout)
                self._changed.clear()
            except Exception:
                log.exception("Ошибка планировщика напоминаний")
                self._changed.wait(60)
                self._changed.clear()
