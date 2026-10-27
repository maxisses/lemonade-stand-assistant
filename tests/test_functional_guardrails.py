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
    async def json(self):
        result = next(self.lines)
        if isinstance(result, Exception): raise result
        return result


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

    async def run_unary(self, body):
        with patch.object(app, 'ORCHESTRATOR_STREAMING', False):
            return await self.run_stream([body])

    async def test_complete_unary_response_is_released(self):
        events, session = await self.run_unary({'choices':[{'message':{'content':'Fresh lemonade.'},'finish_reason':'stop'}]})
        self.assertFalse(session.payload['stream'])
        self.assertEqual([e['content'] for e in events if e['type']=='chunk'], ['Fresh lemonade.'])
        self.assertEqual(events[-1]['type'], 'done')

    async def test_unary_output_detection_discards_content(self):
        body = {'choices':[{'message':{'content':'Must remain hidden.'},'finish_reason':'stop'}], 'warnings':[{'type':'UNSUITABLE_OUTPUT'}]}
        events, _ = await self.run_unary(body)
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'policy')

    async def test_unary_input_detection_without_choices_is_a_block(self):
        events, _ = await self.run_unary({'warnings':[{'type':'UNSUITABLE_INPUT'}]})
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'policy')

    async def test_unary_failures_and_incomplete_content_are_not_released(self):
        bodies = [ConnectionError('Transport failed'), {}, {'choices':[{'message':{'content':'Buffered.'}}]}, {'choices':[{'message':{'reasoning_content':'Private.'},'finish_reason':'length'}]}]
        for body in bodies:
            with self.subTest(body=type(body).__name__):
                events, _ = await self.run_unary(body)
                self.assertFalse(any(e['type']=='chunk' for e in events))
                self.assertEqual(events[-1]['type'], 'error')

    async def test_unary_local_output_policy_is_enforced(self):
        events, _ = await self.run_unary({'choices':[{'message':{'content':'Try oranges.'},'finish_reason':'stop'}]})
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'regex')

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

    async def test_sse_fields_without_optional_space_are_processed(self):
        lines = [chunk('Fresh lemonade.'), chunk(finish='stop'), 'data: [DONE]\n']
        events, _ = await self.run_stream([line.replace('data: ', 'data:', 1) for line in lines])
        self.assertEqual([e['content'] for e in events if e['type']=='chunk'], ['Fresh lemonade.'])
        self.assertEqual(events[-1]['type'], 'done')

    async def test_server_template_options_forwarded_without_exposing_reasoning(self):
        lines = ['data:'+json.dumps({'choices':[{'delta':{'reasoning_content':'Private intermediate text'}}]})+'\n', chunk('Fresh lemonade.'), chunk(finish='stop'), 'data:[DONE]\n']
        with patch.object(app, 'MODEL_CHAT_TEMPLATE_KWARGS', {'enable_thinking': False}):
            events, session = await self.run_stream(lines)
        self.assertEqual(session.payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual([e['content'] for e in events if e['type']=='chunk'], ['Fresh lemonade.'])

    async def test_unspaced_late_block_after_finish_discards_content(self):
        blocked = {'warnings':[{'type':'UNSUITABLE_OUTPUT'}]}
        events, _ = await self.run_stream([chunk('Buffered text.'), chunk(finish='stop'), 'data:'+json.dumps(blocked)+'\n', 'data:[DONE]\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1].get('detector_type'), 'policy')

    async def test_finish_without_completion_marker_is_not_released(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), chunk(finish='stop')])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

    async def test_transport_failure_after_terminal_frame_discards_content(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), chunk(finish='stop'), 'data:[DONE]\n', ConnectionError('Interrupted transport')])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

    async def test_unspaced_error_event_discards_content(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), 'event:error\n'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

    async def test_incomplete_final_frame_is_not_ignored(self):
        events, _ = await self.run_stream([chunk('Buffered text.'), chunk(finish='stop'), 'data:[DONE]\n', 'data:{'])
        self.assertFalse(any(e['type']=='chunk' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

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

class OutcomeTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, process, busy=False, message='Lemonade please.'):
        collector = app.AsyncMetricsCollector()
        slots = asyncio.Semaphore(1)
        if busy: await slots.acquire()
        with patch.object(app, 'metrics', collector), patch.object(app, 'process_chat', process), patch.object(app, 'request_slots', slots):
            request = Request({'type':'http', 'headers':[(b'x-source', b'fake'), (b'x-mode', b'baseline')]})
            response = await app.chat(app.ChatRequest(message=message), request)
            events = [event async for event in response.body_iterator]
        data = collector._sources['presenter']
        self.assertEqual(data['total_requests'], 1)
        self.assertEqual(data['active_requests'], 0)
        self.assertEqual(sum(data['outcomes'].values()), 1)
        self.assertIn('mode="protected"', await collector.get_prometheus_metrics())
        return data

    async def test_several_detector_hits_count_as_one_block(self):
        async def process(message, source):
            await app.metrics.add_detections([{'results':[{'detector_id':'hap'},{'detector_id':'language_detection'}]}], 'input', source)
            yield {'type':'error', 'detector_type':'hap'}
        data = await self.request(process)
        self.assertEqual(data['outcomes']['blocked'], 1)
        self.assertEqual(sum(d['input'] for d in data['detections'].values()), 2)

    async def test_service_failure_is_not_a_policy_block(self):
        async def process(message, source):
            yield {'type':'error', 'detector_type':'error'}
        data = await self.request(process)
        self.assertEqual(data['outcomes']['error'], 1)
        self.assertEqual(data['outcomes']['blocked'], 0)

    async def test_completed_request_counts_once(self):
        async def process(message, source):
            yield {'type':'chunk', 'content':'Lemonade.'}
            yield {'type':'done'}
        data = await self.request(process)
        self.assertEqual(data['outcomes']['allowed'], 1)

    async def test_busy_request_is_rejected_before_processing(self):
        async def process(message, source):
            raise AssertionError('Busy request reached processing')
            yield
        data = await self.request(process, busy=True)
        self.assertEqual(data['outcomes']['rejected'], 1)

    async def test_length_limit_is_rejected_not_blocked(self):
        data = await self.request(app.process_chat, message='a' * (app.MAX_INPUT_CHARS + 1))
        self.assertEqual(data['outcomes']['rejected'], 1)

    async def test_disconnected_request_leaves_one_error_and_no_pending_request(self):
        collector = app.AsyncMetricsCollector()
        async def process(message, source):
            yield {'type':'chunk', 'content':'Buffered test.'}
            yield {'type':'done'}
        with patch.object(app, 'metrics', collector), patch.object(app, 'process_chat', process), patch.object(app, 'request_slots', asyncio.Semaphore(1)):
            response = await app.chat(app.ChatRequest(message='Lemonade.'), Request({'type':'http', 'headers':[]}))
            await anext(response.body_iterator)
            self.assertEqual(collector._sources['presenter']['active_requests'], 1)
            await response.body_iterator.aclose()
        data = collector._sources['presenter']
        self.assertEqual(data['outcomes'], {'allowed':0,'blocked':0,'error':1,'rejected':0})
        self.assertEqual(data['active_requests'], 0)

if __name__ == '__main__': unittest.main()
