#!/usr/bin/env python3
"""删除 CRM 用户的完整闭环：删除校验 -> 全模块交接 -> 再删除。

示例:
  python3 handover/delete_user_flow.py \
      --env test --from-user 5622694 --to-user 5595966 \
      --usertoken "$UC_USER_TOKEN" --cookie-file /path/to/cookie.txt

Cookie 文件内容可以是浏览器导出的 Cookie 请求头值，或包含 ``-b '...'``
的 curl 文本。Cookie 不会写入配置文件或日志。
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from handover_common import api, infer_pc_api  # noqa: E402
from lib.config import apply_config_defaults, load_config  # noqa: E402


DELETE_BLOCKED_CODE = 200051
DONE_STATUSES = {2}


def load_cookie(cookie=None, cookie_file=None):
    """Load a Cookie header value without printing it."""
    value = cookie or os.environ.get('UC_COOKIE', '')
    if cookie_file:
        value = Path(cookie_file).read_text().strip()
    if not value:
        raise ValueError('请通过 --cookie-file、--cookie 或 UC_COOKIE 提供删除接口 Cookie')
    match = re.search(r"-b\s+'([^']+)'", value)
    return match.group(1) if match else value


def delete_user(uc_api, user_id, usertoken, cookie, apptoken, origin):
    """Call UC deletion endpoint and return its JSON response."""
    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/json; charset=utf-8',
        'apptoken': apptoken,
        'crmplatformtype': 'lixiaoyun',
        'Origin': origin,
        'Platform': 'IK',
        'Referer': f'{origin.rstrip("/")}/',
        'usertoken': usertoken,
        'Cookie': cookie,
    }
    try:
        response = requests.post(
            f'{uc_api.rstrip("/")}/api/user/management/deleteUser',
            headers=headers,
            json={'uid': user_id},
            timeout=30,
        )
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        return {'code': -1, 'message': f'删除请求失败: {exc}'}


def create_full_handover(pc_api, token, source_uid, target_uid, assets):
    """Create a handover task for every module returned by the asset API."""
    data = assets.get('data') or {}
    modules = data.get('modules') or []
    form_user = data.get('form_user') or {'uid': source_uid, 'name': ''}
    entity_data = [
        {
            'module_class': module.get('module_class'),
            'module_name': module.get('module_name', ''),
            'to_user_uid': target_uid,
            'to_assist_user_uid': target_uid,
        }
        for module in modules
    ]
    return api(
        pc_api,
        token,
        'grove_tasks',
        {
            'job_type': 'Handover',
            'job_args': {
                'from_user_uid': str(source_uid),
                'from_user': form_user,
                'entity_data': entity_data,
            },
        },
        method='POST',
    )


def wait_for_handover(pc_api, token, task_no, poll_interval=2, timeout=120):
    """Wait for an asynchronous handover task to reach a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = api(pc_api, token, f'grove_tasks/{task_no}')
        data = result.get('data') or {}
        if data.get('status') in {2, 3, 4, 5, 6}:
            return data
        time.sleep(poll_interval)
    return {'status': -1, 'status_name': '交接任务超时', 'task_no': task_no}


def process_user(pc_api, uc_api, crm_token, usertoken, cookie, apptoken,
                 source_uid, target_uid, origin, poll_interval=2, timeout=120):
    """Process one user and return a concise result dictionary."""
    first_delete = delete_user(uc_api, source_uid, usertoken, cookie, apptoken, origin)
    if first_delete.get('code') == 0:
        return {'user_id': source_uid, 'result': 'deleted_direct'}
    if first_delete.get('code') != DELETE_BLOCKED_CODE:
        return {'user_id': source_uid, 'result': 'delete_error', 'response': first_delete}

    assets = api(pc_api, crm_token, 'handovers/user_assets_counts', {'user_uid': source_uid})
    if assets.get('code') != 0:
        return {'user_id': source_uid, 'result': 'assets_error', 'response': assets}

    handover = create_full_handover(pc_api, crm_token, source_uid, target_uid, assets)
    task_no = (handover.get('data') or {}).get('task_no')
    if handover.get('code') != 0 or not task_no:
        return {'user_id': source_uid, 'result': 'handover_create_error', 'response': handover}

    task = wait_for_handover(pc_api, crm_token, task_no, poll_interval, timeout)
    if task.get('status') not in DONE_STATUSES:
        return {'user_id': source_uid, 'result': 'handover_incomplete', 'task_no': task_no, 'task': task}

    final_delete = delete_user(uc_api, source_uid, usertoken, cookie, apptoken, origin)
    return {
        'user_id': source_uid,
        'result': 'deleted_after_handover' if final_delete.get('code') == 0 else 'delete_blocked',
        'task_no': task_no,
        'response': final_delete,
    }


def main():
    parser = argparse.ArgumentParser(description='CRM 用户删除-交接-再删除完整闭环')
    parser.add_argument('--env', choices=['test', 'staging', 'production'], default='test')
    parser.add_argument('--profile')
    parser.add_argument('--api', help='CRM Web 域名')
    parser.add_argument('--token', help='CRM API Token')
    parser.add_argument('--uc-api', help='UC 管理接口域名')
    parser.add_argument('--origin', help='CRM Web Origin')
    parser.add_argument('--usertoken', help='UC 删除接口 usertoken')
    parser.add_argument('--apptoken', help='UC 删除接口 apptoken')
    parser.add_argument('--cookie')
    parser.add_argument('--cookie-file')
    parser.add_argument('--from-user', type=int, action='append', required=True, help='待删除 UID，可重复传入')
    parser.add_argument('--to-user', type=int, required=True, help='交接接收人 UID')
    parser.add_argument('--poll-interval', type=float, default=2)
    parser.add_argument('--timeout', type=int, default=120)
    args = apply_config_defaults(parser.parse_args(), parser)
    env_config = load_config(args.env, args.profile)
    args.uc_api = args.uc_api or os.environ.get('UC_API') or env_config.get('uc_api')
    args.origin = args.origin or os.environ.get('CRM_ORIGIN') or env_config.get('origin')
    args.usertoken = args.usertoken or os.environ.get('UC_USER_TOKEN') or env_config.get('usertoken') or args.token
    args.apptoken = args.apptoken or os.environ.get('UC_APP_TOKEN') or env_config.get('apptoken')
    if not args.uc_api:
        args.uc_api = f'https://uc-{args.env}.weiwenjia.com'
    if not args.origin:
        args.origin = f'https://lxcrm-{args.env}.weiwenjia.com'
    if not args.usertoken or not args.apptoken:
        parser.error('--usertoken/--apptoken 或 UC_USER_TOKEN/UC_APP_TOKEN 必须提供')
    try:
        cookie = load_cookie(args.cookie, args.cookie_file)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    pc_api = infer_pc_api(args.api)
    failed = False
    for source_uid in args.from_user:
        result = process_user(
            pc_api, args.uc_api, args.token, args.usertoken, cookie, args.apptoken,
            source_uid, args.to_user, args.origin, args.poll_interval, args.timeout,
        )
        print(result)
        if result['result'] not in {'deleted_direct', 'deleted_after_handover'}:
            print(f'处理失败或仍被拦截: {source_uid}', file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
