#!/usr/bin/env python3
"""Verify AI workbench todo changes for a disposable Lead.

The script does not create data. Use an existing disposable lead, or create
one with lead/batch_create_lead.py first. By default it restores the original
revisit_remind_at. Pass --delete-after only for a disposable lead.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import requests


CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://lxcrm-test.weiwenjia.com").rstrip("/")
AIWB_BASE_URL = os.getenv(
    "AIWB_BASE_URL", "https://lxcrm-api-test.weiwenjia.com"
).rstrip("/")
WORKBENCH_ID = int(os.getenv("AIWB_WORKBENCH_ID", "1"))
TIMEOUT = float(os.getenv("AIWB_TIMEOUT", "20"))


def crm_headers(token: str) -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Token token={token}"}


def aiwb_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f'Token token="{token}",device="web"',
        "Origin": "https://lxcrm-test.weiwenjia.com",
        "Referer": "https://lxcrm-test.weiwenjia.com/",
        "X-LX-GID": "",
    }


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[requests.Response, dict[str, Any]]:
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=body,
        timeout=TIMEOUT,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"non-JSON response: {method} {url} status={response.status_code}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"response root must be an object: {payload!r}")
    return response, payload


def require_success(response: requests.Response, payload: dict[str, Any]) -> None:
    if response.status_code >= 400 or payload.get("code") not in (0, "0"):
        raise RuntimeError(
            f"API failed: status={response.status_code}, payload={payload}"
        )


def get_lead(token: str, lead_id: int) -> dict[str, Any]:
    response, payload = request_json(
        "GET",
        f"{CRM_BASE_URL}/api/v2/leads/{lead_id}",
        headers=crm_headers(token),
    )
    require_success(response, payload)
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("id") != lead_id:
        raise RuntimeError(f"lead not found or unexpected response: {payload}")
    return data


def update_revisit(token: str, lead_id: int, revisit_at: str) -> None:
    response, payload = request_json(
        "PUT",
        f"{CRM_BASE_URL}/api/v2/leads/{lead_id}",
        headers={**crm_headers(token), "Content-Type": "application/json"},
        body={"lead": {"revisit_remind_at": revisit_at}},
    )
    require_success(response, payload)


def delete_lead(token: str, lead_id: int) -> None:
    response, payload = request_json(
        "DELETE",
        f"{CRM_BASE_URL}/api/v2/leads/{lead_id}",
        headers=crm_headers(token),
    )
    require_success(response, payload)


def todo_items(
    token: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    response, payload = request_json(
        "GET",
        f"{AIWB_BASE_URL}/api/pc/ai_workbenches/todos_index",
        headers=aiwb_headers(token),
        params={
            "ai_workbench_id": WORKBENCH_ID,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    require_success(response, payload)
    data = payload.get("data") or {}
    items = data.get("list") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RuntimeError(f"todo response has no list: {payload}")
    return [item for item in items if isinstance(item, dict)]


def find_lead(items: list[dict[str, Any]], lead_id: int) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in items
            if item.get("entity_type") == "Lead"
            and str(item.get("entity_id")) == str(lead_id)
        ),
        None,
    )


def find_lead_with_due(
    items: list[dict[str, Any]], lead_id: int, expected: str
) -> dict[str, Any] | None:
    item = find_lead(items, lead_id)
    if item and str(item.get("due_at", "")).startswith(expected.replace(" ", "T")):
        return item
    return None


def wait_for(
    label: str,
    check: Any,
    *,
    wait_seconds: int,
    interval_seconds: int,
) -> Any:
    deadline = time.monotonic() + wait_seconds
    last_value = None
    while True:
        last_value = check()
        if last_value:
            return last_value
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"timeout waiting for {label} after {wait_seconds}s; last={last_value}"
            )
        time.sleep(interval_seconds)


def assert_due_at(item: dict[str, Any], expected: str) -> None:
    due_at = str(item.get("due_at", ""))
    expected_prefix = expected.replace(" ", "T")
    if not due_at.startswith(expected_prefix):
        raise RuntimeError(f"due_at mismatch: expected={expected}, actual={due_at}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lead-id", required=True, type=int)
    parser.add_argument("--period-start", default="2026-07-30")
    parser.add_argument("--period-end", default="2026-07-31")
    parser.add_argument("--period-time", default="18:00")
    parser.add_argument("--outside-date", default="2026-08-01")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=5)
    parser.add_argument("--delete-after", action="store_true")
    args = parser.parse_args()

    token = os.getenv("AIWB_TOKEN")
    if not token:
        print("AIWB_TOKEN is required", file=sys.stderr)
        return 2

    original = get_lead(token, args.lead_id)
    original_revisit = original.get("revisit_remind_at")
    period_at = f"{args.period_end} {args.period_time}"
    period_start_at = f"{args.period_start} {args.period_time}"
    outside_at = f"{args.outside_date} {args.period_time}"
    deleted = False
    print(f"Lead {args.lead_id}: {original.get('name')}")
    print(f"Original revisit_remind_at: {original_revisit}")

    try:
        print(f"[1] Set revisit inside period: {period_start_at}")
        update_revisit(token, args.lead_id, period_start_at)
        item = wait_for(
            "todo appears inside period",
            lambda: find_lead_with_due(
                todo_items(token, args.period_start, args.period_start),
                args.lead_id,
                period_start_at,
            ),
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )
        assert_due_at(item, period_start_at)
        print(f"PASS inside period: {item}")

        print(f"[2] Move revisit outside period: {outside_at}")
        update_revisit(token, args.lead_id, outside_at)
        wait_for(
            "todo removed after moving outside period",
            lambda: find_lead(
                todo_items(token, args.period_start, args.period_end), args.lead_id
            )
            is None,
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )
        print("PASS outside period: lead is absent from the selected period")

        print(f"[3] Move revisit back into period: {period_at}")
        update_revisit(token, args.lead_id, period_at)
        item = wait_for(
            "todo refreshed after moving back inside period",
            lambda: find_lead_with_due(
                todo_items(token, args.period_end, args.period_end),
                args.lead_id,
                period_at,
            ),
            wait_seconds=args.wait_seconds,
            interval_seconds=args.interval_seconds,
        )
        assert_due_at(item, period_at)
        old_item = find_lead(
            todo_items(token, args.period_start, args.period_start), args.lead_id
        )
        if old_item is not None:
            raise RuntimeError(f"stale todo remains on old date: {old_item}")
        print(f"PASS refreshed period: {item}")

        if args.delete_after:
            print("[4] Delete disposable lead")
            delete_lead(token, args.lead_id)
            wait_for(
                "todo removed after lead deletion",
                lambda: find_lead(
                    todo_items(token, args.period_end, args.period_end), args.lead_id
                )
                is None,
                wait_seconds=args.wait_seconds,
                interval_seconds=args.interval_seconds,
            )
            print("PASS deletion: lead is absent from todo")
            deleted = True
        else:
            print("[4] Skip deletion: --delete-after was not provided")
    finally:
        if args.delete_after and not deleted:
            try:
                delete_lead(token, args.lead_id)
                print("Cleanup: disposable lead deleted after an interrupted run")
            except Exception as exc:  # pragma: no cover - cleanup diagnostics
                print(f"Cleanup failed: {exc}", file=sys.stderr)
        elif not args.delete_after and original_revisit is not None:
            print(f"Restore original revisit_remind_at: {original_revisit}")
            update_revisit(token, args.lead_id, str(original_revisit))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
