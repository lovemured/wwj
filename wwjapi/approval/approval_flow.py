#!/usr/bin/env python3
"""审批流程自动化 - 配置化版本，支持任意模块
使用:
  python3 approval_flow.py --module Contract --action full          # 完整流程
  python3 approval_flow.py --module Contract --action approve --entity-id ID
  python3 approval_flow.py --module Contract --action reject --entity-id ID
  python3 approval_flow.py --module Contract --action detail --entity-id ID
  python3 approval_flow.py --list-workflows                         # 列出可用工作流
  python3 approval_flow.py --module Contract --action enable         # 启用审批流
"""
import importlib.util
import json,random,argparse,time,os,uuid,sys
from datetime import datetime,timedelta

import requests

DEFAULT_PROCESS_API = 'https://process-platform-staging.ikcrm.com'
PROCESS_API = DEFAULT_PROCESS_API

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
from lib.upload import pc_url, process_file_fields, upload_attach_files
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

# ========== 模块配置 ==========
# 每个模块定义: API路径, 请求体key, 创建所需字段, 系统字段映射
MODULE_CONFIG = {
    'Contract': {
        'api_path': 'contracts',
        'body_key': 'contract',
        'create_fields': {
            'title': lambda: f'审批测试合同-{datetime.now().strftime("%m%d%H%M%S")}',
            'customer_id': 'customer_id',  # 从info中取
            'total_amount': lambda: round(random.uniform(1000, 99999), 2),
            'sign_date': lambda: (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d'),
        },
        'field_maps': ['category', 'payment_type'],
        'dependencies': ['customers', 'products'],
    },
    'Lead': {
        'api_path': 'leads',
        'body_key': 'lead',
        'create_fields': {
            'name': lambda: f'审批测试线索-{datetime.now().strftime("%m%d%H%M%S")}',
            'company_name': lambda: f'测试公司-{datetime.now().strftime("%m%d%H%M%S")}',
        },
        'field_maps': ['source', 'status'],
        'field_maps_source': 'lead',
        'dependencies': [],
    },
    'Opportunity': {
        'api_path': 'opportunities',
        'body_key': 'opportunity',
        'create_fields': {
            'title': lambda: f'审批测试商机-{datetime.now().strftime("%m%d%H%M%S")}',
            'customer_id': 'customer_id',
            'expect_amount': lambda: round(random.uniform(1000, 99999), 2),
        },
        'field_maps': ['category'],
        'dependencies': ['customers'],
    },
    'Customer': {
        'api_path': 'customers',
        'body_key': 'customer',
        'create_fields': {
            'name': lambda: f'审批测试客户-{datetime.now().strftime("%m%d%H%M%S")}',
            'company_name': lambda: f'测试公司-{datetime.now().strftime("%m%d%H%M%S")}',
        },
        'field_maps': ['category', 'source', 'status'],
        'dependencies': [],
    },
    'Quotation': {
        'api_path': 'quotations',
        'body_key': 'quotation',
        'create_fields': {
            'title': lambda: f'审批测试报价-{datetime.now().strftime("%m%d%H%M%S")}',
            'customer_id': 'customer_id',
            'total_amount': lambda: round(random.uniform(1000, 99999), 2),
        },
        'field_maps': ['category'],
        'dependencies': ['customers', 'products'],
    },
    'Contact': {
        'api_path': 'contacts',
        'body_key': 'contact',
        'create_fields': {
            'name': lambda: f'审批测试联系人-{datetime.now().strftime("%m%d%H%M%S")}',
            'customer_id': 'customer_id',
        },
        'field_maps': ['category'],
        'dependencies': ['customers'],
    },
}

# entity_klass -> CRM模块名映射（用于流程平台）
ENTITY_KLASS_MAP = {
    'Contract': 'Contract',
    'Lead': 'Lead',
    'Opportunity': 'Opportunity',
    'Customer': 'Customer',
    'Quotation': 'Quotation',
    'Contact': 'Contact',
}
BUSINESS_TYPE_MODULES = {'Customer', 'Opportunity', 'Quotation', 'Contract'}
DETAILED_MODULE_SCRIPTS = {
    'Lead': ('lead', 'batch_create_lead.py'),
    'Customer': ('customer', 'batch_create_customer.py'),
    'Contact': ('contact', 'batch_create_contact.py'),
    'Opportunity': ('opportunity', 'batch_create_opportunity.py'),
    'Quotation': ('quotation', 'batch_create_quotation.py'),
    'Contract': ('contract', 'batch_create_contract.py'),
}
PC_CREATE_MODULES = {'Quotation', 'Contract'}

# ========== HTTP 工具 ==========
def _request(method, url, headers, data=None):
    try:
        resp = requests.request(method, url, headers=headers, json=data, timeout=30)
    except requests.RequestException as exc:
        return {'code': -1, 'message': f'请求失败: {exc}'}
    try:
        body = resp.json()
    except ValueError:
        body = {'raw_text': resp.text[:500]}
    if resp.status_code >= 400 and isinstance(body, dict):
        body.setdefault('message', f'HTTP {resp.status_code}: {resp.text[:500]}')
    return body


def _v2(api, token, method, path, data=None):
    url = api.rstrip('/') + '/api/v2/' + path.lstrip('/')
    h = {'Content-Type': 'application/json', 'Authorization': f'Token token={token}'}
    return _request(method, url, h, data)

def _pc(api, token, method, path, data=None):
    pc = api.replace('//lxcrm-staging.', '//lxcrm-api-staging.').replace('//lxcrm-test.', '//lxcrm-api-test.')
    url = pc.rstrip('/') + '/api/pc/' + path.lstrip('/')
    h = {'Content-Type': 'application/json', 'Authorization': f'Token token={token}'}
    return _request(method, url, h, data)

def _process(token, method, path, data=None):
    url = PROCESS_API.rstrip('/') + '/api/v1/' + path.lstrip('/')
    h = {
        'Content-Type': 'application/json',
        'accept': 'application/json',
        'access-token': token,
        'authorization': f'Token token="{token}",device="web"',
        'x-lxy-app': 'crm',
        'x-lxy-platform': 'lixiaoyun'
    }
    return _request(method, url, h, data)


def current_user_info(api, token):
    info = _v2(api, token, 'GET', 'user/info')
    data = info.get('data') or {}
    return {
        'user_id': data.get('id'),
        'uid': data.get('uid'),
        'organization_id': data.get('organization_id'),
    }


def list_business_types(api, token, module):
    if module not in BUSINESS_TYPE_MODULES:
        return []
    detail = _pc(api, token, 'GET', f'custom_fields?model_klass={module}')
    groups = (detail.get('data') or {}).get('custom_field_groups') or []
    field_id = None
    for group in groups:
        for field in group.get('custom_fields') or []:
            if field.get('field_id'):
                field_id = field['field_id']
                break
        if field_id:
            break
    if not field_id:
        return []
    field_detail = _pc(api, token, 'GET', f'custom_fields/{field_id}?custom_field_template_id=1331')
    return (field_detail.get('data') or {}).get('custom_field_templates') or []


def first_enabled_business_type(api, token, module):
    for item in list_business_types(api, token, module):
        if item.get('status') == 'enable':
            return item
    return None


def wait_execute_record(token, entity_id, entity_klass, timeout=20, interval=2):
    deadline = time.time() + timeout
    last = {}
    while time.time() <= deadline:
        last = _process(token, 'GET', f'execute_records/detail?entity_id={entity_id}&entity_type={entity_klass}')
        if (last.get('data') or {}).get('execute_record_id'):
            return last
        time.sleep(interval)
    return last


def load_batch_create_module(module):
    folder, filename = DETAILED_MODULE_SCRIPTS[module]
    path = os.path.join(REPO_ROOT, folder, filename)
    spec = importlib.util.spec_from_file_location(f'batch_create_{module.lower()}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# ========== 工作流管理 ==========
def fetch_workflows(token):
    r = _process(token, 'GET', 'workflows?page=1&per_page=100')
    return r.get('data', {}).get('list', [])


def list_workflows(api, token, only_enabled=True):
    """列出所有工作流"""
    workflows = fetch_workflows(token)
    if only_enabled:
        workflows = [w for w in workflows if w.get('status') == 'enable']
    print(f'\n{"="*60}')
    print(f'  可用工作流 ({len(workflows)} 个)')
    print(f'{"="*60}')
    for w in workflows:
        status_icon = '✅' if w['status'] == 'enable' else '⬜'
        print(f'  {status_icon} ID:{w["id"]} {w["name"]}')
        print(f'     模块:{w["entity_klass"]} 触发:{w["trigger_timing_i18n"]} 状态:{w["status_i18n"]}')
    return workflows

def module_created_workflows(api, token, module):
    entity_klass = ENTITY_KLASS_MAP.get(module, module)
    workflows = fetch_workflows(token)
    items = [
        workflow for workflow in workflows
        if workflow.get('entity_klass') == entity_klass and workflow.get('trigger_timing') == 'created'
    ]
    return sorted(items, key=lambda item: item.get('updated_at') or item.get('created_at') or '', reverse=True)


def workflow_payload(workflow, status):
    return {
        'workflow': {
            'name': workflow.get('name'),
            'entity_klass': workflow.get('entity_klass'),
            'trigger_timing': workflow.get('trigger_timing'),
            'trigger_odds': workflow.get('trigger_odds') or 'always',
            'trigger_filters': workflow.get('trigger_filters') or [],
            'editable': workflow.get('editable') or {'enable': 1, 'policy': 'cannot', 'fields': []},
            'notify_others': workflow.get('notify_others') or [],
            'allow_again_reject': workflow.get('allow_again_reject') or False,
            'status': status,
        },
        'app': 'crm',
    }


def build_approvers(api, token):
    users_pc = _pc(api, token, 'GET', 'users?page=1&per_page=50')
    users_data = users_pc.get('data', {})
    user_list = users_data.get('list') or users_data.get('users') or []
    return [
        {'uid': u['uid'], 'name': u['name'], 'tabId': 'users', 'tabType': 'user', 'third_userid': None}
        for u in user_list[:3] if u.get('uid')
    ]


def workflow_version_payload(api, token, workflow, module):
    workflow_id = workflow.get('id')
    workflow_name = workflow.get('name') or f'{module}新增审批'
    current = current_user_info(api, token)
    current_uid = (
        (workflow.get('update_user') or {}).get('uid')
        or (workflow.get('user') or {}).get('uid')
        or current.get('uid')
        or current.get('user_id')
        or 0
    )
    workflow_oid = workflow.get('oid') or current.get('organization_id')
    approvers = build_approvers(api, token)
    if not approvers:
        return None

    end_id = 'lxcrmjava' + uuid.uuid4().hex
    return {
        'workflow_id': str(workflow_id),
        'snapshot_url': '',
        'workflow_version': {
            'elements': [
                {'id': 'start', 'name': 'start', 'type': 'STARTEVENT', 'lxData': {'title': '', 'frontEndNodeType': 'startNode'}},
                {'id': 'approve_node', 'name': '审批节点', 'type': 'APPROVEELEMENT',
                 'lxData': {'title': '', 'frontEndNodeType': 'approveNodeLikeBasicNode'},
                 'parameters': {
                     'name': '审批节点',
                     'approvers': {'users': approvers},
                     'approveType': 'ORAPPROVE',
                     'approval_opinion': 'optional',
                     'allowEditableFields': [],
                     'showAllowEditableFields': False,
                 }},
                {'id': end_id, 'name': end_id, 'type': 'ENDEVENT',
                 'lxData': {'title': '', 'frontEndNodeType': 'endNode'}, 'parameters': {}},
            ],
            'sequences': [
                {'id': 'startNextIdapprove_node', 'name': 'startNextIdapprove_node', 'sourceRef': 'start', 'targetRef': 'approve_node'},
                {'id': f'approve_nodeNextId{end_id}', 'name': f'approve_nodeNextId{end_id}', 'sourceRef': 'approve_node', 'targetRef': end_id},
            ],
            'name': workflow_name,
            'active': True,
            'appType': 'ikcrm',
            'id': '',
            'uid': current_uid,
            'oid': workflow_oid,
            'settings': {
                'allowAddCc': False,
                'allowWithdraw': True,
                'configVersion': 2,
                'allowAdminProxy': True,
                'allowAgainReject': False,
                'allowRepeatApproval': False,
                'emptyApproverStatus': 'AUTOMATIC_FORWARD_TO_ADMIN',
                'ccRecipientsSettings': [],
                'allowApprovalWhenInitApprover': False,
            },
        },
    }


def apply_workflow_definition(api, token, workflow, module):
    workflow_id = workflow.get('id')
    if not workflow_id:
        return False
    detail = (_process(token, 'GET', f'workflows/{workflow_id}').get('data') or workflow)
    payload = workflow_version_payload(api, token, detail, module)
    if not payload:
        print('  ✗ 没有可用审批人，无法应用审批流程')
        return False
    result = _process(token, 'POST', 'workflows/flow_enable', payload)
    if result.get('code') != 0:
        print(f'  ✗ 应用审批流程失败: {result.get("message","?")}')
        return False
    print(f'  ✓ 已应用审批流程: workflow={workflow_id}')
    return True


def enable_existing_workflow(api, token, workflow, module):
    workflow_id = workflow.get('id')
    if not workflow_id:
        return None
    detail = (_process(token, 'GET', f'workflows/{workflow_id}').get('data') or workflow)
    update_result = _process(token, 'PUT', f'workflows/{workflow_id}', workflow_payload(detail, 'enable'))
    if update_result.get('code') not in (0, None):
        print(f'  ✗ 启用审批设置失败: {update_result.get("message","?")}')
        return None

    if not apply_workflow_definition(api, token, detail, module):
        return None

    print(f'  ✓ 已启用审批设置 ID:{workflow_id} {detail.get("name")}')
    return workflow_id


def ensure_workflow_enabled(api, token, module):
    """确保模块新增审批可用：有启用则复用，有禁用则启用最新，无设置则创建。"""
    workflows = module_created_workflows(api, token, module)
    for workflow in workflows:
        if workflow.get('status') == 'enable':
            if not apply_workflow_definition(api, token, workflow, module):
                return None
            print(f'  ✓ 已存在启用审批流，复用 ID:{workflow.get("id")} {workflow.get("name")}')
            return workflow.get('id')
    if workflows:
        latest = workflows[0]
        print(f'  发现禁用审批设置，准备启用最新一条 ID:{latest.get("id")} {latest.get("name")}')
        return enable_existing_workflow(api, token, latest, module)
    print(f'  未找到 {module} 新增审批设置，准备创建一条')
    return create_workflow(api, token, module)

def create_workflow(api, token, module):
    """创建并启用指定模块的审批流"""
    entity_klass = ENTITY_KLASS_MAP.get(module, module)
    print(f'  准备创建 {module} 审批流...')
    
    # 创建审批流
    workflow_data = {
        'workflow': {
            'datarange': [],
            'trigger_odds': 'always',
            'name': f'{module}新增审批',
            'entity_klass': entity_klass,
            'trigger_timing': 'created',
            'editable': {'enable': 1, 'policy': 'cannot', 'fields': []},
            'notify_others': [],
            'notify_others_or_editable_policy0': 'editable_policy',
            'trigger_filters': [],
            'allow_again_reject': False,
            'notify_others_desc': []
        },
        'app': 'crm'
    }
    
    r1 = _process(token, 'POST', 'workflows', workflow_data)
    wid = r1.get('data', {}).get('id')
    if not wid:
        print(f'  ✗ 创建工作流失败: {r1.get("message","?")}')
        return None
    print(f'  ✓ 创建工作流 ID:{wid}')

    detail = (_process(token, 'GET', f'workflows/{wid}').get('data') or {'id': wid, 'name': f'{module}新增审批'})
    if apply_workflow_definition(api, token, detail, module):
        print(f'  ✅ 启用 {module} 审批流成功! ID:{wid}')
        return wid
    else:
        print('  ✗ 启用审批流失败')
        return None


def enable_workflow(api, token, module):
    """确保指定模块的新增审批流已启用"""
    print(f'  准备检查 {module} 审批流...')
    return ensure_workflow_enabled(api, token, module)

# ========== 字段发现 ==========
def discover(api, token, module):
    """发现模块所需的字段定义"""
    cfg = MODULE_CONFIG[module]
    info = {'customers': [], 'pc_users': [], 'products': [], 'fm': {}, 'template_id': None}

    if module in DETAILED_MODULE_SCRIPTS:
        try:
            batch_module = load_batch_create_module(module)
            batch_info = batch_module.discover(api, token)
            info['batch_module'] = batch_module
            info['batch_info'] = batch_info
            info['fm'] = batch_info.get('fm', {})
            users = batch_info.get('users') or batch_info.get('pc_users') or []
            info['pc_users'] = [int(u) for u in users if str(u).isdigit()]
            info['customers'] = [{'id': c} for c in batch_info.get('customers', [])] or [{'id': c} for c in batch_info.get('cs', [])]
            info['products'] = batch_info.get('products') or batch_info.get('pd') or []
            return info
        except Exception as exc:
            print(f'  ⚠️ {module} 详细字段发现失败，降级使用基础创建: {exc}')
    
    # 获取依赖数据
    if 'customers' in cfg.get('dependencies', []):
        cl = _v2(api, token, 'GET', 'customers?per_page=20&sort=created_at&order=desc')
        if cl:
            info['customers'] = [{'id': c['id'], 'name': c.get('name', '')} for c in cl.get('data', {}).get('customers', []) if c.get('id')]
    
    if 'products' in cfg.get('dependencies', []):
        pr = _v2(api, token, 'GET', 'products?per_page=20')
        if pr:
            info['products'] = [str(p['id']) for p in pr.get('data', {}).get('products', []) if p.get('id')]
    
    us = _v2(api, token, 'GET', 'user/simple_list')
    if us:
        info['pc_users'] = [int(u['value']) for u in us.get('simple_users', []) if u.get('value') and u.get('value') != '']
    
    # 系统字段映射
    fm_name = cfg.get('field_maps_source', cfg['api_path'])
    fm = _v2(api, token, 'GET', f'field_maps/{fm_name}')
    if fm:
        for f in fm.get('data', {}).get(fm_name, []):
            vals = [v for v in f.get('field_values', []) if v.get('status') == 'enable']
            if vals:
                info['fm'][f['field_name']] = [str(v['id']) for v in vals]

    business_type = first_enabled_business_type(api, token, module)
    if business_type:
        info['template_id'] = business_type.get('id')
        print(f'  业务类型:{business_type.get("name")}({business_type.get("id")})')
    
    return info

def validate_dependencies(module, info):
    cfg = MODULE_CONFIG[module]
    missing = []
    if 'customers' in cfg.get('dependencies', []) and not info['customers']:
        missing.append('客户')
    if 'products' in cfg.get('dependencies', []) and not info['products']:
        missing.append('产品')
    if missing:
        print(f'  ✗ 缺少依赖数据: {", ".join(missing)}')
        return False
    return True

# ========== 实体创建 ==========
def detailed_field_count(batch_info):
    fields = batch_info.get('fields') or batch_info.get('fd') or {}
    return sum(len(fields.get(key, [])) for key in fields)


def build_detailed_data(api, token, module, batch_module, batch_info):
    suffix = datetime.now().strftime('%H%M%S')
    if module in ('Quotation', 'Contract'):
        data = batch_module.build(batch_info, api, token)
    elif module == 'Contact':
        customer_id = int(random.choice(batch_info.get('cs'))) if batch_info.get('cs') else None
        data = {
            'name': f'审批详细联系人-{suffix}',
            'customer_id': customer_id,
            'department': random.choice(['研发部', '产品部', '销售部', '市场部', '财务部']),
            'job': random.choice(['经理', '总监', '主管', '工程师', '销售']),
            'category': random.choice(batch_info.get('fm', {}).get('category', ['2103262'])),
            'note': f'审批流程详细联系人测试-{suffix}',
            'birth_date': batch_module.rf()[:7] + '-01',
            'gender': random.choice(['male', 'female']),
            'address_attributes': {
                'phone': batch_module.rp(),
                'tel': '0519-' + str(random.randint(10000000, 99999999)),
                'email': batch_module.re(),
                'wechat': batch_module.rp(),
                'qq': str(random.randint(10000000, 999999999)),
                'wangwang': batch_module.rp(),
                'url': batch_module.ru(),
                'zip': '5180' + str(random.randint(10, 99)),
                'province_id': random.choice([1, 10, 13, 21]),
                'detail_address': random.choice(['科技路', '创新路', '发展大道']) + str(random.randint(1, 999)) + '号',
            },
        }
        batch_module.fill_fields(data, batch_info)
    else:
        data = batch_module.build(batch_info)

    if module == 'Lead':
        data['name'] = f'审批详细线索-{suffix}'
        data['company_name'] = f'审批测试{batch_module.rt()}科技'
        data['note'] = f'审批流程详细线索测试-{suffix}'
    elif module == 'Customer':
        data['name'] = f'审批详细客户-{suffix}'
        data['company_name'] = f'审批测试{batch_module.rt()}科技有限公司'
        data['note'] = f'审批流程详细客户测试-{suffix}'
        data.pop('approve_status', None)
        data.pop('parent_id', None)
    elif module == 'Opportunity':
        data['title'] = f'审批详细商机-{suffix}'
        data['note'] = f'审批流程详细商机测试-{suffix}'
    elif module == 'Quotation':
        data['name'] = f'审批详细报价单-{suffix}'
        data['title'] = f'审批详细报价单-{suffix}'
        data['note'] = f'审批流程详细报价单测试-{suffix}'
    elif module == 'Contract':
        data['title'] = f'审批详细合同-{suffix}'
        data['special_terms'] = f'审批流程详细合同测试-{suffix}'
        data.setdefault('intl_extra_attributes', {})
        data.setdefault('received_payment_plans_attributes', [])
    return data


def create_detailed_entity(api, token, module, info, attachment_dir=None):
    """复用各模块 batch_create 脚本创建更完整的数据。"""
    batch_module = info.get('batch_module') or load_batch_create_module(module)
    batch_info = info.get('batch_info') or batch_module.discover(api, token)
    data = build_detailed_data(api, token, module, batch_module, batch_info)
    cfg = MODULE_CONFIG[module]
    uploaded_files = len(process_file_fields(api, token, module, data, attachment_dir))

    base = api.rstrip()
    if module in PC_CREATE_MODULES or uploaded_files:
        base = pc_url(api).rstrip()
        url = f'{base}/api/pc/{cfg["api_path"]}'
    else:
        url = f'{base}/api/v2/{cfg["api_path"]}'

    resp = requests.post(
        url,
        headers={'Content-Type': 'application/json', 'Authorization': f'Token token={token}'},
        json={cfg['body_key']: data},
        timeout=30,
    )
    try:
        result = resp.json()
    except ValueError:
        result = {'message': resp.text[:500]}

    eid = result.get('data', {}).get('id')
    status = result.get('data', {}).get('approve_status', '')
    if eid:
        attached_files = upload_attach_files(api, token, module, eid, attachment_dir)
        print(
            f'  ✓ 创建详细{module} ID:{eid} 审批状态:{status} '
            f'自定义字段:{detailed_field_count(batch_info)} 文件字段:{uploaded_files} 系统附件:{attached_files}'
        )
        return eid, status

    print(f'  ✗ 创建详细{module}失败: {result.get("message","?")}')
    return None, None


def create_entity(api, token, module, info, attachment_dir=None):
    """创建指定模块的实体"""
    if info.get('batch_info'):
        return create_detailed_entity(api, token, module, info, attachment_dir)

    cfg = MODULE_CONFIG[module]
    if not validate_dependencies(module, info):
        return None, None
    
    data = {cfg['body_key']: {}}
    
    for field, value_spec in cfg['create_fields'].items():
        if callable(value_spec):
            data[cfg['body_key']][field] = value_spec()
        elif value_spec == 'customer_id' and info['customers']:
            data[cfg['body_key']][field] = random.choice(info['customers'])['id']
        elif value_spec == 'product_id' and info['products']:
            data[cfg['body_key']][field] = random.choice(info['products'])
    
    # 系统字段
    for fm_name in cfg.get('field_maps', []):
        if info['fm'].get(fm_name):
            data[cfg['body_key']][fm_name] = random.choice(info['fm'][fm_name])

    if info.get('template_id'):
        data[cfg['body_key']]['custom_field_template_id'] = info['template_id']
    
    r = _v2(api, token, 'POST', cfg['api_path'], data)
    eid = r.get('data', {}).get('id')
    status = r.get('data', {}).get('approve_status', '')
    
    if eid:
        print(f'  ✓ 创建{module} ID:{eid} 审批状态:{status}')
        return eid, status
    else:
        print(f'  ✗ 创建{module}失败: {r.get("message","?")}')
        return None, None

# ========== 审批操作 ==========
def extract_approver_uid(details):
    """从流程详情里提取一个可代理审批的 uid。"""
    for detail in details:
        users = detail.get('setting_all_users') or []
        if users:
            return users[0].get('uid')

        for key in ('approval_users', 'approvers', 'users'):
            value = detail.get(key)
            if isinstance(value, list) and value:
                uid = value[0].get('uid') if isinstance(value[0], dict) else None
                if uid:
                    return uid
            if isinstance(value, dict):
                users = value.get('users') or []
                if users:
                    return users[0].get('uid')
    return None


def validate_process_record(data):
    record = data.get('execute_record') or {}
    if not record.get('execution_id') and record.get('status') == 'applying':
        print('  ✗ 流程平台执行实例未启动: execution_id 为空')
        print('    当前 CRM 已进入待审批，但流程引擎没有生成审批任务，需要检查该模块的审批流配置/流程平台支持。')
        return False
    return True


def approve_via_process(api, token, entity_id, module):
    """通过流程平台审批通过"""
    entity_klass = ENTITY_KLASS_MAP.get(module, module)
    
    r = wait_execute_record(token, entity_id, entity_klass)
    data = r.get('data', {})
    record_id = data.get('execute_record_id')
    if not record_id:
        print(f'  ✗ 未找到执行记录')
        return False
    
    status = data.get('execute_record', {}).get('status', '')
    print(f'  执行记录ID: {record_id} 状态: {status}')
    
    if status == 'pass':
        print(f'  ⚠️ 审批已通过')
        return True

    if not validate_process_record(data):
        return False
    
    details = data.get('execution_details', [])
    agent_uid = extract_approver_uid(details)
    
    if not agent_uid:
        print(f'  ✗ 未找到审批人')
        return False
    
    print(f'  代理审批人: uid={agent_uid}')
    
    result = _process(token, 'POST', f'execute_records/{record_id}/perform', {
        'execute_action': 'pass',
        'execute_opinion': f'审批通过-{datetime.now().strftime("%H%M%S")}',
        'agent_uid': agent_uid
    })
    
    if result.get('code') == 0:
        print(f'  ✓ 审批通过! {module}ID:{entity_id}')
        return True
    else:
        print(f'  ✗ 审批失败: {result.get("message","?")}')
        return False

def reject_via_process(api, token, entity_id, module):
    """通过流程平台驳回"""
    entity_klass = ENTITY_KLASS_MAP.get(module, module)
    
    r = wait_execute_record(token, entity_id, entity_klass)
    data = r.get('data', {})
    record_id = data.get('execute_record_id')
    if not record_id:
        print(f'  ✗ 未找到执行记录')
        return False

    if not validate_process_record(data):
        return False
    
    details = data.get('execution_details', [])
    agent_uid = extract_approver_uid(details)

    if not agent_uid:
        print(f'  ✗ 未找到审批人')
        return False
    
    result = _process(token, 'POST', f'execute_records/{record_id}/perform', {
        'execute_action': 'reject',
        'execute_opinion': f'驳回原因-{datetime.now().strftime("%H%M%S")}',
        'agent_uid': agent_uid
    })
    if result.get('code') == 0:
        print(f'  ✓ 驳回成功! {module}ID:{entity_id}')
        return True
    else:
        print(f'  ✗ 驳回失败: {result.get("message","?")}')
        return False

def get_detail(api, token, entity_id, module):
    """查询审批详情"""
    entity_klass = ENTITY_KLASS_MAP.get(module, module)
    r = _process(token, 'GET', f'execute_records/detail?entity_id={entity_id}&entity_type={entity_klass}')
    data = r.get('data', {})
    exec_status = data.get('execute_record', {}).get('status_i18n', '?')
    print(f'  流程平台状态: {exec_status}')
    
    # 也查CRM状态
    cfg = MODULE_CONFIG.get(module)
    if cfg:
        cr = _v2(api, token, 'GET', f'{cfg["api_path"]}/{entity_id}')
        crm_data = cr.get('data', {})
        entity_data = crm_data.get(cfg['body_key']) if isinstance(crm_data, dict) else {}
        crm_status = (
            crm_data.get('approve_status_i18n')
            or (entity_data or {}).get('approve_status_i18n')
        )
        if not crm_status:
            raw_status = crm_data.get('approve_status') or (entity_data or {}).get('approve_status')
            crm_status = {
                'approved': '已通过',
                'applying': '待审批',
                'rejected': '已驳回',
                '1': '待审批',
            }.get(str(raw_status), raw_status or '?')
        print(f'  CRM状态: {crm_status}')
    
    return data

# ========== 主入口 ==========
def main():
    global PROCESS_API
    cfg = load_config()
    p = argparse.ArgumentParser(description='审批流程自动化(配置化)')
    p.add_argument('--api', default=cfg.get('api', ''))
    p.add_argument('--token', default=cfg.get('token', ''))
    p.add_argument('--process-api', default=cfg.get('process_api', DEFAULT_PROCESS_API))
    p.add_argument('--module', default='Contract', choices=list(MODULE_CONFIG.keys()),
                   help='测试模块 (Contract/Lead/Opportunity/Customer/Quotation/Contact)')
    p.add_argument('--entity-id', type=int, help='实体ID')
    p.add_argument('--action', choices=['full', 'approve', 'reject', 'detail', 'enable'],
                   default='full', help='操作类型')
    p.add_argument('--list-workflows', action='store_true', help='列出所有工作流')
    p.add_argument('--attachment-dir', default=cfg.get('attachment_dir'),
                   help='本地图片/附件目录；传入后会随机上传到文件字段和附件字段')
    
    a = p.parse_args()
    if not a.api or not a.token:
        p.error('请在config.json中配置api和token')
    
    api = a.api.rstrip('/')
    token = a.token
    PROCESS_API = a.process_api.rstrip('/')
    
    # 列出工作流
    if a.list_workflows:
        list_workflows(api, token)
        return
    
    module = a.module
    entity_klass = ENTITY_KLASS_MAP[module]
    
    # 启用审批流
    if a.action == 'enable':
        enable_workflow(api, token, module)
        return
    
    # 对已有实体操作
    if a.action in ('approve', 'reject', 'detail'):
        if not a.entity_id:
            p.error('--entity-id 必需')
        if a.action == 'approve':
            approve_via_process(api, token, a.entity_id, module)
        elif a.action == 'reject':
            reject_via_process(api, token, a.entity_id, module)
        else:
            get_detail(api, token, a.entity_id, module)
        return
    
    # === full 完整流程 ===
    print(f'\n{"="*60}')
    print(f'  审批流程自动化 - 模块: {module}')
    print(f'{"="*60}')

    print('\n[Step 0/5] 校验审批设置...')
    workflow_id = ensure_workflow_enabled(api, token, module)
    if not workflow_id:
        print('审批设置不可用，终止')
        return
    
    print('\n[Step 1/5] 发现字段定义...')
    info = discover(api, token, module)
    print(f'  客户:{len(info["customers"])} 用户:{len(info["pc_users"])} 产品:{len(info["products"])}')
    
    print(f'\n[Step 2/5] 创建{module}...')
    eid, status = create_entity(api, token, module, info, a.attachment_dir)
    if not eid:
        print('终止')
        return
    time.sleep(1)
    
    if status == 'approved':
        print(f'\n  ⚠️ {module}已自动审批通过')
        return
    
    print(f'\n[Step 3/5] 查询流程平台执行记录...')
    time.sleep(2)
    
    print(f'\n[Step 4/5] 执行审批...')
    ok = approve_via_process(api, token, eid, module)
    if not ok:
        print('审批失败，终止')
        return
    time.sleep(1)
    
    print(f'\n[Step 5/5] 验证审批结果...')
    get_detail(api, token, eid, module)
    print(f'\n{"="*60}')
    print(f'  {module}ID: {eid}  审批完成')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
