"""Exercise actual scheduling/stdio boundaries without model calls or credentials."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import codex_quota_events as events
import collect_codex_quota as collector

IDENTITY = 'fixture-account'
DIGEST = hashlib.sha256(IDENTITY.encode()).hexdigest()
RESULT = {'accountId':IDENTITY, 'rateLimits': {
    'primary':{'usedPercent':9,'windowDurationMins':10080,'resetsAt':1900000000},
    'secondary':None, 'planType':'fixture'}}


class SignalsTests(unittest.TestCase):
    def test_new_token_event_triggers_but_chat_text_partial_and_history_do_not(self):
        with tempfile.TemporaryDirectory() as root:
            sessions = Path(root)/'sessions'; sessions.mkdir()
            path = sessions/'one.jsonl'
            token = json.dumps({'type':'event_msg','payload':{'type':'token_count'}}).encode()+b'\n'
            path.write_bytes(token)
            watch = events.LocalSignals(root)
            self.assertFalse(watch.poll())
            with path.open('ab') as stream:
                stream.write(b'{"type":"event_msg","payload":{"type":"agent_message","message":"private"}}\n')
                stream.write(token[:-1])
            self.assertFalse(watch.poll())
            with path.open('ab') as stream:
                stream.write(b'\n')
            self.assertTrue(watch.poll())
            self.assertFalse(watch.poll())
            path.write_bytes(token)
            self.assertTrue(watch.poll())  # Truncation is detected.

    def test_republication_keeps_verified_quota_timestamp(self):
        value = collector.sanitize(RESULT, DIGEST)
        async def sample_value():
            monitor = events.Monitor({}, collector.sanitize, collector.unavailable, None)
            monitor.latest = value
            monitor.reader_connected = True
            return monitor.sample()
        sample = asyncio.run(sample_value())
        self.assertEqual(sample['capturedAt'], value['capturedAt'])
        self.assertEqual(sample['collection']['fallbackSeconds'], 60)
        self.assertNotIn('accountId', sample)


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def test_notification_stdio_dedup_and_disconnect(self):
        with tempfile.TemporaryDirectory() as root:
            executable = Path(root)/'fixture-reader'
            source = '''#!/usr/bin/env python3
import json,sys
for line in sys.stdin:
 v=json.loads(line)
 if 'id' not in v:continue
 if v['method']=='initialize':r={}
 else:
  r=RESULT
  event={'method':'account/rateLimits/updated','params':{'rateLimits':r['rateLimits']}}
  print(json.dumps(event),flush=True);print(json.dumps(event),flush=True)
 print(json.dumps({'id':v['id'],'result':r}),flush=True)
'''.replace('r=RESULT', 'r='+repr(RESULT))
            executable.write_text(source); executable.chmod(0o700)
            changes = []
            reader = events.Reader({'codexHome':root,'codexExecutable':str(executable)}, changes.append)
            await reader.open()
            try:
                value = await reader.request('account/rateLimits/read', {})
                self.assertEqual(value, RESULT)
                self.assertEqual(changes, ['official-notification'])
                await reader.request('account/rateLimits/read', {})
                self.assertEqual(len(changes), 1)
                await events.stop_process(reader.process)
                with self.assertRaises(Exception):
                    await reader.request('account/rateLimits/read', {}, timeout=.1)
            finally:
                await reader.close()

    async def test_event_burst_is_coalesced_and_wrong_account_is_rejected(self):
        reads = []
        class FakeReader:
            def __init__(self, config, changed): pass
            async def open(self): pass
            async def close(self): pass
            async def request(self, *args):
                reads.append(1)
                return RESULT if len(reads) == 1 else {**RESULT, 'accountId':'wrong-account'}
        m = events.Monitor({'expectedAccountDigest':DIGEST}, collector.sanitize, collector.unavailable, None)
        with patch.object(events, 'Reader', FakeReader), patch.object(events, 'MIN_READ_SECONDS', .03), patch.object(events, 'DEBOUNCE_SECONDS', .01):
            task = asyncio.create_task(m.reader_loop())
            try:
                await asyncio.wait_for(m.dirty.wait(), 1)
                self.assertEqual(m.latest['status'], 'available')
                m.dirty.clear()
                for _ in range(20): m.trigger('device-usage')
                await asyncio.wait_for(m.dirty.wait(), 1)
                self.assertEqual(len(reads), 2)
                self.assertEqual(m.latest['status'], 'unavailable')
            finally:
                task.cancel(); await asyncio.gather(task, return_exceptions=True)

    async def test_fallback_reads_without_any_event_and_reader_reconnects(self):
        reads, opens = [], []
        class FakeReader:
            def __init__(self, config, changed): pass
            async def open(self): opens.append(1)
            async def close(self): pass
            async def request(self, *args): reads.append(1); return RESULT
        m = events.Monitor({'expectedAccountDigest':DIGEST}, collector.sanitize, collector.unavailable, None)
        real_sleep = asyncio.sleep
        async def fast_sleep(delay): await real_sleep(min(delay, .01))
        with patch.object(events, 'Reader', FakeReader), patch.object(events, 'FALLBACK_SECONDS', .02), patch.object(events, 'MIN_READ_SECONDS', .001), patch.object(events, 'DEBOUNCE_SECONDS', .001), patch.object(events.asyncio, 'sleep', fast_sleep):
            tasks = [asyncio.create_task(m.reader_loop()), asyncio.create_task(m.timer_loop())]
            try:
                await real_sleep(.09)
                self.assertGreaterEqual(len(reads), 3)
                self.assertEqual(len(opens), 1)
            finally:
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def test_disconnected_reader_is_reopened_and_publisher_is_serial(self):
        opens, published = [], []
        class FakeReader:
            def __init__(self, config, changed): pass
            async def open(self): opens.append(1)
            async def close(self): pass
            async def request(self, *args):
                if len(opens)==1: raise RuntimeError('disconnected')
                return RESULT
        def publish(config, sample): published.append(sample)
        m = events.Monitor({'expectedAccountDigest':DIGEST}, collector.sanitize, collector.unavailable, publish)
        real_sleep = asyncio.sleep
        async def fast_sleep(delay): await real_sleep(min(delay, .01))
        with patch.object(events, 'Reader', FakeReader), patch.object(events.asyncio, 'sleep', fast_sleep):
            tasks = [asyncio.create_task(m.reader_loop()),asyncio.create_task(m.publisher_loop())]
            try:
                await real_sleep(.08)
                self.assertGreaterEqual(len(opens), 2)
                self.assertEqual(m.latest['status'], 'available')
                self.assertTrue(any(s['status']=='available' for s in published))
            finally:
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
