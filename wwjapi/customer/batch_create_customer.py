#!/usr/bin/env python3
"""批量创建客户(含文件字段) - 支持任意CRM环境
使用: python3 batch_create_customer.py --api https://域名 --token xxx [数量]"""
import requests,json,random,string,sys,argparse,time
from datetime import datetime,timedelta
import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import process_file_fields, pc_url

def fetch(api,path,token,pc=False):
    base=api.rstrip("/")+("/api/pc" if pc else "/api/v2")
    r=requests.get(f"{base}/{path.lstrip('/')}",headers={"Authorization":f"Token token={token}"},timeout=15)
    return r.json()

def discover(api,token):
    info={"fm":{},"fields":{"sel":[],"ms":[],"cas":[],"mcas":[],"txt":[],"num":[],"eml":[],"mob":[],"url":[],"dt":[],"usr":[],"m_usr":[],"dept":[],"m_dept":[],"rel":[],"file":[]},"opts":{}}

    # 1. 系统字段
    fm=fetch(api,"field_maps/customer",token)
    for f in fm.get("data",{}).get("customer",[]):
        vals=[v for v in f.get("field_values",[]) if v.get("status")=="enable"]
        if vals: info["fm"][f["field_name"]]=[str(v["id"]) for v in vals]

    # 2. 业务类型模板 - 取第一个enable的
    tpl_ids=set()
    # 从字段详情中获取
    cf=fetch(api,"custom_fields?model_klass=Customer",token,pc=True)
    # 从第一个select字段的详情获取模板列表
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            if f.get("field_id"):
                fid=str(f["field_id"])
                if len(fid)>=5:
                    detail=fetch(api,f"custom_fields/{fid}?custom_field_template_id=1331",token,pc=True)
                    for t in detail.get("data",{}).get("custom_field_templates",[]):
                        if t.get("status")=="enable":
                            tpl_ids.add((t["id"],t["name"]))
                    break
        if tpl_ids: break
    # 默认模板
    if not tpl_ids: tpl_ids=[(1331,"全字段发发发发付")]
    info["template_id"]=list(tpl_ids)[0][0]

    # 3. 自定义字段分类
    ft_map={"select":"sel","multi_select":"ms","nested_select_field":"cas","multi_nested_select_field":"mcas",
            "text_field":"txt","text_area":"txt","number_field":"num","currency_field":"num",
            "email_field":"eml","mobile_field":"mob","url_field":"url","datetime_field":"dt",
            "user_field":"usr","multi_user_field":"m_usr","department_field":"dept",
            "multi_department_field":"m_dept","custom_relation_field":"rel"}
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            n=f.get("name",""); ft=f.get("field_type",""); fid=f.get("field_id"); lb=f.get("label","")
            if n in ["name","company_name","note","parent","status","category","source","industry","staff_size","channel","labels","revisit_remind_at"]: continue
            if n.startswith("address.") or n.startswith("subform_"): continue
            if n.startswith("file_asset"): info["fields"]["file"].append({"name":n,"label":lb}); continue
            t=ft_map.get(ft,"txt")
            info["fields"][t].append({"name":n,"label":lb,"fid":fid})

    # 4. 下拉选项值
    for entry in info["fields"]["sel"]+info["fields"]["ms"]+info["fields"]["cas"]+info["fields"]["mcas"]:
        fid=entry["fid"]
        if not fid: continue
        detail=fetch(api,f"custom_fields/{fid}?custom_field_template_id={info['template_id']}",token,pc=True)
        opts=detail.get("data",{}).get("options",{}).get("select_options",[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict):
                v=o.get("value","")
                if v: values.append(v)
        if values: info["opts"][entry["name"]]=values

    # 5. 用户/部门/标签/客户列表
    us=fetch(api,"user/simple_list?per_page=50",token)
    info["users"]=[u["value"] for u in us.get("simple_users",[]) if u.get("value") and u.get("value")!=""]
    dp=fetch(api,"departments",token)
    info["depts"]=[str(d["id"]) for d in dp.get("data",{}).get("departments",[]) if d.get("id")]
    lb=fetch(api,"labels",token)
    info["labels"]=[{"label_id":l["id"],"label_group_id":g["group_id"]} for g in lb.get("data",{}).get("label_groups",[]) for l in g.get("labels",[])]

    # 6. 客户列表（供上级客户使用）
    cl=fetch(api,"customers?per_page=50",token)
    info["customers"]=[str(c["id"]) for c in cl.get("data",{}).get("customers",[]) if c.get("id")]

    return info

def rp(): return random.choice(["138","139","150","151","186","187","188","189"])+"".join(random.choices(string.digits,k=8))
def re(): return "".join(random.choices(string.ascii_lowercase,k=8))+"@"+random.choice(["qq.com","163.com","126.com","gmail.com"])
def ru(): return "https://www."+"".join(random.choices(string.ascii_lowercase,k=10))+".com"
def rt(): return "".join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def ri(): return random.randint(10000,99999)
def rd(): return round(random.uniform(100,99999),2)
def rf(): return (datetime.now()+timedelta(days=random.randint(1,30))).strftime("%Y-%m-%d")
ROADS=["科技路","创新路","发展大道","人民路","建设路","中山路","解放路","高新路","创业路","工业路","商务大道","文化路","学府路","江南大道","花园路"]

def build(info):
    c={}
    for k,vals in info["fm"].items():
        if vals: c[k]=vals[0] if k!="channel" else vals[-1]
    c["revisit_remind_at"]=(datetime.now()+timedelta(days=random.randint(1,14))).strftime("%Y-%m-%d %H:%M")
    c["custom_field_template_id"]=info["template_id"]
    if info["labels"]: c["customer_labels_attributes"]=random.sample(info["labels"],min(3,len(info["labels"])))
    if info["customers"]: c["parent_id"]=random.choice(info["customers"])
    pm=rp()
    c["address_attributes"]={**random.choice([{"province_id":1,"city_id":1,"district_id":4},{"province_id":10,"city_id":77,"district_id":0},{"province_id":13,"city_id":122,"district_id":1106},{"province_id":21,"city_id":231,"district_id":3380}]),
        "detail_address":f"{random.choice(ROADS)}{random.randint(1,999)}号","phone":pm,
        "tel":f"0519-{''.join(random.choices(string.digits,k=8))}","email":re(),"url":ru(),
        "wechat":rp(),"qq":str(random.randint(10000000,999999999)),"wangwang":rp(),
        "fax":f"0519-{''.join(random.choices(string.digits,k=8))}","zip":f"518{random.randint(0,99):02d}"}
    for f in info["fields"]["txt"]: c[f["name"]]=rt()
    for f in info["fields"]["eml"]: c[f["name"]]=re()
    for f in info["fields"]["mob"]: c[f["name"]]=rp()
    for f in info["fields"]["url"]: c[f["name"]]=ru()
    for f in info["fields"]["num"]: c[f["name"]]=rd() if "金额" in f["label"] or "币" in f["label"] else ri()
    for f in info["fields"]["dt"]: c[f["name"]]=rf()
    for f in info["fields"]["sel"]:
        opts=info["opts"].get(f["name"],[])
        if opts: c[f["name"]]=random.choice(opts)
    for f in info["fields"]["ms"]:
        opts=info["opts"].get(f["name"],[])
        if opts: c[f["name"]]=random.sample(opts,random.randint(2,min(4,len(opts))))
    for f in info["fields"]["cas"]:
        opts=info["opts"].get(f["name"],[])
        if opts: c[f["name"]]=random.choice(opts)
    for f in info["fields"]["mcas"]: # 级联多选-随机2个
        opts=info["opts"].get(f["name"],[])
        if len(opts)>=2: c[f["name"]]=random.sample(opts,2)
        elif opts: c[f["name"]]=[random.choice(opts)]
    if info["users"]:
        for f in info["fields"]["usr"]: c[f["name"]]=random.sample(info["users"],1)
        for f in info["fields"]["m_usr"]:
            n=min(3,len(info["users"]))
            if n>=1: c[f["name"]]=random.sample(info["users"],n)
    if info["depts"]:
        for f in info["fields"]["dept"]: c[f["name"]]=random.sample(info["depts"],1)
        for f in info["fields"]["m_dept"]:
            n=min(2,len(info["depts"]))
            if n>=1: c[f["name"]]=random.sample(info["depts"],n)
    for f in info["fields"]["rel"]: c[f["name"]]=str(random.randint(1,99))
    return c

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api",help="API域名")
    p.add_argument("--token",help="Token")
    p.add_argument("--env", choices=["test", "staging", "production"])
    p.add_argument("count",nargs="?",type=int,default=1)
    p.add_argument("--delay",type=float,default=0.3)
    p.add_argument("--attachment-dir",help="本地附件目录,随机取图片上传到文件字段")
    a=apply_config_defaults(p.parse_args(), p)
    print(f"\n{'='*60}\nAPI: {a.api}\n数量: {a.count}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print(f"{'='*60}")
    print("\n[1/2] 自动发现字段...")
    try: info=discover(a.api,a.token)
    except Exception as e: print(f"失败: {e}"); return
    print(f"  业务模板: {info['template_id']}  系统:{len(info['fm'])} 文本:{len(info['fields']['txt'])} 邮箱:{len(info['fields']['eml'])} 手机:{len(info['fields']['mob'])}")
    print(f"  链接:{len(info['fields']['url'])} 数字:{len(info['fields']['num'])} 时间:{len(info['fields']['dt'])}")
    print(f"  单选:{len(info['fields']['sel'])} 多选:{len(info['fields']['ms'])} 级联单选:{len(info['fields']['cas'])} 级联多选:{len(info['fields']['mcas'])}")
    print(f"  文件:{len(info['fields']['file'])} 用户:{len(info['users'])} 部门:{len(info['depts'])} 标签:{len(info['labels'])} 已有客户:{len(info['customers'])}")
    print(f"\n[2/2] 创建 {a.count} 条...")
    ok=fail=0
    for i in range(1,a.count+1):
        try:
            data=build(info)
            data["name"]=f"批量客户-{datetime.now().strftime('%H%M%S')}-{i}"
            data["company_name"]=f"深圳{rt()}科技有限公司"
            data["note"]=f"批量第{i}条"; data["approve_status"]="approved"
            # 处理文件字段
            nfiles=len(process_file_fields(a.api,a.token,"Customer",data,a.attachment_dir))
            # 有文件字段时用PC API,否则用v2
            pc=bool(info["fields"]["file"] and nfiles)
            url=pc_url(a.api)+"/api/pc/customers" if pc else f"{a.api}/api/v2/customers"
            r=requests.post(url,headers={"Content-Type":"application/json","Authorization":f"Token token={a.token}"},
                json={"customer":data},timeout=30)
            res=r.json()
            if res.get("code")==0: ok+=1;print(f"  ✓ [{i}/{a.count}] ID:{res['data']['id']} 文件:{nfiles}个")
            else: fail+=1;print(f"  ✗ [{i}/{a.count}] {res.get('message','?')}")
        except Exception as e: fail+=1;print(f"  ✗ [{i}/{a.count}] {e}")
        if i<a.count and a.delay>0: time.sleep(a.delay)
    print(f"\n完成! 成功:{ok} 失败:{fail}")

if __name__=="__main__": main()
