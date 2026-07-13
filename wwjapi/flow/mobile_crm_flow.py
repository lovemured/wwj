#!/usr/bin/env python3
"""移动端CRM创建全流程: 产品 -> 市场活动 -> 线索 -> 客户/联系人 -> 商机 -> 报价单 -> 合同 -> 回款计划 -> 回款记录 -> 开票记录 -> 拜访计划 -> 拜访签到 -> 工作报告

使用:
  python3 flow/mobile_crm_flow.py
  python3 flow/mobile_crm_flow.py --api https://lxcrm-staging.weiwenjia.com --token your_token
  python3 flow/mobile_crm_flow.py --cnt 3

说明:
  - 该脚本只走移动端/H5使用的 /api/v2 接口，不混用 PC 全流程代码。
  - 该脚本会先新增产品，后续商机/报价单/合同直接引用本轮新增产品。
  - 业务类型默认值来自移动端抓包，可通过参数覆盖。
"""
import argparse
import os
import random
import string
import sys
import time
import uuid
from datetime import datetime, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import upload_to_oss


TOKEN = ""
API = ""
API_BASE = ""
CHECKIN_API = ""


def api_base(api):
    api = api.rstrip("/")
    return api.replace("//lxcrm-staging.", "//lxcrm-api-staging.").replace("//lxcrm-test.", "//lxcrm-api-test.").replace("//lxcrm.", "//lxcrm-api.")


def checkin_api_base(api):
    if "staging" in api:
        return "https://staging-pc-checkin.ikcrm.com"
    if "test" in api:
        return "https://test-pc-checkin.ikcrm.com"
    return "https://pc-checkin.ikcrm.com"


def mobile_headers():
    return {
        "accept": "*/*",
        "authorization": f'Token token="{TOKEN}",device="lxcrm_duli",version_code="4.0.1"',
        "content-type": "application/json; chartset=utf-8",
        "origin": API.rstrip("/").replace("://lxcrm.", "://crmh5.").replace("lxcrm-", "crmh5-"),
        "x-requested-with": "com.lixiaoyun.aike",
        "x-lx-gid": "wwjOILf2wJkAF7CiLHlI",
    }


def request_json(method, path, data=None, params=None, timeout=60):
    params = dict(params or {})
    if method.upper() in ("POST", "PUT", "PATCH"):
        params.setdefault("request_ticket", str(uuid.uuid4()))
    clean_path = path.lstrip("/")
    if clean_path.startswith("apaas/"):
        url = f"{API_BASE}/{clean_path}"
    else:
        url = f"{API_BASE}/api/v2/{clean_path}"
    last_body = None
    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=mobile_headers(), json=data, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_body = {"code": -1, "message": f"请求失败: {exc}"}
        else:
            try:
                body = resp.json()
            except ValueError:
                body = {"code": -1, "message": resp.text[:500]}
            if resp.status_code >= 400 and isinstance(body, dict):
                body.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
            message = str(body.get("message", "")) if isinstance(body, dict) else ""
            if "Retry later" not in message:
                return body
            last_body = body
        if attempt < 2:
            time.sleep(2 + attempt)
    return last_body


def checkin_request_json(method, path, data=None, params=None, timeout=60):
    params = dict(params or {})
    if method.upper() in ("POST", "PUT", "PATCH"):
        params.setdefault("request_ticket", str(uuid.uuid4()))
    url = f"{CHECKIN_API.rstrip('/')}/api/v3/{path.lstrip('/')}"
    last_body = None
    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=mobile_headers(), json=data, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_body = {"code": -1, "message": f"请求失败: {exc}"}
        else:
            try:
                body = resp.json()
            except ValueError:
                body = {"code": -1, "message": resp.text[:500]}
            if resp.status_code >= 400 and isinstance(body, dict):
                body.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
            message = str(body.get("message", "")) if isinstance(body, dict) else ""
            if "Retry later" not in message:
                return body
            last_body = body
        if attempt < 2:
            time.sleep(2 + attempt)
    return last_body


def checkin_signout_enabled():
    headers = mobile_headers()
    headers["apptype"] = "ikcrm"
    try:
        resp = requests.get(f"{CHECKIN_API.rstrip('/')}/api/pc/v3/setting_get", headers=headers, timeout=30)
    except requests.RequestException:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    setting = ((data.get("data") or {}).get("checkinSetting") or {})
    return int(setting.get("checkinOutFlg") or 0) == 1


def rid(prefix):
    return f"{prefix}{str(int(time.time() * 1000))[-8:]}{''.join(random.choices(string.digits, k=2))}"


def date_after(days, with_time=False):
    value = datetime.now() + timedelta(days=days)
    return value.strftime("%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d")


def money():
    return random.randint(80, 800)


def get_current_user():
    data = request_json("GET", "user/info")
    user = data.get("data") or {}
    if data.get("code") != 0 or not user.get("id"):
        raise RuntimeError(f"获取当前用户失败: {data}")
    return user


def get_products(limit=2):
    data = request_json("GET", "products", params={"page": 1, "per_page": max(limit, 2)})
    products = (data.get("data") or {}).get("products") or []
    if data.get("code") != 0 or not products:
        raise RuntimeError(f"获取产品失败: {data}")
    return products[:limit]


def get_product_category_id():
    data = request_json("GET", "product_categories")
    products = (data.get("data") or {}).get("products") or []
    for item in products:
        if item.get("id"):
            return item.get("id")
    return None


def get_lead_detail(lead_id):
    data = request_json("GET", f"leads/{lead_id}")
    if data.get("code") != 0:
        raise RuntimeError(f"获取线索详情失败: {data}")
    return data.get("data") or {}


def get_simple_users(limit=5):
    data = request_json("GET", "user/simple_list", params={"page": 1, "per_page": 50})
    users = data.get("simple_users") or (data.get("data") or {}).get("simple_users") or []
    ids = [item.get("value") or item.get("id") for item in users if item.get("value") or item.get("id")]
    return [int(item) for item in ids[:limit] if str(item).isdigit()]


def get_pc_user_ids(limit=50):
    url = f"{API_BASE}/api/pc/users"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Token token={TOKEN}"},
            params={"page": 1, "per_page": limit},
            timeout=30,
        )
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []
    users = (data.get("data") or {}).get("users") or (data.get("data") or {}).get("list") or []
    ids = [item.get("id") or item.get("uid") for item in users if item.get("id") or item.get("uid")]
    return [int(item) for item in ids if str(item).isdigit()]


def fetch_apaas_values(custom_form_id, limit=5):
    data = request_json(
        "GET",
        "/apaas/api/v2/form_entities/simple",
        params={"page": 1, "per_page": limit, "without_count": "true", "custom_form_id": custom_form_id},
    )
    models = (data.get("data") or {}).get("models") or []
    return [item.get("value") or item.get("id") for item in models if item.get("value") or item.get("id")]


def local_files(attachment_dir):
    if not attachment_dir or not os.path.isdir(attachment_dir):
        return [], []
    images = []
    docs = []
    doc_exts = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".ppt", ".pptx"}
    for name in os.listdir(attachment_dir):
        if name.startswith("."):
            continue
        path = os.path.join(attachment_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"):
            images.append(path)
        elif ext in doc_exts:
            docs.append(path)
    return images, docs


def upload_first(paths):
    for path in paths:
        aid = upload_to_oss(API, TOKEN, path)
        if aid:
            return aid
    return None


def upload_market_files(args):
    images, docs = local_files(args.attachment_dir)
    file_id = upload_first(docs)
    if not file_id:
        file_id = upload_to_oss(API, TOKEN, None)
    image_id = upload_first(images)
    attachment_id = upload_first((docs + images) or (images + docs))
    return file_id, image_id, [attachment_id] if attachment_id else []


def upload_pair_files(args):
    images, docs = local_files(args.attachment_dir)
    file_id = upload_first(docs)
    if not file_id:
        file_id = upload_to_oss(API, TOKEN, None)
    image_id = upload_first(images)
    return file_id, image_id


def product_assets(products):
    attrs = []
    for index, product in enumerate(products, 1):
        unit_price = float(product.get("standard_unit_price") or 1)
        quantity = 1
        item = {
            "key": "new_data_" + "".join(random.choices(string.ascii_letters + string.digits, k=8)),
            "product.name": product.get("name"),
            "product_id": product.get("id"),
            "product": dict(product, value=product.get("id"), label=product.get("name")),
            "standard_unit_price": unit_price,
            "recommended_unit_price": unit_price,
            "quantity": quantity,
            "discount": 1,
            "total_price": round(unit_price * quantity, 2),
            "position": index,
        }
        attrs.append(item)
    return attrs


def create_product(user, args, index):
    name = rid("移动产品-")
    file_id, custom_image_id = upload_pair_files(args)
    images, _ = local_files(args.attachment_dir)
    product_image_id = upload_first(images)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:2]
    product = {
        "name": name,
        "product_no": "MPROD" + str(int(time.time()))[-6:] + str(index),
        "attachment_ids": [product_image_id] if product_image_id else [],
        "standard_unit_price": money(),
        "sale_unit": random.choice(["个", "台", "套", "件"]),
        "unit_cost": money(),
        "introduction": f"{name} 介绍",
        "spec": f"{name} 规格",
        "file_asset_dfad4f": {"attachment_ids": [file_id] if file_id else []},
        "file_asset_16e1c7": {"attachment_ids": [custom_image_id] if custom_image_id else []},
        "text_asset_4f5c49_other": "",
        "text_asset_4f5c49": "sel_3712",
        "text_asset_e20853": ["mul_0ca5", "mul_6023"],
        "user_field_asset_e63d73": [user["id"]],
        "user_field_asset_6d7530": [user["id"]] + assist_user_ids,
        "subform_asset_5b4e1f": [],
        "approve_status": "approved",
    }
    category_id = get_product_category_id()
    if category_id:
        product["product_category_id"] = category_id
    data = {"product": product, "attachment_ids": [product_image_id] if product_image_id else []}
    return request_json("POST", "products", data=data), name


def create_products(user, args):
    products = []
    for index in range(1, args.product_count + 1):
        resp, name = create_product(user, args, index)
        product_id = require_id("新增产品", resp)
        product = resp.get("data") or {}
        product.setdefault("id", product_id)
        product.setdefault("name", name)
        product.setdefault("standard_unit_price", product.get("standard_unit_price") or 1)
        products.append(product)
        print(f"  ✅ 1/17 产品 {index}/{args.product_count}: {product_id} {name}")
    return products


def create_market_activity(user, args):
    name = rid("移动市场活动-")
    file_id, image_id, attachment_ids = upload_market_files(args)
    assist_user_ids = [uid for uid in get_simple_users(5) if uid != user["id"]][:3]
    data = {
        "market_activity": {
            "custom_field_template_id": args.market_template_id,
            "name": name,
            "category": 2103386,
            "start_date": date_after(1),
            "end_date": date_after(90),
            "estimated_cost": money(),
            "actual_cost": money(),
            "estimated_income": money() * 2,
            "actual_income": money() * 2,
            "status": 2103391,
            "address_attributes": {
                "country_id": 4,
                "province_id": 28,
                "city_id": 307,
                "district_id": 4030,
                "detail_address": "上海市浦东新区峨山路91弄",
                "lat": 31.21625,
                "lng": 121.532983,
            },
            "description": f"{name} 描述",
            "schedule": f"{name} 计划",
            "summary": f"{name} 总结",
            "note": f"{name} 备注",
            "text_asset_452acf": f"{name} 文本",
            "text_asset_2d730c": f"{rid('mail').lower()}@example.com",
            "text_asset_b0e8b9": "138" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_9791b5": f"{name} 自定义多行文本",
            "numeric_asset_516446": money(),
            "numeric_asset_7ae511": round(random.uniform(1, 99), 2),
            "numeric_asset_d4c517": money(),
            "file_asset_81e797": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_355de0": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_5983c8": date_after(2, True)[:-3],
            "datetime_asset_77c0c4": date_after(3),
            "text_asset_3b327b_other": "",
            "text_asset_3b327b": "sel_4744",
            "text_asset_360484": ["mul_6f15", "mul_4327", "mul_39f5"],
            "text_asset_942909": f"https://example.com/mobile-market/{int(time.time())}",
            "text_asset_cd0724": "eb35b6b4-1be4-425d-a0e7-e3543b63b5f4",
            "user_field_asset_f18ab6": [user["id"]],
            "user_field_asset_cdcd6f": [user["id"]] + assist_user_ids[:2],
            "user_field_asset_cb7899": [user.get("department_id")],
            "user_field_asset_74a3c8": [user.get("department_id")],
            "text_asset_75c13d": ["nes_f16e", "nes_14bd", "nes_7348"],
            "subform_asset_03e453": [],
            "custom_relation_asset_89aa2c": 18,
            "attachment_ids": attachment_ids,
            "revisit_remind_at": date_after(30, True)[:-3],
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": assist_user_ids,
            "approve_status": "approved",
        },
        "attachment_ids": attachment_ids,
    }
    return request_json("POST", "market_activities", data=data), name


def create_lead(user, market_activity_id, args):
    name = rid("移动线索-")
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]]
    visit_plan_values = fetch_apaas_values(277)
    apaas_values = fetch_apaas_values(335)
    data = {
        "lead": {
            "custom_field_template_id": args.lead_template_id,
            "name": name,
            "company_name": rid("移动线索公司-"),
            "market_activity_id": market_activity_id,
            "department": "移动测试部",
            "job": "移动测试岗位",
            "address_attributes": {
                "tel": "",
                "phone": "139" + "".join(random.choices(string.digits, k=8)),
                "wechat": rid("wx"),
                "qq": str(random.randint(100000, 999999)),
                "wangwang": rid("ww"),
                "country_id": 4,
                "province_id": 28,
                "city_id": 307,
                "district_id": 4030,
                "detail_address": "上海市浦东新区峨山路91弄",
                "lat": 31.21625,
                "lng": 121.532983,
                "zip": "200120",
            },
            "text_asset_2095bb": f"{name} 单行文本",
            "text_asset_71ce4b": f"{rid('leadmail').lower()}@example.com",
            "text_asset_33b4ba": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_1a816d": f"{name} 多行文本",
            "numeric_asset_3160c3": money(),
            "numeric_asset_493a2f": round(random.uniform(1, 99), 2),
            "numeric_asset_63be61": money(),
            "file_asset_099c55": {"attachment_ids": []},
            "file_asset_5e763f": {"attachment_ids": []},
            "datetime_asset_5d3cd9": date_after(1, True),
            "datetime_asset_beca71": date_after(2),
            "text_asset_b6b26a_other": "",
            "text_asset_b6b26a": "sel_d551",
            "text_asset_61ac37": ["mul_f7e1", "mul_938c"],
            "text_asset_2c5471": f"https://example.com/mobile-lead/{int(time.time())}",
            "text_asset_4e6ad8": "b9547578-2186-4ee8-9bcb-52fd0b05cf5b/nes_8b62",
            "user_field_asset_03be5a": [user["id"]],
            "user_field_asset_9a4657": [user["id"]] + assist_user_ids[:2],
            "user_field_asset_3b1490": [user.get("department_id")],
            "user_field_asset_29bf74": [user.get("department_id")],
            "text_asset_2b431c_other": "",
            "text_asset_2b431c": "sel_5597",
            "text_asset_06269b_other": "",
            "text_asset_06269b": "sel_8413",
            "text_asset_ed3b3a": ["nes_c7c4", "nes_19ab", "nes_32f4"],
            "custom_relation_asset_4bed23": visit_plan_values[0] if visit_plan_values else None,
            "custom_relation_asset_554137": apaas_values[0] if apaas_values else None,
            "subform_asset_fa2e7f": [],
            "status": args.lead_status,
            "source": None,
            "note": f"{name} 备注",
            "channel": None,
            "revisit_remind_at": date_after(7, True)[:-3],
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "approve_status": "approved",
        }
    }
    return request_json("POST", "leads", data=data), name


def init_turn_to_customer(lead_id, args):
    return request_json(
        "GET",
        f"leads/{lead_id}/turn_to_customer",
        params={"is_check": "false", "custom_field_template_id": args.customer_template_id},
    )


def create_customer_from_lead(user, lead_id, lead_detail, args):
    customer_name = lead_detail.get("company_name") or rid("移动客户-")
    contact_name = rid("移动联系人-")
    address = lead_detail.get("address") or {}
    file_id, image_id = upload_pair_files(args)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:3]
    relation_207 = fetch_apaas_values(207)
    relation_335 = fetch_apaas_values(335)
    labels = [{"label_group_id": 1600001, "label_id": 1700002}]
    data = {
        "customer": {
            "custom_field_template_id": args.customer_template_id,
            "name": customer_name,
            "company_name": lead_detail.get("company_name") or customer_name,
            "labels": labels,
            "customer_labels_attributes": labels,
            "category": 2103226,
            "address_attributes": {
                "tel": address.get("tel") or "021-" + str(random.randint(10000000, 99999999)),
                "phone": address.get("phone") or lead_detail.get("text_asset_33b4ba") or "138" + "".join(random.choices(string.digits, k=8)),
                "email": address.get("email") or lead_detail.get("text_asset_71ce4b") or f"{rid('custmail').lower()}@example.com",
                "fax": address.get("fax") or "021-" + str(random.randint(10000000, 99999999)),
                "url": address.get("url") or lead_detail.get("text_asset_2c5471") or f"https://example.com/customer/{int(time.time())}",
                "wechat": address.get("wechat") or rid("wx"),
                "qq": address.get("qq") or str(random.randint(100000, 999999)),
                "wangwang": address.get("wangwang") or rid("ww"),
                "country_id": (address.get("country") or {}).get("id") or 4,
                "province_id": (address.get("province") or {}).get("id") or 28,
                "city_id": (address.get("city") or {}).get("id") or 307,
                "district_id": (address.get("district") or {}).get("id") or 4030,
                "detail_address": address.get("detail_address") or "上海市浦东新区峨山路91弄",
                "lat": address.get("lat") or 31.21625,
                "lng": address.get("lng") or 121.532983,
                "zip": address.get("zip") or "200120",
            },
            "text_asset_67eef7": lead_detail.get("text_asset_2095bb") or f"{customer_name} 单行文本",
            "text_asset_87f993": lead_detail.get("text_asset_71ce4b") or f"{rid('custmail').lower()}@example.com",
            "text_asset_65a3b9": lead_detail.get("text_asset_33b4ba") or "138" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_03cbf4": lead_detail.get("text_area_asset_1a816d") or f"{customer_name} 多行文本",
            "numeric_asset_287205": lead_detail.get("numeric_asset_3160c3") or money(),
            "numeric_asset_1dda60": lead_detail.get("numeric_asset_493a2f") or round(random.uniform(1, 99), 2),
            "numeric_asset_78438c": lead_detail.get("numeric_asset_63be61") or money(),
            "file_asset_c75568": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_118b2b": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_b63623": (lead_detail.get("datetime_asset_5d3cd9") or date_after(1, True))[:16],
            "datetime_asset_cdd74f": lead_detail.get("datetime_asset_beca71") or date_after(2),
            "text_asset_06ea8a_other": "",
            "text_asset_06ea8a": "sel_9631",
            "text_asset_f5df13": ["mul_5c5c", "mul_8c3d"],
            "text_asset_cc11bf": lead_detail.get("text_asset_2c5471") or f"https://example.com/mobile-customer/{int(time.time())}",
            "text_asset_ed815c": "0b5f6e6c-57f4-439d-99fe-12deed681429/nes_791c/nes_52bb",
            "text_asset_661b52": ["nes_493c", "nes_1425"],
            "text_asset_733a50": ["nes_e82a", "nes_add6"],
            "custom_relation_asset_b3bf08": relation_207[0] if relation_207 else None,
            "custom_relation_asset_bdd62a": relation_335[0] if relation_335 else None,
            "user_field_asset_2b4662": lead_detail.get("user_field_asset_03be5a") or [user["id"]],
            "user_field_asset_50ed26": lead_detail.get("user_field_asset_9a4657") or [user["id"]],
            "user_field_asset_b581ec": lead_detail.get("user_field_asset_3b1490") or [user.get("department_id")],
            "user_field_asset_e53dff": lead_detail.get("user_field_asset_29bf74") or [user.get("department_id")],
            "subform_asset_24a0d1": [],
            "number": "MCUST" + str(int(time.time()))[-6:],
            "beginning_payments_amount": money(),
            "status": 2103223,
            "source": 2103229,
            "industry": 2103241,
            "staff_size": 2103252,
            "note": f"{customer_name} 备注",
            "channel": 2103259,
            "revisit_remind_at": lead_detail.get("revisit_remind_at") or date_after(7, True)[:-3],
            "user_field_asset_2b77c3": [user.get("department_id")],
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": assist_user_ids,
            "approve_status": "approved",
            "contacts_attributes": [
                {
                    "name": contact_name,
                    "department": "移动测试部",
                    "job": "移动测试岗位",
                    "text_area_asset_cc3839": f"{contact_name} 多行文本",
                    "numeric_asset_b2effc": money(),
                    "numeric_asset_d94ed2": 0,
                    "file_asset_4bbabd": {"attachment_ids": []},
                    "file_asset_d5d248": {"attachment_ids": []},
                    "datetime_asset_73c24f": date_after(1, True)[:-3],
                    "text_asset_0b794f_other": "",
                    "text_asset_0b794f": None,
                    "text_asset_83d9a2": [],
                    "user_field_asset_ad58d1": [],
                    "user_field_asset_2d9992": [],
                    "user_field_asset_49a7f2": [],
                    "user_field_asset_0d5452": [],
                    "subform_asset_942585": [],
                    "address_attributes": {
                        "tel": "",
                        "phone": "138" + "".join(random.choices(string.digits, k=8)),
                        "wechat": rid("wx"),
                        "qq": str(random.randint(100000, 999999)),
                        "wangwang": rid("ww"),
                        "zip": "200120",
                    },
                    "gender_other": "",
                    "gender": None,
                    "note": f"{contact_name} 备注",
                    "approve_status": "approved",
                }
            ],
        },
        "refer_lead_id": lead_id,
    }
    return request_json("POST", "customers", data=data), customer_name, contact_name


def extract_id(resp):
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("id")
    return None


def extract_contact_id(customer_resp):
    data = customer_resp.get("data")
    if not isinstance(data, dict):
        return None
    for key in ("contacts", "contact", "contacts_attributes"):
        value = data.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0].get("id") or value[0].get("contact_id")
        if isinstance(value, dict):
            return value.get("id") or value.get("contact_id")
    return data.get("contact_id")


def ensure_customer_labels(customer_id):
    payload = {
        "customer": {
            "customer_labels_attributes": [{"label_group_id": 1600001, "label_id": 1700002}],
        }
    }
    data = request_json("PUT", f"customers/{customer_id}", data=payload)
    if data.get("code") != 0:
        raise RuntimeError(f"补充客户标签失败: {data}")
    return data


def create_opportunity(user, customer_id, contact_id, products, args):
    assets = product_assets(products)
    total = round(sum(item["total_price"] for item in assets), 2)
    title = rid("移动商机-")
    file_id, image_id = upload_pair_files(args)
    attachment_id = upload_to_oss(API, TOKEN, None)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:3]
    relation_335 = fetch_apaas_values(335)
    contact_assetships = []
    if contact_id:
        contact_assetships.append({"category": "2103263", "contact_id": contact_id, "_destroy": -1})
    data = {
        "opportunity": {
            "custom_field_template_id": args.opportunity_template_id,
            "title": title,
            "customer_id": customer_id,
            "contact_assetships_attributes": contact_assetships,
            "product_assets_attributes": assets,
            "expect_amount": total,
            "expect_sign_date": date_after(60),
            "get_time": date_after(0),
            "note": f"{title} 备注",
            "text_asset_c1553e": str(total),
            "stage": 2103276,
            "source": 2103268,
            "kind": 2103282,
            "revisit_remind_at": date_after(7, True)[:-3],
            "text_asset_638666": f"{title} 单行文本",
            "text_asset_dfe927": f"{rid('oppmail').lower()}@example.com",
            "text_asset_185333": "138" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_c680ab": f"{title} 多行文本",
            "numeric_asset_97a85f": money(),
            "numeric_asset_0d8fba": round(random.uniform(1, 99), 2),
            "numeric_asset_ef9e0a": total,
            "file_asset_f6074e": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_4b177c": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_eb8db4": date_after(1, True)[:-3],
            "datetime_asset_4be661": date_after(2),
            "text_asset_b7afff_other": "",
            "text_asset_b7afff": "sel_fc2c",
            "text_asset_01ed5d": ["mul_590c", "mul_b233"],
            "text_asset_3159dd": f"https://example.com/mobile-opportunity/{int(time.time())}",
            "text_asset_8bec7c": "82f65bb3-0394-44c3-aece-b85dec72de96",
            "user_field_asset_f9d65e": [user["id"]],
            "user_field_asset_89027b": [user["id"]] + assist_user_ids[:2],
            "user_field_asset_8ef24e": [user.get("department_id")],
            "user_field_asset_258b11": [user.get("department_id")],
            "numeric_asset_2c2735": round(random.random(), 2),
            "custom_relation_asset_207f6d": relation_335[0] if relation_335 else None,
            "subform_asset_40e883": [],
            "attachment_ids": [attachment_id] if attachment_id else [],
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": assist_user_ids,
            "approve_status": "approved",
        },
        "attachment_ids": [attachment_id] if attachment_id else [],
    }
    return request_json("POST", "opportunities", data=data), title, total, assets


def create_quotation(user, customer_id, contact_id, opportunity_id, total, product_assets_for_quote, args):
    name = rid("移动报价单-")
    file_id, image_id = upload_pair_files(args)
    attachment_id = upload_to_oss(API, TOKEN, None)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:3]
    relation_335 = fetch_apaas_values(335)
    data = {
        "quotation": {
            "custom_field_template_id": args.quotation_template_id,
            "name": name,
            "customer_id": customer_id,
            "contact_id": contact_id,
            "opportunity_id": opportunity_id,
            "product_assets_attributes": product_assets_for_quote,
            "product_total_amount": total,
            "additional_discount_amount": 0,
            "whole_discount": 1,
            "total_amount": total,
            "subsidiary_id": args.quotation_subsidiary_id,
            "address_attributes": {
                "contact_phone": "138" + "".join(random.choices(string.digits, k=8)),
                "contact_email": f"{rid('quotecontact').lower()}@example.com",
            },
            "quotation_no": "MQTE" + str(int(time.time()))[-6:],
            "quotation_date": date_after(0),
            "effective_date_fr": date_after(0),
            "effective_date_to": date_after(30),
            "title": f"{name} 主标题",
            "sub_title": f"{name} 副标题",
            "note": f"{name} 备注",
            "revisit_remind_at": date_after(7, True)[:-3],
            "text_asset_9480b6": f"{name} 单行文本",
            "text_asset_21d24d": f"{rid('quotemail').lower()}@example.com",
            "text_asset_7a8f30": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_036dae": f"{name} 多行文本",
            "numeric_asset_434967": money(),
            "numeric_asset_835cc9": round(random.uniform(1, 99), 2),
            "numeric_asset_7b99c5": total,
            "file_asset_00f1da": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_e9bf24": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_24475b": date_after(1, True)[:-3],
            "datetime_asset_440ea8": date_after(2),
            "text_asset_806b76_other": "",
            "text_asset_806b76": "sel_2dd0",
            "text_asset_2fc9ef": ["mul_888a", "mul_da8e"],
            "text_asset_8f7b83": "MQAUTO" + str(int(time.time()))[-6:],
            "text_asset_f977de": f"https://example.com/mobile-quotation/{int(time.time())}",
            "text_asset_66a6b3": "611d99fd-5ba1-4c63-84fe-5c8607410d0a",
            "user_field_asset_66ce2e": [user["id"]],
            "user_field_asset_cb7ec0": [user["id"]] + assist_user_ids[:2],
            "user_field_asset_f812dc": [user.get("department_id")],
            "user_field_asset_94a823": [user.get("department_id")],
            "custom_relation_asset_9b5c46": relation_335[0] if relation_335 else None,
            "subform_asset_7b9c48": [],
            "status": 2103411,
            "attachment_ids": [attachment_id] if attachment_id else [],
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": assist_user_ids,
            "approve_status": "approved",
        },
        "attachment_ids": [attachment_id] if attachment_id else [],
    }
    return request_json("POST", "quotations", data=data), name


def create_contract(user, customer_id, opportunity_id, quotation_id, contact_id, total, product_assets_for_contract, args):
    title = rid("移动合同-")
    contact_assetships = []
    if contact_id:
        contact_assetships.append({"category": "2103263", "contact_id": contact_id, "_destroy": -1})
    file_id, image_id = upload_pair_files(args)
    attachment_id = upload_to_oss(API, TOKEN, None)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:3]
    relation_207 = fetch_apaas_values(207)
    relation_281 = fetch_apaas_values(281)
    relation_335 = fetch_apaas_values(335)
    data = {
        "contract": {
            "custom_field_template_id": args.contract_template_id,
            "title": title,
            "sn": "MCON" + str(int(time.time()))[-6:],
            "customer_id": customer_id,
            "opportunity_id": str(opportunity_id),
            "quotation_ids": [quotation_id] if quotation_id else [],
            "product_assets_attributes": product_assets_for_contract,
            "total_amount": total,
            "sign_date": date_after(0),
            "start_at": date_after(60),
            "end_at": date_after(120),
            "customer_signer": random.choice(["张三", "李四", "王五", "赵六"]),
            "our_signer": random.choice(["徐弘", "薛飞", "王乐", "龚婷"]),
            "contact_assetships_attributes": contact_assetships,
            "text_asset_8ff807": f"{title} 单行文本",
            "text_asset_2662d1": f"{rid('contractmail').lower()}@example.com",
            "text_asset_108683": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_b7e45d": f"{title} 多行文本",
            "numeric_asset_b5b100": money(),
            "numeric_asset_c85903": round(random.uniform(1, 99), 2),
            "numeric_asset_370774": total,
            "file_asset_6db5ff": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_ff1161": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_3004f8": date_after(1, True)[:-3],
            "datetime_asset_76ffee": date_after(120),
            "text_asset_8f0210_other": "",
            "text_asset_8f0210": "sel_bdb5",
            "text_asset_0b1b20": ["mul_041b", "mul_5c0f"],
            "text_asset_845f63": f"https://example.com/mobile-contract/{int(time.time())}",
            "text_asset_819d20": "688b6b7f-5dae-4deb-b6ac-3fa0d2605e32",
            "user_field_asset_936f43": [user["id"]],
            "user_field_asset_a7166d": [user["id"]] + assist_user_ids[:2],
            "user_field_asset_c6708f": [user.get("department_id")],
            "user_field_asset_7ec6cb": [user.get("department_id")],
            "custom_relation_asset_b7960e": relation_281[0] if relation_281 else None,
            "custom_relation_asset_a8b04b": relation_335[0] if relation_335 else None,
            "custom_relation_asset_a1469c": relation_207[0] if relation_207 else None,
            "subform_asset_33dcf3": [],
            "status": 2103294,
            "category": 2103285,
            "payment_type": 2103292,
            "attachment_ids": [attachment_id] if attachment_id else [],
            "received_payment_plans_attributes": [],
            "revisit_remind_at": date_after(7, True)[:-3],
            "special_terms": f"{title} 特殊条款",
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": assist_user_ids,
            "approve_status": "approved",
        },
        "attachment_ids": [attachment_id] if attachment_id else [],
    }
    return request_json("POST", "contracts", data=data), title


def create_received_payment_plans(contract_id, total):
    first_amount = round(total * 0.5, 2)
    second_amount = round(total - first_amount, 2)
    plans = {
        "0": {
            "key": "".join(random.choices(string.ascii_letters + string.digits, k=8)),
            "amount": first_amount,
            "amountString": "0.00",
            "period_name": "第1期",
            "title": "第1期回款计划",
            "receive_date": date_after(30),
            "receive_stage": 1,
            "is_deletable": True,
        },
        "1": {
            "key": "".join(random.choices(string.ascii_letters + string.digits, k=8)),
            "amount": second_amount,
            "amountString": "0.00",
            "period_name": "第2期",
            "title": "第2期回款计划",
            "receive_date": date_after(60),
            "receive_stage": 2,
            "is_deletable": True,
        },
    }
    return request_json(
        "POST",
        f"contracts/{contract_id}/received_payment_plans/batch_create",
        data={"received_payment_plans": plans},
    )


def create_received_payment(user, customer_id, contract_id, plan_id, amount, args):
    title = rid("移动回款-")
    file_id, image_id = upload_pair_files(args)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:2]
    relation_281 = fetch_apaas_values(281)
    relation_277 = fetch_apaas_values(277)
    relation_335 = fetch_apaas_values(335)
    data = {
        "received_payment": {
            "sn": "MRP" + str(int(time.time()))[-6:],
            "receive_date": date_after(30),
            "amount": amount,
            "customer_id": customer_id,
            "contract": contract_id,
            "received_payment_plan_id": plan_id,
            "text_asset_18ede5": f"{title} 单行文本",
            "text_asset_b9d07d": f"{rid('rpmail').lower()}@example.com",
            "text_asset_ff7380": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_f043ba": f"{title} 多行文本",
            "numeric_asset_92e02a": money(),
            "numeric_asset_e7d80e": round(random.uniform(1, 99), 2),
            "numeric_asset_dab234": amount,
            "file_asset_a44026": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_3ec938": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_358dba": date_after(1, True)[:-3],
            "datetime_asset_a73685": date_after(2),
            "text_asset_3a9b20_other": "",
            "text_asset_3a9b20": "sel_1660",
            "text_asset_bcedce": ["mul_40be", "mul_c040"],
            "text_asset_b5dbe4": "MRPAUTO" + str(int(time.time()))[-6:],
            "text_asset_559863": f"https://example.com/mobile-received-payment/{int(time.time())}",
            "text_asset_cab720": "6a319792-568f-4860-a2fd-90c9b66412f1",
            "user_field_asset_d5bfdd": [user["id"]],
            "user_field_asset_945129": [user["id"]] + assist_user_ids,
            "user_field_asset_67e581": [user.get("department_id")],
            "user_field_asset_5124bc": [user.get("department_id")],
            "custom_relation_asset_14df6e": relation_281[0] if relation_281 else None,
            "custom_relation_asset_1498b3": relation_277[0] if relation_277 else None,
            "custom_relation_asset_44eee1": relation_335[0] if relation_335 else None,
            "subform_asset_17cb9c": [],
            "payment_type": 2103292,
            "received_types": 2103298,
            "receive_user_id": user["id"],
            "note": f"{title} 备注",
            "user_id": user["id"],
            "approve_status": "approved",
        }
    }
    return request_json("POST", f"contracts/{contract_id}/received_payments", data=data), title


def create_invoiced_payment(user, customer_id, contract_id, amount, args):
    title = rid("移动开票-")
    file_id, image_id = upload_pair_files(args)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:2]
    relation_335 = fetch_apaas_values(335)
    data = {
        "invoiced_payment": {
            "sn": "MIP" + str(int(time.time()))[-6:],
            "invoiced_date": date_after(0),
            "amount": amount,
            "customer_id": customer_id,
            "contract": contract_id,
            "broker_user_id": user["id"],
            "text_asset_661b25": f"{title} 单行文本",
            "text_asset_42faa2": f"{rid('ipmail').lower()}@example.com",
            "text_asset_a20ef5": "138" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_838b06": f"{title} 多行文本",
            "numeric_asset_4e75e7": money(),
            "numeric_asset_238713": round(random.uniform(1, 99), 2),
            "numeric_asset_4c9c3a": amount,
            "file_asset_6cd8cb": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_e9ac92": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_118223": date_after(1, True)[:-3],
            "datetime_asset_0d5d1f": date_after(2),
            "text_asset_719999_other": "",
            "text_asset_719999": "sel_eeea",
            "text_asset_7e3e8f": ["mul_a6ce", "mul_4a93"],
            "text_asset_1adca6": "MIPAUTO" + str(int(time.time()))[-6:],
            "text_asset_598bc4": f"https://example.com/mobile-invoiced-payment/{int(time.time())}",
            "text_asset_d6f39f": "f7e525f3-9e5a-4fa0-9438-22a95f7124d0",
            "user_field_asset_9f0f0a": [user["id"]],
            "user_field_asset_da88de": [user["id"]] + assist_user_ids,
            "user_field_asset_19a457": [user.get("department_id")],
            "user_field_asset_89c6dd": [user.get("department_id")],
            "custom_relation_asset_2fcfad": relation_335[0] if relation_335 else None,
            "subform_asset_7b3eb9": [],
            "content": f"{title} 票据内容",
            "invoice_types": 2103303,
            "invoice_no": "MINV" + str(int(time.time()))[-6:],
            "note": f"{title} 备注",
            "user_id": user["id"],
            "approve_status": "approved",
        }
    }
    return request_json("POST", f"contracts/{contract_id}/invoiced_payments", data=data), title


def create_checkin_plan(user, customer_id):
    name = rid("移动拜访计划-")
    relation_335 = fetch_apaas_values(335)
    start_at = date_after(0, True)[:-3]
    end_at = date_after(3, True)[:-3]
    data = {
        "checkin_plan": {
            "name": name,
            "category": 2296140,
            "start_at": start_at,
            "end_at": end_at,
            "duration": 2880,
            "checkin_plan_visits_attributes": [
                {"checkable_type": "Customer", "checkable_id": customer_id},
            ],
            "content": f"{name} 内容",
            "status_other": "",
            "status": None,
            "text_asset_65d658_other": "",
            "text_asset_65d658": "sel_8500",
            "numeric_asset_5c4f92": money(),
            "subform_asset_a4f8ff": [],
            "custom_relation_asset_f8f5b3": relation_335[0] if relation_335 else None,
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "assist_user_ids": [],
            "approve_status": "approved",
        }
    }
    return request_json("POST", "checkin_plans", data=data), name


def create_checkin_signout(user, checkin_plan_id, customer_id, contact_id, contract_id, opportunity_id, args):
    plan_detail = request_json("GET", f"checkin_plans/{checkin_plan_id}")
    plan = plan_detail.get("data") or {}
    visits = plan.get("checkin_plan_visits") or []
    checkable_ids = [
        item.get("checkable_id")
        for item in visits
        if isinstance(item, dict) and item.get("checkable_type") == "Customer" and item.get("checkable_id")
    ]
    if not checkable_ids:
        checkable_ids = [customer_id]
    _, image_id = upload_pair_files(args)
    address = {
        "lat": 31.216975,
        "lng": 121.532538,
        "offDistance": None,
        "detail_address": "上海市浦东新区塘桥街道浦东软件园陆家嘴分园2号楼陆家嘴软件园",
    }
    checkin_resp = checkin_request_json(
        "POST",
        "checkin",
        data={
            "address_self": address,
            "address_checkable": {"detail_address": "", "lat": None, "lng": None},
            "update_entity_address": False,
            "checkin_plan_id": checkin_plan_id,
            "checkinPlanTarget": {
                "id": checkin_plan_id,
                "name": plan.get("name"),
                "visit": {
                    "checkable_type": "Customer",
                    "custom_app_id": None,
                    "custom_form_id": None,
                    "custom_form_type": None,
                    "checkable_ids": checkable_ids,
                },
                "value": checkin_plan_id,
            },
            "checkable_id": customer_id,
            "checkable_type": "Customer",
            "isApaas": False,
            "uuid": str(uuid.uuid4()),
        },
    )
    if checkin_resp.get("code") != 0:
        return checkin_resp, {}, None
    visit_id = first_id(checkin_resp.get("data"))
    if not visit_id and isinstance(checkin_resp.get("data"), dict):
        visit_id = checkin_resp["data"].get("checkin_id")
    if not visit_id:
        checkin_list = checkin_request_json(
            "GET",
            "checkin",
            params={"page": 1, "per_page": 50, "checkable_id": customer_id, "checkable_type": "Customer"},
        )
        for item in ((checkin_list.get("data") or {}).get("list") or []):
            if item.get("checkin_plan_id") == checkin_plan_id and item.get("checkable_id") == customer_id:
                visit_id = item.get("id")
                break
    data = {
        "address_self": address,
        "id": visit_id,
        "checkable_id": customer_id,
        "checkable_type": "Customer",
        "text_asset_b3411c": [""],
        "text_asset_b3411c_display": "",
        "numeric_asset_770620": "",
        "message": f"移动拜访签到-{str(int(time.time() * 1000))[-8:]}",
        "attachments": {"attachment_ids": [image_id] if image_id else []},
        "contacts_ids": [contact_id] if contact_id else [],
        "affiliatedOthers_label": "",
        "contract_id": contract_id,
        "opportunity_id": opportunity_id,
        "text_asset_3e9dcd": "",
        "text_asset_cbab62": "",
        "text_area_asset_a12116": "",
        "numeric_asset_8251fa": "",
        "numeric_asset_3de8c6": "",
        "text_asset_6c61fe": "",
        "error_reason": [3],
    }
    if image_id:
        data["attachmentsurls"] = []
    if not visit_id:
        return {"code": -1, "message": f"签到成功但无法获取签到ID: {checkin_resp}"}, {}, None
    signin_check = checkin_request_json("GET", f"checkin/{visit_id}", params={"id": visit_id, "type": "signin"})
    if not checkin_signout_enabled():
        return {"code": 0, "message": "签到成功，系统未开启签退"}, {"signin": signin_check}, visit_id
    resp = checkin_request_json("POST", "signout", data=data)
    signout_check = checkin_request_json("GET", f"checkin/{visit_id}", params={"id": visit_id, "type": "signout"})
    return resp, {"signin": signin_check, "signout": signout_check}, visit_id


def create_revisit_log(user, contact_id, contract_id, args):
    title = rid("移动合同跟进-")
    file_id, image_id = upload_pair_files(args)
    attachment_id = image_id or file_id
    user_ids = get_simple_users(5)
    at_user_ids = [str(uid) for uid in user_ids if uid != user["id"]][:2]
    data = {
        "audio_ids": [],
        "revisit_log": {
            "category": 2103331,
            "category_display": "电话",
            "category_mapped": "电话",
            "loggable_id": str(contract_id),
            "loggable_type": "Contract",
            "real_revisit_at": date_after(0, True)[:-3],
            "revisit_remind_at": date_after(7, True)[:-3],
            "remind_at": date_after(7, True)[:-3],
            "contentLabel": "跟进内容",
            "content": f"{title} 内容",
            "affiliatedOthers_label": "",
            "contacts": [],
            "text_asset_45f3d7": f"{title} 单行文本",
            "text_asset_08e9dd": f"{rid('revisitmail').lower()}@example.com",
            "text_asset_75d0ef": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_70564f": f"{title} 多行文本",
            "numeric_asset_f0f157": money(),
            "numeric_asset_01311b": round(random.uniform(1, 99), 2),
            "numeric_asset_10aa51": money(),
            "file_asset_a336f1": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_04e181": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_68a6be": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_7fbfea": date_after(1, True)[:-3],
            "datetime_asset_e2fa42": date_after(2),
            "text_asset_ef8f07": "sel_fea7",
            "text_asset_ef8f07_display": "单选1",
            "text_asset_ef_8_f_07": "sel_fea7",
            "text_asset_ef_8_f_07_display": "单选1",
            "text_asset_b0f7cc": ["mul_ea3a", "mul_c71d"],
            "text_asset_0bf12e": f"https://example.com/mobile-revisit-log/{int(time.time())}",
            "text_asset_9024f3": "2ccac6ea-3ebd-4619-a189-e8a4d25d1800",
            "user_field_asset_9e8f43": [user["id"]],
            "user_field_asset_1689ff": [user["id"]] + [int(uid) for uid in at_user_ids],
            "user_field_asset_ed3e6e": [user.get("department_id")],
            "user_field_asset_9c7b37": [user.get("department_id")],
            "selectImg": {"urls": [], "attachmentIds": [attachment_id] if attachment_id else []},
            "address_attributes": {"detail_address": "上海市浦东新区峨山路91弄与规划三路交叉口西南40米"},
            "address": {"full_address": "上海市浦东新区峨山路91弄与规划三路交叉口西南40米"},
            "sub_id": "",
            "loggable_name": "",
            "custom_app_id": "",
        },
        "at_user_ids": at_user_ids,
        "contacts_ids": [contact_id] if contact_id else [],
        "attachment_ids": [attachment_id] if attachment_id else [],
        "source": "crm",
    }
    return request_json("POST", "revisit_logs", data=data), title


def create_expense(user, customer_id, contact_id, contract_id, revisit_log_id, checkin_id, amount, args):
    title = rid("移动费用-")
    file_id, image_id = upload_pair_files(args)
    attachment_id = upload_to_oss(API, TOKEN, None)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:2]
    relation_281 = fetch_apaas_values(281)
    relation_335 = fetch_apaas_values(335)
    data = {
        "expense": {
            "sn": "MEX" + str(int(time.time()))[-6:],
            "category": 2103338,
            "description": f"{title} 描述",
            "amount": amount,
            "incurred_at": date_after(0),
            "customer_id": customer_id,
            "contact_ids": [contact_id] if contact_id else [],
            "related_item_type": "Contract",
            "related_item_id": contract_id,
            "revisit_log_id": revisit_log_id,
            "checkin_id": checkin_id,
            "text_asset_68377c": f"{title} 单行文本",
            "text_asset_679989": f"{rid('expensemail').lower()}@example.com",
            "text_asset_9f6032": "138" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_347fc2": f"{title} 多行文本",
            "numeric_asset_2b06a9": money(),
            "numeric_asset_c5f617": round(random.uniform(1, 99), 2),
            "numeric_asset_0f936a": amount,
            "file_asset_bab316": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_b90096": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_afab92": date_after(1, True)[:-3],
            "datetime_asset_6ae0dd": date_after(2),
            "text_asset_d79474_other": "",
            "text_asset_d79474": "sel_afb7",
            "text_asset_0179ae": ["mul_0fcf", "mul_fa31"],
            "text_asset_b326e6": "MEXAUTO" + str(int(time.time()))[-6:],
            "text_asset_b5a741": f"https://example.com/mobile-expense/{int(time.time())}",
            "text_asset_9dd72b": "7c3fb65a-4624-4048-87e8-cc035dfe829a",
            "text_asset_4fb25a_other": "",
            "text_asset_4fb25a": "sel_98ca",
            "user_field_asset_7d249c": [user["id"]],
            "user_field_asset_fb25ca": [user["id"]] + assist_user_ids,
            "user_field_asset_c00e46": [user.get("department_id")],
            "user_field_asset_baaf85": [user.get("department_id")],
            "custom_relation_asset_d24ca4": relation_281[0] if relation_281 else None,
            "custom_relation_asset_70aa17": relation_335[0] if relation_335 else None,
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "approve_status": "approved",
        },
        "attachment_ids": [attachment_id] if attachment_id else [],
    }
    return request_json("POST", "expenses", data=data), title


def create_expense_account(user, expense_id, amount, args):
    title = rid("移动报销单-")
    file_id, image_id = upload_pair_files(args)
    user_ids = get_simple_users(5)
    assist_user_ids = [uid for uid in user_ids if uid != user["id"]][:2]
    relation_281 = fetch_apaas_values(281)
    relation_335 = fetch_apaas_values(335)
    data = {
        "expense_account": {
            "sn": "MEA" + str(int(time.time()))[-6:],
            "expense_ids": [expense_id],
            "amount": amount,
            "user_id": user["id"],
            "owned_department_id": user.get("department_id"),
            "note": f"{title} 备注",
            "text_asset_86b76b": f"{title} 单行文本",
            "text_asset_44a58a": f"{rid('eamail').lower()}@example.com",
            "text_asset_75e1c4": "139" + "".join(random.choices(string.digits, k=8)),
            "text_area_asset_bd00b8": f"{title} 多行文本",
            "numeric_asset_918e18": money(),
            "numeric_asset_14bf17": round(random.uniform(1, 99), 2),
            "numeric_asset_6f517e": amount,
            "file_asset_9474fd": {"attachment_ids": [file_id] if file_id else []},
            "file_asset_5d78b7": {"attachment_ids": [image_id] if image_id else []},
            "datetime_asset_cce928": date_after(1, True)[:-3],
            "datetime_asset_0d2be0": date_after(2),
            "text_asset_5883f3_other": "",
            "text_asset_5883f3": "sel_e647",
            "text_asset_d8e811": ["mul_777e", "mul_6a35"],
            "text_asset_fb8592": "MEAAUTO" + str(int(time.time()))[-6:],
            "text_asset_72a986": f"https://example.com/mobile-expense-account/{int(time.time())}",
            "text_asset_7aa140": "14188da2-c0ee-4710-a60e-6d1d9064dc47",
            "user_field_asset_41bc81": [user["id"]],
            "user_field_asset_86354d": [user["id"]] + assist_user_ids,
            "user_field_asset_9bce1b": [user.get("department_id")],
            "user_field_asset_6104aa": [user.get("department_id")],
            "custom_relation_asset_293d2b": relation_281[0] if relation_281 else None,
            "custom_relation_asset_ca0778": relation_335[0] if relation_335 else None,
            "approve_status": "approved",
        },
        "expense_ids": [expense_id],
    }
    return request_json("POST", "expense_accounts", data=data), title


def create_schedule_report(user, args):
    title = rid("移动工作报告-")
    user_ids = [uid for uid in get_pc_user_ids(50) if uid != user["id"]]
    if not user_ids:
        user_ids = [uid for uid in get_simple_users(10) if uid != user["id"]]
    reviewer_id = random.choice(user_ids or [user["id"]])
    cc_candidates = [uid for uid in user_ids if uid != reviewer_id]
    cc_ids = random.sample(cc_candidates, min(args.schedule_report_cc_count, len(cc_candidates)))
    data = {
        "cycle": args.schedule_report_cycle,
        "image_ids": [],
        "summary_audio_ids": [],
        "schedule_audio_ids": [],
        "text_area_asset_121d37_audio_ids": [],
        "schedule_report": {
            "due_at": date_after(0),
            "marking_user_id": reviewer_id,
            "report_cc_users_attributes": {str(index): {"user_id": uid} for index, uid in enumerate(cc_ids)},
            "summary": f"{title} 今日总结",
            "schedule": f"{title} 明日计划",
            "text_area_asset_121d37": f"{title} 自定义多行文本",
        },
    }
    return request_json("POST", "schedule_reports", data=data), title


def require_id(step, resp):
    entity_id = extract_id(resp)
    if not entity_id:
        raise RuntimeError(f"{step}失败: {resp}")
    return entity_id


def first_id(value):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("id"):
                return item.get("id")
    if isinstance(value, dict):
        if value.get("id"):
            return value.get("id")
        for item in value.values():
            if isinstance(item, dict) and item.get("id"):
                return item.get("id")
    return None


def first_received_payment_plan_id(contract_id):
    data = request_json("GET", f"contracts/{contract_id}")
    contract = data.get("data") or {}
    return first_id(contract.get("received_payment_plans"))


def run_once(index, args):
    print(f"\n{'#' * 60}\n# 移动端全流程 第 {index}/{args.cnt} 轮\n{'#' * 60}")
    user = get_current_user()
    products = create_products(user, args)

    market_resp, market_name = create_market_activity(user, args)
    market_id = require_id("新增市场活动", market_resp)
    print(f"  ✅ 2/17 市场活动: {market_id} {market_name}")

    lead_resp, lead_name = create_lead(user, market_id, args)
    lead_id = require_id("新增线索", lead_resp)
    print(f"  ✅ 3/17 线索: {lead_id} {lead_name}")
    lead_detail = get_lead_detail(lead_id)

    init_resp = init_turn_to_customer(lead_id, args)
    if init_resp.get("code") != 0:
        raise RuntimeError(f"线索转客户初始化失败: {init_resp}")
    print("  ✅ 4/17 线索转客户初始化")

    customer_resp, customer_name, contact_name = create_customer_from_lead(user, lead_id, lead_detail, args)
    customer_id = require_id("线索转客户", customer_resp)
    ensure_customer_labels(customer_id)
    contact_id = extract_contact_id(customer_resp)
    print(f"  ✅ 5/17 客户: {customer_id} {customer_name} 联系人:{contact_id or contact_name}")

    opportunity_resp, opportunity_title, total, opportunity_product_assets = create_opportunity(
        user, customer_id, contact_id, products, args
    )
    opportunity_id = require_id("新增商机", opportunity_resp)
    print(f"  ✅ 6/17 商机: {opportunity_id} {opportunity_title} 金额:{total}")

    quotation_resp, quotation_name = create_quotation(
        user, customer_id, contact_id, opportunity_id, total, opportunity_product_assets, args
    )
    quotation_id = require_id("新增报价单", quotation_resp)
    print(f"  ✅ 7/17 报价单: {quotation_id} {quotation_name}")

    contract_resp, contract_title = create_contract(
        user, customer_id, opportunity_id, quotation_id, contact_id, total, opportunity_product_assets, args
    )
    contract_id = require_id("新增合同", contract_resp)
    print(f"  ✅ 8/17 合同: {contract_id} {contract_title}")

    plan_resp = create_received_payment_plans(contract_id, total)
    if plan_resp.get("code") != 0:
        raise RuntimeError(f"新增回款计划失败: {plan_resp}")
    plan_id = first_id(plan_resp.get("data")) or first_received_payment_plan_id(contract_id)
    print(f"  ✅ 9/17 回款计划: {plan_id or '-'}")

    received_payment_resp, received_payment_title = create_received_payment(
        user, customer_id, contract_id, plan_id, round(total * 0.5, 2), args
    )
    received_payment_id = require_id("新增回款记录", received_payment_resp)
    print(f"  ✅ 10/17 回款记录: {received_payment_id} {received_payment_title}")

    invoiced_payment_resp, invoiced_payment_title = create_invoiced_payment(
        user, customer_id, contract_id, round(total * 0.5, 2), args
    )
    invoiced_payment_id = require_id("新增开票记录", invoiced_payment_resp)
    print(f"  ✅ 11/17 开票记录: {invoiced_payment_id} {invoiced_payment_title}")

    checkin_plan_resp, checkin_plan_name = create_checkin_plan(user, customer_id)
    checkin_plan_id = require_id("新增拜访计划", checkin_plan_resp)
    print(f"  ✅ 12/17 拜访计划: {checkin_plan_id} {checkin_plan_name}")

    signout_resp, signout_check, checkin_visit_id = create_checkin_signout(
        user, checkin_plan_id, customer_id, contact_id, contract_id, opportunity_id, args
    )
    if signout_resp.get("code") != 0:
        raise RuntimeError(f"拜访签到失败: {signout_resp}")
    if checkin_visit_id:
        print(f"  ✅ 13/17 拜访签到: {checkin_visit_id}")
    else:
        print("  ○ 13/17 拜访签到: 未找到可签退记录，需补充签到创建接口")

    revisit_log_resp, revisit_log_title = create_revisit_log(user, contact_id, contract_id, args)
    revisit_log_id = require_id("新增合同跟进记录", revisit_log_resp)
    print(f"  ✅ 14/17 合同跟进记录: {revisit_log_id} {revisit_log_title}")

    expense_resp, expense_title = create_expense(
        user, customer_id, contact_id, contract_id, revisit_log_id, checkin_visit_id, round(total * 0.1, 2), args
    )
    expense_id = require_id("新增费用", expense_resp)
    print(f"  ✅ 15/17 费用: {expense_id} {expense_title}")

    expense_account_resp, expense_account_title = create_expense_account(user, expense_id, round(total * 0.1, 2), args)
    expense_account_id = require_id("新增报销单", expense_account_resp)
    print(f"  ✅ 16/17 报销单: {expense_account_id} {expense_account_title}")

    schedule_report_resp, schedule_report_title = create_schedule_report(user, args)
    schedule_report_id = require_id("新增工作报告", schedule_report_resp)
    print(f"  ✅ 17/17 工作报告: {schedule_report_id} {schedule_report_title}")

    return {
        "products": [item.get("id") for item in products],
        "market_activity": market_id,
        "lead": lead_id,
        "customer": customer_id,
        "contact": contact_id,
        "opportunity": opportunity_id,
        "quotation": quotation_id,
        "contract": contract_id,
        "received_payment_plan": plan_id,
        "received_payment": received_payment_id,
        "invoiced_payment": invoiced_payment_id,
        "checkin_plan": checkin_plan_id,
        "checkin_visit": checkin_visit_id,
        "revisit_log": revisit_log_id,
        "expense": expense_id,
        "expense_account": expense_account_id,
        "schedule_report": schedule_report_id,
    }


def main():
    parser = argparse.ArgumentParser(description="移动端CRM创建全流程")
    parser.add_argument("--api")
    parser.add_argument("--token")
    parser.add_argument("--env", choices=["test", "staging", "production"])
    parser.add_argument("--cnt", type=int, default=1)
    parser.add_argument("--market-template-id", type=int, default=844)
    parser.add_argument("--lead-template-id", type=int, default=805)
    parser.add_argument("--customer-template-id", type=int, default=846)
    parser.add_argument("--opportunity-template-id", type=int, default=812)
    parser.add_argument("--quotation-template-id", type=int, default=797)
    parser.add_argument("--quotation-subsidiary-id", type=int, default=23)
    parser.add_argument("--contract-template-id", type=int, default=795)
    parser.add_argument("--lead-status", type=int, default=2162424)
    parser.add_argument("--product-count", type=int, default=2)
    parser.add_argument("--schedule-report-cycle", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--schedule-report-cc-count", type=int, default=2)
    parser.add_argument("--attachment-dir", help="本地附件目录，用于市场活动图片/文件/附件字段")
    args = apply_config_defaults(parser.parse_args(), parser)

    global API, API_BASE, CHECKIN_API, TOKEN
    API = args.api.rstrip("/")
    API_BASE = api_base(API)
    CHECKIN_API = checkin_api_base(API)
    TOKEN = args.token

    print(f"{'=' * 60}\n移动端CRM创建全流程\nAPI: {API}\n轮数: {args.cnt}\n{'=' * 60}")
    if args.attachment_dir:
        print(f"附件目录: {args.attachment_dir}")
    results = []
    for index in range(1, args.cnt + 1):
        results.append(run_once(index, args))

    print(f"\n{'=' * 60}\n完成: {len(results)}/{args.cnt}\n{'=' * 60}")
    for index, item in enumerate(results, 1):
        print(
            f"第{index}轮 市场活动:{item['market_activity']} 线索:{item['lead']} "
            f"产品:{','.join(str(pid) for pid in item['products'])} "
            f"客户:{item['customer']} 联系人:{item['contact'] or '-'} "
            f"商机:{item['opportunity']} 报价单:{item['quotation']} 合同:{item['contract']} "
            f"回款计划:{item['received_payment_plan'] or '-'} 回款记录:{item['received_payment']} "
            f"开票记录:{item['invoiced_payment']} 拜访计划:{item['checkin_plan']} 拜访签到:{item['checkin_visit']} "
            f"跟进记录:{item['revisit_log']} 费用:{item['expense']} 报销单:{item['expense_account']} "
            f"工作报告:{item['schedule_report']}"
        )


if __name__ == "__main__":
    main()
