#!/usr/bin/env python3
"""Disposable fixtures and readback for the Android full-form label regression."""
import json, os, sys
from pathlib import Path
import pc_api_regression as core
from pc_module_regression import Run, MODELS

OUT = Path(__file__).resolve().parent/'results/20261113-mobile-label-ui'
core.OUT = OUT
core.PREFIX = 'MU13b47'
core.SESSION.headers.update(Authorization=f'Token token="{os.environ["CRM_LABEL_TOKEN"]}",device="web"')
phase=sys.argv[1]
if phase in ('prepare','resume'):
    if phase=='prepare':
        r=Run()
    else:
        state=json.loads((OUT/'modules-summary.json').read_text());ev=json.loads((OUT/'evidence.json').read_text())['requests'];core.EVIDENCE[:]=ev
        r=Run.__new__(Run);r.__dict__.update({k:state[k] for k in ['entities','results','parents','metadata']});r.fixture=core.PCLeadTests();r.counter=len(r.entities);r.baseline=ev[0]['response']['data']['list']
    old=json.loads((OUT.parent/'20261113-label-filter/filter-state.json').read_text())
    r.metadata={k:old['metadata'][k] for k in MODELS}
    if phase=='prepare':
        groups=[r.fixture.group(name=core.PREFIX+'多',applicable_models=['Lead']+list(MODELS)),r.fixture.group(name=core.PREFIX+'单',select_type='radio',applicable_models=['Lead']+list(MODELS))]
        labels=[r.fixture.label(g['id'],core.PREFIX+key) for g,keys in zip(groups,[['多A','多B'],['单A','单B']]) for key in keys]
    else:
        groups=[x['response']['data'] for x in ev if x['method']=='POST' and x['path']=='/label_groups'];labels=[x['response']['data'] for x in ev if x['method']=='POST' and x['path']=='/labels']
    if 'customer' not in r.parents:r.parents['customer']=r.create('Customer',[],'父客户')
    r.parents['contract']=r.create('Contract',[],'父合同')
    for m in MODELS:
        if m!='Quotation':r.create(m,[],'页面'+m)
    actual=core.success(r.fixture.create_lead([],name=core.PREFIX+'页面Lead'))
    r.entities.append({'model':'Lead','id':actual['id'],'name':core.PREFIX+'页面Lead','deleted':False});r.save()
    (OUT/'fixture.json').write_text(json.dumps({'groups':groups,'labels':labels,'baseline':r.baseline},ensure_ascii=False,indent=2))
    print('PREPARED',[(e['model'],e['id'],e['name']) for e in r.entities],flush=True)
else:
    state=json.loads((OUT/'modules-summary.json').read_text());fixture=json.loads((OUT/'fixture.json').read_text())
    core.EVIDENCE[:]=json.loads((OUT/'evidence.json').read_text())['requests']
    MODELS['Lead']=('leads','lead','name')
    if phase=='read':
        model=sys.argv[2];e=next(e for e in state['entities'] if e['model']==model and '页面' in e['name']);d=core.success(core.api('GET','/'+MODELS[model][0]+'/'+str(e['id'])))
        ids=[x['id'] for x in fixture['labels']]
        expected={'added':ids[:3],'edited':[ids[1],ids[3]],'removed':[ids[3]],'cleared':[]}[sys.argv[3]]
        actual_ids=sorted(x['id'] for x in d.get('labels',[]))
        assert actual_ids==expected,(model,sys.argv[3],actual_ids,expected)
        print(json.dumps({'model':model,'id':e['id'],'name':e['name'],'labels':d.get('labels',[]),'url':d.get('url')},ensure_ascii=False))
        (OUT/(model+'-'+sys.argv[3]+'-readback.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
    elif phase=='cleanup':
        r=Run.__new__(Run);r.__dict__.update({k:state[k] for k in ['entities','results','parents','metadata']});r.baseline=fixture['baseline'];core.OWN_GROUPS.update(g['id'] for g in fixture['groups']);core.OWN_LABELS.update(l['id'] for l in fixture['labels']);r.cleanup()
