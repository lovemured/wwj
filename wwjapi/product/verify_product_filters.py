#!/usr/bin/env python3
"""只读验证移动端产品筛选接口。

示例：
  python3 product/verify_product_filters.py --token "$WWJ_USER_TOKEN"

验证目标：
1. /api/v3/permissions/user_setting 的 product 筛选字段覆盖情况；
2. /api/v2/products 对已抓包确认参数格式的单字段及组合筛选结果。

指定 --product-id 时，基于当前环境实际返回的产品筛选字段生成一条组合请求。
"""
import argparse
import json
import os
import sys
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests


DEFAULT_API = "https://lxcrm-api-test.weiwenjia.com"
HEADER_DEVICE = "lxcrm_duli"
HEADER_VERSION = "4.0.1"
PC_TO_MOBILE_FIELD = {"shop": "shop_id"}
SUPPORTED_TYPES = {
    "number",
    "custom_field_select",
    "custom_field_multi_select",
    "custom_field_nested_select",
    "custom_field_department_field",
    "custom_field_multi_department_field",
}


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    filter_type: str
    number_format: Optional[str]
    visible: bool


@dataclass
class Case:
    field: Field
    params: List[Tuple[str, str]]
    matches: Callable[[Dict[str, Any]], bool]


@dataclass
class Result:
    status: str
    title: str
    detail: str


class MobileClient:
    def __init__(self, api: str, token: str, timeout: int) -> None:
        self.api = api.rstrip("/")
        self.timeout = timeout
        self.token = token
        host = urlparse(self.api).netloc
        web_host = host.replace("-api-", "-") if "-api-" in host else host
        h5_host = web_host.replace("lxcrm-", "crmh5-", 1)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "*/*",
                "Authorization": (
                    f'Token token="{token}",device="{HEADER_DEVICE}",'
                    f'version_code="{HEADER_VERSION}"'
                ),
                "Origin": f"https://{h5_host}",
                "X-Requested-With": "com.lixiaoyun.aike",
            }
        )

    def get(self, path: str, params: Any = None) -> Dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.api}{path}", params=params, timeout=self.timeout
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(f"请求 {path} 失败: {error}") from error
        if payload.get("code") != 0:
            raise RuntimeError(f"接口 {path} 返回失败: {payload.get('message', '未知错误')}")
        return payload

    def product_fields(self) -> List[Field]:
        payload = self.get("/api/v3/permissions/user_setting")
        filters = (
            (payload.get("data") or {})
            .get("user_setting", {})
            .get("custom_filter", {})
            .get("product", [])
        )
        return [
            Field(
                name=item["field_name"],
                label=item.get("label") or item["field_name"],
                filter_type=item.get("filter_field_type") or "unknown",
                number_format=item.get("number_format"),
                visible=bool(item.get("visible")),
            )
            for item in filters
            if item.get("field_name")
        ]

    def pc_product_fields(self) -> List[Dict[str, Any]]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Authorization": f'Token token={self.token},device="web"',
            "Origin": self._web_origin(),
        }
        try:
            response = requests.get(
                f"{self.api}/api/pc/customs/filter_form_columns",
                headers=headers,
                params={"model_klass": "product"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(f"请求 PC 产品筛选字段失败: {error}") from error
        if payload.get("code") != 0:
            raise RuntimeError(
                "PC 产品筛选字段接口返回失败: " + payload.get("message", "未知错误")
            )
        return (payload.get("data") or {}).get("columns") or []

    def _web_origin(self) -> str:
        host = urlparse(self.api).netloc
        web_host = host.replace("-api-", "-") if "-api-" in host else host
        return f"https://{web_host}"

    def products(
        self, params: Sequence[Tuple[str, str]], per_page: int
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        query = [("page", "1"), ("per_page", str(per_page))] + list(params)
        data = self.get("/api/v2/products", query).get("data") or {}
        return data.get("products") or [], data

    def product_detail(self, product_id: int) -> Dict[str, Any]:
        return self.get(f"/api/v2/products/{product_id}").get("data") or {}

    def all_products(
        self, per_page: int, max_pages: int
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        first_data: Dict[str, Any] = {}
        for page in range(1, max_pages + 1):
            data = self.get(
                "/api/v2/products", {"page": page, "per_page": per_page}
            ).get("data") or {}
            if page == 1:
                first_data = data
            products.extend(data.get("products") or [])
            if not data.get("has_next_page"):
                return products, first_data
        return products, first_data


def decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).rstrip("%"))
    except (InvalidOperation, ValueError):
        return None


def product_value(product: Dict[str, Any], name: str) -> Any:
    if name == "shop_id":
        return (product.get("shop") or {}).get("id")
    return product.get(name)


def has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def date_part(value: Any) -> Optional[date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def direct_case(field: Field, value: Any) -> Optional[Case]:
    if field.name == "lock_status" and isinstance(value, bool):
        expected = value
        return Case(
            field,
            [("lock_status", "1" if expected else "0")],
            lambda product: product.get("lock_status") is expected,
        )
    if field.name == "shop_id" and has_value(value):
        expected = str(value)
        return Case(
            field,
            [("shop_id", expected)],
            lambda product: str(product_value(product, "shop_id")) == expected,
        )
    return None


def custom_case(field: Field, value: Any) -> Optional[Case]:
    if field.filter_type == "number":
        number = decimal(value)
        if number is None:
            return None
        expected = number
        key = f"custom_field_filter_within_{field.name}[]"
        return Case(
            field,
            [(key, str(expected)), (key, str(expected))],
            lambda product: decimal(product_value(product, field.name)) == expected,
        )

    if field.filter_type == "custom_field_select":
        expected = str(value)
        return Case(
            field,
            [(f"custom_field_filter_{field.name}", expected)],
            lambda product: str(product_value(product, field.name)) == expected,
        )

    if field.filter_type in {
        "custom_field_multi_select",
        "custom_field_multi_department_field",
    }:
        if not isinstance(value, list) or not value:
            return None
        expected = str(value[0])
        return Case(
            field,
            [(f"custom_field_filter_multi_in_{field.name}", expected)],
            lambda product: expected
            in [str(item) for item in (product_value(product, field.name) or [])],
        )

    if field.filter_type == "custom_field_department_field":
        values = value if isinstance(value, list) else [value]
        if not values:
            return None
        expected = str(values[0])
        return Case(
            field,
            [(f"custom_field_filter_in_{field.name}", expected)],
            lambda product: expected
            in [str(item) for item in (product_value(product, field.name) or [])],
        )

    if field.filter_type == "custom_field_nested_select":
        values = value if isinstance(value, list) else [value]
        if not values:
            return None
        expected = str(values[0])
        return Case(
            field,
            [(f"custom_field_filter_nested_select_in_{field.name}", expected)],
            lambda product: expected
            in [
                str(item)
                for item in (
                    product_value(product, field.name)
                    if isinstance(product_value(product, field.name), list)
                    else [product_value(product, field.name)]
                )
            ],
        )
    return None


def time_case(field: Field, value: Any) -> Optional[Case]:
    selected_date = date_part(value)
    if (
        field.filter_type != "time"
        or selected_date is None
        or field.name in {"created_at", "updated_at"}
    ):
        return None
    expected = selected_date.isoformat()
    key = f"custom_field_filter_{field.name}[]"
    return Case(
        field,
        [(key, expected), (key, expected)],
        lambda product: date_part(product_value(product, field.name)) == selected_date,
    )


def build_case(field: Field, product: Dict[str, Any]) -> Optional[Case]:
    value = product_value(product, field.name)
    direct = direct_case(field, value)
    if direct:
        return direct
    if not has_value(value):
        return None
    return custom_case(field, value) or time_case(field, value)


def target_number_case(field: Field, value: Any) -> Optional[Case]:
    expected = decimal(value)
    if expected is None:
        return None
    lower = expected - Decimal("1")
    upper = expected + Decimal("1")
    key = f"custom_field_filter_within_{field.name}[]"
    return Case(
        field,
        [(key, str(lower)), (key, str(upper))],
        lambda product: decimal(product_value(product, field.name)) is not None
        and lower <= decimal(product_value(product, field.name)) <= upper,
    )


def target_case(field: Field, product: Dict[str, Any]) -> Optional[Case]:
    value = product_value(product, field.name)
    if not has_value(value) and not (field.name == "lock_status" and isinstance(value, bool)):
        return None
    if field.name == "channel":
        expected = str(value)
        return Case(
            field,
            [("channel", expected)],
            lambda item: str(item.get("channel")) == expected,
        )
    if field.name in {"created_at", "updated_at"}:
        expected = date_part(value)
        if expected is None:
            return None
        key = f"{field.name}[]"
        return Case(
            field,
            [(key, expected.isoformat()), (key, expected.isoformat())],
            lambda item: date_part(item.get(field.name)) == expected,
        )
    if field.filter_type == "number":
        return target_number_case(field, value)
    return direct_case(field, value) or custom_case(field, value) or time_case(field, value)


def target_combination_result(
    client: MobileClient, product_id: int, cases: List[Case], per_page: int
) -> Result:
    params = [param for case in cases for param in case.params]
    returned, _ = client.products(params, per_page)
    returned_ids = {item.get("id") for item in returned}
    invalid_ids = [
        item.get("id") for item in returned if not all(case.matches(item) for case in cases)
    ]
    missing_target = product_id not in returned_ids
    if missing_target or invalid_ids:
        details = []
        if missing_target:
            details.append(f"未返回目标产品 {product_id}")
        if invalid_ids:
            details.append(f"不满足全部条件的产品: {invalid_ids[:5]}")
        return Result("FAIL", f"全字段组合筛选 ({len(cases)} 个条件)", "；".join(details))
    return Result(
        "PASS",
        f"全字段组合筛选 ({len(cases)} 个条件)",
        f"返回 {len(returned)} 条，包含目标产品 {product_id}，且全部满足条件",
    )


def check_case(
    client: MobileClient, case: Case, per_page: int
) -> Result:
    returned, _ = client.products(case.params, per_page)
    title = f"{case.field.label} ({case.field.name})"
    if not returned:
        return Result("FAIL", title, "接口返回 0 条，未命中用于构造条件的基准产品")
    invalid_ids = [product.get("id") for product in returned if not case.matches(product)]
    if invalid_ids:
        return Result("FAIL", title, f"不满足条件的产品: {invalid_ids[:5]}")
    return Result("PASS", title, f"返回 {len(returned)} 条，均符合条件")


def coverage_results(pc_fields: List[Dict[str, Any]], mobile_fields: List[Field]) -> List[Result]:
    pc_by_name = {
        PC_TO_MOBILE_FIELD.get(field["name"], field["name"]): field
        for field in pc_fields
        if field.get("name")
    }
    mobile_by_name = {field.name: field for field in mobile_fields}
    missing = [field for name, field in pc_by_name.items() if name not in mobile_by_name]
    extra = [field for name, field in mobile_by_name.items() if name not in pc_by_name]
    label_differences = [
        field
        for name, field in pc_by_name.items()
        if name in mobile_by_name and field.get("label") != mobile_by_name[name].label
    ]
    return [
        Result(
            "PASS" if not (missing or extra or label_differences) else "FAIL",
            "PC/移动端筛选字段一致性",
            "字段名和标签均与 PC 一致"
            if not (missing or extra or label_differences)
            else "；".join(
                part
                for part in [
                    "移动端缺少: " + "、".join(field.get("label", field["name"]) for field in missing)
                    if missing
                    else "",
                    "移动端多出: " + "、".join(field.label for field in extra) if extra else "",
                    "标签不一致: " + "、".join(field.get("name", "") for field in label_differences)
                    if label_differences
                    else "",
                ]
                if part
            ),
        ),
        Result(
            "PASS",
            "筛选字段数量",
            f"PC {len(pc_by_name)} 个，移动端 {len(mobile_by_name)} 个",
        ),
    ]


def write_report(results: List[Result], output: Optional[Path]) -> None:
    for result in results:
        print(f"[{result.status}] {result.title}: {result.detail}")
    summary = {
        status: sum(item.status == status for item in results)
        for status in ("PASS", "FAIL", "SKIP")
    }
    print(f"\n汇总: 通过 {summary['PASS']}，失败 {summary['FAIL']}，跳过 {summary['SKIP']}")
    if output:
        output.write_text(
            json.dumps(
                {"summary": summary, "results": [item.__dict__ for item in results]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"报告: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="只读验证移动端产品筛选接口")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--token", default=os.getenv("WWJ_USER_TOKEN"))
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--product-id", type=int, help="指定产品并验证其全部筛选字段组合")
    parser.add_argument(
        "--fields",
        help="逗号分隔的字段名，仅验证指定字段；默认验证全部已配置字段",
    )
    args = parser.parse_args()
    if not args.token:
        parser.error("缺少 --token，或设置 WWJ_USER_TOKEN")
    if args.per_page < 1 or args.max_pages < 1:
        parser.error("--per-page 和 --max-pages 必须大于 0")

    client = MobileClient(args.api, args.token, args.timeout)
    configured_fields = client.product_fields()
    pc_fields = client.pc_product_fields()
    if args.product_id:
        target = client.product_detail(args.product_id)
        if target.get("id") != args.product_id:
            raise RuntimeError(f"未读取到产品 {args.product_id}")
        results = coverage_results(pc_fields, configured_fields)
        cases: List[Case] = []
        missing: List[str] = []
        pc_field_names = {
            PC_TO_MOBILE_FIELD.get(item.get("name"), item.get("name"))
            for item in pc_fields
            if item.get("name")
        }
        fields = [field for field in configured_fields if field.name in pc_field_names]
        for field in fields:
            case = target_case(field, target)
            if case:
                cases.append(case)
            else:
                missing.append(f"{field.label} ({field.name})")
        if missing:
            results.append(
                Result(
                    "SKIP",
                    "全字段组合条件构造",
                    f"21 个 PC 字段中，以下 {len(missing)} 个字段没有移动端配置或目标产品没有可用于正向命中的值: "
                    + "、".join(missing),
                )
            )
        if cases:
            results.append(target_combination_result(client, args.product_id, cases, args.per_page))
        write_report(results, args.report)
        return 1 if any(result.status == "FAIL" for result in results) else 0

    products, _ = client.all_products(args.per_page, args.max_pages)
    if not products:
        raise RuntimeError("产品列表为空，无法构造筛选条件")
    baseline_ids = {product["id"] for product in products if product.get("id")}
    fields = configured_fields
    if args.fields:
        requested_names = {name.strip() for name in args.fields.split(",") if name.strip()}
        fields = [field for field in fields if field.name in requested_names]
        unknown_names = requested_names - {field.name for field in fields}
        if unknown_names:
            parser.error("字段不在产品筛选配置中: " + ", ".join(sorted(unknown_names)))
    print(
        f"已读取产品字段配置 {len(configured_fields)} 个，"
        f"本次验证 {len(fields)} 个，产品基准数据 {len(baseline_ids)} 条"
    )
    results = coverage_results(pc_fields, configured_fields)
    passing_cases: List[Case] = []

    for field in fields:
        title = f"{field.label} ({field.name})"
        if (
            field.filter_type not in SUPPORTED_TYPES
            and field.name not in {"lock_status", "shop_id"}
            and field.filter_type != "time"
        ):
            results.append(
                Result("SKIP", title, f"尚未抓到 {field.filter_type} 的列表参数格式")
            )
            continue
        case = next(
            (candidate for product in products if (candidate := build_case(field, product))),
            None,
        )
        if not case:
            results.append(
                Result("SKIP", title, "没有可用于构造条件的值，或该时间字段仅支持相对时间")
            )
            continue
        result = check_case(client, case, args.per_page)
        results.append(result)
        if result.status == "PASS":
            passing_cases.append(case)

    for product in products:
        cases = [case for case in passing_cases if case.matches(product)]
        if len(cases) >= 2:
            selected = cases[:3]
            params = [param for case in selected for param in case.params]
            returned, _ = client.products(params, args.per_page)
            invalid_ids = [
                item.get("id") for item in returned if not all(case.matches(item) for case in selected)
            ]
            fields_text = " + ".join(case.field.label for case in selected)
            status = "PASS" if returned and not invalid_ids else "FAIL"
            detail = (
                f"返回 {len(returned)} 条，均符合条件"
                if status == "PASS"
                else "组合条件未命中或返回了不符合条件的产品"
            )
            results.append(Result(status, f"组合筛选 ({fields_text})", detail))
            break
    else:
        results.append(Result("SKIP", "组合筛选", "没有同一产品具备两个已验证字段条件"))

    write_report(results, args.report)
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(2)
