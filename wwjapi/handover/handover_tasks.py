#!/usr/bin/env python3
"""查询交接任务 - 任务列表 + 任务详情
使用:
  # 任务列表
  python3 handover_tasks.py --api https://域名 --token xxx \
      --action list --operator-uid 操作人UID

  # 按状态筛选
  python3 handover_tasks.py --api https://域名 --token xxx \
      --action list --operator-uid 操作人UID --status 2

  # 任务详情
  python3 handover_tasks.py --api https://域名 --token xxx \
      --action detail --task-no 任务编号
"""
import argparse
from handover_common import api, infer_pc_api, STATUS_MAP


def list_tasks(pc_api, token, operator_uid, status=None, page=1, page_size=10):
    """查询交接任务列表"""
    print(f'\n{"="*60}')
    print(f'  交接任务列表 (操作人: {operator_uid})')
    print(f'{"="*60}')
    params = {
        'job_type': 'Handover',
        'operator_uid': operator_uid,
        'page': page,
        'page_size': page_size,
    }
    if status is not None:
        params['status'] = status
    res = api(pc_api, token, 'grove_tasks', params)
    if res.get('code') != 0:
        print(f'  ✗ 查询失败: {res.get("message", "未知错误")}')
        return
    data = res.get('data', {})
    tasks = data.get('list', [])
    print(f'  共 {len(tasks)} 条记录 (第{page}页)\n')
    if not tasks:
        print('  暂无交接任务')
        return
    for t in tasks:
        status_name = t.get('status_name', STATUS_MAP.get(t.get('status'), f'未知({t.get("status")})'))
        operator = t.get('operator', {})
        job_args = t.get('job_args', {})
        entity_data = job_args.get('entity_data', [])
        from_uid = job_args.get('from_user_uid', '')
        modules_str = ', '.join([e.get('module_name', e.get('module_class', '?')) for e in entity_data])
        print(f'  #{t["task_no"]}  {status_name}')
        print(f'    操作人: {operator.get("name", "")} (UID: {operator.get("uid", "")})')
        print(f'    源用户UID: {from_uid}')
        print(f'    模块: {modules_str}')
        print(f'    创建时间: {t.get("created_at", "")}')
        if t.get('ended_at'):
            print(f'    完成时间: {t["ended_at"]}')
        print()


def task_detail(pc_api, token, task_no):
    """查询任务详情"""
    print(f'\n{"="*60}')
    print(f'  交接任务详情 #{task_no}')
    print(f'{"="*60}')
    res = api(pc_api, token, f'grove_tasks/{task_no}')
    if res.get('code') != 0:
        print(f'  ✗ 查询失败: {res.get("message", "未知错误")}')
        return
    data = res.get('data', {})
    status_name = data.get('status_name', STATUS_MAP.get(data.get('status'), f'未知({data.get("status")})'))
    operator = data.get('operator', {})
    job_args = data.get('job_args', {})
    job_results = data.get('job_results', {})
    entity_data = job_args.get('entity_data', [])
    from_user = job_results.get('from_user', {})
    print(f'  任务编号: {data.get("task_no")}')
    print(f'  状态: {status_name}')
    print(f'  操作人: {operator.get("name", "")} (UID: {operator.get("uid", "")})')
    print(f'  源用户: {from_user.get("name", "")} (UID: {from_user.get("uid", "")})')
    print(f'  创建时间: {data.get("created_at", "")}')
    if data.get('started_at'):
        print(f'  开始时间: {data["started_at"]}')
    if data.get('ended_at'):
        print(f'  完成时间: {data["ended_at"]}')
    print()
    # 模块详情 - 从 job_results 取执行状态
    result_entities = job_results.get('entity_data', [])
    if result_entities:
        print(f'  模块执行详情 ({len(result_entities)} 个):')
        print(f'    总进度: {job_results.get("completed_module_count", 0)}/{job_results.get("total_module_count", 0)} 完成')
        for m in result_entities:
            print(f'    【{m.get("module_name", m.get("module_class"))}】({m["module_class"]})')
            print(f'      状态: {m.get("status_name", "未知")}')
            print(f'      进度: {m.get("progress", 0)}%')
            print(f'      处理: {m.get("final_count", 0)}/{m.get("total_count", 0)} 条')
            if m.get('errors'):
                for err in m['errors']:
                    print(f'      错误: {err}')
            print()
    elif entity_data:
        print(f'  模块配置 ({len(entity_data)} 个):')
        for m in entity_data:
            print(f'    【{m.get("module_name", m.get("module_class"))}】({m["module_class"]})')
            print(f'      目标负责人UID: {m.get("to_user_uid", "")}')
            print(f'      目标协作人UID: {m.get("to_assist_user_uid", "")}')
            print()
    return res


def main():
    p = argparse.ArgumentParser(description='查询交接任务')
    p.add_argument('--api', required=True, help='API域名')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--action', required=True, choices=['list', 'detail'],
                   help='list: 任务列表 | detail: 任务详情')
    p.add_argument('--operator-uid', type=int, help='操作人UID（list模式必需）')
    p.add_argument('--task-no', help='任务编号（detail模式必需）')
    p.add_argument('--status', type=int, choices=[0, 1, 2, 3, 4, 5, 6],
                   help='任务状态筛选 0待执行 1执行中 2已完成 3执行失败 4部分成功')
    p.add_argument('--page', type=int, default=1, help='页码')
    p.add_argument('--page-size', type=int, default=10, help='每页数量')
    a = p.parse_args()

    pc_api = infer_pc_api(a.api)
    print(f'API: {pc_api}')

    if a.action == 'list':
        if not a.operator_uid:
            p.error('--operator-uid 在 list 模式下必需')
        list_tasks(pc_api, a.token, a.operator_uid, a.status, a.page, a.page_size)
    elif a.action == 'detail':
        if not a.task_no:
            p.error('--task-no 在 detail 模式下必需')
        task_detail(pc_api, a.token, a.task_no)


if __name__ == '__main__':
    main()
