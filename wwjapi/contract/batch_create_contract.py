#!/usr/bin/env python3
"""批量创建合同 - 含客户/商机/报价单联动, 业务类型"""
import json,random,string,argparse,time,subprocess
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import create_entity, upload_attach_files
import requests

def curl(api,token,method,path,data=None):
    a=api.rstrip('/')
    c=['curl','-s','-k','-X',method,'-H','Content-Type: application/json','-H',f'Authorization: Token token={token}']
    if data: c+=['-d',json.dumps(data)]
    c+=[f'{a}/api/v2/{path.lstrip("/")}']
    raw=subprocess.run(c,capture_output=True,timeout=60).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def pcurl(api,token,path):
    pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.')
    raw=subprocess.run(['curl','-s','-k','-H','Authorization: Token token='+token,pc+'/api/pc/'+path.lstrip('/')],capture_output=True,timeout=15).stdout
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def discover(api,token):
    i={'fm':{},'fd':{'sel':[],'ms':[],'cas':[],'tx':[],'nu':[],'em':[],'mb':[],'ur':[],'dt':[],'us':[],'mu':[],'dp':[],'md':[],'rl':[]},'op':{}}
    fm=curl(api,token,'GET','field_maps/contract')
    for f in fm.get('data',{}).get('contract',[]):
        v=[x for x in f.get('field_values',[]) if x.get('status')=='enable']
        if v: i['fm'][f['field_name']]=[str(x['id']) for x in v]
    cf=pcurl(api,token,'custom_fields?model_klass=Contract')
    m={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'tx','text_area':'tx','number_field':'nu','currency_field':'nu','email_field':'em','mobile_field':'mb','url_field':'ur','datetime_field':'dt','user_field':'us','multi_user_field':'mu','department_field':'dp','multi_department_field':'md','custom_relation_field':'rl'}
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); t=f.get('field_type',''); fid=f.get('field_id')
            if n in ['title','sn','product_assets','total_amount','sign_date','start_at','end_at','contact_assetships','checking_payments_amount','received_payments_amount','unreceived_amount','unchecking_payments_amount','status','category','payment_type','customer_signer','our_signer','attachments','revisit_remind_at','received_payment_plans','special_terms','customer','opportunity','quotations']: continue
            if n.startswith('subform_') or n.startswith('file_asset'): continue
            tt=m.get(t,'tx'); i['fd'][tt].append({'name':n,'label':f.get('label',''),'fid':fid})
    for e in i['fd']['sel']+i['fd']['ms']+i['fd']['cas']:
        if not e['fid']: continue
        d=pcurl(api,token,f'custom_fields/{e["fid"]}')
        os=d.get('data',{}).get('options',{}).get('select_options',[])
        vs=[]
        for o in os:
            if isinstance(o,list) and len(o)==2: vs.append(o[1])
            elif isinstance(o,dict): vs.append(o.get('value',''))
        vs=[x for x in vs if x]
        if vs: i['op'][e['name']]=vs
    # PC端用户(用于协作)
    us_pc=pcurl(api,token,'users?page=1&per_page=50')
    i['pc_users']=[]
    if us_pc.get('code')==0:
        ud=us_pc.get('data',{}); pu=ud.get('users',ud.get('list',[]))
        if pu: i['pc_users']=[str(u['id']) for u in pu if u.get('id')]
    dp=curl(api,token,'GET','departments'); i['dp']=[str(x['id']) for x in dp.get('data',{}).get('departments',[]) if x.get('id')]
    cl=curl(api,token,'GET','customers?per_page=50&sort=created_at&order=desc'); i['cs']=[str(x['id']) for x in cl.get('data',{}).get('customers',[]) if x.get('id')]
    pr=curl(api,token,'GET','products?per_page=50'); i['pd']=[str(x['id']) for x in pr.get('data',{}).get('products',[]) if x.get('id')]
    # 业务模板
    i['template_id']=None
    for entry in i['fd'].get('sel',[]):
        if entry['fid']:
            try:
                td=pcurl(api,token,'custom_fields/'+str(entry['fid']))
                for t in td.get('data',{}).get('custom_field_templates',[]):
                    if t.get('status')=='enable': i['template_id']=t['id']; break
            except: pass
            if i['template_id']: break
    return i

rp=lambda: random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
re=lambda: ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
ru=lambda: 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
rt=lambda: ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
ri=lambda: random.randint(10000,99999); rd=lambda: round(random.uniform(100,99999),2)
rf=lambda: (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')

def build(i,api,token):
    c={}
    for k,v in i['fm'].items():
        if v: c[k]=v[0]
    # 对应客户 + 商机(找有客户下有联系人的)
    if i['cs']:
        found_cid=None
        known_good=['5600044','5600040','5600033','5600020','5600019']
        for kcid in known_good:
            if kcid in i['cs']:
                try:
                    cr=curl(api,token,'GET','customers/'+kcid)
                    cons=cr.get('data',{}).get('contacts',[])
                    opps=curl(api,token,'GET','opportunities?customer_id='+kcid).get('data',{}).get('opportunities',[])
                    if cons and opps:
                        found_cid=int(kcid)
                        c['opportunity_id']=opps[0]['id']
                        # 该客户下的报价单
                        qts=curl(api,token,'GET','quotations?customer_id='+kcid).get('data',{}).get('list',[])
                        if qts: c['quotation_ids']=[q['id'] for q in qts[:3]]
                        break
                except: continue
        if not found_cid:
            for scid in i['cs']:
                try:
                    cr=curl(api,token,'GET','customers/'+str(scid))
                    cons=cr.get('data',{}).get('contacts',[])
                    if not cons: continue
                    opps=curl(api,token,'GET','opportunities?customer_id='+str(scid)).get('data',{}).get('opportunities',[])
                    if opps:
                        found_cid=int(scid)
                        c['opportunity_id']=opps[0]['id']
                        qts=curl(api,token,'GET','quotations?customer_id='+str(scid)).get('data',{}).get('list',[])
                        if qts: c['quotation_ids']=[q['id'] for q in qts[:3]]
                        break
                except: continue
        if found_cid: c['customer_id']=found_cid
    # 业务类型
    if i['template_id']: c['custom_field_template_id']=i['template_id']
    # 关联产品(3个)
    if i['pd']:
        pids=random.sample(i['pd'],min(3,len(i['pd'])))
        c['product_assets_attributes']=[{'product_id':int(p),'quantity':random.randint(1,10),'price':random.randint(1000,100000)} for p in pids]
    # 协作人(3个用户)
    if len(i['pc_users'])>=3: c['assist_user_ids']=random.sample(i['pc_users'],3)
    elif i['pc_users']: c['assist_user_ids']=i['pc_users'][:3]
    # 基础字段
    c['title']='合同-'+str(time.time())[-8:]; c['sn']='HT'+rt()
    c['sign_date']=rf(); c['start_at']=rf(); c['end_at']=rf()
    c['total_amount']=rd(); c['checking_payments_amount']=rd(); c['received_payments_amount']=rd()
    c['unreceived_amount']=rd(); c['unchecking_payments_amount']=rd()
    c['customer_signer']=rt()[:4]; c['our_signer']=rt()[:4]
    c['revisit_remind_at']=(datetime.now()+timedelta(days=random.randint(1,14))).strftime('%Y-%m-%d %H:%M')
    for kf in ['tx','em','mb','ur']:
        fn={'tx':rt,'em':re,'mb':rp,'ur':ru}
        for f in i['fd'][kf]: c[f['name']]=fn[kf]()
    for f in i['fd']['nu']: c[f['name']]=rd() if '金额' in f['label'] or '币' in f['label'] else ri()
    for f in i['fd']['dt']: c[f['name']]=rf()
    for f in i['fd']['sel']:
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in i['fd']['ms']:
        o=i['op'].get(f['name'],[]); c[f['name']]=random.sample(o,random.randint(2,min(4,len(o)))) if o else None
    for f in i['fd']['cas']:
        o=i['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    if i['pc_users']:
        for f in i['fd']['us']: c[f['name']]=random.sample(i['pc_users'],1)
        for f in i['fd']['mu']: c[f['name']]=random.sample(i['pc_users'],min(3,len(i['pc_users'])))
    if i['dp']:
        for f in i['fd']['dp']: c[f['name']]=random.sample(i['dp'],1)
        for f in i['fd']['md']: c[f['name']]=random.sample(i['dp'],min(2,len(i['dp'])))
    for f in i['fd']['rl']: c[f['name']]=str(random.choice(['7','13']))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('cnt',nargs='?',type=int,default=1); p.add_argument('--delay',type=float,default=0.5)
    p.add_argument("--attachment-dir",help="本地图片目录,上传到文件字段")
    a=apply_config_defaults(p.parse_args(), p)
    print(f"\n{'='*60}\n合同\nAPI: {a.api}\n数量: {a.cnt}\n{'='*60}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    try:
        i=discover(a.api,a.token)
        print(f'  系统:{len(i["fm"])} 客户:{len(i["cs"])} 模板:{i.get("template_id","无")} 用户:{len(i.get("pc_users",[]))}')
    except Exception as e: print(f'失败: {e}'); return
    ok=fail=0
    for n in range(1,a.cnt+1):
        try:
            d=build(i,a.api,a.token); d['special_terms']=f'批量第{n}条'
            # 通过PC端点POST(支持assist_user_ids持久化)
            d['user_id']=12380524; d['want_department_id']=5013378
            d['intl_extra_attributes']={}; d['received_payment_plans_attributes']=[]
            if a.attachment_dir:
                res,nfiles = create_entity(a.api, a.token, "Contract", d, a.attachment_dir)
                if res.get('code')==0:
                    qid=res['data']['id']
                    nattach=upload_attach_files(a.api,a.token,"Contract",qid,a.attachment_dir)
                    ok+=1; print(f"  ✓ [{n}/{a.cnt}] ID:{qid} 客户:{d.get('customer_id')} 文件:{nfiles} 附件:{nattach}")
                else: fail+=1; print(f"  ✗ [{n}/{a.cnt}] {res.get('message','?')[:60]}")
            else:
                pc_api=a.api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.')
                pc_args=['curl','-s','-k','-X','POST','-H','Content-Type: application/json',
                    '-H',f'Authorization: Token token={a.token}',
                    '-d',json.dumps({'contract':d}),pc_api+'/api/pc/contracts']
                pc_raw=subprocess.run(pc_args,capture_output=True,timeout=60).stdout
                pc_res=json.loads(pc_raw) if pc_raw else {}
                if pc_res.get('code')==0: ok+=1; qid=pc_res['data']['id']; print(f"  ✓ [{n}/{a.cnt}] ID:{qid} 客户:{d.get('customer_id')} 报价单:{len(d.get('quotation_ids',[]))}个")
                else: fail+=1; print(f"  ✗ [{n}/{a.cnt}] {pc_res.get('message','?')[:60]}")
        except Exception as e: fail+=1; print(f"  ✗ [{n}/{a.cnt}] {e}")
        if n<a.cnt and a.delay>0: time.sleep(a.delay)
    print(f'\n完成! 成功:{ok} 失败:{fail}')
if __name__=='__main__': main()
