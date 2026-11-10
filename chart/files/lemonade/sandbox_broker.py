"""Fixed-template broker: authenticated service requests, fresh Kata claims, cleanup."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import time

import aiohttp
from fastapi import FastAPI, HTTPException, Request

NAMESPACE='lemonade-sandbox'
EXT='/apis/extensions.agents.x-k8s.io/v1beta1/namespaces/'+NAMESPACE
CORE='/apis/agents.x-k8s.io/v1beta1/namespaces/'+NAMESPACE
PODS='/api/v1/namespaces/'+NAMESPACE+'/pods'
SERVICE_ACCOUNT=Path('/var/run/secrets/kubernetes.io/serviceaccount')
OWNER={'lemonade.openshift.io/broker':'true'}


class Broker:
    def __init__(self):self.client=None;self.lock=asyncio.Lock();self.active=None;self.task=None;self.cleanup_error=False
    async def kube(self,method,path,data=None,missing=False):
        token=(SERVICE_ACCOUNT/'token').read_text().strip()
        async with self.client.request(method,'https://kubernetes.default.svc'+path,
                headers={'Authorization':'Bearer '+token},json=data,timeout=aiohttp.ClientTimeout(total=12)) as response:
            if missing and response.status==404:return None
            if not 200<=response.status<300:
                raise HTTPException(503,f'Sandbox platform rejected {method} {path} (HTTP {response.status}).')
            try:raw=await response.content.readexactly(32769)
            except asyncio.IncompleteReadError as partial:raw=partial.partial
            if len(raw)>32768:raise HTTPException(503,'Sandbox platform response exceeded the bound.')
            return json.loads(raw)
    async def runner(self,pod,code):
        # The destination comes only from the authenticated, owner-verified Pod status.
        address=ipaddress.ip_address(pod['status']['podIP'])
        if not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast:
            raise HTTPException(503,'Runner address is outside the private Pod network.')
        host='['+str(address)+']' if address.version==6 else str(address)
        async with self.client.post('http://'+host+':8080/run',json={'code':code},
                timeout=aiohttp.ClientTimeout(total=12),allow_redirects=False) as response:
            if response.status!=200:raise HTTPException(503,'Runner rejected execution (HTTP '+str(response.status)+').')
            try:raw=await response.content.readexactly(16385)
            except asyncio.IncompleteReadError as partial:raw=partial.partial
            if len(raw)>16384:raise HTTPException(503,'Runner response exceeded the bound.')
            return json.loads(raw)
    async def cleanup(self,name):
        await self.kube('DELETE',EXT+'/sandboxclaims/'+name,{'propagationPolicy':'Foreground'},missing=True)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if await self.kube('GET',EXT+'/sandboxclaims/'+name,missing=True) is None:return
            await asyncio.sleep(.5)
        raise HTTPException(503,'Sandbox cleanup has not completed; new executions are paused.')
    async def start(self):
        self.client=aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=str(SERVICE_ACCOUNT/'ca.crt'))))
        # No replay after a broker restart. Recover only our labeled claims.
        try:
            claims=await self.kube('GET',EXT+'/sandboxclaims?labelSelector=lemonade.openshift.io%2Fbroker%3Dtrue')
            for item in claims['items']:await self.cleanup(item['metadata']['name'])
        except Exception:self.cleanup_error=True
    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:await self.task
            except BaseException:pass
        if self.client:await self.client.close()
    async def execute(self,run_id,code):
        if self.lock.locked() or self.cleanup_error:raise HTTPException(409,'Sandbox is busy or cleanup requires attention.')
        async with self.lock:
            pool=await self.kube('GET',EXT+'/sandboxwarmpools/lemonade-python')
            if pool.get('status',{}).get('readyReplicas',0)<1:raise HTTPException(409,'No warm VM-backed sandbox is ready.')
            self.active=run_id;self.task=asyncio.current_task()
            name='lemonade-'+run_id
            result=None;start=time.monotonic()
            try:
                await self.kube('POST',EXT+'/sandboxclaims',{'apiVersion':'extensions.agents.x-k8s.io/v1beta1','kind':'SandboxClaim',
                    'metadata':{'name':name,'labels':OWNER},'spec':{'warmPoolRef':{'name':'lemonade-python'},'lifecycle':{'shutdownPolicy':'DeleteForeground','shutdownTime':(datetime.now(timezone.utc)+timedelta(seconds=240)).isoformat(),'ttlSecondsAfterFinished':0}}})
                deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    claim=await self.kube('GET',EXT+'/sandboxclaims/'+name)
                    target=claim.get('status',{}).get('sandbox',{}).get('name')
                    if target and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',target):
                        sandbox=await self.kube('GET',CORE+'/sandboxes/'+target)
                        pod=await self.kube('GET',PODS+'/'+target,missing=True)
                        if pod:
                            owners=pod['metadata'].get('ownerReferences',[])
                            if pod['spec'].get('runtimeClassName')!='kata-remote' or not any(x.get('uid')==sandbox['metadata']['uid'] for x in owners):
                                raise HTTPException(503,'VM runtime/ownership verification failed; execution refused.')
                            if any(x.get('type')=='Ready' and x.get('status')=='True' for x in pod.get('status',{}).get('conditions',[])):
                                result=await self.runner(pod,code)
                                # Runner output is untrusted evidence, never an authorization decision.
                                result={k:result.get(k) for k in ('outcome','stdout','exit_code','seconds','output_truncated','dataset')}
                                result.update(runtime='kata-remote',sandbox=target,pod_uid=pod['metadata']['uid'],
                                    code_sha256=hashlib.sha256(code.encode()).hexdigest(),allocation_seconds=round(time.monotonic()-start,3))
                                break
                    await asyncio.sleep(.5)
                if result is None:raise HTTPException(504,'A VM-backed sandbox did not become ready before the deadline.')
                return result
            finally:
                try:await asyncio.shield(self.cleanup(name))
                except Exception:
                    self.cleanup_error=True
                    if result is not None:result['cleanup']='attention_required'
                else:
                    if result is not None:result['cleanup']='complete'
                self.active=None;self.task=None

broker=Broker()
@asynccontextmanager
async def lifespan(app):
    await broker.start()
    yield
    await broker.stop()
app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

def authenticate(request):
    expected=os.environ.get('SANDBOX_BROKER_KEY','')
    if not expected or not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+expected):
        raise HTTPException(403,'Service authorization required.')

@app.get('/health')
async def health():return {'ready':not broker.cleanup_error}

@app.get('/state')
async def state(request:Request):
    authenticate(request)
    pool=await broker.kube('GET',EXT+'/sandboxwarmpools/lemonade-python')
    return {'active':broker.active,'cleanup_error':broker.cleanup_error,'runtime':'kata-remote','preview':True,'ready':pool.get('status',{}).get('readyReplicas',0)>0}

@app.post('/runs')
async def execute(request:Request):
    authenticate(request)
    raw=await request.body()
    if len(raw)>12000:raise HTTPException(413,'Request too large.')
    try:
        data=json.loads(raw)
        assert set(data)=={'id','code'} and re.fullmatch('[a-f0-9]{32}',data['id'])
        assert isinstance(data['code'],str) and 0<len(data['code'].encode())<=8000
    except (ValueError,AssertionError,TypeError,KeyError):raise HTTPException(400,'Invalid execution request.') from None
    return await broker.execute(data['id'],data['code'])

@app.delete('/runs/{run_id}')
async def cancel(run_id:str,request:Request):
    authenticate(request)
    if broker.active==run_id and broker.task:broker.task.cancel()
    return {'stop_requested':broker.active==run_id}
