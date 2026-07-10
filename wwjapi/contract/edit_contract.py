#!/usr/bin/env python3
"""编辑合同 - 所有字段值不能和编辑前一样"""
import requests,json,random,string,argparse
from datetime import datetime,timedelta
def fetch(api,path,token,pc=False):
    base=api.rstrip('/')+('/api/pc' if pc else '/api/v2')
    return requests.get(f"{base}/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15).json()
def choose_diff(opts,old): candidates=[o for o in opts if o!=old]; return random.choice(candidates) if candidates else old
def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def re(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def ru(): return 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--api',required=True); p.add_argument('--token',required=True); p.add_argument('--id',required=True,type=int)
    a=p.parse_args(); api=a.api.rstrip('/'); token=a.token
    r=requests.get(f"{api}/api/v2/contracts/{a.id}",headers={'Authorization':f'Token token={token}'})
    old=r.json().get('data',{}); 
    if not old.get('id'): print('合同不存在'); return
    cf=fetch(api,'custom_fields?model_klass=Contract',token,pc=True)
    info={'fields':{},'opts':{}}
    ft_map={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'txt','text_area':'txt','number_field':'num','currency_field':'num','email_field':'eml','mobile_field':'mob','url_field':'url','datetime_field':'dt','user_field':'usr','multi_user_field':'m_usr','department_field':'dept','multi_department_field':'m_dept','custom_relation_field':'rel'}
    for t in ft_map.values(): info['fields'][t]=[]
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); ft=f.get('field_type',''); fid=f.get('field_id');
            if n in ['title','sn','product_assets','total_amount','sign_date','start_at','end_at','contact_assetships','checking_payments_amount','received_payments_amount','unreceived_amount','unchecking_payments_amount','status','category','payment_type','customer_signer','our_signer','attachments','revisit_remind_at','received_payment_plans','special_terms']: continue
            if n.startswith('subform_') or n.startswith('file_asset'): continue
            t=ft_map.get(ft,'txt'); info['fields'][t].append({'name':n,'label':f.get('label',''),'fid':fid})
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
    fm=fetch(api,'field_maps/contract',token)
    info['fm_opts']={}
    for f in fm.get('data',{}).get('contract',[]):
        vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
        if vals: info['fm_opts'][f['field_name']]=[str(v['id']) for v in vals]
    us=fetch(api,'user/simple_list?per_page=50',token); info['users']=[u['value'] for u in us.get('simple_users',[]) if u.get('value') and u.get('value')!='']
    dp=fetch(api,'departments',token); info['depts']=[str(d['id']) for d in dp.get('data',{}).get('departments',[]) if d.get('id')]
    cl=fetch(api,'customers?per_page=50&sort=created_at&order=desc',token); info['customers']=[str(c['id']) for c in cl.get('data',{}).get('customers',[]) if c.get('id')]
    data={}
    for fk in ['status','category','payment_type']:
        opts=info['fm_opts'].get(fk,[]); data[fk]=choose_diff(opts,str(old.get(fk,'')))
    old_cid=str(old.get('customer_id',''))
    cand_c=[c for c in info['customers'] if c!=old_cid]
    if cand_c: data['customer_id']=int(random.choice(cand_c))
    data['title']='合同-'+rt(); data['sn']='HT'+rt()
    data['sign_date']=rf(); data['start_at']=rf(); data['end_at']=rf()
    data['total_amount']=rd(); data['checking_payments_amount']=rd(); data['received_payments_amount']=rd()
    data['unreceived_amount']=rd(); data['unchecking_payments_amount']=rd()
    data['customer_signer']=rt()[:4]; data['our_signer']=rt()[:4]
    old_rt=old.get('revisit_remind_at','')
    while True:
        new_rt=(datetime.now()+timedelta(days=random.randint(1,14))).strftime('%Y-%m-%d %H:%M')
        if new_rt!=old_rt: break
    data['revisit_remind_at']=new_rt
    for f in info['fields']['txt']: data[f['name']]=rt()
    for f in info['fields']['eml']: data[f['name']]=re()
    for f in info['fields']['mob']: data[f['name']]=rp()
    for f in info['fields']['url']: data[f['name']]=ru()
    for f in info['fields']['num']: data[f['name']]=rd() if '金额' in f['label'] else ri()
    for f in info['fields']['dt']: data[f['name']]=rf()
    for f in info['fields']['sel']:
        opts=info['opts'].get(f['name'],[]); data[f['name']]=choose_diff(opts,old.get(f['name'],''))
    for f in info['fields']['ms']:
        opts=info['opts'].get(f['name'],[]); old_v=old.get(f['name'],[])
        cand=[o for o in opts if o not in old_v]
        data[f['name']]=cand[:min(2,len(cand))] if cand else opts[:min(2,len(opts))]
    for f in info['fields']['cas']:
        opts=info['opts'].get(f['name'],[]); data[f['name']]=choose_diff(opts,old.get(f['name'],''))
    if info['users']:
        for f in info['fields']['usr']:
            old_v=set(old.get(f['name'],[]) or []); cand=[u for u in info['users'] if u not in old_v]
            if cand: data[f['name']]=random.sample(cand,1)
        for f in info['fields']['m_usr']:
            old_v=set(old.get(f['name'],[]) or []); cand=[u for u in info['users'] if u not in old_v]
            if cand: data[f['name']]=random.sample(cand,min(3,len(cand)))
    if info['depts']:
        for f in info['fields']['dept']:
            old_v=set(old.get(f['name'],[]) or []); cand=[d for d in info['depts'] if d not in old_v]
            if cand: data[f['name']]=random.sample(cand,1)
        for f in info['fields']['m_dept']:
            old_v=set(old.get(f['name'],[]) or []); cand=[d for d in info['depts'] if d not in old_v]
            if len(cand)>=2: data[f['name']]=random.sample(cand,2)
    for f in info['fields']['rel']: data[f['name']]=str(random.choice(['7','13']))
    r=requests.put(f"{api}/api/v2/contracts/{a.id}",headers={'Content-Type':'application/json','Authorization':f'Token token={token}'},json={'contract':data})
    res=r.json()
    if res.get('code')==0: print(f'✅ 编辑成功!')
    else: print(f"✗ {res.get('message','?')}")
if __name__=='__main__': main()
