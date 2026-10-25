"""Date and habit statistics. Independent of the desktop interface."""

from __future__ import annotations

from datetime import date, timedelta


def habit_stats(created_on: date, completed: set[date], today: date) -> dict:
    """Count the current streak through today, or through yesterday if still pending.

    A pending task retains yesterday's streak until the day ends. Future dates never
    count toward progress. The creation day is included in the denominator.
    """
    total_days = max(1, (today - created_on).days + 1)
    valid = {day for day in completed if created_on <= day <= today}
    count = len(valid)
    cursor = today if today in valid else today - timedelta(days=1)
    streak = 0
    while cursor >= created_on and cursor in valid:
        streak += 1
        cursor -= timedelta(days=1)
    return {
        "total_days": total_days,
        "completed_days": count,
        "completion_percent": round(count * 100 / total_days),
        "streak": streak,
        "completed_today": today in valid,
    }
