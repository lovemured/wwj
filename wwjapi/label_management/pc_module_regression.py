#!/usr/bin/env python3
"""PC label regression for the other nine modules, using only owned fixtures."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import traceback
import uuid
from urllib.parse import urlencode

import pc_api_regression as core

MODELS = {
    'Customer': ('customers', 'customer', 'name'),
    'MarketActivity': ('market_activities', 'market_activity', 'name'),
    'Contact': ('contacts', 'contact', 'name'),
    'Opportunity': ('opportunities', 'opportunity', 'title'),
    'Quotation': ('quotations', 'quotation', 'name'),
    'Contract': ('contracts', 'contract', 'title'),
    'ReceivedPayment': ('received_payments', 'received_payment', 'sn'),
    'InvoicedPayment': ('invoiced_payments', 'invoiced_payment', 'sn'),
    'Product': ('products', 'product', 'name'),
}
PRE = Path(__file__).resolve().parent / 'data/all_modules_20261112'


class Run:
    def __init__(self):
        self.entities = []
        self.results = []
        self.metadata = {}
        self.primary = {}
        self.parents = {}
        self.fixture = core.PCLeadTests()
        self.counter = 0
        self.baseline = core.groups()
        self.save()

    def save(self):
        core.OUT.mkdir(parents=True, exist_ok=True)
        (core.OUT / 'modules-summary.json').write_text(json.dumps({
            'prefix': core.PREFIX, 'results': self.results, 'entities': self.entities,
            'parents': self.parents, 'metadata': self.metadata,
            'remaining_group_ids': sorted(core.OWN_GROUPS),
            'remaining_label_ids': sorted(core.OWN_LABELS),
        }, ensure_ascii=False, indent=2), encoding='utf-8')

    def case(self, model, name, fn):
        start = len(core.EVIDENCE)
        result = {'model': model, 'case': name, 'status': 'PASS', 'evidence_start': start}
        try:
            fn()
        except Exception:
            result.update(status='FAIL', error=traceback.format_exc())
        result['evidence_end'] = len(core.EVIDENCE)
        self.results.append(result)
        self.save()
        print(model, name, result['status'], result.get('error', '')[-500:], flush=True)

    def prepare(self):
        assert sum(len(g['labels']) for g in self.baseline) + 6 <= core.success(core.api('GET', '/label_groups'))['max_label_count']
        self.multi = self.fixture.group(applicable_models=list(MODELS))
        self.radio = self.fixture.group(name=core.PREFIX + 'R', select_type='radio', applicable_models=list(MODELS))
        self.private = self.fixture.group(name=core.PREFIX + 'L', applicable_models=['Lead'])
        self.m1, self.m2, self.kept = [self.fixture.label(self.multi['id'], core.PREFIX + '多' + str(i)) for i in range(3)]
        self.r1, self.r2 = [self.fixture.label(self.radio['id'], core.PREFIX + '单' + str(i)) for i in range(2)]
        self.excluded = self.fixture.label(self.private['id'], core.PREFIX + '线索专属')
        self.save()
        for model, (path, wrapper, _) in MODELS.items():
            query = {}
            templates = PRE / (model + '-templates.json')
            if templates.exists():
                enabled = [x for x in json.loads(templates.read_text())['data']['list'] if x['status'] == 'enable']
                query['custom_field_template_id'] = enabled[0]['id']
            fields = core.success(core.api('GET', '/custom_fields?' + urlencode({'model_klass': model, **query})))
            flattened = [f for g in fields['custom_field_groups'] for f in g['custom_fields']]
            self.metadata[model] = {'template': query.get('custom_field_template_id'),
                                    'field_id': next(f['field_id'] for f in flattened if f['name'] == 'labels'),
                                    'fields': flattened}
        self.parents['customer'] = self.create('Customer', [], '关联客户')
        self.parents['contract'] = self.create('Contract', [], '关联合同')
        self.save()

    def defaults(self, model):
        path, _, _ = MODELS[model]
        query = {'custom_field_template_id': self.metadata[model]['template']} if self.metadata[model]['template'] else {}
        if model == 'InvoicedPayment':
            query['contract_id'] = self.parents['contract']['id']
        return core.success(core.api('GET', '/' + path + '/new?' + urlencode(query)))

    def data(self, model, labels, suffix):
        defaults = self.defaults(model)
        self.counter += 1
        name = core.PREFIX + suffix + str(self.counter)
        body = {k: copy.deepcopy(v) for k, v in defaults.items()
                if re.match(r'^(numeric|text|text_area|datetime)_asset_', k) and v not in (None, '', [])}
        body.update({MODELS[model][2]: name, 'user_id': 1000025901, 'want_department_id': 5506212,
                     'labels': [self.chosen(x) for x in labels]})
        if self.metadata[model]['template']:
            body['custom_field_template_id'] = self.metadata[model]['template']
        today = core.datetime.now().strftime('%Y-%m-%d')
        if model == 'Customer':
            body.update(company_name=name, source=391979, numeric_asset_c12fb7=12.34,
                        numeric_asset_b6049b='10', numeric_asset_26d18d='123', contacts_attributes=[],
                        assist_user_ids=[], address_attributes={})
        if model in ('Contact', 'Opportunity', 'Quotation', 'Contract', 'ReceivedPayment', 'InvoicedPayment'):
            body['customer_id'] = self.parents['customer']['id']
        if model == 'MarketActivity':
            body.update(start_date=today, end_date=today, estimated_cost=100, actual_cost=100,
                        estimated_income=100, actual_income=100)
        if model == 'Opportunity':
            body.update(stage=392023, expect_sign_date=today, expect_amount=100,
                        product_assets_attributes=[], contact_assetships_attributes=[])
        if model == 'Quotation':
            body.update(title=name, quotation_date=today, total_amount=100, whole_discount=1,
                        product_assets_attributes=[], contact_assetships_attributes=[])
        if model == 'Contract':
            body.update(sn=name, sign_date=today, total_amount=100000, numeric_asset_4999ae=0,
                        product_assets_attributes=[], received_payment_plans_attributes=[],
                        contact_assetships_attributes=[])
        if model in ('ReceivedPayment', 'InvoicedPayment'):
            body.update(amount=25, contract_id=self.parents['contract']['id'])
        if model == 'ReceivedPayment':
            body.update(receive_date=today, receive_user_id=1000025901)
        if model == 'InvoicedPayment':
            body.update(invoiced_date=today, broker_user_id=1000025901, invoice_types=392049)
        if model == 'Product':
            body.update(product_no=name, spec='测试规格', standard_unit_price=10, unit_cost=5, sale_unit='个')
        return body

    def chosen(self, label):
        group = self.radio if label['label_group_id'] == self.radio['id'] else self.private if label['label_group_id'] == self.private['id'] else self.multi
        return self.fixture.chosen(group, label)

    def create(self, model, labels, suffix='测试'):
        path, wrapper, identity = MODELS[model]
        data = self.data(model, labels, suffix)
        body = {wrapper: data, 'request_ticket': str(uuid.uuid4())}
        if model == 'InvoicedPayment':
            body['contract_id'] = data['contract_id']
        actual = core.success(core.api('POST', '/' + path, body))
        entity = {'model': model, 'id': actual['id'], 'name': data[identity], 'deleted': False}
        self.entities.append(entity)
        self.save()
        return entity

    def detail(self, entity):
        return core.success(core.api('GET', '/' + MODELS[entity['model']][0] + '/' + str(entity['id'])))

    def check(self, entity, labels):
        actual = sorted(x['id'] for x in self.detail(entity)['labels'])
        assert actual == sorted(x['id'] for x in labels), (entity, actual, [x['id'] for x in labels])

    def update(self, entity, values):
        path, wrapper, _ = MODELS[entity['model']]
        body = {wrapper: values, 'request_ticket': str(uuid.uuid4())}
        if entity['model'] == 'Contact':
            return core.api('POST', f'/{path}/{entity["id"]}/new_update', body)
        return core.api('PUT', f'/{path}/{entity["id"]}', body)

    def set(self, entity, labels):
        core.success(self.update(entity, {'labels': [self.chosen(x) for x in labels]}))
        self.check(entity, labels)

    def reset(self, entity, labels):
        self.set(entity, labels)

    def batch(self, model, entities, labels, operation):
        return core.api('PUT', '/batch_resources/batch_update', {
            'name': 'labels', 'field_id': self.metadata[model]['field_id'], 'field_name': 'labels',
            'field_label': '标签', 'field_value': [{'id': x['id'], 'group_id': x['label_group_id']} for x in labels],
            'operation_selection': operation, 'resource_ids': [x['id'] for x in entities], 'resource_type': model})

    def records(self, model):
        a = self.create(model, [self.m1, self.m2, self.r1], '全标')
        b = self.create(model, [self.m1, self.r2], '部分')
        empty = self.create(model, [], '空标')
        untouched = self.create(model, [self.m1, self.m2, self.r1], '未选')
        self.primary[model] = a
        def creation():
            for entity, expected in ((a, [self.m1, self.m2, self.r1]), (b, [self.m1, self.r2]),
                                     (empty, []), (untouched, [self.m1, self.m2, self.r1])):
                self.check(entity, expected)
        self.case(model, 'create_multi_radio_empty_readback', creation)
        def edit():
            self.set(a, [self.m1, self.r2])
            path, wrapper, _ = MODELS[model]
            key = 'introduction' if model == 'Product' else 'description' if model == 'MarketActivity' else 'note'
            core.success(self.update(a, {key: core.PREFIX + '保留标签'}))
            self.check(a, [self.m1, self.r2])
            self.set(a, [])
        self.case(model, 'edit_preserve_omitted_and_clear', edit)
        def radio():
            path, wrapper, _ = MODELS[model]
            result = self.update(a, {'labels': [self.chosen(x) for x in (self.m1, self.r1, self.r2)]})
            if result[1].get('code') == 0:
                ids = [x['id'] for x in self.detail(a)['labels']]
                assert self.m1['id'] in ids and len(set(ids) & {self.r1['id'], self.r2['id']}) == 1, ids
            else:
                core.rejected(result)
        self.case(model, 'single_group_never_saves_two_values', radio)
        if model in ('MarketActivity', 'ReceivedPayment', 'InvoicedPayment'):
            self.results.append({'model': model, 'case': 'batch_edit', 'status': 'OUT_OF_SCOPE',
                                 'reason': '用户确认此模块 PC 不支持批量编辑'})
            self.save()
            return
        def append():
            self.reset(a, [self.m1, self.r1]); self.reset(b, [self.m1]); self.reset(empty, [])
            for _ in range(2):
                core.success(self.batch(model, [a, b, empty], [self.m2], 'append'))
                self.check(a, [self.m1, self.m2, self.r1]); self.check(b, [self.m1, self.m2]); self.check(empty, [self.m2])
                self.check(untouched, [self.m1, self.m2, self.r1])
        self.case(model, 'batch_append_multi_repeated_scope', append)
        def append_radio():
            self.reset(a, [self.m1, self.r1])
            core.success(self.batch(model, [a], [self.r2], 'append'))
            self.check(a, [self.m1, self.r2])
        self.case(model, 'batch_append_radio_replaces_same_group', append_radio)
        def replace():
            self.reset(a, [self.m1, self.r1]); self.reset(empty, [])
            for _ in range(2):
                core.success(self.batch(model, [a, empty], [self.m2, self.r2], 'replace'))
                for entity in (a, empty): self.check(entity, [self.m2, self.r2])
                self.check(untouched, [self.m1, self.m2, self.r1])
        self.case(model, 'batch_replace_all_groups_repeated_scope', replace)
        def remove_any():
            self.reset(a, [self.m1, self.m2, self.kept, self.r1]); self.reset(b, [self.m1, self.r2]); self.reset(empty, [])
            for _ in range(2):
                core.success(self.batch(model, [a, b, empty], [self.m1, self.m2], 'remove_one_match'))
                self.check(a, [self.kept, self.r1]); self.check(b, [self.r2]); self.check(empty, [])
                self.check(untouched, [self.m1, self.m2, self.r1])
        self.case(model, 'batch_remove_any_partial_and_repeated', remove_any)
        def remove_full():
            self.reset(a, [self.m1, self.m2, self.kept, self.r1]); self.reset(b, [self.m1, self.r2]); self.reset(empty, [])
            for _ in range(2):
                core.success(self.batch(model, [a, b, empty], [self.m1, self.r1], 'remove_full_match'))
                self.check(a, [self.m2, self.kept]); self.check(b, [self.m1, self.r2]); self.check(empty, [])
                self.check(untouched, [self.m1, self.m2, self.r1])
        self.case(model, 'batch_remove_full_cross_groups_partial_repeated', remove_full)
        def wrong_module():
            for operation in ('append', 'remove_one_match', 'remove_full_match'):
                self.reset(a, [self.m1])
                result = self.batch(model, [a], [self.excluded], operation)
                if result[1].get('code') == 0: core.success(result)
                else: core.rejected(result)
                self.check(a, [self.m1])
            self.reset(a, [self.m1])
            result = self.batch(model, [a], [self.m2, self.excluded], 'replace')
            if result[1].get('code') == 0:
                core.success(result); self.check(a, [self.m2])
            else:
                core.rejected(result); self.check(a, [self.m1])
        self.case(model, 'wrong_module_four_batch_modes_protect_data', wrong_module)

    def cleanup(self):
        errors = []
        for entity in reversed(self.entities):
            if entity['deleted']: continue
            path = '/' + MODELS[entity['model']][0] + '/' + str(entity['id'])
            try:
                core.success(core.api('DELETE', path))
                status, payload = core.api('GET', path)
                assert status == 200 and payload.get('code') in (100100, 100114), (status, payload)
                entity['deleted'] = True
            except Exception:
                errors.append({'entity': entity, 'error': traceback.format_exc()})
            self.save()
        if not errors:
            core.cleanup(set(core.OWN_GROUPS), set(core.OWN_LABELS))
        self.results.append({'model': 'cleanup', 'case': 'only_owned_entities_and_labels',
                             'status': 'FAIL' if errors else 'PASS', 'errors': errors})
        self.results.append({'model': 'compatibility', 'case': 'preexisting_label_configuration_unchanged',
                             'status': 'PASS' if core.groups() == self.baseline else 'FAIL'})
        self.save()


if __name__ == '__main__':
    token = os.environ['CRM_LABEL_TOKEN']
    core.SESSION.headers.update({'Authorization': f'Token token="{token}",device="web"', 'Accept': 'application/json'})
    run = Run()
    try:
        run.prepare()
        for model in (sys.argv[1:] or MODELS):
            try:
                run.records(model)
            except Exception:
                run.results.append({'model': model, 'case': 'fixture_setup', 'status': 'BLOCKED', 'error': traceback.format_exc()})
                run.save()
                print(model, 'BLOCKED', run.results[-1]['error'][-700:], flush=True)
    except Exception:
        run.results.append({'model': 'setup', 'case': 'prerequisites', 'status': 'BLOCKED', 'error': traceback.format_exc()})
        print(run.results[-1]['error'], flush=True)
    finally:
        run.cleanup()
        print('Evidence:', core.OUT, flush=True)
    raise SystemExit(0 if all(x['status'] == 'PASS' for x in run.results) else 1)
