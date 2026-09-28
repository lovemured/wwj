from __future__ import annotations

import pytest

from .client import AIWorkbenchClient, assert_success
from .config import settings


def _client() -> AIWorkbenchClient:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not settings.pc_token:
        pytest.skip("未设置AIWB_PC_TOKEN，跳过在线接口用例")
    return AIWorkbenchClient(settings)


def test_power_logs_contract() -> None:
    """算力消费查询是POST查询接口，返回分页和消费明细字段。"""
    payload = assert_success(
        _client().post(
            "/api/pc/ai_orders/power_logs",
            json={
                "page": 1,
                "per_page": 10,
                "filters": {"created_at": "today_ago"},
            },
        )
    )
    data = payload["data"]
    assert isinstance(data.get("list"), list)
    for field in ("page", "per_page", "total_count", "has_next_page"):
        assert field in data, field
    for item in data["list"]:
        assert {"id", "created_at", "category_name", "quantity"}.issubset(item)
        assert item["quantity"] >= 0


def test_power_filter_columns_contract() -> None:
    payload = assert_success(
        _client().get("/api/pc/ai_orders/filter_columns")
    )
    options = payload["data"].get("options")
    assert isinstance(options, list)
    names = {option.get("name") for option in options}
    assert {"created_at", "category", "operation_type"}.issubset(names)
