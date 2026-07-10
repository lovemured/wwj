#!/usr/bin/env python3
"""员工交接接口测试脚本
支持以下交接相关接口的测试：
  1. 交接前统计  - 查询用户各模块资产数量
  2. 检查容量    - 校验接收人容量上限
  3. 创建交接    - 创建交接任务(异步执行)
  4. 任务列表    - 查询交接任务列表
  5. 任务详情    - 查询单个任务详情
  6. 重新开始    - 恢复失败/中断的交接任务

使用:
  # 交接前统计：查看用户 A 各模块数据量
  python3 handover_test.py --api https://域名 --token xxx --action check_assets --from-user 用户UID

  # 检查容量：查看接收人 B 能否接收
  python3 handover_test.py --api https://域名 --token xxx --action check_capacity \
      --from-user 源用户UID --to-user 目标用户UID --modules lead,customer

  # 创建交接：将用户 A 的线索/客户交接给用户 B
  python3 handover_test.py --api https://域名 --token xxx --action create \
      --from-user 源用户UID --to-user 目标负责人UID --assist-user 目标协作人UID \
      --modules lead,customer

  # 使用自定义模块（如项目跟进 data_93171715128380）
  python3 handover_test.py --api https://域名 --token xxx --action create \
      --from-user 源用户UID --to-user 目标UID \
      --modules lead,data_93171715128380 \
      --module-names 线索,项目跟进

  # 任务列表：查看交接任务执行状态
  python3 handover_test.py --api https://域名 --token xxx --action list_tasks --operator-uid 操作人UID

  # 任务详情：查看指定任务的详细信息
  python3 handover_test.py --api https://域名 --token xxx --action task_detail --task-no 任务编号

  # 重新开始：恢复执行失败的任务
  python3 handover_test.py --api https://域名 --token xxx --action resume --task-no 任务编号

  # 完整流程：统计→检查容量→创建→查状态
  python3 handover_test.py --api https://域名 --token xxx --action full \
      --from-user 源用户UID --to-user 目标负责人UID --assist-user 目标协作人UID \
      --modules lead,customer --operator-uid 操作人UID
"""
import requests, argparse, sys, json, time

PC_API = None
TOKEN = None
HEADERS = None


def api(path, data=None, method='GET'):
    """通用 API 请求（PC 端点）"""
    url = f'{PC_API}/api/pc/{path.lstrip("/")}'
    try:
        if method == 'GET':
            params = data or {}
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        else:
            r = requests.request(method, url, headers=HEADERS, json=data, timeout=60)
        return r.json()
    except requests.RequestException as e:
        return {'code': -1, 'message': f'请求失败: {e}'}


def print_section(title):
    """打印分隔标题"""
    print(f'\n{"=" * 60}')
    print(f'  {title}')
    print('=' * 60)


def print_json(obj, indent=2):
    """格式化打印 JSON"""
    print(json.dumps(obj, ensure_ascii=False, indent=indent))


# ====== 接口实现 ======

def check_assets(from_user_uid):
    """1. 交接前统计 - 查询用户各模块资产数量"""
    print_section(f'交接前统计 (用户UID: {from_user_uid})')
    res = api('handovers/user_assets_counts', {'user_uid': from_user_uid})
    code = res.get('code', -1)

    if code != 0:
        print(f'✗ 查询失败: {res.get("message", "未知错误")}')
        print_json(res)
        return None

    modules = res.get('data', {}).get('modules', [])
    if not modules:
        print('  该用户没有可交接的数据')
        return res

    print(f'  共 {len(modules)} 个模块有数据:\n')
    total = 0
    for m in modules:
        print(f'    {m["module_name"]:<12} ({m["module_class"]}): {m["count"]} 条')
        total += m['count']
    print(f'    {"-" * 32}')
    print(f'    合计: {total} 条')
    return res


def check_capacity(from_user_uid, to_user_uid, modules):
    """2. 检查容量 - 校验接收人容量上限"""
    print_section(f'检查容量 源用户={from_user_uid} -> 接收人={to_user_uid}')
    module_list = []
    for mc in modules:
        module_list.append({
            'module_class': mc,
            'to_user_uid': to_user_uid,
            'from_user_uid': from_user_uid,
        })

    res = api('handovers/check_capacity', data={'modules': module_list}, method='POST')
    code = res.get('code', -1)

    if code != 0:
        print(f'✗ 容量检查失败: {res.get("message", "未知错误")}')
        print_json(res)
        return None

    data = res.get('data', {})
    mods = data.get('modules', [])
    print(f'  共检查 {len(mods)} 个模块:\n')
    for m in mods:
        print(f'  【{m["module_name"]}】({m["module_class"]})')
        d = m.get('data', {})
        print(f'    是否开启限制: {"是" if d.get("enable_limit") else "否"}')
        print(f'    限制类型: {d.get("limit_type", "N/A")}')
        for limit in d.get('limits', []):
            source_name = limit.get('source_name', limit.get('category_name', 'N/A'))
            count = limit.get('count', 0)
            used = limit.get('used_count', 0)
            remain = count - used
            print(f'    来源 "{source_name}": 上限={count}, 已用={used}, 剩余={remain}')
        print()
    return res


def create_handover(from_user_uid, to_user_uid, assist_user_uid, modules, module_names=None):
    """3. 创建交接任务（异步执行）"""
    print_section(f'创建交接任务')
    print(f'  源用户: {from_user_uid}')
    print(f'  新负责人: {to_user_uid}')
    print(f'  新协作人: {assist_user_uid}')
    print(f'  交接模块: {modules}')

    entity_data = []
    for i, mc in enumerate(modules):
        mn = module_names[i] if module_names and i < len(module_names) else mc
        entity = {
            'module_class': mc,
            'module_name': mn,
            'to_user_uid': to_user_uid,
            'to_assist_user_uid': assist_user_uid,
        }
        entity_data.append(entity)
        print(f'    {i + 1}. {mn} ({mc}) -> 负责人:{to_user_uid} 协作人:{assist_user_uid}')

    payload = {
        'job_type': 'Handover',
        'job_args': {
            'from_user_uid': from_user_uid,
            'entity_data': entity_data,
        }
    }
    print(f'\n  请求体:')
    print_json(payload)

    res = api('grove_tasks', data=payload, method='POST')
    code = res.get('code', -1)

    if code == 0:
        data = res.get('data', {})
        print(f'\n  ✅ 交接任务创建成功!')
        print(f'    任务编号: {data.get("task_no")}')
        print(f'    状态: {data.get("status_name")} (code: {data.get("status")})')
    elif code == -1 and res.get('data', {}).get('has_running_task'):
        print(f'\n  ⚠️ 企业下已有相同的交接任务在执行中，请等待完成后再试')
    else:
        print(f'\n  ✗ 创建失败: {res.get("message", "未知错误")}')
    print_json(res)
    return res


def list_tasks(operator_uid, status=None, page=1, page_size=10):
    """4. 查询交接任务列表"""
    print_section(f'查询交接任务列表 (操作人UID: {operator_uid})')
    params = {
        'job_type': 'Handover',
        'operator_uid': operator_uid,
        'page': page,
        'page_size': page_size,
    }
    if status is not None:
        params['status'] = status

    res = api('grove_tasks', data=params, method='GET')
    code = res.get('code', -1)

    if code != 0:
        print(f'✗ 查询失败: {res.get("message", "未知错误")}')
        print_json(res)
        return None

    data = res.get('data', {})
    if not data.get('has_task'):
        print('  暂无交接任务')
        return res

    tasks = data.get('list', [])
    status_map = {0: '待执行', 1: '执行中', 2: '已完成', 3: '执行失败', 4: '部分成功', 5: '未知错误', 6: '超时'}

    print(f'  共 {len(tasks)} 个任务:\n')
    for t in tasks:
        s = t.get('status', -1)
        s_name = status_map.get(s, f'未知({s})')
        jr = t.get('job_results', {})
        total_m = jr.get('total_module_count', 0)
        done_m = jr.get('completed_module_count', 0)
        failed_m = jr.get('failed_module_count', 0)

        created = t.get('created_at', '')[:19].replace('T', ' ')
        print(f'  📋 任务: {t["task_no"][:16]}...')
        print(f'     状态: {s_name}  |  模块: {done_m}/{total_m} 完成  |  失败: {failed_m}')
        print(f'     创建: {created}')
        print()
    return res


def task_detail(task_no):
    """5. 查询任务详情"""
    print_section(f'任务详情: {task_no}')
    res = api(f'grove_tasks/{task_no}')
    code = res.get('code', -1)

    if code != 0:
        print(f'✗ 查询失败: {res.get("message", "未知错误")}')
        return None

    data = res.get('data', {})
    status_map = {0: '待执行', 1: '执行中', 2: '已完成', 3: '执行失败', 4: '部分成功', 5: '未知错误', 6: '超时'}
    s = data.get('status', -1)
    s_name = status_map.get(s, f'未知({s})')

    print(f'  任务编号: {data.get("task_no")}')
    print(f'  任务类型: {data.get("job_type")}')
    print(f'  状态: {s_name} (code: {s})')

    jr = data.get('job_results', {})
    fu = jr.get('from_user', {})
    print(f'\n  源用户: {fu.get("name", "?")} (UID: {fu.get("uid")})')

    print(f'\n  模块交接明细:')
    for em in jr.get('entity_data', []):
        es = em.get('status', -1)
        es_name = status_map.get(es, f'未知({es})')
        icon = {'已完成': '✅', '执行中': '⏳', '待处理': '⏸', '执行失败': '❌'}.get(es_name, '❓')
        print(f'  {icon} {em["module_name"]:<12} ({em["module_class"]})')
        print(f'    状态: {es_name}  进度: {em.get("progress", 0) * 100:.0f}%  数量: {em.get("final_count", 0)}')
        tu = em.get('to_user', {})
        ta = em.get('to_assist_user', {})
        print(f'    接收负责人: {tu.get("name", "?")} (UID: {tu.get("uid")})')
        print(f'    接收协作人: {ta.get("name", "?")} (UID: {ta.get("uid")})')
        for err in em.get('errors', []):
            print(f'    ⚠️ 错误: [{err.get("code")}] {err.get("message")}')

    op = data.get('operator', {})
    print(f'\n  操作人: {op.get("name", "?")} (UID: {op.get("uid")})')
    print(f'  创建: {data.get("created_at", "")[:19].replace("T", " ")}')
    if data.get('started_at'):
        print(f'  开始: {data["started_at"][:19].replace("T", " ")}')
    if data.get('ended_at'):
        print(f'  结束: {data["ended_at"][:19].replace("T", " ")}')
    return res


def resume(task_no):
    """6. 重新开始/恢复执行"""
    print_section(f'恢复执行任务: {task_no}')
    res = api(f'grove_tasks/{task_no}/resume', data={}, method='POST')
    code = res.get('code', -1)

    if code == 0:
        data = res.get('data', {})
        print(f'  ✅ 任务已恢复执行!')
        print(f'    任务编号: {data.get("task_no")}')
        print(f'    状态: {data.get("status_name")} (code: {data.get("status")})')
    else:
        print(f'  ✗ 恢复失败: {res.get("message", "未知错误")}')
        print_json(res)
    return res


def full_flow(from_user_uid, to_user_uid, assist_user_uid, modules, module_names, operator_uid):
    """完整交接流程测试"""
    print_section('开始完整交接流程')
    print(f'  源用户: {from_user_uid}')
    print(f'  目标负责人: {to_user_uid}')
    print(f'  目标协作人: {assist_user_uid}')
    print(f'  模块: {modules}')
    print(f'  操作人: {operator_uid}')

    # Step 1: 交接前统计
    print('\n\n【Step 1/4】交接前统计...')
    assets = check_assets(from_user_uid)
    if not assets:
        print('⚠️ 统计失败，继续尝试...')

    # Step 2: 检查容量
    print('\n\n【Step 2/4】检查容量...')
    cap = check_capacity(from_user_uid, to_user_uid, modules)
    if not cap:
        print('⚠️ 容量检查失败，继续尝试...')

    # Step 3: 创建交接
    print('\n\n【Step 3/4】创建交接任务...')
    task = create_handover(from_user_uid, to_user_uid, assist_user_uid, modules, module_names)
    if not task or task.get('code') != 0:
        print('✗ 创建交接任务失败，流程终止')
        return

    task_no = task.get('data', {}).get('task_no')
    if not task_no:
        print('✗ 未获取到任务编号')
        return

    # Step 4: 轮询任务状态（最多等 60 秒）
    print('\n\n【Step 4/4】轮询任务状态...')
    for i in range(12):
        time.sleep(5)
        detail = task_detail(task_no)
        if not detail:
            continue
        status = detail.get('data', {}).get('status', -1)
        if status == 2:
            print(f'\n  ✅ 交接任务已完成!')
            break
        elif status in (3, 5, 6):
            print(f'\n  ❌ 交接任务执行失败 (status={status})')
            print(f'  可执行 resume 操作恢复:')
            print(f'    python3 handover_test.py --api ... --action resume --task-no {task_no}')
            break
        elif status == 4:
            print(f'\n  ⚠️ 交接任务部分成功')
            break
        print(f'  第 {i + 1}/12 次轮询: 状态={detail["data"]["status_name"]}，继续等待...')
    else:
        print('\n  ⏰ 轮询超时，请手动查看任务状态')

    print(f'\n{"=" * 60}')
    print(f'  完整流程结束')
    print(f'  任务编号: {task_no}')
    print(f'  查看详情: python3 handover_test.py --api ... --action task_detail --task-no {task_no}')
    print(f'  恢复执行: python3 handover_test.py --api ... --action resume --task-no {task_no}')
    print('=' * 60)


def main():
    p = argparse.ArgumentParser(description='员工交接接口测试脚本')
    p.add_argument('--api', required=True, help='API域名，如 https://lxcrm-staging.weiwenjia.com')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--action', required=True,
                   choices=['check_assets', 'check_capacity', 'create', 'list_tasks',
                            'task_detail', 'resume', 'full'],
                   help='操作类型')
    # 用户相关
    p.add_argument('--from-user', type=int, help='源用户UID（被交接人）')
    p.add_argument('--to-user', type=int, help='目标负责人UID')
    p.add_argument('--assist-user', type=int, default=0, help='目标协作人UID')
    p.add_argument('--operator-uid', type=int, help='操作人UID')
    # 模块
    p.add_argument('--modules', help='模块列表，逗号分隔，如 lead,customer')
    p.add_argument('--module-names', help='模块显示名，逗号分隔，如 线索,客户')
    # 任务
    p.add_argument('--task-no', help='任务编号')
    p.add_argument('--status', type=int, choices=[0, 1, 2, 3, 4, 5, 6],
                   help='任务状态筛选 0待执行 1执行中 2已完成 3执行失败 4部分成功')
    p.add_argument('--page', type=int, default=1, help='页码')
    p.add_argument('--page-size', type=int, default=10, help='每页数量')

    a = p.parse_args()

    global PC_API, TOKEN, HEADERS
    # 推断 PC API 域名
    api_url = a.api.rstrip('/')
    PC_API = api_url.replace('//lxcrm-staging.', '//lxcrm-api-staging.')
    PC_API = PC_API.replace('//lxcrm-test.', '//lxcrm-api-test.')
    if PC_API == api_url:
        PC_API = api_url  # 非标准域名，直接用
    TOKEN = a.token
    HEADERS = {'Content-Type': 'application/json', 'Authorization': f'Token token={TOKEN}'}

    print(f'API: {PC_API}')
    print(f'Action: {a.action}')

    # 解析模块列表
    modules = a.modules.split(',') if a.modules else []
    module_names = a.module_names.split(',') if a.module_names else None

    # 执行操作
    if a.action == 'check_assets':
        if not a.from_user:
            p.error('--from-user 必需')
        check_assets(a.from_user)

    elif a.action == 'check_capacity':
        if not a.from_user or not a.to_user or not a.modules:
            p.error('--from-user, --to-user, --modules 均必需')
        check_capacity(a.from_user, a.to_user, modules)

    elif a.action == 'create':
        if not a.from_user or not a.to_user or not a.modules:
            p.error('--from-user, --to-user, --modules 均必需')
        create_handover(a.from_user, a.to_user, a.assist_user or a.to_user, modules, module_names)

    elif a.action == 'list_tasks':
        if not a.operator_uid:
            p.error('--operator-uid 必需')
        list_tasks(a.operator_uid, a.status, a.page, a.page_size)

    elif a.action == 'task_detail':
        if not a.task_no:
            p.error('--task-no 必需')
        task_detail(a.task_no)

    elif a.action == 'resume':
        if not a.task_no:
            p.error('--task-no 必需')
        resume(a.task_no)

    elif a.action == 'full':
        if not a.from_user or not a.to_user or not a.modules or not a.operator_uid:
            p.error('--from-user, --to-user, --modules, --operator-uid 均必需')
        full_flow(a.from_user, a.to_user, a.assist_user or a.to_user,
                  modules, module_names, a.operator_uid)


if __name__ == '__main__':
    main()
