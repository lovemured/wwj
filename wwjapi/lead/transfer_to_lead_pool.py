#!/usr/bin/env python3
"""转线索池 - 将线索转入线索池
使用: python3 transfer_to_lead_pool.py --api https://域名 --token xxx --lead-id 线索ID
      python3 transfer_to_lead_pool.py --api https://域名 --token xxx --lead-id 线索ID --pool-id 线索池ID
"""
import requests, argparse, sys

def main():
    p = argparse.ArgumentParser(description='转线索池')
    p.add_argument('--api', required=True, help='API域名')
    p.add_argument('--token', required=True, help='Token')
    p.add_argument('--lead-id', required=True, type=int, help='线索ID')
    p.add_argument('--pool-id', type=int, default=0, help='线索池ID(默认取第一个可用)')
    a = p.parse_args()

    api = a.api.rstrip('/')
    # 推断PC API域名
    api_pc = api.replace('//lxcrm-staging.', '//lxcrm-api-staging.')
    api_pc = api_pc.replace('//lxcrm-test.', '//lxcrm-api-test.')
    # 如果非标准域名，使用原域名
    if api_pc == api:
        api_pc = api

    H = {'Content-Type': 'application/json', 'Authorization': f'Token token={a.token}'}
    v2 = f'{api}/api/v2'
    # PC API基础路径
    pc_api_base = api_pc if 'api' in api_pc else api
    pc_path = f'{pc_api_base}/api/pc'

    print('=' * 70)
    print('转线索池')
    print('=' * 70)

    # 获取线索信息
    r = requests.get(f'{v2}/leads/{a.lead_id}', headers=H)
    lead = r.json().get('data', {})
    if not lead.get('id'):
        print(f'✗ 线索{a.lead_id}不存在')
        sys.exit(1)
    print(f'\n线索: {lead.get("name")} (状态: {lead.get("status_mapped", "")})')

    # 获取线索池列表
    cs = requests.get(f'{v2}/common_leads/common_settings', headers=H)
    pools = cs.json().get('data', {}).get('common_settings', [])

    if not pools:
        print('✗ 未找到线索池配置'); sys.exit(1)

    # 选择池
    if a.pool_id:
        pool = next((p for p in pools if p['id'] == a.pool_id), None)
        if not pool:
            print(f'✗ 线索池ID {a.pool_id} 不存在'); sys.exit(1)
    else:
        pool = pools[0]  # 取第一个

    print(f'\n目标线索池: {pool.get("name")} (ID: {pool.get("id")})')

    # 执行转换
    payload = {'lead_ids': [a.lead_id], 'common_id': pool['id']}

    # 尝试PC端点
    r = requests.post(f'{pc_path}/batch_resources/mass_transfer_to_common_pool',
                       headers=H, json=payload)

    try:
        res = r.json()
    except:
        res = {}

    code = res.get('code', r.status_code)

    if code == 0:
        print(f'✅ 线索{a.lead_id} 已成功转入线索池"{pool.get("name")}"!')
    else:
        # 降级方案：PUT lead_common_setting_id
        print(f'PC端点返回 {r.status_code}，尝试降级方案...')
        r2 = requests.put(f'{v2}/leads/{a.lead_id}',
                          headers=H,
                          json={'lead': {'lead_common_setting_id': pool['id']}})
        res2 = r2.json()
        if res2.get('code') == 0:
            print(f'✅ 线索{a.lead_id} 已成功转入线索池"{pool.get("name")}"(PUT方式)!')
        else:
            print(f'✗ 转线索池失败: {res2.get("message", "未知错误")}')
            sys.exit(1)

    print(f'\n{"=" * 70}')
    print('完成!')
    print('=' * 70)


if __name__ == '__main__':
    main()
