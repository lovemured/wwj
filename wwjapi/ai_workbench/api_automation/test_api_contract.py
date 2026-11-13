from __future__ import annotations

from uuid import uuid4

import pytest

from .client import (
    AIWorkbenchClient,
    assert_api_envelope,
    assert_success,
    records_from,
)
from .config import settings


PC_PANEL_ENDPOINTS = (
    "/api/pc/ai_workbenches/todos_index",
    "/api/pc/ai_workbenches/customer_follow_up",
    "/api/pc/ai_workbenches/lead_follow_up",
    "/api/pc/ai_workbenches/key_opportunities",
    "/api/pc/ai_workbenches/visit_management",
    "/api/pc/ai_workbenches/ai_work_focus",
)

MOBILE_ENDPOINTS = tuple(
    path.replace("/api/pc/", "/api/v2/")
    for path in PC_PANEL_ENDPOINTS
)


def _require_token(token: str) -> None:
    if not settings.run_online:
        pytest.skip("AIWB_RUN_ONLINE未开启，跳过在线接口用例")
    if not token:
        pytest.skip("未设置测试token，跳过在线接口用例")


def _request_id() -> str:
    return str(uuid4())


def _workbench_params(request_id: str | None = None) -> dict[str, str | int]:
    return {
        "ai_workbench_id": settings.workbench_id,
        "start_date": settings.period_start,
        "end_date": settings.period_end,
        "request_id": request_id or _request_id(),
    }


@pytest.fixture
def pc_client() -> AIWorkbenchClient:
    _require_token(settings.pc_token)
    return AIWorkbenchClient(settings)


@pytest.fixture
def mobile_client() -> AIWorkbenchClient:
    _require_token(settings.mobile_token)
    return AIWorkbenchClient(settings, mobile=True)


@pytest.mark.parametrize("endpoint", PC_PANEL_ENDPOINTS)
def test_pc_workbench_endpoint_envelope(
    pc_client: AIWorkbenchClient, endpoint: str
) -> None:
    """PC前台看板接口均返回统一的 code/data/message 响应壳。"""
    payload = assert_success(pc_client.get(endpoint, **_workbench_params()))
    assert_api_envelope(payload)
    assert isinstance(payload["data"], dict)


@pytest.mark.parametrize("endpoint", PC_PANEL_ENDPOINTS[:5])
def test_pc_list_panel_returns_list(
    pc_client: AIWorkbenchClient, endpoint: str
) -> None:
    """列表型看板的数据列表必须是数组，空数据也应返回空数组。"""
    payload = assert_success(pc_client.get(endpoint, **_workbench_params()))
    assert isinstance(payload["data"], dict)
    assert isinstance(records_from(payload), list)


def test_pc_goal_completion_requires_one_goal_id(
    pc_client: AIWorkbenchClient,
) -> None:
    """目标完成接口必须按目标ID查询；未提供目标ID应被服务端拦截。"""
    response = pc_client.get(
        "/api/pc/ai_workbenches/goal_completion",
        ai_workbench_id=settings.workbench_id,
        start_date=settings.period_start,
        end_date=settings.period_end,
        request_id=_request_id(),
    )
    assert response.status_code < 500
    payload = response.json()
    assert payload.get("code") not in (0, "0", 200, "200"), (
        "缺少sales_goal_id时接口不应返回成功"
    )


@pytest.mark.parametrize("endpoint", MOBILE_ENDPOINTS)
def test_mobile_workbench_endpoint_envelope(
    mobile_client: AIWorkbenchClient, endpoint: str
) -> None:
    payload = assert_success(mobile_client.get(endpoint, **_workbench_params()))
    assert_api_envelope(payload)
    assert isinstance(payload["data"], dict)


def test_pc_mobile_record_shape_is_consistent(
    pc_client: AIWorkbenchClient,
    mobile_client: AIWorkbenchClient,
) -> None:
    """同一工作台/周期下，PC和移动端的列表数据都应保持数组结构。"""
    request_id = _request_id()
    for pc_endpoint, mobile_endpoint in zip(
        PC_PANEL_ENDPOINTS[:5], MOBILE_ENDPOINTS[:5]
    ):
        pc_payload = assert_success(
            pc_client.get(pc_endpoint, **_workbench_params(request_id))
        )
        mobile_payload = assert_success(
            mobile_client.get(mobile_endpoint, **_workbench_params(request_id))
        )
        assert isinstance(records_from(pc_payload), list)
        assert isinstance(records_from(mobile_payload), list)


def test_invalid_token_is_rejected() -> None:
    """鉴权回归：无效Token不得读取工作台业务数据。"""
    _require_token(settings.pc_token)
    invalid_settings = settings.__class__(
        pc_base_url=settings.pc_base_url,
        mobile_base_url=settings.mobile_base_url,
        pc_token="invalid-token-for-contract-test",
        mobile_token="",
        workbench_id=settings.workbench_id,
        request_timeout=settings.request_timeout,
        period_start=settings.period_start,
        period_end=settings.period_end,
        mobile_device=settings.mobile_device,
        mobile_version_code=settings.mobile_version_code,
        mobile_gid=settings.mobile_gid,
        mobile_app=settings.mobile_app,
        poll_attempts=settings.poll_attempts,
        poll_interval=settings.poll_interval,
        run_online=settings.run_online,
        run_manual_analysis=False,
        run_mutating_tests=False,
    )
    response = AIWorkbenchClient(invalid_settings).get(
        "/api/pc/ai_workbenches/todos_index",
        **_workbench_params(),
    )
    assert response.status_code in (401, 403)
