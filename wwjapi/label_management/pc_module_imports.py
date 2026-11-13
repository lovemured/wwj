#!/usr/bin/env python3
"""Remaining PC module import matrices; only synthetic records and own parents."""
from environment import settings
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import traceback
from urllib.parse import urlencode
import requests
from openpyxl import load_workbook
import pc_api_regression as core
import pc_import_labels as imp
from pc_module_regression import Run, MODELS, PRE

INVENTORY = json.loads((PRE / 'template_inventory.json').read_text())


def options(wb, title):
    return [r[0] for r in wb[title].iter_rows(min_row=2, values_only=True) if r[0] is not None]


def make_rows(run, model, info, wb, scenarios, names):
    ws = wb.worksheets[0]
    headers = [str(c.value or '') for c in ws[info['header_row']]]
    identity = next(i for i, h in enumerate(headers) if
        ('备注' in h if model == 'ReceivedPayment' else
         '开票编号' in h if model == 'InvoicedPayment' else
         '产品名称' in h if model == 'Product' else
         '姓名' in h if model == 'Contact' else
         '商机标题' in h if model == 'Opportunity' else
         '报价单名称' in h if model == 'Quotation' else
         '合同标题' in h if model == 'Contract' else '客户名称' in h) and '关联产品' not in h)
    rows = []
    for key, label_value, _ in scenarios:
        row = [None] * info['columns']
        for i, h in enumerate(headers):
            if '关联产品' in h or '必填' not in h:
                continue
            if '对应客户' in h:
                row[i] = run.parents['customer']['name']
            elif '合同标题' in h and model in ('ReceivedPayment', 'InvoicedPayment'):
                row[i] = run.parents['contract']['name']
            elif '日期' in h:
                row[i] = core.datetime.now().strftime('%Y-%m-%d')
            elif '金额' in h:
                row[i] = 25
            elif '收款人' in h or '经手人' in h:
                row[i] = settings.value('import_user_name', '徐弘')
            elif '跟进状态' in h or '销售阶段' in h or '票据类型' in h:
                title = next(s for s in wb.sheetnames if s.startswith('Sheet') and h.replace('(必填)', '') == s[5:])
                row[i] = options(wb, title)[0]
            elif '规格' in h:
                row[i] = '测试规格'
            else:
                row[i] = names[key]
        row[identity] = names[key]
        row[info['label_col'] - 1] = label_value
        # Resolve relations by IDs owned by this run, as well as unique display names.
        for i, h in enumerate(headers):
            if h.endswith(']ID') and ('对应客户' in h):
                row[i] = run.parents['customer']['id']
            if h.endswith(']ID') and ('对应合同' in h or '合同标题' in h):
                row[i] = run.parents['contract']['id']
        rows.append(row)
    return rows, identity


def find_owned(run, model, names):
    found = {}
    path, _, key = MODELS[model]
    if model == 'ReceivedPayment': key = 'note'
    for page in range(1, 6):
        data = core.success(core.api('GET', '/' + path + '?' + urlencode({
            'page': page, 'per_page': 100, 'sort': 'created_at', 'order': 'desc'})))
        for item in data['list']:
            name = item.get(key)
            if model == 'ReceivedPayment' and name not in names and item.get('contract_id') == run.parents['contract']['id']:
                name = core.success(core.api('GET', '/' + path + '/' + str(item['id']))).get('note')
            if name in names:
                found[name] = item['id']
                if not any(e['model'] == model and e['id'] == item['id'] for e in run.entities):
                    run.entities.append({'model': model, 'id': item['id'], 'name': name, 'deleted': False})
        run.save()
        if not data.get('has_next_page'): break
    return found


def module_import(run, model, info):
    template = core.OUT / (model + '-template.xlsx')
    query = {'custom_field_template_id': run.metadata[model]['template']} if run.metadata[model]['template'] else {}
    response = core.SESSION.get(core.BASE + '/entity_loaders/template/' + model + '.xlsx?' + urlencode(query), timeout=45)
    response.raise_for_status()
    template.write_bytes(response.content)
    if not response.content.startswith(b'PK'):
        run.results.append({'model': model, 'case': 'import_template', 'status': 'BLOCKED', 'response': response.text})
        run.save(); return
    wb = load_workbook(template)
    actual = {str(v) for v in options(wb, 'Sheet标签')}
    expected = {x['content'] for g in core.groups() if model in g['applicable_models'] for x in g['labels']}
    run.results.append({'model': model, 'case': 'import_template_options', 'status': 'PASS' if actual == expected else 'FAIL',
                        'missing': sorted(expected - actual), 'unexpected': sorted(actual - expected)})
    scenarios = [
        ('multi_chinese_comma', '，'.join([run.m1['content'], run.m2['content']]), [run.m1, run.m2]),
        ('multi_ascii_comma', ','.join([run.m1['content'], run.m2['content']]), [run.m1, run.m2]),
        ('radio_one', run.r1['content'], [run.r1]),
        ('cross_groups', '，'.join([run.m1['content'], run.r1['content']]), [run.m1, run.r1]),
        ('blank', None, []),
        ('unknown', core.PREFIX + '不存在', None),
        ('wrong_module', run.excluded['content'], None),
        ('radio_multiple', '，'.join([run.r1['content'], run.r2['content']]), None),
        ('mixed_unknown', '，'.join([run.m1['content'], core.PREFIX + '不存在']), None),
        ('bad_separator', '；'.join([run.m1['content'], run.m2['content']]), None),
    ]
    names = {key: core.PREFIX + model[:3] + str(i) for i, (key, _, _) in enumerate(scenarios)}
    rows, identity = make_rows(run, model, info, wb, scenarios, names)
    plan = {'template': str(template), 'sheet': wb.sheetnames[0], 'dataStart': info['header_row'] + 1,
            'width': info['columns'], 'rows': rows, 'artifact': str(core.OUT / (model + '-artifact.xlsx')),
            'output': str(core.OUT / (model + '-matrix.xlsx')), 'afterPreview': str(core.OUT / (model + '-after.png')),
            'previewRange': f'A{info["header_row"]}:I{info["header_row"] + 3}'}
    plan_path = core.OUT / (model + '-plan.json')
    plan_path.write_text(json.dumps(plan, ensure_ascii=False))
    subprocess.run([str(imp.NODE), str(imp.ROOT / 'import_workbook.mjs'), str(plan_path)], check=True)
    imp.preserve_template(plan)
    try:
        history = imp.import_file(Path(plan['output']), model, run.metadata[model]['template'])
    finally:
        found = find_owned(run, model, set(names.values()))
    errors = {}
    if history.get('fail_count'):
        response = requests.get(history['file_path'], timeout=45)
        response.raise_for_status()
        error_path = core.OUT / (model + '-errors.xlsx')
        error_path.write_bytes(response.content)
        errors_wb = load_workbook(error_path, read_only=True, data_only=True)
        sheet = errors_wb.worksheets[0]
        table = list(sheet.values)
        header = next(i for i, r in enumerate(table) if '错误' in r)
        col = table[header].index('错误')
        # Locate names by exact unique values; error export can reorder columns.
        for row in table[header + 1:]:
            name = next((v for v in row if v in set(names.values())), None)
            if name: errors[name] = row[col]
    imp.write(model + '-parsed-errors.json', errors)
    for key, value, labels in scenarios:
        entity_id = found.get(names[key])
        actual_ids = None
        if entity_id:
            actual_ids = sorted(x['id'] for x in run.detail({'model': model, 'id': entity_id})['labels'])
        expected_ids = None if labels is None else sorted(x['id'] for x in labels)
        error = str(errors.get(names[key], ''))
        passed = (actual_ids == expected_ids and entity_id is not None) if labels is not None else (
            entity_id is None and ('单选，只能填写一个' in error if key == 'radio_multiple' else '不存在或未对本模块启用' in error))
        status = 'PASS' if passed else 'BLOCKED' if labels is not None and entity_id is None and error and '标签' not in error else 'FAIL'
        run.results.append({'model': model, 'case': 'import_' + key, 'status': status,
            'name': names[key], 'value': value, 'expected_label_ids': expected_ids, 'actual_label_ids': actual_ids,
            'entity_id': entity_id, 'error': error})
        run.save()
        print(model, 'import_' + key, status, error, flush=True)
    run.results.append({'model': model, 'case': 'import_history_counts',
        'status': 'PASS' if (history['total_count'], history['success_count'], history['fail_count']) == (10, 5, 5) else 'FAIL',
        'history': history})
    run.save()


if __name__ == '__main__':
    imp.TOKEN = settings.token
    core.SESSION.headers.update(settings.headers())
    spec = importlib.util.spec_from_file_location('import_helper', imp.ROOT.parent / 'import/error-report-import/error_report_import_tester.py')
    imp.helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(imp.helper)
    imp.helper.print_json = lambda *args: None
    link = imp.ROOT / 'node_modules'
    own_link = not link.exists()
    if own_link: link.symlink_to(imp.PACKAGES, target_is_directory=True)
    run = Run()
    try:
        run.prepare()
        from pc_module_mappings import run_mappings
        run_mappings(run)
        for model in ('Quotation', 'Contact', 'Product'):
            try:
                run.records(model)
            except Exception:
                run.results.append({'model': model, 'case': 'fixture_setup', 'status': 'BLOCKED', 'error': traceback.format_exc()})
                run.save()
        subprocess.run([str(imp.NODE), str(imp.MARK), '--operation-kind', 'edit', '--expected-output-count', '8', '--output-format', 'xlsx'], check=True)
        for info in INVENTORY:
            model = info['model']
            if model == 'MarketActivity':
                run.results.append({'model': model, 'case': 'import', 'status': 'OUT_OF_SCOPE', 'reason': '用户确认市场活动不支持导入'})
                run.save()
                continue
            try:
                module_import(run, model, info)
            except Exception:
                run.results.append({'model': model, 'case': 'import_execution', 'status': 'BLOCKED', 'error': traceback.format_exc()})
                run.save(); print(model, run.results[-1]['error'], flush=True)
    finally:
        run.cleanup()
        if own_link: link.unlink()
        print('Evidence:', core.OUT, flush=True)
