from __future__ import annotations

import os

import pytest

from .client import AIWorkbenchClient, assert_success
from .config import settings


EXPECTED_CATEGORIES = {
    "ai_todo",
    "customer_follow_up",
    "lead_follow_up",
    "key_opportunities",
    "visit_management",
    "goal_completion",
    "contract_receipt_management",
    "team_performance_distribution",
    "team_process_distribution",
}


def _client() -> AIWorkbenchClient:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not settings.pc_token:
        pytest.skip("未设置AIWB_PC_TOKEN，跳过在线接口用例")
    return AIWorkbenchClient(settings)


def _panel_map(payload: dict) -> dict[str, dict]:
    panels = payload["data"]["ai_panels"]
    assert isinstance(panels, list)
    return {panel["category"]: panel for panel in panels}


def test_workbench_new_defaults_all_nine_panels_enabled() -> None:
    """新建模板接口：9个本期看板默认全部开启。"""
    payload = assert_success(_client().get("/api/pc/settings/ai_workbenches/new"))
    data = payload["data"]
    panel_map = _panel_map(payload)
    assert set(panel_map) == EXPECTED_CATEGORIES
    assert len(panel_map) == 9
    assert all(panel["status"] is True for panel in panel_map.values())
    assert data["max_custom_rules_per_panel"] == 5
    assert data["max_filters_per_rule"] == 10


def test_workbench_new_capability_contract() -> None:
    """新增配置应返回能力名称和各看板可挂载能力。"""
    payload = assert_success(_client().get("/api/pc/settings/ai_workbenches/new"))
    data = payload["data"]
    names = data["ai_capability_names"]
    expected_names = {
        "risk_warning",
        "method_guidance",
        "follow_up_script",
        "goal_prediction",
        "smart_sort",
        "smart_analysis",
    }
    assert expected_names.issubset(names)
    for category, panel in _panel_map(payload).items():
        capabilities = panel["supported_ai_capabilities"]
        assert isinstance(capabilities, list), category
        for capability in capabilities:
            assert {"name", "label"}.issubset(capability), capability
            assert capability["name"] in names, capability


def test_workbench_new_rule_defaults_are_well_formed() -> None:
    payload = assert_success(_client().get("/api/pc/settings/ai_workbenches/new"))
    for category, panel in _panel_map(payload).items():
        assert isinstance(panel["rules"], list), category
        for rule in panel["rules"]:
            assert "enable" in rule or "id" in rule, rule
            if "enable" in rule:
                assert isinstance(rule["enable"], bool), rule
        assert isinstance(panel["position"], int), category


def test_workbench_list_has_pagination_contract() -> None:
    payload = assert_success(
        _client().get(
            "/api/pc/settings/ai_workbenches",
            page=1,
            per_page=10,
        )
    )
    data = payload["data"]
    assert isinstance(data.get("list"), list)
    for field in ("page", "per_page", "total_count", "has_next_page"):
        assert field in data, field


def test_workbench_detail_contains_panel_configuration() -> None:
    payload = assert_success(
        _client().get(
            f"/api/pc/settings/ai_workbenches/{settings.workbench_id}"
        )
    )
    data = payload["data"]
    assert data["id"] == settings.workbench_id
    assert isinstance(data.get("ai_panels"), list)
    for panel in data["ai_panels"]:
        assert {"id", "category", "status", "rules"}.issubset(panel), panel
        assert isinstance(panel["rules"], list)
        if "ai_capabilities" in panel:
            assert isinstance(panel["ai_capabilities"], list)


def test_rule_options_contains_team_metric_groups() -> None:
    payload = assert_success(
        _client().get("/api/pc/settings/ai_workbenches/rule_options")
    )
    data = payload["data"]
    for field in (
        "performance_metrics",
        "follow_up_metrics",
        "visit_metrics",
        "call_metrics",
    ):
        assert isinstance(data.get(field), list), field
        for option in data[field]:
            assert {"value", "label"}.issubset(option), option


@pytest.mark.parametrize(
    ("category", "rule_type"),
    [
        ("customer_follow_up", "unfollowed"),
        ("lead_follow_up", "unfollowed"),
        ("key_opportunities", "sign_possibility"),
        ("contract_receipt_management", "contract_end_soon"),
        ("team_performance_distribution", "performance_metric"),
        ("ai_todo", "lead_revisit_remind_at"),
        ("ai_todo", "task"),
    ],
)
def test_filter_columns_contract(category: str, rule_type: str) -> None:
    """筛选字段接口允许正常返回，也允许文档定义的code:-1缺口。"""
    response = _client().get(
        "/api/pc/settings/ai_workbenches/filter_columns",
        category=category,
        rule_type=rule_type,
    )
    assert response.status_code < 500
    payload = response.json()
    assert isinstance(payload, dict)
    assert "code" in payload
    if payload.get("code") in (0, "0", 200, "200"):
        assert isinstance(payload.get("data"), dict)
        assert isinstance(payload["data"].get("advanced_filter_columns"), list)
    else:
        assert payload.get("code") == -1


def test_preset_panel_states_when_configured() -> None:
    """线上预设模板状态：只有显式提供预设模板ID时才执行。"""
    preset_id = os.getenv("AIWB_PRESET_WORKBENCH_ID")
    if not preset_id:
        pytest.skip("未设置AIWB_PRESET_WORKBENCH_ID，跳过预设模板状态校验")
    payload = assert_success(
        _client().get(f"/api/pc/settings/ai_workbenches/{preset_id}")
    )
    panel_map = _panel_map(payload)
    assert panel_map["contract_receipt_management"]["status"] is True
    assert panel_map["team_performance_distribution"]["status"] is False
    assert panel_map["team_process_distribution"]["status"] is False
