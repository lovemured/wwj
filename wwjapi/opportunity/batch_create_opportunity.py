#!/usr/bin/env python3
"""批量创建商机 - 支持任意CRM环境(使用已有客户ID)
使用: python3 batch_create_opportunity.py --api https://域名 --token xxx [数量]"""
import requests,json,random,string,sys,argparse,time
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import process_file_fields, pc_url, upload_attach_files

def fetch(api,path,token,pc=False):
    base=api.rstrip('/')+('/api/pc' if pc else '/api/v2')
    return requests.get(f"{base}/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15).json()

def discover(api,token):
    info={'fm':{},'fields':{'sel':[],'ms':[],'cas':[],'txt':[],'num':[],'eml':[],'mob':[],'url':[],'dt':[],'usr':[],'m_usr':[],'dept':[],'m_dept':[],'rel':[],'file':[]},'opts':{}}
    # 系统字段
    fm=fetch(api,'field_maps/opportunity',token)
    for f in fm.get('data',{}).get('opportunity',[]):
        vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
        if vals: info['fm'][f['field_name']]=[str(v['id']) for v in vals]
    # 自定义字段
    cf=fetch(api,'custom_fields?model_klass=Opportunity',token,pc=True)
    ft_map={'select':'sel','multi_select':'ms','nested_select_field':'cas',
            'text_field':'txt','text_area':'txt','number_field':'num','currency_field':'num',
            'email_field':'eml','mobile_field':'mob','url_field':'url','datetime_field':'dt',
            'user_field':'usr','multi_user_field':'m_usr','department_field':'dept',
            'multi_department_field':'m_dept','custom_relation_field':'rel'}
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); ft=f.get('field_type',''); fid=f.get('field_id'); lb=f.get('label','')
            if n in ['title','customer','contact_assetships','product_assets','expect_amount','expect_sign_date','get_time','stage','kind','source','revisit_remind_at','note','attachments']: continue
            if n.startswith('subform_'): continue
            if n.startswith('file_asset'): info['fields']['file'].append({'name':n,'label':lb}); continue
            t=ft_map.get(ft,'txt'); info['fields'][t].append({'name':n,'label':lb,'fid':fid})
    # 选项
    for entry in info['fields']['sel']+info['fields']['ms']+info['fields']['cas']:
        fid=entry['fid']
        if not fid: continue
        detail=fetch(api,f'custom_fields/{fid}',token,pc=True)
        opts=detail.get('data',{}).get('options',{}).get('select_options',[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict): values.append(o.get('value',''))
        values=[v for v in values if v]
        if values: info['opts'][entry['name']]=values
    # 业务模板
    info['template_id']=1331
    for entry in info['fields']['sel']:
        fid=entry['fid']
        if fid:
            try:
                detail=fetch(api,f'custom_fields/{fid}',token,pc=True)
                for t in detail.get('data',{}).get('custom_field_templates',[]):
                    if t.get('status')=='enable':
                        info['template_id']=t['id']; break
            except: pass
            if info['template_id']!=1331: break
    # 用户/部门
    us=fetch(api,'user/simple_list?per_page=50',token)
    info['users']=[u['value'] for u in us.get('simple_users',[]) if u.get('value') and u.get('value')!='']
    dp=fetch(api,'departments',token)
    info['depts']=[str(d['id']) for d in dp.get('data',{}).get('departments',[]) if d.get('id')]
    # 已有客户列表
    cl=fetch(api,'customers?per_page=50&sort=created_at&order=desc',token)
    info['customers']=[str(c['id']) for c in cl.get('data',{}).get('customers',[]) if c.get('id')]
    return info

def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def re(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def ru(): return 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')

def build(info):
    c={}
    # 系统字段
    c['custom_field_template_id']=info['template_id']
    for k,vals in info['fm'].items():
        if vals: c[k]=vals[0]
    c['revisit_remind_at']=(datetime.now()+timedelta(days=random.randint(1,14))).strftime('%Y-%m-%d %H:%M')
    c['expect_amount']=rd()
    c['expect_sign_date']=rf()
    c['get_time']=rf()
    # 客户(整数ID)
    if info['customers']: c['customer_id']=int(random.choice(info['customers']))
    for f in info['fields']['txt']: c[f['name']]=rt()
    for f in info['fields']['eml']: c[f['name']]=re()
    for f in info['fields']['mob']: c[f['name']]=rp()
    for f in info['fields']['url']: c[f['name']]=ru()
    for f in info['fields']['num']: c[f['name']]=rd() if '金额' in f['label'] or '币' in f['label'] else ri()
    for f in info['fields']['dt']: c[f['name']]=rf()
    for f in info['fields']['sel']:
        opts=info['opts'].get(f['name'],[])
        if opts: c[f['name']]=random.choice(opts)
    for f in info['fields']['ms']:
        opts=info['opts'].get(f['name'],[])
        if opts: c[f['name']]=random.sample(opts,random.randint(2,min(4,len(opts))))
    for f in info['fields']['cas']:
        opts=info['opts'].get(f['name'],[])
        if opts: c[f['name']]=random.choice(opts)
    if info['users']:
        for f in info['fields']['usr']: c[f['name']]=random.sample(info['users'],1)
        for f in info['fields']['m_usr']: c[f['name']]=random.sample(info['users'],min(3,len(info['users'])))
    if info['depts']:
        for f in info['fields']['dept']: c[f['name']]=random.sample(info['depts'],1)
        for f in info['fields']['m_dept']: c[f['name']]=random.sample(info['depts'],min(2,len(info['depts'])))
    for f in info['fields']['rel']: c[f['name']]=str(random.choice(['7','13']))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('count',nargs='?',type=int,default=1); p.add_argument('--delay',type=float,default=0.3)
    p.add_argument('--attachment-dir',help='本地附件目录,随机取图片上传到文件字段')
    a=apply_config_defaults(p.parse_args(), p)
    print(f"\n{'='*60}\nAPI: {a.api}\n数量: {a.count}\n{'='*60}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print('\n[1/2] 自动发现字段...')
    try: info=discover(a.api,a.token)
    except Exception as e: print(f'失败: {e}'); return
    print(f'  系统:{len(info["fm"])} 文本:{len(info["fields"]["txt"])} 邮箱:{len(info["fields"]["eml"])} 手机:{len(info["fields"]["mob"])}')
    print(f'  单选:{len(info["fields"]["sel"])} 多选:{len(info["fields"]["ms"])} 级联:{len(info["fields"]["cas"])}')
    print(f'  文件字段:{len(info["fields"]["file"])}')
    print(f'  已有客户:{len(info["customers"])} 用户:{len(info["users"])} 部门:{len(info["depts"])}')
    print(f'\n[2/2] 创建 {a.count} 条...')
    ok=fail=0
    for i in range(1,a.count+1):
        try:
            data=build(info)
            nfiles=len(process_file_fields(a.api,a.token,'Opportunity',data,a.attachment_dir))
            pc=bool(info['fields']['file'] and nfiles)
            url=pc_url(a.api)+'/api/pc/opportunities' if pc else f'{a.api}/api/v2/opportunities'
            data['title']=f'批量商机-{datetime.now().strftime("%H%M%S")}-{i}'
            data['note']=f'批量第{i}条'
            r=requests.post(url,
                headers={'Content-Type':'application/json','Authorization':f'Token token={a.token}'},
                json={'opportunity':data},timeout=30)
            res=r.json()
            if res.get('code')==0:
                lid=res['data']['id']
                nattach=upload_attach_files(a.api,a.token,'Opportunity',lid,a.attachment_dir)
                ok+=1;print(f"  ✓ [{i}/{a.count}] ID:{lid} 文件:{nfiles} 附件:{nattach}")
            else: fail+=1;print(f"  ✗ [{i}/{a.count}] {res.get('message','?')[:80]}")
        except Exception as e: fail+=1;print(f"  ✗ [{i}/{a.count}] {e}")
        if i<a.count and a.delay>0: time.sleep(a.delay)
    print(f'\n完成! 成功:{ok} 失败:{fail}')

if __name__=='__main__': main()
