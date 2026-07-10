#!/usr/bin/env python3
"""线索转客户 - PC端点完整转换(字段映射)
使用: python3 turn_lead_to_customer.py --api URL --token TOKEN --new
      python3 turn_lead_to_customer.py --api URL --token TOKEN --lead-id ID
"""
import requests, json, random, string, argparse, time
from datetime import datetime, timedelta

ROADS = ['科技路','创新路','发展大道','人民路','建设路','中山路','解放路','高新路','创业路']
def rp(): return random.choice(['138','139','150','151','186','187','188','189'])+''.join(random.choices(string.digits,k=8))
def re(): return ''.join(random.choices(string.ascii_lowercase,k=8))+'@'+random.choice(['qq.com','163.com','126.com','gmail.com'])
def ru(): return 'https://www.'+''.join(random.choices(string.ascii_lowercase,k=10))+'.com'
def rt(): return ''.join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime("%Y-%m-%d")

def fetch(api,path,token,pc=False):
    base=api.rstrip('/')+('/api/pc' if pc else '/api/v2')
    return requests.get(f"{base}/{path.lstrip('/')}",headers={'Authorization':f'Token token={token}'},timeout=15).json()

def get_template_id(api,token):
    try:
        cf=fetch(api,'custom_fields?model_klass=Customer',token,pc=True)
        for g in cf.get('data',{}).get('custom_field_groups',[]):
            for f in g.get('custom_fields',[]):
                fid=f.get('field_id')
                if fid and len(str(fid))>=5:
                    detail=fetch(api,f'custom_fields/{fid}',token,pc=True)
                    for t in detail.get('data',{}).get('custom_field_templates',[]):
                        if t.get('status')=='enable': return t['id']
    except: pass
    return 1331

def discover_fields(api,token,klass):
    """发现字段定义，返回按标签+类型索引的映射表"""
    cf=fetch(api,f'custom_fields?model_klass={klass}',token,pc=True)
    result={}
    for g in cf.get('data',{}).get('custom_field_groups',[]):
        for f in g.get('custom_fields',[]):
            n=f.get('name',''); lb=f.get('label',''); ft=f.get('field_type',''); fid=f.get('field_id')
            if n.startswith('address.') or n.startswith('subform_') or n.startswith('file_asset'): continue
            if ft in ['field_map_field','select2_field','labels_field','address_select']: continue
            # 用标签+类型作为key
            key=f"{lb}__{ft}"
            result[key]={
                'name':n,'label':lb,'type':ft,'field_id':fid,
                'required':f.get('required',False)
            }
    return result

def build_field_mapping(lead_fields,customer_fields):
    """通过标签+类型建立线索→客户字段名映射"""
    mapping={}  # lead_field_name → customer_field_name
    # 先按标签精确匹配
    for key,cinfo in customer_fields.items():
        if key in lead_fields:
            linfo=lead_fields[key]
            mapping[linfo['name']]=cinfo['name']
    # 处理遗留字段: 一些特殊的映射
    special_map={
        'custom_field_template_id':'custom_field_template_id',
        'department':'department','job':'job',
    }
    # 按keyword匹配
    keywords={
        '新增单行文本':'新增单行文本','新增邮箱':'新增邮箱','新增手机':'新增手机',
        '新增多行文本':'新增多行文本','新增整数':'新增整数','新增小数':'新增小数',
        '新增金额':'新增金额','新增时间':'新增时间','新增日期':'新增日期',
        '新增单选下拉':'新增单选下拉','新增多选下拉':'新增多选下拉',
        '新增自动编号':'新增自动编号','新增链接':'新增链接','新增级联':'新增级联',
        '新增用户单选':'新增用户单选','新增用户多选':'新增用户多选',
        '新增部门单选':'新增部门单选','新增部门多选':'新增部门多选',
        '级联多选':'级联多选','拜访计划':'测试','apaas新表单':'apaas新表单',
        '客户类型':'客户类型','所属行业':'所属行业',
    }
    # 按标签loose匹配
    for lk,lv in lead_fields.items():
        for ck,cv in customer_fields.items():
            # 标签部分匹配
            ll=lv['label']; cl=cv['label']
            if ll and cl and (ll[:3] in cl or cl[:3] in ll):
                if lv['type']==cv['type']:
                    mapping[lv['name']]=cv['name']
    return mapping

def main():
    p=argparse.ArgumentParser(description='线索转客户(字段映射)')
    p.add_argument('--api',required=True); p.add_argument('--token',required=True)
    p.add_argument('--new',action='store_true'); p.add_argument('--lead-id',type=int,default=0)
    a=p.parse_args()
    api=a.api.rstrip('/')
    api_pc=api.replace('//lxcrm-staging.','//lxcrm-api-staging.').replace('//lxcrm-test.','//lxcrm-api-test.')
    token=a.token
    H={'Content-Type':'application/json','Authorization':f'Token token={token}'}
    v2=f"{api}/api/v2"
    print('='*70); print('线索转客户(字段映射)'); print('='*70)

    # Step 1: 创建/获取线索
    if a.new:
        print('\n[1/4] 创建完整线索...')
        import batch_create_lead
        info=batch_create_lead.discover(api,token)
        data=batch_create_lead.build(info)
        data['name']='转客户线索-'+datetime.now().strftime('%H%M%S')
        data['company_name']='转客户'+rt()+'科技'; data['note']='线索转客户测试'
        data['approve_status']='approved'
        r=requests.post(f"{v2}/leads",headers=H,json={'lead':data})
        lid=r.json()['data']['id']
        print(f'  ✅ 线索ID: {lid}')
    else:
        lid=a.lead_id; r=requests.get(f'{v2}/leads/{lid}',headers=H)
        lid=a.lead_id; ld=requests.get(f'{v2}/leads/{lid}',headers=H).json().get("data",{})
        if ld.get("id"): print(f'  线索: {ld.get("name")}')

    # Step 2: 获取线索详情
    print('\n[2/4] 获取线索详情...')
    lead=requests.get(f'{v2}/leads/{lid}',headers=H).json().get('data',{})

    # Step 3: 发现字段并建立映射
    print('[3/4] 发现字段定义+建立映射...')
    lead_fs=discover_fields(api,token,'Lead')
    cust_fs=discover_fields(api,token,'Customer')
    mapping=build_field_mapping(lead_fs,cust_fs)
    print(f'  映射规则: {len(mapping)}条')

    # Step 4: 获取转换表单并注入字段值
    tid=get_template_id(api,token)
    print(f'[4/4] 获取转换表单+注入字段值+POST...(模板ID:{tid})')
    form=fetch(api_pc,f'leads/{lid}/turn_to_customer?custom_field_template_id={tid}',token,pc=True)
    if form.get('code')!=0: print(f'  ✗ {form.get("message","?")}'); return
    data=form.get('data',{})
    customer=data.get('customer',{})

    # === 填充客户字段值 ===
    # 特殊映射: 线索的"姓名"→客户的"客户名称"
    lead_name=lead.get('name')
    if lead_name and not customer.get('name'):
        customer['name']=lead_name

    # 1. 系统字段 - 随机取customer自己的field_map选项值
    cust_fm=requests.get(f"{v2}/field_maps/customer",headers=H).json()
    cust_fm_opts={}
    for f in cust_fm.get('data',{}).get('customer',[]):
        fn=f.get('field_name')
        vals=[v for v in f.get('field_values',[]) if v.get('status')=='enable']
        if vals: cust_fm_opts[fn]=[str(v['id']) for v in vals]

    for fk in ['name','company_name']:
        lv=lead.get(fk,'')
        if lv: customer[fk]=lv
    for fk in ['status','category','source','industry','staff_size','channel']:
        opts=cust_fm_opts.get(fk,[])
        if opts: customer[fk]=random.choice(opts)
    customer['custom_field_template_id']=tid
    customer['approve_status']='approved'
    lrt=lead.get('revisit_remind_at')
    customer['revisit_remind_at']=lrt if lrt else (datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d %H:%M")

    # 2. 自定义字段 - 按映射传入线索值(跳过下拉/级联类型，让随机填充从API获取正确选项)
    skip_types={'select','multi_select','nested_select_field','multi_nested_select_field'}
    lname2cname={}
    for lname,cname in mapping.items():
        lv=lead.get(lname)
        ft=lead_fs.get(f"{lead_fs.get(f'___{lname}')}__",{})  # can't get type easily, use a lookup
        if lv is not None and lv!='' and lv!=[]:
            # store the mapping for later type check
            lname2cname[lname]=cname

    # Build reverse lookup: cname → field type
    cname_to_type={cinfo['name']:cinfo['type'] for cinfo in cust_fs.values()}

    for lname,cname in mapping.items():
        lv=lead.get(lname)
        if lv is not None and lv!='' and lv!=[]:
            ft=cname_to_type.get(cname,'')
            if ft in skip_types:
                continue  # skip, will be filled by random fill with correct API options
            customer[cname]=lv

    # 3. 客户特有的字段 - 从API获取正确选项值填充
    customer_filled=set(customer.keys())
    # 获取所有客户下拉字段的选项值
    cust_opts={}
    for key,cinfo in cust_fs.items():
        cn=cinfo['name']
        if cn in customer_filled: continue
        fid=cinfo.get('field_id')
        if fid and cinfo['type'] in ['select','multi_select','nested_select_field','multi_nested_select_field']:
            try:
                detail=requests.get(f"{api_pc}/api/pc/custom_fields/{fid}?custom_field_template_id={tid}",headers=H,timeout=10).json()
                sel_opts=detail.get('data',{}).get('options',{}).get('select_options',[])
                values=[]
                for o in sel_opts:
                    if isinstance(o,list) and len(o)==2: values.append(o[1])
                    elif isinstance(o,dict): values.append(o.get('value',''))
                values=[v for v in values if v]
                if values: cust_opts[cn]=values
            except: pass

    for key,cinfo in cust_fs.items():
        cn=cinfo['name']
        if cn in customer_filled: continue
        ft=cinfo['type']
        opts=cust_opts.get(cn,[])
        if ft=='text_field': customer[cn]=rt()
        elif ft=='text_area': customer[cn]=rt()*3
        elif ft=='email_field': customer[cn]=re()
        elif ft=='mobile_field': customer[cn]=rp()
        elif ft=='url_field': customer[cn]=ru()
        elif ft=='number_field': customer[cn]=ri()
        elif ft=='currency_field': customer[cn]=rd()
        elif ft=='datetime_field': customer[cn]=rf()
        elif ft=='select' and opts: customer[cn]=random.choice(opts)
        elif ft=='multi_select' and len(opts)>=2: customer[cn]=random.sample(opts,random.randint(2,min(4,len(opts))))
        elif ft=='multi_select' and opts: customer[cn]=[random.choice(opts)]
        elif ft=='nested_select_field' and opts: customer[cn]=random.choice(opts)
        elif ft=='multi_nested_select_field' and len(opts)>=2: customer[cn]=random.sample(opts,2)
        elif ft=='multi_nested_select_field' and opts: customer[cn]=[random.choice(opts)]
        elif ft=='user_field' and lead.get('user_field_asset_03be5a'): customer[cn]=[lead['user_field_asset_03be5a'][0]]
        elif ft=='multi_user_field' and lead.get('user_field_asset_9a4657'): customer[cn]=lead['user_field_asset_9a4657'][:3]
        elif ft=='department_field': customer[cn]=lead.get('user_field_asset_3b1490',['5013377'])
        elif ft=='multi_department_field': customer[cn]=lead.get('user_field_asset_29bf74',['5013377','5013378'])
        elif ft=='custom_relation_field':
            # 用已知有效ID
            known_ids={'custom_relation_asset_b3bf08':['17','65','83','97'],
                       'custom_relation_asset_bdd62a':['7']}
            ids=known_ids.get(cn,['1'])
            customer[cn]=random.choice(ids)
        elif ft=='text_field': customer[cn]=rt()

    # 构建payload - PC接口只负责创建客户，联系人和商机单独创建
    payload={'refer_lead_id':lid,'data_from':'turn_to_customer','customer':customer,
        'contacts_attributes':[],'contact_assetships_attributes':[],'opportunity_id':0,
        'address_attributes':data.get('address_attributes',{}),
        'user_id':data.get('user_id',''),'want_department_id':data.get('want_department_id',''),
        'subsidiary_id':'','subsidiary_users_attributes':[],'assist_user_ids':[]}

    # 地址 - 从线索填充
    laddr=lead.get('address',{})
    if laddr.get('phone') or laddr.get('email') or laddr.get('detail_address'):
        new_addr={}
        for ak in ['detail_address','phone','tel','email','wechat','qq','wangwang','fax','zip','url']:
            av=laddr.get(ak)
            if av: new_addr[ak]=av
        # 地区
        province_id=laddr.get('province_id') or laddr.get('province',{}).get('id')
        city_id=laddr.get('city_id') or laddr.get('city',{}).get('id')
        district_id=laddr.get('district_id') or laddr.get('district',{}).get('id')
        if province_id: new_addr['province_id']=province_id
        if city_id: new_addr['city_id']=city_id
        if district_id: new_addr['district_id']=district_id
        payload['address_attributes']=new_addr
        customer['address_attributes']=new_addr

    r=requests.post(f'{api_pc}/api/pc/customers',headers=H,json=payload)
    try: res=r.json()
    except: print(f'  ✗ 非JSON'); return
    if res.get('code')!=0: print(f'  ✗ {res.get("message","?")[:100]}'); return
    cid=res['data']['id']; print(f'  ✅ 客户ID: {cid}')
    time.sleep(0.3)

    # 验证
    nl=requests.get(f'{v2}/leads/{lid}',headers=H).json().get('data',{})
    c=requests.get(f'{v2}/customers/{cid}',headers=H).json().get('data',{})

    # 创建联系人(含字段映射)
    laddr=lead.get('address',{})
    con_name=lead.get('name','联系人')
    con_phone=laddr.get('phone') or rp()
    con_email=laddr.get('email') or re()
    con_data={'contact':{'name':con_name,'phone':con_phone,'email':con_email,
        'customer_id':cid,'department':lead.get('department',''),'job':lead.get('job',''),
        'address_attributes':{k:laddr.get(k) for k in ['detail_address','phone','tel','email','wechat','qq','wangwang','fax','zip','url'] if laddr.get(k)}}}
    # 映射联系人的自定义字段
    con_fs=discover_fields(api,token,'Contact')
    con_lname2cname={}
    con_cname2type={}
    for lk,lv in lead_fs.items():
        for ck,cv in con_fs.items():
            if lv['label']==cv['label'] and lv['type']==cv['type']:
                con_lname2cname[lv['name']]=cv['name']
                con_cname2type[cv['name']]=cv['type']
    skip_con_types={'select','multi_select','nested_select_field','multi_nested_select_field'}
    for lname,cname in con_lname2cname.items():
        lv=lead.get(lname)
        if lv is not None and lv!='' and lv!=[]:
            ft=con_cname2type.get(cname,'')
            if ft in skip_con_types: continue
            con_data['contact'][cname]=lv
    # 联系人下拉字段补充
    for key,cinfo in con_fs.items():
        cn=cinfo['name']
        if cn in con_data['contact'] or cn in ['name','customer_id','department','job']: continue
        ft=cinfo['type']; fid=cinfo.get('field_id')
        opts=[]
        if fid and ft in ('select','multi_select','nested_select_field','multi_nested_select_field'):
            try:
                d=requests.get(f"{api_pc}/api/pc/custom_fields/{fid}?custom_field_template_id={tid}",headers=H,timeout=10).json()
                sel=d.get('data',{}).get('options',{}).get('select_options',[])
                for o in sel:
                    if isinstance(o,list) and len(o)==2: opts.append(o[1])
                    elif isinstance(o,dict): opts.append(o.get('value',''))
                opts=[v for v in opts if v]
            except: pass
        if ft=='text_field': con_data['contact'][cn]=rt()
        elif ft=='text_area': con_data['contact'][cn]=rt()*3
        elif ft=='email_field': con_data['contact'][cn]=con_email or re()
        elif ft=='mobile_field': con_data['contact'][cn]=con_phone or rp()
        elif ft=='url_field': con_data['contact'][cn]=ru()
        elif ft=='number_field': con_data['contact'][cn]=ri()
        elif ft=='currency_field': con_data['contact'][cn]=rd()
        elif ft=='datetime_field': con_data['contact'][cn]=rf()
        elif ft=='date_field': con_data['contact'][cn]=rf()[:10]
        elif ft=='select' and opts: con_data['contact'][cn]=random.choice(opts)
        elif ft=='multi_select' and len(opts)>=2: con_data['contact'][cn]=random.sample(opts,random.randint(2,min(4,len(opts))))
        elif ft=='nested_select_field' and opts: con_data['contact'][cn]=random.choice(opts)
        elif ft=='multi_nested_select_field' and len(opts)>=2: con_data['contact'][cn]=random.sample(opts,2)
        elif ft=='user_field' and lead.get('user_field_asset_03be5a'): con_data['contact'][cn]=[lead['user_field_asset_03be5a'][0]]
        elif ft=='multi_user_field' and lead.get('user_field_asset_9a4657'): con_data['contact'][cn]=lead['user_field_asset_9a4657'][:3]
        elif ft=='department_field': con_data['contact'][cn]=lead.get('user_field_asset_3b1490',['5013377'])
        elif ft=='multi_department_field': con_data['contact'][cn]=lead.get('user_field_asset_29bf74',['5013377','5013378'])
        elif ft=='custom_relation_field': con_data['contact'][cn]='1'
    con_res=requests.post(f'{v2}/contacts',headers=H,json=con_data).json()
    if con_res.get('code')==0:
        print(f'  ✅ 联系人创建成功: {con_name}')
    else:
        print(f'  ⚠️ 联系人创建失败: {con_res.get("message","")[:60]}')

    # 创建商机
    opp_title=f"商机-{lead.get('name','')}" or '商机-'+datetime.now().strftime('%H%M%S')
    opp_data={'opportunity':{'title':opp_title,'customer_id':cid,'source':'2103268',
        'stage':'2103276','expect_amount':random.randint(10000,500000),'note':f'来自线索{lid}转换'}}
    opp_res=requests.post(f'{v2}/opportunities',headers=H,json=opp_data).json()
    if opp_res.get('code')==0:
        print(f'  ✅ 商机创建成功: {opp_title}')
    else:
        print(f'  ⚠️ 商机创建失败: {opp_res.get("message","")[:60]}')

    # 统计映射后的字段
    mapped=0
    for lname,cname in mapping.items():
        lv=lead.get(lname)
        cv=c.get(cname)
        if lv and cv and lv!='' and cv!='' and lv!=[] and cv!=[] and lv!={} and cv!={}:
            mapped+=1

    print(f'\n{"="*70}')
    print('转换验证')
    print('='*70)
    print(f'  线索 {lid} -> 客户 {cid}')
    print(f'  turned_to_customer: {nl.get("turned_to_customer")}')
    print(f'  turned_customer_name: {nl.get("turned_to_customer_name")}')
    print(f'  字段映射: {mapped}/{len(mapping)} 映射成功')
    print(f'  客户: {c.get("name")} | 联系人: {len(c.get("contacts",[]))}个')
    addr=c.get('address',{}); print(f'  地区: {addr.get("region_info","-")}')
    print(f'\n✅ 完成!')

if __name__=='__main__': main()
