#!/usr/bin/env python3
"""编辑线索 - 所有字段值不能和编辑前一样
使用: python3 edit_lead.py --api https://xxx.com --token xxx --id 线索ID"""
import requests,json,random,string,argparse
from datetime import datetime,timedelta

def fetch(api,path,token,pc=False):
    base=api.rstrip("/")+("/api/pc" if pc else "/api/v2")
    r=requests.get(f"{base}/{path.lstrip('/')}",headers={"Authorization":f"Token token={token}"},timeout=15)
    return r.json()

def choose_diff(opts,old): return random.choice([o for o in opts if o!=old]) if [o for o in opts if o!=old] else old

def choose_diff_list(opts,old_list,count):
    old_set=set(old_list) if old_list else set()
    candidates=[o for o in opts if o not in old_set]
    if len(candidates)>=count: return random.sample(candidates,count)
    return random.sample(opts,count) if opts else []

ROADS=["科技路","创新路","发展大道","人民路","建设路","中山路","解放路","高新路","创业路","工业路","商务大道","文化路","学府路","江南大道","花园路"]
def rp(): return random.choice(["138","139","150","151","186","187","188","189"])+"".join(random.choices(string.digits,k=8))
def re(): return "".join(random.choices(string.ascii_lowercase,k=8))+"@"+random.choice(["qq.com","163.com","126.com","gmail.com"])
def ru(): return "https://www."+"".join(random.choices(string.ascii_lowercase,k=10))+".com"
def rt(): return "".join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime("%Y-%m-%d")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api",required=True); p.add_argument("--token",required=True)
    p.add_argument("--id",required=True,type=int)
    a=p.parse_args()
    api=a.api.rstrip("/"); token=a.token

    print("读取当前线索值...")
    r=requests.get(f"{api}/api/v2/leads/{a.id}",headers={"Authorization":f"Token token={token}"})
    old=r.json().get("data",{})
    if not old.get("id"): print("线索不存在"); return

    # 发现字段
    print("自动发现字段选项...")
    cf=fetch(api,"custom_fields?model_klass=Lead",token,pc=True)
    info={"fields":{},"opts":{}}
    ft_map={"select":"sel","multi_select":"ms","nested_select_field":"cas","multi_nested_select_field":"mcas",
            "text_field":"txt","text_area":"txt","number_field":"num","currency_field":"num",
            "email_field":"eml","mobile_field":"mob","url_field":"url","datetime_field":"dt",
            "user_field":"usr","multi_user_field":"m_usr","department_field":"dept",
            "multi_department_field":"m_dept","custom_relation_field":"rel"}
    for t in ft_map.values(): info["fields"][t]=[]
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            n=f.get("name",""); ft=f.get("field_type",""); fid=f.get("field_id"); lb=f.get("label","")
            if n in ["name","company_name","note","status","source","channel","revisit_remind_at","job","department",]: continue
            if n.startswith("address.") or n.startswith("subform_") or n.startswith("file_asset"): continue
            t=ft_map.get(ft,"txt"); info["fields"][t].append({"name":n,"label":lb,"fid":fid})
    # 选项
    for entry in info["fields"]["sel"]+info["fields"]["ms"]+info["fields"]["cas"]+info["fields"]["mcas"]:
        fid=entry["fid"]
        if not fid: continue
        detail=fetch(api,f"custom_fields/{fid}?custom_field_template_id=1331",token,pc=True)
        opts=detail.get("data",{}).get("options",{}).get("select_options",[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict) and o.get("value"): values.append(o["value"])
        if values: info["opts"][entry["name"]]=values

    # 系统字段选项
    fm=fetch(api,"field_maps/lead",token)
    info["fm_opts"]={}
    for f in fm.get("data",{}).get("lead",[]):
        vals=[v for v in f.get("field_values",[]) if v.get("status")=="enable"]
        if vals: info["fm_opts"][f["field_name"]]=[str(v["id"]) for v in vals]

    us=fetch(api,"user/simple_list?per_page=50",token)
    info["users"]=[u["value"] for u in us.get("simple_users",[]) if u.get("value") and u.get("value")!=""]
    dp=fetch(api,"departments",token)
    info["depts"]=[str(d["id"]) for d in dp.get("data",{}).get("departments",[]) if d.get("id")]
    lb=fetch(api,"labels",token)
    info["labels"]=[{"label_id":l["id"],"label_group_id":g["group_id"]} for g in lb.get("data",{}).get("label_groups",[]) for l in g.get("labels",[])]
    # 市场活动
    ma=fetch(api,"market_activities/simple_market_activities",token,pc=True)
    info["market_activities"]=[m for m in ma.get("data",{}).get("list",[]) if m.get("id")]

    print("生成编辑后值...")
    data={}
    # 系统字段
    for fk in ["status","source","channel"]:
        opts=info["fm_opts"].get(fk,[]); old_v=str(old.get(fk,""))
        if opts: data[fk]=choose_diff(opts,old_v)
    old_rt=old.get("revisit_remind_at","")
    while True:
        new_rt=(datetime.now()+timedelta(days=random.randint(1,14))).strftime("%Y-%m-%d %H:%M")
        if new_rt!=old_rt: break
    data["revisit_remind_at"]=new_rt
    data["department"]=random.choice(["研发部","产品部","销售部","市场部","财务部"])
    data["job"]=random.choice(["经理","总监","主管","工程师","代表"])

    # 标签-换不同
    old_label_ids=[l["id"] for l in old.get("labels",[])]
    new_labels=[l for l in info["labels"] if l["label_id"] not in old_label_ids]
    if new_labels: data["customer_labels_attributes"]=random.sample(new_labels,min(3,len(new_labels)))

    # 地址
    region=random.choice([{"province_id":1,"city_id":1,"district_id":4},{"province_id":10,"city_id":77,"district_id":0},{"province_id":13,"city_id":122,"district_id":1106},{"province_id":21,"city_id":231,"district_id":3380}])
    if info["market_activities"]:
        old_ma=old.get("market_activity",{}).get("id","")
        cand_ma=[m for m in info["market_activities"] if m["id"]!=old_ma]
        if cand_ma: data["market_activity_id"]=random.choice(cand_ma)["id"]
    data["address_attributes"]={**region,"detail_address":f"{random.choice(ROADS)}{random.randint(1,999)}号",
        "phone":rp(),"tel":f"0519-{''.join(random.choices(string.digits,k=8))}","email":re(),
        "url":ru(),"wechat":rp(),"qq":str(random.randint(10000000,999999999)),"wangwang":rp(),
        "fax":f"0519-{''.join(random.choices(string.digits,k=8))}","zip":f"518{random.randint(0,99):02d}"}

    for f in info["fields"]["txt"]+info["fields"]["eml"]+info["fields"]["mob"]+info["fields"]["url"]:
        data[f["name"]]=rt()
    for f in info["fields"]["eml"]: data[f["name"]]=re()
    for f in info["fields"]["mob"]: data[f["name"]]=rp()
    for f in info["fields"]["url"]: data[f["name"]]=ru()
    for f in info["fields"]["num"]: data[f["name"]]=rd() if "金额" in f["label"] or "币" in f["label"] else ri()
    for f in info["fields"]["dt"]: data[f["name"]]=rf()
    for f in info["fields"]["sel"]:
        opts=info["opts"].get(f["name"],[]); data[f["name"]]=choose_diff(opts,old.get(f["name"],""))
    for f in info["fields"]["ms"]:
        opts=info["opts"].get(f["name"],[]); data[f["name"]]=choose_diff_list(opts,old.get(f["name"],[]),random.randint(2,min(4,len(opts))))
    for f in info["fields"]["cas"]:
        opts=info["opts"].get(f["name"],[]); data[f["name"]]=choose_diff(opts,old.get(f["name"],""))
    for f in info["fields"]["mcas"]:
        opts=info["opts"].get(f["name"],[]); data[f["name"]]=choose_diff_list(opts,old.get(f["name"],[]),2)

    # 用户/部门-换不同
    old_usr=set(old.get("user_field_asset_03be5a",[]) or [])
    cand_usr=[u for u in info["users"] if u not in old_usr]
    if cand_usr: data["user_field_asset_03be5a"]=random.sample(cand_usr,1)
    old_mu=set(old.get("user_field_asset_9a4657",[]) or [])
    cand_mu=[u for u in info["users"] if u not in old_mu]
    if cand_mu: data["user_field_asset_9a4657"]=random.sample(cand_mu,min(3,len(cand_mu)))
    old_dept=set(old.get("user_field_asset_3b1490",[]) or [])
    cand_dept=[d for d in info["depts"] if d not in old_dept]
    if cand_dept: data["user_field_asset_3b1490"]=random.sample(cand_dept,1)
    old_md=set(old.get("user_field_asset_29bf74",[]) or [])
    cand_md=[d for d in info["depts"] if d not in old_md]
    if len(cand_md)>=2: data["user_field_asset_29bf74"]=random.sample(cand_md,2)

    # 数据关联-用有效ID
    for f in info["fields"]["rel"]:
        old_v=str(old.get(f["name"],"")); data[f["name"]]="1" if old_v!="1" else "2"

    print(f"编辑线索 ID:{a.id}...")
    r=requests.put(f"{api}/api/v2/leads/{a.id}",
        headers={"Content-Type":"application/json","Authorization":f"Token token={token}"},
        json={"lead":data},timeout=30)
    res=r.json()
    if res.get("code")==0:
        print("✅ 编辑成功!")
        r2=requests.get(f"{api}/api/v2/leads/{a.id}",headers={"Authorization":f"Token token={token}"})
        new=r2.json().get("data",{})
        for k in ["status_mapped","source_mapped","text_asset_b6b26a","text_asset_4e6ad8"]:
            print(f'  ✓ {k}: {old.get(k)} -> {new.get(k)}')
    else:
        print(f"✗ {res.get('message','?')}")

if __name__=="__main__": main()
