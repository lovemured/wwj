from __future__ import annotations

import os
from datetime import date
from dataclasses import dataclass


def _default_period() -> tuple[str, str]:
    today = date.today()
    return today.replace(day=1).isoformat(), today.isoformat()


DEFAULT_PERIOD_START, DEFAULT_PERIOD_END = _default_period()


@dataclass(frozen=True)
class Settings:
    pc_base_url: str = os.getenv(
        "AIWB_PC_BASE_URL", "https://lxcrm-api-test.weiwenjia.com"
    ).rstrip("/")
    mobile_base_url: str = os.getenv(
        "AIWB_MOBILE_BASE_URL", "https://lxcrm-api-test.weiwenjia.com"
    ).rstrip("/")
    pc_token: str = os.getenv("AIWB_PC_TOKEN", "")
    mobile_token: str = os.getenv("AIWB_MOBILE_TOKEN", "")
    workbench_id: int = int(os.getenv("AIWB_WORKBENCH_ID", "1"))
    request_timeout: float = float(os.getenv("AIWB_TIMEOUT", "20"))
    period_start: str = os.getenv("AIWB_PERIOD_START", DEFAULT_PERIOD_START)
    period_end: str = os.getenv("AIWB_PERIOD_END", DEFAULT_PERIOD_END)
    mobile_device: str = os.getenv("AIWB_MOBILE_DEVICE", "lxcrm_duli")
    mobile_version_code: str = os.getenv("AIWB_MOBILE_VERSION_CODE", "4.0.1")
    mobile_gid: str = os.getenv("AIWB_MOBILE_GID", "")
    mobile_app: str = os.getenv("AIWB_MOBILE_APP", "com.lixiaoyun.aike")
    poll_attempts: int = int(os.getenv("AIWB_POLL_ATTEMPTS", "6"))
    poll_interval: float = float(os.getenv("AIWB_POLL_INTERVAL", "2"))
    run_manual_analysis: bool = os.getenv(
        "AIWB_RUN_MANUAL_ANALYSIS", ""
    ).lower() in {"1", "true", "yes"}
    run_online: bool = os.getenv("AIWB_RUN_ONLINE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    run_mutating_tests: bool = os.getenv(
        "AIWB_RUN_MUTATING_TESTS", ""
    ).lower() in {"1", "true", "yes"}


settings = Settings()
