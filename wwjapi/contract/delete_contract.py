#!/usr/bin/env python3
"""删除合同 - 优先删除最早创建的"""
import requests,argparse,time
def main():
    p=argparse.ArgumentParser(); p.add_argument('--api',required=True); p.add_argument('--token',required=True)
    p.add_argument('--id',type=int,default=0); p.add_argument('--count',type=int,default=0)
    a=p.parse_args(); api=a.api.rstrip('/'); H={'Authorization':f'Token token={a.token}'}; v2=f'{api}/api/v2'
    if a.id:
        r=requests.delete(f'{v2}/contracts/{a.id}',headers=H); res=r.json()
        if res.get('code')==0: print(f"✅ 删除成功! ID:{a.id}")
        else: print(f"✗ {res.get('message')}")
        return
    if a.count:
        deleted=0; page=1
        while deleted<a.count:
            r=requests.get(f'{v2}/contracts?per_page=50&sort=created_at&order=asc&page={page}',headers=H)
            items=r.json().get('data',{}).get('contracts',[])
            if not items: break
            for c in items:
                if deleted>=a.count: break; cid=c['id']
                dr=requests.delete(f'{v2}/contracts/{cid}',headers=H)
                if dr.json().get('code')==0: deleted+=1; print(f"  ✓ [{deleted}/{a.count}] ID:{cid}")
                else: print(f"  ○ {dr.json().get('message')}")
            page+=1; time.sleep(0.2)
        print(f"\n完成! 删除 {deleted} 条")
if __name__=='__main__': main()
