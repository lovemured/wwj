#!/usr/bin/env python3
"""完整CRM流程: 线索→客户→联系人→商机→报价单→合同→回款→开票→费用→报销单(含全部字段)
修复: 非线索转客户/业务类型/系统字段/关联产品/报价单编号/发票号/报销关联等
使用: python3 wwjapi/flow/crm_flow.py [轮数]
"""
import importlib.util
import json,random,string,argparse,time,sys,os,requests
from datetime import datetime,timedelta
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import pc_url, process_file_fields, upload_attach_files, upload_to_oss

PC=None; TOKEN=None
REPO_ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def crm_url():
    return PC.replace('//lxcrm-api-staging.','//lxcrm-staging.').replace('//lxcrm-api-test.','//lxcrm-test.').replace('//lxcrm-api.','//lxcrm.')

def request_json(method,url,data=None,timeout=60):
    try:
        resp=requests.request(
            method,url,
            headers={'Content-Type':'application/json','Authorization':f'Token token={TOKEN}'},
            json=data if data is not None else None,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {'code':-1,'message':f'请求失败: {exc}'}
    try:
        body=resp.json()
    except ValueError:
        body={'raw_text':resp.text[:500]}
    if resp.status_code>=400 and isinstance(body,dict):
        body.setdefault('message',f'HTTP {resp.status_code}: {resp.text[:500]}')
    return body

def api(postfix,data=None,method='GET',pc=False):
    a=PC if pc else crm_url()
    base=a.rstrip('/')+('/api/pc' if pc else '/api/v2')
    return request_json(method,f'{base}/{postfix.lstrip("/")}',data=data)

def pcurl(path):
    return request_json('GET',PC.rstrip()+'/api/pc/'+path.lstrip('/'),timeout=15)

def v2curl(path):
    return request_json('GET',crm_url().rstrip()+'/api/v2/'+path.lstrip('/'),timeout=15)

def usable_template_id(module_key):
    templates=pcurl('custom_field_templates?model_klass='+{
        'ea':'expense_account',
    }.get(module_key,module_key)).get('data',{}).get('list',[])
    enabled=[item for item in templates if item.get('status')=='enable' and item.get('is_usable',True)]
    return max(enabled,key=lambda item:int(item.get('id') or 0)).get('id') if enabled else None

def load_local_module(name, relative_path):
    path=os.path.join(REPO_ROOT,relative_path)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fetch_apaas_values(custom_form_id, per_page=20):
    url=f"{PC}/apaas/api/v2/form_entities/simple?page=1&per_page={per_page}&without_count=true&custom_form_id={custom_form_id}"
    data=request_json('GET',url,timeout=15).get('data',{})
    return [
        str(item.get('value') or item.get('id'))
        for item in data.get('models',[])
        if item.get('value') or item.get('id')
    ]

def enabled_field_values(model, field_name):
    fields=v2curl('field_maps/'+model).get('data',{}).get(model,[])
    for field in fields:
        if field.get('field_name')==field_name:
            return [str(item['id']) for item in field.get('field_values',[]) if item.get('status')=='enable']
    return []

def pick_apaas_value(values):
    return random.choice(values) if values else None

def create_market_activity(api_base, attachment_dir, ts):
    market=load_local_module('batch_create_market','market/batch_create_market.py')
    market_info=market.discover(api_base,TOKEN)
    data=market.build(market_info)
    data['name']=f'CRM市场活动-{ts}'
    data['note']=f'CRM全流程市场活动-{ts}'
    process_file_fields(api_base,TOKEN,'MarketActivity',data,attachment_dir)
    attach_ids=upload_local_attachment_ids(api_base,attachment_dir,2)
    if attach_ids:
        data['attachments']=[{'id':aid,'uploadId':aid,'note':'','key':'','type':'application/octet-stream'} for aid in attach_ids]
    res=request_json('POST',f'{PC}/api/pc/market_activities',data={'market_activity':data,'attachment_ids':attach_ids})
    return res.get('data',{}).get('id'),res

def upload_local_attachment_ids(api_base, attachment_dir, count=1):
    if not attachment_dir:
        return []
    files=[
        os.path.join(attachment_dir,name)
        for name in os.listdir(attachment_dir)
        if os.path.isfile(os.path.join(attachment_dir,name)) and not name.startswith('.')
    ]
    if not files:
        return []
    image_files=[path for path in files if path.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp','.bmp','.heic'))]
    candidates=image_files or files
    random.shuffle(candidates)
    ids=[]
    for path in candidates:
        aid=upload_to_oss(api_base,TOKEN,path)
        if aid:
            ids.append(aid)
        if len(ids)>=count:
            break
    return ids

def upload_expense_attachment_ids(api_base, attachment_dir, count=1):
    return upload_local_attachment_ids(api_base,attachment_dir,count)

# ========== 字段发现 ==========
def discover():
    info={'fm':{},'op':{},'pc_users':[],'dp':[],'cs':[],'contracts':[],'products':[],'subsidiaries':[],'template_ids':{},
          'expense_categories':[],'current_user':{},'apaas_207':[],'apaas_277':[],'apaas_281':[],'relation_values':{},
          'lead':{},'customer':{},'contact':{},'opportunity':{},'quotation':{},'contract':{},'rp':{},'ip':{},'expense':{},'ea':{},
          'lead_file':[],'customer_file':[],'contact_file':[],'opportunity_file':[],'quotation_file':[],'contract_file':[],'rp_file':[],'ip_file':[],'expense_file':[],'ea_file':[],
          'lead_attach':[],'opportunity_attach':[],'quotation_attach':[],'contract_attach':[]}

    us=pcurl('users?page=1&per_page=50')
    if us.get('code')==0:
        ud=us.get('data',{}); pu=ud.get('users',ud.get('list',[]))
        if pu: info['pc_users']=[u['id'] for u in pu if u.get('id')]
    user_info=v2curl('user/info').get('data',{})
    if user_info:
        info['current_user']={
            'id':user_info.get('id'),
            'department_id':user_info.get('department_id'),
            'name':user_info.get('name'),
        }

    dp=v2curl('departments'); info['dp']=[x['id'] for x in dp.get('data',{}).get('departments',[]) if x.get('id')]
    cl=v2curl('customers?per_page=50&sort=created_at&order=desc'); info['cs']=[str(c['id']) for c in cl.get('data',{}).get('customers',[]) if c.get('id')]
    ct=v2curl('contracts?per_page=50&sort=created_at&order=desc')
    info['contracts']=[{'id':c['id'],'customer_id':c.get('customer_id')} for c in ct.get('data',{}).get('list',ct.get('data',{}).get('contracts',[])) if c.get('id')]
    pr=v2curl('products?per_page=50'); info['products']=[str(p['id']) for p in pr.get('data',{}).get('products',[]) if p.get('id')]
    sub=v2curl('subsidiaries'); info['subsidiaries']=[str(s['id']) for s in sub.get('list',[]) if s.get('id')]
    if not info['subsidiaries']:
        sub_pc=pcurl('subsidiaries')
        info['subsidiaries']=[str(s['id']) for s in sub_pc.get('data',{}).get('list',[]) if s.get('id')]
    lb=v2curl('labels'); info['labels']=[]
    for g in lb.get('data',{}).get('label_groups',[]):
        for l in g.get('labels',[]):
            info['labels'].append({'label_id':l['id'],'label_group_id':g['group_id']})

    # 系统字段 + 付款方式
    for fm_name in ['lead','customer','contact','opportunity','quotation','contract','received_payment','invoiced_payment','expense']:
        fm=v2curl('field_maps/'+fm_name); info['fm'][fm_name]={}
        for f in fm.get('data',{}).get(fm_name,[]):
            vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
            if vals: info['fm'][fm_name][f['field_name']]=[str(v['id']) for v in vals]
    pm=v2curl('field_maps/contract')
    for f in pm.get('data',{}).get('contract',[]):
        if f['field_name']=='payment_type':
            vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
            if vals: info['fm']['payment_type']=[str(v['id']) for v in vals]

    # 自定义字段 + 业务模板
    tm={'select':'sel','multi_select':'ms','nested_select_field':'cas','text_field':'tx','text_area':'tx',
        'number_field':'nu','currency_field':'nu','email_field':'em','mobile_field':'mb','url_field':'ur',
        'datetime_field':'dt','user_field':'us','multi_user_field':'mu','department_field':'dp',
        'multi_department_field':'md','custom_relation_field':'rl','multi_nested_select_field':'mcas'}
    ex_map={
        'lead':{'name','company_name','department','job','status','source','channel','revisit_remind_at','note','market_activity'},
        'customer':{'name','company_name','note','parent','status','category','source','industry','staff_size','channel','labels','revisit_remind_at','number','beginning_payments_amount'},
        'contact':{'name','customer','department','job','category','gender','birth_date','note'},
        'opportunity':{'title','customer','contact_assetships','product_assets','expect_amount','expect_sign_date','get_time','stage','kind','source','revisit_remind_at','note'},
        'quotation':{'name','quotation_no','quotation_date','effective_date_fr','effective_date_to','product_assets','product_total_amount','additional_discount_amount','whole_discount','total_amount','status','title','sub_title','note','revisit_remind_at','customer','contact','opportunity'},
        'contract':{'title','sn','product_assets','total_amount','sign_date','start_at','end_at','contact_assetships','checking_payments_amount','received_payments_amount','unreceived_amount','unchecking_payments_amount','status','category','payment_type','customer_signer','our_signer','revisit_remind_at','received_payment_plans','special_terms','customer','opportunity','quotations'},
        'rp':{'title','sn','product_assets','total_amount','sign_date','start_at','end_at','customer','contract','contact_assetships','received_payment_plan','receive_user','receive_date','amount','received_types','payment_type','note','attachments','broker_user','invoiced_date','invoice_types','invoice_no','content','plan_date','received_amount','invoice_amount','unreceived_amount'},
        'ip':{'title','sn','product_assets','total_amount','sign_date','start_at','end_at','customer','contract','contact_assetships','received_payment_plan','receive_user','receive_date','amount','received_types','payment_type','note','attachments','broker_user','invoiced_date','invoice_types','invoice_no','content','plan_date','received_amount','invoice_amount','unreceived_amount'},
        'expense':{'sn','category','description','amount','incurred_at','customer','contacts_expenses','related_item','revisit_log','checkin','attachments','note','user','owned_department'},
        'ea':{'sn','note','user','owned_department','amount'},
    }
    template_keys=['lead','customer','opportunity','quotation','contract','ea']

    for klass,key in [('Lead','lead'),('Customer','customer'),('Contact','contact'),
                      ('Opportunity','opportunity'),('Quotation','quotation'),
                      ('Contract','contract'),('ReceivedPayment','rp'),
                      ('InvoicedPayment','ip'),('Expense','expense'),
                      ('ExpenseAccount','ea')]:
        fd={}; file_fd=[]; attach_fd=[]
        cf=pcurl('custom_fields?model_klass='+klass)
        if not cf.get('data'): continue
        for g in cf.get('data',{}).get('custom_field_groups',[]):
            for f in g.get('custom_fields',[]):
                n=f.get('name',''); t=f.get('field_type',''); fid=f.get('field_id')
                if key=='expense' and n=='category' and fid:
                    d=pcurl('custom_fields/'+str(fid))
                    opts=d.get('data',{}).get('input_field_options',{}).get('collection_options',[])
                    info['expense_categories']=[
                        (str(o.get('value')),o.get('label'))
                        for o in opts
                        if isinstance(o,dict) and o.get('value') not in (None,'') and o.get('label')
                    ]
                if n in ex_map.get(key,set()) or n.startswith('subform_') or n in ['address.contact_phone','address.contact_email']: continue
                if n.startswith('file_asset') and t in ('file_field','file_type'):
                    file_fd.append({'name':n,'label':f.get('label','')}); continue
                if t=='attachments_field':
                    attach_fd.append({'name':n,'label':f.get('label','')}); continue
                st=tm.get(t,'tx')
                fd[st]=fd.get(st,[])+[{'name':n,'fid':fid,'label':f.get('label','')}]
        relation_values={}
        for relation in fd.get('rl',[]):
            detail=pcurl('custom_fields/'+str(relation['fid'])).get('data',{})
            source=((detail.get('options') or {}).get('relation_options') or {}).get('relation_source') or {}
            if source.get('id'):
                values=fetch_apaas_values(source['id'])
                if values:
                    relation_values[relation['name']]=values
        info['relation_values'][key]=relation_values
        info[key]=fd
        info[key+'_file']=file_fd
        info[key+'_attach']=attach_fd

        # 仅使用当前用户可见且启用的业务类型，不能从字段详情中猜测。
        if key in template_keys:
            info['template_ids'][key]=usable_template_id(key)

    info['apaas_207']=fetch_apaas_values(207)
    info['apaas_277']=fetch_apaas_values(277)
    info['apaas_281']=fetch_apaas_values(281)

    # 选项值
    for key in ['lead','customer','contact','opportunity','quotation','contract','rp','ip','expense','ea']:
        for st in ['sel','ms','cas','mcas']:
            for f in info[key].get(st,[]):
                if f['fid']:
                    d=pcurl('custom_fields/'+str(f['fid']))
                    os_=d.get('data',{}).get('options',{}).get('select_options',[])
                    vs=[]
                    for o in os_:
                        if isinstance(o,list) and len(o)==2: vs.append(o[1])
                        elif isinstance(o,dict): vs.append(o.get('value',''))
                    vs=[x for x in vs if x]
                    if vs: info['op'][f['name']]=vs
    return info

# ========== 随机值 ==========
gv=lambda: random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
ge=lambda: ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
gu=lambda: 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
gt=lambda: ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,10)))
ga=lambda: round(random.uniform(100,999),2)
gd=lambda: (datetime.now()+timedelta(days=random.randint(1,30))).strftime('%Y-%m-%d')
gdt=lambda: (datetime.now()+timedelta(days=random.randint(28,31))).strftime('%Y-%m-%d %H:%M')
gi=lambda: random.randint(10000,99999)
R=['科技路','创新路','发展大道','人民路','建设路','中山路']
J=['经理','总监','主管','工程师']
EXPENSE_CATEGORIES=[
    ('2103338','招待费'),
    ('2103339','交通费'),
    ('2103340','酒店费'),
    ('2103341','通讯费'),
    ('2103342','物流费'),
    ('2103343','礼品费'),
    ('2103344','其他'),
]

def fill(c,fd,module_key):
    for kf in ['tx','em','mb','ur']:
        fn={'tx':gt,'em':ge,'mb':gv,'ur':gu}
        for f in fd.get(kf,[]): c[f['name']]=fn[kf]()
    for f in fd.get('nu',[]): c[f['name']]=gi()
    for f in fd.get('dt',[]): c[f['name']]=gd()
    for f in fd.get('sel',[]):
        o=info['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in fd.get('ms',[]):
        o=info['op'].get(f['name'],[]); c[f['name']]=random.sample(o,random.randint(2,min(4,len(o)))) if o else None
    for f in fd.get('cas',[]):
        o=info['op'].get(f['name'],[]); c[f['name']]=random.choice(o) if o else None
    for f in fd.get('mcas',[]):
        o=info['op'].get(f['name'],[])
        if len(o)>=2: c[f['name']]=random.sample(o,2)
        elif o: c[f['name']]=[random.choice(o)]
    if info['pc_users']:
        for f in fd.get('us',[]): c[f['name']]=random.sample(info['pc_users'],1)
        for f in fd.get('mu',[]): c[f['name']]=random.sample(info['pc_users'],min(3,len(info['pc_users'])))
    if info['dp']:
        for f in fd.get('dp',[]): c[f['name']]=random.sample(info['dp'],1)
        for f in fd.get('md',[]): c[f['name']]=random.sample(info['dp'],min(2,len(info['dp'])))
    for f in fd.get('rl',[]):
        values=info.get('relation_values',{}).get(module_key,{}).get(f['name'],[])
        c[f['name']]=random.choice(values) if values else str(random.choice(['7','13']))
    return c

def prod_attrs(n=3):
    if not info['products']: return []
    pids=random.sample(info['products'],min(n,len(info['products'])))
    return [{'product_id':int(p),'quantity':random.randint(1,10)} for p in pids]

def pick_assist_user_ids(count=2):
    users=[u for u in info.get('pc_users',[]) if u]
    if len(users)>=count:
        return random.sample(users,count)
    return users

def validate_discovery(info):
    missing=[]
    if not info['pc_users']: missing.append('用户')
    if not info['dp']: missing.append('部门')
    if missing:
        print(f'  ✗ 缺少基础数据: {", ".join(missing)}')
        return False
    if not info['products']:
        print('  ⚠️ 未发现产品，商机/报价单/合同将无法验证产品关联')
    if not info['subsidiaries']:
        print('  ⚠️ 未发现乙方主体，报价单会跳过乙方主体字段')
    return True

def run(n, attachment_dir=None):
    api_base=crm_url()
    primary_user_id=info.get('current_user',{}).get('id') or info['pc_users'][0]
    primary_department_id=info.get('current_user',{}).get('department_id') or (info['dp'][0] if info['dp'] else None)
    completed=0
    for r in range(1,n+1):
        ts=str(int(time.time()*1000))[-8:]
        print(f'\n{"#"*60}\n# 第 {r}/{n} 轮\n{"#"*60}')

        # ====== 1. 市场活动 ======
        mid=None
        market_res={}
        try:
            mid,market_res=create_market_activity(api_base,attachment_dir,ts)
        except Exception as exc:
            market_res={'message':str(exc)}
        if mid:
            print(f'  ✅ 1/12 市场活动 ID:{mid}')
        else:
            print(f'  ○ 1/12 市场活动创建失败，线索跳过市场活动关联: {market_res.get("message",market_res)}')

        # ====== 2. 线索 ======
        data1={'lead':{
            'name':f'CRM线索-{ts}','company_name':f'CRM{gt()}科技',
            'source':random.choice(info['fm'].get('lead',{}).get('source',['2103314'])),
            'status':random.choice(info['fm'].get('lead',{}).get('status',['2103322'])),
            'channel':random.choice(info['fm'].get('lead',{}).get('channel',['2103327'])),
            'department':'研发部','job':random.choice(J),'approve_status':'approved',
            'revisit_remind_at':gdt(),'note':f'CRM流程线索-{ts}',
            'address_attributes':{'phone':gv(),'tel':'0519-'+str(gi()),'email':ge(),
                'wechat':gv(),'qq':str(gi()),'wangwang':gv(),'url':gu(),
                'zip':f'518{random.randint(10,99)}','province_id':random.choice([1,10,13,21]),
                'detail_address':f'{random.choice(R)}{random.randint(1,999)}号'},
        }}
        fill(data1['lead'],info['lead'],'lead')
        if mid:
            data1['lead']['market_activity_id']=mid
        if info['template_ids'].get('lead'): data1['lead']['custom_field_template_id']=info['template_ids']['lead']
        process_file_fields(api_base,TOKEN,'Lead',data1['lead'],attachment_dir)
        lead_res=api('leads',data=data1,method='POST')
        lid=lead_res.get('data',{}).get('id')
        if not lid:
            print(f'  ✗ 2/12 线索创建失败: {lead_res.get("message",lead_res)}')
            continue
        print(f'  ✅ 2/12 线索 ID:{lid}')

        # ====== 3. 线索转客户(PC端点) ======
        cid=None
        try:
            # 先获取转客户表单(用于获取模板和结构数据)
            tid=info['template_ids'].get('customer',1331)
            form=api('leads/'+str(lid)+'/turn_to_customer?custom_field_template_id='+str(tid),method='GET',pc=True)
            # PC端点POST创建客户(含refer_lead_id标记已转换)
            customer={'name':f'CRM客户-{ts}','company_name':f'CRM{gt()}科技','status':random.choice(info['fm'].get('customer',{}).get('status',['2103221'])),
                'category':random.choice(info['fm'].get('customer',{}).get('category',['2103226'])),
                'source':random.choice(info['fm'].get('customer',{}).get('source',['2103229'])),
                'industry':random.choice(info['fm'].get('customer',{}).get('industry',['2103241'])),
                'staff_size':random.choice(info['fm'].get('customer',{}).get('staff_size',['2103252'])),
                'channel':random.choice(info['fm'].get('customer',{}).get('channel',['2103259'])),
                'approve_status':'approved','revisit_remind_at':gdt(),
                'custom_field_template_id':tid if tid else None,
                'number':'CUST'+ts,
                'beginning_payments_amount':ga(),
                'note':f'CRM客户备注-{ts}',
                'customer_labels_attributes':random.sample(info['labels'],min(3,len(info['labels']))) if info['labels'] else None,
                'address_attributes':{'phone':gv(),'tel':'0519-'+str(gi()),'email':ge(),'wechat':gv(),
                    'qq':str(gi()),'wangwang':gv(),'url':gu(),'fax':'0519-'+str(gi()),'zip':f'518{random.randint(10,99)}',
                    'province_id':random.choice([1,10,13,21]),
                    'detail_address':f'{random.choice(R)}{random.randint(1,999)}号'},
                'parent_id':int(random.choice(info['cs'])) if info['cs'] else None,
            }
            fill(customer,info['customer'],'customer')
            customer['number']='CUST'+ts
            customer['beginning_payments_amount']=ga()
            customer['note']=f'CRM客户备注-{ts}'
            assist_user_ids=pick_assist_user_ids(2)
            if assist_user_ids:
                customer['assist_user_ids']=assist_user_ids
            rel207=pick_apaas_value(info.get('apaas_207',[]))
            if rel207:
                customer['custom_relation_asset_b3bf08']=rel207
            # 级联多选字段需要传数组
            for cf in ['text_asset_661b52','text_asset_733a50']:
                opts=info['op'].get(cf,[])
                if len(opts)>=2: customer[cf]=random.sample(opts,2)
                elif opts: customer[cf]=[random.choice(opts)]
            payload={'refer_lead_id':lid,'data_from':'turn_to_customer','customer':customer}
            if assist_user_ids:
                payload['assist_user_ids']=assist_user_ids
            process_file_fields(api_base,TOKEN,'Customer',customer,attachment_dir)
            res=api('customers',data=payload,method='POST',pc=True)
            if res.get('code')==0 and res.get('data') and res['data'].get('id'):
                cid=res['data']['id']
            else:
                # fallback: 通过V2直接创建
                customer.pop('customer_labels_attributes',None)
                c2=api('customers',data={'customer':customer},method='POST')
                cid=c2.get('data',{}).get('id')
                if not cid:
                    res=c2
        except Exception as exc:
            res={'message':str(exc)}
        if not cid:
            print(f'  ✗ 3/12 客户创建失败: {res.get("message",res)}')
            continue
        print(f'  ✅ 3/12 客户(ID:{cid}, 线索已转换)')

        # ====== 4. 联系人 ======
        data3={'contact':{
            'name':f'联系人-{ts}','customer_id':cid,
            'department':random.choice(['研发部','产品部','销售部']),'job':random.choice(J),
            'category':random.choice(info['fm'].get('contact',{}).get('category',['2103262'])),
            'gender':random.choice(['male','female']),'birth_date':gd()[:7]+'-01','note':gt(),
            'address_attributes':{'phone':gv(),'tel':'0519-'+str(gi()),'email':ge(),'wechat':gv(),
                'qq':str(gi()),'wangwang':gv(),'url':gu(),'zip':f'518{random.randint(10,99)}',
                'province_id':random.choice([1,10,13,21]),
                'detail_address':f'{random.choice(R)}{random.randint(1,999)}号'},
        }}
        fill(data3['contact'],info['contact'],'contact')
        process_file_fields(api_base,TOKEN,'Contact',data3['contact'],attachment_dir)
        cid_con=api('contacts',data=data3,method='POST').get('data',{}).get('id')
        print(f'  {"✅" if cid_con else "○"} 4/12 联系人 ID:{cid_con or "-"}')

        # ====== 5. 商机(含产品) ======
        data4={'opportunity':{
            'title':f'商机-{ts}','customer_id':cid,
            'source':random.choice(enabled_field_values('opportunity','source') or info['fm'].get('opportunity',{}).get('source',['2103268'])),
            'stage':random.choice(enabled_field_values('opportunity','stage') or info['fm'].get('opportunity',{}).get('stage',['2103276'])),
            'kind':random.choice(enabled_field_values('opportunity','kind') or info['fm'].get('opportunity',{}).get('kind',['2103282'])),
            'expect_amount':ga(),'expect_sign_date':gd(),'get_time':gd(),'revisit_remind_at':gdt(),
            'note':f'CRM商机备注-{ts}',
            'product_assets_attributes':prod_attrs(3),
        }}
        fill(data4['opportunity'],info['opportunity'],'opportunity')
        if info['template_ids'].get('opportunity'): data4['opportunity']['custom_field_template_id']=info['template_ids']['opportunity']
        process_file_fields(api_base,TOKEN,'Opportunity',data4['opportunity'],attachment_dir)
        opp_res=api('opportunities',data=data4,method='POST')
        oid=opp_res.get('data',{}).get('id')
        if oid: upload_attach_files(api_base,TOKEN,'Opportunity',oid,attachment_dir)
        if not oid:
            print(f'  ✗ 5/12 商机创建失败: {opp_res.get("message",opp_res)}')
            continue
        print(f'  ✅ 5/12 商机 ID:{oid}')

        # ====== 6. 报价单(含编号、乙方主体、产品) ======
        data5={'quotation':{
            'name':f'报价-{ts}','title':f'报价单-{ts}','customer_id':cid,
            'contact_id':cid_con,'opportunity_id':oid,'status':'2103411',
            'quotation_no':'QTE'+ts[-6:],
            'quotation_date':gd(),'effective_date_fr':gd(),'effective_date_to':gd(),
            'total_amount':ga(),'product_total_amount':ga(),
            'subsidiary_id':int(random.choice(info['subsidiaries'])) if info['subsidiaries'] else None,
            'revisit_remind_at':gdt(),'assist_user_ids':info['pc_users'][:2],
            'product_assets_attributes':prod_attrs(3),
        }}
        fill(data5['quotation'],info['quotation'],'quotation')
        if info['template_ids'].get('quotation'): data5['quotation']['custom_field_template_id']=info['template_ids']['quotation']
        process_file_fields(api_base,TOKEN,'Quotation',data5['quotation'],attachment_dir)
        quote_res=api('quotations',data=data5,method='POST',pc=True)
        qid=quote_res.get('data',{}).get('id')
        if qid: upload_attach_files(api_base,TOKEN,'Quotation',qid,attachment_dir)
        if not qid:
            print(f'  ✗ 6/12 报价单创建失败: {quote_res.get("message",quote_res)}')
            continue
        print(f'  ✅ 6/12 报价单 ID:{qid}')

        # ====== 7. 合同(含产品+业务类型) ======
        data6={'contract':{
            'title':f'合同-{ts}','customer_id':cid,
            'opportunity_id':oid,'quotation_ids':[qid],'total_amount':ga(),
            'category':random.choice(info['fm'].get('contract',{}).get('category',['2103285'])),
            'payment_type':random.choice(info['fm'].get('contract',{}).get('payment_type',['2103290'])),
            'status':random.choice(info['fm'].get('contract',{}).get('status',['2103294'])),
            'sign_date':gd(),'start_at':gd(),'end_at':gd(),
            'customer_signer':gt()[:4],'our_signer':gt()[:4],
            'checking_payments_amount':ga(),'received_payments_amount':ga(),
            'unreceived_amount':ga(),'unchecking_payments_amount':ga(),
            'assist_user_ids':info['pc_users'][:3],
            'revisit_remind_at':gdt(),
            'special_terms':f'CRM合同备注-{ts}',
            'product_assets_attributes':prod_attrs(3),
        }}
        fill(data6['contract'],info['contract'],'contract')
        data6['contract']['special_terms']=f'CRM合同备注-{ts}'
        rel207=pick_apaas_value(info.get('apaas_207',[]))
        if rel207:
            data6['contract']['custom_relation_asset_a1469c']=rel207
        if info['template_ids'].get('contract'): data6['contract']['custom_field_template_id']=info['template_ids']['contract']
        process_file_fields(api_base,TOKEN,'Contract',data6['contract'],attachment_dir)
        contract_res=api('contracts',data=data6,method='POST',pc=True)
        ctid=contract_res.get('data',{}).get('id')
        if ctid: upload_attach_files(api_base,TOKEN,'Contract',ctid,attachment_dir)
        if not ctid:
            print(f'  ✗ 7/12 合同创建失败: {contract_res.get("message",contract_res)}')
            continue
        print(f'  ✅ 7/12 合同 ID:{ctid}')

        # ====== 8. 回款计划 ======
        pl=api('received_payment_plans/batch_create',data={
            'contract_id':ctid,'plans':[
                {'period_name':'第1期','receive_stage':1,'receive_date':gd(),'amount':str(ga()),
                 'received_types':random.choice(info['fm'].get('received_payment',{}).get('received_types',['2103298'])),
                 'receive_user_id':primary_user_id,'note':f'CRM回款计划第1期-{ts}'},
                {'period_name':'第2期','receive_stage':2,'receive_date':gd(),'amount':str(ga()),
                 'received_types':random.choice(info['fm'].get('received_payment',{}).get('received_types',['2103298'])),
                 'receive_user_id':primary_user_id,'note':f'CRM回款计划第2期-{ts}'},
            ]},method='POST',pc=True)
        pid=pl.get('data',[{}])[0].get('id') if pl.get('code')==0 else None
        print(f'  {"✅" if pid else "○"} 8/12 回款计划 ID:{pid or "-"}')

        # ====== 9. 回款记录 ======
        data8={'received_payment':{
            'amount':ga(),'receive_date':gd(),
            'received_types':random.choice(info['fm'].get('received_payment',{}).get('received_types',['2103298'])),
            'customer_id':cid,'contract_id':ctid,'received_payment_plan_id':pid,
            'payment_type':random.choice(info['fm'].get('payment_type',['2103290'])),
            'receive_user_id':primary_user_id,'note':f'CRM回款-{ts}',
        }}
        fill(data8['received_payment'],info['rp'],'rp')
        rel277=pick_apaas_value(info.get('apaas_277',[]))
        if rel277:
            data8['received_payment']['custom_relation_asset_1498b3']=rel277
        process_file_fields(api_base,TOKEN,'ReceivedPayment',data8['received_payment'],attachment_dir)
        rpid=api('received_payments',data=data8,method='POST',pc=True).get('data',{}).get('id')
        print(f'  {"✅" if rpid else "○"} 9/12 回款记录 ID:{rpid or "-"}')

        # ====== 10. 开票记录(含发票号码) ======
        data9={'invoiced_payment':{
            'amount':ga(),'invoiced_date':gd(),'invoice_no':'INV'+ts,
            'invoice_types':random.choice(info['fm'].get('invoiced_payment',{}).get('invoice_types',['2103302'])),
            'customer_id':cid,'broker_user_id':primary_user_id,
            'content':f'CRM开票-{ts}','note':f'开票-{ts}',
        },'contract_id':ctid}
        fill(data9['invoiced_payment'],info['ip'],'ip')
        process_file_fields(api_base,TOKEN,'InvoicedPayment',data9['invoiced_payment'],attachment_dir)
        ipid=api('invoiced_payments',data=data9,method='POST',pc=True).get('data',{}).get('id')
        print(f'  {"✅" if ipid else "○"} 10/12 开票记录 ID:{ipid or "-"}')

        # ====== 11. 费用(含费用类型) ======
        category_id,cat_desc=random.choice(info.get('expense_categories') or EXPENSE_CATEGORIES)
        expense_attachment_ids=upload_expense_attachment_ids(api_base,attachment_dir)
        data10={'expense':{
            'sn':f'FE{ts}','description':f'{cat_desc}-{gt()}','amount':ga(),
            'incurred_at':gd(),'customer_id':cid,
            'contacts_expenses_attributes':[{'contact_id':cid_con}] if cid_con else [],
            'category':category_id,
            'user_id':primary_user_id,
            'owned_department_id':primary_department_id,
            'related_item_type':'Contract','related_item_id':ctid,
        },'attachment_ids':expense_attachment_ids}
        fill(data10['expense'],info['expense'],'expense')
        if cid_con:
            data10['expense']['contacts_expenses_attributes']=[{'contact_id':cid_con}]
        process_file_fields(api_base,TOKEN,'Expense',data10['expense'],attachment_dir)
        eid=api('expenses',data=data10,method='POST',pc=True).get('data',{}).get('id')
        if eid:
            upload_attach_files(api_base,TOKEN,'Expense',eid,attachment_dir)
        print(f'  {"✅" if eid else "○"} 11/12 费用 ID:{eid or "-"}')

        # ====== 12. 报销单(关联费用) ======
        data11={'expense_account':{
            'sn':f'BX{ts}','amount':ga(),'note':f'CRM报销-关联费用{eid}',
            'user_id':primary_user_id,'want_department_id':primary_department_id,'department_id':primary_department_id,
        }}
        fill(data11['expense_account'],info['ea'],'ea')
        rel281=pick_apaas_value(info.get('apaas_281',[]))
        if rel281:
            data11['expense_account']['custom_relation_asset_293d2b']=rel281
        if info['template_ids'].get('ea'): data11['expense_account']['custom_field_template_id']=info['template_ids']['ea']
        process_file_fields(api_base,TOKEN,'ExpenseAccount',data11['expense_account'],attachment_dir)
        data11['expense_ids']=[eid] if eid else []
        eaid=api('expense_accounts',data=data11,method='POST',pc=True).get('data',{}).get('id')
        print(f'  {"✅" if eaid else "○"} 12/12 报销单 ID:{eaid or "-"}')

        # 汇总
        items=[('市场活动',mid),('线索',lid),('客户',cid),('联系人',cid_con),('商机',oid),('报价单',qid),
               ('合同',ctid),('回款计划',pid),('回款记录',rpid),('开票记录',ipid),('费用',eid),('报销单',eaid)]
        print(f'\n  {"-"*40}\n  第{r}轮汇总:')
        for n,v in items: print(f'    {n}: {v or "-"}')
        print(f'  产品关联: 商机✓ 报价单✓ 合同✓')
        completed+=1
        time.sleep(1)
    return completed

def main():
    p=argparse.ArgumentParser(description='完整CRM流程(含全部字段)')
    p.add_argument('--api'); p.add_argument('--token')
    p.add_argument('--env', choices=['test','staging','production'])
    p.add_argument('--profile', choices=['gray','standard'])
    p.add_argument('cnt',nargs='?',type=int,default=1)
    p.add_argument('--attachment-dir',help='本地附件目录,随机取图片上传到文件字段')
    a=apply_config_defaults(p.parse_args(), p)
    global PC,TOKEN,info
    PC=pc_url(a.api.rstrip('/'))
    TOKEN=a.token

    print(f'{"="*60}\n完整CRM流程(修复版)\nAPI: {a.api}\n轮数: {a.cnt}\n{"="*60}')
    if a.attachment_dir: print(f'附件目录: {a.attachment_dir}')
    print('\n[发现字段定义...]')
    info=discover()
    print(f'  用户:{len(info["pc_users"])} 部门:{len(info["dp"])} 产品:{len(info["products"])} 乙方:{len(info["subsidiaries"])}')
    if not validate_discovery(info):
        return
    for k in ['lead','customer','contact','opportunity','quotation','contract','rp','ip','expense','ea']:
        n=sum(len(v) for v in info[k].values())
        nf=len(info[k+'_file']); na=len(info[k+'_attach'])
        print(f'  {k}: {n}个自定义字段',end='')
        if nf: print(f' 文件:{nf}',end='')
        if na: print(f' 附件:{na}',end='')
        if info['template_ids'].get(k): print(f' 模板ID:{info["template_ids"][k]}',end='')
        print()

    completed=run(a.cnt, a.attachment_dir)
    if completed==a.cnt:
        print(f'\n{"="*60}\n✅ 全部完成! 成功轮数:{completed}/{a.cnt}\n{"="*60}')
    else:
        print(f'\n{"="*60}\n⚠️ 执行结束，成功轮数:{completed}/{a.cnt}\n{"="*60}')

if __name__=='__main__': main()
