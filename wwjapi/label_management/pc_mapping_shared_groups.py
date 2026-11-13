#!/usr/bin/env python3
"""Online mapping regression for shared-group filtering, using owned fixtures."""
from environment import settings
import json
import os
import traceback
import uuid
from urllib.parse import urlencode
import pc_api_regression as core
from pc_module_regression import Run, MODELS

PATHS = [('Customer', 'Contact', 'customer_id'), ('Customer', 'Opportunity', 'customer_id'),
         ('Customer', 'Quotation', 'customer_id'), ('Customer', 'Contract', 'customer_id'),
         ('Opportunity', 'Quotation', 'opportunity_id'),
         ('Contract', 'ReceivedPayment', 'contract_id'), ('Contract', 'InvoicedPayment', 'contract_id')]


def check_mapping(run, source, target, relation, source_labels, expected, case):
    run.set(source, source_labels)
    path, wrapper, identity = MODELS[target]
    query = {relation: source['id']}
    if run.metadata[target]['template']:
        query['custom_field_template_id'] = run.metadata[target]['template']
    preview = core.success(core.api('GET', '/' + path + '/new?' + urlencode(query)))
    mapped = preview.get('labels', [])
    expected_ids = sorted(x['id'] for x in expected)
    actual_ids = sorted(x['id'] for x in mapped)
    record = {'case': case, 'source': source, 'target': target, 'relation': relation,
              'source_label_ids': sorted(x['id'] for x in source_labels), 'expected_label_ids': expected_ids,
              'prefill_label_ids': actual_ids, 'prefill_path': '/' + path + '/new?' + urlencode(query)}
    run.mapping_details.append(record)
    (core.OUT / 'mapping-details.json').write_text(json.dumps(run.mapping_details, ensure_ascii=False, indent=2))
    assert actual_ids == expected_ids, record
    body = run.data(target, [], '共组映射')
    body.update(labels=mapped, **{relation: source['id']})
    if target == 'Contract': body['quotation_ids'] = []
    request = {wrapper: body, 'request_ticket': str(uuid.uuid4())}
    if target == 'InvoicedPayment': request['contract_id'] = source['id']
    data = core.success(core.api('POST', '/' + path, request))
    entity = {'model': target, 'id': data['id'], 'name': body[identity], 'deleted': False}
    run.entities.append(entity); run.save()
    record['target_entity'] = dict(entity)
    record['saved_label_ids'] = sorted(x['id'] for x in run.detail(entity)['labels'])
    (core.OUT / 'mapping-details.json').write_text(json.dumps(run.mapping_details, ensure_ascii=False, indent=2))
    assert record['saved_label_ids'] == expected_ids, record
    run.check(source, source_labels)
    # The product correctly blocks removing a module while its records use the
    # group. Remove this owned target before changing group applicability.
    run.set(entity, [])
    core.success(core.api('DELETE', '/' + path + '/' + str(entity['id'])))
    _, removed = core.api('GET', '/' + path + '/' + str(entity['id']))
    assert removed.get('code') in (100100, 100114), removed
    entity['deleted'] = True
    run.save()


def scope(group, models):
    core.success(core.api('PUT', '/label_groups/' + str(group['id']), {'label_group': {'applicable_models': models}}))
    actual = next(g for g in core.groups() if g['id'] == group['id'])
    assert set(actual['applicable_models']) == set(models), actual


if __name__ == '__main__':
    token = settings.token
    core.SESSION.headers.update(settings.headers())
    run = Run(); run.mapping_details = []
    try:
        run.prepare()
        run.parents['opportunity'] = run.create('Opportunity', [], '映射源商机')
        for source_model, target, relation in PATHS:
            # Clear other owned parents to detect accidental fallback inheritance.
            for parent in run.parents.values(): run.set(parent, [])
            source = run.parents[source_model.lower()]
            scope(run.multi, [source_model, target]); scope(run.radio, [source_model, target])
            scope(run.private, [source_model])
            shared = [run.m1, run.m2, run.r1]
            all_labels = shared + [run.excluded]
            name = source_model + '_to_' + target
            run.case(target, name + '_shared_groups_filter_private',
                     lambda: check_mapping(run, source, target, relation, all_labels, shared, 'shared_groups_filter_private'))
            scope(run.multi, [source_model]); scope(run.radio, [source_model])
            run.case(target, name + '_no_shared_groups',
                     lambda: check_mapping(run, source, target, relation, all_labels, [], 'no_shared_groups'))
            run.case(target, name + '_empty_source_labels',
                     lambda: check_mapping(run, source, target, relation, [], [], 'empty_source_labels'))
    except Exception:
        run.results.append({'model': 'setup', 'case': 'setup', 'status': 'BLOCKED', 'error': traceback.format_exc()})
        print(run.results[-1]['error'], flush=True)
    finally:
        run.cleanup()
        print('Evidence:', core.OUT, flush=True)
    raise SystemExit(0 if all(x['status'] == 'PASS' for x in run.results) else 1)
