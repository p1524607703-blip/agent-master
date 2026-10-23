import http.client
import importlib.util
import io
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[2]/'scripts/device-binding/device_connector.py'
spec=importlib.util.spec_from_file_location('bound_connector',path)
connector=importlib.util.module_from_spec(spec);spec.loader.exec_module(connector)


class Reply:
    status=200
    def __init__(self): self.body=io.BytesIO(b'data: {"type":"response.completed"}\n\n')
    def getheader(self,name): return 'text/event-stream' if name=='Content-Type' else None
    def read1(self,size): return self.body.read(size)


class Connection:
    def close(self): pass


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.server=connector.LocalServer(('127.0.0.1',0),connector.Handler)
        self.server.config={'localKey':'fixture-local','apiKey':'fixture-server','baseUrl':'https://example.test/api/codex/v1'}
        self.server.slots=threading.BoundedSemaphore(1)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,method='GET',path='/v1/models',body=None,**extra):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={'Authorization':'Bearer fixture-local',**extra}
        conn.request(method,path,body=body,headers=headers)
        response=conn.getresponse(); status=response.status; raw=response.read();conn.close()
        return status,raw

    def test_local_origin_host_credential_and_path_boundaries(self):
        with patch.object(connector,'open_upstream') as upstream:
            for kwargs,expected in [({'Origin':'http://evil.test'},403),({'Host':'evil.test'},403),
                                    ({'Authorization':'Bearer fixture-server'},401)]:
                self.assertEqual(self.request(**kwargs)[0],expected)
            self.assertEqual(self.request(path='/v1/models?x=1')[0],404)
            self.assertEqual(self.request(method='POST',path='/v1/responses',body=b'{}',**{'Transfer-Encoding':'chunked'})[0],413)
            upstream.assert_not_called()

    def test_stream_preserved_and_only_fixed_https_target_used(self):
        body=b'{"input":"hi","stream":true}'
        with patch.object(connector,'open_upstream',return_value=(Connection(),Reply())) as upstream:
            status,raw=self.request('POST','/v1/responses',body)
            self.assertEqual(status,200);self.assertIn(b'response.completed',raw)
            self.assertEqual(upstream.call_args.args[1:],('POST','/api/codex/v1/responses',body))

    def test_hardware_failure_does_not_fallback_or_call_remote(self):
        with patch.object(connector,'signer',side_effect=RuntimeError('hardware unavailable')):
            with self.assertRaises(RuntimeError): connector.proof(self.server.config,'GET','/api/codex/v1/models',b'')
        for url in ('http://example.test/v1','https://u:p@example.test/v1','https://example.test/v1?x=1'):
            with self.assertRaises(ValueError):connector.base({'baseUrl':url})
