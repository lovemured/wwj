#!/usr/bin/env python3
"""批量创建产品 - 支持任意CRM环境(含自定义字段)
使用: python3 batch_create_product.py [数量]"""
import requests,json,random,string,sys,argparse,time,os
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import process_file_fields, pc_url

def fetch(api,path,token,pc=False):
    base=api.rstrip('/')+('/api/pc' if pc else '/api/v2')
    r=requests.get(f"{base}/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15)
    return r.json()

def pcurl(api,token,path):
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.').replace('//lxcrm.','//lxcrm-api.')
    r=requests.get(f"{pc}/api/pc/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15)
    return r.json()

def discover(api,token):
    info={'categories':[],'custom_fields':[],'users':[],'departments':[],'select_opts':{},'fields':{'file':[]}}
    cat=fetch(api,'product_categories',token)
    info['categories']=[str(c['id']) for c in cat.get('data',{}).get('products',[]) if c.get('id')]
    us=pcurl(api,token,'users?page=1&per_page=50')
    info['users']=[u['uid'] for u in us.get('data',{}).get('list',[]) if u.get('uid')]
    dp=pcurl(api,token,'departments')
    info['departments']=[d['id'] for d in dp.get('data',{}).get('joined_departments',[]) if d.get('id')]
    # 已手动处理的系统字段名
    builtin={'name','product_no','standard_unit_price','sale_unit','introduction','unit_cost','product_category_id','attachment_id'}
    cf=pcurl(api,token,'custom_fields?model_klass=Product')
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            ft=f.get('field_type','')
            fid=f.get('field_id')
            name=f.get('name','')
            if not fid or not name: continue
            if name in builtin: continue
            if ft in ('subform_field',): continue
            if ft in ('file_field','file_type'): info['fields']['file'].append({'name':name,'label':f.get('label','')}); continue
            info['custom_fields'].append({'field_id':fid,'name':name,'type':ft,'label':f.get('label','')})
            if ft in ('select','multi_select','nested_select_field'):
                if name not in info['select_opts']:
                    d=pcurl(api,token,f'custom_fields/{fid}')
                    opts=d.get('data',{}).get('input_field_options',{}).get('collection_options',[])
                    vals=[o['value'] for o in opts if o.get('value') and o.get('value')!='']
                    if vals: info['select_opts'][name]=vals
    return info

NAMES=['智能办公椅','便携投影仪','无线蓝牙耳机','机械键盘','USB-C扩展坞','4K显示器','人体工学鼠标','笔记本支架','降噪耳麦','桌面充电站']
UNITS=['个','台','套','箱','只','条','把','件']
def rn(): return random.choice(NAMES)+'-'+''.join(random.choices(string.ascii_uppercase+string.digits,k=4))
def rp(): return 'PROD-'+''.join(random.choices(string.digits,k=8))
def rp2(): return round(random.uniform(10,9999),2)
def rph(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def rem(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def rurl(): return 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
def rdt(): return (datetime.now()+timedelta(days=random.randint(-30,30))).strftime('%Y-%m-%dT%H:%M:%S+08:00')
def rdate(): return (datetime.now()+timedelta(days=random.randint(-30,30))).strftime('%Y-%m-%d')

def gen_custom_value(field,info):
    ft=field['type']; name=field['name']
    if ft=='text_field': return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(4,12)))
    if ft=='text_area': return '自定义文本-'+''.join(random.choices(string.ascii_letters,k=8))
    if ft=='number_field': return random.randint(1,9999)
    if ft=='currency_field': return round(random.uniform(10,9999),2)
    if ft=='email_field': return rem()
    if ft=='mobile_field': return rph()
    if ft=='url_field': return rurl()
    if ft=='datetime_field': return random.choice([rdt(),rdate()])
    if ft=='select':
        opts=info['select_opts'].get(name,[])
        return random.choice(opts) if opts else ''
    if ft=='multi_select':
        opts=info['select_opts'].get(name,[])
        return random.sample(opts,min(random.randint(1,3),len(opts))) if opts else []
    if ft=='nested_select_field':
        opts=info['select_opts'].get(name,[])
        return random.choice(opts) if opts else ''
    if ft in ('department_field','multi_department_field'):
        depts=info['departments']
        count=2 if ft=='multi_department_field' else 1
        return random.sample(depts,min(count,len(depts))) if depts else []
    if ft in ('user_field','multi_user_field'):
        users=info['users']
        count=2 if ft=='multi_user_field' else 1
        return random.sample(users,min(count,len(users))) if users else []
    return ''

def main():
    p=argparse.ArgumentParser(description='批量创建产品(含自定义字段)')
    p.add_argument('--api')
    p.add_argument('--token')
    p.add_argument('--env', choices=['test','staging','production'])
    p.add_argument('cnt',nargs='?',type=int,default=1)
    p.add_argument('--attachment-dir',help='本地附件目录,随机取图片上传到文件字段')
    a=apply_config_defaults(p.parse_args(), p)
    api=a.api.rstrip('/'); token=a.token
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print('发现字段定义...')
    info=discover(api,token)
    print(f'  产品分类:{len(info["categories"])} 用户:{len(info["users"])} 部门:{len(info["departments"])}')
    print(f'  自定义字段:{len(info["custom_fields"])}个')
    print(f'  文件字段:{len(info["fields"]["file"])}')
    for cf in info['custom_fields']:
        print(f'    {cf["name"]} ({cf["label"]}) [{cf["type"]}]')
    created=0
    for i in range(a.cnt):
        cat_id=random.choice(info['categories']) if info['categories'] else None
        data={'product':{
            'name':rn(),'product_no':rp(),'standard_unit_price':rp2(),
            'sale_unit':random.choice(UNITS),'introduction':f'产品介绍-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'unit_cost':rp2(),
        }}
        if cat_id: data['product']['product_category_id']=int(cat_id)
        for cf in info['custom_fields']:
            val=gen_custom_value(cf,info)
            if val is not None and val != '' and val != []:
                data['product'][cf['name']]=val
        nfiles=len(process_file_fields(api,token,'Product',data['product'],a.attachment_dir))
        pc=bool(info['fields']['file'] and nfiles)
        url=pc_url(api)+'/api/pc/products' if pc else f'{api}/api/v2/products'
        r=requests.post(url,headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},json=data)
        res=r.json()
        if res.get('code')==0:
            pid=res.get('data',{}).get('id')
            created+=1; print(f"  ✓ [{created}/{a.cnt}] 产品ID:{pid} {data['product']['name']} 附件:{nfiles}")
        else:
            print(f"  ✗ {res.get('message','?')}")
        time.sleep(0.3)
    print(f"\n完成! 创建 {created} 个产品")

if __name__=='__main__': main()
