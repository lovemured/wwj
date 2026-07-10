#!/usr/bin/env python3
"""一键验证交接模块 - 自动执行完整流程并输出结果"""
import sys, os, json, time, io

sys.path.insert(0, os.path.dirname(__file__))
from handover_common import api, infer_pc_api, STATUS_MAP
import create_handover
import handover_tasks
import resume_handover


def verify(pc_api, token, from_uid, to_uid, operator_uid):
    results = {'passed': 0, 'failed': 0, 'steps': []}

    def step(name, ok, detail=''):
        status = '\U0001f7e6' if ok else '\u274c'
        results['steps'].append({'name': name, 'ok': ok, 'detail': detail})
        if ok:
            results['passed'] += 1
        else:
            results['failed'] += 1
        print(f'  {status} {name}')
        if detail:
            for line in detail.strip().split('\n'):
                print(f'    {line}')

    print(f'\n{"="*60}')
    print(f'  交接模块一键验证')
    print(f'  源用户: {from_uid} -> 目标用户: {to_uid}')
    print(f'  操作人: {operator_uid}')
    print(f'{"="*60}')

    # === 1. 交接前统计 ===
    print(f'\n--- 1/6 交接前统计 ---')
    assets = create_handover.check_assets(pc_api, token, from_uid)
    if assets and assets.get('code') == 0:
        modules = assets.get('data', {}).get('modules', [])
        detail = f'共 {len(modules)} 个模块有数据'
        step('交接前统计', True, detail)
    else:
        step('交接前统计', False, assets.get('message','?') if assets else '返回空')

    # === 2. 检查容量 ===
    print(f'\n--- 2/6 检查容量 ---')
    test_modules = ['lead', 'customer']
    cap = create_handover.check_capacity(pc_api, token, from_uid, to_uid, test_modules)
    if cap and cap.get('code') == 0:
        mods = cap.get('data', {}).get('modules', [])
        all_pass = all(m.get('data', {}).get('pass') for m in mods)
        detail = f'检查 {len(mods)} 个模块，{"全部可接收" if all_pass else "部分模块不可接收"}'
        step('检查容量', all_pass, detail)
    else:
        step('检查容量', False, cap.get('message','?') if cap else '返回空')

    # === 3. 创建交接 ===
    print(f'\n--- 3/6 创建交接 ---')
    task = create_handover.create_handover(
        pc_api, token, from_uid, to_uid, to_uid, test_modules,
        from_user_name='用户1')
    task_no = ''
    if task and task.get('code') == 0:
        task_no = task.get('data', {}).get('task_no', '')
        step('创建交接', True, f'任务编号: {task_no}')
    else:
        step('创建交接', False, task.get('message','?') if task else '返回空')

    # === 4. 任务列表 ===
    print(f'\n--- 4/6 任务列表 ---')
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    handover_tasks.list_tasks(pc_api, token, operator_uid)
    sys.stdout = old_stdout
    output = captured.getvalue()
    has_tasks = '暂无交接任务' not in output
    step('任务列表', has_tasks, f'操作人: {operator_uid}')

    # === 5. 任务详情 ===
    print(f'\n--- 5/6 任务详情 ---')
    if task_no:
        captured = io.StringIO()
        sys.stdout = captured
        handover_tasks.task_detail(pc_api, token, task_no)
        sys.stdout = old_stdout
        output = captured.getvalue()
        has_detail = '查询失败' not in output
        step('任务详情', has_detail, f'任务: {task_no}')
    else:
        step('任务详情', False, '无任务编号，跳过')

    # === 6. 恢复任务 ===
    print(f'\n--- 6/6 恢复任务 ---')
    if task_no:
        captured = io.StringIO()
        sys.stdout = captured
        resume_handover.resume(pc_api, token, task_no)
        sys.stdout = old_stdout
        output = captured.getvalue()
        step('恢复任务', True, '接口调用完成')
    else:
        step('恢复任务', False, '无任务编号，跳过')

    # === 汇总 ===
    print(f'\n{"="*60}')
    print(f'  验证汇总: {results["passed"]}/{len(results["steps"])} 通过, '
          f'{results["failed"]} 失败')
    print(f'{"="*60}')
    return results


def main():
    import argparse
    p = argparse.ArgumentParser(description='一键验证交接模块')
    p.add_argument('--api', required=True, help='API域名')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--from-user', type=int, required=True, help='源用户UID')
    p.add_argument('--to-user', type=int, required=True, help='目标用户UID')
    p.add_argument('--operator-uid', type=int, required=True, help='操作人UID')
    a = p.parse_args()

    pc_api = infer_pc_api(a.api)
    print(f'API: {pc_api}')
    verify(pc_api, a.token, a.from_user, a.to_user, a.operator_uid)


if __name__ == '__main__':
    main()
