#!/usr/bin/env python3
"""Mobile label integration checks for the nine remaining CRM modules.

Uses only the authorized test environment and owned synthetic records.
CRM_LABEL_TOKEN is read from the environment. No import or batch editing.
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
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pc_api_regression as core
from pc_module_regression import Run, MODELS


TEMPLATES = {'Customer': 1172, 'MarketActivity': 1444, 'Opportunity': 1840,
             'Quotation': 1968, 'Contract': 2382}
MAPPING_PATHS = [('Customer', 'Contact', 'customer_id'),
                 ('Customer', 'Opportunity', 'customer_id'),
                 ('Customer', 'Quotation', 'customer_id'),
                 ('Customer', 'Contract', 'customer_id'),
                 ('Opportunity', 'Quotation', 'opportunity_id'),
                 ('Contract', 'ReceivedPayment', 'contract_id'),
                 ('Contract', 'InvoicedPayment', 'contract_id'),
                 ('Opportunity', 'Contract', 'opportunity_id')]
PC_BASE = core.BASE
MOBILE_BASE = PC_BASE.removesuffix('/pc') if hasattr(str, 'removesuffix') else PC_BASE[:-3]
_original_api = core.api
_last_request = 0


def paced_api(method, path, body=None):
    global _last_request
    time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
    _last_request = time.monotonic()
    start = len(core.EVIDENCE)
    try:
        return _original_api(method, path, body)
    finally:
        for record in core.EVIDENCE[start:]:
            record['api_base'] = core.BASE
        core.save()


def mobile(method, path, body=None, version='v2'):
    core.BASE = MOBILE_BASE + '/' + version
    try:
        return core.api(method, path, body)
    finally:
        core.BASE = PC_BASE


def label_ids(values):
    return sorted(x['id'] for x in values)


class MobileRun(Run):
    def __init__(self):
        self.bodies = {}
        self.gaps = {}
        self.list_paths = {}
        self.default_cache = {}
        self.mapping_details = []
        super().__init__()

    def save(self):
        super().save()
        (core.OUT / 'mobile-coverage.json').write_text(json.dumps({
            'gaps': self.gaps, 'list_endpoints': self.list_paths,
            'mappings': self.mapping_details,
        }, ensure_ascii=False, indent=2))

    def prepare(self):
        limits = core.success(core.api('GET', '/label_groups'))
        assert len(self.baseline) + 3 <= limits['max_group_count']
        assert sum(len(g['labels']) for g in self.baseline) + 6 <= limits['max_label_count']
        self.multi = self.fixture.group(applicable_models=list(MODELS))
        self.radio = self.fixture.group(name=core.PREFIX + 'R', select_type='radio', applicable_models=list(MODELS))
        self.private = self.fixture.group(name=core.PREFIX + 'L', applicable_models=['Lead'])
        self.m1, self.m2, self.kept = [self.fixture.label(self.multi['id'], core.PREFIX + '多' + str(i)) for i in range(3)]
        self.r1, self.r2 = [self.fixture.label(self.radio['id'], core.PREFIX + '单' + str(i)) for i in range(2)]
        self.excluded = self.fixture.label(self.private['id'], core.PREFIX + '线索专属')
        self.metadata = {model: {'template': TEMPLATES.get(model)} for model in MODELS}
        self.parents['customer'] = self.create('Customer', [], '关联客户')
        self.parents['contract'] = self.create('Contract', [], '关联合同')
        self.parents['opportunity'] = self.create('Opportunity', [], '关联商机')

    def defaults(self, model):
        if model not in self.default_cache:
            path = MODELS[model][0]
            query = {'custom_field_template_id': TEMPLATES[model]} if model in TEMPLATES else {}
            # PC defaults supply tenant-specific required fields only; operations are mobile.
            if model == 'InvoicedPayment':
                query['contract_id'] = self.parents['contract']['id']
            self.default_cache[model] = core.success(core.api('GET', '/' + path + '/new?' + urlencode(query)))
        return copy.deepcopy(self.default_cache[model])

    def data(self, model, labels, suffix):
        body = super().data(model, labels, suffix)
        body['owned_department_id'] = body.pop('want_department_id')
        body['labels'] = [{'id': x['id']} for x in labels]
        body['approve_status'] = 'approved'
        if model in ('ReceivedPayment', 'InvoicedPayment'):
            body['contract'] = body['contract_id']
        return body

    def create(self, model, labels, suffix='移动标签', extra=None, root_extra=None):
        path, wrapper, identity = MODELS[model]
        body = self.data(model, labels, suffix)
        body.update(extra or {})
        route = '/' + path
        if model in ('ReceivedPayment', 'InvoicedPayment'):
            route = f'/contracts/{body["contract_id"]}/{path}'
        request = {wrapper: body, **(root_extra or {})}
        actual = core.success(mobile('POST', route + '?request_ticket=' + str(uuid.uuid4()), request))
        identifier = actual.get('id') or actual.get(wrapper, {}).get('id')
        assert identifier, (model, actual)
        entity = {'model': model, 'id': identifier, 'name': body[identity], 'deleted': False}
        self.entities.append(entity)
        self.bodies[(model, identifier)] = body
        self.save()
        return entity

    def detail(self, entity):
        return core.success(core.api('GET', '/' + MODELS[entity['model']][0] + '/' + str(entity['id'])))

    def mobile_route(self, entity):
        path = MODELS[entity['model']][0]
        if entity['model'] in ('ReceivedPayment', 'InvoicedPayment'):
            contract_id = self.bodies[(entity['model'], entity['id'])]['contract_id']
            return f'/contracts/{contract_id}/{path}/{entity["id"]}'
        return '/' + path + '/' + str(entity['id'])

    def check(self, entity, labels, include_list=True):
        expected = label_ids(labels)
        path, wrapper, _ = MODELS[entity['model']]
        pc = self.detail(entity)
        assert label_ids(pc['labels']) == expected, ('PC persistence', entity, expected, pc['labels'])
        actual = core.success(mobile('GET', self.mobile_route(entity)))
        actual = actual.get(wrapper, actual)
        if 'labels' in actual:
            assert label_ids(actual['labels']) == expected, ('mobile detail', entity, expected, actual['labels'])
        else:
            self.gaps[entity['model'] + '_detail'] = 'Mobile v2 detail omits labels; persistence verified with PC detail.'
        if include_list:
            self.check_list(entity, labels)
        self.save()

    def check_list(self, entity, labels):
        model = entity['model']; path = MODELS[model][0]
        if model == 'ReceivedPayment':
            result = mobile('GET', '/received_payment_center/received_payments?page=1&per_page=15&sort=updated_at&scope=received_payment&order=desc')
            self.list_paths[model] = 'v2/received_payment_center/received_payments?scope=received_payment'
        elif model == 'InvoicedPayment':
            result = mobile('GET', '/received_payment_center/invoiced_payments?page=1&per_page=15&sort=updated_at&scope=invoiced_payment&order=desc')
            self.list_paths[model] = 'v2/received_payment_center/invoiced_payments?scope=invoiced_payment'
        elif model not in self.list_paths:
            for version in ('v3', 'v2'):
                result = mobile('GET', '/' + path + '?page=1&per_page=15&sort=updated_at&order=desc', version=version)
                if result[0] == 200 and result[1].get('code') == 0:
                    self.list_paths[model] = version
                    break
            else:
                self.gaps[model + '_list'] = 'List endpoint needs actual APP request.'
                self.list_paths[model] = None
                return
        else:
            if not self.list_paths[model]: return
            result = mobile('GET', '/' + path + '?page=1&per_page=15&sort=updated_at&order=desc', version=self.list_paths[model])
        listing = core.success(result)
        rows = listing.get('list', listing.get(path, [])) if isinstance(listing, dict) else listing
        row = next((x for x in rows if x.get('id') == entity['id']), None)
        assert row is not None, ('Owned record missing from latest list', model, entity['id'])
        key = 'labels_mapped' if 'labels_mapped' in row else 'labels' if 'labels' in row else None
        if key:
            assert label_ids(row[key]) == label_ids(labels), ('list', entity, labels, row[key])
        else:
            self.gaps[model + '_list_labels'] = 'Current list response omits label field; APP rendering needs confirmation.'

    def update(self, entity, values):
        model = entity['model']; path, wrapper, _ = MODELS[model]
        body = copy.deepcopy(self.bodies[(model, entity['id'])])
        body.pop('labels', None)
        body.update(values, id=entity['id'])
        if 'labels' in body: body['labels'] = [{'id': x['id']} for x in body['labels']]
        return mobile('PUT', self.mobile_route(entity), {wrapper: body})

    def set(self, entity, labels):
        core.success(self.update(entity, {'labels': labels}))
        self.check(entity, labels)

    def records(self, model):
        entity = self.create(model, [self.m1, self.m2, self.r1])
        self.primary[model] = entity
        self.case(model, 'create_multi_radio_readback', lambda: self.check(entity, [self.m1, self.m2, self.r1]))
        if '--list-only' in sys.argv:
            self.case(model, 'clear_labels_list_readback', lambda: self.set(entity, []))
            return
        self.case(model, 'edit_replace_multi_and_switch_radio', lambda: self.set(entity, [self.m2, self.r2]))
        def omitted():
            key = 'introduction' if model == 'Product' else 'description' if model == 'MarketActivity' else 'note'
            core.success(self.update(entity, {key: core.PREFIX + '省略标签'}))
            self.check(entity, [self.m2, self.r2])
        self.case(model, 'edit_omitted_labels_preserved', omitted)
        self.case(model, 'edit_duplicate_ids_deduplicated', lambda: (
            core.success(self.update(entity, {'labels': [self.m1, self.m1, self.r1]})),
            self.check(entity, [self.m1, self.r1])))
        self.case(model, 'edit_clear_labels', lambda: self.set(entity, []))
        def conflict():
            result = self.update(entity, {'labels': [self.m1, self.r1, self.r2]})
            if result[1].get('code') == 0:
                actual = self.detail(entity)['labels']
                assert self.m1['id'] in label_ids(actual)
                assert len(set(label_ids(actual)) & {self.r1['id'], self.r2['id']}) == 1, actual
                self.check(entity, actual)
            else:
                core.rejected(result); self.check(entity, [])
        self.case(model, 'radio_conflict_never_persists_two', conflict)
        def foreign():
            self.set(entity, [self.m1])
            result = self.update(entity, {'labels': [self.m2, self.excluded]})
            if result[1].get('code') == 0:
                self.check(entity, [self.m2])
            else:
                core.rejected(result); self.check(entity, [self.m1])
        self.case(model, 'wrong_module_label_filtered_or_rejected', foreign)

    def options(self):
        snapshot = core.groups()
        for model, wrapper in [('Lead', 'lead')] + [(m, v[1]) for m, v in MODELS.items()]:
            def check_options(model=model, wrapper=wrapper):
                actual = core.success(mobile('GET', '/labels?' + urlencode({'model_klass': wrapper})))['label_groups']
                expected = {g['id']: g for g in snapshot if model in g['applicable_models']}
                assert {g['group_id'] for g in actual} == set(expected), (model, actual, list(expected))
                for group in actual:
                    saved = expected[group['group_id']]
                    assert group['group_name'] == saved['name']
                    assert group['select_type'] == saved['select_type']
                    assert group['color'].lower() == saved['color'].lower()
                    assert sorted((x['id'], x['content']) for x in group['labels']) == sorted((x['id'], x['content']) for x in saved['labels'])
            self.case(model, 'mobile_options_exact_module_filter', check_options)

    def mappings(self):
        for source_model, target, relation in MAPPING_PATHS:
            source = self.parents[source_model.lower()]
            # Clear all synthetic parent values to isolate the intended source.
            for parent in self.parents.values():
                core.success(self.update(parent, {'labels': []}))
            shared = [self.m1, self.m2, self.r1]
            # The private group is source-only and never applies to the target.
            core.success(core.api('PUT', '/label_groups/' + str(self.private['id']),
                                  {'label_group': {'applicable_models': [source_model]}}))
            for suffix, selected, expected in [('shared_filter_private', shared + [self.excluded], shared),
                                                ('no_shared_labels', [self.excluded], []),
                                                ('empty_source', [], [])]:
                def check_mapping(selected=selected, expected=expected, suffix=suffix):
                    self.set(source, selected)
                    path = '/' + MODELS[target][0] + '/new'
                    query = {relation: source['id']}
                    if target in TEMPLATES: query['custom_field_template_id'] = TEMPLATES[target]
                    if target == 'ReceivedPayment':
                        path = f'/contracts/{source["id"]}/received_payments/new'
                    preview = core.success(mobile('GET', path + '?' + urlencode(query)))
                    assert 'labels' in preview, ('Prefill omits labels; confirm actual APP endpoint', path)
                    assert label_ids(preview['labels']) == label_ids(expected), (path, expected, preview['labels'])
                    extra = {relation: source['id'], 'labels': [{'id': x['id']} for x in preview['labels']]}
                    root = {'turn_to_contract': True, 'source_name': 'opportunity'} if source_model == 'Opportunity' and target == 'Contract' else {}
                    entity = self.create(target, expected, '映射', extra=extra, root_extra=root)
                    self.check(entity, expected)
                    self.check(source, selected, include_list=False)
                    self.mapping_details.append({'source': source_model, 'target': target, 'case': suffix,
                        'prefill_path': path + '?' + urlencode(query), 'source_id': source['id'],
                        'target_id': entity['id'], 'expected_label_ids': label_ids(expected)})
                    # Remove target labels before changing the private group's applicability.
                    core.success(self.update(entity, {'labels': []}))
                    self.save()
                self.case(target, source_model + '_to_' + target + '_' + suffix, check_mapping)
            core.success(self.update(source, {'labels': []}))


if __name__ == '__main__':
    core.OUT = Path(__file__).resolve().parent / 'results' / datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S-mobile-modules')
    core.PREFIX = 'M' + uuid.uuid4().hex[:6]
    core.api = paced_api
    core.SESSION.headers.update({
        'Authorization': f'Token token="{os.environ["CRM_LABEL_TOKEN"]}",device="lxcrm_duli",version_code="4.0.1"',
        'Accept': '*/*', 'Content-Type': 'application/json; chartset=utf-8',
        'Origin': 'https://crmh5-test.weiwenjia.com', 'X-Requested-With': 'com.lixiaoyun.aike',
        'X-Lx-Gid': 'wwjg8aoKBzsWlkMGCHYG',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 16; SM-S9280 Build/BP4A.251205.006; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/156.0.8078.47 Mobile Safari/537.36',
    })
    run = MobileRun()
    try:
        run.prepare()
        if '--options' in sys.argv:
            run.options()
        for model in (sys.argv[1:] or MODELS):
            if model.startswith('--'): continue
            try:
                run.records(model)
            except Exception:
                run.results.append({'model': model, 'case': 'fixture_setup', 'status': 'BLOCKED', 'error': traceback.format_exc()})
                run.save(); print(model, 'BLOCKED', run.results[-1]['error'][-600:], flush=True)
        if '--mappings' in sys.argv or len(sys.argv) == 1:
            run.mappings()
    except Exception:
        run.results.append({'model': 'setup', 'case': 'prerequisites', 'status': 'BLOCKED', 'error': traceback.format_exc()})
        run.save(); print(run.results[-1]['error'], flush=True)
    finally:
        run.cleanup()
        print('Evidence:', core.OUT, flush=True)
    raise SystemExit(0 if all(x['status'] == 'PASS' for x in run.results) else 1)
