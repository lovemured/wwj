#!/usr/bin/env python3
"""批量创建跟进记录 - 关联客户/线索/商机/合同(含自定义字段)
使用: python3 batch_create_revisit_log.py [数量] [类型]
  type: customer(默认) lead opportunity contract"""
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

def discover(api,token,entity_type):
    info={'entities':[],'custom_fields':[],'users':[],'departments':[],'select_opts':{},'fields':{'file':[]}}
    # 可关联实体
    v2_ep={'customer':'customers','lead':'leads','opportunity':'opportunities','contract':'contracts'}
    ep=v2_ep.get(entity_type,entity_type)
    r=fetch(api,f'{ep}?per_page=50&sort=created_at&order=desc',token)
    key=entity_type if entity_type in ['lead'] else ep
    items=r.get('data',{}).get(key,[]) or r.get('data',{}).get('list',[])
    info['entities']=[{'id':e['id'],'name':e.get('name','')} for e in items if e.get('id')]
    # 用户
    us=fetch(api,'user/simple_list',token)
    info['users']=[int(u['value']) for u in us.get('simple_users',[]) if u.get('value') and u.get('value')!='']
    # 部门
    dp=pcurl(api,token,'departments')
    info['departments']=[d['id'] for d in dp.get('data',{}).get('joined_departments',[]) if d.get('id')]
    # 自定义字段
    cf=pcurl(api,token,'custom_fields?model_klass=RevisitLog')
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            ft=f.get('field_type',''); fid=f.get('field_id'); name=f.get('name','')
            if not fid or not name: continue
            if ft in ('subform_field','field_map_field','date_field','email_field','url_field','nested_select_field','department_field','multi_department_field','multi_user_field'): continue
            if ft in ('file_field','file_type'): info['fields']['file'].append({'name':name,'label':f.get('label','')}); continue
            if f.get('category')=='common' and ft in ('text_area',): continue
            info['custom_fields'].append({'field_id':fid,'name':name,'type':ft,'label':f.get('label','')})
            if ft in ('select','multi_select','nested_select_field'):
                if name not in info['select_opts']:
                    d=pcurl(api,token,f'custom_fields/{fid}')
                    opts=d.get('data',{}).get('input_field_options',{}).get('collection_options',[])
                    vals=[o['value'] for o in opts if o.get('value') and o.get('value')!='']
                    if vals: info['select_opts'][name]=vals
    return info

CONTENTS=['电话沟通客户需求','发送产品资料','安排产品演示','跟进报价反馈','确认合同条款','客户回访','售后技术支持','节日问候','邀请参加活动','确认收货情况']
def rc(): return random.choice(CONTENTS)+'-'+''.join(random.choices(string.ascii_letters,k=4))
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
    p=argparse.ArgumentParser(description='批量创建跟进记录(含自定义字段)')
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('--env', choices=['test','staging','production'])
    p.add_argument('--profile', choices=['gray','standard'])
    p.add_argument('cnt',nargs='?',type=int,default=1)
    p.add_argument('entity_type',nargs='?',default='customer',help='customer/lead/opportunity/contract')
    p.add_argument('--attachment-dir',help='本地附件目录,随机取图片上传到文件字段')
    a=apply_config_defaults(p.parse_args(), p)
    api=a.api.rstrip('/'); token=a.token; et=a.entity_type
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print(f'发现字段定义 (关联类型: {et})...')
    info=discover(api,token,et)
    print(f'  可关联{et}: {len(info["entities"])} 个')
    print(f'  自定义字段:{len(info["custom_fields"])}个')
    print(f'  文件字段:{len(info["fields"]["file"])}')
    for cf in info['custom_fields']:
        print(f'    {cf["name"]} ({cf["label"]}) [{cf["type"]}]')
    if not info['entities']: print('没有可关联的实体'); return
    created=0
    for i in range(a.cnt):
        ent=random.choice(info['entities'])
        next_week=(datetime.now()+timedelta(days=7)).strftime('%Y-%m-%d %H:%M')
        data={'revisit_log':{
            'content':rc(),'loggable_id':ent['id'],
            'loggable_type':et.capitalize(),'loggable_name':ent.get('name',''),
            'remind_at':next_week,
        }}
        for cf in info['custom_fields']:
            val=gen_custom_value(cf,info)
            if val is not None and val != '' and val != []:
                data['revisit_log'][cf['name']]=val
        nfiles=len(process_file_fields(api,token,'RevisitLog',data['revisit_log'],a.attachment_dir))
        pc=bool(info['fields']['file'] and nfiles)
        url=pc_url(api)+'/api/pc/revisit_logs' if pc else f'{api}/api/v2/revisit_logs'
        r=requests.post(url,
            headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},json=data)
        res=r.json()
        if res.get('code')==0:
            rid=res.get('data',{}).get('id')
            created+=1; print(f"  ✓ [{created}/{a.cnt}] 跟进ID:{rid} -> {et}ID:{ent['id']} 附件:{nfiles}")
        else:
            print(f"  ✗ {res.get('message','?')}")
        time.sleep(0.3)
    print(f"\n完成! 创建 {created} 条跟进记录")

if __name__=='__main__': main()
