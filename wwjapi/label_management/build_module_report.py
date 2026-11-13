#!/usr/bin/env python3
"""Consolidate observed results, preserving raw evidence and review corrections."""
import copy
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'results'
FIRST = '20261112-162502'
SECOND = '20261112-163949'
PROOF = '20261112-164622'
models = {'Customer':'客户','MarketActivity':'市场活动','Contact':'联系人','Opportunity':'商机','Quotation':'报价单',
          'Contract':'合同','ReceivedPayment':'回款','InvoicedPayment':'开票','Product':'产品'}
unsupported = {'MarketActivity','ReceivedPayment','InvoicedPayment'}
latest = {}
for run_id in (FIRST, SECOND):
    raw = json.loads((ROOT / run_id / 'modules-summary.json').read_text())
    for item in raw['results']:
        if item['model'] not in models or item['case'] in ('fixture_setup', 'batch_edit', 'import'):
            continue
        if item['model'] in unsupported and (item['case'].startswith('batch_') or item['case'].startswith('wrong_module')):
            continue
        row = copy.deepcopy(item)
        row['run'] = run_id
        latest[(row['model'], row['case'])] = row
correction = json.loads((ROOT / SECOND / 'review-adjustments.json').read_text())['template_value_normalization']
assert correction['status'] == 'PASS'
latest[('Customer','import_template_options')].update(status='PASS', review=correction)
rows = list(latest.values())
counts = Counter(x['status'] for x in rows)
assert len(rows) == 167, len(rows)
assert counts == {'PASS':162,'FAIL':5}, counts
last = json.loads((ROOT / SECOND / 'modules-summary.json').read_text())
cleanup_done = all(x['deleted'] for x in last['entities']) and not last['remaining_group_ids'] and not last['remaining_label_ids']
proof = json.loads((ROOT / PROOF / 'customer-isolation-proof.json').read_text())
summary = {'scope':'PC API integration; excludes unsupported functions and quotation-to-contract per user',
           'counts':dict(counts),'checkpoint_count':len(rows),
           'counting_note':'Shared fixture scenarios and import rows/checks; not 167 isolated unit tests or a full requirement acceptance rate.',
           'cases':rows,'customer_isolation_proof':proof,'cleanup_complete':cleanup_done,
           'cleanup_entities_second_run':len(last['entities']),
           'excluded':{'batch_edit':['MarketActivity','ReceivedPayment','InvoicedPayment'],
                       'import':['MarketActivity'],'mapping':['Quotation to Contract']}}
(ROOT / 'remaining-modules-final.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
lines = ['# STORY 22730：PC 剩余模块标签测试结果', '',
'测试日期：2026-11-12。测试环境：`lxcrm-test.weiwenjia.com`，企业 5500906。使用 `test-master`，通过 PC API 执行；不代表页面交互或移动端验收。', '',
'## 结论', '',
'本轮有效检查点 **167 个：通过 162，失败 5**。5 个失败归并为 **2 个新增问题**：客户批量编辑缺少模块适用范围校验；产品导入成功后标签丢失。', '',
'统计为各模块场景、共享导入任务中的行级检查、模板检查和导入历史核对。它们并非 167 个独立单元测试，也不是整项需求的验收通过率。重复执行取最终有效接口结果；原始请求与首次失败均保留。', '',
'## 按模块结果', '',
'| 模块 | 单条新建/编辑/清空/单选约束 | 四种批量模式及范围校验 | 导入 10 行矩阵 |',
'|---|---|---|---|']
for model,name in models.items():
    direct = [x for x in rows if x['model']==model and not x['case'].startswith(('mapping_', 'import_'))]
    basic = [x for x in direct if not x['case'].startswith(('batch_', 'wrong_module'))]
    batch = [x for x in direct if x['case'].startswith(('batch_', 'wrong_module'))]
    imports = [x for x in rows if x['model']==model and x['case'].startswith('import_') and x['case'] not in ('import_template_options','import_history_counts')]
    basic_text = '通过' if all(x['status']=='PASS' for x in basic) and len(basic)==3 else '见明细'
    batch_text = '不支持，用户排除' if model in unsupported else '跨模块追加/替换失败；常规四模式通过' if model=='Customer' else '通过'
    import_text = '不支持，用户排除' if model=='MarketActivity' else '4 条合法标签未落库；其余 6 条通过' if model=='Product' else '10/10 通过'
    lines.append(f'| {name} | {basic_text} | {batch_text} | {import_text} |')
lines += ['',
'基础场景验证：多选与单选跨组新建、空标签新建、编辑、未传标签时保留原值、显式空数组清空；单选同组两个值不得同时保存。', '',
'支持批量编辑的 6 个模块验证：追加、多选去重、单选同组替换、全部替换、移除任一匹配、移除完全匹配、跨组条件、部分匹配、重复请求、空标签记录，以及未勾选记录不受影响。客户的模块范围校验另外按四种模式逐项独立复现。', '',
'8 个支持导入模块各执行一个 10 行任务：中文逗号多选、英文逗号多选、单选一个值、跨分组、空值、未知标签、模块不适用标签、单选多值、合法混未知、错误分隔符。每个任务均为 5 行成功、5 行预期失败，并核对业务详情及错误报告。导入任务计数成功不等于标签已正确落库，产品问题由详情回读发现。', '',
'模板标签选项核对覆盖 8 个模块。客户模板把纯数字标签 `1212`、`3333` 保存为数字单元格，按显示文本比较后与当前可用标签完全一致；不计缺陷。原始类型差异与复核记录分别保留。', '',
'## 关联新建及流转', '',
'以下 8 条路径通过：客户下新增联系人、商机、报价单、合同；商机下新增报价单；合同下新增回款、开票；商机转合同。每条均先验证源标签，再核对 `/new` 预填标签，直接提交预填返回的标签，最后回读目标及源记录。', '',
'商机转合同预填接口：`GET /api/pc/contracts/new?custom_field_template_id=2382&opportunity_id=<本次自建商机ID>`。提交使用用户提供的外层 `turn_to_contract=true`、`source_name="opportunity"`，绑定本次自建客户与商机。', '',
'报价单生成合同按用户要求暂不测试，等待修复。此前线索转客户的完整链路结果见既有报告，不重复计入本轮 167 项。当前 8 条映射仅验证适用于源和目标的正常值；映射配置关闭、目标不适用值过滤及转换失败回滚未在本轮完整验证。', '',
'## 新增问题', '',
'### NEW-01 / Medium：客户批量追加与替换能保存不适用于客户的标签', '',
'创建仅适用于 `Lead` 的标签分组和标签，再通过客户 `PUT /batch_resources/batch_update` 提交该标签。`append` 和 `replace` 均返回 HTTP 200 / code 0，客户详情实际含有该非法模块标签。合法多选标签仍保留或按替换请求更新。', '',
'独立复现：分组 `2000136`，仅适用 `Lead`，标签 `2200454`。追加客户 `8384922`，预期 `[2200449]`，实际 `[2200449,2200454]`；替换客户 `8384923`，预期 `[2200450]`，实际 `[2200450,2200454]`。这些均为临时数据，已删除。移除任一/完全匹配未引入非法标签。', '',
'建议：客户批量赋值在追加与替换前统一校验标签所属企业、分组及目标模块适用范围。可拒绝整条操作，或按已确认规则过滤；不得保存仅限其他模块的标签。', '',
'证据：`20261112-164622/customer-isolation-proof.json` 及同目录 `evidence.json`；首次复现为 `20261112-162502` 的客户 `wrong_module_four_batch_modes_protect_data`。', '',
'### NEW-02 / High：产品导入显示成功，但有效标签未保存', '',
'下载当前产品原生模板，保留其元数据和验证规则，填入已存在且适用 `Product` 的标签后上传、校验、正式导入。任务 `16219`，附件 `1507013605`，结果显示总数 10、成功 5、失败 5。', '',
'其中 4 行合法标签应分别落库：中文逗号 `[2200449,2200450]`、英文逗号同值、单选 `[2200452]`、跨组 `[2200449,2200452]`。产品 `2904745`、`2904746`、`2904747`、`2904748` 的详情 `labels` 全部为 `[]`。空标签行正常；5 条负向数据均按标签错误拒绝。', '',
'同一组标签的手工创建和编辑已验证可回读。因此本问题定位在产品导入的标签持久化路径。建议补齐导入成功后的标签关联写入，并将导入历史与详情回读纳入回归。', '',
'证据：`20261112-163949/Product-matrix.xlsx`、`Product-matrix-history.json`、`Product-parsed-errors.json`、`modules-summary.json` 和 `evidence.json`。输入单元格经原生模板与导出文件逐格核对；4 条产品数据已纳入清理。', '',
'## 前面已发现的未关闭问题', '',
'| 严重度 | 问题 | 原执行记录 |', '|---|---|---|',
'| Medium | 分组名称 11 字仍可保存，需求上限为 10 字 | `20261112-143907` |',
'| Medium | 非法 `select_type="BadType"` 返回 code 500，并泄露内部异常和堆栈 | `20261112-143907` |',
'| Medium | 单标签改为空名称返回成功，但保留旧值，缺少明确校验反馈 | `20261112-151603` |', '',
'前面 67 条独立 API 场景的去重结果为通过 63、失败 3、跳过 1，跨多次执行汇总，未在本轮全量重跑。此前线索导入 12 个检查点通过，其中 10 条矩阵行共享一个任务。不要把这些统计与本轮检查点直接相加后称为独立用例数。', '',
'## 排除、纠正及未覆盖', '',
'- 用户确认市场活动、回款、开票不支持批量编辑，本轮已排除。最初对通用批量接口的探测异常不作为这些模块功能缺陷。',
'- 用户确认市场活动不支持导入；“不支持的导入类型”为本轮范围排除。',
'- 用户要求暂不测报价单生成合同；待修复后补测。',
'- 联系人页面实际使用 `POST /contacts/{id}/new_update`。最初 `PUT /contacts/{id}` 的结果已作废，正确入口重跑通过。',
'- 报价单初始测试数据折扣 `100` 不合法，改为 `1` 后重跑通过；不计产品缺陷。',
'- 产品第一次编辑缺少唯一请求号，重复请求影响了前置状态。补充 UUID `request_ticket` 后全部单条与批量场景通过，原失败不计缺陷。',
'- 企业声明为高级版，但接口仍报告分组 30、标签 200；灰测/额度配置未确认。50 分组、高级版 500 标签及充分剩余额度下单批 200/201 边界未完成验收。',
'- 本轮仅 PC API；UI 布局/弹窗、筛选/导出/打印、权限矩阵、APP、AI、企微同步、客户公海/线索池及其他业务模板未完成覆盖。',
'- 当前只使用一个管理员和每模块选定模板，不证明其他角色、其他模板均可用。', '',
'## 数据清理与可复查材料', '',
f'第一轮创建的 34 条业务数据、复现追加的 4 条客户均已删除，并用详情不可访问确认。第二轮创建/导入的 {len(last["entities"])} 条业务数据清理状态：**{"已完成" if cleanup_done else "仍在执行，尚未完成"}**。', '',
'每轮仅清理本轮登记的业务记录、标签和分组；用户原有 95 个模块标签及线索标签不作为清理对象。导入文件、错误报告、导入任务历史保留作证据，系统自动编号序列不回退。', '',
'第一轮基线比较发现既有分组 `2000096`、`2000097` 的适用模块新增了 `Contract`。本轮自动化请求未修改这两个分组，不作回滚；因此原始基线比较 FAIL 作为并行环境变化记录，不作为自动化改坏存量配置的证据。', '',
f'- 最终机器明细：`remaining-modules-final.json`（{len(rows)} 个有效检查点，原始证据目录与索引保留）。',
'- 第一轮直接场景：`20261112-162502/evidence.json`、`modules-summary.json`。',
'- 正确接口补测、8 条映射、8 个导入任务：`20261112-163949/`。',
'- 客户范围问题独立复现：`20261112-164622/`。',
'- 执行脚本：`../pc_module_regression.py`、`../pc_module_mappings.py`、`../pc_module_imports.py`。脚本仅从环境变量读取 Token。', '',
'当前结论：存在 2 个新增问题和 3 个此前未关闭问题，暂不建议按整项标签管理需求验收通过。']
(ROOT / 'STORY-22730-PC-剩余模块最终结果.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'counts':dict(counts),'cleanup_complete':cleanup_done,'entities':len(last['entities'])},ensure_ascii=False))
