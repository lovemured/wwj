#!/usr/bin/env python3
"""编辑回款/开票记录 - 精简版"""
import requests,json,random,string,argparse
from datetime import datetime,timedelta
def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def re(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999); rd=lambda: round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--api',required=True); p.add_argument('--token',required=True)
    p.add_argument('--type',choices=['received_payment','invoiced_payment'],default='received_payment')
    p.add_argument('--id',required=True,type=int)
    a=p.parse_args(); api=a.api.rstrip('/'); t=a.type
    H={'Authorization':f'Token token={a.token}'}
    r=requests.get(f"{api}/api/v2/{t}s/{a.id}",headers=H)
    old=r.json().get('data',{})
    if not old.get('id'): print(f'记录{a.id}不存在'); return
    data={'amount':rd(),'note':f'编辑{rt()[:6]}'}; data['receive_date' if t=='received_payment' else 'invoiced_date']=rf()
    r2=requests.put(f"{api}/api/v2/{t}s/{a.id}",headers={'Content-Type':'application/json',**H},json={t:data})
    res=r2.json()
    if res.get('code')==0: print(f"✅ 编辑成功 ID:{a.id}")
    else: print(f"✗ {res.get('message','?')}")
if __name__=='__main__': main()
