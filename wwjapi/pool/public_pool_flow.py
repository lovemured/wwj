#!/usr/bin/env python3
"""线索池 + 客户公海冒烟流程

使用:
  python3 pool/public_pool_flow.py
  python3 pool/public_pool_flow.py --api https://lxcrm-staging.weiwenjia.com --token your_token
  python3 pool/public_pool_flow.py --admin-token admin_token --member-token member_token
  python3 pool/public_pool_flow.py --admin-token admin_token --member-token member_token --take-mode single
  python3 pool/public_pool_flow.py --admin-token admin_token --member-token member_token --take-mode batch
  python3 pool/public_pool_flow.py --lead-pool-id 123 --customer-pool-id 456

流程:
  1. 复用/新建专用线索池，从普通线索列表取最早的已通过线索，批量转入线索池，查询线索池列表，抢回线索
  2. 复用/新建专用客户公海，从普通客户列表取最早的已通过客户，批量转入客户公海，查询客户公海列表，抢回客户

说明:
  - 线索池、客户公海默认按固定名称复用，不存在时才创建，避免每次运行都新增配置。
  - 管理员token负责创建数据、转入线索池/客户公海；成员token负责从池/公海抢回。
  - --take-mode single 对应列表每行后面的“抢”；--take-mode batch 对应顶部批量“抢”按钮。
  - 如果不传 --member-token，会优先读取config.json中的member_token；仍未配置时才使用管理员token兼容单账号环境。
  - 指定 --lead-pool-id/--customer-pool-id 时，会复用管理员可转入且成员可抢回的已有配置。
"""
import argparse
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import load_config
from lib.upload import pc_url

DEFAULT_LEAD_POOL_NAME = "自动化线索池"
DEFAULT_CUSTOMER_POOL_NAME = "自动化客户公海"


def headers(token):
    return {"Content-Type": "application/json", "Authorization": f"Token token={token}"}


def api_base(api, pc=False):
    return f"{pc_url(api).rstrip('/')}/api/pc" if pc else f"{api.rstrip('/')}/api/v2"


def request_json(method, url, token, **kwargs):
    try:
        resp = requests.request(method, url, headers=headers(token), timeout=kwargs.pop("timeout", 60), **kwargs)
    except requests.RequestException as exc:
        return {"code": -1, "message": f"请求失败: {exc}"}
    try:
        body = resp.json()
    except ValueError:
        body = {"code": -1, "message": resp.text[:500]}
    if resp.status_code >= 400 and isinstance(body, dict):
        body.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return body


def ok(resp):
    return str(resp.get("code")) == "0"


def first_id(resp):
    data = resp.get("data")
    if isinstance(data, dict):
        if data.get("id"):
            return data.get("id")
        for key in ("list", "leads", "customers"):
            items = data.get(key)
            if isinstance(items, list) and items:
                return items[0].get("id")
    return None


def response_items(resp):
    data = resp.get("data") or {}
    if isinstance(data, dict):
        for key in ("list", "customers", "common_settings", "customer_common_settings", "lead_common_settings"):
            items = data.get(key)
            if isinstance(items, list):
                return items
    return []


def choose_shared_pool(admin_pools, member_pools, pool_id):
    member_ids = {int(item.get("id") or 0) for item in member_pools}
    candidates = [item for item in admin_pools if int(item.get("id") or 0) in member_ids]
    if pool_id:
        return next((item for item in candidates if int(item.get("id") or 0) == pool_id), None)
    candidates.sort(key=lambda item: (bool(item.get("auto_distribute")), bool(item.get("auto_follow"))))
    return candidates[0] if candidates else None


def find_pool_by_name(pools, name):
    return next((item for item in pools if item.get("name") == name), None)


def find_shared_pool_by_name(admin_pools, member_pools, name):
    member_ids = {int(item.get("id") or 0) for item in member_pools}
    return next((item for item in admin_pools if item.get("name") == name and int(item.get("id") or 0) in member_ids), None)


def current_user(api, token):
    resp = request_json("GET", f"{api_base(api)}/user/info", token)
    user = resp.get("data") or {}
    if not user.get("id"):
        raise RuntimeError(f"获取当前用户失败: {resp}")
    return user


def get_lead_pools(api, token):
    resp = request_json("GET", f"{api_base(api, pc=True)}/lead_commons/common_settings", token)
    pools = response_items(resp)
    if not pools:
        resp = request_json("GET", f"{api.rstrip()}/api/v2/common_leads/common_settings", token)
        pools = response_items(resp)
    return pools


def get_customer_pools(api, token):
    resp = request_json("GET", f"{api_base(api, pc=True)}/customer_commons/common_settings", token)
    return response_items(resp)


def create_lead_pool(api, admin_token, member_token, args, name):
    member_ids = [int(item) for item in (args.lead_pool_member_ids or [])]
    if not member_ids:
        member_ids = [current_user(api, member_token)["id"]]
    payload = {
        "lead_common_setting": {
            "name": name,
            "member_user_ids": member_ids,
            "member_department_ids": [],
            "admin_user_ids": [],
            "member_data_enable": True,
            "auto_distribute": False,
            "lead_setting_rules_attributes": [],
        }
    }
    resp = request_json("POST", f"{api_base(api, pc=True)}/settings/lead_commons", admin_token, json=payload)
    pool_id = first_id(resp)
    if not pool_id:
        raise RuntimeError(f"创建专用线索池失败: {resp}")
    return {"id": pool_id, "name": name, "member_user_ids": member_ids}


def create_customer_pool(api, admin_token, member_token, args, name):
    member_ids = [int(item) for item in (args.customer_pool_member_ids or [])]
    if not member_ids:
        member_ids = [current_user(api, member_token)["id"]]
    payload = {
        "customer_common_setting": {
            "name": name,
            "member_user_ids": member_ids,
            "member_department_ids": [],
            "admin_user_ids": [],
            "member_data_enable": True,
            "auto_distribute": False,
            "customer_setting_rules_attributes": [],
        }
    }
    resp = request_json("POST", f"{api_base(api, pc=True)}/settings/customer_commons", admin_token, json=payload)
    pool_id = first_id(resp)
    if not pool_id:
        raise RuntimeError(f"创建专用客户公海失败: {resp}")
    return {"id": pool_id, "name": name, "member_user_ids": member_ids}


def choose_or_create_lead_pool(api, admin_token, member_token, args):
    admin_pools = get_lead_pools(api, admin_token)
    member_pools = get_lead_pools(api, member_token)
    if args.lead_pool_id:
        pool = choose_shared_pool(admin_pools, member_pools, args.lead_pool_id)
        if not pool:
            raise RuntimeError(f"线索池 {args.lead_pool_id} 不是管理员可转入且成员可抢回的共同池")
        return pool
    name = args.lead_pool_name or DEFAULT_LEAD_POOL_NAME
    pool = find_shared_pool_by_name(admin_pools, member_pools, name)
    if pool:
        return pool
    if find_pool_by_name(admin_pools, name):
        raise RuntimeError(f"已存在线索池「{name}」，但成员token不可见/不可抢回，请检查线索池成员配置")
    return create_lead_pool(api, admin_token, member_token, args, name)


def choose_or_create_customer_pool(api, admin_token, member_token, args):
    admin_pools = get_customer_pools(api, admin_token)
    member_pools = get_customer_pools(api, member_token)
    if args.customer_pool_id:
        pool = choose_shared_pool(admin_pools, member_pools, args.customer_pool_id)
        if not pool:
            raise RuntimeError(f"客户公海 {args.customer_pool_id} 不是管理员可转入且成员可抢回的共同公海")
        return pool
    name = args.customer_pool_name or DEFAULT_CUSTOMER_POOL_NAME
    pool = find_shared_pool_by_name(admin_pools, member_pools, name)
    if pool:
        return pool
    if find_pool_by_name(admin_pools, name):
        raise RuntimeError(f"已存在客户公海「{name}」，但成员token不可见/不可抢回，请检查客户公海成员配置")
    return create_customer_pool(api, admin_token, member_token, args, name)


def fetch_transferable_leads(api, token, count):
    selected = []
    page = 1
    while len(selected) < count and page <= 10:
        resp = request_json(
            "GET",
            f"{api_base(api, pc=True)}/leads",
            token,
            params={"page": page, "per_page": 50, "sort": "created_at", "order": "asc", "approve_status": "approved"},
        )
        if not ok(resp):
            raise RuntimeError(f"查询线索列表失败: {resp}")
        items = response_items(resp)
        if not items:
            break
        for item in items:
            if item.get("approve_status") != "approved":
                continue
            if item.get("lead_common_setting_id"):
                continue
            if item.get("turned_to_customer"):
                continue
            if item.get("id"):
                selected.append(item)
            if len(selected) >= count:
                break
        page += 1
    if len(selected) < count:
        raise RuntimeError(f"可转入线索不足，需要{count}条，实际找到{len(selected)}条")
    return selected[:count]


def fetch_transferable_customers(api, token, count):
    selected = []
    page = 1
    while len(selected) < count and page <= 10:
        resp = request_json(
            "GET",
            f"{api_base(api, pc=True)}/customers",
            token,
            params={"page": page, "per_page": 50, "sort": "created_at", "order": "asc", "approve_status": "approved"},
        )
        if not ok(resp):
            raise RuntimeError(f"查询客户列表失败: {resp}")
        items = response_items(resp)
        if not items:
            break
        for item in items:
            if item.get("approve_status") != "approved":
                continue
            if item.get("customer_common_setting_id") or item.get("common_setting_id") or item.get("common_id"):
                continue
            if item.get("id"):
                selected.append(item)
            if len(selected) >= count:
                break
        page += 1
    if len(selected) < count:
        raise RuntimeError(f"可转入客户不足，需要{count}条，实际找到{len(selected)}条")
    return selected[:count]


def transfer_leads_to_pool(api, token, lead_ids, pool_id):
    return request_json(
        "PUT",
        f"{api_base(api, pc=True)}/batch_resources/mass_transfer_to_common_pool",
        token,
        json={"resource_ids": lead_ids, "common_id": pool_id, "resource_type": "Lead"},
    )


def transfer_customers_to_pool(api, token, customer_ids, pool_id):
    batch_resp = request_json(
        "PUT",
        f"{api_base(api, pc=True)}/batch_resources/mass_transfer_to_common_pool",
        token,
        json={"resource_ids": customer_ids, "common_id": pool_id, "resource_type": "Customer"},
    )
    if ok(batch_resp):
        return {"code": 0, "message": batch_resp.get("message") or "批量转入客户公海成功", "mode": "batch", "resp": batch_resp}

    results = []
    for customer_id in customer_ids:
        api_label, resp = transfer_customer_to_pool(api, token, customer_id, pool_id)
        results.append({"customer_id": customer_id, "api": api_label, "resp": resp})
        if not api_label:
            return {"code": -1, "message": "客户转入公海失败", "batch_resp": batch_resp, "results": results}
    return {"code": 0, "message": f"成功逐条转入{len(customer_ids)}个客户", "mode": "single", "batch_resp": batch_resp, "results": results}


def transfer_customer_to_pool(api, token, customer_id, pool_id):
    attempts = [
        ("PUT /api/pc/customers/:id/turn_common", "PUT", f"{api_base(api, pc=True)}/customers/{customer_id}/turn_common", {"params": {"common_id": pool_id}}),
        (
            "PUT /api/pc/customers/:id/transfer_to_common_pool",
            "PUT",
            f"{api_base(api, pc=True)}/customers/{customer_id}/transfer_to_common_pool",
            {"params": {"common_id": pool_id}},
        ),
        (
            "PUT /api/pc/customers/:id/turn_common(json)",
            "PUT",
            f"{api_base(api, pc=True)}/customers/{customer_id}/turn_common",
            {"json": {"common_id": pool_id}},
        ),
    ]
    return first_success(token, attempts)


def first_success(token, attempts):
    errors = []
    for label, method, url, kwargs in attempts:
        resp = request_json(method, url, token, **kwargs)
        if ok(resp):
            return label, resp
        errors.append({"api": label, "resp": resp})
    return None, {"code": -1, "message": "所有候选接口均失败", "errors": errors}


def list_lead_pool(api, token, pool_id):
    return request_json(
        "GET",
        f"{api_base(api, pc=True)}/lead_commons",
        token,
        params={"common_id": pool_id, "page": 1, "per_page": 20, "sort": "created_at", "order": "desc"},
    )


def list_customer_pool(api, token, pool_id):
    return request_json(
        "GET",
        f"{api_base(api, pc=True)}/customer_commons",
        token,
        params={"common_id": pool_id, "page": 1, "per_page": 20, "sort": "created_at", "order": "desc"},
    )


def contains_all_ids(resp, entity_ids):
    found = {int(item.get("id") or 0) for item in response_items(resp)}
    return all(int(entity_id) in found for entity_id in entity_ids)


def take_leads(api, token, lead_ids, pool_id, take_mode):
    if take_mode == "single":
        results = []
        for lead_id in lead_ids:
            resp = request_json("POST", f"{api_base(api)}/leads/{lead_id}/take", token)
            results.append({"lead_id": lead_id, "resp": resp})
            if not ok(resp):
                return {"code": -1, "message": "单条抢线索失败", "results": results}
        return {"code": 0, "message": f"成功单条抢回{len(lead_ids)}个线索", "results": results}
    return request_json(
        "PUT",
        f"{api_base(api, pc=True)}/batch_resources/bulk_take",
        token,
        json={"resource_type": "LeadCommon", "resource_ids": lead_ids, "common_id": pool_id},
    )


def take_customer(api, token, customer_id, pool_id, take_mode):
    if take_mode == "single":
        return request_json("PUT", f"{api_base(api, pc=True)}/customers/{customer_id}/take", token)
    return request_json(
        "PUT",
        f"{api_base(api, pc=True)}/batch_resources/bulk_take",
        token,
        json={"resource_type": "CustomerCommon", "resource_ids": [customer_id], "common_id": pool_id},
    )


def take_customers(api, token, customer_ids, pool_id, take_mode):
    if take_mode == "single":
        results = []
        for customer_id in customer_ids:
            resp = take_customer(api, token, customer_id, pool_id, take_mode)
            results.append({"customer_id": customer_id, "resp": resp})
            if not ok(resp):
                return {"code": -1, "message": "单条抢客户失败", "results": results}
        return {"code": 0, "message": f"成功单条抢回{len(customer_ids)}个客户", "results": results}
    return request_json(
        "PUT",
        f"{api_base(api, pc=True)}/batch_resources/bulk_take",
        token,
        json={"resource_type": "CustomerCommon", "resource_ids": customer_ids, "common_id": pool_id},
    )


def run_lead_pool(args):
    print("\n[线索池]")
    pool = choose_or_create_lead_pool(args.api, args.admin_token, args.member_token, args)
    print(f"  目标线索池: {pool.get('name')}({pool.get('id')})")

    leads = fetch_transferable_leads(args.api, args.admin_token, args.lead_count)
    lead_ids = [item["id"] for item in leads]
    print(f"  ✅ 选取最早已通过线索: {','.join(str(item) for item in lead_ids)}")

    transfer_resp = transfer_leads_to_pool(args.api, args.admin_token, lead_ids, pool["id"])
    if not ok(transfer_resp):
        raise RuntimeError(f"批量转入线索池失败: {transfer_resp}")
    print(f"  ✅ 批量转入线索池: {transfer_resp.get('message') or '成功'}")

    time.sleep(1)
    list_resp = list_lead_pool(args.api, args.member_token, pool["id"])
    print(f"  {'✅' if contains_all_ids(list_resp, lead_ids) else '○'} 线索池列表查询: {'找到全部线索' if contains_all_ids(list_resp, lead_ids) else '未在第一页找到全部线索'}")

    take_resp = take_leads(args.api, args.member_token, lead_ids, pool["id"], args.take_mode)
    if not ok(take_resp):
        raise RuntimeError(f"抢回线索失败: {take_resp}")
    print(f"  ✅ 抢回线索({args.take_mode}): {','.join(str(item) for item in lead_ids)}")
    return {"pool_id": pool["id"], "lead_ids": lead_ids}


def run_customer_pool(args):
    print("\n[客户公海]")
    pool = choose_or_create_customer_pool(args.api, args.admin_token, args.member_token, args)
    print(f"  目标客户公海: {pool.get('name')}({pool.get('id')})")

    customers = fetch_transferable_customers(args.api, args.admin_token, args.customer_count)
    customer_ids = [item["id"] for item in customers]
    print(f"  ✅ 选取最早已通过客户: {','.join(str(item) for item in customer_ids)}")

    transfer_resp = transfer_customers_to_pool(args.api, args.admin_token, customer_ids, pool["id"])
    if not ok(transfer_resp):
        raise RuntimeError(f"客户转入公海失败: {transfer_resp}")
    print(f"  ✅ 转入客户公海({transfer_resp.get('mode')}): {transfer_resp.get('message') or '成功'}")

    list_resp = list_customer_pool(args.api, args.member_token, pool["id"])
    print(f"  {'✅' if contains_all_ids(list_resp, customer_ids) else '○'} 客户公海列表查询: {'找到全部客户' if contains_all_ids(list_resp, customer_ids) else '未在第一页找到全部客户'}")

    take_resp = take_customers(args.api, args.member_token, customer_ids, pool["id"], args.take_mode)
    if not ok(take_resp):
        raise RuntimeError(f"抢回客户失败: {take_resp}")
    print(f"  ✅ 抢回客户({args.take_mode}): {','.join(str(item) for item in customer_ids)}")
    return {"pool_id": pool["id"], "customer_ids": customer_ids}


def main():
    parser = argparse.ArgumentParser(description="线索池 + 客户公海冒烟流程")
    parser.add_argument("--api")
    parser.add_argument("--env", choices=["test", "staging", "production"])
    parser.add_argument("--token", help="兼容参数，等价于 --admin-token")
    parser.add_argument("--admin-token", help="线索池/客户公海管理员token，用于创建、转入、查询配置")
    parser.add_argument("--member-token", help="线索池/客户公海成员token，用于抢回")
    parser.add_argument("--lead-pool-id", type=int, help="指定线索池ID")
    parser.add_argument("--lead-pool-name", default=DEFAULT_LEAD_POOL_NAME, help=f"复用/新建线索池名称，默认：{DEFAULT_LEAD_POOL_NAME}")
    parser.add_argument("--lead-pool-member-ids", type=lambda value: [int(item) for item in value.split(",") if item], help="新建线索池成员用户ID，逗号分隔；默认取member-token当前用户")
    parser.add_argument("--lead-count", type=int, default=5, help="批量转入线索数量")
    parser.add_argument("--customer-pool-id", type=int, help="指定客户公海ID")
    parser.add_argument("--customer-pool-name", default=DEFAULT_CUSTOMER_POOL_NAME, help=f"复用/新建客户公海名称，默认：{DEFAULT_CUSTOMER_POOL_NAME}")
    parser.add_argument("--customer-pool-member-ids", type=lambda value: [int(item) for item in value.split(",") if item], help="新建客户公海成员用户ID，逗号分隔；默认取member-token当前用户")
    parser.add_argument("--customer-count", type=int, default=5, help="批量转入客户数量")
    parser.add_argument("--take-mode", choices=["single", "batch"], default="single", help="single=行内抢，batch=顶部批量抢")
    parser.add_argument("--only", choices=["all", "lead", "customer"], default="all")
    args = parser.parse_args()
    cfg = load_config(args.env)
    args.api = args.api or cfg.get("api", "")
    args.token = args.token or cfg.get("token", "")
    if not args.api:
        parser.error(f"请在config.{args.env}.json中配置api，或通过--api传入" if args.env else "请在config.json中配置api，或通过--api传入")
    args.api = args.api.rstrip("/")
    args.admin_token = args.admin_token or args.token
    args.member_token = args.member_token or cfg.get("member_token") or args.admin_token
    if not args.admin_token:
        parser.error(f"请在config.{args.env}.json中配置token，或通过--token/--admin-token传入管理员token" if args.env else "请在config.json中配置token，或通过--token/--admin-token传入管理员token")
    if not args.member_token:
        parser.error("请通过--member-token传入成员token，或使用--token兼容单账号环境")

    print(f"{'=' * 70}\n线索池 + 客户公海冒烟流程\nAPI: {args.api}\n{'=' * 70}")
    print(f"管理员token: {args.admin_token[:6]}***{args.admin_token[-4:]}")
    print(f"成员token: {args.member_token[:6]}***{args.member_token[-4:]}")
    results = {}
    if args.only in ("all", "lead"):
        results["lead"] = run_lead_pool(args)
    if args.only in ("all", "customer"):
        results["customer"] = run_customer_pool(args)

    print(f"\n{'=' * 70}\n完成\n{'=' * 70}")
    if results.get("lead"):
        print(f"线索池:{results['lead']['pool_id']} 线索:{','.join(str(item) for item in results['lead']['lead_ids'])}")
    if results.get("customer"):
        print(f"客户公海:{results['customer']['pool_id']} 客户:{','.join(str(item) for item in results['customer']['customer_ids'])}")


if __name__ == "__main__":
    main()
