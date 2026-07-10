#!/usr/bin/env python3
"""编辑客户 - 所有字段值不能和编辑前一样
使用: python3 /tmp/edit_customer.py --api https://xxx.com --token xxx --id 客户ID
"""
import requests,json,random,string,argparse
from datetime import datetime,timedelta

def fetch(api,path,token,pc=False):
    base=api.rstrip("/")+("/api/pc" if pc else "/api/v2")
    r=requests.get(f"{base}/{path.lstrip('/')}",headers={"Authorization":f"Token token={token}"},timeout=15)
    return r.json()

def get_old_values(api,token,cid):
    """获取当前值"""
    r=requests.get(f"{api}/api/v2/customers/{cid}",headers={"Authorization":f"Token token={token}"})
    return r.json().get("data",{})

def choose_diff(opts,old):
    """选一个和旧值不同的选项"""
    candidates=[o for o in opts if o!=old]
    return random.choice(candidates) if candidates else old

def choose_diff_list(opts,old_list,count):
    """选count个和旧列表不同的值"""
    old_set=set(old_list) if old_list else set()
    candidates=[o for o in opts if o not in old_set]
    if len(candidates)>=count: return random.sample(candidates,count)
    return random.sample(opts,count) if opts else []

def rp(): return random.choice(["138","139","150","151","186","187","188","189"])+"".join(random.choices(string.digits,k=8))
def re(): return "".join(random.choices(string.ascii_lowercase,k=8))+"@"+random.choice(["qq.com","163.com","126.com","gmail.com"])
def ru(): return "https://www."+"".join(random.choices(string.ascii_lowercase,k=10))+".com"
def rt(): return "".join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime("%Y-%m-%d")
ROADS=["科技路","创新路","发展大道","人民路","建设路","中山路","解放路","高新路","创业路","工业路","商务大道","文化路","学府路","江南大道","花园路"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api",required=True)
    p.add_argument("--token",required=True)
    p.add_argument("--id",required=True,type=int)
    a=p.parse_args()

    api=a.api.rstrip("/")
    token=a.token

    # 获取当前值
    print("读取当前客户值...")
    old=get_old_values(api,token,a.id)
    if not old.get("id"):
        print("客户不存在"); return

    # 自动发现选项
    print("自动发现字段选项...")
    cf=fetch(api,"custom_fields?model_klass=Customer",token,pc=True)
    
    # 构建选项映射
    info={}
    ft_map={"select":"sel","multi_select":"ms","nested_select_field":"cas","multi_nested_select_field":"mcas",
            "text_field":"txt","text_area":"txt","number_field":"num","currency_field":"num",
            "email_field":"eml","mobile_field":"mob","url_field":"url","datetime_field":"dt",
            "user_field":"usr","multi_user_field":"m_usr","department_field":"dept",
            "multi_department_field":"m_dept","custom_relation_field":"rel"}
    info["fields"]={t:[] for t in ft_map.values()}
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            n=f.get("name",""); ft=f.get("field_type",""); fid=f.get("field_id"); lb=f.get("label","")
            if n in ["name","company_name","note","parent","status","category","source","industry","staff_size","channel","labels","revisit_remind_at","number","beginning_payments_amount"]: continue
            if n.startswith("address.") or n.startswith("subform_") or n.startswith("file_asset"): continue
            t=ft_map.get(ft,"txt")
            info["fields"][t].append({"name":n,"label":lb,"fid":fid})

    info["opts"]={}
    for entry in info["fields"]["sel"]+info["fields"]["ms"]+info["fields"]["cas"]+info["fields"]["mcas"]:
        fid=entry["fid"]
        if not fid: continue
        detail=fetch(api,f"custom_fields/{fid}?custom_field_template_id={old.get('custom_field_template_id') or 1331}",token,pc=True)
        opts=detail.get("data",{}).get("options",{}).get("select_options",[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict):
                v=o.get("value","")
                if v: values.append(v)
        if values: info["opts"][entry["name"]]=values

    # 系统字段选项
    fm=fetch(api,"field_maps/customer",token)
    info["fm_opts"]={}
    for f in fm.get("data",{}).get("customer",[]):
        vals=[v for v in f.get("field_values",[]) if v.get("status")=="enable"]
        if vals: info["fm_opts"][f["field_name"]]=[str(v["id"]) for v in vals]

    # 用户/部门/标签
    us=fetch(api,"user/simple_list?per_page=50",token)
    info["users"]=[u["value"] for u in us.get("simple_users",[]) if u.get("value") and u.get("value")!=""]
    dp=fetch(api,"departments",token)
    info["depts"]=[str(d["id"]) for d in dp.get("data",{}).get("departments",[]) if d.get("id")]
    lb=fetch(api,"labels",token)
    info["labels"]=[{"label_id":l["id"],"label_group_id":g["group_id"]} for g in lb.get("data",{}).get("label_groups",[]) for l in g.get("labels",[])]

    # 构建编辑数据
    print("生成编辑后值...")
    data={}

    # 系统字段 - 换不同选项
    for fk in ["status","category","source","industry","staff_size","channel"]:
        opts=info["fm_opts"].get(fk,[])
        old_v=str(old.get(fk,""))
        if opts: data[fk]=choose_diff(opts,old_v)

    # 业务类型不变（不能随便换）
    # 下次跟进时间
    old_rt=old.get("revisit_remind_at","")
    while True:
        new_rt=(datetime.now()+timedelta(days=random.randint(1,14))).strftime("%Y-%m-%d %H:%M")
        if new_rt!=old_rt: break
    data["revisit_remind_at"]=new_rt

    # 标签 - 换不同的
    old_label_ids=[l["id"] for l in old.get("labels",[])]
    new_labels=[]
    for l in info["labels"]:
        if l["label_id"] not in old_label_ids:
            new_labels.append(l)
    if new_labels:
        data["customer_labels_attributes"]=random.sample(new_labels,min(3,len(new_labels)))

    # 地址 - 更新为新值
    old_addr=old.get("address",{})
    while True:
        new_phone=rp()
        if new_phone!=old_addr.get("phone",""): break
    data["address_attributes"]={
        **random.choice([{"province_id":1,"city_id":1,"district_id":4},{"province_id":10,"city_id":77,"district_id":0},{"province_id":13,"city_id":122,"district_id":1106},{"province_id":21,"city_id":231,"district_id":3380}]),
        "detail_address":f"{random.choice(ROADS)}{random.randint(1,999)}号",
        "phone":new_phone,"tel":f"0519-{''.join(random.choices(string.digits,k=8))}",
        "email":re(),"url":ru(),"wechat":rp(),"qq":str(random.randint(10000000,999999999)),
        "wangwang":rp(),"fax":f"0519-{''.join(random.choices(string.digits,k=8))}", "zip":f"518{random.randint(0,99):02d}"
    }

    # 文本
    for f in info["fields"]["txt"]+info["fields"]["eml"]+info["fields"]["mob"]+info["fields"]["url"]:
        if f["name"]=="number": data[f["name"]]=rt()
    
    # 邮箱-换新值
    for f in info["fields"]["eml"]: data[f["name"]]=re()
    # 手机-换新值
    for f in info["fields"]["mob"]: data[f["name"]]=rp()
    # 链接-换新值
    for f in info["fields"]["url"]: data[f["name"]]=ru()
    # 文本
    for f in info["fields"]["txt"]: data[f["name"]]=rt()
    # 数字
    for f in info["fields"]["num"]:
        data[f["name"]]=rd() if "金额" in f["label"] or "币" in f["label"] else ri()
    # 时间
    for f in info["fields"]["dt"]: data[f["name"]]=rf()

    # 单选下拉
    for f in info["fields"]["sel"]:
        opts=info["opts"].get(f["name"],[])
        if opts: data[f["name"]]=choose_diff(opts,old.get(f["name"],""))

    # 多选下拉
    for f in info["fields"]["ms"]:
        opts=info["opts"].get(f["name"],[])
        old_v=old.get(f["name"],[])
        if opts: data[f["name"]]=choose_diff_list(opts,old_v,random.randint(2,min(4,len(opts))))

    # 级联单选
    for f in info["fields"]["cas"]:
        opts=info["opts"].get(f["name"],[])
        if opts: data[f["name"]]=choose_diff(opts,old.get(f["name"],""))

    # 级联多选
    for f in info["fields"]["mcas"]:
        opts=info["opts"].get(f["name"],[])
        old_v=old.get(f["name"],[])
        if opts: data[f["name"]]=choose_diff_list(opts,old_v,2)

    # 用户
    old_u=old.get("user_field_asset_2b4662",[]) or []
    cand=[u for u in info["users"] if u not in old_u]
    if cand: data["user_field_asset_2b4662"]=random.sample(cand,1)
    old_um=old.get("user_field_asset_50ed26",[]) or []
    cand_m=[u for u in info["users"] if u not in old_um]
    if cand_m: data["user_field_asset_50ed26"]=random.sample(cand_m,min(3,len(cand_m)))

    # 部门
    old_db=old.get("user_field_asset_b581ec",[]) or []
    cand_db=[d for d in info["depts"] if d not in old_db]
    if cand_db: data["user_field_asset_b581ec"]=random.sample(cand_db,1)
    old_de=old.get("user_field_asset_e53dff",[]) or []
    cand_de=[d for d in info["depts"] if d not in old_de]
    if len(cand_de)>=2: data["user_field_asset_e53dff"]=random.sample(cand_de,2)
    old_d2=old.get("user_field_asset_2b77c3",[]) or []
    cand_d2=[d for d in info["depts"] if d not in old_d2]
    if cand_d2: data["user_field_asset_2b77c3"]=random.sample(cand_d2,1)

    # 数据关联 - 使用已知有效ID，切换为不同的值
    rel_valid_ids={'custom_relation_asset_b3bf08':['17','65'],'custom_relation_asset_bdd62a':['7']}
    for f in info["fields"]["rel"]:
        fname=f["name"]
        old_v=str(old.get(fname,""))
        valid_ids=rel_valid_ids.get(fname,[])
        cand=[v for v in valid_ids if v!=old_v]
        if cand: data[fname]=random.choice(cand)

    # 执行编辑（PUT请求）
    print(f"编辑客户 ID:{a.id}...")
    r=requests.put(f"{api}/api/v2/customers/{a.id}",
        headers={"Content-Type":"application/json","Authorization":f"Token token={token}"},
        json={"customer":data},timeout=30)
    res=r.json()
    
    if res.get("code")==0:
        print(f"✅ 编辑成功!")
        # 验证
        r2=requests.get(f"{api}/api/v2/customers/{a.id}",headers={"Authorization":f"Token token={token}"})
        new=r2.json().get("data",{})
        changed=0
        for k in ["status_mapped","category_mapped","source_mapped","industry_mapped","staff_size_mapped","channel_mapped",
                  "text_asset_67eef7","text_asset_87f993","text_asset_65a3b9","text_asset_cc11bf",
                  "text_asset_06ea8a","text_asset_ed815c"]:
            old_val=str(old.get(k,""))
            new_val=str(new.get(k,""))
            s="✓" if old_val!=new_val else "○"
            if old_val!=new_val: changed+=1
            print(f'  {s} {k}: {old_val[:30]} -> {new_val[:30]}')
        print(f"\n已变更: {changed} 个字段")
    else:
        print(f"✗ 编辑失败: {res.get('message','?')}")

if __name__=="__main__": main()
