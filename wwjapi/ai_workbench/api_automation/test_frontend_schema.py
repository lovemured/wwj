from __future__ import annotations

import os

import pytest

from .client import AIWorkbenchClient, assert_success, records_from
from .config import settings
from .test_api_contract import _request_id, _workbench_params


def _client() -> AIWorkbenchClient:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not settings.pc_token:
        pytest.skip("未设置AIWB_PC_TOKEN，跳过在线接口用例")
    return AIWorkbenchClient(settings)


def _assert_fields(item: dict, fields: set[str]) -> None:
    missing = fields - item.keys()
    assert not missing, f"返回记录缺少字段: {missing}; item={item}"


def test_available_workbench_schema() -> None:
    payload = assert_success(
        _client().get("/api/pc/ai_workbenches/available_workbench")
    )
    data = payload["data"]
    assert {"id", "name", "ai_panels"}.issubset(data)
    assert isinstance(data["ai_panels"], list)
    for panel in data["ai_panels"]:
        _assert_fields(panel, {"id", "category"})


def test_todos_schema_when_records_exist() -> None:
    payload = assert_success(
        _client().get(
            "/api/pc/ai_workbenches/todos_index",
            **_workbench_params(_request_id()),
        )
    )
    data = payload["data"]
    assert isinstance(data.get("list"), list)
    for item in data["list"]:
        _assert_fields(
            item,
            {
                "id",
                "priority_label",
                "sort",
                "rule_type",
                "related_type",
                "related_id",
                "entity_type",
                "entity_id",
                "status",
            },
        )
        assert item["status"] in {"completed", "pending"}


@pytest.mark.parametrize(
    ("endpoint", "fields"),
    [
        (
            "/api/pc/ai_workbenches/customer_follow_up",
            {"id", "name", "priority_label", "sort", "rule_type"},
        ),
        (
            "/api/pc/ai_workbenches/lead_follow_up",
            {"id", "name", "priority_label", "sort", "rule_type"},
        ),
        (
            "/api/pc/ai_workbenches/key_opportunities",
            {
                "title",
                "customer_name",
                "expect_amount",
                "expect_sign_date",
                "stage",
                "stage_mapped",
                "sign_possibility",
            },
        ),
        (
            "/api/pc/ai_workbenches/visit_management",
            {
                "plan_id",
                "plan_name",
                "start_at",
                "end_at",
                "checkable_type",
                "checkable_name",
                "status",
                "status_i18n",
                "content",
            },
        ),
    ],
)
def test_list_panel_item_schema(
    endpoint: str, fields: set[str]
) -> None:
    payload = assert_success(
        _client().get(endpoint, **_workbench_params(_request_id()))
    )
    for item in records_from(payload):
        _assert_fields(item, fields)


def test_followed_list_pagination_schema() -> None:
    payload = assert_success(
        _client().get(
            "/api/pc/ai_workbenches/followed_list",
            start_date=settings.period_start,
            end_date=settings.period_end,
            entity_type="Customer",
            page=1,
            per_page=10,
        )
    )
    data = payload["data"]
    assert isinstance(data.get("list"), list)
    for field in ("page", "per_page", "has_next_page", "total_count"):
        assert field in data, field
    for item in data["list"]:
        _assert_fields(item, {"id", "name", "followed_at", "followed_type"})


def test_goal_completion_schema_when_goal_id_configured() -> None:
    goal_id = os.getenv("AIWB_SALES_GOAL_ID")
    if not goal_id:
        pytest.skip("未设置AIWB_SALES_GOAL_ID，跳过目标完成接口字段校验")
    payload = assert_success(
        _client().get(
            "/api/pc/ai_workbenches/goal_completion",
            **_workbench_params(_request_id()),
            sales_goal_id=int(goal_id),
        )
    )
    data = payload["data"]
    fields = {
        "goal_name",
        "total",
        "goal_total",
        "goal_percent",
        "time_progress",
        "progress_deviation",
        "remaining_days",
        "daily_required_amount",
        "mom_growth",
        "yoy_growth",
    }
    _assert_fields(data, fields)
