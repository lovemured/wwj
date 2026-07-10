#!/usr/bin/env python3
"""创建交接任务 - 支持交接前统计、检查容量、创建交接
使用:
  # 完整流程：统计→检查容量→创建
  python3 create_handover.py --api https://域名 --token xxx \
      --from-user 源用户UID --to-user 目标负责人UID \
      --modules lead,customer

  # 仅统计
  python3 create_handover.py --api https://域名 --token xxx \
      --action check_assets --from-user 用户UID

  # 仅检查容量
  python3 create_handover.py --api https://域名 --token xxx \
      --action check_capacity --from-user 源UID --to-user 目标UID --modules lead,customer

  # 自定义模块名（如 data_93171715128380）
  python3 create_handover.py --api https://域名 --token xxx \
      --from-user 源UID --to-user 目标UID \
      --modules lead,data_93171715128380 \
      --module-names 线索,项目跟进
"""
import argparse, sys
from handover_common import api, infer_pc_api


def check_assets(pc_api, token, from_user_uid):
    """交接前统计"""
    print(f'\n{"="*60}')
    print(f'  交接前统计 (用户UID: {from_user_uid})')
    print(f'{"="*60}')
    res = api(pc_api, token, 'handovers/user_assets_counts',
              {'user_uid': from_user_uid})
    if res.get('code') != 0:
        print(f'  ✗ 查询失败: {res.get("message", "未知错误")}')
        return None
    modules = res.get('data', {}).get('modules', [])
    if not modules:
        print('  该用户没有可交接的数据')
        return res
    total = 0
    for m in modules:
        print(f'    {m["module_name"]:<12} ({m["module_class"]}): {m["count"]} 条')
        total += m['count']
    print(f'    {"-"*32}')
    print(f'    合计: {total} 条')
    return res


def check_capacity(pc_api, token, from_user_uid, to_user_uid, modules):
    """检查接收人容量"""
    print(f'\n{"="*60}')
    print(f'  检查容量 {from_user_uid} -> {to_user_uid}')
    print(f'{"="*60}')
    module_list = [{
        'module_class': mc,
        'to_user_uid': to_user_uid,
        'from_user_uid': from_user_uid,
    } for mc in modules]
    res = api(pc_api, token, 'handovers/check_capacity',
              {'modules': module_list}, method='POST')
    if res.get('code') != 0:
        print(f'  ✗ 容量检查失败: {res.get("message", "未知错误")}')
        return None
    mods = res.get('data', {}).get('modules', [])
    for m in mods:
        d = m.get('data', {})
        print(f'  【{m["module_name"]}】({m["module_class"]})')
        print(f'    是否开启限制: {"是" if d.get("enable_limit") else "否"}')
        print(f'    限制类型: {d.get("limit_type", "N/A")}')
        for limit in d.get('limits', []):
            print(f'    - {limit.get("source_name", "")}: '
                  f'{limit.get("current_count", 0)}/{limit.get("limit_count", 0)}')
        print(f'    是否可接收: {"✅ 是" if d.get("pass") else "❌ 否"}')
    return res


def create_handover(pc_api, token, from_user_uid, to_user_uid,
                    assist_user_uid, modules, module_names=None,
                    from_user_name=''):
    """创建交接任务"""
    print(f'\n{"="*60}')
    print(f'  创建交接 {from_user_uid} -> {to_user_uid}')
    print(f'{"="*60}')
    entity_data = []
    for i, mc in enumerate(modules):
        # module_class 首字母大写（前端格式：Lead, Customer 等）
        mc_cased = mc[0].upper() + mc[1:] if mc else mc
        mn = module_names[i] if module_names and i < len(module_names) else mc
        entity = {
            'module_class': mc_cased,
            'module_name': mn,
            'to_user_uid': to_user_uid,
            'to_assist_user_uid': assist_user_uid,
        }
        entity_data.append(entity)
        print(f'    {i+1}. {mn} ({mc_cased}) -> 负责人:{to_user_uid} 协作人:{assist_user_uid}')
    payload = {
        'job_type': 'Handover',
        'job_args': {
            'from_user_uid': from_user_uid,
            'from_user': {
                'uid': from_user_uid,
                'name': from_user_name,
            },
            'entity_data': entity_data,
        }
    }
    res = api(pc_api, token, 'grove_tasks', payload, method='POST')
    if res.get('code') == 0:
        task_no = res.get('data', {}).get('task_no', '')
        print(f'  ✅ 交接任务创建成功!')
        print(f'  任务编号: {task_no}')
    else:
        print(f'  ✗ 创建失败: {res.get("message", "未知错误")}')
    return res


def main():
    p = argparse.ArgumentParser(description='创建交接任务')
    p.add_argument('--api', required=True, help='API域名')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--action', choices=['check_assets', 'check_capacity', 'create'],
                   default='create', help='操作类型（默认完整创建）')
    p.add_argument('--from-user', type=int, required=True, help='源用户UID')
    p.add_argument('--from-user-name', default='', help='源用户姓名（前端格式需要）')
    p.add_argument('--to-user', type=int, help='目标负责人UID')
    p.add_argument('--assist-user', type=int, default=0, help='目标协作人UID（默认同--to-user）')
    p.add_argument('--modules', help='模块列表，逗号分隔')
    p.add_argument('--module-names', help='模块显示名，逗号分隔')
    a = p.parse_args()

    pc_api = infer_pc_api(a.api)
    modules = a.modules.split(',') if a.modules else []
    module_names = a.module_names.split(',') if a.module_names else None

    print(f'API: {pc_api}')

    if a.action == 'check_assets':
        check_assets(pc_api, a.token, a.from_user)

    elif a.action == 'check_capacity':
        if not a.to_user or not a.modules:
            p.error('--to-user 和 --modules 在 check_capacity 模式下必需')
        check_capacity(pc_api, a.token, a.from_user, a.to_user, modules)

    elif a.action == 'create':
        if not a.to_user or not a.modules:
            p.error('--to-user 和 --modules 在 create 模式下必需')
        assets = check_assets(pc_api, a.token, a.from_user)
        if assets is None:
            sys.exit(1)
        cap = check_capacity(pc_api, a.token, a.from_user, a.to_user, modules)
        if cap is None:
            sys.exit(1)
        create_handover(pc_api, a.token, a.from_user, a.to_user,
                        a.assist_user or a.to_user, modules, module_names,
                        from_user_name=a.from_user_name)


if __name__ == '__main__':
    main()
