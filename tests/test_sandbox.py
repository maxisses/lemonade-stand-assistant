"""Offline authorization, lifecycle and boundary tests. No cloud/model calls."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'chart/files/lemonade'))
import sandbox_broker as broker
from sandbox_control import extract_code
from test_demo_runtime import call, ControlTests
from sandbox_control import SandboxControl


class SyntaxTests(unittest.TestCase):
    def test_complete_fenced_code(self):
        self.assertEqual(extract_code('```python\nprint(160)\n```'),'print(160)')
    def test_partial_or_oversized_code_is_rejected(self):
        for text in ('```python\nprint(', 'x='+'1'*8100, ''):
            with self.subTest(text=text[:20]),self.assertRaises((ValueError,SyntaxError)):extract_code(text)
    def test_compile_never_executes(self):
        with patch('os.system') as system:
            extract_code("import os\nos.system('not-executed')")
            system.assert_not_called()


class FakeBroker(broker.Broker):
    def __init__(self,runtime='kata-remote',owner=True):
        super().__init__();self.calls=[];self.runtime=runtime;self.owner=owner;self.deleted=False
    async def kube(self,method,path,data=None,missing=False):
        self.calls.append((method,path,data))
        if '/sandboxwarmpools/' in path:return {'status':{'readyReplicas':1}}
        if method=='DELETE':self.deleted=True;return {}
        if method=='POST' and path.endswith('/sandboxclaims'):return {}
        if '/sandboxclaims/' in path:
            return None if self.deleted else {'status':{'sandbox':{'name':'owned-sandbox'}}}
        if '/sandboxes/' in path:return {'metadata':{'uid':'sandbox-uid'}}
        if '/pods/' in path:
            return {'metadata':{'uid':'pod-uid','ownerReferences':[{'uid':'sandbox-uid' if self.owner else 'someone-else'}]},
                    'spec':{'runtimeClassName':self.runtime},'status':{'conditions':[{'type':'Ready','status':'True'}]}}
        raise AssertionError(path)
    async def runner(self,pod,code):
        self.calls.append(('POST','verified-runner',{'code':code}))
        return {'outcome':'completed','stdout':'160','exit_code':0,'seconds':.1}


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unauthenticated_request_before_kubernetes(self):
        with patch.dict(os.environ,{'SANDBOX_BROKER_KEY':'fake-test-secret'}),patch.object(broker.broker,'execute') as execute:
            status,_,_=await call(broker.app,'/runs','POST',{'id':'a'*32,'code':'print(1)'})
            self.assertEqual(status,403);execute.assert_not_called()
    async def test_fresh_vm_claim_executes_exact_code_then_cleans_up(self):
        service=FakeBroker();code='print(160)'
        result=await service.execute('a'*32,code)
        self.assertEqual(result['code_sha256'],hashlib.sha256(code.encode()).hexdigest())
        self.assertEqual(result['cleanup'],'complete');self.assertTrue(service.deleted)
        calls=[c for c in service.calls if c[1]=='verified-runner']
        self.assertEqual(calls[0][2],{'code':code})
    async def test_shared_kernel_or_wrong_owner_fails_closed(self):
        for service in (FakeBroker(runtime='runc'),FakeBroker(owner=False)):
            with self.subTest(runtime=service.runtime,owner=service.owner),self.assertRaises(broker.HTTPException):
                await service.execute('b'*32,'print(1)')
            self.assertTrue(service.deleted)
            self.assertFalse(any(c[1]=='verified-runner' for c in service.calls))
    async def test_failed_cleanup_blocks_next_run(self):
        service=FakeBroker()
        async def fail(name):raise RuntimeError('simulated cleanup failure')
        service.cleanup=fail
        result=await service.execute('a'*32,'print(1)')
        self.assertEqual(result['cleanup'],'attention_required')
        with self.assertRaises(broker.HTTPException):await service.execute('b'*32,'print(2)')
    async def test_platform_json_waits_for_all_chunks_and_keeps_size_bound(self):
        class Response:
            status=200
            def __init__(self,payload):
                self.content=asyncio.StreamReader()
                self.content.feed_data(payload[:3])
                async def finish():
                    await asyncio.sleep(.01)
                    self.content.feed_data(payload[3:]);self.content.feed_eof()
                self.pending=asyncio.create_task(finish())
            async def __aenter__(self):return self
            async def __aexit__(self,*args):await self.pending
        class Client:
            def __init__(self,payload):self.payload=payload
            def request(self,*args,**kwargs):return Response(self.payload)
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'token').write_text('fake-test-token')
            service=broker.Broker()
            with patch.object(broker,'SERVICE_ACCOUNT',Path(folder)):
                service.client=Client(b'{"status":{"readyReplicas":1}}')
                self.assertEqual(await service.kube('GET','/fixture'),{'status':{'readyReplicas':1}})
                service.client=Client(b' '*32769)
                with self.assertRaises(broker.HTTPException):await service.kube('GET','/fixture')
    async def test_runner_rejects_non_pod_destinations(self):
        service=broker.Broker()
        for address in ['127.0.0.1','169.254.169.254','8.8.8.8','::1']:
            with self.subTest(address=address),self.assertRaises(broker.HTTPException):
                await service.runner({'status':{'podIP':address}},'print(1)')
    async def test_parallel_execution_is_rejected(self):
        service=FakeBroker()
        async with service.lock:
            with self.assertRaises(broker.HTTPException):await service.execute('a'*32,'print(1)')

if __name__=='__main__':unittest.main()


class SandboxControlTests(unittest.IsolatedAsyncioTestCase):
    operator_headers=ControlTests.operator_headers
    asyncTearDown=ControlTests.asyncTearDown
    async def asyncSetUp(self):
        await ControlTests.asyncSetUp(self)
        self.sandbox=SandboxControl(self.control)
        self.control.sandbox=self.sandbox
        self.broker_calls=[]
        async def fake_broker(path,method='GET',data=None,timeout=15):
            self.broker_calls.append((path,method,data))
            return {'active':None,'cleanup_error':False}
        self.sandbox.broker=fake_broker
    async def test_sandbox_mutations_require_operator_and_csrf(self):
        for headers in ({},self.operator_headers('reader-token'),{'X-Forwarded-Access-Token':'operator-token'}):
            status,_,_=await call(self.app,'/api/control/sandbox/probe','POST',{'probe':'timeout'},headers)
            self.assertIn(status,(401,403))
        self.assertEqual(self.broker_calls,[])
    async def test_rejects_freeform_code_and_open_audience(self):
        status,_,_=await call(self.app,'/api/control/sandbox/generate','POST',{'task':'arbitrary','code':'print(1)'},self.operator_headers())
        self.assertEqual(status,400)
        self.control.audience.window('open',1)
        status,_,_=await call(self.app,'/api/control/sandbox/probe','POST',{'probe':'timeout'},self.operator_headers())
        self.assertEqual(status,409)
    async def test_review_hash_cannot_be_changed_or_replayed(self):
        record={'id':'a'*32,'created':1,'status':'review','code':'print(1)','code_sha256':hashlib.sha256(b'print(1)').hexdigest()}
        self.sandbox.save(record)
        status,_,_=await call(self.app,'/api/control/sandbox/'+record['id']+'/run','POST',{'code_sha256':'changed'},self.operator_headers())
        self.assertEqual(status,409)
        record['status']='finished';self.sandbox.save(record)
        status,_,_=await call(self.app,'/api/control/sandbox/'+record['id']+'/run','POST',{'code_sha256':record['code_sha256']},self.operator_headers())
        self.assertEqual(status,409)
        self.assertEqual(self.broker_calls,[])
