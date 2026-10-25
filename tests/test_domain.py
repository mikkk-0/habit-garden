import unittest
from datetime import date

from habit_garden.domain import habit_stats


class HabitStatsTests(unittest.TestCase):
    def test_new_habit(self):
        self.assertEqual(
            habit_stats(date(2026, 10, 25), set(), date(2026, 10, 25)),
            {"total_days": 1, "completed_days": 0, "completion_percent": 0, "streak": 0, "completed_today": False},
        )

    def test_streak_remains_active_until_today_ends(self):
        result = habit_stats(
            date(2026, 10, 20),
            {date(2026, 10, 20), date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24)},
            date(2026, 10, 25),
        )
        self.assertEqual(result["streak"], 3)
        self.assertEqual(result["total_days"], 6)
        self.assertEqual(result["completed_days"], 4)
        self.assertEqual(result["completion_percent"], 67)

    def test_completed_today_extends_streak_and_ignores_future(self):
        result = habit_stats(date(2026, 10, 23), {date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)}, date(2026, 10, 25))
        self.assertEqual(result["streak"], 2)
        self.assertEqual(result["completion_percent"], 67)
        self.assertTrue(result["completed_today"])


if __name__ == "__main__":
    unittest.main()
