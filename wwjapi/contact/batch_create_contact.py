#!/usr/bin/env python3
"""批量创建联系人 - 关联客户
使用: python3 batch_create_contact.py --api https://域名 --token xxx [数量]"""
import json,random,string,argparse,time,subprocess
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import create_entity
import requests

def v2curl(api,token,path,method='GET',data=None):
    a=api.rstrip('/')
    c=['curl','-s','-k','-X',method,'-H','Content-Type: application/json','-H','Authorization: Token token='+token]
    if data: c+=['-d',json.dumps(data)]
    c+=[a+'/api/v2/'+path.lstrip('/')]
    raw=subprocess.run(c,capture_output=True,timeout=30).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def pcurl(api,token,path):
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.').replace('//lxcrm.','//lxcrm-api.')
    raw=subprocess.run(['curl','-s','-k','-H','Authorization: Token token='+token,pc+'/api/pc/'+path.lstrip('/')],capture_output=True,timeout=15).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def discover(api,token):
    i={'fm':{},'fd':{},'op':{},'cs':[],'pc_users':[],'dp':[]}
    # 系统字段(联系人角色)
    fm=v2curl(api,token,'field_maps/contact')
    for f in fm.get('data',{}).get('contact',[]):
        if f['field_name']=='category':
            i['fm']['category']=[str(v['id']) for v in f.get('field_values',[]) if v.get('status')=='enable']
    # 自定义字段
    cf=pcurl(api,token,'custom_fields?model_klass=Contact')
    tm={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'tx','text_area':'tx',
        'number_field':'nu','currency_field':'nu','email_field':'em','mobile_field':'mb','url_field':'ur',
        'datetime_field':'dt','user_field':'us','multi_user_field':'mu','department_field':'dp',
        'multi_department_field':'md','custom_relation_field':'rl'}
    ex={'name','customer','department','job','category','gender','birth_date','note'}
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); t=f.get('field_type',''); fid=f.get('field_id')
            if n in ex or n.startswith('address.') or n.startswith('subform_') or n.startswith('file_asset'): continue
            st=tm.get(t,'tx')
            i['fd'][st]=i['fd'].get(st,[])+[{'name':n,'fid':fid,'label':f.get('label','')}]
    # 选项值
    for st in ['sel','ms','cas']:
        for f in i['fd'].get(st,[]):
            if f['fid']:
                d=pcurl(api,token,'custom_fields/'+str(f['fid']))
                os_=d.get('data',{}).get('options',{}).get('select_options',[])
                vs=[]
                for o in os_:
                    if isinstance(o,list) and len(o)==2: vs.append(o[1])
                    elif isinstance(o,dict): vs.append(o.get('value',''))
                vs=[x for x in vs if x]
                if vs: i['op'][f['name']]=vs
    # 用户/部门/客户
    us=pcurl(api,token,'users?page=1&per_page=50')
    if us.get('code')==0:
        ud=us.get('data',{}); pu=ud.get('users',ud.get('list',[]))
        if pu: i['pc_users']=[u['id'] for u in pu if u.get('id')]
    dp=v2curl(api,token,'departments')
    i['dp']=[x['id'] for x in dp.get('data',{}).get('departments',[]) if x.get('id')]
    cl=v2curl(api,token,'customers?per_page=50&sort=created_at&order=desc')
    i['cs']=[str(c['id']) for c in cl.get('data',{}).get('customers',[]) if c.get('id')]
    return i

rp=lambda: random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
re=lambda: ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
ru=lambda: 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
rt=lambda: ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
ri=lambda: random.randint(10000,99999); rd=lambda: round(random.uniform(100,99999),2)
rf=lambda: (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')

def fill_fields(c,i):
    for kf in ['tx','em','mb','ur']:
        fn={'tx':rt,'em':re,'mb':rp,'ur':ru}
        for f in i['fd'].get(kf,[]): c[f['name']]=fn[kf]()
    for f in i['fd'].get('nu',[]): c[f['name']]=rd() if '金额' in f.get('label','') or '币' in f.get('label','') else ri()
    for f in i['fd'].get('dt',[]): c[f['name']]=rf()
    for f in i['fd'].get('sel',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in i['fd'].get('ms',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.sample(o,random.randint(2,min(4,len(o)))) if o else None
    for f in i['fd'].get('cas',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    if i['pc_users']:
        for f in i['fd'].get('us',[]): c[f['name']]=random.sample(i['pc_users'],1)
        for f in i['fd'].get('mu',[]): c[f['name']]=random.sample(i['pc_users'],min(3,len(i['pc_users'])))
    if i['dp']:
        for f in i['fd'].get('dp',[]): c[f['name']]=random.sample(i['dp'],1)
        for f in i['fd'].get('md',[]): c[f['name']]=random.sample(i['dp'],min(2,len(i['dp'])))
    for f in i['fd'].get('rl',[]): c[f['name']]=str(random.choice(['7','13']))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('--env', choices=['test','staging','production'])
    p.add_argument('--profile', choices=['gray','standard'])
    p.add_argument('cnt',nargs='?',type=int,default=1); p.add_argument('--delay',type=float,default=0.3)
    p.add_argument("--attachment-dir",help="本地图片目录,上传到文件字段")
    a=apply_config_defaults(p.parse_args(), p); api=a.api.rstrip('/')
    print(f"\n{'='*60}\n联系人\nAPI: {api} 数量: {a.cnt}\n{'='*60}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    try:
        i=discover(api,a.token)
        print(f'  客户:{len(i["cs"])} 用户:{len(i["pc_users"])} 部门:{len(i["dp"])}')
    except Exception as e: print(f'失败: {e}'); return

    ok=fail=0
    for n in range(1,a.cnt+1):
        try:
            cid=int(random.choice(i['cs'])) if i['cs'] else None
            contact={'name':'联系人-'+rt()[:6],'customer_id':cid,
                'department':random.choice(['研发部','产品部','销售部','市场部','财务部']),
                'job':random.choice(['经理','总监','主管','工程师','销售']),
                'category':random.choice(i['fm'].get('category',['2103262'])),
                'note':'联系人-'+rt()[:6],
                'birth_date':rf()[:7]+'-01',
                'gender':random.choice(['male','female']),
                'address_attributes':{'phone':rp(),'tel':'0519-'+str(random.randint(10000000,99999999)),
                    'email':re(),'wechat':rp(),'qq':str(random.randint(10000000,999999999)),
                    'wangwang':rp(),'url':ru(),'zip':'5180'+str(random.randint(10,99)),
                    'province_id':random.choice([1,10,13,21]),
                    'detail_address':random.choice(['科技路','创新路','发展大道'])+str(random.randint(1,999))+'号'}}
            fill_fields(contact,i)
            if a.attachment_dir:
                res,nfiles = create_entity(api, a.token, "Contact", contact, a.attachment_dir)
                if res.get('code')==0:
                    ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{res['data']['id']} 文件:{nfiles}个")
                else:
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
            else:
                res=v2curl(api,a.token,'contacts','POST',{'contact':contact})
                if res.get('code')==0:
                    ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{res['data']['id']} 客户:{cid} {contact['name']}")
                else:
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
        except Exception as e: fail+=1;print(f"  ✗ [{n}/{a.cnt}] {e}")
        if n<a.cnt and a.delay>0: time.sleep(a.delay)
    print(f'\n完成! 成功:{ok} 失败:{fail}')

if __name__=='__main__': main()
