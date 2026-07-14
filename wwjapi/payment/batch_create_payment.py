#!/usr/bin/env python3
"""批量创建回款计划+回款记录+开票记录(含文件字段)
流程: 先创建回款计划 → 再创建回款记录(关联第一期次)
使用: python3 batch_create_payment.py --api https://域名 --token xxx [数量] [类型]
  type: received_payment(回款记录+计划)  invoiced_payment(开票记录)
"""
import json,random,string,argparse,time,subprocess,sys,os,requests
from datetime import datetime,timedelta
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import process_file_fields, pc_url

def pcurl(api,token,path,method='GET',data=None):
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.').replace('//lxcrm.','//lxcrm-api.')
    c=['curl','-s','-k','-X',method,'-H','Content-Type: application/json','-H','Authorization: Token token='+token]
    if data: c+=['-d',json.dumps(data)]
    c+=[pc+'/api/pc/'+path.lstrip('/')]
    raw=subprocess.run(c,capture_output=True,timeout=60).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def v2curl(api,token,path):
    c=['curl','-s','-k','-H','Authorization: Token token='+token,api.rstrip('/')+'/api/v2/'+path.lstrip('/')]
    raw=subprocess.run(c,capture_output=True,timeout=15).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def discover(api,token):
    i={'payment_type':[],'pc_users':[],'contracts':[],'cs':[],'dp':[],
       'fd':{'sel':[],'ms':[],'cas':[],'tx':[],'nu':[],'em':[],'mb':[],'ur':[],'dt':[],'us':[],'mu':[],'dp':[],'md':[],'rl':[]},
       'op':{},'fm':{}}
    # 付款方式
    pm=v2curl(api,token,'field_maps/contract')
    for f in pm.get('data',{}).get('contract',[]):
        if f['field_name']=='payment_type':
            i['payment_type']=[str(v['id']) for v in f.get('field_values',[]) if v.get('status')=='enable']
    # 回款类型
    rp=v2curl(api,token,'field_maps/received_payment')
    for f in rp.get('data',{}).get('received_payment',[]):
        i['fm'][f['field_name']]=[str(v['id']) for v in f.get('field_values',[]) if v.get('status')=='enable']
    # 开票类型
    ip=v2curl(api,token,'field_maps/invoiced_payment')
    for f in ip.get('data',{}).get('invoiced_payment',[]):
        i['fm'][f['field_name']]=[str(v['id']) for v in f.get('field_values',[]) if v.get('status')=='enable']
    # 用户
    us=pcurl(api,token,'users?page=1&per_page=50')
    if us.get('code')==0:
        ud=us.get('data',{}); pu=ud.get('users',ud.get('list',[]))
        if pu: i['pc_users']=[str(u['id']) for u in pu if u.get('id')]
    # 合同+客户
    cl=v2curl(api,token,'contracts?per_page=50&sort=created_at&order=desc')
    ct_list=cl.get('data',{}).get('list',cl.get('data',{}).get('contracts',[]))
    i['contracts']=[{'id':c['id'],'title':c.get('title',''),'customer_id':c.get('customer_id')} for c in ct_list if c.get('id')]
    cl2=v2curl(api,token,'customers?per_page=50&sort=created_at&order=desc')
    i['cs']=[str(c['id']) for c in cl2.get('data',{}).get('customers',[]) if c.get('id')]
    # 部门
    dp=v2curl(api,token,'departments')
    i['dp']=[str(x['id']) for x in dp.get('data',{}).get('departments',[]) if x.get('id')]
    # 自定义字段(回款记录/开票记录),含文件字段
    i['file_fields']={'rp':[],'ip':[]}
    for klass,pfx in [('ReceivedPayment','rp'),('InvoicedPayment','ip')]:
        cf=pcurl(api,token,'custom_fields?model_klass='+klass)
        for g in cf.get('data',{}).get('custom_field_groups',[]):
            for f in g.get('custom_fields',[]):
                n=f.get('name',''); t=f.get('field_type',''); fid=f.get('field_id')
                ex=['title','sn','product_assets','total_amount','sign_date','start_at','end_at','customer','contract',
                    'contact_assetships','received_payment_plan','receive_user','receive_date','amount','received_types',
                    'payment_type','note','attachments','broker_user','invoiced_date','invoice_types','invoice_no','content',
                    'plan_date','received_amount','invoice_amount','unreceived_amount']
                if n in ex or n.startswith('subform_'): continue
                if n.startswith('file_asset'):
                    i['file_fields'][pfx].append({'name':n,'label':f.get('label','')}); continue
                # 类型映射
                tm={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'tx','text_area':'tx',
                    'number_field':'nu','currency_field':'nu','email_field':'em','mobile_field':'mb','url_field':'ur',
                    'datetime_field':'dt','user_field':'us','multi_user_field':'mu','department_field':'dp',
                    'multi_department_field':'md','custom_relation_field':'rl'}
                st=tm.get(t,'tx')
                i['fd'][pfx+'_'+st]=i['fd'].get(pfx+'_'+st,[])+[{'name':n,'fid':fid,'label':f.get('label','')}]
    # 选项值
    for pfx in ['rp','ip']:
        for k in list(i['fd'].keys()):
            if k.startswith(pfx+'_sel') or k.startswith(pfx+'_ms') or k.startswith(pfx+'_cas'):
                for f in i['fd'][k]:
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
    if i['contracts']: ct=random.choice(i['contracts']); return ct['id'],int(ct.get('customer_id',5600044))
    elif i['cs']: return None,int(random.choice(i['cs']))
    return None,None

def fill_custom_fields(c,i,pfx):
    """填充自定义字段, pfx='rp'或'ip'"""
    for kf in ['tx','em','mb','ur']:
        fn={'tx':rt,'em':re,'mb':rp,'ur':ru}
        for f in i['fd'].get(pfx+'_'+kf,[]): c[f['name']]=fn[kf]()
    for f in i['fd'].get(pfx+'_nu',[]): c[f['name']]=rd() if '金额' in f['label'] or '币' in f['label'] else ri()
    for f in i['fd'].get(pfx+'_dt',[]): c[f['name']]=rf()
    for f in i['fd'].get(pfx+'_sel',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in i['fd'].get(pfx+'_ms',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.sample(o,random.randint(2,min(4,len(o)))) if o else None
    for f in i['fd'].get(pfx+'_cas',[]):
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    if i['pc_users']:
        for f in i['fd'].get(pfx+'_us',[]): c[f['name']]=random.sample(i['pc_users'],1)
        for f in i['fd'].get(pfx+'_mu',[]): c[f['name']]=random.sample(i['pc_users'],min(3,len(i['pc_users'])))
    if i.get('dp'):
        for f in i['fd'].get(pfx+'_dp',[]): c[f['name']]=random.sample(i['dp'],1)
        for f in i['fd'].get(pfx+'_md',[]): c[f['name']]=random.sample(i['dp'],min(2,len(i['dp'])))
    for f in i['fd'].get(pfx+'_rl',[]): c[f['name']]=str(random.choice(['7','13']))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('--env', choices=['test','staging','production'])
    p.add_argument('--profile', choices=['gray','standard'])
    p.add_argument('cnt',nargs='?',type=int,default=1); p.add_argument('--delay',type=float,default=0.5)
    p.add_argument('--type',choices=['received_payment','invoiced_payment'],default='received_payment')
    p.add_argument('--attachment-dir',help='本地图片目录,上传到文件字段')
    a=apply_config_defaults(p.parse_args(), p)
    api=a.api.rstrip('/')

    print(f"\n{'='*60}")
    print('回款计划+回款记录' if a.type=='received_payment' else '开票记录')
    print(f'API: {api} 数量: {a.cnt}')
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print('='*60)

    try:
        i=discover(api,a.token)
        print(f'  合同:{len(i["contracts"])} 客户:{len(i["cs"])} 用户:{len(i["pc_users"])} 部门:{len(i["dp"])}')
        print(f'  回款文件字段:{len(i["file_fields"]["rp"])} 开票文件字段:{len(i["file_fields"]["ip"])}')
    except Exception as e: print(f'失败: {e}'); return

    ok=fail=0
    for n in range(1,a.cnt+1):
        try:
            ct_id,cust_id=pick_contract(i)
            if not ct_id:
                fail+=1;print(f"  ✗ [{n}/{a.cnt}] 无可用合同"); continue

            if a.type=='received_payment':
                nfiles_rp=0
                # Step1: 创建回款计划(2期)
                plans=[
                    {'period_name':'第1期','receive_stage':1,'receive_date':rf(),'amount':str(rd())[:8],
                     'received_types':random.choice(i['fm'].get('received_types',['2103298'])),
                     'payment_type':random.choice(i['payment_type']) if i['payment_type'] else None,
                     'receive_user_id':int(random.choice(i['pc_users'])) if i['pc_users'] else None},
                    {'period_name':'第2期','receive_stage':2,'receive_date':rf(),'amount':str(rd())[:8],
                     'received_types':random.choice(i['fm'].get('received_types',['2103298']))},
                ]
                pc_res=pcurl(api,a.token,'received_payment_plans/batch_create','POST',
                    {'contract_id':ct_id,'plans':plans})
                if pc_res.get('code')!=0 or not pc_res.get('data'):
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] 创建计划失败: {pc_res.get('message','?')[:60]}"); continue
                plan_id=pc_res['data'][0]['id']  # 第1期ID

                # Step2: 创建回款记录(关联第1期)
                rp_data={'amount':rd(),'receive_date':rf(),'received_types':random.choice(i['fm'].get('received_types',['2103298'])),
                    'customer_id':cust_id,'contract_id':ct_id,'received_payment_plan_id':plan_id,
                    'payment_type':random.choice(i['payment_type']) if i['payment_type'] else None,
                    'receive_user_id':int(random.choice(i['pc_users'])) if i['pc_users'] else None,
                    'note':f'批量第{n}条-回款'}
                fill_custom_fields(rp_data,i,'rp')
                # 文件字段
                if a.attachment_dir:
                    nfiles_rp=len(process_file_fields(api,a.token,'ReceivedPayment',rp_data,a.attachment_dir))
                    rp_res=requests.post(pc_url(api)+'/api/pc/received_payments',
                        headers={'Content-Type':'application/json','Authorization':f'Token token={a.token}'},
                        json={'received_payment':rp_data},timeout=30).json()
                else:
                    rp_res=pcurl(api,a.token,'received_payments','POST',{'received_payment':rp_data})
                if rp_res.get('code')==0:
                    fmsg=f' 文件:{nfiles_rp}个' if a.attachment_dir else ''
                    ok+=1;print(f"  ✓ [{n}/{a.cnt}] 计划:{plan_id} 回款:{rp_res['data']['id']} 金额:{rp_data['amount']}{fmsg}")
                else:
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] 回款失败: {rp_res.get('message','?')[:60]}")

            elif a.type=='invoiced_payment':
                nfiles_ip=0
                ip_data={'amount':rd(),'invoiced_date':rf(),'invoice_no':'INV'+str(time.time())[-8:],
                    'customer_id':cust_id,
                    'invoice_types':random.choice(i['fm'].get('invoice_types',['2103302'])),
                    'broker_user_id':int(random.choice(i['pc_users'])) if i['pc_users'] else None,
                    'content':'开票内容-'+random.choice(['技术服务费','软件开发费','咨询费','服务费','产品采购费','项目开发费'])+'-'+str(time.time())[-6:],
                    'note':f'批量第{n}条-开票'}
                fill_custom_fields(ip_data,i,'ip')
                # 文件字段
                if a.attachment_dir:
                    nfiles_ip=len(process_file_fields(api,a.token,'InvoicedPayment',ip_data,a.attachment_dir))
                    ip_res=requests.post(pc_url(api)+'/api/pc/invoiced_payments',
                        headers={'Content-Type':'application/json','Authorization':f'Token token={a.token}'},
                        json={'invoiced_payment':ip_data,'contract_id':ct_id},timeout=30).json()
                else:
                    ip_res=pcurl(api,a.token,'invoiced_payments','POST',
                        {'invoiced_payment':ip_data,'contract_id':ct_id})
                if ip_res.get('code')==0:
                    fmsg=f' 文件:{nfiles_ip}个' if a.attachment_dir else ''
                    ok+=1;print(f"  ✓ [{n}/{a.cnt}] ID:{ip_res['data']['id']} 金额:{ip_data['amount']}{fmsg}")
                else:
                    fail+=1;print(f"  ✗ [{n}/{a.cnt}] {ip_res.get('message','?')[:60]}")

        except Exception as e: fail+=1;print(f"  ✗ [{n}/{a.cnt}] {e}")
        if n<a.cnt and a.delay>0: time.sleep(a.delay)

    print(f'\n完成! 成功:{ok} 失败:{fail}')
    if ok>0 and a.type=='received_payment':
        print('  注:回款计划(2期)+回款记录(关联第1期)')

if __name__=='__main__': main()
