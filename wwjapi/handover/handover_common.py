#!/usr/bin/env python3
"""交接模块公共工具函数"""
import requests

STATUS_MAP = {
    0: '待执行', 1: '执行中', 2: '已完成',
    3: '执行失败', 4: '部分成功', 5: '已中断', 6: '已取消',
}


def api(pc_api, token, path, data=None, method='GET'):
    """通用 API 请求"""
    url = f'{pc_api}/api/pc/{path.lstrip("/")}'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Token token={token}'}
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, params=data, timeout=30)
        else:
            r = requests.request(method, url, headers=headers, json=data, timeout=60)
        try:
            return r.json()
        except ValueError:
            return {'code': -1, 'message': f'响应非JSON: {r.text[:200]}'}
    except requests.RequestException as e:
        return {'code': -1, 'message': f'请求失败: {e}'}


def infer_pc_api(api_url):
    """推断 PC API 域名"""
    u = api_url.rstrip('/')
    u = u.replace('//lxcrm-staging.', '//lxcrm-api-staging.')
    u = u.replace('//lxcrm-test.', '//lxcrm-api-test.')
    return u
