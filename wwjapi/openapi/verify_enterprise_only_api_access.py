#!/usr/bin/env python3
"""Verify that enterprise-only OpenAPI endpoints are denied to a basic plan.

Example:
  export OPENAPI_CLIENT_ID='oa_xxx'
  export OPENAPI_CLIENT_SECRET='sk-xxx'
  python3 openapi/verify_enterprise_only_api_access.py \
    --host https://lxcrm-staging.weiwenjia.com \
    --report /tmp/enterprise-api-access.json

The script never prints credentials or tokens. Existing records are read-only.
PUT and DELETE use a non-existent ID unless the same run unexpectedly creates a
record, in which case that record is used and deleted immediately.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests


DEFAULT_HOST = "https://lxcrm-staging.weiwenjia.com"
DEFAULT_SAFE_ID = 999_999_999_999
DENIED_MESSAGE = "该接口为企业版专属，请升级后使用"


class OpenAPIClient:
    def __init__(self, host: str, client_id: str, client_secret: str, timeout: int):
        self.host = host.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.session = requests.Session()
        self.user_id: int | None = None

    def authorize(self) -> dict[str, Any]:
        response = self.session.post(
            f"{self.host}/api/openapi/v2/auth/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        body = parse_json(response)
        data = body.get("data") or {}
        token = data.get("access_token") if isinstance(data, dict) else None
        if response.status_code != 200 or body.get("code") != 0 or not token:
            raise RuntimeError(
                f"OAuth failed: HTTP {response.status_code}, "
                f"code={body.get('code')}, message={body.get('message')}"
            )

        self.user_id = data.get("user_id")
        self.session.headers.update(
            {
                "Authorization": (
                    f"Token token={token}, device=open_api, version_code=9.9.9"
                ),
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        return {
            "http": response.status_code,
            "code": body.get("code"),
            "message": body.get("message"),
            "expires_in": data.get("expires_in"),
            "user_id": self.user_id,
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        response = self.session.request(
            method,
            f"{self.host}{path}",
            json=payload,
            timeout=self.timeout,
        )
        body = parse_json(response)
        if retry_auth and (response.status_code == 401 or body.get("code") == 100401):
            self.authorize()
            return self.request(method, path, payload, retry_auth=False)
        return response.status_code, body


def parse_json(response: requests.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {"raw": response.text[:500]}
    return body if isinstance(body, dict) else {"data": body}


def extract_id(body: dict[str, Any], resource_key: str) -> int | None:
    data = body.get("data")
    if not isinstance(data, dict):
        return None
    if resource_key == "task":
        scheduleable = data.get("scheduleable")
        if isinstance(scheduleable, dict):
            return scheduleable.get("id")
        return None
    for candidate in (data, data.get(resource_key), data.get("resource"), data.get("entity")):
        if isinstance(candidate, dict) and candidate.get("id") is not None:
            return candidate["id"]
    return None


def denied(http_status: int, body: dict[str, Any]) -> bool:
    return (
        http_status == 403
        and body.get("code") == -1
        and body.get("message") == DENIED_MESSAGE
    )


class DenialVerifier:
    def __init__(self, client: OpenAPIClient, safe_id: int):
        self.client = client
        self.safe_id = safe_id
        self.results: list[dict[str, Any]] = []
        self.created: dict[str, tuple[int, str]] = {}
        self.department_id: int | None = None
        self.customer_id: int | None = None
        self.run_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"

    def discover_context(self) -> None:
        if self.client.user_id:
            status, body = self.client.request(
                "GET", f"/api/openapi/v2/user/{self.client.user_id}"
            )
            data = body.get("data")
            if status == 200 and body.get("code") == 0 and isinstance(data, dict):
                self.department_id = data.get("department_id")

        status, body = self.client.request("GET", "/api/openapi/v2/customers")
        data = body.get("data")
        customers = data.get("customers") if isinstance(data, dict) else None
        if status == 200 and body.get("code") in (None, 0) and customers:
            self.customer_id = customers[0].get("id")

    def check(
        self,
        module: str,
        name: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        note: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        status, body = self.client.request(method, path, payload)
        passed = denied(status, body)
        result = {
            "module": module,
            "name": name,
            "method": method,
            "path": path,
            "http": status,
            "code": body.get("code"),
            "message": body.get("message"),
            "passed": passed,
        }
        if note:
            result["note"] = note
        self.results.append(result)
        label = "PASS" if passed else "FAIL"
        print(
            f"[{label}] {method:<6} {path} -> "
            f"HTTP {status}, code={body.get('code')}, message={body.get('message')}"
        )
        return status, body

    def test_simple(self) -> None:
        self.check("附件", "附件列表", "GET", "/api/openapi/v2/attachments")

    def test_task(self) -> None:
        base = "/api/openapi/v2/events"
        note = f"基础版套餐验证-任务-{self.run_id}"
        status, body = self.check(
            "任务",
            "任务新增",
            "POST",
            base,
            {
                "event": {
                    "note": note,
                    "remind_at": "2099-01-01 10:00",
                    "event_user_ids": [self.client.user_id],
                }
            },
        )
        created_id = extract_id(body, "task") if status < 400 else None
        if created_id:
            self.created["task"] = (created_id, base)
        target = created_id or self.safe_id
        target_note = "本轮意外创建的记录" if created_id else "不存在的安全 ID"
        path = f"{base}/{target}"
        self.check("任务", "任务更新", "PUT", path, {"event": {"note": f"{note}-update"}}, target_note)
        self.check("任务", "任务详情", "GET", path, note=target_note)
        status, body = self.check("任务", "任务删除", "DELETE", path, note=target_note)
        if created_id and status < 400 and body.get("code") == 0:
            self.created.pop("task", None)

    def test_expenses(self) -> None:
        base = "/api/openapi/v2/expenses"
        self.check("费用", "费用筛选条件", "GET", f"{base}/filter_sort_group")
        self.check("费用", "费用列表", "GET", base)
        description = f"基础版套餐验证-费用-{self.run_id}"
        status, body = self.check(
            "费用",
            "费用新增",
            "POST",
            base,
            {
                "expense": {
                    "sn": f"BEXP{self.run_id.replace('-', '')[-18:]}",
                    "customer_id": self.customer_id,
                    "amount": "1.23",
                    "incurred_at": "2099-01-01",
                    "user_id": self.client.user_id,
                    "owned_department_id": self.department_id,
                    "description": description,
                }
            },
        )
        created_id = extract_id(body, "expense") if status < 400 else None
        if created_id:
            self.created["expense"] = (created_id, base)
        target = created_id or self.safe_id
        target_note = "本轮意外创建的记录" if created_id else "不存在的安全 ID"
        path = f"{base}/{target}"
        self.check("费用", "费用详情", "GET", path, note=target_note)
        self.check(
            "费用",
            "费用更新",
            "PUT",
            path,
            {"expense": {"description": f"{description}-update"}},
            target_note,
        )

    def test_expense_accounts(self) -> None:
        base = "/api/openapi/v2/expense_accounts"
        self.check("报销单", "报销单列表", "GET", base)
        self.check("报销单", "报销单筛选条件", "GET", f"{base}/filter_sort_group")
        expense_id = self.created.get("expense", (self.safe_id, ""))[0]
        status, body = self.check(
            "报销单",
            "报销单新增",
            "POST",
            base,
            {
                "expense_account": {
                    "sn": f"BACC{self.run_id.replace('-', '')[-18:]}",
                    "user_id": self.client.user_id,
                    "owned_department_id": self.department_id,
                    "note": f"基础版套餐验证-报销单-{self.run_id}",
                    "approve_status": "approved",
                },
                "expense_ids": [expense_id],
            },
        )
        created_id = extract_id(body, "expense_account") if status < 400 else None
        if created_id:
            self.created["expense_account"] = (created_id, base)
        target = created_id or self.safe_id
        target_note = "本轮意外创建的记录" if created_id else "不存在的安全 ID"
        path = f"{base}/{target}"
        self.check("报销单", "报销单详情", "GET", path, note=target_note)
        self.check(
            "报销单",
            "更新报销单",
            "PUT",
            path,
            {"expense_account": {"note": "基础版套餐验证-update"}},
            target_note,
        )
        status, body = self.check("报销单", "删除报销单", "DELETE", path, note=target_note)
        if created_id and status < 400 and body.get("code") == 0:
            self.created.pop("expense_account", None)

    def finish_expenses(self) -> None:
        base = "/api/openapi/v2/expenses"
        created = self.created.get("expense")
        target = created[0] if created else self.safe_id
        note = "本轮意外创建的记录" if created else "不存在的安全 ID"
        status, body = self.check("费用", "费用删除", "DELETE", f"{base}/{target}", note=note)
        if created and status < 400 and body.get("code") == 0:
            self.created.pop("expense", None)

    def test_resource(
        self,
        module: str,
        resource_key: str,
        base: str,
        create_payload: dict[str, Any],
        update_payload: dict[str, Any],
    ) -> None:
        self.check(module, f"{module}列表", "GET", base)
        self.check(module, f"{module}筛选条件", "GET", f"{base}/filter_sort_group")
        status, body = self.check(module, f"{module}新增", "POST", base, create_payload)
        created_id = extract_id(body, resource_key) if status < 400 else None
        if created_id:
            self.created[resource_key] = (created_id, base)
        target = created_id or self.safe_id
        note = "本轮意外创建的记录" if created_id else "不存在的安全 ID"
        path = f"{base}/{target}"
        self.check(module, f"{module}详情", "GET", path, note=note)
        self.check(module, f"更新{module}", "PUT", path, update_payload, note)
        status, body = self.check(module, f"删除{module}", "DELETE", path, note=note)
        if created_id and status < 400 and body.get("code") == 0:
            self.created.pop(resource_key, None)

    def cleanup(self) -> None:
        for key in ("expense_account", "expense", "task", "checkin_plan", "market_activity"):
            record = self.created.get(key)
            if not record:
                continue
            record_id, base = record
            status, body = self.client.request("DELETE", f"{base}/{record_id}")
            cleaned = status < 400 and body.get("code") == 0
            print(
                f"[{'CLEAN' if cleaned else 'WARN'}] DELETE {base}/{record_id} -> "
                f"HTTP {status}, code={body.get('code')}, message={body.get('message')}"
            )
            if cleaned:
                self.created.pop(key, None)

    def run(self) -> None:
        self.discover_context()
        try:
            self.test_simple()
            self.test_task()
            self.test_expenses()
            self.test_expense_accounts()
            self.finish_expenses()

            checkin_name = f"基础版套餐验证-拜访计划-{self.run_id}"
            self.test_resource(
                "拜访计划",
                "checkin_plan",
                "/api/openapi/v2/checkin_plans",
                {
                    "checkin_plan": {
                        "name": checkin_name,
                        "start_at": "2099-01-01 10:00",
                        "end_at": "2099-01-01 11:00",
                        "duration": 60,
                        "checkin_plan_visits_attributes": [
                            {"checkable_type": "Customer", "checkable_id": self.customer_id}
                        ],
                        "content": "基础版套餐验证",
                        "user_id": self.client.user_id,
                        "owned_department_id": self.department_id,
                        "assist_user_ids": [],
                        "approve_status": "approved",
                    }
                },
                {"checkin_plan": {"name": f"{checkin_name}-update"}},
            )

            market_name = f"基础版套餐验证-市场活动-{self.run_id}"
            self.test_resource(
                "市场活动",
                "market_activity",
                "/api/openapi/v2/market_activities",
                {
                    "market_activity": {
                        "name": market_name,
                        "start_date": "2099-01-01",
                        "end_date": "2099-01-02",
                        "estimated_cost": 1,
                        "actual_cost": 1,
                        "estimated_income": 1,
                        "actual_income": 1,
                        "description": "基础版套餐验证",
                        "user_id": self.client.user_id,
                        "owned_department_id": self.department_id,
                        "assist_user_ids": [],
                        "approve_status": "approved",
                    }
                },
                {"market_activity": {"name": f"{market_name}-update"}},
            )
        finally:
            self.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify basic-plan denial for 29 enterprise-only OpenAPI endpoints."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--client-id", default=os.getenv("OPENAPI_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("OPENAPI_CLIENT_SECRET"))
    parser.add_argument("--safe-id", type=int, default=DEFAULT_SAFE_ID)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.client_id or not args.client_secret:
        parser.error(
            "provide --client-id/--client-secret or set "
            "OPENAPI_CLIENT_ID/OPENAPI_CLIENT_SECRET"
        )
    return args


def main() -> int:
    args = parse_args()
    client = OpenAPIClient(args.host, args.client_id, args.client_secret, args.timeout)
    try:
        auth_result = client.authorize()
    except (requests.RequestException, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        f"OAuth success: user_id={auth_result['user_id']}, "
        f"expires_in={auth_result['expires_in']}"
    )
    verifier = DenialVerifier(client, args.safe_id)
    verifier.run()
    passed = sum(result["passed"] for result in verifier.results)
    total = len(verifier.results)
    report = {
        "host": client.host,
        "user_id": client.user_id,
        "expected": {
            "http": 403,
            "code": -1,
            "message": DENIED_MESSAGE,
        },
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "remaining_created_records": len(verifier.created),
        },
        "results": verifier.results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {args.report}")
    print(
        f"Summary: {passed}/{total} matched the basic-plan denial; "
        f"remaining created records={len(verifier.created)}"
    )
    return 0 if passed == total and not verifier.created else 1


if __name__ == "__main__":
    raise SystemExit(main())
