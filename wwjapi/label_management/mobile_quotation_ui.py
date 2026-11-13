"""Helpers used for quotation create/edit/remove/copy/contract Android UI checks.

Requires an active Appium WebView session and the local run fixture ledger.
The functions are interactive helpers, not an unattended regression runner.
"""
import json,pathlib,requests,os
import appium_webview as wd
OUT=pathlib.Path(__file__).resolve().parent/'results/20261113-mobile-quotation-ui';PREFIX='MQ13f62'
H={'Authorization':f'Token token="{os.environ["CRM_LABEL_TOKEN"]}",device="lxcrm_duli",version_code="4.0.1"'}
def api(m,p,b=None):
 r=requests.request(m,'https://lxcrm-api-test.weiwenjia.com'+p,headers=H,json=b,timeout=45);d=r.json();f=OUT/'api-evidence.json';log=json.loads(f.read_text()) if f.exists() else [];log.append({'method':m,'path':p,'body':b,'status':r.status_code,'response':d});f.write_text(json.dumps(log,ensure_ascii=False,indent=2));assert r.ok and d.get('code')==0,str(d)[:1000];return d['data']
def text(t):return wd.visible_click('//*[text()='+json.dumps(t,ensure_ascii=False)+']')
def fill(name,value):
 e=wd.find('//input[@name='+json.dumps(name)+']');wd.call('POST','/element/'+e+'/clear',{});wd.call('POST','/element/'+e+'/value',{'text':str(value)})
def snap(name):
 d=wd.state();(OUT/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));wd.shot(str(OUT/(name+'.png')));print(json.dumps(d,ensure_ascii=False)[-6500:])
def network(name):
 q=wd.js('return window.__qaRequests||[]');
 for x in q:x.pop('headers',None)
 (OUT/(name+'-network.json')).write_text(json.dumps(q,ensure_ascii=False,indent=2));print([(x['method'],x['url'],x.get('response',{}).get('code')) for x in q][-12:])
def back():
 wd.call('POST','/context',{'name':'NATIVE_APP'});wd.call('POST','/appium/device/press_keycode',{'keycode':4});wd.call('POST','/context',{'name':'WEBVIEW_com.lixiaoyun.aike'})
def picker():
 if not wd.js('return Array.from(document.querySelectorAll(".lxy-form-item-title-tx")).some(e=>e.textContent==="标签")'):text('展开')
 text('标签');wd.wait('return document.body.innerText.includes("'+PREFIX+'共享A")')
def toggle(content):wd.visible_click('//div[@class="lxy-form-label-list"]/div[text()='+json.dumps(content,ensure_ascii=False)+']')
def chosen():return wd.js('return Array.from(document.querySelectorAll(".lxy-form-label-list:not(.lxy-form-label-list-selected):not(.lxy-form-label-list-cell)>.lxy-form-label-item")).filter(e=>e.style.color).map(e=>e.textContent)')
def register(model,route,id,name=None):
 f=json.loads((OUT/'fixture.json').read_text());d=api('GET','/api/pc/'+route+'/'+str(id));entry={'model':model,'id':id,'name':d.get('name',d.get('title')), 'deleted':False}
 if not any(e['id']==id and e['model']==model for e in f['entities']):f['entities'].append(entry)
 (OUT/'fixture.json').write_text(json.dumps(f,ensure_ascii=False,indent=2));return d

def record(stage,route,id,expected):
 d=api('GET','/api/pc/'+route+'/'+str(id));actual=sorted(x['id'] for x in d['labels']);f=json.loads((OUT/'fixture.json').read_text());want=sorted(f['labels'][i]['id'] for i in expected);logfile=OUT/'ui-results.json';log=json.loads(logfile.read_text()) if logfile.exists() else [];log.append({'stage':stage,'route':route,'id':id,'expected':want,'actual':actual,'status':'PASS' if actual==want else 'FAIL'});logfile.write_text(json.dumps(log,ensure_ascii=False,indent=2));assert actual==want,(actual,want);(OUT/(stage+'-readback.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(stage,'PASS',actual)
