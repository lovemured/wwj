#!/usr/bin/env python3
"""客户导出脚本 - 自动发起导出、监听 Faye、下载 xlsx

常用执行方式:
  # 使用 config.json 里的 api/token，导出全部客户到 outputs/exports/customers
  python3 export/export_customers.py --all-pages

  # 只导出第 1 页
  python3 export/export_customers.py --page 1

  # 只计算导出页，不真正导出
  python3 export/export_customers.py --calculate-only

  # 只导出指定客户 ID，多个 ID 用英文逗号分隔
  python3 export/export_customers.py --page 1 --selected-ids 5500052,5500051

  # 指定环境和 token
  python3 export/export_customers.py --all-pages \
    --api https://lxcrm-staging.weiwenjia.com \
    --token your_token

  # 带列表筛选条件导出，可重复传 --param
  python3 export/export_customers.py --all-pages \
    --param tab_type=my \
    --param query=自动化

说明:
  - 客户导出真实接口是 POST /api/pc/v1/customers/pc_index。
  - 先用 format_type=calculate_export_pages 获取导出页，再用 format_type=xlsx 发起异步导出。
  - 文件 URL 通过 Faye 通道 /export/file/xlsx/{当前用户ID} 返回。
  - 下载文件名会自动 URL 解码，中文名会按中文落盘。
"""
import argparse
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_leads import (
    DEFAULT_FAYE_URL,
    FayeListener,
    current_user,
    download_file,
    parse_params,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import pc_url


def headers(api, token):
    return {
        "accept": "application/json, text/plain, */*",
        "authorization": f'Token token="{token}",device="web"',
        "content-type": "application/json",
        "origin": api.rstrip("/"),
        "referer": f"{api.rstrip('/')}/",
    }


def parse_ids(value):
    if not value:
        return None
    ids = []
    for item in value.split(","):
        item = item.strip()
        if item:
            ids.append(int(item))
    return ids


def request_export(api, token, payload, timeout=60):
    url = f"{pc_url(api)}/api/pc/v1/customers/pc_index"
    resp = requests.post(url, headers=headers(api, token), json=payload, timeout=timeout)
    try:
        data = resp.json()
    except ValueError:
        data = {"raw_text": resp.text[:500]}
    if resp.status_code >= 400 and isinstance(data, dict):
        data.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return data


def build_payload(base_params, selected_ids, format_type, export_page=None):
    payload = dict(base_params)
    payload.update({"model_klass": "customer", "format_type": format_type})
    payload.setdefault("page", 1)
    payload.setdefault("per_page", 10)
    if selected_ids is not None:
        payload["selected_ids"] = selected_ids
    if export_page is not None:
        payload["export_page"] = export_page
    return payload


def calculate_pages(api, token, base_params, selected_ids):
    payload = build_payload(base_params, selected_ids, "calculate_export_pages")
    data = request_export(api, token, payload)
    if data.get("code") != 0:
        raise RuntimeError(f"计算导出页失败: {data}")
    return data.get("data") or {}


def export_page(api, token, page, base_params, selected_ids):
    payload = build_payload(base_params, selected_ids, "xlsx", page)
    data = request_export(api, token, payload)
    if data.get("code") != 0:
        raise RuntimeError(f"发起导出失败: {data}")
    body = data.get("data") or {}
    if not body.get("async_client_id") or not body.get("faye_channel"):
        raise RuntimeError(f"导出接口缺少 async_client_id/faye_channel: {data}")
    return body


def main():
    parser = argparse.ArgumentParser(description="导出客户 xlsx")
    parser.add_argument("--api")
    parser.add_argument("--token")
    parser.add_argument("--env", choices=["test", "staging", "production"])
    parser.add_argument("--page", type=int, help="导出指定页")
    parser.add_argument("--all-pages", action="store_true", help="导出全部页")
    parser.add_argument("--calculate-only", action="store_true", help="只计算导出页")
    parser.add_argument("--selected-ids", help="指定客户 ID，英文逗号分隔")
    parser.add_argument("--output-dir", default="outputs/exports/customers")
    parser.add_argument("--param", action="append", help="列表筛选参数，格式 key=value，可重复传")
    parser.add_argument("--faye-url", default=DEFAULT_FAYE_URL)
    parser.add_argument("--timeout", type=int, default=180)
    args = apply_config_defaults(parser.parse_args(), parser)

    api = args.api.rstrip("/")
    token = args.token
    base_params = parse_params(args.param)
    selected_ids = parse_ids(args.selected_ids)
    output_dir = Path(args.output_dir)

    user = current_user(api, token)
    if not user.get("id"):
        raise RuntimeError("无法获取当前用户，检查 api/token")
    inferred_channel = f"/export/file/xlsx/{user['id']}"

    print(f"\n{'=' * 60}\n客户导出\nAPI: {api}\n当前用户: {user.get('name')}({user.get('id')})\n{'=' * 60}")
    pages_info = calculate_pages(api, token, base_params, selected_ids)
    export_pages = pages_info.get("export_pages") or []
    print(f"总数:{pages_info.get('total_count')} 每页:{pages_info.get('per_page')} 导出页:{export_pages}")
    if args.calculate_only:
        return

    if args.all_pages:
        pages = [item["export_page"] for item in export_pages if item.get("export_page")]
    elif args.page:
        pages = [args.page]
    else:
        pages = [export_pages[0]["export_page"]] if export_pages else [1]

    listener = FayeListener(args.faye_url, inferred_channel)
    listener.start()
    print(f"已监听 faye: {inferred_channel}")

    downloaded = []
    try:
        for page in pages:
            print(f"\n[导出第 {page} 页]")
            body = export_page(api, token, page, base_params, selected_ids)
            print(f"  async_client_id: {body['async_client_id']}")
            data = listener.wait_success(body["async_client_id"], args.timeout)
            path = download_file(data["qiniu_file_path"], output_dir, f"customers_page_{page}.xlsx")
            downloaded.append(path)
            print(f"  下载完成: {path}")
    finally:
        listener.stop()

    print("\n完成:")
    for path in downloaded:
        print(f"  {path}")


if __name__ == "__main__":
    main()
