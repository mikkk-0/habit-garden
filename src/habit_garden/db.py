"""SQLite storage: one row per habit and one row per completed day."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from .domain import habit_stats
from .emoji_catalog import DEFAULT_EMOJI, allowed_emojis


TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class ValidationError(ValueError):
    pass


def default_database_path() -> Path:
    explicit = os.getenv("HABIT_GARDEN_DB")
    if explicit:
        return Path(explicit).expanduser()
    base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "habit-garden" / "habits.db"


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not (name := value.strip()) or len(name) > 80:
        raise ValidationError("Название должно содержать от 1 до 80 символов")
    return name


def _validate_symbol(value: object) -> str:
    if not isinstance(value, str) or not (symbol := value.strip()) or len(symbol) > 8:
        raise ValidationError("Символ должен содержать от 1 до 8 символов")
    return symbol


def _validate_emoji(value: object) -> str:
    if not isinstance(value, str) or value not in allowed_emojis():
        raise ValidationError("Выберите эмодзи из списка")
    return value


def _validate_time(value: object) -> str:
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise ValidationError("Время должно быть в формате ЧЧ:ММ")
    return value


class HabitStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_on TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
                symbol_off TEXT NOT NULL DEFAULT '○',
                symbol_on TEXT NOT NULL DEFAULT '●',
                label_emoji TEXT NOT NULL DEFAULT '🌱',
                reminder_time TEXT NOT NULL DEFAULT '20:00',
                last_notified_on TEXT
            );
            CREATE TABLE IF NOT EXISTS completions (
                habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                PRIMARY KEY (habit_id, day)
            ) WITHOUT ROWID;
            """
        )
        # Existing installations keep their tasks and completion history.
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(habits)")}
        if "label_emoji" not in columns:
            with self._connection:
                self._connection.execute("ALTER TABLE habits ADD COLUMN label_emoji TEXT NOT NULL DEFAULT '🌱'")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _row(self, habit_id: int) -> sqlite3.Row:
        row = self._connection.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        if row is None:
            raise KeyError("Задание не найдено")
        return row

    def create(self, data: dict, today: date | None = None) -> dict:
        today = today or date.today()
        name = _validate_name(data.get("name"))
        off = _validate_symbol(data.get("symbol_off", "○"))
        on = _validate_symbol(data.get("symbol_on", "●"))
        label = _validate_emoji(data.get("label_emoji", DEFAULT_EMOJI))
        reminder = _validate_time(data.get("reminder_time", "20:00"))
        with self._lock, self._connection:
            cur = self._connection.execute(
                "INSERT INTO habits (name, created_on, symbol_off, symbol_on, label_emoji, reminder_time) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, today.isoformat(), off, on, label, reminder),
            )
            return self.get(cur.lastrowid, today)

    def get(self, habit_id: int, today: date | None = None) -> dict:
        today = today or date.today()
        with self._lock:
            row = self._row(habit_id)
            days = {
                date.fromisoformat(result["day"])
                for result in self._connection.execute(
                    "SELECT day FROM completions WHERE habit_id = ? AND day <= ?",
                    (habit_id, today.isoformat()),
                )
            }
            item = {key: row[key] for key in row.keys() if key != "last_notified_on"}
            item["archived"] = bool(item["archived"])
            item.update(habit_stats(date.fromisoformat(row["created_on"]), days, today))
            return item

    def list(self, today: date | None = None) -> list[dict]:
        today = today or date.today()
        with self._lock:
            ids = [row[0] for row in self._connection.execute("SELECT id FROM habits ORDER BY id DESC")]
            return [self.get(habit_id, today) for habit_id in ids]

    def update(self, habit_id: int, data: dict, today: date | None = None) -> dict:
        if not isinstance(data, dict):
            raise ValidationError("Неверный формат данных")
        allowed = {"name", "symbol_off", "symbol_on", "label_emoji", "reminder_time", "archived"}
        if not data or set(data) - allowed:
            raise ValidationError("Нет допустимых полей для изменения")
        values = {}
        for key, value in data.items():
            if key == "name":
                values[key] = _validate_name(value)
            elif key.startswith("symbol_"):
                values[key] = _validate_symbol(value)
            elif key == "label_emoji":
                values[key] = _validate_emoji(value)
            elif key == "reminder_time":
                values[key] = _validate_time(value)
            elif type(value) is bool:
                values[key] = int(value)
            else:
                raise ValidationError("Архив должен быть логическим значением")
        with self._lock, self._connection:
            self._row(habit_id)
            columns = ", ".join(f"{key} = ?" for key in values)
            self._connection.execute(
                f"UPDATE habits SET {columns} WHERE id = ?", (*values.values(), habit_id)
            )
            return self.get(habit_id, today)

    def set_completion(self, habit_id: int, day: date, completed: bool, today: date | None = None) -> dict:
        today = today or date.today()
        if type(completed) is not bool:
            raise ValidationError("Статус выполнения должен быть логическим значением")
        with self._lock, self._connection:
            row = self._row(habit_id)
            if row["archived"]:
                raise ValidationError("Архивное задание сначала нужно восстановить")
            if day < date.fromisoformat(row["created_on"]) or day > today:
                raise ValidationError("Дату до создания или в будущем отметить нельзя")
            if completed:
                self._connection.execute(
                    "INSERT OR IGNORE INTO completions (habit_id, day) VALUES (?, ?)",
                    (habit_id, day.isoformat()),
                )
            else:
                self._connection.execute(
                    "DELETE FROM completions WHERE habit_id = ? AND day = ?",
                    (habit_id, day.isoformat()),
                )
            return self.get(habit_id, today)

    def month(self, habit_id: int, year: int, month: int) -> list[str]:
        if not (1 <= year <= 9999 and 1 <= month <= 12):
            raise ValidationError("Неверный месяц")
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 and year < 9999 else None
        if end is None and month < 12:
            end = date(year, month + 1, 1)
        with self._lock:
            self._row(habit_id)
            query = "SELECT day FROM completions WHERE habit_id = ? AND day >= ?"
            params: list = [habit_id, start.isoformat()]
            if end:
                query += " AND day < ?"
                params.append(end.isoformat())
            return [row[0] for row in self._connection.execute(query, params)]

    def claim_due_reminders(self, now: datetime) -> list[dict]:
        """Atomically claim reminders due today; each habit alerts at most once/day."""
        day = now.date().isoformat()
        clock = now.strftime("%H:%M")
        with self._lock, self._connection:
            rows = self._connection.execute(
                """SELECT h.id, h.name FROM habits h
                   WHERE h.archived = 0 AND h.created_on <= ?
                     AND h.reminder_time <= ?
                     AND (h.last_notified_on IS NULL OR h.last_notified_on < ?)
                     AND NOT EXISTS (
                       SELECT 1 FROM completions c WHERE c.habit_id = h.id AND c.day = ?
                     )""",
                (day, clock, day, day),
            ).fetchall()
            if rows:
                self._connection.executemany(
                    "UPDATE habits SET last_notified_on = ? WHERE id = ?",
                    ((day, row["id"]) for row in rows),
                )
            return [{"id": row["id"], "name": row["name"]} for row in rows]

    def next_reminder(self, now: datetime) -> datetime | None:
        """Find when to wake. API edits wake the scheduler separately."""
        today = now.date()
        with self._lock:
            rows = self._connection.execute(
                """SELECT h.id, h.reminder_time, h.last_notified_on,
                          EXISTS(SELECT 1 FROM completions c
                                 WHERE c.habit_id = h.id AND c.day = ?) AS done_today
                   FROM habits h WHERE h.archived = 0""",
                (today.isoformat(),),
            ).fetchall()
        candidates = []
        for row in rows:
            hour, minute = map(int, row["reminder_time"].split(":"))
            due = datetime.combine(today, datetime.min.time()).replace(hour=hour, minute=minute)
            if row["last_notified_on"] == today.isoformat() or row["done_today"]:
                due += timedelta(days=1)
            candidates.append(due)
        return min(candidates) if candidates else None
