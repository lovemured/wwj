from __future__ import annotations

import time
from typing import Any

import pytest

from .client import AIWorkbenchClient, assert_success
from .config import settings
from .test_api_contract import _request_id, _workbench_params


def _client() -> AIWorkbenchClient:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not settings.pc_token:
        pytest.skip("未设置AIWB_PC_TOKEN，跳过在线接口用例")
    return AIWorkbenchClient(settings)


def _ai_results(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    return data.get("ai_results") if isinstance(data, dict) else None


def _item_ids(value: Any) -> list[int]:
    ids: list[int] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "ai_record_item_id" and isinstance(child, int):
                ids.append(child)
            else:
                ids.extend(_item_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_item_ids(child))
    return list(dict.fromkeys(ids))


@pytest.mark.parametrize("analysis_type", ["work_focus", "ai_analysis"])
def test_allow_manual_ai_analysis_contract(analysis_type: str) -> None:
    payload = assert_success(
        _client().get(
            "/api/pc/ai_workbenches/allow_manual_ai_analysis",
            analysis_type=analysis_type,
        )
    )
    data = payload["data"]
    assert {"allow", "status", "reason"}.issubset(data), data
    assert isinstance(data["allow"], bool)
    if data["allow"] is False:
        assert data["status"] in {"insufficient_power", "rate_limited", None}
        assert data["reason"]


@pytest.mark.skipif(
    not settings.run_manual_analysis,
    reason="设置AIWB_RUN_MANUAL_ANALYSIS=true后才执行，避免误扣算力",
)
def test_manual_work_focus_uses_manual_flag_and_can_poll() -> None:
    """手动分析必须携带manual_ai_analysis=true，并支持状态轮询。"""
    request_id = _request_id()
    payload = assert_success(
        _client().get(
            "/api/pc/ai_workbenches/ai_work_focus",
            **_workbench_params(request_id),
            manual_ai_analysis="true",
        )
    )
    ai_results = _ai_results(payload)
    assert isinstance(ai_results, dict), payload
    assert ai_results.get("status") in {"processing", "partial", "completed"}

    for item_id in _item_ids(ai_results):
        advice_payload = assert_success(
            _client().get(
                "/api/pc/ai_workbenches/panel_advice",
                ai_record_item_id=item_id,
            )
        )
        advice = _ai_results(advice_payload)
        assert isinstance(advice, dict)


def test_ai_result_status_is_known_when_returned() -> None:
    """看板接口若返回AI结果，状态必须是文档定义的三态之一。"""
    endpoint = "/api/pc/ai_workbenches/todos_index"
    payload = assert_success(
        _client().get(endpoint, **_workbench_params(_request_id()))
    )
    ai_results = _ai_results(payload)
    if ai_results is None:
        pytest.skip("当前环境该看板未返回AI结果")
    if isinstance(ai_results, dict):
        assert ai_results.get("status") in {"processing", "partial", "completed"}
