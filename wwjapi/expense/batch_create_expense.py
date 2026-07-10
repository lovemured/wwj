#!/usr/bin/env python3
"""批量创建费用+报销单 - 关联客户合同
使用: python3 batch_create_expense.py --api https://域名 --token xxx [数量] [类型]
  type: expense(费用)  expense_account(报销单)
"""
import json,random,string,argparse,time,subprocess
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import create_entity
import requests

def pcurl(api,token,path,method='GET',data=None):
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.')
    c=['curl','-s','-k','-X',method,'-H','Content-Type: application/json','-H','Authorization: Token token='+token]
    if data: c+=['-d',json.dumps(data)]
    c+=[pc+'/api/pc/'+path.lstrip('/')]
    raw=subprocess.run(c,capture_output=True,timeout=60).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def v2curl(api,token,path,method='GET',data=None):
    a=api.rstrip('/')
    c=['curl','-s','-k','-X',method,'-H','Content-Type: application/json','-H','Authorization: Token token='+token]
    if data: c+=['-d',json.dumps(data)]
    c+=[a+'/api/v2/'+path.lstrip('/')]
    raw=subprocess.run(c,capture_output=True,timeout=60).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def discover(api,token):
    i={'fm':{},'pc_users':[],'contracts':[],'cs':[],'dp':[],'fd_e':{},'fd_ea':{},'op':{}}
    # 用户
    us=pcurl(api,token,'users?page=1&per_page=50')
    if us.get('code')==0:
        ud=us.get('data',{}); pu=ud.get('users',ud.get('list',[]))
        if pu: i['pc_users']=[u['id'] for u in pu if u.get('id')]
    # 合同+客户
    cl=v2curl(api,token,'contracts?per_page=50&sort=created_at&order=desc')
    ct_list=cl.get('data',{}).get('list',cl.get('data',{}).get('contracts',[]))
    i['contracts']=[{'id':c['id'],'title':c.get('title',''),'customer_id':c.get('customer_id')} for c in ct_list if c.get('id')]
    cl2=v2curl(api,token,'customers?per_page=50&sort=created_at&order=desc')
    i['cs']=[c['id'] for c in cl2.get('data',{}).get('customers',[]) if c.get('id')]
    dp=v2curl(api,token,'departments')
    i['dp']=[x['id'] for x in dp.get('data',{}).get('departments',[]) if x.get('id')]
    # 费用类型(从现有费用获取类别或使用已知ID)
    i['fm']['category']=['2103306','2103338','2103307','2103308','2103309','2103310','2103311','2103312','2103313']
    # 自定义字段
    tm={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'tx','text_area':'tx',
        'number_field':'nu','currency_field':'nu','email_field':'em','mobile_field':'mb','url_field':'ur',
        'datetime_field':'dt','user_field':'us','multi_user_field':'mu','department_field':'dp',
        'multi_department_field':'md','custom_relation_field':'rl'}
    ex={'description','amount','incurred_at','customer','contacts_expenses','related_item','revisit_log','checkin','attachments','note','user','owned_department','sn','category'}
    for klass,pfx,fd in [('Expense','e',i['fd_e']),('ExpenseAccount','ea',i['fd_ea'])]:
        cf=pcurl(api,token,'custom_fields?model_klass='+klass)
        if not cf.get('data'): continue
        for g in cf.get('data',{}).get('custom_field_groups',[]):
            for f in g.get('custom_fields',[]):
                n=f.get('name',''); t=f.get('field_type',''); fid=f.get('field_id')
                if n in ex or n.startswith('subform_') or n.startswith('file_asset'): continue
                st=tm.get(t,'tx'); key=pfx+'_'+st
                fd[key]=fd.get(key,[])+[{'name':n,'fid':fid,'label':f.get('label','')}]
    # 选项值
    for fd in [i['fd_e'],i['fd_ea']]:
        for k in list(fd.keys()):
            if '_sel' in k or '_ms' in k or '_cas' in k:
                for f in fd[k]:
                    if f['fid']:
                        d=pcurl(api,token,'custom_fields/'+str(f['fid']))
                        os_=d.get('data',{}).get('options',{}).get('select_options',[])
                        vs=[]
                        for o in os_:
                            if isinstance(o,list) and len(o)==2: vs.append(o[1])
                            elif isinstance(o,dict): vs.append(o.get('value',''))
                        vs=[x for x in vs if x]
                        if vs: i['op'][f['name']]=vs
    return i

rp=lambda: random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
re=lambda: ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
ru=lambda: 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
rt=lambda: ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
ri=lambda: random.randint(10000,99999); rd=lambda: round(random.uniform(100,99999),2)
rf=lambda: (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')

def pick_contract(i):
    if i['contracts']:
        ct=random.choice(i['contracts'])
        return ct['id'],ct.get('customer_id',i['cs'][0] if i['cs'] else None),ct['title']
    return None,random.choice(i['cs']) if i['cs'] else None,''

def fill_fields(c,i,fd,pfx):
    for kf in ['tx','em','mb','ur']:
        fn={'tx':rt,'em':re,'mb':rp,'ur':ru}
        for f in fd.get(pfx+'_'+kf,[]): c[f['name']]=fn[kf]()
    for f in fd.get(pfx+'_nu',[]): c[f['name']]=rd() if '金额' in f.get('label','') or '币' in f.get('label','') else ri()
    for f in fd.get(pfx+'_dt',[]): c[f['name']]=rf()
    for f in fd.get(pfx+'_sel',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in fd.get(pfx+'_ms',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.sample(o,random.randint(2,min(4,len(o)))) if o else None
    for f in fd.get(pfx+'_cas',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    if i['pc_users']:
        for f in fd.get(pfx+'_us',[]): c[f['name']]=random.sample(i['pc_users'],1)
        for f in fd.get(pfx+'_mu',[]): c[f['name']]=random.sample(i['pc_users'],min(3,len(i['pc_users'])))
    if i['dp']:
        for f in fd.get(pfx+'_dp',[]): c[f['name']]=random.sample(i['dp'],1)
        for f in fd.get(pfx+'_md',[]): c[f['name']]=random.sample(i['dp'],min(2,len(i['dp'])))
    for f in fd.get(pfx+'_rl',[]): c[f['name']]=str(random.choice(['7','13']))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('cnt',nargs='?',type=int,default=1); p.add_argument('--delay',type=float,default=0.5)
    p.add_argument('--type',choices=['expense','expense_account'],default='expense')
    p.add_argument("--attachment-dir",help="本地图片目录,上传到文件字段")
    a=apply_config_defaults(p.parse_args(), p); api=a.api.rstrip('/')
    names={'expense':'费用','expense_account':'报销单'}
    print(f"\n{'='*60}\n{names[a.type]}\nAPI: {api} 数量: {a.cnt}\n{'='*60}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    try:
        i=discover(api,a.token)
        print(f'  合同:{len(i["contracts"])} 客户:{len(i["cs"])} 用户:{len(i["pc_users"])} 部门:{len(i["dp"])}')
    except Exception as e: print(f'失败: {e}'); import traceback; traceback.print_exc(); return

    ok=fail=0
    for n in range(1,a.cnt+1):
        try:
            ct_id,cust_id,ct_title=pick_contract(i)
            if a.type=='expense':
                desc=random.choice(['交通费','办公用品费','餐饮费','通讯费','差旅费','培训费'])
                exp={'sn':'FE'+str(int(time.time()*1000))[-8:],'description':desc+'-'+rt()[:6],'amount':round(random.uniform(100,999),2),
                     'incurred_at':rf(),'customer_id':cust_id,
                     'category':desc,
                     'related_item_type':'Contract' if ct_id else '','related_item_id':ct_id}
                fill_fields(exp,i,i['fd_e'],'e')
                if a.attachment_dir:
                    res,nfiles = create_entity(api, a.token, "Expense", exp, a.attachment_dir)
                    if res.get('code')==0:
                        ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{res['data']['id']} 金额:{exp['amount']} 文件:{nfiles}个")
                    else:
                        fail+=1;print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
                else:
                    res=v2curl(api,a.token,'expenses','POST',{'expense':exp})
                    if res.get('code')==0:
                        ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{res['data']['id']} 金额:{exp['amount']} {desc}")
                    else:
                        fail+=1;print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
            elif a.type=='expense_account':
                ea={'sn':'BX'+str(int(time.time()*1000))[-8:],'amount':round(random.uniform(100,999),2),'note':'报销-'+rt()[:6],
                    'owned_department_id':int(random.choice(i['dp'])) if i['dp'] else None,
                    'user_id':int(random.choice(i['pc_users'])) if i['pc_users'] else None}
                fill_fields(ea,i,i['fd_ea'],'ea')
                res=pcurl(api,a.token,'expense_accounts','POST',{'expense_account':ea})
                if res.get('code')==0:
                    ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{res['data']['id']} 金额:{ea['amount']}")
                else:
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
        except Exception as e: fail+=1;print(f"  ✗ [{n}/{a.cnt}] {e}")
        if n<a.cnt and a.delay>0: time.sleep(a.delay)
    print(f'\n完成! 成功:{ok} 失败:{fail}')

if __name__=='__main__': main()
