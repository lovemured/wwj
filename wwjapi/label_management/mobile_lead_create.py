#!/usr/bin/env python3
"""Mobile lead label creation checks against the authorized test tenant only.

Run with CRM_LABEL_TOKEN in the environment. Creates and deletes owned leads.
"""
import copy
import json
import os
from pathlib import Path
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


BASE = 'https://lxcrm-api-test.weiwenjia.com/api'
NOW = datetime.now(ZoneInfo('Asia/Shanghai'))
OUT = Path(__file__).resolve().parent / 'results' / NOW.strftime('%Y%m%d-%H%M%S-mobile-lead')
PREFIX = 'APP标签' + uuid.uuid4().hex[:8]
LABELS = [2200267, 2200104, 2200265, 2200273]


def main():
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Token token="{os.environ["CRM_LABEL_TOKEN"]}",device="lxcrm_duli",version_code="4.0.1"',
        'Accept': '*/*', 'Content-Type': 'application/json; chartset=utf-8',
        'Origin': 'https://crmh5-test.weiwenjia.com',
        'X-Requested-With': 'com.lixiaoyun.aike',
    })
    evidence, cases, owned = [], [], []
    OUT.mkdir(parents=True)

    def save():
        (OUT / 'evidence.json').write_text(json.dumps({
            'prefix': PREFIX, 'requests': evidence, 'cases': cases,
            'remaining_lead_ids': owned,
        }, ensure_ascii=False, indent=2))

    def api(method, path, body=None):
        r = session.request(method, BASE + path, json=body, timeout=30)
        p = r.json()
        evidence.append({'method': method, 'path': path, 'request': body,
                         'http_status': r.status_code, 'response': p})
        if method == 'POST' and path.startswith('/v2/leads?') and p.get('code') == 0:
            owned.append(p['data']['id'])
        save()
        return r.status_code, p

    def success(result):
        status, p = result
        assert status == 200 and p.get('code') == 0, (status, p.get('code'), p.get('message'))
        return p.get('data')

    lead = {
        'text_asset_a063a3': 'false', 'source': 392064, 'status': 617883,
        'address_attributes': {'detail_address': '', 'lat': '', 'lng': ''},
        'inquiry_attributes': {'employee_account': ''}, 'channel': None,
        'text_area_asset_df70dd': '20', 'numeric_asset_922345': 2,
        'datetime_asset_f4fc01': NOW.strftime('%Y-%m-%d'),
        'text_asset_292a34': None, 'text_asset_215879': None,
        'numeric_asset_aa4b85': 1, 'numeric_asset_39fe31': 1.55,
        'numeric_asset_714d0e': -0.0083, 'numeric_asset_97dc97': 0,
        'user_id': 1000025901, 'owned_department_id': 5506212, 'approve_status': 'approved',
    }
    for key in ('subform_asset_26051c', 'product_assets_attributes', 'product_assets',
                'text_asset_b8bc01', 'user_field_asset_148036', 'user_field_asset_9d2ba3',
                'user_field_asset_752552', 'user_field_asset_6e1f7d', 'text_asset_8571b3',
                'text_asset_6badcf', 'subform_asset_796a9a', 'subform_asset_826506',
                'subform_asset_372340', 'subform_asset_837fd1'):
        lead[key] = []
    for key in ('numeric_asset_585717', 'numeric_asset_c017c6', 'numeric_asset_d85589',
                'text_asset_292a34_other', 'text_asset_215879_other'):
        lead[key] = ''
    for key in ('file_asset_de3667', 'file_asset_5a3171', 'file_asset_916766'):
        lead[key] = {'attachment_ids': []}
    try:
        groups = success(api('GET', '/pc/label_groups'))['list']
        legal = {x['id'] for g in groups if 'Lead' in g['applicable_models'] for x in g['labels']}
        assert set(LABELS) <= legal, 'Provided labels no longer applicable to Lead'
        for name, labels in [('four_multi_labels', LABELS), ('empty_labels', []),
                             ('duplicate_label_ids', LABELS + [LABELS[0]])]:
            try:
                body = copy.deepcopy(lead)
                body.update(name=PREFIX + name, labels=[{'id': x} for x in labels])
                result = success(api('POST', '/v2/leads?request_ticket=' + str(uuid.uuid4()), {'lead': body}))
                identifier = result['id']
                observed = {}
                for surface in ('v2', 'pc'):
                    detail = success(api('GET', f'/{surface}/leads/{identifier}'))
                    actual = [x['id'] for x in detail.get('labels', [])]
                    observed[surface] = actual
                    assert sorted(actual) == sorted(set(labels)), (surface, labels, actual)
                cases.append({'case': name, 'status': 'PASS', 'lead_id': identifier,
                              'expected_label_ids': sorted(set(labels)), 'actual': observed})
            except Exception as e:
                cases.append({'case': name, 'status': 'FAIL', 'error': str(e)})
            save()
    finally:
        for identifier in owned.copy():
            success(api('DELETE', f'/v2/leads/{identifier}'))
            status, p = api('GET', f'/v2/leads/{identifier}')
            assert p.get('code') in (100100, 100114), (status, p.get('code'))
            owned.remove(identifier)
            save()
    print(json.dumps({'out': str(OUT), 'cases': cases, 'remaining_lead_ids': owned}, ensure_ascii=False))
    return 0 if len(cases) == 3 and all(x['status'] == 'PASS' for x in cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
