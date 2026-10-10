"""Offline safety tests for the unprivileged, read-only host gateway."""

import json
from pathlib import Path
import signal
import subprocess

from deploy.ops import host_service as ops


def test_only_readonly_capabilities_exposed():
    gateway = ops.Operations()
    caps = gateway.handle({"operation": "capabilities"})
    assert caps == {
        "ok": True,
        "operations": ["capabilities", "release_preflight"],
        "deployment_enabled": False,
        "rehearsal_enabled": False,
    }


def test_rejects_shell_deploy_and_extra_arguments():
    gateway = ops.Operations()
    for request in (
        {"operation": "shell", "command": "id"},
        {"operation": "deploy_release", "sha": "a" * 40},
        {"operation": "release_preflight", "command": "whoami"},
        {"operation": "start_v15_rehearsal", "database": "crew_prod"},
        {"operation": "rehearsal_status", "job_id": "a" * 32},
        ["release_preflight"],
        {"operation": 7},
    ):
        assert gateway.handle(request)["ok"] is False


def test_rehearsal_is_permanently_disabled():
    assert ops.Operations().handle({"operation": "start_v15_rehearsal"}) == {
        "ok": False, "error": "rehearsal_not_enabled"
    }


def test_pinned_git_checks_use_direct_unprivileged_git(monkeypatch):
    calls = []

    def fake_run(*args, timeout=8):
        calls.append(args)
        return True, ""

    monkeypatch.setattr(ops, "run_fixed", fake_run)
    for path in (ops.PRODUCTION, ops.STAGING):
        assert ops.git_inspect(path, "status", "--porcelain") == (True, "")
        command = calls[-1]
        assert command[0] == "/usr/bin/git"
        assert "/usr/sbin/runuser" not in command
        assert "sudo" not in command
        assert f"safe.directory={path}" in command
        assert "core.fsmonitor=false" in command
    assert len(calls) == 2
    assert ops.git_inspect(Path("/opt/crew-other"), "status", "--porcelain") == (False, "")
    assert ops.git_inspect(ops.PRODUCTION, "fetch", "origin", "main") == (False, "")
    assert len(calls) == 2


def test_preflight_reports_git_readiness_not_release_approval(monkeypatch):
    def command(*args, timeout=8):
        if args[-2:] == ("rev-parse", "HEAD"):
            if str(ops.STAGING) in args:
                return True, ops.EXPECTED_RELEASE
            return True, ops.EXPECTED_PRODUCTION
        if args[-2:] == ("status", "--porcelain"):
            return True, ""
        raise AssertionError(args)

    monkeypatch.setattr(ops, "run_fixed", command)
    status = ops.Operations().handle({"operation": "release_preflight"})
    assert status["ok"] is True
    assert status["git_ready"] is True
    assert status["ready"] is False
    assert status["privileged_backup_check"] == "required"
    assert status["migration_rehearsal"] == "disabled"


def test_dirty_worktree_blocks_git_readiness(monkeypatch):
    def command(*args, timeout=8):
        if args[-2:] == ("rev-parse", "HEAD"):
            return True, (ops.EXPECTED_RELEASE if str(ops.STAGING) in args
                          else ops.EXPECTED_PRODUCTION)
        if args[-2:] == ("status", "--porcelain"):
            return True, " M app.py" if str(ops.PRODUCTION) in args else ""
        raise AssertionError(args)

    monkeypatch.setattr(ops, "run_fixed", command)
    outcome = ops.preflight()
    assert not outcome["git_ready"]
    assert not outcome["checks"]["production_clean"]
    assert outcome["ready"] is False


def test_runner_timeout_terminates_own_process_group(monkeypatch):
    sent = []

    class FakeProcess:
        pid = 987654
        returncode = -signal.SIGTERM

        def __init__(self, *args, **kwargs):
            assert kwargs["start_new_session"] is True
            assert kwargs["stdin"] == subprocess.DEVNULL

        def communicate(self, timeout=None):
            if timeout != 3:
                raise subprocess.TimeoutExpired(cmd=("git",), timeout=timeout)
            return "", ""

    monkeypatch.setattr(ops.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(ops.os, "killpg", lambda pid, sig: sent.append((pid, sig)))
    assert ops.run_fixed("/usr/bin/git", "--version", timeout=1) == (False, "")
    assert sent == [(987654, signal.SIGTERM)]


def test_service_definition_is_unprivileged():
    content = (
        Path(__file__).resolve().parents[1] / "deploy/ops/crew-ops.service"
    ).read_text(encoding="utf-8")
    assert "User=crew\n" in content
    assert "Group=crew-ops\n" in content
    assert "NoNewPrivileges=yes" in content
    assert "ProtectSystem=strict" in content
    assert "User=root\n" not in content


def test_v15_shell_script_syntax_and_trust_boundary():
    """The separate privileged rehearsal candidate is NEVER exposed by gateway."""
    script = Path(__file__).resolve().parents[1] / "deploy/v15-migration-rehearsal.sh"
    source = script.read_text(encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0
    assert 'source "$PROD/deploy/postgres-env.sh"' not in source
    assert 'TEST_URL=$(/usr/bin/python3' in source
    assert '[[ "$PGDATABASE" == crew_prod && "$PGPORT" == 5432 ]]' in source
    assert '[[ "$existing" == 0 ]]' in source
    assert 'pg_admin dropdb "$TEST_DB"' in source


def test_socket_protocol_has_no_command_execution_fields():
    reply = ops.Operations().handle({"operation": "shell", "command": "id"})
    assert json.dumps(reply) == '{"ok": false, "error": "operation_not_allowed"}'
