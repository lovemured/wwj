#!/usr/bin/env python3
"""Verify Lead owner and collaborator visibility in AI workbench todos.

Use a disposable Lead owned by the old user. The script changes only owner and
assist_user_ids, then deletes the Lead when --delete-after is supplied.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_workbench.verify_change_rules import (  # noqa: E402
    CRM_BASE_URL,
    crm_headers,
    delete_lead,
    find_lead,
    request_json,
    require_success,
    todo_items,
)


def update_assignment(
    token: str, lead_id: int, owner_id: int, assist_user_ids: list[int]
) -> None:
    response, payload = request_json(
        "PUT",
        f"{CRM_BASE_URL}/api/v2/leads/{lead_id}",
        headers={**crm_headers(token), "Content-Type": "application/json"},
        body={
            "lead": {
                "user_id": owner_id,
                "assist_user_ids": assist_user_ids,
            }
        },
    )
    require_success(response, payload)


def get_assignment(token: str, lead_id: int) -> tuple[int | None, list[int]]:
    response, payload = request_json(
        "GET",
        f"{CRM_BASE_URL}/api/v2/leads/{lead_id}",
        headers=crm_headers(token),
    )
    require_success(response, payload)
    data = payload.get("data") or {}
    owner = data.get("user") or {}
    owner_id = owner.get("id") if isinstance(owner, dict) else None
    assistants = data.get("assist_user_ids") or []
    if not assistants:
        assistants = [
            item.get("id")
            for item in (data.get("assist_users") or [])
            if isinstance(item, dict) and item.get("id")
        ]
    return owner_id, [int(item) for item in assistants]


def visible(token: str, lead_id: int, start_date: str, end_date: str) -> bool:
    return find_lead(todo_items(token, start_date, end_date), lead_id) is not None


def wait_visibility(
    label: str,
    check: Any,
    expected: bool,
    *,
    wait_seconds: int,
    interval_seconds: int,
) -> None:
    deadline = time.monotonic() + wait_seconds
    while True:
        actual = bool(check())
        if actual == expected:
            print(f"PASS {label}: {actual}")
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"timeout waiting for {label}: expected={expected}, actual={actual}"
            )
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lead-id", required=True, type=int)
    parser.add_argument("--period-start", default="2026-07-30")
    parser.add_argument("--period-end", default="2026-07-30")
    parser.add_argument("--old-owner-id", type=int, default=1000025901)
    parser.add_argument("--new-user-id", type=int, default=1000029992)
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument("--delete-after", action="store_true")
    args = parser.parse_args()

    old_token = os.getenv("AIWB_OLD_TOKEN")
    new_token = os.getenv("AIWB_NEW_TOKEN")
    if not old_token or not new_token:
        print("AIWB_OLD_TOKEN and AIWB_NEW_TOKEN are required", file=sys.stderr)
        return 2

    actual_owner, original_assist = get_assignment(old_token, args.lead_id)
    if not actual_owner:
        raise RuntimeError("could not read original owner")
    if actual_owner != args.old_owner_id:
        raise RuntimeError(
            f"lead owner mismatch: expected old owner={args.old_owner_id}, "
            f"actual={actual_owner}; prepare the test data first"
        )
    old_owner = args.old_owner_id
    new_owner = args.new_user_id
    print(f"Lead {args.lead_id}: old_owner={old_owner}, new_user={new_owner}")
    print(f"Original assist_user_ids: {original_assist}")
    deleted = False

    try:
        print("[1] Change owner from old user to new user")
        update_assignment(old_token, args.lead_id, new_owner, [])
        wait_visibility(
            "old owner no longer sees todo",
            lambda: visible(old_token, args.lead_id, args.period_start, args.period_end),
            False,
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )
        wait_visibility(
            "new owner sees todo",
            lambda: visible(new_token, args.lead_id, args.period_start, args.period_end),
            True,
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )

        print("[2] Restore old owner and add new user as collaborator")
        update_assignment(old_token, args.lead_id, old_owner, [new_owner])
        wait_visibility(
            "old owner still sees todo as owner",
            lambda: visible(old_token, args.lead_id, args.period_start, args.period_end),
            True,
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )
        wait_visibility(
            "collaborator sees todo",
            lambda: visible(new_token, args.lead_id, args.period_start, args.period_end),
            True,
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )

        if args.delete_after:
            print("[3] Delete disposable Lead")
            delete_lead(old_token, args.lead_id)
            wait_visibility(
                "todo removed after deletion",
                lambda: visible(new_token, args.lead_id, args.period_start, args.period_end),
                False,
                wait_seconds=args.wait_seconds,
                interval_seconds=args.interval_seconds,
            )
            deleted = True
    finally:
        if args.delete_after and not deleted:
            try:
                delete_lead(old_token, args.lead_id)
                print("Cleanup: disposable Lead deleted")
            except Exception as exc:  # pragma: no cover - cleanup diagnostics
                print(f"Cleanup failed: {exc}", file=sys.stderr)
        elif not args.delete_after:
            update_assignment(old_token, args.lead_id, old_owner, original_assist)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
