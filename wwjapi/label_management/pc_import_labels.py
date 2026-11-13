#!/usr/bin/env python3
"""Online PC Lead label import regression, using synthetic names and own fixtures.

Run with CRM_LABEL_TOKEN in the environment. Never replays the user's attachment.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

import requests
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

import pc_api_regression as core

ROOT = Path(__file__).resolve().parent
NODE = Path('/Users/mured/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
PACKAGES = NODE.parent.parent / 'node_modules'
MARK = Path('/Users/mured/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1111.10930/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ET.register_namespace('', NS[1:-1])


def write(name, value):
    (core.OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def preserve_template(plan):
    """Keep native template metadata, validations and styles outside edited values."""
    start = plan.get('dataStart', 14)
    width = plan.get('width', 70)
    with ZipFile(plan['template']) as source, ZipFile(plan['artifact']) as generated:
        original = ET.fromstring(source.read('xl/worksheets/sheet1.xml'))
        changed = ET.fromstring(generated.read('xl/worksheets/sheet1.xml'))
        strings = []
        if 'xl/sharedStrings.xml' in generated.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(generated.read('xl/sharedStrings.xml'))]
        data = original.find(NS + 'sheetData')
        styles = {''.join(c for c in cell.get('r') if c.isalpha()): cell.get('s')
                  for cell in original.findall(f".//{NS}row[@r='{start}']/{NS}c")}
        for row in list(data):
            if int(row.get('r')) >= start:
                data.remove(row)
        for row in changed.find(NS + 'sheetData'):
            if not start <= int(row.get('r')) < start + len(plan['rows']):
                continue
            for cell in row:
                # Use the template's original data-row style, not re-exported styles.
                col = ''.join(c for c in cell.get('r') if c.isalpha())
                cell.attrib.pop('s', None)
                if styles.get(col):
                    cell.set('s', styles[col])
                if cell.get('t') == 's':
                    value = strings[int(cell.find(NS + 'v').text)]
                    cell.remove(cell.find(NS + 'v'))
                    cell.set('t', 'inlineStr')
                    ET.SubElement(ET.SubElement(cell, NS + 'is'), NS + 't').text = value
            data.append(row)
        original.find(NS + 'dimension').set('ref', f'A1:{get_column_letter(width)}{start - 1 + len(plan["rows"])}')
        with ZipFile(plan['output'], 'w', ZIP_DEFLATED) as output:
            for item in source.infolist():
                output.writestr(item, ET.tostring(original, encoding='utf-8', xml_declaration=True)
                                if item.filename == 'xl/worksheets/sheet1.xml' else source.read(item.filename))
    before = load_workbook(plan['template'])
    after = load_workbook(plan['output'])
    assert before.sheetnames == after.sheetnames
    for old, new in zip(before, after):
        for row in old:
            for cell in row:
                if old.title == plan['sheet'] and cell.row >= start:
                    continue
                assert cell.value == new[cell.coordinate].value, (old.title, cell.coordinate)
    actual = [[after[plan['sheet']].cell(start + i, j + 1).value for j in range(width)]
              for i in range(len(plan['rows']))]
    assert actual == plan['rows'], 'Saved input cells differ from the test plan'


def build(rows, stem, first=False):
    plan = {'template': str(core.OUT / 'template.xlsx'), 'sheet': '线索XS',
            'rows': rows, 'artifact': str(core.OUT / (stem + '-artifact.xlsx')),
            'output': str(core.OUT / (stem + '.xlsx')),
            'beforePreview': str(core.OUT / 'before.png'),
            'afterPreview': str(core.OUT / (stem + '-after.png'))}
    path = core.OUT / (stem + '-plan.json')
    write(path.name, plan)
    if first:
        subprocess.run([str(NODE), str(ROOT / 'import_workbook.mjs'), str(path), 'preview'], check=True)
        subprocess.run([str(NODE), str(MARK), '--operation-kind', 'edit',
                        '--expected-output-count', '2', '--output-format', 'xlsx'], check=True)
    subprocess.run([str(NODE), str(ROOT / 'import_workbook.mjs'), str(path)], check=True)
    preserve_template(plan)
    return Path(plan['output'])


def row(name, labels):
    values = [None] * 70
    values[2], values[4] = labels, name
    return values


def own_leads():
    found = {}
    page = 1
    while True:
        data = core.success(core.api('GET', '/leads?' + urlencode({
            'page': page, 'per_page': 100, 'sort': 'created_at', 'order': 'desc'})))
        for lead in data['list']:
            if lead.get('name') in NAMES:
                found[lead['name']] = lead['id']
                core.OWN_LEADS.add(lead['id'])
        core.save()
        if not data.get('has_next_page') or page >= 5:
            return found
        page += 1


def import_file(path, model='Lead', template_id=None):
    query = {'loader_name': model}
    if template_id:
        query['custom_field_template_id'] = template_id
    new = core.success(core.api('GET', '/entity_loaders/new?' + urlencode(query)))
    listener = helper.FayeListener(helper.DEFAULT_FAYE_URL, new['faye_channel'], new['import_client_id'])
    listener.start()
    try:
        helper.upload_to_oss.qiniu_token_path = '/api/pc/qiniu/auth/oss_upload_token.json'
        uploaded = helper.upload_to_oss('https://lxcrm-test.weiwenjia.com', TOKEN, path)
        write(path.stem + '-attachment.json', uploaded)
        body = {k: new[k] for k in ('import_client_id', 'import_max_count',
                                    'import_trigger_approve_max_count', 'recognize_fields')}
        body.update(loader_name=model, entity_loader_file=uploaded['file_url'],
                    file_attachment_id=uploaded['attachment_id'])
        if template_id:
            body['custom_field_template_id'] = template_id
        core.success(core.api('POST', '/entity_loaders/upload', body))
        validated = listener.wait_for('validated_result', 45)
        write(path.stem + '-validated.json', validated)
        assert validated, 'No validation event; import was not submitted'
        assert str(validated['data']['code']) == '0', validated
        submit = {k: body[k] for k in ('loader_name', 'entity_loader_file', 'file_attachment_id', 'import_client_id')}
        if template_id:
            submit['custom_field_template_id'] = template_id
        core.success(core.api('POST', '/entity_loaders/import', submit))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            for kind in (model, model + '2'):
                history = core.success(core.api('GET', '/entity_loaders/import_histories?' + urlencode({
                    'importable_type': kind, 'page': 1, 'per_page': 30})))
                match = next((x for x in history['list'] if x.get('attachment_id') == uploaded['attachment_id']), None)
                if match:
                    write(path.stem + '-history.json', match)
                    print('IMPORT', path.stem, json.dumps(match, ensure_ascii=False), flush=True)
                    return match
            time.sleep(3)
        raise AssertionError('No completed history for this attachment; inspect before retrying')
    finally:
        write(path.stem + '-events.json', listener.messages)
        listener.stop()


def error_rows(history):
    response = requests.get(history['file_path'], timeout=40)
    response.raise_for_status()
    path = core.OUT / 'matrix-error-report.xlsx'
    path.write_bytes(response.content)
    wb = load_workbook(path, data_only=True)
    sheet = wb.worksheets[0]
    headers = {c.value: c.column for c in sheet[8] if c.value}
    errors = {sheet.cell(i, headers['姓名标题1(必填)']).value:
              sheet.cell(i, headers['错误']).value for i in range(9, sheet.max_row + 1)}
    write('matrix-errors.json', errors)
    return errors, 'Sheet标签' in wb.sheetnames


if __name__ == '__main__':
    TOKEN = os.environ['CRM_LABEL_TOKEN']
    core.SESSION.headers.update({'Authorization': f'Token token="{TOKEN}",device="web"', 'Accept': 'application/json'})
    core.OUT.mkdir(parents=True, exist_ok=True)
    link = ROOT / 'node_modules'
    if not link.exists():
        link.symlink_to(PACKAGES, target_is_directory=True)
    spec = importlib.util.spec_from_file_location('import_helper', ROOT.parent / 'import/error-report-import/error_report_import_tester.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.print_json = lambda *args: None
    baseline = core.groups()
    fixture = core.PCLeadTests()
    NAMES = set()
    outcome = {'status': 'ERROR', 'cases': []}
    try:
        multi = fixture.group(applicable_models=['Lead'])
        radio = fixture.group(name=core.PREFIX + 'R', select_type='radio', applicable_models=['Lead'])
        forbidden = fixture.group(name=core.PREFIX + 'C', applicable_models=['Contact'])
        m1, m2 = [fixture.label(multi['id'], core.PREFIX + '多' + str(i)) for i in range(2)]
        r1, r2 = [fixture.label(radio['id'], core.PREFIX + '单' + str(i)) for i in range(2)]
        excluded = fixture.label(forbidden['id'], core.PREFIX + '联系人')
        response = core.SESSION.get(core.BASE + '/entity_loaders/template/Lead.xlsx', timeout=40)
        response.raise_for_status()
        (core.OUT / 'template.xlsx').write_bytes(response.content)
        wb = load_workbook(core.OUT / 'template.xlsx')
        actual_options = {c.value for row_ in wb['Sheet标签'].iter_rows(min_row=2) for c in row_ if c.value}
        expected_options = {x['content'] for g in core.groups() if 'Lead' in g['applicable_models'] for x in g['labels']}
        assert actual_options == expected_options, (actual_options - expected_options, expected_options - actual_options)
        outcome['cases'].append({'case': 'Lead_template_applicable_label_options', 'status': 'PASS'})
        smoke_name = core.PREFIX + '导入冒烟'
        NAMES.add(smoke_name)
        smoke = import_file(build([row(smoke_name, m1['content'])], 'smoke', first=True))
        found = own_leads()
        assert smoke['success_count'] == 1 and smoke['fail_count'] == 0, smoke
        fixture.assert_lead_label_ids(found[smoke_name], [m1['id']])
        outcome['cases'].append({'case': 'Lead_import_smoke', 'status': 'PASS'})
        scenarios = [
            ('multi_chinese_comma', '，'.join([m1['content'], m2['content']]), [m1['id'], m2['id']]),
            ('multi_ascii_comma', ','.join([m1['content'], m2['content']]), [m1['id'], m2['id']]),
            ('radio_one', r1['content'], [r1['id']]),
            ('cross_groups', '，'.join([m1['content'], r1['content']]), [m1['id'], r1['id']]),
            ('blank', None, []),
            ('unknown', core.PREFIX + '不存在', None),
            ('wrong_module', excluded['content'], None),
            ('radio_multiple', '，'.join([r1['content'], r2['content']]), None),
            ('mixed_unknown', '，'.join([m1['content'], core.PREFIX + '不存在']), None),
            ('bad_separator', '；'.join([m1['content'], m2['content']]), None),
        ]
        names = {key: core.PREFIX + '导入' + str(i) for i, (key, _, _) in enumerate(scenarios)}
        NAMES.update(names.values())
        history = import_file(build([row(names[key], value) for key, value, _ in scenarios], 'matrix'))
        found = own_leads()
        errors, has_label_sheet = error_rows(history)
        assert set(errors) == {names[key] for key, _, expected in scenarios if expected is None}, errors
        assert history['success_count'] == 5 and history['fail_count'] == 5, history
        outcome['error_template_has_label_sheet'] = has_label_sheet
        for key, value, expected in scenarios:
            identifier = found.get(names[key])
            actual = [x['id'] for x in fixture.lead_labels(identifier)] if identifier else None
            passed = (identifier is None) if expected is None else (identifier is not None and sorted(actual) == sorted(expected))
            if expected is None:
                passed = passed and ('单选，只能填写一个' in errors[names[key]] if key == 'radio_multiple'
                                     else '不存在或未对本模块启用' in errors[names[key]])
            outcome['cases'].append({'case': key, 'name': names[key], 'value': value,
                                     'expected_label_ids': expected, 'actual_label_ids': actual,
                                     'error_message': errors.get(names[key]),
                                     'lead_id': identifier, 'status': 'PASS' if passed else 'FAIL'})
        assert history['total_count'] == len(scenarios), history
        outcome['status'] = 'FAIL' if any(c['status'] == 'FAIL' for c in outcome['cases']) else 'PASS'
    except Exception:
        outcome['error'] = traceback.format_exc()
        print(outcome['error'], flush=True)
    finally:
        try:
            own_leads()
            fixture.cleanup_leads(set(core.OWN_LEADS))
            core.cleanup(set(core.OWN_GROUPS), set(core.OWN_LABELS))
            outcome['existing_configuration_unchanged'] = core.groups() == baseline
        except Exception:
            outcome['cleanup_error'] = traceback.format_exc()
        outcome['remaining_lead_ids'] = sorted(core.OWN_LEADS)
        outcome['remaining_group_ids'] = sorted(core.OWN_GROUPS)
        outcome['remaining_label_ids'] = sorted(core.OWN_LABELS)
        write('import-summary.json', outcome)
        print(json.dumps(outcome, ensure_ascii=False), flush=True)
        print('Evidence:', core.OUT, flush=True)
    clean = not (core.OWN_LEADS or core.OWN_GROUPS or core.OWN_LABELS or outcome.get('cleanup_error'))
    raise SystemExit(0 if outcome['status'] == 'PASS' and clean
                     and outcome.get('existing_configuration_unchanged') else 1)
