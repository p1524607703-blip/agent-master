"""Controlled upstream streams: no model calls or database needed."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.background import BackgroundTask
from app.core import observability as trace
from app.core.config import settings
from app.services import codex_telemetry as relay


def event(kind='response.completed'):
    response = {'id':'synthetic-response','status':kind.split('.')[-1],
                'usage':{'input_tokens':2,'output_tokens':3,'total_tokens':5}}
    return ('data: '+json.dumps({'type':kind,'response':response})+'\n\n').encode()


class Source(httpx.AsyncByteStream):
    def __init__(self, chunks, error=None):
        self.chunks, self.error, self.closed = chunks, error, False
    async def __aiter__(self):
        for chunk in self.chunks: yield chunk
        if self.error: raise self.error
    async def aclose(self): self.closed = True


class StreamOutcomeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(settings,'codex_event_spool_dir',self.tmp))
        self.stack.enter_context(patch.object(relay,'upstream',return_value=('http://127.0.0.1/v1',{})))
        self.flush = self.stack.enter_context(patch.object(relay,'flush_events',new=AsyncMock()))
        self.device = {'device_id':uuid.uuid4(),'user_id':1}
        self.context = {'request_id':'safe-proxy-request'}
        self.calls = []

    def mock_source(self, chunks, error=None):
        self.source = Source(chunks,error)
        def handler(request):
            self.calls.append(request)
            return httpx.Response(200,headers={'content-type':'text/event-stream',
                'x-upstream-request-id':'safe-upstream-id'},stream=self.source)
        original = httpx.AsyncClient
        self.stack.enter_context(patch.object(relay.httpx,'AsyncClient',side_effect=lambda **kw:
            original(transport=httpx.MockTransport(handler),**kw)))

    async def consume(self):
        trace.request_context.set(self.context)
        headers = {}
        _,_,rid,stream = await relay.proxy_response(self.device,b'{"model":"synthetic"}',response_headers=headers)
        body = b''.join([chunk async for chunk in stream])
        await stream.aclose()
        paths = list(Path(self.tmp).glob('*.json'))
        self.assertEqual(len(paths),1)
        self.assertEqual(self.flush.await_count,1)
        self.assertEqual(len(self.calls),1)  # Never replay partial or failed output.
        self.assertEqual(headers['X-Model-Request-ID'],rid)
        self.assertEqual(self.calls[0].headers['x-request-id'],rid)
        self.assertEqual(self.context['model_request_id'],rid)
        self.assertEqual(self.context['model_upstream_request_id'],'safe-upstream-id')
        self.assertTrue(self.source.closed)
        self.assertEqual(list((Path(self.tmp)/'control'/'leases').glob('*.json')),[])
        return body,json.loads(paths[0].read_text())

    async def test_complete_stream_records_first_output_and_one_terminal_accounting(self):
        self.mock_source([b'data: {"type":"response.output_text.delta","delta":"private output"}\n\n',event()])
        body,record = await self.consume()
        self.assertNotIn(b'event: error',body)
        self.assertEqual((record['http_status'],record['completed'],record['model_outcome']),(200,True,'completed'))
        self.assertEqual(record['usage']['total_tokens'],5)
        for field in ('model_headers_ms','model_first_byte_ms','model_first_output_ms','model_stream_ms'):
            self.assertGreaterEqual(record[field],0)
        self.assertNotIn('private output',json.dumps(record)+json.dumps(self.context))

    async def test_truncated_eof_explicitly_fails_without_fabricating_usage(self):
        self.mock_source([b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'])
        body,record = await self.consume()
        self.assertEqual(body.count(b'event: error'),1)
        self.assertIn(b'upstream_stream_interrupted',body)
        self.assertIn(b'safe-proxy-request',body)
        self.assertEqual((record['http_status'],record['completed'],record['model_outcome']),(502,False,'incomplete'))
        self.assertEqual(record['model_error_type'],'MissingTerminalEvent')
        self.assertIsNone(record['usage'])

    async def test_protocol_error_surfaces_failure_and_sanitizes_exception_message(self):
        self.mock_source([b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'],
                         httpx.RemoteProtocolError('secret upstream payload'))
        body,record = await self.consume()
        self.assertIn(b'event: error',body)
        self.assertEqual((record['http_status'],record['model_outcome'],record['model_error_type']),
                         (502,'transport_error','RemoteProtocolError'))
        self.assertNotIn('secret upstream payload',json.dumps(record)+json.dumps(self.context)+body.decode())

    async def test_idle_timeout_before_first_output_is_clear_and_not_retried(self):
        self.mock_source([],httpx.ReadTimeout('private timeout details'))
        body,record = await self.consume()
        self.assertIn(b'event: error',body)
        self.assertEqual(record['model_error_type'],'ReadTimeout')
        self.assertIsNone(record['model_first_byte_ms'])
        self.assertIsNone(record['model_first_output_ms'])

    async def test_large_valid_terminal_is_not_mistaken_for_truncation(self):
        final = {'id':'large-response','status':'completed','output':[{'text':'x'*(1024*1024+32)}],
                 'usage':{'input_tokens':2,'output_tokens':3,'total_tokens':5}}
        self.mock_source([('data: '+json.dumps({'type':'response.completed','response':final})+'\n\n').encode()])
        body,record = await self.consume()
        self.assertNotIn(b'event: error',body)
        self.assertTrue(record['completed'])
        self.assertEqual(record['usage']['total_tokens'],5)
        self.assertLess(len(json.dumps(record)),4096)

    async def test_client_closing_after_terminal_error_does_not_hide_source_failure(self):
        self.mock_source([b'data: {"type":"response.created"}\n\n'])
        _,_,_,stream = await relay.proxy_response(self.device,b'{}')
        await stream.__anext__()
        failure = await stream.__anext__()
        self.assertIn(b'event: error',failure)
        await stream.aclose()
        records = [json.loads(p.read_text()) for p in Path(self.tmp).glob('*.json')]
        self.assertEqual(len(records),1)
        self.assertEqual((records[0]['http_status'],records[0]['model_outcome'],records[0]['completed']),
                         (502,'incomplete',False))
        self.assertEqual(records[0]['model_error_type'],'MissingTerminalEvent')
        self.assertEqual(self.flush.await_count,1)

    async def test_upstream_incomplete_terminal_preserves_actual_usage_and_status(self):
        self.mock_source([event('response.incomplete')])
        body,record = await self.consume()
        self.assertNotIn(b'event: error',body)
        self.assertEqual((record['http_status'],record['model_outcome'],record['completed']),(200,'incomplete',False))
        self.assertEqual(record['usage']['total_tokens'],5)

    async def test_upstream_failed_terminal_is_not_replaced_with_another_failure(self):
        self.mock_source([event('response.failed')])
        body,record = await self.consume()
        self.assertNotIn(b'event: error',body)
        self.assertEqual(record['model_outcome'],'failed')
        self.assertFalse(record['completed'])

    async def test_complete_terminal_then_transport_failure_preserves_completion_and_usage(self):
        self.mock_source([event().rstrip(b'\n')],httpx.RemoteProtocolError('private'))
        body,record = await self.consume()
        self.assertNotIn(b'event: error',body)
        self.assertEqual((record['http_status'],record['model_outcome'],record['completed']),
                         (502,'completed_transport_error',True))
        self.assertEqual(record['usage']['total_tokens'],5)

    async def test_client_disconnect_stages_once_before_cleanup_and_releases_lease(self):
        self.mock_source([b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n',event()])
        _,_,_,stream = await relay.proxy_response(self.device,b'{}')
        await stream.__anext__()
        await stream.aclose()
        records = [json.loads(p.read_text()) for p in Path(self.tmp).glob('*.json')]
        self.assertEqual(len(records),1)
        self.assertEqual((records[0]['http_status'],records[0]['model_outcome'],records[0]['completed']),
                         (499,'client_cancelled',False))
        self.assertIsNone(records[0]['usage'])
        self.assertEqual(self.flush.await_count,1)
        self.assertEqual(list((Path(self.tmp)/'control'/'leases').glob('*.json')),[])


class ASGIStreamDiagnosticTests(unittest.TestCase):
    def test_http200_stream_has_explicit_failed_outcome_and_correlated_ids(self):
        records = []
        app = FastAPI()
        app.add_middleware(trace.RequestDiagnosticsMiddleware)
        @app.post('/model')
        async def model():
            headers = {}
            status,ctype,rid,stream = await relay.proxy_response(
                {'device_id':uuid.uuid4(),'user_id':1},b'{}',response_headers=headers)
            return StreamingResponse(stream,status_code=status,media_type=ctype,headers=headers,
                                     background=BackgroundTask(stream.aclose))
        original = httpx.AsyncClient
        source = Source([b'data: {"type":"response.created"}\n\n'],httpx.RemoteProtocolError('secret'))
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(settings,'codex_event_spool_dir',tmp))
            stack.enter_context(patch.object(relay,'upstream',return_value=('http://127.0.0.1/v1',{})))
            stack.enter_context(patch.object(relay,'flush_events',new=AsyncMock()))
            stack.enter_context(patch.object(trace,'emit_diagnostic',side_effect=lambda x:records.append(dict(x))))
            stack.enter_context(patch.object(relay.httpx,'AsyncClient',side_effect=lambda **kw:original(
                transport=httpx.MockTransport(lambda _:httpx.Response(200,headers={'content-type':'text/event-stream'},stream=source)),**kw)))
            with TestClient(app) as client: response = client.post('/model')
        self.assertEqual(response.status_code,200)  # Cannot change headers after partial output.
        self.assertIn('upstream_stream_interrupted',response.text)
        self.assertEqual(records[0]['status_code'],200)
        self.assertEqual(records[0]['model_http_status'],502)
        self.assertFalse(records[0]['model_completed'])
        self.assertEqual(records[0]['model_outcome'],'transport_error')
        self.assertEqual(records[0]['model_request_id'],response.headers['x-model-request-id'])
        self.assertEqual(records[0]['request_id'],response.headers['x-request-id'])
        self.assertEqual(records[0]['performance_class'],'model_stream')
        self.assertNotIn('secret',json.dumps(records))
