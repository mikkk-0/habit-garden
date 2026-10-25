"""Local presentation order, deliberately separate from the habit database."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from .db import ValidationError


def default_order_path() -> Path:
    explicit = os.getenv("HABIT_GARDEN_ORDER")
    if explicit:
        return Path(explicit).expanduser()
    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "habit-garden" / "order.json"


class HabitOrder:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.RLock()

    def load(self) -> list[int]:
        with self._lock:
            try:
                ids = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return []
            except (OSError, ValueError):
                return []
            if not isinstance(ids, list) or any(type(item) is not int or item <= 0 for item in ids):
                return []
            if len(ids) != len(set(ids)):
                return []
            return ids

    def save(self, ids: object, existing_ids: set[int]) -> None:
        if not isinstance(ids, list) or any(type(item) is not int or item <= 0 for item in ids):
            raise ValidationError("Порядок заданий должен быть списком ID")
        if len(ids) != len(set(ids)) or set(ids) != existing_ids:
            raise ValidationError("Список заданий изменился — обновите страницу")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=".order-", delete=False) as file:
                    temporary = Path(file.name)
                    json.dump(ids, file, separators=(",", ":"))
                    file.write("\n")
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def sort(self, tasks: list[dict]) -> list[dict]:
        order = self.load()
        by_id = {task["id"]: task for task in tasks}
        saved_ids = set(order)
        # Newly created tasks keep the existing newest-first default.
        return [task for task in tasks if task["id"] not in saved_ids] + [by_id[task_id] for task_id in order if task_id in by_id]
