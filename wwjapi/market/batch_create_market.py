#!/usr/bin/env python3
"""批量创建市场活动(含文件字段/附件/地址/业务类型) - PC API
使用: python3 batch_create_market.py --api https://域名 --token xxx [数量]"""
import requests,json,random,string,sys,argparse,time,os,shutil,tempfile
from datetime import datetime,timedelta
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config import apply_config_defaults
from lib.upload import discover_file_fields, pc_url, upload_to_oss

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def request_json(method, url, **kwargs):
    r = requests.request(method, url, **kwargs)
    r.raise_for_status()
    return r.json()

def fetch(api,path,token):
    base=api.rstrip("/")+"/api/v2"
    return request_json("get",f"{base}/{path.lstrip('/')}",headers={"Authorization":f"Token token={token}"},timeout=15)

def fetch_apaas_simple(api, token, custom_form_id, per_page=20):
    url=f"{pc_url(api)}/apaas/api/v2/form_entities/simple?page=1&per_page={per_page}&without_count=true&custom_form_id={custom_form_id}"
    headers={
        "accept":"application/json, text/plain, */*",
        "authorization":f'Token token="{token}",device="web"',
        "origin":api.rstrip("/"),
        "referer":api.rstrip("/")+"/",
    }
    return request_json("get",url,headers=headers,timeout=15)

def discover(api,token):
    info={"fm":{},"fields":{"sel":[],"ms":[],"cas":[],"mcas":[],"txt":[],"num":[],"eml":[],"mob":[],"url":[],"dt":[],"usr":[],"m_usr":[],"dept":[],"m_dept":[],"rel":[],"file":[]},"opts":{},"template_id":None}
    pc=pc_url(api)
    # 系统字段
    fm=fetch(api,"field_maps/market_activity",token)
    for f in fm.get("data",{}).get("market_activity",[]):
        vals=[v for v in f.get("field_values",[]) if v.get("status")=="enable"]
        if vals: info["fm"][f["field_name"]]=[str(v["id"]) for v in vals]
    # 自定义字段
    cf=request_json("get",f"{pc}/api/pc/custom_fields?model_klass=MarketActivity",
        headers={"Authorization":f"Token token={token}"},timeout=15)
    ft_map={"select":"sel","multi_select":"ms","nested_select_field":"cas","multi_nested_select_field":"mcas",
            "text_field":"txt","text_area":"txt","number_field":"num","currency_field":"num",
            "email_field":"eml","mobile_field":"mob","url_field":"url","datetime_field":"dt",
            "user_field":"usr","multi_user_field":"m_usr","department_field":"dept",
            "multi_department_field":"m_dept","custom_relation_field":"rel"}
    ex={"name","note","category","status","user_id","want_department_id","start_date","end_date",
        "estimated_cost","actual_cost","estimated_income","actual_income","description","schedule","summary","approve_status","attachments"}
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            n=f.get("name",""); ft=f.get("field_type",""); fid=f.get("field_id"); lb=f.get("label","")
            if n in ex: continue
            if n.startswith("subform_"): continue
            if ft in ("subform_field","stat_field"): continue
            if n.startswith("file_asset"): info["fields"]["file"].append({"name":n,"label":lb}); continue
            if ft=="attachments_field": info["fields"]["file"].append({"name":n,"label":lb}); continue  # 记录用于统计
            if n.startswith("address."): continue  # 地址单独处理
            t=ft_map.get(ft,"txt"); info["fields"][t].append({"name":n,"label":lb,"fid":fid})
    # 选项
    for entry in info["fields"]["sel"]+info["fields"]["ms"]+info["fields"]["cas"]+info["fields"]["mcas"]:
        fid=entry["fid"]
        if not fid: continue
        d=request_json("get",f"{pc}/api/pc/custom_fields/{fid}",
            headers={"Authorization":f"Token token={token}"},timeout=15)
        opts=d.get("data",{}).get("options",{}).get("select_options",[])
        values=[]
        for o in opts:
            if isinstance(o,list) and len(o)==2: values.append(o[1])
            elif isinstance(o,dict): values.append(o.get("value",""))
        if values: info["opts"][entry["name"]]=values
    # 业务模板
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            if f.get("field_type") in ("select","multi_select") and f.get("field_id"):
                fid=str(f["field_id"])
                if len(fid)>=5:
                    d=request_json("get",f"{pc}/api/pc/custom_fields/{fid}",
                        headers={"Authorization":f"Token token={token}"},timeout=15)
                    for t in d.get("data",{}).get("custom_field_templates",[]):
                        if t.get("status")=="enable": info["template_id"]=t["id"]; break
                if info["template_id"]: break
        if info["template_id"]: break
    # 用户/部门
    us=fetch(api,"user/simple_list?per_page=50",token)
    info["users"]=[u["value"] for u in us.get("simple_users",[]) if u.get("value") and u.get("value")!=""]
    dp=fetch(api,"departments",token)
    info["depts"]=[str(d["id"]) for d in dp.get("data",{}).get("departments",[]) if d.get("id")]
    # 用户信息
    ui=fetch(api,"user/info",token)
    info["user_id"]=ui.get("data",{}).get("id")
    info["department_id"]=ui.get("data",{}).get("department_id")
    info["file_fields"]=discover_file_fields(api,token,"MarketActivity")
    try:
        apaas=fetch_apaas_simple(api,token,335)
        info["apaas_form_values"]=[str(item.get("value") or item.get("id")) for item in apaas.get("data",{}).get("models",[]) if item.get("value") or item.get("id")]
    except Exception:
        info["apaas_form_values"]=[]
    return info

NAMES=["春季促销","新品发布会","客户答谢会","行业峰会","产品培训","市场调研","品牌推广","渠道招商","线上直播","周年庆典"]
ROADS=["科技路","创新路","发展大道","人民路","建设路","中山路","解放路","高新路","创业路","工业路"]
def rn(): return random.choice(NAMES)+"-"+datetime.now().strftime('%Y%m%d%H%M%S')
def rt(): return "".join(random.choices(string.ascii_letters+string.digits,k=random.randint(5,15)))
def rd(): return round(random.uniform(1000,99999),2)
def rf(days=None): return (datetime.now()+timedelta(days=days if days is not None else random.randint(1,60))).strftime("%Y-%m-%d")

def build(info):
    c={}
    for k,vals in info["fm"].items():
        if vals: c[k]=random.choice(vals)
    start_offset=random.randint(1,60)
    end_offset=start_offset+random.randint(0,15)
    c["start_date"]=rf(start_offset); c["end_date"]=rf(end_offset)
    c["estimated_cost"]=rd(); c["actual_cost"]=rd()
    c["estimated_income"]=rd(); c["actual_income"]=rd()
    c["description"]=rt()[:20]; c["schedule"]=rt()[:20]; c["summary"]=rt()[:20]
    if info["user_id"]: c["user_id"]=info["user_id"]
    if info["department_id"]: c["want_department_id"]=info["department_id"]
    if info["template_id"]: c["custom_field_template_id"]=info["template_id"]
    # 地址
    region=random.choice([{"province_id":1,"city_id":1,"district_id":4},{"province_id":10,"city_id":77,"district_id":0},{"province_id":13,"city_id":122,"district_id":1106},{"province_id":21,"city_id":231,"district_id":3380}])
    c["address_attributes"]={**region,"detail_address":f"{random.choice(ROADS)}{random.randint(1,999)}号"}
    for f in info["fields"]["txt"]: c[f["name"]]=rt()[:10]
    for f in info["fields"]["eml"]: c[f["name"]]="".join(random.choices(string.ascii_lowercase,k=6))+"@qq.com"
    for f in info["fields"]["mob"]: c[f["name"]]=random.choice(["138","139","150","151","186","187","188","189"])+"".join(random.choices(string.digits,k=8))
    for f in info["fields"]["url"]: c[f["name"]]="https://www."+"".join(random.choices(string.ascii_lowercase,k=8))+".com"
    for f in info["fields"]["num"]: c[f["name"]]=rd() if "金额" in f["label"] or "币" in f["label"] else random.randint(1000,99999)
    for f in info["fields"]["dt"]: c[f["name"]]=rf()
    for f in info["fields"]["sel"]:
        opts=info["opts"].get(f["name"],[]); v=random.choice(opts) if opts else None
        c[f["name"]]=v
        if v=="other": c[f["name"]+"_other"]="其他-自定义文本"
    for f in info["fields"]["ms"]:
        opts=info["opts"].get(f["name"],[]); c[f["name"]]=random.sample(opts,min(2,len(opts))) if opts else []
    for f in info["fields"]["cas"]:
        opts=info["opts"].get(f["name"],[]); c[f["name"]]=random.choice(opts) if opts else None
    for f in info["fields"]["mcas"]:
        opts=info["opts"].get(f["name"],[]); c[f["name"]]=random.sample(opts,2) if len(opts)>=2 else ([random.choice(opts)] if opts else [])
    if info["users"]:
        for f in info["fields"]["usr"]: c[f["name"]]=random.sample(info["users"],1)
        for f in info["fields"]["m_usr"]: c[f["name"]]=random.sample(info["users"],min(3,len(info["users"])))
    if info["depts"]:
        for f in info["fields"]["dept"]: c[f["name"]]=random.sample(info["depts"],1)
        for f in info["fields"]["m_dept"]: c[f["name"]]=random.sample(info["depts"],min(2,len(info["depts"])))
    for f in info["fields"]["rel"]:
        if f["name"]=="custom_relation_asset_89aa2c" and info.get("apaas_form_values"):
            c[f["name"]]=random.choice(info["apaas_form_values"])
        else:
            c[f["name"]]=None
    # 自动编号类字段通常服务端生成，客户端传值会被忽略。
    for f in info["fields"]["txt"]:
        if "自动编号" in f["label"]:
            c.pop(f["name"],None)
    return c

IMAGE_EXTS={".jpg",".jpeg",".png"}
DOC_EXTS={".docx",".xlsx",".pdf"}

def split_upload_files(attachment_dir):
    images=[]; docs=[]
    if not attachment_dir:
        return images,docs
    for name in os.listdir(attachment_dir):
        path=os.path.join(attachment_dir,name)
        if not os.path.isfile(path):
            continue
        ext=os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXTS:
            images.append(path)
        if ext in DOC_EXTS:
            docs.append(path)
    return images,docs

def choose_files(files, count):
    if not files:
        return []
    if len(files) >= count:
        return random.sample(files, count)
    return [random.choice(files) for _ in range(count)]

def prepare_upload_path(path):
    name=os.path.basename(path)
    try:
        name.encode("ascii")
        return path, None
    except UnicodeEncodeError:
        suffix=os.path.splitext(name)[1].lower()
        fd,tmp_path=tempfile.mkstemp(suffix=suffix, prefix="upload_")
        os.close(fd)
        shutil.copyfile(path, tmp_path)
        return tmp_path, tmp_path

def process_market_file_fields(api,token,data,file_fields,image_files,doc_files):
    uploaded={}
    for f in file_fields:
        label=f.get("label","")
        is_image_field="图片" in label
        selected=choose_files(image_files if is_image_field else doc_files, 3 if is_image_field else 2)
        ids=[]
        for path in selected:
            upload_path,tmp_path=prepare_upload_path(path)
            try:
                aid=upload_to_oss(api,token,upload_path)
                if aid:
                    ids.append(aid)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        if ids:
            data[f["name"]]={"attachment_ids":ids}
            uploaded[f["name"]]=ids
    return uploaded

def fetch_detail(api, token, entity_id):
    return request_json("get",f"{pc_url(api)}/api/pc/market_activities/{entity_id}",
        headers={"Authorization":f"Token token={token}"},timeout=15).get("data",{})

def validate_fields(sent, detail):
    checks=[]

    def add(name, expected, actual):
        checks.append((name, expected, actual, expected == actual))

    def normalize_scalar(value):
        if isinstance(value, float):
            return str(value).rstrip("0").rstrip(".")
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            return value.rstrip("0").rstrip(".") if value.replace(".","",1).isdigit() else value
        return value

    def normalize_list(value):
        if not isinstance(value, list):
            return value
        return sorted(normalize_scalar(v) for v in value)

    scalar_fields=["name","note","start_date","end_date","estimated_cost","actual_cost",
        "estimated_income","actual_income","description","schedule","summary",
        "custom_field_template_id","revisit_remind_at"]
    for field in scalar_fields:
        if field in sent:
            add(field, normalize_scalar(sent.get(field)), normalize_scalar(detail.get(field)))

    if "user_id" in sent:
        add("user_id", normalize_scalar(sent["user_id"]), normalize_scalar((detail.get("user") or {}).get("id")))
    if "want_department_id" in sent:
        add("want_department_id", normalize_scalar(sent["want_department_id"]), normalize_scalar((detail.get("owned_department") or {}).get("id")))

    sent_address=sent.get("address_attributes") or {}
    detail_address=detail.get("address") or detail.get("address_attributes") or {}
    address_map={
        "province_id": (detail_address.get("province") or {}).get("id"),
        "city_id": (detail_address.get("city") or {}).get("id"),
        "district_id": (detail_address.get("district") or {}).get("id"),
        "detail_address": detail_address.get("detail_address"),
    }
    for field, actual in address_map.items():
        if field in sent_address:
            add(f"address.{field}", normalize_scalar(sent_address.get(field)), normalize_scalar(actual))

    for key, value in sent.items():
        if key in scalar_fields or key == "address_attributes":
            continue
        if key in ("user_id","want_department_id"):
            continue
        if key == "attachments":
            continue
        if isinstance(value, (str, int, float)) or value is None:
            add(key, normalize_scalar(value), normalize_scalar(detail.get(key)))
        elif isinstance(value, list):
            actual=detail.get(key)
            if isinstance(actual, list):
                if actual and isinstance(actual[0], dict) and "id" in actual[0]:
                    actual=[item.get("id") for item in actual]
                add(key, normalize_list(value), normalize_list(actual))
            else:
                add(key, normalize_list(value), actual)
        elif isinstance(value, dict) and "attachment_ids" in value:
            actual=detail.get(key)
            actual_ids=[]
            if isinstance(actual, dict):
                actual_ids=actual.get("attachment_ids",[])
            elif isinstance(actual, list):
                actual_ids=[item.get("id") for item in actual if isinstance(item, dict) and item.get("id")]
            add(key, normalize_list(value["attachment_ids"]), normalize_list(actual_ids))
    return checks

def collect_uploaded_ids(data, attach_ids):
    ids={}
    for key, value in data.items():
        if isinstance(value, dict) and "attachment_ids" in value:
            ids[key]=value["attachment_ids"]
    ids["attachments"]=attach_ids
    return ids

def verify_uploaded_files(detail, uploaded_ids):
    checks=[]
    for key, expected_ids in uploaded_ids.items():
        if not expected_ids:
            continue
        if key == "attachments":
            actual_ids=[item.get("id") for item in detail.get("all_attachments",[]) if item.get("id")]
        else:
            actual_ids=[item.get("id") for item in detail.get(key,[]) if isinstance(item, dict) and item.get("id")]
        checks.append((key, sorted(str(x) for x in expected_ids), sorted(str(x) for x in actual_ids), sorted(str(x) for x in expected_ids) == sorted(str(x) for x in actual_ids)))
    return checks

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api"); p.add_argument("--token")
    p.add_argument("count",nargs="?",type=int,default=1); p.add_argument("--delay",type=float,default=0.3)
    p.add_argument("--attachment-dir",help="本地附件目录，图片字段随机传3张图，文件/附件随机传2个文件")
    p.add_argument("--verify",action="store_true",help="创建后回查详情并校验字段")
    a=apply_config_defaults(p.parse_args(), p)
    print(f"\n{'='*60}\n市场活动\nAPI: {a.api}\n数量: {a.count}")
    if a.attachment_dir: print(f"附件目录: {a.attachment_dir}")
    print(f"{'='*60}")
    print("\n[1/2] 自动发现字段...")
    try: info=discover(a.api,a.token)
    except Exception as e: print(f"失败: {e}"); return
    print(f"  系统:{len(info['fm'])} 文本:{len(info['fields']['txt'])} 邮箱:{len(info['fields']['eml'])} 手机:{len(info['fields']['mob'])}")
    print(f"  单选:{len(info['fields']['sel'])} 多选:{len(info['fields']['ms'])} 级联:{len(info['fields']['cas'])} 级联多选:{len(info['fields']['mcas'])}")
    print(f"  文件:{len(info['fields']['file'])} 用户:{len(info['users'])} 部门:{len(info['depts'])} 模板:{info['template_id']}")
    image_files,doc_files=split_upload_files(a.attachment_dir)
    if len(image_files) < 3:
        print("失败: 图片文件少于3张")
        return
    if len(doc_files) < 2:
        print("失败: 文档文件少于2个")
        return
    print(f"\n[2/2] 创建 {a.count} 条...")
    ok=fail=0
    for i in range(1,a.count+1):
        try:
            data=build(info)
            data["name"]=rn()
            data["note"]=f"批量第{i}条"
            # 文件字段(file_asset)
            file_uploads=process_market_file_fields(a.api,a.token,data,info["file_fields"],image_files,doc_files)
            nfiles=sum(len(v) for v in file_uploads.values())
            # 附件字段(attachments) - 前端在创建时一并传入
            attach_ids=[]
            for path in choose_files(doc_files, 2):
                upload_path,tmp_path=prepare_upload_path(path)
                try:
                    aid=upload_to_oss(a.api,a.token,upload_path)
                    if aid:
                        attach_ids.append(aid)
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            if attach_ids:
                data["attachments"]=[{"id":aid,"uploadId":aid,"note":"","key":"","type":"application/octet-stream"} for aid in attach_ids]
            payload={"market_activity":data,"attachment_ids":attach_ids}
            # 创建
            r=requests.post(pc_url(a.api)+"/api/pc/market_activities",
                headers={"Content-Type":"application/json","Authorization":f"Token token={a.token}"},
                json=payload,timeout=30)
            r.raise_for_status()
            res=r.json()
            if res.get("code")==0:
                mid=res['data']['id']
                if a.verify:
                    detail=fetch_detail(a.api,a.token,mid)
                    checks=validate_fields(data,detail)
                    file_checks=verify_uploaded_files(detail,collect_uploaded_ids(data,attach_ids))
                    checks.extend(file_checks)
                    passed=sum(1 for _,_,_,ok in checks if ok)
                    failed=[item for item in checks if not item[3]]
                    ok+=1;print(f"  ✓ [{i}/{a.count}] ID:{mid} 文件:{nfiles} 附件:{len(attach_ids)} 模板:{info['template_id']} 校验:{passed}/{len(checks)}")
                    for name, expected, actual, _ in failed[:10]:
                        print(f"    - {name} 不一致: expected={expected!r} actual={actual!r}")
                else:
                    ok+=1;print(f"  ✓ [{i}/{a.count}] ID:{mid} 文件:{nfiles} 附件:{len(attach_ids)} 模板:{info['template_id']}")
            else: fail+=1;print(f"  ✗ [{i}/{a.count}] {res.get('message','?')}")
        except Exception as e: fail+=1;print(f"  ✗ [{i}/{a.count}] {e}")
        if i<a.count and a.delay>0: time.sleep(a.delay)
    print(f"\n完成! 成功:{ok} 失败:{fail}")

if __name__=="__main__": main()
