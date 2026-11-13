#!/usr/bin/env python3
"""Authorized test tenant: mobile lead labels, list and customer conversion.

CRM_LABEL_TOKEN is required. Only this run's records and labels are deleted.
"""
import copy
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


BASE = 'https://lxcrm-api-test.weiwenjia.com/api'
NOW = datetime.now(ZoneInfo('Asia/Shanghai'))
OUT = Path(__file__).resolve().parent / 'results' / NOW.strftime('%Y%m%d-%H%M%S-mobile-edit-conversion')
PREFIX = 'M' + uuid.uuid4().hex[:6]


def main():
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Token token="{os.environ["CRM_LABEL_TOKEN"]}",device="lxcrm_duli",version_code="4.0.1"',
        'Content-Type': 'application/json; chartset=utf-8',
        'Origin': 'https://crmh5-test.weiwenjia.com', 'X-Requested-With': 'com.lixiaoyun.aike',
    })
    records, cases, owned, mappings = [], [], [], []
    OUT.mkdir(parents=True)

    def save():
        (OUT / 'evidence.json').write_text(json.dumps({
            'prefix': PREFIX, 'requests': records, 'cases': cases,
            'remaining_owned': owned, 'mappings': mappings,
        }, ensure_ascii=False, indent=2))

    def api(method, path, body=None):
        time.sleep(0.7)  # Pace requests in the shared test environment.
        r = session.request(method, BASE + path, json=body, timeout=30)
        try:
            p = r.json()
        except ValueError:
            p = {'non_json': r.text[:500]}
        records.append({'method': method, 'path': path, 'request': body,
                        'http_status': r.status_code, 'response': p})
        resource = path.split('?')[0]
        if method == 'POST' and resource in ('/v2/leads', '/v2/customers', '/pc/label_groups', '/pc/labels') and p.get('code') == 0:
            owned.append({'path': resource + '/' + str(p['data']['id'])})
        save()
        assert r.status_code == 200 and p.get('code') == 0, (r.status_code, p.get('code'), p.get('message'))
        return p.get('data')

    def case(name, fn):
        start = len(records)
        try:
            fn()
            result = {'case': name, 'status': 'PASS'}
        except Exception:
            result = {'case': name, 'status': 'FAIL', 'error': traceback.format_exc()}
        result.update(evidence_start=start, evidence_end=len(records))
        cases.append(result); save()
        print(name, result['status'], result.get('error', ''), flush=True)

    def ids(values):
        return sorted(x['id'] for x in values)

    def picked(labels):
        return [{'id': x['id']} for x in labels]

    lead_body = {
        'source': 392064, 'status': 617883, 'text_asset_a063a3': 'false',
        'text_area_asset_df70dd': '20', 'numeric_asset_922345': 2,
        'numeric_asset_aa4b85': 1, 'numeric_asset_39fe31': 1.55,
        'numeric_asset_714d0e': -0.0083, 'numeric_asset_97dc97': 0,
        'datetime_asset_f4fc01': NOW.strftime('%Y-%m-%d'),
        'user_id': 1000025901, 'owned_department_id': 5506212,
        'approve_status': 'approved', 'address_attributes': {}, 'product_assets_attributes': [],
    }

    def create_lead(labels, suffix):
        body = copy.deepcopy(lead_body)
        body.update(name=PREFIX + suffix, labels=picked(labels))
        return api('POST', '/v2/leads?request_ticket=' + str(uuid.uuid4()), {'lead': body})

    def check_lead(identifier, expected):
        for surface in ('v2', 'pc'):
            detail = api('GET', f'/{surface}/leads/{identifier}')
            assert ids(detail['labels']) == ids(expected), (surface, ids(expected), detail['labels'])
        listing = api('GET', '/v3/leads?page=1&per_page=15&sort=updated_at&order=desc')
        row = next(x for x in listing['list'] if x['id'] == identifier)
        # List exposes labels_mapped; detail exposes labels.
        value = row['labels_mapped']
        assert ids(value) == ids(expected), (ids(expected), value)
        assert sorted(x['content'] for x in value) == sorted(x['content'] for x in expected)
        return detail

    try:
        api('GET', '/pc/label_groups')
        groups = []
        for suffix, kind, models in [('共多', 'multi', ['Lead', 'Customer', 'Contact']),
                                      ('共单', 'radio', ['Lead', 'Customer', 'Contact']),
                                      ('独有', 'multi', ['Lead'])]:
            groups.append(api('POST', '/pc/label_groups', {'label_group': {
                'name': PREFIX + suffix, 'select_type': kind, 'color': '#1890FF',
                'applicable_models': models}}))
        labels = []
        for group, suffixes in zip(groups, [('多1', '多2'), ('单1', '单2'), ('独1',)]):
            for suffix in suffixes:
                labels.append(api('POST', '/pc/labels', {'label': {
                    'label_group_id': group['id'], 'content': PREFIX + suffix}}))
        m1, m2, r1, r2, private = labels
        def edit(selected, expected=None, omit=False):
            body = copy.deepcopy(lead_body)
            body.update(id=identifier, name=PREFIX + '编辑')
            if not omit:
                body['labels'] = picked(selected)
            api('PUT', f'/v2/leads/{identifier}', {'lead': body})
            check_lead(identifier, selected if expected is None else expected)

        if '--conversion-only' not in sys.argv:
            identifier = create_lead([m1], '编辑')['id']
            case('edit_replace_multi', lambda: edit([m2]))
            case('edit_shared_multi_and_radio', lambda: edit([m1, m2, r1]))
            case('edit_switch_radio', lambda: edit([m1, m2, r2]))
            case('edit_omit_labels_keeps_values', lambda: edit([], [m1, m2, r2], omit=True))
            case('edit_duplicate_ids_deduplicated', lambda: edit([m1, m1, r1], [m1, r1]))
            case('edit_clear_labels', lambda: edit([]))
            case('edit_reselect_after_clear', lambda: edit([m2, r2]))

        def convert(source_labels, expected, suffix):
            source = create_lead(source_labels, suffix)
            source_id = source['id']
            before = check_lead(source_id, source_labels)
            assert not before['turned_to_customer'] and not before['turned_customer_id'], before['turned_customer_id']
            preview = api('GET', f'/v2/leads/{source_id}/turn_to_customer?is_check=false&custom_field_template_id=1172')
            assert ids(preview['labels']) == ids(expected), (ids(expected), preview.get('labels'))
            after_preview = api('GET', f'/v2/leads/{source_id}')
            assert not after_preview['turned_to_customer'] and not after_preview['turned_customer_id']
            assert ids(after_preview['labels']) == ids(source_labels)
            contact = {
                'name': PREFIX + suffix + '联系人', 'department': '2', 'job': 'efe',
                'numeric_asset_29dc2b': 0.99, 'labels': picked(expected),
                'address_attributes': {'zip': '4546467575'}, 'approve_status': 'approved',
            }
            customer = {
                'custom_field_template_id': 1172, 'name': PREFIX + suffix + '客户',
                'company_name': PREFIX + '测试企业', 'source': 391979,
                'numeric_asset_c12fb7': 12.34, 'numeric_asset_b6049b': 13,
                'numeric_asset_26d18d': 123, 'user_id': 1000025901,
                'owned_department_id': 5506212, 'approve_status': 'approved',
                'address_attributes': {}, 'assist_user_ids': [],
                'labels': picked(preview['labels']), 'contacts_attributes': [contact],
            }
            created = api('POST', '/v2/customers?request_ticket=' + str(uuid.uuid4()),
                          {'customer': customer, 'refer_lead_id': source_id})
            customer_id = created['id']
            for surface in ('v2', 'pc'):
                detail = api('GET', f'/{surface}/customers/{customer_id}')
                assert ids(detail['labels']) == ids(expected), (surface, detail['labels'])
            contacts = api('GET', f'/v2/customers/{customer_id}').get('contacts', [])
            assert contacts, 'Customer response did not expose newly created contact'
            for row in contacts:
                contact_id = row['id']
                owned.append({'path': '/v2/contacts/' + str(contact_id)}); save()
                detail = api('GET', f'/v2/contacts/{contact_id}')
                # v2 contact detail currently omits labels; verify persistence via PC.
                pc_contact = api('GET', f'/pc/contacts/{contact_id}')
                assert ids(pc_contact['labels']) == ids(expected), pc_contact['labels']
            converted = api('GET', f'/v2/leads/{source_id}')
            assert converted['turned_to_customer'] and converted['turned_customer_id'] == customer_id
            assert ids(converted['labels']) == ids(source_labels)
            mappings.append({'case': suffix, 'lead_id': source_id, 'customer_id': customer_id,
                             'source_labels': ids(source_labels), 'expected': ids(expected),
                             'contacts': [x['id'] for x in contacts],
                             'mobile_contact_labels_exposed': 'labels' in detail.get('contact', {})}); save()

        case('conversion_shared_multi_radio_filter_private', lambda: convert([m1, m2, r1, private], [m1, m2, r1], '共用'))
        case('conversion_no_shared_group', lambda: convert([private], [], '专属'))
        case('conversion_empty_source', lambda: convert([], [], '空值'))
    except Exception:
        cases.append({'case': 'setup', 'status': 'FAIL', 'error': traceback.format_exc()}); save()
        print(cases[-1]['error'], flush=True)
    finally:
        errors = []
        # Contacts before customers; then leads, labels and groups.
        for resource in ('/v2/contacts/', '/v2/customers/', '/v2/leads/', '/pc/labels/', '/pc/label_groups/'):
            for item in owned.copy():
                if not item['path'].startswith(resource):
                    continue
                try:
                    cleanup_path = item['path'].replace('/v2/', '/pc/')
                    api('DELETE', cleanup_path)
                    if resource.startswith('/v2/'):
                        r = session.get(BASE + cleanup_path, timeout=30)
                        p = r.json()
                        records.append({'method': 'GET', 'path': cleanup_path, 'http_status': r.status_code, 'response': p})
                        assert p.get('code') in (100100, 100114), p.get('code')
                    owned.remove(item); save()
                except Exception as e:
                    errors.append({'path': item['path'], 'error': str(e)})
        cases.append({'case': 'cleanup', 'status': 'PASS' if not owned and not errors else 'FAIL', 'errors': errors})
        save()
    print('Evidence:', OUT, flush=True)
    return 0 if all(x['status'] == 'PASS' for x in cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
