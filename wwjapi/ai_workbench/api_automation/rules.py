from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None


def is_overdue_before_today(value: Any, today: date) -> bool:
    parsed = parse_datetime(value)
    return parsed is not None and parsed.date() < today


def highest_priority(values: list[str]) -> str | None:
    order = {"常规": 1, "重要": 2, "紧急": 3}
    return max(values, key=lambda value: order.get(value, 0), default=None)


def count_ai_charges(
    *,
    todo_categories: list[str],
    called_cards: list[str],
) -> int:
    """Current confirmed billing baseline: each todo category/card call counts once."""
    return len(set(todo_categories)) + len(set(called_cards))
