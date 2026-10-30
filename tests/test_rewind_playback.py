"""Exercise the cinema's playback state with Node's dependency-free test runner."""
import subprocess
from pathlib import Path


def test_rewind_playback_transitions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "--test", "frontend/tests/rewind-playback.test.mjs"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
