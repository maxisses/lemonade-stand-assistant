"""Offline security, admission and same-path tests for the event runtime.

All HTTP clients are fakes. No provider, Kubernetes or AWS requests are made.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from multidict import CIMultiDict
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chart/files/lemonade"))
import audience_gateway as gateway
import demo_control as control
import provider_budget as provider


def request(path="/", method="POST", body=None, headers=None):
    raw = body if isinstance(body, bytes) else json.dumps(body or {}).encode()
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.Event().wait()
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": method, "scheme": "https",
             "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
             "client": ("198.51.100.1", 1234), "server": ("demo.example", 443)}
    return Request(scope, receive)


async def call(app, path, method="GET", body=None, headers=None):
    req = request(path, method, body, headers)
    messages = []
    async def send(message):
        messages.append(message)
    await app(req.scope, req.receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), raw


class Reply:
    def __init__(self, status=200, data=None, headers=None, gate=None):
        self.status = status
        self.data = data if data is not None else {"choices": [{"message": {"content": "Lemonade."}}], "usage": {"total_tokens": 20}}
        self.headers = CIMultiDict(headers or {"Content-Type": "application/json"})
        self.gate = gate
        self.entered = asyncio.Event()

    async def __aenter__(self):
        self.entered.set()
        return self

    async def __aexit__(self, *args):
        return False

    async def read(self):
        if self.gate is not None:
            await self.gate.wait()
        return self.data if isinstance(self.data, bytes) else json.dumps(self.data).encode()

    async def json(self):
        return self.data


class FakeClient:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.replies:
            return self.replies.pop(0)
        if "selfsubjectaccessreviews" in url:
            token = kwargs["headers"]["Authorization"]
            verb = kwargs["json"]["spec"]["resourceAttributes"]["verb"]
            allowed = token == "Bearer operator-token" or (token == "Bearer reader-token" and verb == "get")
            return Reply(201, {"status": {"allowed": allowed}})
        if url.endswith("/budget"):
            return Reply(200, {"paused": "", "last_hour": {"requests": 0}})
        return Reply()

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    async def close(self):
        pass


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {"MODEL_API_KEY": "fake-provider-key", "PROVIDER_MODEL": "fake-model", "PROVIDER_BASE_URL": "https://model.example"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = str(Path(self.directory.name) / "provider.sqlite")
        provider.app.state.ledger = provider.Ledger(self.path)
        self.addCleanup(provider.app.state.ledger.db.close)
        provider.app.state.session = FakeClient()
        provider.app.state.lock = asyncio.Lock()
        provider.app.state.slots = asyncio.Semaphore(1)
        provider.app.state.configuring = False
        provider.app.state.models_lock = asyncio.Lock()
        provider.app.state.model_catalog = None
        provider.app.state.waiting = 0
        provider.app.state.errors = 0

    def req(self, body=None, headers=None):
        return request(body=body or {"model": "fake-model", "messages": [{"role": "user", "content": "Hi"}]},
                       headers={"Authorization": "Bearer fake-provider-key", **(headers or {})})

    async def test_auth_allowlist_and_bounded_generation(self):
        for req in [request(), self.req(headers={"Authorization": "Bearer wrong"})]:
            with self.assertRaises(HTTPException) as error:
                await provider.forward("v1/chat/completions", req)
            self.assertEqual(error.exception.status_code, 401)
        for path in ["models", "v1/files", "../chat/completions"]:
            with self.assertRaises(HTTPException) as error:
                await provider.forward(path, self.req())
            self.assertEqual(error.exception.status_code, 404)
        for extra in [{"max_tokens": 193}, {"max_tokens": True}, {"max_completion_tokens": 999}, {"n": True}, {"n": 2}, {"stream": True}, {"model": "another-model"}]:
            with self.subTest(extra=extra), self.assertRaises(HTTPException) as error:
                await provider.forward("v1/chat/completions", self.req({"model": "fake-model", **extra}))
            self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(provider.app.state.session.calls, [])

    async def test_missing_cap_normalized_no_redirects_and_role_reserved(self):
        response = await provider.forward("v1/chat/completions", self.req(headers={"X-Demo-Role": "attacker"}))
        self.assertEqual(response.status_code, 200)
        method, url, kwargs = provider.app.state.session.calls[0]
        self.assertEqual(url, "https://model.example/v1/chat/completions")
        self.assertEqual(kwargs["json"]["max_tokens"], 128)
        self.assertIs(kwargs["json"]["stream"], False)
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(kwargs["json"]["chat_template_kwargs"], {"enable_thinking": False})
        row = provider.app.state.ledger.db.execute("SELECT role,tokens,estimated,status FROM calls").fetchone()
        self.assertEqual(row, ("attacker", 20, 0, "completed"))

    async def test_queue_rejection_makes_no_call(self):
        provider.app.state.waiting = 8
        with self.assertRaises(HTTPException) as error:
            await provider.forward("tokenize", self.req())
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(provider.app.state.session.calls, [])
        self.assertEqual(provider.app.state.ledger.usage(3600)["requests"], 0)

    async def test_throttle_pauses_all_roles_without_retry(self):
        provider.app.state.session = FakeClient([Reply(429, {"secret": "upstream-detail"})])
        response = await provider.forward("tokenize", self.req())
        self.assertEqual(response.status_code, 429)
        self.assertNotIn(b"upstream-detail", response.body)
        self.assertEqual(provider.app.state.ledger.paused(), "provider_throttled")
        with self.assertRaises(HTTPException) as error:
            await provider.forward("tokenize", self.req(headers={"X-Demo-Role": "judge"}))
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(len(provider.app.state.session.calls), 1)

    async def test_repeated_errors_pause_and_redirect_is_error(self):
        provider.app.state.session = FakeClient([Reply(302), Reply(500), Reply(503)])
        for expected in [502, 500, 503]:
            response = await provider.forward("tokenize", self.req())
            self.assertEqual(response.status_code, expected)
        self.assertEqual(len(provider.app.state.session.calls), 3)
        self.assertEqual(provider.app.state.ledger.paused(), "repeated_provider_errors")

    async def test_cancel_keeps_charge_and_restart_marks_unknown_work(self):
        reply = Reply(gate=asyncio.Event())
        provider.app.state.session = FakeClient([reply])
        task = asyncio.create_task(provider.forward("v1/chat/completions", self.req()))
        await reply.entered.wait()
        reserved = provider.app.state.ledger.usage(3600)["tokens"]
        self.assertGreater(reserved, 128)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(provider.app.state.waiting, 0)
        row = provider.app.state.ledger.db.execute("SELECT status,tokens,estimated FROM calls").fetchone()
        self.assertEqual(row, ("cancelled_unknown_upstream", reserved, 1))
        provider.app.state.ledger.reserve("judge", True, 100)
        restarted = provider.Ledger(self.path)
        try:
            self.assertEqual(restarted.db.execute("SELECT status FROM calls ORDER BY id DESC LIMIT 1").fetchone()[0], "interrupted")
            self.assertEqual(restarted.usage(3600)["generations"], 2)
        finally:
            restarted.db.close()

    async def test_hourly_budget_persists_and_auxiliary_calls_count(self):
        ledger = provider.app.state.ledger
        for _ in range(120):
            ledger.finish(ledger.reserve("target", True, 1), "completed")
        with self.assertRaises(HTTPException):
            ledger.reserve("attacker", True, 1)
        self.assertEqual(ledger.paused(), "hourly_budget")
        reopened = provider.Ledger(self.path)
        try:
            self.assertEqual(reopened.paused(), "hourly_budget")
            self.assertEqual(reopened.usage(3600)["generations"], 120)
        finally:
            reopened.db.close()

    async def test_pacing_uses_persisted_generation_time(self):
        identifier = provider.app.state.ledger.reserve("target", True, 100)
        provider.app.state.ledger.finish(identifier, "interrupted")
        sleeps = []
        async def capture_sleep(seconds):
            sleeps.append(seconds)
        with patch.object(provider.asyncio, "sleep", capture_sleep):
            await provider.forward("v1/chat/completions", self.req())
        self.assertEqual(len(sleeps), 1)
        self.assertGreater(sleeps[0], 4)
        self.assertLessEqual(sleeps[0], 5)

    async def test_model_discovery_is_cached_filtered_and_does_not_generate(self):
        provider.app.state.session = FakeClient([Reply(200, {'data':[
            {'id':'fake-model'}, {'id':'second/model'}, {'id':'<script>'}, {'id':'fake-model'}]})])
        first=await provider.models(self.req())
        second=await provider.models(self.req())
        self.assertEqual([m['id'] for m in first['models']], ['fake-model','second/model'])
        self.assertEqual(first,second)
        self.assertEqual(len(provider.app.state.session.calls),1)
        method,url,kwargs=provider.app.state.session.calls[0]
        self.assertEqual((method,url),('GET','https://model.example/v1/models'))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(provider.app.state.ledger.usage(3600)['requests'],0)

    async def test_settings_only_accept_advertised_models_and_survive_restart(self):
        provider.app.state.session = FakeClient([Reply(200, {'data':[{'id':'fake-model'},{'id':'second-model'}]})])
        with self.assertRaises(HTTPException):
            await provider.configure(request(body={'model':'second-model','concurrency':2}))
        for body in ({'model':'fake-model','concurrency':True},{'model':'fake-model','concurrency':5},
                     {'model':'missing-model','concurrency':2}):
            with self.assertRaises(HTTPException):await provider.configure(self.req(body))
        result=await provider.configure(self.req({'model':'second-model','concurrency':2}))
        self.assertEqual(result['settings'],{'model':'second-model','concurrency':2})
        with self.assertRaises(HTTPException):await provider.forward('tokenize',self.req())
        await provider.forward('tokenize',self.req({'model':'second-model'}))
        self.assertEqual(provider.app.state.ledger.db.execute('SELECT model FROM calls').fetchone()[0],'second-model')
        reopened=provider.Ledger(self.path)
        try:self.assertEqual(reopened.settings(),result['settings'])
        finally:reopened.db.close()

    async def test_configuration_rejects_active_requests_and_discovery_failure(self):
        provider.app.state.waiting=1
        with self.assertRaises(HTTPException) as error:
            await provider.configure(self.req({'model':'fake-model','concurrency':2}))
        self.assertEqual(error.exception.status_code,409)
        provider.app.state.waiting=0
        provider.app.state.session=FakeClient([Reply(503,{'secret':'not-to-display'})])
        catalog=await provider.models(self.req())
        self.assertIsNotNone(catalog['discovery_error'])
        self.assertNotIn('not-to-display',json.dumps(catalog))
        with self.assertRaises(HTTPException):
            await provider.configure(self.req({'model':'other-model','concurrency':2}))
        self.assertEqual(provider.app.state.ledger.settings(),{'model':'fake-model','concurrency':1})
        self.assertFalse(provider.app.state.configuring)

    async def test_concurrent_roles_share_slots_and_reservations(self):
        await provider.configure(self.req({'model':'fake-model','concurrency':2}))
        gates=[asyncio.Event() for _ in range(3)]
        replies=[Reply(gate=gate) for gate in gates]
        provider.app.state.session=FakeClient(replies)
        tasks=[asyncio.create_task(provider.forward('tokenize',self.req(headers={'X-Demo-Role':role})))
               for role in ('target','attacker','judge')]
        try:
            await asyncio.wait_for(replies[0].entered.wait(),1)
            await asyncio.wait_for(replies[1].entered.wait(),1)
            self.assertFalse(replies[2].entered.is_set())
            self.assertEqual(provider.app.state.ledger.usage(3600)['requests'],2)
            with self.assertRaises(HTTPException):
                await provider.configure(self.req({'model':'fake-model','concurrency':1}))
            gates[0].set()
            await asyncio.wait_for(replies[2].entered.wait(),1)
            gates[1].set();gates[2].set()
            await asyncio.gather(*tasks)
            self.assertEqual(provider.app.state.ledger.usage(3600)['requests'],3)
            self.assertEqual(provider.app.state.waiting,0)
        finally:
            for task in tasks:
                if not task.done():task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"AUDIENCE_GATEWAY_KEY": "internal-key", "APPLICATION_URL": "https://app.internal"})
        self.env.start()
        self.addCleanup(self.env.stop)
        gateway.app.state.client = FakeClient()

    async def test_public_allowlist_excludes_operator_and_raw_chat(self):
        for method, path in [("GET", "control"), ("GET", "api/control/state"), ("POST", "api/control/runs"), ("GET", "metrics"), ("POST", "api/chat"), ("DELETE", "api/audience/chat"), ("GET", "api/audience/session"), ("GET", "api/audience/../control")]:
            with self.subTest(method=method, path=path), self.assertRaises(HTTPException) as error:
                await gateway.forward(path, request(method=method))
            self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(gateway.app.state.client.calls, [])

    async def test_proxy_strips_authority_headers_and_disables_redirects(self):
        gateway.app.state.client = FakeClient([Reply(200, b"ok", {"Content-Type": "text/plain", "Set-Cookie": "lemonade_audience=fake; Secure; HttpOnly; SameSite=Strict"})])
        response = await gateway.forward("api/audience/session", request(headers={
            "Authorization": "Bearer operator-token", "X-Forwarded-Access-Token": "operator-token",
            "X-Audience-Gateway": "forged", "X-Demo-Role": "judge", "Origin": "https://audience.example",
            "Cookie": "lemonade_audience=old", "X-CSRF-Token": "csrf"}))
        _, url, kwargs = gateway.app.state.client.calls[0]
        headers = {k.lower(): v for k, v in kwargs["headers"].items()}
        self.assertEqual(url, "https://app.internal/api/audience/session")
        self.assertEqual(headers["x-audience-gateway"], "internal-key")
        self.assertNotIn("authorization", headers)
        self.assertNotIn("x-forwarded-access-token", headers)
        self.assertNotIn("x-demo-role", headers)
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("HttpOnly", response.headers["set-cookie"])

    async def test_large_public_payload_is_not_forwarded(self):
        with self.assertRaises(HTTPException) as error:
            await gateway.forward("api/audience/chat", request(body=b"x" * 2049))
        self.assertEqual(error.exception.status_code, 413)
        self.assertEqual(gateway.app.state.client.calls, [])

    def streaming_reply(self, gate, fail=False):
        class StreamReply(Reply):
            def __init__(self):
                super().__init__(200, headers={"Content-Type": "text/event-stream"})
                self.content = self
                self.closed = False

            async def read(self):
                raise AssertionError("The gateway must not buffer the whole SSE response")

            async def iter_any(self):
                yield b'data: {"type":"status","stage":"processing"}\n\n'
                await gate.wait()
                if fail:
                    raise gateway.aiohttp.ClientPayloadError("private upstream diagnostic")
                yield b'data: {"type":"validated"}\n\ndata: {"type":"chunk","content":"Lemonade."}\n\n'
                yield b'data: {"type":"done"}\n\n'

            async def __aexit__(self, *args):
                self.closed = True
        return StreamReply()

    async def test_sse_progress_reaches_client_before_checked_answer(self):
        gate, first = asyncio.Event(), asyncio.Event()
        upstream = self.streaming_reply(gate)
        gateway.app.state.client = FakeClient([upstream])
        response = await gateway.forward("api/audience/chat", request())
        self.assertNotIn("content-length", response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store, no-transform")
        messages = []
        async def send(message):
            messages.append(message)
            if message.get("body"): first.set()
        req = request()
        task = asyncio.create_task(response(req.scope, req.receive, send))
        try:
            await asyncio.wait_for(first.wait(), 1)
            self.assertIn(b'"status"', b''.join(m.get('body', b'') for m in messages))
            self.assertNotIn(b'Lemonade.', b''.join(m.get('body', b'') for m in messages))
            self.assertFalse(upstream.closed)
            gate.set()
            await task
            self.assertIn(b'Lemonade.', b''.join(m.get('body', b'') for m in messages))
            self.assertTrue(upstream.closed)
        finally:
            if not task.done():
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task

    async def test_sse_client_cancellation_closes_upstream(self):
        gate, first = asyncio.Event(), asyncio.Event()
        upstream = self.streaming_reply(gate)
        gateway.app.state.client = FakeClient([upstream])
        response = await gateway.forward("api/audience/chat", request())
        async def send(message):
            if message.get("body"): first.set()
        req = request()
        task = asyncio.create_task(response(req.scope, req.receive, send))
        await asyncio.wait_for(first.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(upstream.closed)

    async def test_sse_transport_failure_is_safe_error_not_policy_block(self):
        gate = asyncio.Event(); gate.set()
        upstream = self.streaming_reply(gate, fail=True)
        gateway.app.state.client = FakeClient([upstream])
        status, _, raw = await call(gateway.app, "/api/audience/chat", "POST", {"message": "Hello"})
        self.assertEqual(status, 200)
        self.assertIn(b'"outcome":"error"', raw)
        self.assertNotIn(b'"validated"', raw)
        self.assertNotIn(b'"done"', raw)
        self.assertNotIn(b'private upstream diagnostic', raw)
        self.assertTrue(upstream.closed)


class AudienceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "audience.sqlite")
        self.store = control.AudienceStore(self.path)
        self.addCleanup(self.store.db.close)

    def test_generic_window_hashed_sessions_and_revocation(self):
        with self.assertRaises(HTTPException):
            self.store.create("customer")
        self.store.window("open")
        token = self.store.create()
        row = self.store.session(token)
        self.assertEqual(row["persona"], "audience")
        self.assertEqual(row["id"], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(row["id"], token)
        self.store.window("close")
        with self.assertRaises(HTTPException):
            self.store.session(token)
        self.store.window("open")
        with self.assertRaises(HTTPException):
            self.store.begin(token)

    def test_per_session_minute_total_and_single_inflight_limits(self):
        self.store.window("open", 10)
        token = self.store.create("attacker")
        session, event = self.store.begin(token)
        with self.assertRaises(HTTPException):
            self.store.begin(token)
        self.store.finish(session, event, "blocked", .01)
        for _ in range(2):
            session, event = self.store.begin(token)
            self.store.finish(session, event, "allowed", .01)
        with self.assertRaises(HTTPException):
            self.store.begin(token)
        self.store.db.execute("UPDATE events SET started=started-61")
        self.store.db.commit()
        for _ in range(3):
            session, event = self.store.begin(token)
            self.store.finish(session, event, "allowed", .01)
        self.store.db.execute("UPDATE events SET started=started-61")
        self.store.db.commit()
        with self.assertRaises(HTTPException):
            self.store.begin(token)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events").fetchone()[0], 6)

    def test_shared_queue_and_event_allowance(self):
        self.store.window("open")
        active = []
        for _ in range(8):
            active.append(self.store.begin(self.store.create("customer")))
        with self.assertRaises(HTTPException):
            self.store.begin(self.store.create("customer"))
        for session, event in active:
            self.store.finish(session, event, "allowed", .01)
        for _ in range(52):
            session, event = self.store.begin(self.store.create("customer"))
            self.store.finish(session, event, "allowed", .01)
        with self.assertRaises(HTTPException):
            self.store.begin(self.store.create("customer"))
        self.assertEqual(self.store.state()["requests_used"], 60)

    def test_restart_closes_window_and_marks_unknown_work_as_error(self):
        self.store.window("open")
        self.store.begin(self.store.create("customer"))
        restarted = control.AudienceStore(self.path)
        try:
            self.assertFalse(restarted.state()["open"])
            self.assertEqual(restarted.db.execute("SELECT outcome FROM events").fetchone()[0], "error")
            self.assertEqual(restarted.pending, set())
        finally:
            restarted.db.close()


class Metrics:
    def __init__(self):
        self.started = []
        self.finished = []

    async def increment_request(self, source):
        self.started.append(source)

    async def finish_request(self, source, outcome):
        self.finished.append((source, outcome))


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {"DEMO_SESSION_SECRET": "fake-session-secret", "AUDIENCE_GATEWAY_KEY": "internal-key",
            "DEMO_DATA_DIR": self.directory.name, "OPERATOR_URL": "https://operator.example", "AUDIENCE_URL": "https://audience.example",
            "MODEL_API_KEY": "fake-provider-key", "PROVIDER_BUDGET_URL": "https://budget.internal"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.calls = []
        async def process(message, source):
            self.calls.append((message, source))
            if message == "blocked":
                yield {"type": "error", "detector_type": "policy", "content": "Blocked"}
            elif message == "error":
                yield {"type": "error", "content": "Provider unavailable"}
            else:
                yield {"type": "chunk", "content": "Lemonade."}
                yield {"type": "done"}
        self.core = SimpleNamespace(SYSTEM_PROMPT="Lemonade policy", ALL_REGEX_PATTERNS=[], HAP_LOCAL_PATTERNS=[],
            VLLM_MODEL="fake-model", MAX_INPUT_CHARS=100, MAX_OUTPUT_TOKENS=128, request_slots=asyncio.Semaphore(1),
            metrics=Metrics(), process_chat=process)
        self.app = FastAPI()
        self.control = control.DemoControl(self.app, self.core)
        class ConfigClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.settings={"model":"fake-model","concurrency":1}
                self.unavailable=False
            def request(self,method,url,**kwargs):
                if url.endswith(("/budget","/models","/budget/settings")):
                    self.calls.append((method,url,kwargs))
                    if self.unavailable:return Reply(503,{})
                    if url.endswith('/models'):
                        return Reply(200,{"models":[{"id":"fake-model"},{"id":"other-model"}],"selected_model":self.settings['model'],"discovery_error":None})
                    if url.endswith('/budget/settings'):
                        if kwargs['json']['model'] not in ('fake-model','other-model'):return Reply(400,{})
                        self.settings=dict(kwargs['json'])
                    return Reply(200,{"settings":dict(self.settings),"paused":"","concurrency":self.settings['concurrency']})
                return super().request(method,url,**kwargs)
        self.control.client = ConfigClient()

    async def asyncTearDown(self):
        await self.control.shutdown()

    def operator_headers(self, token="operator-token"):
        return {"X-Forwarded-Access-Token": token, "Origin": "https://operator.example",
                "X-CSRF-Token": self.control.csrf(hashlib.sha256(token.encode()).hexdigest())}

    async def test_read_and_execute_permissions_are_separate_and_fail_closed(self):
        status, _, _ = await call(self.app, "/api/control/state")
        self.assertEqual(status, 401)
        status, _, raw = await call(self.app, "/api/control/state", headers=self.operator_headers("reader-token"))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["permissions"]["can_execute"])
        status, _, _ = await call(self.app, "/api/control/audience", "POST", {"action": "open"}, self.operator_headers("reader-token"))
        self.assertEqual(status, 403)
        self.assertFalse(self.control.audience.state()["open"])
        self.control.client = FakeClient([Reply(500, {"status": {"allowed": True}})])
        with self.assertRaises(HTTPException):
            await self.control.permission(request(headers={"X-Forwarded-Access-Token": "unseen-token"}))

    async def test_mutations_require_csrf_and_same_origin(self):
        valid = self.operator_headers()
        for headers in [{k: v for k, v in valid.items() if k != "X-CSRF-Token"}, {**valid, "X-CSRF-Token": "wrong"}, {**valid, "Origin": "https://attacker.example"}]:
            status, _, _ = await call(self.app, "/api/control/audience", "POST", {"action": "open"}, headers)
            self.assertEqual(status, 403)
        status, _, _ = await call(self.app, "/api/control/audience", "POST", {"action": "open"}, valid)
        self.assertEqual(status, 200)
        self.assertTrue(self.control.audience.state()["open"])

    async def audience_headers(self):
        headers = {"X-Audience-Gateway": "internal-key", "Origin": "https://audience.example"}
        self.control.audience.window("open")
        status, response_headers, raw = await call(self.app, "/api/audience/session", "POST", {}, headers)
        self.assertEqual(status, 200)
        cookie = response_headers[b"set-cookie"].decode()
        for flag in ["HttpOnly", "Secure", "SameSite=strict"]:
            self.assertIn(flag, cookie)
        headers["Cookie"] = cookie.split(";", 1)[0]
        self.assertNotIn("persona", json.loads(raw))
        headers["X-CSRF-Token"] = json.loads(raw)["csrf_token"]
        return headers

    async def test_generic_session_role_switches_preserve_cookie_quota_and_guarded_path(self):
        headers = await self.audience_headers()
        csrf = headers.pop("X-CSRF-Token")
        status, _, _ = await call(self.app, "/api/audience/chat", "POST", {"message": "Hello"}, headers)
        self.assertEqual(status, 403)
        headers["X-CSRF-Token"] = csrf
        status, _, raw3 = await call(self.app, "/api/audience/chat", "POST", {"message": "Hello", "source": "automation"}, headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Lemonade.", raw3)
        for persona in ("customer", "attacker", "operator", None):
            status, response_headers, raw = await call(self.app, "/api/audience/session", "POST", {"persona": persona}, headers)
            self.assertEqual(status, 200)
            self.assertEqual(response_headers[b"set-cookie"].decode().split(";", 1)[0], headers["Cookie"])
            self.assertEqual(json.loads(raw)["remaining_requests"], 5)
            self.assertEqual(json.loads(raw)["csrf_token"], csrf)
        self.assertEqual(self.control.audience.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
        self.assertEqual(self.control.audience.db.execute("SELECT persona FROM sessions").fetchone()[0], "audience")
        status, _, raw = await call(self.app, "/api/audience/state", headers=headers)
        self.assertEqual(json.loads(raw)["remaining_requests"], 5)
        await self.control.evaluate("Hello", "forged", "fake-run")
        self.assertEqual(self.calls, [("Hello", "audience_chat"), ("Hello", "automation")])
        self.assertEqual(self.core.metrics.finished, [("audience_chat", "allowed"), ("automation", "allowed")])

    async def test_existing_legacy_sessions_and_historical_labels_are_preserved(self):
        headers = await self.audience_headers()
        self.control.audience.db.execute("UPDATE sessions SET persona='customer'")
        self.control.audience.db.commit()
        status, _, _ = await call(self.app, "/api/audience/chat", "POST", {"message": "Hello"}, headers)
        self.assertEqual(status, 200)
        status, response_headers, raw = await call(self.app, "/api/audience/session", "POST", {}, headers)
        self.assertEqual(status, 200)
        self.assertEqual(response_headers[b"set-cookie"].decode().split(";", 1)[0], headers["Cookie"])
        self.assertEqual(json.loads(raw)["remaining_requests"], 5)
        self.assertEqual(self.control.audience.db.execute("SELECT persona FROM sessions").fetchone()[0], "customer")
        self.assertEqual(self.control.audience.summary()["customer"]["allowed"], 1)
        self.assertEqual(self.calls[-1][1], "audience_chat")

    @staticmethod
    def frames(raw):
        if isinstance(raw, str):raw = raw.encode()
        return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith(b"data: ")]

    async def test_progress_and_heartbeat_precede_validation_without_content_leak(self):
        headers = await self.audience_headers()
        release = asyncio.Event()
        entered = asyncio.Event()
        content = "Checked lemonade answer. " * 30
        async def delayed(message, source):
            yield {"type": "chunk", "content": content}
            entered.set()
            await release.wait()
            yield {"type": "done"}
        self.core.process_chat = delayed
        req = request("/api/audience/chat", "POST", {"message": "Hello"}, headers)
        chunks = []
        heartbeat = asyncio.Event()
        async def send(item):
            if item["type"] == "http.response.body":
                chunks.append(item.get("body", b""))
                if b'"heartbeat"' in chunks[-1]:heartbeat.set()
        with patch.object(control, "STREAM_HEARTBEAT_SECONDS", .005):
            task = asyncio.create_task(self.app(req.scope, req.receive, send))
            try:
                await asyncio.wait_for(entered.wait(), 1)
                await asyncio.wait_for(heartbeat.wait(), 1)
                before = self.frames(b"".join(chunks))
                self.assertEqual(before[0]["type"], "status")
                self.assertTrue(all(f["type"] in {"status", "heartbeat"} for f in before))
                self.assertNotIn(content.encode(), b"".join(chunks))
                release.set()
                await task
            finally:
                if not task.done():task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        frames = self.frames(b"".join(chunks))
        validated = next(i for i, f in enumerate(frames) if f["type"] == "validated")
        checked_chunks = [(i, f["content"]) for i, f in enumerate(frames) if f["type"] == "chunk"]
        self.assertTrue(all(i > validated and len(text) <= control.STREAM_CHUNK_CHARS for i, text in checked_chunks))
        self.assertEqual("".join(text for _, text in checked_chunks), content)
        self.assertEqual(frames[-1], {"type": "done", "outcome": "allowed", "remaining_requests": 5})

    async def test_blocked_truncated_and_failed_core_never_release_partial_content(self):
        headers = await self.audience_headers()
        for scenario, expected in [("blocked", "blocked"), ("truncated", "error"), ("failed", "error")]:
            async def failing(message, source):
                yield {"type": "chunk", "content": "UNCHECKED PRIVATE CONTENT"}
                if scenario == "blocked":
                    yield {"type": "error", "message": "Policy blocked", "detector_type": "policy"}
                    # An inconsistent terminal marker must not undo a failure.
                    yield {"type": "done"}
                elif scenario == "failed":
                    raise RuntimeError("SECRET EXCEPTION DETAIL")
            self.core.process_chat = failing
            status, _, raw = await call(self.app, "/api/audience/chat", "POST", {"message": scenario}, headers)
            self.assertEqual(status, 200)
            frames = self.frames(raw)
            self.assertEqual(frames[-1]["type"], "error")
            self.assertEqual(frames[-1]["outcome"], expected)
            self.assertFalse(any(f["type"] in {"chunk", "validated", "done"} for f in frames))
            self.assertNotIn(b"UNCHECKED", raw)
            self.assertNotIn(b"SECRET", raw)
        self.assertEqual(self.core.metrics.finished, [("audience_chat", "blocked"), ("audience_chat", "error"), ("audience_chat", "error")])
        rows = self.control.audience.db.execute("SELECT outcome FROM events ORDER BY id").fetchall()
        self.assertEqual([r[0] for r in rows], ["blocked", "error", "error"])

    async def test_audience_disconnect_cancels_inflight_and_finalizes_once(self):
        headers = await self.audience_headers()
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def slow(message, source):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            yield {"type": "done"}
        self.core.process_chat = slow
        task = asyncio.create_task(call(self.app, "/api/audience/chat", "POST", {"message": "Hello"}, headers))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(cancelled.is_set())
        self.assertEqual(self.core.metrics.started, ["audience_chat"])
        self.assertEqual(self.core.metrics.finished, [("audience_chat", "cancelled")])
        self.assertEqual(self.control.audience.pending, set())
        self.assertEqual(self.control.audience.db.execute("SELECT outcome FROM events").fetchone()[0], "cancelled")

    async def test_disconnect_before_stream_start_finalizes_reserved_event(self):
        headers = await self.audience_headers()
        req = request("/api/audience/chat", "POST", {"message": "Hello"}, headers)
        async def send(item):
            if item["type"] == "http.response.start":raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.app(req.scope, req.receive, send)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.control.audience.pending, set())
        self.assertEqual(self.control.audience.db.execute("SELECT outcome FROM events").fetchone()[0], "cancelled")
        self.assertEqual(self.core.metrics.started, ["audience_chat"])
        self.assertEqual(self.core.metrics.finished, [("audience_chat", "cancelled")])

    async def test_disconnect_after_validated_result_preserves_allowed_outcome(self):
        headers = await self.audience_headers()
        req = request("/api/audience/chat", "POST", {"message": "Hello"}, headers)
        async def send(item):
            if item["type"] == "http.response.body" and b'"validated"' in item.get("body", b""):
                raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.app(req.scope, req.receive, send)
        self.assertEqual(self.control.audience.db.execute("SELECT outcome FROM events").fetchone()[0], "allowed")
        self.assertEqual(self.control.audience.pending, set())
        self.assertEqual(self.core.metrics.finished, [("audience_chat", "allowed")])

    async def test_gateway_key_and_origin_are_required_for_public_backend(self):
        for headers in [{}, {"X-Audience-Gateway": "wrong"}, {"X-Audience-Gateway": "internal-key", "Origin": "https://attacker.example"}]:
            status, _, _ = await call(self.app, "/api/audience/state", headers=headers)
            self.assertEqual(status, 403)

    async def test_long_idempotency_key_repeated_start_does_not_duplicate(self):
        body = {"profile": "functional", "idempotency_key": "x" * 128}
        first, _, raw = await call(self.app, "/api/control/runs", "POST", body, self.operator_headers())
        second, _, raw2 = await call(self.app, "/api/control/runs", "POST", body, self.operator_headers())
        self.assertEqual((first, second), (200, 200))
        self.assertEqual(json.loads(raw)["id"], json.loads(raw2)["id"])
        self.assertEqual(len(self.control.engine.list()), 1)

    async def test_errors_are_not_blocks_and_cancellation_finalizes_once(self):
        self.assertEqual((await self.control.execute("blocked", "automation"))["outcome"], "blocked")
        self.assertEqual((await self.control.execute("error", "automation"))["outcome"], "error")
        entered = asyncio.Event()
        async def slow(message, source):
            entered.set()
            await asyncio.Event().wait()
            yield {"type": "done"}
        self.core.process_chat = slow
        task = asyncio.create_task(self.control.execute("Hi", "presenter"))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.control.presenter_waiting, 0)
        self.assertEqual(self.core.metrics.finished, [("automation", "blocked"), ("automation", "error"), ("presenter", "cancelled")])

    async def test_presenter_completion_preserves_other_waiting_presenter(self):
        first_entered, first_release, second_entered, second_release = (asyncio.Event() for _ in range(4))
        async def slow(message, source):
            entered, release = (first_entered, first_release) if message == "first" else (second_entered, second_release)
            entered.set()
            await release.wait()
            yield {"type": "done"}
        self.core.process_chat = slow
        first = asyncio.create_task(self.control.execute("first", "presenter"))
        await first_entered.wait()
        second = asyncio.create_task(self.control.execute("second", "presenter"))
        await asyncio.sleep(0)
        self.assertEqual(self.control.presenter_waiting, 1)
        first_release.set()
        await first
        await second_entered.wait()
        self.assertEqual(self.control.presenter_waiting, 0)
        second_release.set()
        await second
        self.assertEqual(len(self.core.metrics.finished), 2)

    async def test_model_settings_apply_to_all_roles_and_recover_from_provider_state(self):
        status,_,raw=await call(self.app,"/api/control/settings",headers=self.operator_headers())
        self.assertEqual(status,200)
        self.assertEqual([model['id'] for model in json.loads(raw)['models']],['fake-model','other-model'])
        original_policy=self.control.policy()['id']
        status,_,raw=await call(self.app,"/api/control/settings","POST",{'model':'other-model','concurrency':3},self.operator_headers())
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['settings'],{'model':'other-model','concurrency':3})
        self.assertEqual(self.core.VLLM_MODEL,'other-model')
        self.assertEqual(self.core.request_slots._value,3)
        self.assertNotEqual(self.control.policy()['id'],original_policy)
        await self.control.generate('judge',{'task':'Review fixture'},96,'fake-run')
        completion=next(c for c in reversed(self.control.client.calls) if c[1].endswith('/v1/chat/completions'))
        self.assertEqual(completion[2]['json']['model'],'other-model')
        fresh_core=SimpleNamespace(**vars(self.core))
        fresh_core.VLLM_MODEL='stale-environment-model'
        fresh=control.DemoControl(FastAPI(),fresh_core)
        fresh.client=self.control.client
        try:
            async with fresh.config_lock:await fresh.sync_settings()
            self.assertEqual(fresh_core.VLLM_MODEL,'other-model')
            self.assertEqual(fresh.settings['concurrency'],3)
        finally:await fresh.shutdown()

    async def test_settings_reject_open_audience_active_campaign_and_active_request(self):
        headers=self.operator_headers()
        change={'model':'other-model','concurrency':2}
        self.control.audience.window('open')
        status,_,_=await call(self.app,'/api/control/settings','POST',change,headers)
        self.assertEqual(status,409)
        self.control.audience.window('close')
        entered,release=asyncio.Event(),asyncio.Event()
        async def slow(message,source):
            entered.set()
            await release.wait()
            yield {'type':'done'}
        self.core.process_chat=slow
        presenter=asyncio.create_task(self.control.execute('Hello','presenter'))
        await entered.wait()
        status,_,_=await call(self.app,'/api/control/settings','POST',change,headers)
        self.assertEqual(status,409)
        release.set();await presenter
        entered.clear();release.clear()
        status,_,raw=await call(self.app,'/api/control/runs','POST',{'profile':'functional','idempotency_key':'active-settings-test'},headers)
        self.assertEqual(status,200)
        run_id=json.loads(raw)['id']
        await entered.wait()
        await self.control.engine.pause(run_id)
        status,_,_=await call(self.app,'/api/control/settings','POST',change,headers)
        self.assertEqual(status,409)
        await self.control.engine.stop(run_id)
        self.assertFalse(any(c[1].endswith('/budget/settings') for c in self.control.client.calls))

    async def test_unavailable_provider_settings_fail_closed_before_target(self):
        self.control.client.unavailable=True
        with self.assertRaises(HTTPException) as error:
            await self.control.execute('Hello','presenter')
        self.assertEqual(error.exception.status_code,503)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.control.application_inflight,0)
        self.assertEqual(self.control.presenter_waiting,0)
        status,_,_=await call(self.app,'/api/control/runs','POST',{'profile':'functional','idempotency_key':'unavailable-start'},self.operator_headers())
        self.assertEqual(status,503)
        self.assertEqual(self.control.engine.list(),[])
        self.control.client.unavailable=False
        result=await self.control.execute('Hello','presenter')
        self.assertEqual(result['outcome'],'allowed')

    async def test_saved_profiles_are_durable_immutable_revisions_with_run_snapshot(self):
        headers=self.operator_headers()
        body={'name':'Stage checks','profile':'functional','options':{'case_ids':['topic-apples'],'max_seconds':45}}
        status,_,raw=await call(self.app,'/api/control/profiles','POST',body,headers)
        self.assertEqual(status,200)
        first=json.loads(raw)
        body['options']={'case_ids':['instruction-marker'],'max_seconds':60}
        status,_,raw=await call(self.app,'/api/control/profiles','POST',body,headers)
        second=json.loads(raw)
        self.assertEqual(second['revision'],2)
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(next(p for p in self.control.profiles() if p['id']==first['id'])['options']['max_seconds'],45)
        status,_,raw=await call(self.app,'/api/control/runs','POST',{'profile_id':first['id'],'idempotency_key':'saved-profile-start'},headers)
        self.assertEqual(status,200)
        run=json.loads(raw)
        for _ in range(100):
            run=self.control.engine.get(run['id'])
            if run['status']=='completed':break
            await asyncio.sleep(.001)
        self.assertEqual(run['status'],'completed')
        self.assertEqual(run['profile_definition']['id'],first['id'])
        self.assertEqual(run['budget']['max_attempts'],3)
        self.assertEqual(run['budget']['max_seconds'],45)
        fresh=control.DemoControl(FastAPI(),self.core)
        fresh.client=self.control.client
        try:
            saved=next(p for p in fresh.profiles() if p['id']==first['id'])
            self.assertEqual(saved,first)
            self.assertEqual(fresh.engine.get(run['id'])['profile_definition'],run['profile_definition'])
        finally:await fresh.shutdown()

    async def test_configuration_lock_prevents_model_change_racing_admission(self):
        headers=self.operator_headers()
        entered,release=asyncio.Event(),asyncio.Event()
        original_provider=self.control.provider
        async def provider_call(path,body=None,role=None):
            if path=='/budget/settings':
                entered.set()
                await release.wait()
            return await original_provider(path,body,role)
        self.control.provider=provider_call
        change=asyncio.create_task(call(self.app,'/api/control/settings','POST',{'model':'other-model','concurrency':2},headers))
        await entered.wait()
        target=asyncio.create_task(self.control.execute('Hello','presenter'))
        await asyncio.sleep(0)
        self.assertEqual(self.calls,[])
        release.set()
        self.assertEqual((await change)[0],200)
        self.assertEqual((await target)['outcome'],'allowed')
        self.assertEqual(self.core.VLLM_MODEL,'other-model')
        self.assertEqual(self.control.application_inflight,0)

    async def test_profile_and_settings_mutations_require_permission_csrf_and_safe_fields(self):
        for path,body in [('/api/control/profiles',{'name':'Example','profile':'adaptive','options':{}}),('/api/control/settings',{'model':'other-model','concurrency':2})]:
            status,_,_=await call(self.app,path,'POST',body,self.operator_headers('reader-token'))
            self.assertEqual(status,403)
            headers=self.operator_headers();headers.pop('X-CSRF-Token')
            status,_,_=await call(self.app,path,'POST',body,headers)
            self.assertEqual(status,403)
        for body in [{'model':'other-model','concurrency':True},{'model':'other-model','concurrency':5},{'model':'unadvertised','concurrency':2}]:
            status,_,_=await call(self.app,'/api/control/settings','POST',body,self.operator_headers())
            self.assertEqual(status,400)
        status,_,_=await call(self.app,'/api/control/profiles','POST',{'name':'Unsafe','profile':'adaptive','options':{'system_prompt':'Override'}},self.operator_headers())
        self.assertEqual(status,400)


if __name__ == "__main__":
    unittest.main()
