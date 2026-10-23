import errno
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('source_supervisor',Path(__file__).resolve().parents[2]/'deploy/codex_source_supervisor.py')
supervisor=importlib.util.module_from_spec(spec);spec.loader.exec_module(supervisor)


class SupervisorTests(unittest.TestCase):
    def test_slow_process_probe_is_unknown_rather_than_a_dead_source(self):
        with patch.object(supervisor,'owner',side_effect=subprocess.TimeoutExpired('lsof',5)):
            self.assertEqual(supervisor.probe_owner('source',{}),(None,False))
        with patch.object(supervisor,'owner',return_value=None):
            self.assertEqual(supervisor.probe_owner('source',{}),(None,True))

    def test_status_disk_full_preserves_previous_snapshot_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source-status.json';path.write_text('{"state":"healthy"}')
            logger=Mock()
            with patch.object(supervisor,'atomic',side_effect=OSError(errno.ENOSPC,'full')):
                self.assertFalse(supervisor.write_status(path,{'state':'healthy'},logger))
            self.assertEqual(json.loads(path.read_text()),{'state':'healthy'})
            logger.warning.assert_called_once_with('status_write_failed errno=%s',errno.ENOSPC)

    def test_uncertain_process_identity_cannot_trigger_kill(self):
        with patch.object(supervisor.subprocess,'run',side_effect=subprocess.TimeoutExpired('ps',4)),patch.object(supervisor.os,'kill') as kill:
            supervisor.terminate(123,'source',{'sourceExecutable':'/owned/source','sourceOptions':'/owned/options'})
        kill.assert_not_called()
