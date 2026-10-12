"""Validate the Git-delivered bridge bootstrap against actual merged bridge sources.

These fixtures are a temporary transport-branch snapshot, not application runtime assets.
"""
import ast
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest


FIXTURES = {
    "bridge/core.py": "core.py.txt",
    "bridge/server.py": "server.py.txt",
    "runner/worker.py": "worker.py.txt",
    "runner/Dockerfile": "runner_dockerfile.txt",
    "compose.yaml": "compose.yaml.txt",
    ".gitignore": "gitignore.txt",
    ".dockerignore": "dockerignore.txt",
}
STAGING = Path(__file__).resolve().parents[1] / "bridge-bootstrap"


def setup_checkout(path):
    (path / "tests").mkdir(exist_ok=True)
    for relative, fixture in FIXTURES.items():
        destination = path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGING / "fixtures" / fixture, destination)


def mock_git(monkeypatch, checkout, *, branch="feature/multi-repo-development"):
    def check_output(argv, text=True):
        assert argv[0] == "git"
        key = tuple(argv[1:])
        if key == ("rev-parse", "--show-toplevel"):
            return str(checkout)
        if key == ("branch", "--show-current"):
            return branch
        if key == ("status", "--porcelain"):
            return ""
        raise AssertionError("Unexpected Git command: " + repr(argv))
    monkeypatch.setattr(subprocess, "check_output", check_output)


def test_bootstrap_applies_to_exact_live_bridge_snapshot(tmp_path, monkeypatch):
    checkout = tmp_path / "repo"
    checkout.mkdir()
    setup_checkout(checkout)
    mock_git(monkeypatch, checkout)
    monkeypatch.chdir(checkout)

    runpy.run_path(str(STAGING / "multi_repo_bootstrap.py"))

    core = (checkout / "bridge/core.py").read_text()
    server = (checkout / "bridge/server.py").read_text()
    worker = (checkout / "runner/worker.py").read_text()
    worker_dockerfile = (checkout / "runner/Dockerfile").read_text()
    compose = (checkout / "compose.yaml").read_text()
    test = (checkout / "tests/test_multi_repo.py").read_text()

    for content, source in ((core, "core"), (server, "server"),
                            (worker, "worker"), (test, "test_multi_repo")):
        ast.parse(content, filename=source)

    assert "def repository_context(" in core
    assert "return WORKSPACE if _ACTIVE_REPOSITORY.get() == 'crew_games' else BRIDGE_WORKSPACE" in core
    assert "and data.get('fingerprint') == current" in core
    assert "if _ACTIVE_REPOSITORY.get() != 'crew_games':" in core
    assert server.count("def crew_") == 30
    assert server.count("repository: str = 'crew_games'") == 11
    assert worker.count("if kind == 'pytest'") == 1
    assert "elif kind == 'bridge_syntax'" in worker
    assert '"httpx>=0.27,<1"' in worker_dockerfile
    assert '"mcp>=1.15,<2"' in worker_dockerfile
    assert "python3-venv python3-pip git &&" in worker_dockerfile
    assert "CREW_BRIDGE_WORKSPACE: /bridge-source" in compose
    assert "./bridge-source:/bridge-source:rw" in compose
    assert "/bridge-source/" in (checkout / ".gitignore").read_text()
    assert "/bridge-source/" in (checkout / ".dockerignore").read_text()


def test_bootstrap_refuses_wrong_branch(tmp_path, monkeypatch):
    checkout = tmp_path / "repo"
    checkout.mkdir()
    setup_checkout(checkout)
    mock_git(monkeypatch, checkout, branch="main")
    monkeypatch.chdir(checkout)
    prior = (checkout / "bridge/core.py").read_bytes()
    with pytest.raises(SystemExit, match="wrong feature branch"):
        runpy.run_path(str(STAGING / "multi_repo_bootstrap.py"))
    assert (checkout / "bridge/core.py").read_bytes() == prior
