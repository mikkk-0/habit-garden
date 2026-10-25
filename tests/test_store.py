import tempfile
import unittest
import sqlite3
from datetime import date, datetime
from pathlib import Path

from habit_garden.db import HabitStore, ValidationError
from habit_garden.reminders import ReminderScheduler


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = HabitStore(Path(self.temp.name) / "habits.db")
        self.today = date(2026, 10, 25)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_create_complete_uncomplete_and_archive(self):
        task = self.store.create({"name": "  Читать  ", "reminder_time": "19:30"}, self.today)
        self.assertEqual(task["name"], "Читать")
        self.assertEqual(task["completion_percent"], 0)
        task = self.store.set_completion(task["id"], self.today, True, self.today)
        self.assertEqual((task["streak"], task["completion_percent"]), (1, 100))
        self.assertEqual(self.store.month(task["id"], 2026, 10), ["2026-10-25"])
        task = self.store.set_completion(task["id"], self.today, False, self.today)
        self.assertEqual(task["streak"], 0)
        self.assertEqual(self.store.month(task["id"], 2026, 10), [])
        task = self.store.update(task["id"], {"archived": True}, self.today)
        self.assertTrue(task["archived"])
        with self.assertRaises(ValidationError):
            self.store.set_completion(task["id"], self.today, True, self.today)
        task = self.store.update(task["id"], {"archived": False}, self.today)
        self.assertFalse(task["archived"])

    def test_rejects_dates_outside_lifetime_and_bad_fields(self):
        task = self.store.create({"name": "Вода"}, self.today)
        with self.assertRaises(ValidationError):
            self.store.set_completion(task["id"], date(2026, 10, 24), True, self.today)
        with self.assertRaises(ValidationError):
            self.store.set_completion(task["id"], date(2026, 10, 26), True, self.today)
        with self.assertRaises(ValidationError):
            self.store.update(task["id"], {"reminder_time": "25:00"}, self.today)
        with self.assertRaises(ValidationError):
            self.store.update(task["id"], {"archived": "true"}, self.today)

    def test_emoji_label_can_be_created_and_changed(self):
        task = self.store.create({"name": "Читать", "label_emoji": "📚"}, self.today)
        self.assertEqual(task["label_emoji"], "📚")
        changed = self.store.update(task["id"], {"label_emoji": "🌱"}, self.today)
        self.assertEqual(changed["label_emoji"], "🌱")
        with self.assertRaises(ValidationError):
            self.store.update(task["id"], {"label_emoji": "не эмодзи"}, self.today)

    def test_old_database_is_migrated_without_losing_completion(self):
        path = Path(self.temp.name) / "old.db"
        with sqlite3.connect(path) as connection:
            connection.executescript("""
                CREATE TABLE habits (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_on TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0, symbol_off TEXT NOT NULL DEFAULT '○',
                    symbol_on TEXT NOT NULL DEFAULT '●', reminder_time TEXT NOT NULL DEFAULT '20:00',
                    last_notified_on TEXT
                );
                CREATE TABLE completions (habit_id INTEGER NOT NULL, day TEXT NOT NULL,
                    PRIMARY KEY (habit_id, day)) WITHOUT ROWID;
                INSERT INTO habits (id, name, created_on) VALUES (1, 'Старое задание', '2026-10-25');
                INSERT INTO completions (habit_id, day) VALUES (1, '2026-10-25');
            """)
        migrated = HabitStore(path)
        try:
            task = migrated.get(1, self.today)
            self.assertEqual(task["label_emoji"], "🌱")
            self.assertTrue(task["completed_today"])
        finally:
            migrated.close()

    def test_reminders_only_for_due_unfinished_active_habits_once_per_day(self):
        due = self.store.create({"name": "Читать", "reminder_time": "18:00"}, self.today)
        later = self.store.create({"name": "Прогулка", "reminder_time": "21:00"}, self.today)
        done = self.store.create({"name": "Вода", "reminder_time": "18:00"}, self.today)
        archived = self.store.create({"name": "Заметки", "reminder_time": "18:00"}, self.today)
        self.store.set_completion(done["id"], self.today, True, self.today)
        self.store.update(archived["id"], {"archived": True}, self.today)
        messages = []
        scheduler = ReminderScheduler(self.store, notify=messages.append, clock=lambda: datetime(2026, 10, 25, 19))
        self.assertEqual(scheduler.process_due(), 1)
        self.assertEqual(scheduler.process_due(), 0)
        self.assertEqual(messages, ["Читать"])
        self.assertEqual(self.store.next_reminder(datetime(2026, 10, 25, 19)), datetime(2026, 10, 25, 21))
        self.assertEqual(later["name"], "Прогулка")
        self.assertEqual(due["name"], "Читать")


if __name__ == "__main__":
    unittest.main()
