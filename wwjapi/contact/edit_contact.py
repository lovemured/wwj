#!/usr/bin/env python3
"""编辑联系人"""
import requests,json,random,string,argparse
from datetime import datetime,timedelta
def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--api',required=True); p.add_argument('--token',required=True); p.add_argument('--id',required=True,type=int)
    a=p.parse_args(); api=a.api.rstrip('/')
    r=requests.get(f"{api}/api/v2/contacts/{a.id}",headers={'Authorization':f'Token token={a.token}'})
    old=r.json().get('data',{}); 
    if not old.get('id'): print('联系人不存在'); return
    data={'name':'联系人-'+rt()[:6],'job':random.choice(['经理','总监','主管']),'note':'编辑'+rt()[:4]}
    r2=requests.put(f"{api}/api/v2/contacts/{a.id}",headers={'Content-Type':'application/json','Authorization':f'Token token={a.token}'},json={'contact':data})
    res=r2.json()
    if res.get('code')==0: print(f"✅ 编辑成功 ID:{a.id}")
    else: print(f"✗ {res.get('message','?')}")
if __name__=='__main__': main()
