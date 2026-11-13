#!/usr/bin/env python3
"""Verify mapped labels from PC new-record prefill through submitted detail."""
import uuid
from urllib.parse import urlencode
import pc_api_regression as core
from pc_module_regression import MODELS


def mapping(run, source, target, relation, submit_extra=None):
    label_ids = [run.m1['id'], run.m2['id'], run.r1['id']]
    run.check(source, [run.m1, run.m2, run.r1])
    path, wrapper, identity = MODELS[target]
    query = {relation: source['id']}
    if run.metadata[target]['template']:
        query['custom_field_template_id'] = run.metadata[target]['template']
    preview = core.success(core.api('GET', '/' + path + '/new?' + urlencode(query)))
    mapped = preview.get('labels', [])
    assert sorted(x['id'] for x in mapped) == sorted(label_ids), {'source': source, 'target': target, 'prefill_labels': mapped}
    data = run.data(target, [], '映射')
    data['labels'] = mapped
    data[relation] = source['id']
    if target == 'Contract': data['quotation_ids'] = []
    body = {wrapper: data, 'request_ticket': str(uuid.uuid4()), **(submit_extra or {})}
    if target == 'InvoicedPayment': body['contract_id'] = source['id']
    created = core.success(core.api('POST', '/' + path, body))
    entity = {'model': target, 'id': created['id'], 'name': data[identity], 'deleted': False}
    run.entities.append(entity); run.save()
    run.check(entity, [run.m1, run.m2, run.r1])
    run.check(source, [run.m1, run.m2, run.r1])


def run_mappings(run):
    run.set(run.parents['customer'], [run.m1, run.m2, run.r1])
    run.set(run.parents['contract'], [run.m1, run.m2, run.r1])
    opportunity = run.create('Opportunity', [run.m1, run.m2, run.r1], '映射源商机')
    for target in ('Contact', 'Opportunity', 'Quotation', 'Contract'):
        run.case(target, 'mapping_from_customer_prefill_submit_read',
                 lambda target=target: mapping(run, run.parents['customer'], target, 'customer_id'))
    run.case('Quotation', 'mapping_from_opportunity_prefill_submit_read',
             lambda: mapping(run, opportunity, 'Quotation', 'opportunity_id'))
    for target in ('ReceivedPayment', 'InvoicedPayment'):
        run.case(target, 'mapping_from_contract_prefill_submit_read',
                 lambda target=target: mapping(run, run.parents['contract'], target, 'contract_id'))
    run.case('Contract', 'mapping_opportunity_turn_contract_prefill_submit_read',
             lambda: mapping(run, opportunity, 'Contract', 'opportunity_id',
                             {'turn_to_contract': True, 'source_name': 'opportunity'}))
