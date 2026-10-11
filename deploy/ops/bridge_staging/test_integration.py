"""Offline integration tests for the actual installed sync function."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch as mock_patch

from install_artifact_sync import CORE_HOOK, RUNNER_HOOK, SERVER_HOOK, patch

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'workspace'
        self.queue = self.root / 'queue'
        self.workspace.mkdir()
        self.queue.mkdir()
        self.job = 'a' * 32
        self.allowed = ('app/static/react/player.js', 'app/static/react/player.css')
        self.originals = {}
        for rel in self.allowed:
            path = self.workspace / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            self.originals[rel] = ('old-' + rel).encode()
            path.write_bytes(self.originals[rel])
        self.payloads = {rel: ('new-' + rel).encode() for rel in self.allowed}
        export = self.queue / 'artifacts' / self.job
        export.mkdir(parents=True)
        for rel, content in self.payloads.items():
            (export / Path(rel).name).write_bytes(content)
        (export / 'manifest.json').write_text(json.dumps({rel: hashlib.sha256(content).hexdigest() for rel,content in self.payloads.items()}))
        results = self.queue / 'results'
        results.mkdir()
        self.result = {'job_id':self.job,'kind':'react_build','state':'passed','exit_code':0,'branch':'feature/test','fingerprint':'before'}
        (results / (self.job + '.json')).write_text(json.dumps(self.result))
        import contextlib, re, uuid
        class BridgeError(Exception): pass
        self.BridgeError = BridgeError
        namespace = {'QUEUE':self.queue,'MAX_FILE':250000,'BridgeError':BridgeError,
            'locked':contextlib.nullcontext,'validate_branch':lambda b:b,
            'branch':lambda:'feature/test','fingerprint':lambda:'before',
            'safe_path':lambda rel:self.workspace / rel,'audit':lambda *a,**kw:None,
            'json':json,'re':re,'hashlib':hashlib,'Path':Path,'os':os,'uuid':uuid}
        exec(CORE_HOOK, namespace)
        self.sync = namespace['sync_frontend_assets']

    def test_runner_export_permissions_explicit(self):
        self.assertIn("os.chown(export_root, 0, 10001)", RUNNER_HOOK)
        self.assertIn("os.chmod(export_root, 0o750)", RUNNER_HOOK)
        self.assertIn("os.chown(dest, 0, 10001)", RUNNER_HOOK)
        self.assertIn("os.chmod(dest, 0o640)", RUNNER_HOOK)
        self.assertIn("os.chown(manifest_file, 0, 10001)", RUNNER_HOOK)
        self.assertIn("os.chmod(manifest_file, 0o640)", RUNNER_HOOK)

    def test_successful_import(self):
        result = self.sync(self.job)
        self.assertTrue(result['requires_new_checks'])
        for rel, raw in self.payloads.items():
            self.assertEqual((self.workspace / rel).read_bytes(),raw)

    def test_checksum_tampering_rejected_without_writes(self):
        (self.queue / 'artifacts' / self.job / 'player.css').write_text('tampered')
        with self.assertRaisesRegex(self.BridgeError,'checksum'):
            self.sync(self.job)
        self.assertOriginals()

    def test_stale_result_rejected(self):
        self.result['fingerprint'] = 'wrong'
        (self.queue / 'results' / (self.job + '.json')).write_text(json.dumps(self.result))
        with self.assertRaisesRegex(self.BridgeError,'does not match'):
            self.sync(self.job)
        self.assertOriginals()

    def test_second_replace_failure_rolls_back_first(self):
        actual = os.replace
        count = [0]
        def fail_second(src,dst):
            count[0]+=1
            if count[0] == 2:
                raise OSError('simulated interrupted second write')
            return actual(src,dst)
        with mock_patch.dict(self.sync.__globals__, {'os':types.SimpleNamespace(replace=fail_second,chmod=os.chmod)}):
            with self.assertRaisesRegex(self.BridgeError,'restored'):
                self.sync(self.job)
        self.assertOriginals()

    def test_symlink_artifact_rejected(self):
        path = self.queue / 'artifacts' / self.job / 'player.js'
        path.unlink()
        path.symlink_to(self.workspace / self.allowed[0])
        with self.assertRaisesRegex(self.BridgeError,'Unsafe'):
            self.sync(self.job)
        self.assertOriginals()

    def assertOriginals(self):
        for rel, raw in self.originals.items():
            self.assertEqual((self.workspace / rel).read_bytes(),raw)

    def test_installer_against_realistic_bridge_anchors(self):
        repo = self.root / 'bridge-repo'
        fixtures = {
            'runner/worker.py': "def execute(ticket):\n    code, output = _run_check(cmd, cwd, env)\n    return {'job_id': job_id, 'kind': kind}\n",
            'bridge/core.py': "def fingerprint():\n    return 'before'\n\ndef commit_and_push(message: str) -> dict:\n    return {}\n",
            'bridge/server.py': "class MockMCP:\n    def tool(self):\n        return lambda f: f\nmcp = MockMCP()\n\n@mcp.tool()\ndef crew_commit_and_push(message: str):\n    pass\n",
        }
        fixtures['runner/worker.py'] = fixtures['runner/worker.py'].replace('    code, output', '        code, output').replace('    return {', '        return {')
        for rel, src in fixtures.items():
            path = repo / rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(src)
        patch(repo, dry_run=True)
        for rel,src in fixtures.items():
            self.assertEqual((repo/rel).read_text(),src)
        patch(repo, dry_run=False)
        for rel in fixtures:
            self.assertIn('sync_frontend_assets' if 'core' in rel or 'server' in rel else 'export_root', (repo/rel).read_text())
        with self.assertRaisesRegex(ValueError,'anchor'):
            patch(repo, dry_run=False)

if __name__ == '__main__':
    unittest.main()
