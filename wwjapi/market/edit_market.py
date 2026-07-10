#!/usr/bin/env python3
"""编辑市场活动
使用: python3 edit_market.py --api https://域名 --token xxx --id ID"""
import requests,json,random,string,argparse,os
from datetime import datetime,timedelta

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f: return json.load(f)
    return {}

NAMES=["春季促销","新品发布会","客户答谢会","行业峰会","产品培训","市场调研","品牌推广","渠道招商","线上直播","周年庆典"]
def rn(): return random.choice(NAMES)+"-编辑-"+datetime.now().strftime('%H%M%S')
def rd(): return round(random.uniform(1000,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime("%Y-%m-%d")

def main():
    cfg=load_config()
    p=argparse.ArgumentParser(description='编辑市场活动')
    p.add_argument('--api',default=cfg.get('api','')); p.add_argument('--token',default=cfg.get('token',''))
    p.add_argument('--id',required=True,type=int)
    a=p.parse_args()
    if not a.api or not a.token: p.error('请在config.json中配置api和token，或通过--api/--token传入')
    api=a.api.rstrip('/'); token=a.token
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.')
    # 获取当前数据
    r=requests.get(f"{pc}/api/pc/market_activities/{a.id}",headers={'Authorization':f'Token token={token}'})
    old=r.json().get('data',{})
    if not old.get('id'): print('市场活动不存在'); return
    data={'market_activity':{
        'name':rn(),'description':f'编辑于{datetime.now().strftime("%Y-%m-%d %H:%M")}',
        'start_date':rf(),'end_date':rf(),'estimated_cost':rd(),'actual_cost':rd(),
        'estimated_income':rd(),'actual_income':rd(),
    }}
    r2=requests.put(f"{pc}/api/pc/market_activities/{a.id}",
        headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},json=data)
    res=r2.json()
    if res.get('code')==0: print(f"✅ 编辑成功 ID:{a.id} 新名称:{data['market_activity']['name']}")
    else: print(f"✗ {res.get('message','?')}")

if __name__=='__main__': main()