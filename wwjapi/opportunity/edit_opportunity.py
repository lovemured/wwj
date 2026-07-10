#!/usr/bin/env python3
"""编辑商机 - 所有字段值不能和编辑前一样
使用: python3 edit_opportunity.py --api https://域名 --token xxx --id 商机ID"""
import requests,json,random,string,argparse,time
from datetime import datetime,timedelta

def fetch(api,path,token,pc=False):
    base=api.rstrip('/')+('/api/pc' if pc else '/api/v2')
    return requests.get(f"{base}/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15).json()

def choose_diff(opts,old): return random.choice([o for o in opts if o!=old]) if [o for o in opts if o!=old] else old

ROADS=['科技路','创新路','发展大道','人民路','建设路','中山路','解放路','高新路','创业路']
def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def re(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def ru(): return 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api',required=True); p.add_argument('--token',required=True)
    p.add_argument('--id',required=True,type=int)
    a=p.parse_args()
    api=a.api.rstrip('/'); token=a.token

    print('读取当前商机值...')
    r=requests.get(f"{api}/api/v2/opportunities/{a.id}",headers={'Authorization':f'Token token={token}'})
    old=r.json().get('data',{})
    if not old.get('id'): print('商机不存在'); return

    print('自动发现字段选项...')
    cf=fetch(api,'custom_fields?model_klass=Opportunity',token,pc=True)
    info={'fields':{},'opts':{}}
    ft_map={'select':'sel','multi_select':'ms','nested_select_field':'cas',
            'text_field':'txt','text_area':'txt','number_field':'num','currency_field':'num',
            'email_field':'eml','mobile_field':'mob','url_field':'url','datetime_field':'dt',
            'user_field':'usr','multi_user_field':'m_usr','department_field':'dept',
            'multi_department_field':'m_dept','custom_relation_field':'rel'}
    for t in ft_map.values(): info['fields'][t]=[]
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); ft=f.get('field_type',''); fid=f.get('field_id'); lb=f.get('label','')
            if n in ['title','customer','contact_assetships','product_assets','expect_amount','expect_sign_date','get_time','stage','kind','source','revisit_remind_at','note','attachments']: continue
            if n.startswith('subform_') or n.startswith('file_asset'): continue
            t=ft_map.get(ft,'txt'); info['fields'][t].append({'name':n,'label':lb,'fid':fid})
    for entry in info['fields']['sel']+info['fields']['ms']+info['fields']['cas']:
        fid=entry['fid']
        if not fid: continue
        detail=fetch(api,f'custom_fields/{fid}',token,pc=True)
        opts=detail.get('data',{}).get('options',{}).get('select_options',[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict) and o.get('value'): values.append(o['value'])
        if values: info['opts'][entry['name']]=values
    # 系统字段
    fm=fetch(api,'field_maps/opportunity',token)
    info['fm_opts']={}
    for f in fm.get('data',{}).get('opportunity',[]):
        vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
        if vals: info['fm_opts'][f['field_name']]=[str(v['id']) for v in vals]

    us=fetch(api,'user/simple_list?per_page=50',token)
    info['users']=[u['value'] for u in us.get('simple_users',[]) if u.get('value') and u.get('value')!='']
    dp=fetch(api,'departments',token)
    info['depts']=[str(d['id']) for d in dp.get('data',{}).get('departments',[]) if d.get('id')]
    cl=fetch(api,'customers?per_page=50&sort=created_at&order=desc',token)
    info['customers']=[str(c['id']) for c in cl.get('data',{}).get('customers',[]) if c.get('id')]

    print('生成编辑后值...')
    data={}
    for fk in ['source','stage','kind']:
        opts=info['fm_opts'].get(fk,[]); old_v=str(old.get(fk,''))
        if opts: data[fk]=choose_diff(opts,old_v)
    # 客户换不同的
    old_cid=str(old.get('customer_id',''))
    cand_c=[c for c in info['customers'] if c!=old_cid]
    if cand_c: data['customer_id']=int(random.choice(cand_c))
    old_rt=old.get('revisit_remind_at','')
    while True:
        new_rt=(datetime.now()+timedelta(days=random.randint(1,14))).strftime('%Y-%m-%d %H:%M')
        if new_rt!=old_rt: break
    data['revisit_remind_at']=new_rt
    data['expect_amount']=rd()
    data['expect_sign_date']=rf(); data['get_time']=rf()

    for f in info['fields']['txt']+info['fields']['eml']+info['fields']['mob']+info['fields']['url']:
        data[f['name']]=rt()
    for f in info['fields']['eml']: data[f['name']]=re()
    for f in info['fields']['mob']: data[f['name']]=rp()
    for f in info['fields']['url']: data[f['name']]=ru()
    for f in info['fields']['num']: data[f['name']]=rd() if '金额' in f['label'] or '币' in f['label'] else ri()
    for f in info['fields']['dt']: data[f['name']]=rf()
    for f in info['fields']['sel']:
        opts=info['opts'].get(f['name'],[]); data[f['name']]=choose_diff(opts,old.get(f['name'],''))
    for f in info['fields']['ms']:
        opts=info['opts'].get(f['name'],[]); old_v=old.get(f['name'],[])
        if opts: data[f['name']]=[o for o in [random.choice(opts)] if o not in old_v] or [random.choice(opts)]
        else: data[f['name']]=random.sample(opts,min(2,len(opts))) if len(opts)>=2 else opts[:1]
    for f in info['fields']['cas']:
        opts=info['opts'].get(f['name'],[]); data[f['name']]=choose_diff(opts,old.get(f['name'],''))
    if info['users']:
        old_u=set(old.get('user_field_asset_f9d65e',[]) or [])
        cand=[u for u in info['users'] if u not in old_u]
        if cand: data['user_field_asset_f9d65e']=random.sample(cand,1)
        old_um=set(old.get('user_field_asset_89027b',[]) or [])
        cand_m=[u for u in info['users'] if u not in old_um]
        if cand_m: data['user_field_asset_89027b']=random.sample(cand_m,min(3,len(cand_m)))
    if info['depts']:
        for fname in ['user_field_asset_8ef24e','user_field_asset_258b11']:
            old_d=set(old.get(fname,[]) or [])
            cand_d=[d for d in info['depts'] if d not in old_d]
            n=1 if '8ef24e' in fname else 2
            if len(cand_d)>=n: data[fname]=random.sample(cand_d,n)

    print(f'编辑商机 ID:{a.id}...')
    r=requests.put(f"{api}/api/v2/opportunities/{a.id}",
        headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},
        json={'opportunity':data},timeout=30)
    res=r.json()
    if res.get('code')==0:
        print('✅ 编辑成功!')
        r2=requests.get(f"{api}/api/v2/opportunities/{a.id}",headers={'Authorization':f'Token token={token}'})
        new=r2.json().get('data',{})
        changed=sum(1 for k in ['source_mapped','stage_mapped','text_asset_b7afff'] if str(old.get(k,''))!=str(new.get(k,'')))
        print(f'  已变更: {changed}+ 个字段')
    else:
        print(f"✗ {res.get('message','?')}")

if __name__=='__main__': main()
