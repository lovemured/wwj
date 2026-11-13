#!/usr/bin/env python3
"""Owned records for Android label mapping UI verification."""
from environment import settings
import os,json,sys
from pathlib import Path
import pc_api_regression as core
from pc_module_regression import Run,MODELS
OUT=settings.result_root/'20261113-mobile-mapping-ui'
core.OUT=OUT;core.PREFIX='MP13d9'
core.SESSION.headers.update(settings.headers())
if sys.argv[1]=='prepare':
 r=Run();old=json.loads((OUT.parent/'20261113-label-filter/filter-state.json').read_text());r.metadata={k:old['metadata'][k] for k in MODELS}
 both=['Lead','Customer','Contact','Opportunity','Contract']
 r.multi=r.fixture.group(name=core.PREFIX+'共多',applicable_models=both)
 r.radio=r.fixture.group(name=core.PREFIX+'共单',select_type='radio',applicable_models=both)
 r.private=r.fixture.group(name=core.PREFIX+'源',applicable_models=['Lead','Opportunity'])
 labels=[r.fixture.label(r.multi['id'],core.PREFIX+'共享A'),r.fixture.label(r.multi['id'],core.PREFIX+'共享B'),r.fixture.label(r.radio['id'],core.PREFIX+'共享单'),r.fixture.label(r.private['id'],core.PREFIX+'源专属')]
 fixture={'groups':[r.multi,r.radio,r.private],'labels':labels,'baseline':r.baseline};(OUT/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2))
 r.parents['customer']=r.create('Customer',[],'父客户')
 r.create('Opportunity',labels,'转合同商机')
 d=core.success(r.fixture.create_lead([r.chosen(x) for x in labels],name=core.PREFIX+'转新客户线索'));r.entities.append({'model':'Lead','id':d['id'],'name':core.PREFIX+'转新客户线索','deleted':False});r.save()
 print(json.dumps(r.entities,ensure_ascii=False))
else:
 state=json.loads((OUT/'modules-summary.json').read_text());fixture=json.loads((OUT/'fixture.json').read_text());core.EVIDENCE[:]=json.loads((OUT/'evidence.json').read_text())['requests'];MODELS['Lead']=('leads','lead','name')
 if sys.argv[1]=='cleanup':
  r=Run.__new__(Run);r.__dict__.update({k:state[k] for k in ['entities','results','parents','metadata']});current=core.groups();owned={g['id'] for g in fixture['groups']};known={l['id'] for l in fixture['labels']};assert all(l['id'] in known for g in current if g['id'] in owned for l in g['labels']),'Unowned labels found in task groups';r.baseline=[g for g in current if g['id'] not in owned];(OUT/'configuration-before-cleanup.json').write_text(json.dumps({'preserve':r.baseline,'changed_since_start':r.baseline!=fixture['baseline'],'reason':'用户确认测试期间同时修改过标签；以清理前最新配置为保护基线'},ensure_ascii=False,indent=2));core.OWN_GROUPS.update(g['id'] for g in fixture['groups']);core.OWN_LABELS.update(l['id'] for l in fixture['labels']);r.cleanup()
