"""Pure helpers for local-calendar diagnostics."""

from __future__ import annotations


def roll_daily_counter(
    stored_date: str,
    count: int,
    today: str,
) -> tuple[str, int, bool]:
    """Return the current-day counter and whether a rollover occurred."""
    if stored_date == today:
        return stored_date, count, False
    return today, 0, True
