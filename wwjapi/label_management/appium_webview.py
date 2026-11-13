"""Appium commands for the already connected Android APP WebView session."""
import json,requests,pathlib,base64,os
SID=json.loads(pathlib.Path(os.environ['APPIUM_SESSION_FILE']).read_text())['sessionId']
URL=os.environ.get('APPIUM_SERVER_URL','http://127.0.0.1:14723').rstrip('/')+'/session/'+SID

def call(method,path,data=None):
 r=requests.request(method,URL+path,json=data,timeout=60)
 d=r.json(); v=d.get('value')
 if r.status_code>=400:raise RuntimeError(str(v)[:1800])
 return v

def js(script,*args):return call('POST','/execute/sync',{'script':script,'args':list(args)})
def find(xpath):return call('POST','/element',{'using':'xpath','value':xpath})['element-6066-11e4-a52e-4f735466cecf']
def click(xpath):return call('POST','/element/'+find(xpath)+'/click',{})
def state():return {'url':call('GET','/url'),'text':js('return document.body.innerText')}
def shot(path):pathlib.Path(path).write_bytes(base64.b64decode(call('GET','/screenshot')))
if __name__=='__main__':print(json.dumps(call('GET','/contexts'),ensure_ascii=False))

def visible_click(xpath):
 for e in call('POST','/elements',{'using':'xpath','value':xpath}):
  eid=e['element-6066-11e4-a52e-4f735466cecf']
  if call('GET','/element/'+eid+'/displayed'):
   return call('POST','/element/'+eid+'/click',{})
 raise RuntimeError('No visible element for '+xpath)

def wait(script,timeout=20):
 import time
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if js(script):return
  time.sleep(.5)
 raise RuntimeError('UI wait timed out: '+script)
