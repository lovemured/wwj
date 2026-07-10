#!/usr/bin/env python3
"""删除线索 - 优先删除最早创建的线索
使用:
  python3 delete_lead.py --api https://xxx.com --token xxx --id 线索ID
  python3 delete_lead.py --api https://xxx.com --token xxx --count 5"""
import requests,argparse,time

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api",required=True); p.add_argument("--token",required=True)
    p.add_argument("--id",type=int,default=0); p.add_argument("--count",type=int,default=0)
    a=p.parse_args()
    api=a.api.rstrip("/"); H={"Authorization":f"Token token={a.token}"}; v2=f"{api}/api/v2"
    if a.id:
        r=requests.delete(f"{v2}/leads/{a.id}",headers=H)
        res=r.json()
        if res.get("code")==0:
            v=requests.get(f"{v2}/leads/{a.id}",headers=H)
            ok=v.json().get("code")!=0
            print(f"✅ 删除成功! ID:{a.id} 验证:{'✓已删除' if ok else '⚠️仍存在'}")
        else: print(f"✗ {res.get('message')}")
        return
    if a.count:
        deleted=0; page=1
        while deleted<a.count:
            r=requests.get(f"{v2}/leads?per_page=50&sort=created_at&order=asc&page={page}",headers=H)
            leads=r.json().get("data",{}).get("leads",[])
            if not leads: break
            for c in leads:
                if deleted>=a.count: break
                cid=c["id"]
                dr=requests.delete(f"{v2}/leads/{cid}",headers=H)
                if dr.json().get("code")==0:
                    vr=requests.get(f"{v2}/leads/{cid}",headers=H)
                    vok=vr.json().get("code")!=0
                    deleted+=1
                    print(f"  ✓ [{deleted}/{a.count}] ID:{cid} {c.get('name')} 验证:{'✓' if vok else '⚠️'}")
                else: print(f"  ○ 跳过 ID:{cid}: {dr.json().get('message')}")
            page+=1; time.sleep(0.2)
        print(f"\n完成! 删除 {deleted} 条")
    else:
        print("用法: --id 删除指定 | --count 批量删除最早N条")

if __name__=="__main__": main()
