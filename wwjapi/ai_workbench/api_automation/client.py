from __future__ import annotations

from typing import Any

import requests

from .config import Settings


def _token_header(token: str, device: str | None = None) -> str:
    if device:
        return f'Token token="{token}",device="{device}"'
    return f'Token token="{token}",device="web"'


class AIWorkbenchClient:
    def __init__(self, settings: Settings, *, mobile: bool = False) -> None:
        self.settings = settings
        self.mobile = mobile
        self.base_url = (
            settings.mobile_base_url if mobile else settings.pc_base_url
        )
        token = settings.mobile_token if mobile else settings.pc_token
        self.headers = {
            "Accept": "application/json",
            "Authorization": _token_header(
                token,
                settings.mobile_device if mobile else None,
            ),
        }
        if mobile:
            self.headers.update(
                {
                    "X-LX-GID": settings.mobile_gid,
                    "X-Requested-With": settings.mobile_app,
                    "X-Client-Version": settings.mobile_version_code,
                    "Origin": "https://crmh5-test.weiwenjia.com",
                }
            )
        else:
            self.headers.update(
                {
                    "Origin": "https://lxcrm-test.weiwenjia.com",
                    "Referer": "https://lxcrm-test.weiwenjia.com/",
                }
            )

    def get(self, path: str, **params: Any) -> requests.Response:
        params = {key: value for key, value in params.items() if value is not None}
        return requests.get(
            f"{self.base_url}{path}",
            headers=self.headers,
            params=params,
            timeout=self.settings.request_timeout,
        )

    def post(self, path: str, *, json: Any = None, **params: Any) -> requests.Response:
        params = {key: value for key, value in params.items() if value is not None}
        return requests.post(
            f"{self.base_url}{path}",
            headers={**self.headers, "Content-Type": "application/json"},
            params=params,
            json=json,
            timeout=self.settings.request_timeout,
        )

    def put(self, path: str, *, json: Any = None, **params: Any) -> requests.Response:
        params = {key: value for key, value in params.items() if value is not None}
        return requests.put(
            f"{self.base_url}{path}",
            headers={**self.headers, "Content-Type": "application/json"},
            params=params,
            json=json,
            timeout=self.settings.request_timeout,
        )

    def delete(self, path: str, **params: Any) -> requests.Response:
        params = {key: value for key, value in params.items() if value is not None}
        return requests.delete(
            f"{self.base_url}{path}",
            headers=self.headers,
            params=params,
            timeout=self.settings.request_timeout,
        )


def require_json(response: requests.Response) -> dict[str, Any]:
    assert response.status_code < 500, (
        f"接口服务异常: status={response.status_code}, "
        f"url={response.request.url}, body={response.text[:500]}"
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise AssertionError(
            f"接口未返回JSON: status={response.status_code}, "
            f"url={response.request.url}, body={response.text[:500]}"
        ) from exc
    assert isinstance(payload, dict), (
        f"响应根节点必须是对象: url={response.request.url}, payload={payload!r}"
    )
    return payload


def assert_success(response: requests.Response) -> dict[str, Any]:
    payload = require_json(response)
    assert response.status_code < 400, (
        f"接口请求失败: status={response.status_code}, "
        f"url={response.request.url}, payload={payload}"
    )
    code = payload.get("code")
    assert code in (None, 0, "0", 200, "200"), (
        f"接口业务码异常: url={response.request.url}, payload={payload}"
    )
    return payload


def assert_api_envelope(payload: dict[str, Any]) -> None:
    assert "code" in payload, f"响应缺少code字段: {payload}"
    assert "data" in payload, f"响应缺少data字段: {payload}"
    assert "message" in payload, f"响应缺少message字段: {payload}"


def records_from(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract common list shapes without constraining endpoint-specific fields."""
    candidates: list[Any] = [payload.get("data"), payload.get("list"), payload]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        if isinstance(candidate, dict):
            for key in ("list", "items", "records", "data"):
                value = candidate.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []
