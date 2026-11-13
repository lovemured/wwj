#!/usr/bin/env python3
"""Owned fixtures for PC and mobile label filters; token stays in the environment."""
from environment import settings
import copy
import json
import os
from pathlib import Path
import sys
import time
import traceback
from urllib.parse import urlencode

import pc_api_regression as core
from pc_module_regression import Run, MODELS
from mobile_module_regression import TEMPLATES

MODELS['Lead'] = ('leads', 'lead', 'name')
ROOT = settings.api_root
OUT = settings.result_root / '20261113-label-filter'
MOBILE_VERSION = dict.fromkeys(MODELS, 'v3')
MOBILE_VERSION.update(Quotation='v2', Product='v2', ReceivedPayment='v2', InvoicedPayment='v2')
core.OUT = OUT
core.PREFIX = 'F' + core.uuid.uuid4().hex[:5]
_api = core.api
_last = 0


def api(method, path, body=None):
    global _last
    time.sleep(max(0, 0.5 - (time.monotonic() - _last)))
    _last = time.monotonic()
    result = _api(method, path, body)
    core.EVIDENCE[-1]['api_base'] = core.BASE
    core.save()
    return result


core.api = api


def surface(name):
    core.BASE = ROOT + '/pc'
    core.SESSION.headers.update(settings.headers(mobile=name != 'pc'))


class FilterRun(Run):
    def __init__(self):
        self.records_by_model = {}
        self.labels_by_key = {}
        self.groups_by_id = {}
        self.default_cache = {}
        super().__init__()

    def save(self):
        super().save()
        (OUT / 'filter-state.json').write_text(json.dumps({
            'prefix': core.PREFIX, 'entities': self.entities, 'parents': self.parents,
            'records': self.records_by_model, 'labels': self.labels_by_key,
            'groups': self.groups_by_id, 'metadata': self.metadata, 'baseline': getattr(self, 'baseline', []),
            'results': self.results,
        }, ensure_ascii=False, indent=2))

    def chosen(self, label):
        return self.fixture.chosen(self.groups_by_id[label['label_group_id']], label)

    def defaults(self, model):
        if model not in self.default_cache:
            self.default_cache[model] = super().defaults(model)
        return copy.deepcopy(self.default_cache[model])

    def create(self, model, labels, suffix='筛选'):
        if model != 'Lead':
            return super().create(model, labels, suffix)
        name = core.PREFIX + suffix
        actual = core.success(self.fixture.create_lead([self.chosen(x) for x in labels], name=name))
        entity = {'model': model, 'id': actual['id'], 'name': name, 'deleted': False}
        self.entities.append(entity)
        self.save()
        return entity

    def prepare(self):
        limits = core.success(core.api('GET', '/label_groups'))
        assert len(self.baseline) + 3 <= limits['max_group_count']
        assert sum(len(g['labels']) for g in self.baseline) + 7 <= limits['max_label_count']
        for suffix, keys, kind in [('A', ['a', 'b', 'unused'], 'multi'), ('B', ['c', 'd'], 'multi'), ('R', ['r1', 'r2'], 'radio')]:
            group = self.fixture.group(name=core.PREFIX + suffix, select_type=kind, applicable_models=list(MODELS))
            self.groups_by_id[group['id']] = group
            self.save()
            for key in keys:
                self.labels_by_key[key] = self.fixture.label(group['id'], core.PREFIX + key)
                self.save()
        self.metadata = {m: {'template': TEMPLATES.get(m)} for m in MODELS}
        self.parents['customer'] = self.create('Customer', [], '父客户')
        self.parents['contract'] = self.create('Contract', [], '父合同')
        for model in ['Lead'] + [m for m in MODELS if m != 'Lead']:
            self.records_by_model[model] = []
            for keys in [[], ['a'], ['b'], ['a', 'b'], ['a', 'c'], ['c'], ['a', 'r1'], ['b', 'r2'], ['d']]:
                entity = self.create(model, [self.labels_by_key[k] for k in keys], ''.join(keys) or 'empty')
                entity['keys'] = keys
                self.records_by_model[model].append(entity)
                self.check(entity, [self.labels_by_key[k] for k in keys])
                self.save()
            print('PREPARED', model, len(self.records_by_model[model]), flush=True)

    def query(self, platform, model, params, page=1, per_page=100):
        surface(platform)
        path, wrapper, _ = MODELS[model]
        scope = []
        if platform == 'mobile' and model in ('ReceivedPayment', 'InvoicedPayment'):
            path = 'received_payment_center/' + path
            scope = [('scope', wrapper)]
        version = 'pc' if platform == 'pc' else MOBILE_VERSION[model]
        core.BASE = ROOT + '/' + version
        query = [('page', page), ('per_page', per_page), ('sort', 'updated_at'), ('order', 'desc')] + scope + params
        try:
            data = core.success(core.api('GET', '/' + path + '?' + urlencode(query)))
        finally:
            core.BASE = ROOT + '/pc'
        if isinstance(data, list):
            return data
        rows = data.get('list', data.get(MODELS[model][0]))
        assert isinstance(rows, list), ('list shape', model, data)
        return rows

    def params(self, platform, mode, keys):
        ids = [self.labels_by_key[k]['id'] for k in keys]
        if mode == 'ordinary':
            return [('label_id[]', i) for i in ids] + ([('labels[]', i) for i in ids] if platform == 'mobile' else [])
        if mode == 'ordinary_blank':
            return [('label_id[]', -1)] + ([('labels[]', -1)] if platform == 'mobile' else [])
        if mode == 'clear':
            return []
        return [('advanced_filters[][name]', 'labels'), ('advanced_filters[][operator]', mode)] + [
            ('advanced_filters[][query][]', i) for i in ids]

    def verify(self, platform, model, mode, keys):
        params = self.params(platform, mode, keys)
        rows = self.query(platform, model, params)
        ids = [r['id'] for r in rows]
        assert len(ids) == len(set(ids)), ('duplicate rows', ids)
        records = self.records_by_model[model]
        universe = {e['id'] for e in records}
        actual = set(ids) & universe
        want_keys = set(keys)
        if mode == 'contain_one':
            expected = {e['id'] for e in records if want_keys & set(e['keys'])}
        elif mode in ('ordinary', 'contain_all'):
            expected = {e['id'] for e in records if want_keys <= set(e['keys'])}
        elif mode in ('blank', 'ordinary_blank'):
            expected = {e['id'] for e in records if not e['keys']}
        elif mode == 'not_blank':
            expected = {e['id'] for e in records if e['keys']}
        else:
            expected = universe
        info = {'platform': platform, 'model': model, 'mode': mode, 'keys': keys,
                'actual_owned_ids': sorted(actual), 'expected_owned_ids': sorted(expected),
                'returned_count': len(ids), 'result_scope': 'owned fixture IDs'}
        if mode in ('ordinary', 'contain_one', 'contain_all'):
            assert set(ids) <= universe, ('unexpected nonfixture matches', info, sorted(set(ids) - universe))
        if mode == 'ordinary' and len(want_keys) > 1:
            intersection = {e['id'] for e in records if want_keys <= set(e['keys'])}
            union = {e['id'] for e in records if want_keys & set(e['keys'])}
            info['observed_relation'] = 'all' if actual == intersection else 'any' if actual == union else 'other'
        self.results.append({**info, 'status': 'PASS' if actual == expected else 'FAIL'})
        self.save()
        assert actual == expected, info

    def pagination(self, platform, model):
        params = self.params(platform, 'ordinary', ['a'])
        expected = {e['id'] for e in self.records_by_model[model] if 'a' in e['keys']}
        ids = []
        for page in range(1, 6):
            rows = self.query(platform, model, params, page=page, per_page=2)
            ids.extend(r['id'] for r in rows)
            if len(rows) < 2:
                break
        assert len(ids) == len(set(ids)) and set(ids) == expected, (model, platform, ids, expected)

    def test_filters(self, platform):
        surface(platform)
        common = [('ordinary', [k]) for k in ('a', 'c', 'r1', 'unused')]
        common += [('ordinary', k) for k in (['a', 'b'], ['a', 'c'], ['r1', 'r2'], ['a', 'a'])]
        common += [('ordinary_blank', []), ('clear', [])]
        advanced = [(mode, keys) for mode in ('contain_one', 'contain_all') for keys in (
            ['a'], ['a', 'b'], ['a', 'c'], ['r1', 'r2'], ['unused'])]
        advanced += [('blank', []), ('not_blank', [])]
        for model in (sys.argv[2:] or self.records_by_model):
            for mode, keys in common + (advanced if platform == 'pc' else []):
                result_count = len(self.results)
                try:
                    self.verify(platform, model, mode, keys)
                except Exception:
                    if len(self.results) == result_count:
                        self.results.append({'platform': platform, 'model': model, 'mode': mode, 'keys': keys,
                                             'status': 'FAIL', 'error': traceback.format_exc()[-2000:]})
                    self.save()
            self.case(model, platform + '_pagination', lambda: self.pagination(platform, model))
            print('FILTERED', platform, model, flush=True)


def restore():
    state = json.loads((OUT / 'filter-state.json').read_text())
    run = FilterRun.__new__(FilterRun)
    run.entities = state['entities']; run.parents = state['parents']; run.results = state['results']
    run.metadata = state['metadata']; run.baseline = state['baseline']; run.records_by_model = state['records']
    run.labels_by_key = state['labels']; run.groups_by_id = {int(k): v for k, v in state['groups'].items()}
    run.default_cache = {}; run.fixture = core.PCLeadTests(); run.counter = len(run.entities); run.primary = {}
    core.PREFIX = state['prefix']
    core.OWN_GROUPS.update(run.groups_by_id)
    core.OWN_LABELS.update(l['id'] for l in run.labels_by_key.values())
    if (OUT / 'evidence.json').exists():
        core.EVIDENCE[:] = json.loads((OUT / 'evidence.json').read_text())['requests']
    return run


if __name__ == '__main__':
    surface('pc')
    phase = sys.argv[1]
    run = FilterRun() if phase == 'prepare' else restore()
    try:
        if phase == 'prepare': run.prepare()
        elif phase in ('pc', 'mobile'): run.test_filters(phase)
        elif phase == 'cleanup': run.cleanup()
    finally:
        run.save()
    print('RESULTS', OUT, flush=True)
