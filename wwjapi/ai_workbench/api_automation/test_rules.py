from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from .rules import count_ai_charges, highest_priority, is_overdue_before_today


def load_cases() -> dict:
    path = Path(__file__).parent / "data" / "rule_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case", load_cases()["overdue_before_today"]
)
def test_overdue_excludes_today(case: dict) -> None:
    assert is_overdue_before_today(
        case["value"], date.fromisoformat(case["today"])
    ) is case["expected"]


@pytest.mark.parametrize("case", load_cases()["priority_cases"])
def test_same_record_uses_highest_priority(
    case: dict,
) -> None:
    assert highest_priority(case["values"]) == case["expected"]


def test_ai_charge_counts_categories_and_cards_once() -> None:
    case = load_cases()["charge_case"]
    assert count_ai_charges(
        todo_categories=case["todo_categories"],
        called_cards=case["called_cards"],
    ) == case["expected"]
