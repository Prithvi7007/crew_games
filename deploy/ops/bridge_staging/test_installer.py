import ast
from pathlib import Path
import tempfile
import unittest
from install_artifact_sync import patch

class InstallerTests(unittest.TestCase):
    def test_rejects_unexpected_source_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ('runner/worker.py','bridge/core.py','bridge/server.py'):
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('x = 1\n')
            with self.assertRaisesRegex(ValueError, 'anchor'):
                patch(root, dry_run=False)
            self.assertEqual((root/'runner/worker.py').read_text(), 'x = 1\n')

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {
                'runner/worker.py': "def f():\n    code, output = 0, ''\n        code, output = _run_check(cmd, cwd, env)\n        return {'job_id': job_id,}\n",
                'bridge/core.py': "def f():\n    pass\n\ndef commit_and_push(message: str) -> dict:\n    return {}\n",
                'bridge/server.py': "def f():\n    pass\n\n@mcp.tool()\ndef crew_commit_and_push(message: str):\n    pass\n",
            }
            for rel, source in fixtures.items():
                target = root/rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            with self.assertRaises((SyntaxError, ValueError)):
                patch(root, dry_run=True)
            for rel, source in fixtures.items():
                self.assertEqual((root/rel).read_text(), source)

if __name__ == '__main__':
    unittest.main()
