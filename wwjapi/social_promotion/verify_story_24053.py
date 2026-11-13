#!/usr/bin/env python3
"""Temporary verification checklist for ZenTao story 24053.

Run ``python3 social_promotion/verify_story_24053.py --list`` to review the
planned checks. API requests and assertions are intentionally pending the
confirmed endpoint contract and completed implementation.
"""
import argparse
import sys
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Check:
    case_id: str
    area: str
    scenario: str
    expected: str


CHECKS: Sequence[Check] = (
    Check("SP-001", "表单字段", "活动表单配置图片字段", "可配置、上传、提交并正确展示图片"),
    Check("SP-002", "表单字段", "活动表单配置文件字段", "可配置、上传、提交并正确展示文件"),
    Check("SP-003", "市场活动", "关联对象为线索", "显示市场活动选择项，提交线索自动关联所选活动"),
    Check("SP-004", "市场活动", "关联对象不是线索", "不显示市场活动选择项"),
    Check("SP-005", "到期控制", "永不到期", "推广链接持续可访问"),
    Check("SP-006", "到期控制", "自定义时间或跟随市场活动结束时间到期", "访问表单时显示“活动已失效”"),
    Check("SP-007", "分享人", "按分享人和渠道生成分享链接及二维码", "链接/二维码对应正确的分享人和渠道"),
    Check("SP-008", "分享人", "通过分享链接访问并提交线索", "浏览、线索和后续转化保留可追踪归因"),
    Check("SP-009", "统计分析", "查看活动统计", "指标卡、转化漏斗、渠道、分享人 Top10 和趋势符合确认后的口径"),
    Check("SP-010", "平台回归", "PC 与 APP，多平台产品形态", "目标平台上的配置、访问、提交和统计行为一致"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="需求 24053 临时验证清单")
    parser.add_argument(
        "--list", action="store_true", help="只显示需求级验证清单，不请求接口"
    )
    args = parser.parse_args()

    for check in CHECKS:
        status = "PLANNED" if args.list else "NOT VERIFIED"
        print(f"{status} {check.case_id} [{check.area}] {check.scenario}")
        print(f"  预期: {check.expected}")

    if args.list:
        return 0

    print("\n接口请求与断言尚未接入；需待 API 契约和实现完成后补齐。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
