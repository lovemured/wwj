"""共享工具：OSS上传、文件字段处理"""
import mimetypes,requests,os,tempfile,random,string,uuid,time
from datetime import datetime

USER_CACHE = {}

# 模块名 → API路径映射
API_PATH = {
    "Lead": "leads", "Customer": "customers", "Contact": "contacts",
    "Opportunity": "opportunities", "Contract": "contracts",
    "Product": "products", "Quotation": "quotations",
    "Payment": "received_payments", "Expense": "expenses",
    "RevisitLog": "revisit_logs",
    "ReceivedPayment": "received_payments", "InvoicedPayment": "invoiced_payments",
}

def pc_url(api):
    return api.replace("//lxcrm-staging.","//lxcrm-api-staging.").replace("//lxcrm-test.","//lxcrm-api-test.")

def current_user(api,token):
    key=(api.rstrip('/'),token)
    if key in USER_CACHE:
        return USER_CACHE[key]
    for _ in range(3):
        try:
            r=requests.get(f"{api.rstrip('/')}/api/v2/user/info",
                headers={"Authorization":f"Token token={token}"},timeout=15)
            data=r.json().get("data",{})
            result=(str(data.get("id","")),str(data.get("organization_id","")))
            if result[0] and result[1]:
                USER_CACHE[key]=result
                return result
        except (requests.RequestException, ValueError):
            time.sleep(1)
    return "",""

def guess_content_type(filename):
    content_type,_=mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"

def upload_to_oss(api,token,filepath=None):
    """上传文件到OSS，返回附件ID。filepath=None则生成随机文本文件(自动重试)"""
    user_id,org_id=current_user(api,token)
    u=requests.get(f"{api.rstrip('/')}/api/pc/qiniu/auth/oss_upload_token.json?policy=attachment",
        headers={"Authorization":f"Token token={token}"},timeout=15).json().get("uptoken",{})
    if not u.get("accessid"): return None
    if filepath:
        name=os.path.basename(filepath)
        with open(filepath,"rb") as f: content=f.read()
    else:
        fd,path=tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd,"w") as f: f.write("".join(random.choices(string.ascii_letters+string.digits,k=128)))
        name=f"attachment-{datetime.now().strftime('%H%M%S')}.txt"
        with open(path,"rb") as f: content=f.read()
        os.unlink(path)
    content_type=guess_content_type(name)
    for _ in range(3):
        try:
            key=str(uuid.uuid4())+os.path.splitext(name)[1]
            r=requests.post(u["host"],data={
                "name":name,"chunk":"0","chunks":"1","key":key,
                "policy":u["policy"],"OSSAccessKeyId":u["accessid"],
                "signature":u["signature"],"callback":u.get("callback",""),
                "success_action_status":"200","Content-Disposition":"inline",
                "x:userid":user_id,"x:orgid":org_id,"x:user_token":token,
                "x:name":name,"x:custom_name":name,
            },files={"file":(name,content,content_type)},timeout=120)
            aid=r.json().get("payload",{}).get("id")
            if aid: return aid
            # 也可能直接在顶层
            aid=r.json().get("id")
            if aid: return aid
        except: pass
        time.sleep(1)
    return None

def discover_file_fields(api,token,klass):
    """发现模块的file_asset自定义字段"""
    pc=pc_url(api)
    cf=requests.get(f"{pc}/api/pc/custom_fields?model_klass={klass}",
        headers={"Authorization":f"Token token={token}"},timeout=15).json()
    fields=[]
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            n=f.get("name",""); ft=f.get("field_type","")
            if n.startswith("file_asset") and ft in ("file_field","file_type"):
                fields.append({"name":n,"label":f.get("label","")})
    return fields

def discover_attach_fields(api,token,klass):
    """发现模块的attachments系统附件字段(商机附件/报价单附件/合同附件)"""
    pc=pc_url(api)
    cf=requests.get(f"{pc}/api/pc/custom_fields?model_klass={klass}",
        headers={"Authorization":f"Token token={token}"},timeout=15).json()
    fields=[]
    for g in cf.get("data",{}).get("custom_field_groups",[]):
        for f in g.get("custom_fields",[]):
            if f.get("field_type")=="attachments_field":
                fields.append({"name":f.get("name"),"label":f.get("label","")})
    return fields

def process_file_fields(api,token,klass,data,attachment_dir=None):
    """上传文件并设置file_asset字段值,返回上传的附件ID列表"""
    fields=discover_file_fields(api,token,klass)
    if not fields: return []
    entries=[os.path.join(attachment_dir,f) for f in (os.listdir(attachment_dir) if attachment_dir else [])
        if os.path.isfile(os.path.join(attachment_dir,f)) and not f.startswith(".")] if attachment_dir else []
    image_files=[f for f in entries if f.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp','.bmp','.heic'))]
    doc_files=[f for f in entries if not f.lower().endswith(('.ds_store',))]
    uploaded=[]
    for f in fields:
        is_image='图片' in (f.get('label') or '')
        candidates=image_files if is_image and image_files else doc_files
        if candidates:
            candidates=random.sample(candidates,min(5,len(candidates)))
        else:
            candidates=[None]
        aid=None
        for fp in candidates:
            aid=upload_to_oss(api,token,fp)
            if aid:
                break
        if aid:
            uploaded.append(aid)
            data[f["name"]]={"attachment_ids":[aid]}
            if is_image:
                data[f["name"]]["sub_type"]="image"
    return uploaded

def create_entity(api,token,klass,data,attachment_dir=None):
    """创建实体(支持file_asset字段上传),返回(resp_json, uploaded_count)"""
    nfiles=len(process_file_fields(api,token,klass,data,attachment_dir))
    path=API_PATH.get(klass,klass.lower()+"s")
    url=pc_url(api)+f"/api/pc/{path}"
    r=requests.post(url,headers={"Content-Type":"application/json","Authorization":f"Token token={token}"},
        json={klass.lower():data},timeout=30)
    return r.json(),nfiles

def upload_attach_files(api,token,klass,entity_id,attachment_dir=None):
    """上传文件并关联到实体的attachments字段,返回数量"""
    fields=discover_attach_fields(api,token,klass)
    if not fields or not entity_id: return 0
    pc=pc_url(api)
    files=[os.path.join(attachment_dir,f) for f in (os.listdir(attachment_dir) if attachment_dir else [])
        if f.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp','.bmp','.heic'))] if attachment_dir else []
    count=0
    for f in fields:
        fp=random.choice(files) if files else None
        aid=upload_to_oss(api,token,fp)
        if aid:
            if klass in ("Contract","MarketActivity"):
                requests.post(f"{pc}/api/pc/attachments/{entity_id}/add_attachments",
                    headers={"Authorization":f"Token token={token}","Content-Type":"application/json"},
                    json={"klass":klass,"attachments":[{"id":aid,"note":""}]},timeout=15)
            else:
                ent={"Opportunity":"opportunity","Quotation":"quotation"}.get(klass,klass.lower())
                requests.post(f"{api.rstrip('/')}/api/v2/attachments/{ent}/{entity_id}/upload_attachments",
                    headers={"Authorization":f"Token token={token}","Content-Type":"application/json"},
                    json={"attachment_ids":[aid],"sub_type":"file"},timeout=15)
            count+=1
    return count
