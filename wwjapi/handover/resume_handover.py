#!/usr/bin/env python3
"""恢复交接任务 - 重新执行失败/中断的交接任务
使用:
  python3 resume_handover.py --api https://域名 --token xxx --task-no 任务编号
"""
import argparse
from handover_common import api, infer_pc_api, STATUS_MAP


def resume(pc_api, token, task_no):
    """恢复交接任务"""
    print(f'\n{"="*60}')
    print(f'  恢复交接任务 #{task_no}')
    print(f'{"="*60}')

    detail = api(pc_api, token, f'grove_tasks/{task_no}')
    if detail.get('code') != 0:
        print(f'  ✗ 查询任务失败: {detail.get("message", "未知错误")}')
        return
    data = detail.get('data', {})
    status = data.get('status')
    status_name = data.get('status_name', STATUS_MAP.get(status, f'未知({status})'))
    operator = data.get('operator', {})
    job_args = data.get('job_args', {})
    print(f'  当前状态: {status_name}')
    print(f'  操作人: {operator.get("name", "")} (UID: {operator.get("uid", "")})')
    print(f'  源用户UID: {job_args.get("from_user_uid", "")}')

    if status == 2:
        print(f'  ⚠️ 任务已完成，无需恢复')
        return
    if status == 1:
        print(f'  ⚠️ 任务正在执行中，请稍后再试')
        return

    res = api(pc_api, token, f'grove_tasks/{task_no}/resume', {}, method='POST')
    if res.get('code') == 0:
        print(f'  ✅ 任务已重新开始执行!')
    else:
        print(f'  ✗ 恢复失败: {res.get("message", "未知错误")}')
    return res


def main():
    p = argparse.ArgumentParser(description='恢复交接任务')
    p.add_argument('--api', required=True, help='API域名')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--task-no', required=True, help='任务编号')
    a = p.parse_args()

    pc_api = infer_pc_api(a.api)
    print(f'API: {pc_api}')
    resume(pc_api, a.token, a.task_no)


if __name__ == '__main__':
    main()
