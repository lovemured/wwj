#!/usr/bin/env python3
"""批量创建PC/通用版工作报告 - 支持图片/附件/抄送人

使用:
  python3 schedule_report/batch_create_schedule_report_pc.py 1 --cycle daily --verify
  python3 schedule_report/batch_create_schedule_report_pc.py 1 --cycle weekly --verify
  python3 schedule_report/batch_create_schedule_report_pc.py 1 --cycle monthly --verify
"""
import argparse, os, random, string, sys, time
from datetime import date, datetime, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import upload_to_oss


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic")


def request_json(method, url, token, data=None, timeout=60):
    resp = requests.request(
        method,
        url,
        headers={"Content-Type": "application/json", "Authorization": f"Token token={token}"},
        json=data,
        timeout=timeout,
    )
    try:
        body = resp.json()
    except ValueError:
        body = {"raw_text": resp.text[:500]}
    if resp.status_code >= 400 and isinstance(body, dict):
        body.setdefault("message", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return body


def api(api_base, token, path, method="GET", data=None):
    return request_json(method, f"{api_base.rstrip('/')}/api/v2/{path.lstrip('/')}", token, data)


def pc_api(api_base, token, path, method="GET", data=None):
    pc = api_base.replace("//lxcrm-staging.", "//lxcrm-api-staging.").replace("//lxcrm-test.", "//lxcrm-api-test.").replace("//lxcrm.", "//lxcrm-api.")
    return request_json(method, f"{pc.rstrip('/')}/api/pc/{path.lstrip('/')}", token, data)


def random_text(prefix):
    suffix = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{suffix}"


def discover_users(api_base, token):
    current = api(api_base, token, "user/info").get("data", {})
    data = pc_api(api_base, token, "users?page=1&per_page=50").get("data", {})
    users = data.get("users") or data.get("list") or []
    ids = [u["id"] for u in users if u.get("id")]
    return current, ids


def list_local_files(attachment_dir):
    if not attachment_dir:
        return [], []
    files = [
        os.path.join(attachment_dir, name)
        for name in os.listdir(attachment_dir)
        if os.path.isfile(os.path.join(attachment_dir, name)) and not name.startswith(".")
    ]
    images = [path for path in files if path.lower().endswith(IMAGE_EXTS)]
    docs = [path for path in files if not path.lower().endswith(IMAGE_EXTS)]
    return images, docs


def upload_ids(api_base, token, files, count):
    ids = []
    candidates = list(files)
    random.shuffle(candidates)
    for path in candidates:
        aid = upload_to_oss(api_base, token, path)
        if aid:
            ids.append(aid)
        if len(ids) >= count:
            break
    return ids


def choose_reviewer_and_cc(current_user, user_ids, cc_count):
    current_id = current_user.get("id")
    candidates = [uid for uid in user_ids if uid and uid != current_id]
    reviewer = random.choice(candidates or user_ids or [current_id])
    cc_candidates = [uid for uid in candidates if uid != reviewer]
    cc_ids = random.sample(cc_candidates, min(cc_count, len(cc_candidates))) if cc_count > 0 else []
    return reviewer, cc_ids


def build_payload(api_base, token, args, index, current_user, user_ids):
    reviewer_id, cc_ids = choose_reviewer_and_cc(current_user, user_ids, args.cc_count)
    due_at = (date.today() + timedelta(days=index - 1)).isoformat()
    summary = args.summary or random_text("自动化工作总结")
    schedule = args.schedule or random_text("自动化明日计划")

    payload = {
        "cycle": args.cycle,
        "schedule_report": {
            "due_at": due_at,
            "marking_user_id": reviewer_id,
            "summary": f"{summary}-{index}",
            "schedule": f"{schedule}-{index}",
            "report_cc_users_attributes": [{"user_id": uid} for uid in cc_ids],
        },
    }

    if args.custom_text:
        payload["schedule_report"]["text_area_asset_121d37"] = f"{args.custom_text}-{index}"

    images, docs = list_local_files(args.attachment_dir)
    summary_image_ids = upload_ids(api_base, token, images, args.summary_image_count)
    schedule_image_ids = upload_ids(api_base, token, images, args.schedule_image_count)
    report_image_ids = upload_ids(api_base, token, images, args.report_image_count)
    summary_file_ids = upload_ids(api_base, token, docs or images, args.summary_file_count)
    schedule_file_ids = upload_ids(api_base, token, docs or images, args.schedule_file_count)
    report_file_ids = upload_ids(api_base, token, docs or images, args.report_file_count)

    if summary_image_ids:
        payload["summary_attachment_ids"] = summary_image_ids
    if schedule_image_ids:
        payload["schedule_attachment_ids"] = schedule_image_ids
    if report_image_ids:
        payload["image_ids"] = report_image_ids
    if summary_file_ids:
        payload["summary_ids"] = summary_file_ids
    if schedule_file_ids:
        payload["schedule_ids"] = schedule_file_ids
    if report_file_ids:
        payload["file_ids"] = report_file_ids
    return payload


def summarize_detail(detail):
    return {
        "id": detail.get("id"),
        "summary": detail.get("summary"),
        "schedule": detail.get("schedule"),
        "cycle_name": detail.get("cycle_name"),
        "marking_user": (detail.get("marking_user") or {}).get("name"),
        "cc_users": [u.get("name") for u in detail.get("cc_users", [])],
        "summary_content_attachments": len(detail.get("summary_content_attachments") or []),
        "schedule_content_attachments": len(detail.get("schedule_content_attachments") or []),
        "schedule_report_images": len(detail.get("schedule_report_images") or []),
        "summary_attachments": len(detail.get("summary_attachments") or []),
        "schedule_attachments": len(detail.get("schedule_attachments") or []),
        "schedule_report_files": len(detail.get("schedule_report_files") or []),
        "custom_text": detail.get("text_area_asset_121d37"),
    }


def main():
    parser = argparse.ArgumentParser(description="批量创建PC/通用版工作报告")
    parser.add_argument("--api")
    parser.add_argument("--token")
    parser.add_argument("--env", choices=["test", "staging", "production"])
    parser.add_argument("count", nargs="?", type=int, default=1)
    parser.add_argument("--cycle", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--summary")
    parser.add_argument("--schedule")
    parser.add_argument("--custom-text", default="自动化工作报告自定义内容")
    parser.add_argument("--cc-count", type=int, default=2)
    parser.add_argument("--summary-image-count", type=int, default=1)
    parser.add_argument("--schedule-image-count", type=int, default=1)
    parser.add_argument("--report-image-count", type=int, default=1)
    parser.add_argument("--summary-file-count", type=int, default=0)
    parser.add_argument("--schedule-file-count", type=int, default=0)
    parser.add_argument("--report-file-count", type=int, default=0)
    parser.add_argument("--attachment-dir", help="本地附件目录")
    parser.add_argument("--verify", action="store_true", help="创建后回查详情")
    parser.add_argument("--delay", type=float, default=0.3)
    args = apply_config_defaults(parser.parse_args(), parser)
    api_base = args.api.rstrip("/")

    print(f"\n{'=' * 60}\nPC/通用版工作报告\nAPI: {api_base} 数量: {args.count} 周期: {args.cycle}\n{'=' * 60}")
    if args.attachment_dir:
        print(f"附件目录: {args.attachment_dir}")

    current_user, user_ids = discover_users(api_base, args.token)
    print(f"当前用户: {current_user.get('name')}({current_user.get('id')}) 用户数:{len(user_ids)}")

    ok = fail = 0
    for index in range(1, args.count + 1):
        try:
            payload = build_payload(api_base, args.token, args, index, current_user, user_ids)
            res = api(api_base, args.token, "schedule_reports", method="POST", data=payload)
            report_id = res.get("data", {}).get("id")
            if not report_id:
                fail += 1
                print(f"  ✗ [{index}/{args.count}] {res.get('message', res)}")
                continue
            ok += 1
            print(f"  ✓ [{index}/{args.count}] ID:{report_id} 批阅人:{(res.get('data', {}).get('marking_user') or {}).get('name')}")
            if args.verify:
                detail = api(api_base, args.token, f"schedule_reports/{report_id}").get("data", {})
                print("    " + str(summarize_detail(detail)))
        except Exception as exc:
            fail += 1
            print(f"  ✗ [{index}/{args.count}] {exc}")
        if index < args.count and args.delay > 0:
            time.sleep(args.delay)
    print(f"\n完成! 成功:{ok} 失败:{fail}")


if __name__ == "__main__":
    main()
