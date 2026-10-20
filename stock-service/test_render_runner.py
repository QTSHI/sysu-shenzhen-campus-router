"""Portable local checks; no router, credentials, network or shell execution."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import render_runner as tool


class Tests(unittest.TestCase):
    def test_exact_parent_graph_renders_both_artifacts_without_installing(self):
        self.assertEqual(len(tool.verify_sources()),4)
        module=tool.renderer()
        mini='a'*64;observer='b'*64
        for artifact in('runner','shutdown'):
            raw=tool.render(artifact,mini,observer)
            self.assertTrue(raw.startswith(b'#!/bin/sh\n'));self.assertIn(mini.encode('ascii'),raw)
            self.assertIn(observer.encode('ascii'),raw)
            self.assertNotIn(b'@MINI@',raw);self.assertNotIn(b'@OBS@',raw)
            shell=shutil.which('sh')
            if shell:
                with tempfile.TemporaryDirectory()as name:
                    path=Path(name)/(artifact+'.sh');path.write_bytes(raw)
                    result=subprocess.run([shell,'-n',str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
                    self.assertEqual(result.returncode,0,'Generated shell syntax failed')
        self.assertEqual(module.parent_module().PARENT_SHA,tool.SOURCE_SHA256['stock_persistent_runner_logoff.py'])
        for name,pin in tool.SOURCE_SHA256.items():
            self.assertEqual(hashlib.sha256((tool.BASE/name).read_bytes()).hexdigest(),pin)

    def test_strict_v2_parser_keeps_cumulative_counts_and_rejects_old_or_secret_fields(self):
        module=tool.renderer()
        value=dict(kind=module.KIND,phase='online',reason='eap-success',boot_id='00000000-0000-0000-0000-000000000001',
                   uptime_seconds=9999,runner_pid=100,client_pid=200,observer_pid=300,attempt=9,recovery_used=8,
                   eap_success_seen=True,failure_latched=False,wan_carrier=1,observer_segment=15,observer_exit_code=None,
                   recovery_window_count=2,next_recovery_at_uptime=0,recovery_budget_pause=False)
        state=module.parse_state(json.dumps(value).encode('ascii'))
        self.assertEqual(state['attempt'],9);self.assertEqual(state['recovery_used'],8)
        for update in({'kind':'stock_campus_service_state_v1'},{'attempt':True},{'password':'placeholder'},
                      {'recovery_window_count':3},{'recovery_used':1}):
            with self.assertRaises(ValueError):module.parse_state(json.dumps(dict(value,**update)).encode('ascii'))
        with self.assertRaises(ValueError):module.parse_state(json.dumps(value).replace('"attempt": 9','"attempt": 9, "attempt": 9').encode('ascii'))


if __name__=='__main__':unittest.main()
