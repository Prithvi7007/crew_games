#!/usr/bin/env python3
"""One-time Git-delivered bootstrap for CREW bridge multi-repository development.

Run only in the clean feature/multi-repo-development branch of crew-dev-bridge.
This script edits checked-out source; it does not push, merge, or restart anything.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path.cwd()
def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

if git("rev-parse", "--show-toplevel") != str(ROOT):
    raise SystemExit("STOP: execute from repository root")
if git("branch", "--show-current") != "feature/multi-repo-development":
    raise SystemExit("STOP: wrong feature branch")
if git("status", "--porcelain"):
    raise SystemExit("STOP: worktree is not clean")

paths = ["bridge/core.py", "bridge/server.py", "runner/worker.py",
         "compose.yaml", ".gitignore", ".dockerignore"]
src = {p: (ROOT / p).read_text(encoding="utf-8") for p in paths}
originals = dict(src)

def replace(path, old, new):
    count = src[path].count(old)
    if count != 1:
        raise ValueError(f"Unexpected match count for {path}: {count}: {old[:70]!r}")
    src[path] = src[path].replace(old, new, 1)

p = "bridge/core.py"
replace(p, "from contextlib import contextmanager\n",
        "from contextlib import contextmanager\nfrom contextvars import ContextVar\n")
replace(p, "WORKSPACE = Path(os.environ.get('CREW_WORKSPACE', '/workspace'))\n",
        "WORKSPACE = Path(os.environ.get('CREW_WORKSPACE', '/workspace'))\n"
        "BRIDGE_WORKSPACE = Path(os.environ.get('CREW_BRIDGE_WORKSPACE', '/bridge-source'))\n"
        "BRIDGE_REPO = 'Prithvi7007/crew-dev-bridge'\n"
        "_ACTIVE_REPOSITORY = ContextVar('crew_active_repository', default='crew_games')\n")
replace(p, "class BridgeError(Exception):\n    pass\n", '''class BridgeError(Exception):
    pass


@contextmanager
def repository_context(repository: str = 'crew_games'):
    """Select only the fixed repositories, isolated per request/thread."""
    if repository not in ('crew_games', 'crew-dev-bridge'):
        raise BridgeError('Unsupported repository')
    token = _ACTIVE_REPOSITORY.set(repository)
    try:
        yield
    finally:
        _ACTIVE_REPOSITORY.reset(token)


def _repo() -> str:
    return REPO if _ACTIVE_REPOSITORY.get() == 'crew_games' else BRIDGE_REPO


def _workspace() -> Path:
    return WORKSPACE if _ACTIVE_REPOSITORY.get() == 'crew_games' else BRIDGE_WORKSPACE
''')
replace(p, "'event': event, **details}", "'event': event, 'repository': _repo(), **details}")
replace(p, "root = WORKSPACE.resolve()", "root = _workspace().resolve()")
replace(p, "if not WORKSPACE.is_dir():", "if not _workspace().is_dir():")
replace(p, "cwd=WORKSPACE,", "cwd=_workspace(),")
replace(p, "digest = hashlib.sha256()\n    digest.update(branch().encode())",
        "digest = hashlib.sha256()\n    digest.update(_repo().encode('utf-8') + b'\\0')\n    digest.update(branch().encode())")
replace(p, "return {'repository': REPO, 'branch': branch(),",
        "return {'repository': _repo(), 'branch': branch(),")
replace(p, "url = 'https://api.github.com/repos/' + REPO + '/' + endpoint.lstrip('/')",
        "url = 'https://api.github.com/repos/' + _repo() + '/' + endpoint.lstrip('/')")
replace(p, "shutil.copytree(WORKSPACE, target, ignore=ignore, symlinks=False)",
        "shutil.copytree(_workspace(), target, ignore=ignore, symlinks=False)")
replace(p, "if kind not in ('pytest', 'react_build'):\n        raise BridgeError('Only pytest or react_build are supported')",
        "allowed = ('pytest', 'react_build') if _ACTIVE_REPOSITORY.get() == 'crew_games' else ('pytest', 'bridge_syntax')\n"
        "    if kind not in allowed:\n        raise BridgeError('Unsupported check kind for selected repository')")
replace(p, "ticket = {'job_id': job_id, 'kind': kind, 'fingerprint': fingerprint(), 'branch': branch(),",
        "ticket = {'job_id': job_id, 'kind': kind, 'fingerprint': fingerprint(), 'branch': branch(),\n"
        "                  'repository': _repo(),")
replace(p, "return {k: data.get(k) for k in ('job_id', 'kind', 'state', 'exit_code', 'output', 'fingerprint', 'branch')}",
        "if data.get('repository', REPO) != _repo():\n"
        "            raise BridgeError('Check belongs to a different repository')\n"
        "        return {k: data.get(k) for k in ('job_id', 'kind', 'state', 'exit_code', 'output', 'fingerprint', 'branch', 'repository')}")
replace(p, "if (QUEUE / 'jobs' / (job_id + '.json')).is_file():\n        return {'job_id': job_id, 'state': 'queued_or_running'}",
        "queued = QUEUE / 'jobs' / (job_id + '.json')\n"
        "    if queued.is_file():\n"
        "        if json.loads(queued.read_text()).get('repository', REPO) != _repo():\n"
        "            raise BridgeError('Check belongs to a different repository')\n"
        "        return {'job_id': job_id, 'state': 'queued_or_running'}")
replace(p, "if data.get('kind') == kind and data.get('state') == 'passed' and data.get('fingerprint') == current:",
        "if (data.get('repository', REPO) == _repo() and data.get('kind') == kind\n"
        "                    and data.get('state') == 'passed' and data.get('fingerprint') == current):")
replace(p, "    import stat\n    if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):",
        "    import stat\n    if _ACTIVE_REPOSITORY.get() != 'crew_games':\n"
        "        raise BridgeError('React asset import is only allowed for crew_games')\n"
        "    if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):")
replace(p, "if not _check_passed('pytest', current) or not _check_passed('react_build', current):\n"
        "            raise BridgeError('Both pytest and react_build must pass for the current changes')",
        "second_check = 'react_build' if _ACTIVE_REPOSITORY.get() == 'crew_games' else 'bridge_syntax'\n"
        "        if not _check_passed('pytest', current) or not _check_passed(second_check, current):\n"
        "            raise BridgeError('Both required repository checks must pass for the current changes')")
replace(p, "f'https://github.com/{REPO}/commit/", "f'https://github.com/{_repo()}/commit/")

p = "bridge/server.py"
tools = ("crew_repo_status", "crew_read_file", "crew_diff", "crew_create_branch",
         "crew_write_file", "crew_apply_patch", "crew_start_check", "crew_check_status",
         "crew_sync_frontend_assets", "crew_commit_and_push", "crew_open_draft_pr")
for name in tools:
    pattern = (r'(def ' + name + r'\(([^\n]*)\) -> dict:\n'
               r'    """[^\n]*"""\n)    (return core\.[^\n]+)')
    match = re.search(pattern, src[p])
    if match is None:
        raise ValueError("Missing expected server definition: " + name)
    args = match.group(2)
    old = match.group(0)
    new = (match.group(1).replace(
        f"def {name}({args})",
        f"def {name}({args}{', ' if args else ''}repository: str = 'crew_games')"
    ) + "    with core.repository_context(repository):\n"
       + "        " + match.group(3))
    replace(p, old, new)

p = "runner/worker.py"
replace(p, "ALLOWED = {'pytest', 'react_build'}",
        "ALLOWED = {'pytest', 'react_build', 'bridge_syntax'}")
replace(p, "    snapshot = QUEUE / 'snapshots' / job_id",
        "    repository = ticket.get('repository', 'Prithvi7007/crew_games')\n"
        "    if repository not in ('Prithvi7007/crew_games', 'Prithvi7007/crew-dev-bridge'):\n"
        "        raise ValueError('Unsupported repository')\n"
        "    if (kind == 'bridge_syntax' and repository != 'Prithvi7007/crew-dev-bridge') or (kind == 'react_build' and repository != 'Prithvi7007/crew_games'):\n"
        "        raise ValueError('Check kind does not match repository')\n"
        "    snapshot = QUEUE / 'snapshots' / job_id")
replace(p, "        if kind == 'pytest':\n"
        "            cmd, cwd = ['python', '-m', 'pytest', '-q'], working\n"
        "        else:",
        "        if kind == 'pytest':\n"
        "            cmd, cwd = ['python', '-m', 'pytest', '-q'], working\n"
        "        elif kind == 'bridge_syntax':\n"
        "            cmd, cwd = ['python', '-m', 'compileall', '-q', 'bridge', 'runner', 'tests'], working\n"
        "        else:")
replace(p, "return {'job_id': job_id, 'branch': ticket['branch'], 'fingerprint': ticket['fingerprint'],",
        "return {'job_id': job_id, 'branch': ticket['branch'], 'fingerprint': ticket['fingerprint'],\n"
        "                'repository': repository,")

replace("compose.yaml", "      CREW_WORKSPACE: /workspace\n",
        "      CREW_WORKSPACE: /workspace\n      CREW_BRIDGE_WORKSPACE: /bridge-source\n")
replace("compose.yaml", "      - ./source:/workspace:rw\n",
        "      - ./source:/workspace:rw\n      - ./bridge-source:/bridge-source:rw\n")
src[".gitignore"] += "/bridge-source/\n"
src[".dockerignore"] += "/bridge-source/\n"

test = '''"""Multi-repository isolation and scoping tests; no GitHub calls."""
import json
import subprocess

import pytest

from bridge import core


def git(path, *args):
    return subprocess.run(['git', '-C', str(path), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    games = tmp_path / 'games'
    bridge = tmp_path / 'bridge'
    for path in (games, bridge):
        path.mkdir()
        git(path, 'init', '-q', '-b', 'feature/test-branch')
        git(path, 'config', 'user.name', 'CI')
        git(path, 'config', 'user.email', 'test@example.invalid')
        (path / 'example.txt').write_text('hello\\n')
        git(path, 'add', '.')
        git(path, 'commit', '-qm', 'Initial')
    monkeypatch.setattr(core, 'WORKSPACE', games)
    monkeypatch.setattr(core, 'BRIDGE_WORKSPACE', bridge)
    monkeypatch.setattr(core, 'QUEUE', tmp_path / 'queue')
    monkeypatch.setattr(core, 'LOCK', tmp_path / 'queue' / 'workspace.lock')
    monkeypatch.setattr(core, 'AUDIT', tmp_path / 'audit' / 'events.jsonl')
    return games, bridge


def test_invalid_repository_is_rejected(repositories):
    with pytest.raises(core.BridgeError):
        with core.repository_context('../etc'):
            pass


def test_independent_workspaces_and_check_policy(repositories):
    games, bridge = repositories
    with core.repository_context('crew-dev-bridge'):
        assert core.status()['repository'] == 'Prithvi7007/crew-dev-bridge'
        core.write_file('bridge-only.txt', 'bridge', 'NEW')
        bridge_fingerprint = core.fingerprint()
        with pytest.raises(core.BridgeError):
            core.start_check('react_build')
    assert (bridge / 'bridge-only.txt').exists()
    assert not (games / 'bridge-only.txt').exists()
    with core.repository_context('crew_games'):
        assert core.status()['repository'] == core.REPO
        assert core.fingerprint() != bridge_fingerprint
        with pytest.raises(core.BridgeError):
            core.start_check('bridge_syntax')


def test_bridge_check_tickets_are_scoped(repositories):
    with core.repository_context('crew-dev-bridge'):
        result = core.start_check('bridge_syntax')
        job_id = result['job_id']
        ticket = json.loads((core.QUEUE / 'jobs' / (job_id + '.json')).read_text())
        assert ticket['repository'] == 'Prithvi7007/crew-dev-bridge'
        assert core.check_status(job_id)['state'] == 'queued_or_running'
    with core.repository_context('crew_games'):
        with pytest.raises(core.BridgeError):
            core.check_status(job_id)


def test_context_restored_after_exception(repositories):
    with pytest.raises(RuntimeError):
        with core.repository_context('crew-dev-bridge'):
            raise RuntimeError('test')
    assert core.status()['repository'] == core.REPO
'''
src["tests/test_multi_repo.py"] = test

# Fail safely: validate everything before writing anything.
for path in paths:
    if src[path] == originals[path]:
        raise ValueError("Unmodified expected file: " + path)
for path in paths:
    (ROOT / path).write_text(src[path], encoding="utf-8")
(ROOT / "tests/test_multi_repo.py").write_text(test, encoding="utf-8")
print("Updated 7 files. Nothing pushed or restarted.")
print("Next: python3 -m pytest -q && git diff --check")
