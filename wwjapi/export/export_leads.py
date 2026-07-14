#!/usr/bin/env python3
"""线索导出脚本 - 自动发起导出、监听 Faye、下载 xlsx

常用执行方式:
  # 使用 config.json 里的 api/token，导出所有线索页到 outputs/exports/leads
  python3 export/export_leads.py --all-pages

  # 只导出第 1 页
  python3 export/export_leads.py --page 1

  # 只计算导出页，不真正导出
  python3 export/export_leads.py --calculate-only

  # 指定输出目录
  python3 export/export_leads.py --all-pages --output-dir outputs/exports/leads

  # 指定环境和 token
  python3 export/export_leads.py --all-pages \
    --api https://lxcrm-staging.weiwenjia.com \
    --token your_token

  # 带列表筛选条件导出，可重复传 --param
  python3 export/export_leads.py --all-pages \
    --param scope=all_own \
    --param search_key=自动化

说明:
  - 导出接口复用 PC 线索列表: /api/pc/leads。
  - 先用 format_type=calculate_export_pages 获取导出页，再用 format_type=xlsx 发起异步导出。
  - 文件 URL 通过 Faye 通道 /export/file/xlsx/{当前用户ID} 返回。
  - 默认 Faye 地址: https://faye-dev.ikcrm.com/faye，可用 --faye-url 覆盖。
"""
import argparse, os, re, sys, threading, time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import pc_url


DEFAULT_FAYE_URL = "https://faye-dev.ikcrm.com/faye"


def headers(token):
    return {"Authorization": f"Token token={token}", "Content-Type": "application/json"}


def request_json(method, url, token, params=None, timeout=60):
    resp = requests.request(method, url, headers=headers(token), params=params, timeout=timeout)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw_text": resp.text[:500]}
    if resp.status_code >= 400 and isinstance(body, dict):
        body.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return body


def current_user(api, token):
    return request_json("GET", f"{api.rstrip('/')}/api/v2/user/info", token, timeout=15).get("data", {})


def parse_params(items):
    params = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--param 必须是 key=value 格式: {item}")
        key, value = item.split("=", 1)
        params[key] = value
    return params


def calculate_pages(api, token, base_params):
    params = dict(base_params)
    params["format_type"] = "calculate_export_pages"
    data = request_json("GET", f"{pc_url(api)}/api/pc/leads", token, params=params, timeout=60)
    if data.get("code") != 0:
        raise RuntimeError(f"计算导出页失败: {data}")
    return data.get("data") or {}


class FayeListener:
    def __init__(self, faye_url, channel):
        self.faye_url = faye_url
        self.channel = channel
        self.session = requests.Session()
        self.messages = []
        self._stop = False
        self._thread = None
        self.client_id = None

    def start(self):
        hs = self.session.post(
            self.faye_url,
            json=[{"channel": "/meta/handshake", "version": "1.0", "supportedConnectionTypes": ["long-polling"], "id": "1"}],
            timeout=15,
        ).json()[0]
        if not hs.get("successful"):
            raise RuntimeError(f"faye handshake 失败: {hs}")
        self.client_id = hs["clientId"]
        sub = self.session.post(
            self.faye_url,
            json=[{"channel": "/meta/subscribe", "clientId": self.client_id, "subscription": self.channel, "id": "2"}],
            timeout=15,
        ).json()[0]
        if not sub.get("successful"):
            raise RuntimeError(f"faye subscribe 失败: {sub}")

        def loop():
            msg_id = 3
            while not self._stop:
                try:
                    arr = self.session.post(
                        self.faye_url,
                        json=[
                            {
                                "channel": "/meta/connect",
                                "clientId": self.client_id,
                                "connectionType": "long-polling",
                                "id": str(msg_id),
                            }
                        ],
                        timeout=50,
                    ).json()
                    msg_id += 1
                    for msg in arr:
                        if msg.get("channel") == self.channel:
                            self.messages.append(msg)
                except Exception:
                    time.sleep(1)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def wait_success(self, async_client_id, timeout):
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            for index, msg in enumerate(self.messages):
                if index in seen:
                    continue
                seen.add(index)
                data = msg.get("data") or {}
                if data.get("async_client_id") != async_client_id:
                    continue
                status = data.get("status")
                progress = data.get("progress")
                print(f"    faye: status={status} progress={progress}")
                if status == "success" and data.get("qiniu_file_path"):
                    return data
                if status == "failed":
                    raise RuntimeError(f"导出失败: {data}")
            time.sleep(1)
        raise TimeoutError(f"等待导出完成超时: async_client_id={async_client_id}")

    def stop(self):
        self._stop = True


def export_page(api, token, page, base_params):
    params = dict(base_params)
    params.update({"format_type": "xlsx", "export_page": page})
    data = request_json("GET", f"{pc_url(api)}/api/pc/leads", token, params=params, timeout=60)
    if data.get("code") != 0:
        raise RuntimeError(f"发起导出失败: {data}")
    body = data.get("data") or {}
    if not body.get("async_client_id") or not body.get("faye_channel"):
        raise RuntimeError(f"导出接口缺少 async_client_id/faye_channel: {data}")
    return body


def safe_filename(name):
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name.strip() or "leads_export.xlsx"


def filename_from_url(url, fallback):
    path = urlparse(url).path
    name = unquote(os.path.basename(path))
    return safe_filename(name or fallback)


def download_file(url, output_dir, fallback):
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = filename_from_url(url, fallback)
    path = output_dir / filename
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def main():
    parser = argparse.ArgumentParser(description="导出线索 xlsx")
    parser.add_argument("--api")
    parser.add_argument("--token")
    parser.add_argument("--env", choices=["test", "staging", "production"])
    parser.add_argument("--profile", choices=["gray", "standard"])
    parser.add_argument("--page", type=int, help="导出指定页")
    parser.add_argument("--all-pages", action="store_true", help="导出全部页")
    parser.add_argument("--calculate-only", action="store_true", help="只计算导出页")
    parser.add_argument("--output-dir", default="outputs/exports/leads")
    parser.add_argument("--param", action="append", help="列表筛选参数，格式 key=value，可重复传")
    parser.add_argument("--faye-url", default=DEFAULT_FAYE_URL)
    parser.add_argument("--timeout", type=int, default=180)
    args = apply_config_defaults(parser.parse_args(), parser)

    api = args.api.rstrip("/")
    token = args.token
    base_params = parse_params(args.param)
    output_dir = Path(args.output_dir)

    user = current_user(api, token)
    if not user.get("id"):
        raise RuntimeError("无法获取当前用户，检查 api/token")
    inferred_channel = f"/export/file/xlsx/{user['id']}"

    print(f"\n{'=' * 60}\n线索导出\nAPI: {api}\n当前用户: {user.get('name')}({user.get('id')})\n{'=' * 60}")
    pages_info = calculate_pages(api, token, base_params)
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
            body = export_page(api, token, page, base_params)
            print(f"  async_client_id: {body['async_client_id']}")
            data = listener.wait_success(body["async_client_id"], args.timeout)
            file_url = data["qiniu_file_path"]
            path = download_file(file_url, output_dir, f"leads_page_{page}.xlsx")
            downloaded.append(path)
            print(f"  下载完成: {path}")
    finally:
        listener.stop()

    print("\n完成:")
    for path in downloaded:
        print(f"  {path}")


if __name__ == "__main__":
    main()
