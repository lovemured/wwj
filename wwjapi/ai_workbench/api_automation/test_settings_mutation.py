from __future__ import annotations

import os
from uuid import uuid4

import pytest

from .client import AIWorkbenchClient, assert_success
from .config import settings


def _client() -> AIWorkbenchClient:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not settings.run_mutating_tests:
        pytest.skip(
            "AIWB_RUN_MUTATING_TESTS未开启，跳过会创建/修改/删除配置的用例"
        )
    if not settings.pc_token:
        pytest.skip("未设置AIWB_PC_TOKEN，跳过在线接口用例")
    if not os.getenv("AIWB_TEST_USER_ID"):
        pytest.skip("未设置AIWB_TEST_USER_ID，跳过配置生命周期用例")
    return AIWorkbenchClient(settings)


def _scope() -> dict[str, list[int]]:
    return {
        "user_ids": [int(os.environ["AIWB_TEST_USER_ID"])],
        "department_ids": [],
        "role_ids": [],
    }


def _create_payload(new_data: dict) -> dict:
    panels = []
    for panel in new_data["ai_panels"]:
        item = {
            "category": panel["category"],
            "status": panel["status"],
            "position": panel["position"],
            "rules": panel["rules"],
        }
        default_capabilities = [
            capability["name"]
            for capability in panel.get("supported_ai_capabilities", [])
            if capability.get("default") is True
        ]
        if default_capabilities:
            item["ai_capabilities"] = default_capabilities
        panels.append(item)
    return {
        "name": f"AIWB_API_AUTOTEST_{uuid4().hex[:10]}",
        "scope": _scope(),
        "ai_panels_attributes": panels,
    }


def test_workbench_create_update_delete_lifecycle() -> None:
    """显式开启后验证设置页的新增、编辑和删除链路，并自动清理数据。"""
    client = _client()
    new_payload = assert_success(
        client.get("/api/pc/settings/ai_workbenches/new")
    )
    create_payload = _create_payload(new_payload["data"])
    created = assert_success(
        client.post(
            "/api/pc/settings/ai_workbenches",
            json=create_payload,
        )
    )
    workbench_id = created["data"]["id"]
    assert isinstance(workbench_id, int)

    try:
        detail = assert_success(
            client.get(f"/api/pc/settings/ai_workbenches/{workbench_id}")
        )
        panels = detail["data"]["ai_panels"]
        assert panels
        updated_panels = []
        for index, panel in enumerate(panels):
            updated = {
                "id": panel["id"],
                "category": panel["category"],
                "status": False if index == 0 else panel["status"],
                "position": panel.get("position", index + 1),
                "rules": panel.get("rules", []),
                "ai_capabilities": panel.get("ai_capabilities", []),
            }
            updated_panels.append(updated)
        update_payload = {
            "name": f"{create_payload['name']}_UPDATED",
            "scope": _scope(),
            "ai_panels_attributes": updated_panels,
        }
        assert_success(
            client.put(
                f"/api/pc/settings/ai_workbenches/{workbench_id}",
                json=update_payload,
            )
        )
        updated_detail = assert_success(
            client.get(f"/api/pc/settings/ai_workbenches/{workbench_id}")
        )
        assert updated_detail["data"]["name"] == update_payload["name"]
        assert updated_detail["data"]["ai_panels"][0]["status"] is False
    finally:
        response = client.delete(
            f"/api/pc/settings/ai_workbenches/{workbench_id}"
        )
        assert response.status_code < 400, response.text[:500]
