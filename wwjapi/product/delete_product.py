#!/usr/bin/env python3
"""删除产品 - 优先删除最早创建的
使用:
  python3 delete_product.py --id 产品ID
  python3 delete_product.py --count 5"""
import requests,argparse,time,os,json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def main():
    cfg=load_config()
    p=argparse.ArgumentParser(description='删除产品')
    p.add_argument('--api',default=cfg.get('api','')); p.add_argument('--token',default=cfg.get('token',''))
    p.add_argument('--id',type=int,default=0); p.add_argument('--count',type=int,default=0)
    a=p.parse_args()
    if not a.api or not a.token: p.error('请在config.json中配置api和token，或通过--api/--token传入')
    api=a.api.rstrip('/'); H={'Authorization':f'Token token={a.token}'}; v2=f'{api}/api/v2'
    if a.id:
        r=requests.delete(f'{v2}/products/{a.id}',headers=H)
        res=r.json()
        if res.get('code')==0:
            v=requests.get(f'{v2}/products/{a.id}',headers=H)
            ok=v.json().get('code')!=0
            print(f"✅ 删除成功! ID:{a.id} 验证:{'✓已删除' if ok else '⚠️仍存在'}")
        else: print(f"✗ {res.get('message')}")
        return
    if a.count:
        deleted=0; page=1
        while deleted<a.count:
            r=requests.get(f'{v2}/products?per_page=50&sort=created_at&order=asc&page={page}',headers=H)
            items=r.json().get('data',{}).get('products',[])
            if not items: break
            for c in items:
                if deleted>=a.count: break; pid=c['id']
                dr=requests.delete(f'{v2}/products/{pid}',headers=H)
                if dr.json().get('code')==0: deleted+=1; print(f"  ✓ [{deleted}/{a.count}] ID:{pid}")
                else: print(f"  ○ {dr.json().get('message')}")
            page+=1; time.sleep(0.2)
        print(f"\n完成! 删除 {deleted} 条")

if __name__=='__main__': main()
