#!/usr/bin/env python3
"""编辑产品 - 所有字段值不能和编辑前一样
使用: python3 edit_product.py --id 产品ID"""
import requests,json,random,string,argparse,os
from datetime import datetime,timedelta

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

NAMES=['智能办公椅','便携投影仪','无线蓝牙耳机','机械键盘','USB-C扩展坞','4K显示器','人体工学鼠标','笔记本支架','降噪耳麦','桌面充电站']
UNITS=['个','台','套','箱','只','条','把','件']
def rn(): return random.choice(NAMES)+'-'+''.join(random.choices(string.ascii_uppercase+string.digits,k=4))
def rp(): return 'PROD-'+''.join(random.choices(string.digits,k=8))
def rp2(): return round(random.uniform(10,9999),2)

def main():
    cfg=load_config()
    p=argparse.ArgumentParser(description='编辑产品')
    p.add_argument('--api',default=cfg.get('api','')); p.add_argument('--token',default=cfg.get('token',''))
    p.add_argument('--id',required=True,type=int)
    a=p.parse_args()
    if not a.api or not a.token: p.error('请在config.json中配置api和token，或通过--api/--token传入')
    api=a.api.rstrip('/'); token=a.token
    r=requests.get(f"{api}/api/v2/products/{a.id}",headers={'Authorization':f'Token token={token}'})
    old=r.json().get('data',{})
    if not old.get('id'): print('产品不存在'); return
    data={'product':{
        'name':rn(),'product_no':rp(),'standard_unit_price':rp2(),
        'sale_unit':random.choice(UNITS),'introduction':f'编辑-{datetime.now().strftime("%Y%m%d%H%M%S")}',
        'unit_cost':rp2(),
    }}
    r2=requests.put(f"{api}/api/v2/products/{a.id}",headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},json=data)
    res=r2.json()
    if res.get('code')==0: print(f"✅ 编辑成功 ID:{a.id}")
    else: print(f"✗ {res.get('message','?')}")

if __name__=='__main__': main()
