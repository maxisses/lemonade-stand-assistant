"""Operator-only analysis workflow; records share the existing private checkpoint."""
import asyncio
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time
import uuid

import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

ACTIVE={'generating','allocating','running','stopping'}
TASKS={'total':'Read sales.csv using the csv module. Print the total cups and litres at 0.25 litres per cup.',
       'peak':'Read sales.csv using the csv module. Print the day with the most cups and its cup count.'}


def extract_code(text):
    text=text.strip()
    if text.startswith('```'):
        match=re.fullmatch(r'```(?:python)?\s*\n(.*?)\n```',text,re.S)
        if not match:raise ValueError('Incomplete code block')
        text=match.group(1).strip()
    if not text or len(text.encode())>8000:raise ValueError('Invalid code size')
    compile(text,'generated-analysis.py','exec')  # Syntax only; never execute here.
    return text


class SandboxControl:
    def __init__(self,control):
        self.control=control;self.db=control.audience.db;self.task=None
        self.db.execute('CREATE TABLE IF NOT EXISTS sandbox_runs(id TEXT PRIMARY KEY,status TEXT,created REAL,document TEXT)')
        for row in self.db.execute('SELECT id,document FROM sandbox_runs').fetchall():
            record=json.loads(row['document'])
            if record['status'] in ACTIVE:
                record.update(status='interrupted',error='Application restarted; uncertain execution is not replayed.')
                self.save(record)
        self.db.commit();self.routes()
    def list(self):
        return [json.loads(x[0]) for x in self.db.execute('SELECT document FROM sandbox_runs ORDER BY created DESC LIMIT 30')]
    def active(self):return bool(self.task and not self.task.done())
    def save(self,record):
        self.db.execute('INSERT OR REPLACE INTO sandbox_runs VALUES(?,?,?,?)',(record['id'],record['status'],record['created'],json.dumps(record)))
        self.db.commit()
    def find(self,identifier):
        row=self.db.execute('SELECT document FROM sandbox_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'Sandbox record not found.')
        return json.loads(row[0])
    async def broker(self,path,method='GET',data=None,timeout=15):
        url=os.environ['SANDBOX_BROKER_URL']
        if not url.startswith('https://'):raise HTTPException(503,'Broker must use trusted TLS.')
        async with self.control.client.request(method,url+path,json=data,
                headers={'Authorization':'Bearer '+os.environ['SANDBOX_BROKER_KEY']},
                timeout=aiohttp.ClientTimeout(total=timeout),allow_redirects=False) as response:
            try:raw=await response.content.readexactly(32769)
            except asyncio.IncompleteReadError as partial:raw=partial.partial
            if len(raw)>32768:raise HTTPException(503,'Broker response is too large.')
            result=json.loads(raw)
            if response.status>=300:raise HTTPException(response.status,str(result.get('detail','Sandbox service error.'))[:200])
            return result
    async def generate(self,record):
        try:
            response=await self.control.generate('sandbox',{'messages':[
                {'role':'system','content':'You write a tiny Python 3 analysis for Snemeis Lemonade Division. The local sales.csv is synthetic: day,cups; Monday 40; Tuesday 55; Wednesday 65. Use only the standard library. Return only complete Python code, at most 12 lines. No markdown, networking, shell commands or package installation. This code is untrusted and will require operator review before isolated execution.'},
                {'role':'user','content':TASKS[record['task']]}]},192,record['id'])
            if response.get('status')!=200:raise ValueError('Provider did not return a successful response')
            record['code']=extract_code(response['text'])
            record.update(status='review',code_sha256=hashlib.sha256(record['code'].encode()).hexdigest())
        except asyncio.CancelledError:record.update(status='cancelled',error='Generation cancelled; accepted provider work may continue.')
        except Exception:record.update(status='generation_error',error='No complete code candidate was returned. Nothing was executed.')
        finally:self.save(record)
    async def execute(self,record):
        try:
            record.update(status='allocating');self.save(record)
            result=await self.broker('/runs','POST',{'id':record['id'],'code':record['code']},timeout=225)
            if result.get('code_sha256')!=record['code_sha256']:raise ValueError('Code identity mismatch')
            record.update(status='finished',result=result,finished=time.time())
            # Script outputs are untrusted; checks are narrow observations, not proof of containment against all attacks.
            kind=record.get('probe')
            if kind:
                record['check']='observed' if ((kind=='timeout' and result.get('outcome')=='timeout') or
                    (kind in ('egress','credentials') and result.get('outcome')=='completed' and result.get('stdout','').strip()=='BOUNDARY_OBSERVED')) else 'review_required'
        except asyncio.CancelledError:
            try:await self.broker('/runs/'+record['id'],'DELETE')
            except Exception:pass
            record.update(status='cancelled',error='Stop requested. Confirm broker cleanup before the next execution.')
        except Exception:record.update(status='execution_error',error='Sandbox execution or verification failed. Inspect platform health; no retry was sent.')
        finally:self.save(record)
    async def stop(self):
        if self.active():
            self.task.cancel()
            await self.task
    def routes(self):
        app=self.control.app;c=self.control
        async def data(request):
            raw=await request.body()
            if len(raw)>1024:raise HTTPException(413,'Request too large.')
            try:result=json.loads(raw)
            except ValueError:raise HTTPException(400,'Invalid JSON.') from None
            if not isinstance(result,dict):raise HTTPException(400,'Expected an object.')
            return result
        @app.get('/sandbox',response_class=HTMLResponse)
        async def page(request:Request):
            await c.permission(request)
            return HTMLResponse((Path(__file__).parent/'static/sandbox.html').read_text(),headers={'Cache-Control':'no-store'})
        @app.get('/api/control/sandbox')
        async def state(request:Request):
            subject=await c.permission(request)
            try:platform=await self.broker('/state')
            except Exception:platform={'unavailable':True}
            return {'csrf_token':c.csrf(subject),'runs':self.list(),'active':self.active(),'platform':platform,
                    'can_execute':bool(await c.permission(request,execute=True,fail=False)),
                    'locked':c.settings_locked(),'model':c.settings.get('model') if c.settings else None}
        @app.post('/api/control/sandbox/generate')
        async def generate(request:Request):
            await c.mutation(request);body=await data(request)
            if set(body)!={'task'} or not isinstance(body['task'],str) or body['task'] not in TASKS:raise HTTPException(400,'Choose a fixed synthetic analysis task.')
            async with c.config_lock:
                if c.settings_locked():raise HTTPException(409,'Close audience access and finish active work first.')
                await c.sync_settings()
                platform=await self.broker('/state')
                if platform.get('active') or platform.get('cleanup_error') or not platform.get('ready'):raise HTTPException(409,'Sandbox platform is not idle.')
                record={'id':uuid.uuid4().hex,'created':time.time(),'status':'generating','task':body['task'],'model':c.settings['model'],'policy':c.policy(),'synthetic':True}
                self.save(record);self.task=asyncio.create_task(self.generate(record));return record
        @app.post('/api/control/sandbox/{identifier}/run')
        async def execute(identifier:str,request:Request):
            await c.mutation(request);body=await data(request)
            async with c.config_lock:
                if c.settings_locked():raise HTTPException(409,'Close audience access and finish active work first.')
                record=self.find(identifier)
                if record['status']!='review' or body!={'code_sha256':record['code_sha256']}:
                    raise HTTPException(409,'Review the exact current code candidate before executing it.')
                record['status']='allocating';self.save(record);self.task=asyncio.create_task(self.execute(record));return record
        @app.post('/api/control/sandbox/probe')
        async def probe(request:Request):
            await c.mutation(request);body=await data(request)
            if set(body)!={'probe'} or body['probe'] not in ('egress','credentials','timeout'):raise HTTPException(400,'Choose a fixed boundary check.')
            async with c.config_lock:
                if c.settings_locked():raise HTTPException(409,'Close audience access and finish active work first.')
                # Verify the canary service is healthy before testing runner reachability.
                await self.broker('/state')
                if body['probe']=='egress':
                    host=os.environ['SANDBOX_BROKER_URL'].split('/')[2].split(':')[0]
                    addresses=await asyncio.get_running_loop().getaddrinfo(host,8443,family=socket.AF_INET,type=socket.SOCK_STREAM)
                    ip=str(ipaddress.IPv4Address(addresses[0][4][0]))
                    code=f"import socket\ntry:\n s=socket.create_connection(({ip!r},8443),1)\n s.close()\n print('UNEXPECTED_NETWORK_ACCESS')\nexcept (TimeoutError,OSError):\n print('BOUNDARY_OBSERVED')\n"
                elif body['probe']=='credentials':
                    code="from pathlib import Path\np=Path('/var/run/secrets/kubernetes.io/serviceaccount/token')\nprint('UNEXPECTED_TOKEN_MOUNT' if p.exists() else 'BOUNDARY_OBSERVED')\n"
                else:code="import time\ntime.sleep(30)\n"
                record={'id':uuid.uuid4().hex,'created':time.time(),'status':'allocating','probe':body['probe'],'code':code,'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'synthetic':True}
                self.save(record);self.task=asyncio.create_task(self.execute(record));return record
        @app.post('/api/control/sandbox/stop')
        async def stop(request:Request):
            await c.mutation(request)
            await self.stop()
            return {'stop_requested':True}
