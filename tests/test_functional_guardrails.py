"""Offline regression checks; no provider or detector network requests are made."""
import asyncio
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from starlette.requests import Request

source = Path(__file__).resolve().parents[1] / 'chart/files/lemonade/app_fastapi.py'
spec = importlib.util.spec_from_file_location('lemonade_app', source)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def chunk(content=None, finish=None, **extra):
    choice = {'delta': {'content': content} if content is not None else {}, 'finish_reason': finish}
    return 'data: ' + json.dumps({'choices': [choice], **extra}) + '\n'


class FakeResponse:
    status = 200
    def __init__(self, lines):
        self.lines = iter(lines)
        self.content = self
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def readline(self):
        line = next(self.lines, b'')
        if isinstance(line, Exception): raise line
        return line.encode() if isinstance(line, str) else line


class FakeSession:
    def __init__(self, lines):
        self.lines, self.calls, self.payload = lines, 0, None
    def post(self, *args, **kwargs):
        self.calls += 1
        self.payload = kwargs['json']
        return FakeResponse(self.lines)


class GuardrailTests(unittest.IsolatedAsyncioTestCase):
    async def run_stream(self, lines, message='Tell me about lemonade.'):
        session = FakeSession(lines)
        with patch.object(app, 'aiohttp_session', session), patch.object(app, 'MAX_RETRIES', 0):
            events = [e async for e in app.process_chat(message, source='presenter')]
        return events, session

    async def test_valid_stream_is_released_once_after_completion(self):
        events, session = await self.run_stream([chunk('Fresh '), chunk('lemonade.'), chunk(finish='stop'), 'data: [DONE]\n'])
        self.assertEqual([e['content'] for e in events if e['type']=='chunk'], ['Fresh lemonade.'])
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(session.calls, 1)
        self.assertLessEqual(session.payload['max_tokens'], 128)

    async def test_competitor_split_across_chunks_never_reaches_client(self):
        events, _ = await self.run_stream([chunk('Try or'), chunk('anges.'), chunk(finish='stop'), 'data: [DONE]\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'regex')

    async def test_late_detector_block_discards_earlier_content(self):
        blocked = {'warnings':[{'type':'UNSUITABLE_OUTPUT'}], 'detections':{'output':[{'results':[{'detector_id':'hap','score':1.0}]}]}}
        events, _ = await self.run_stream([chunk('Text that must remain buffered.'), 'data: '+json.dumps(blocked)+'\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'hap')

    async def test_block_without_detector_details_is_still_enforced(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), 'data: '+json.dumps({'warnings':[{'type':'UNSUITABLE_OUTPUT'}]})+'\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'policy')

    async def test_interrupted_stream_is_an_error_and_is_not_retried(self):
        events, session = await self.run_stream([chunk('Incomplete text.')])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')
        self.assertEqual(session.calls, 1)

    async def test_error_event_does_not_release_partial_content(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), 'event: error\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

    async def test_local_policy_block_does_not_call_provider(self):
        events, session = await self.run_stream([], 'Tell me about oranges.')
        self.assertEqual(session.calls, 0)
        self.assertEqual(events[-1].get('detector_type'), 'regex')

    async def test_busy_request_does_not_queue_or_call_provider(self):
        with patch.object(app, 'request_slots', asyncio.Semaphore(1)):
            await app.request_slots.acquire()
            request = Request({'type':'http', 'headers':[]})
            response = await app.chat(app.ChatRequest(message='Lemonade please.'), request)
            result = [line async for line in response.body_iterator]
            self.assertIn('already running', ''.join(result))
            app.request_slots.release()

    async def test_client_cannot_invent_a_metrics_source(self):
        sources=[]
        async def fake_process(message, source):
            sources.append(source)
            yield {'type':'done'}
        with patch.object(app, 'process_chat', fake_process), patch.object(app, 'request_slots', asyncio.Semaphore(1)):
            request = Request({'type':'http', 'headers':[(b'x-source', b'arbitrary-unbounded-label')]})
            response = await app.chat(app.ChatRequest(message='Lemonade please.'), request)
            _ = [line async for line in response.body_iterator]
        self.assertEqual(sources, ['presenter'])

if __name__ == '__main__': unittest.main()
