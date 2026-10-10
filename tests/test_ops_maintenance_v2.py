"""Offline, fail-closed tests for the controlled CREW Ops v2 host service."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import stat

import pytest

from deploy.ops import maintenance_v2 as maint
from deploy.ops import bridge_maintenance_v2_client as client


def test_only_fixed_zero_argument_ops():
    assert maint.respond(None) == {"ok": False, "error": "invalid_request"}
    assert maint.respond({"operation": "dashboard", "path": "/etc/shadow"}) == {
        "ok": False, "error": "invalid_request"}
    for command in ("shell", "exec", "run", "restore", "db-upgrade",
                    "execute_v15", "restart_nginx", "chmod", "sudo"):
        assert maint.respond({"operation": command}) == {
            "ok": False, "error": "operation_not_allowed"}
    caps = maint.respond({"operation": "capabilities"})
    assert caps["ok"] is True
    assert caps["shell_enabled"] is False
    assert caps["database_writes_enabled"] is False
    assert caps["approval_required_for_writes"] is True


def test_dashboard_returns_only_aggregate_data(monkeypatch):
    monkeypatch.setattr(maint, "git_sha", lambda: "a" * 40)
    monkeypatch.setattr(maint, "service_active", lambda unit: unit == "crew.service")
    monkeypatch.setattr(maint, "socket_health", lambda: True)
    monkeypatch.setattr(maint, "database_summary", lambda: {
        "revision": "v15_badges", "profiles": 14, "game_completions": 111,
        "user_stats": 14,
    })
    result = maint.respond({"operation": "dashboard"})
    assert result["database"]["profiles"] == 14
    assert result["services"]["nginx.service"] is False
    assert "username" not in json.dumps(result)
    assert "DATABASE_URL" not in json.dumps(result)


def test_asset_summary_does_not_return_source_or_sensitive_paths(monkeypatch):
    monkeypatch.setattr(maint, "read_public_asset",
                        lambda filename: (_fake_fd(), 0o600, 123, filename))
    monkeypatch.setattr(maint, "fixed", lambda *a, **k: (True, "200|text/css"))
    response = maint.respond({"operation": "asset_diagnostics"})
    assert all(x["nginx_user_readable"] for x in response["assets"].values())
    assert response["assets"]["player.js"]["mode"] == "0600"
    assert "/opt/crew" not in json.dumps(response)


def _fake_fd():
    return os.open(os.devnull, os.O_RDONLY)


def test_invalid_asset_name_refused():
    with pytest.raises(maint.Refused, match="asset_not_allowed"):
        maint.read_public_asset("../../../etc/shadow")


def test_asset_must_be_ordinary_owned_file(monkeypatch, tmp_path):
    root = tmp_path / "opt" / "crew" / "app" / "static" / "react"
    root.mkdir(parents=True)
    (root / "player.js").write_text("valid")
    monkeypatch.setattr(maint, "CREW", tmp_path / "opt" / "crew")
    # The real pinned path is intentionally used, not the new CREW variable.
    # Test the final host-path invariant and missing-file fail-closed behavior.
    with pytest.raises((OSError, maint.Refused)):
        maint.read_public_asset("nonexistent")


def test_unknown_bridge_method_rejected_without_socket(monkeypatch):
    def forbidden_socket(*args):
        raise AssertionError("socket must not be opened")
    monkeypatch.setattr(client.socket, "socket", forbidden_socket)
    assert client.request("shell") == {"ok": False, "error": "operation_not_allowed"}


def test_bridge_wraps_broken_socket_without_leaking(monkeypatch):
    def unavailable(*args):
        raise OSError("sensitive details")
    monkeypatch.setattr(client.socket, "socket", unavailable)
    assert client.crew_maint_dashboard() == {
        "ok": False, "error": "maintenance_socket_unavailable"}


def test_approval_absent_means_no_action(monkeypatch):
    monkeypatch.setattr(maint, "action_digest", lambda op: "digest")
    monkeypatch.setattr(maint, "approval_present", lambda: False)
    monkeypatch.setattr(maint, "repair_react_assets",
                        lambda: pytest.fail("repair should not run"))
    result = maint.respond({"operation": "execute_repair_react_assets"})
    assert result == {"ok": False, "error": "root_approval_required"}


def test_plans_bind_digest_to_exact_action_commit_and_assets(monkeypatch):
    monkeypatch.setattr(maint, "git_sha", lambda: "1" * 40)
    monkeypatch.setattr(maint, "asset_fingerprint", lambda: "2" * 64)
    assert maint.action_digest("repair_react_assets") != maint.action_digest("restart_crew")
    result = maint.plan("repair_react_assets")
    assert result["database_migration"] is False
    assert result["approval_required"] is True
    assert result["commit"] == "1" * 40


@pytest.fixture
def state_area(monkeypatch, tmp_path):
    directory = tmp_path / "maint"
    directory.mkdir(mode=0o700)
    (directory / "consumed").mkdir(mode=0o700)
    monkeypatch.setattr(maint, "STATE_DIR", directory)
    monkeypatch.setattr(maint, "CONSUMED", directory / "consumed")
    monkeypatch.setattr(maint, "APPROVAL", directory / "approval.json")
    monkeypatch.setattr(maint, "AUDIT", directory / "audit.jsonl")
    monkeypatch.setattr(maint, "ACTION_STATE", directory / "action.json")
    # CI is unprivileged; simulate root-owned approval/audit files only here.
    monkeypatch.setattr(maint, "_safe_state_dir", lambda: None)
    def test_approval_present():
        p = maint.APPROVAL
        return p.exists() and not p.is_symlink() and stat.S_IMODE(p.stat().st_mode) == 0o600
    monkeypatch.setattr(maint, "approval_present", test_approval_present)
    def test_audit(operation, outcome):
        with maint.AUDIT.open("a") as stream:
            stream.write(json.dumps({"operation": operation, "outcome": outcome}) + "\n")
    monkeypatch.setattr(maint, "audit", test_audit)
    return directory


def stage(state_area, action="repair_react_assets", digest="d" * 64, expired=False):
    until = maint.now() + dt.timedelta(minutes=-1 if expired else 4)
    data = {"operation": action, "plan_digest": digest,
            "expires_at": until.isoformat(), "nonce": "a" * 32}
    path = state_area / "approval.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


def test_approval_consumed_before_action_and_audited(monkeypatch, state_area):
    stage(state_area)
    monkeypatch.setattr(maint, "action_digest", lambda op: "d" * 64)
    def repair():
        assert not maint.APPROVAL.exists()
        assert list(maint.CONSUMED.iterdir())
    monkeypatch.setattr(maint, "repair_react_assets", repair)
    response = maint.execute_action("repair_react_assets")
    assert response["phase"] == "succeeded"
    assert not maint.APPROVAL.exists()
    assert list(maint.CONSUMED.glob("*.json"))
    entries = [json.loads(x) for x in (state_area / "audit.jsonl").read_text().splitlines()]
    assert [e["outcome"] for e in entries] == ["started", "succeeded"]
    assert (state_area / "action.json").exists()
    with pytest.raises(maint.Refused, match="root_approval_required"):
        maint.execute_action("repair_react_assets")


def test_wrong_action_or_digest_never_consumes_approval(state_area):
    staged = stage(state_area)
    with pytest.raises(maint.Refused, match="approval_plan_mismatch"):
        maint.consume_approval("restart_crew", "d" * 64)
    with pytest.raises(maint.Refused, match="approval_plan_mismatch"):
        maint.consume_approval("repair_react_assets", "f" * 64)
    assert staged.exists()


def test_expired_approval_refused(state_area):
    stage(state_area, expired=True)
    with pytest.raises(maint.Refused, match="approval_expired"):
        maint.consume_approval("repair_react_assets", "d" * 64)


def test_symlink_approval_refused(state_area):
    source = state_area / "evil.json"
    source.write_text("{}")
    (state_area / "approval.json").symlink_to(source)
    with pytest.raises(maint.Refused, match="root_approval_required"):
        maint.consume_approval("repair_react_assets", "d" * 64)


def test_no_clobber_existing_approval(monkeypatch, state_area):
    stage(state_area)
    monkeypatch.setattr(maint.sys.stdin, "isatty", lambda: True)
    with pytest.raises(SystemExit, match="prior approval"):
        maint.approve("repair_react_assets")


def test_root_only_state_dir_rejects_permissive_paths(monkeypatch, state_area):
    # Restore the real validator; even a root-owned directory must not be 0755.
    monkeypatch.undo()
    monkeypatch.setattr(maint, "STATE_DIR", state_area)
    monkeypatch.setattr(maint, "CONSUMED", state_area / "consumed")
    state_area.chmod(0o755)
    with pytest.raises(maint.Refused, match="unsafe_state_directory"):
        maint._safe_state_dir()


def test_failure_consumes_approval_and_preserves_audit(monkeypatch, state_area):
    stage(state_area)
    monkeypatch.setattr(maint, "action_digest", lambda op: "d" * 64)
    def fail():
        raise maint.Refused("post_restart_health_failed")
    monkeypatch.setattr(maint, "repair_react_assets", fail)
    result = maint.execute_action("repair_react_assets")
    assert result["error"] == "post_restart_health_failed"
    assert maint.maintenance_status()["last_action"]["phase"] == "failed"
    assert not maint.APPROVAL.exists()


def test_fixed_command_environment_not_inherited(monkeypatch):
    received = {}
    class Result:
        returncode = 0
        stdout = "ok"
    def run(argv, **kwargs):
        received.update(kwargs)
        return Result()
    monkeypatch.setattr(maint.subprocess, "run", run)
    ok, out = maint.fixed("/usr/bin/true")
    assert ok and out == "ok"
    assert "DATABASE_URL" not in received["env"]
    assert "shell" not in received
    assert received["timeout"] == 12


def test_code_release_disabled_without_root_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(maint, "RELEASE_MANIFEST", tmp_path / "absent.json")
    assert maint.respond({"operation": "code_release_plan"}) == {
        "ok": True, "configured": False,
        "message": "root_owned_pinned_manifest_required"}
    monkeypatch.setattr(maint, "git_sha", lambda: "a" * 40)
    result = maint.respond({"operation": "execute_code_release"})
    assert not result["ok"]
    assert result["error"] == "release_manifest_missing_or_invalid"


def test_rejects_untrusted_manifest_or_unsupported_migration(monkeypatch, tmp_path):
    path = tmp_path / "plan.json"
    monkeypatch.setattr(maint, "RELEASE_MANIFEST", path)
    with pytest.raises(maint.Refused, match="release_manifest_missing_or_invalid"):
        maint.read_code_release_manifest()
    path.write_text(json.dumps({"format": 1, "kind": "migrate", "base": "a" * 40,
                                "release": "b" * 40, "db_revision": "v15_badges",
                                "reviewed_pr": 33}))
    path.chmod(0o400)
    monkeypatch.setattr(maint, "stat", stat)
    # CI is unprivileged: only mock the file metadata's root UID.
    real_lstat = Path.lstat
    def fake_lstat(item):
        details = real_lstat(item)
        if item == path:
            class Metadata:
                st_mode = details.st_mode
                st_uid = 0
                st_size = details.st_size
            return Metadata()
        return details
    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(maint.Refused, match="unsupported_release_kind"):
        maint.read_code_release_manifest()


def test_code_release_rejects_unreviewed_migration_changes(monkeypatch):
    manifest = {"base": "a" * 40, "release": "b" * 40,
                "kind": "code_only", "db_revision": "v15_badges",
                "format": 1, "reviewed_pr": 33}
    monkeypatch.setattr(maint, "read_code_release_manifest", lambda: manifest)
    monkeypatch.setattr(maint, "git_sha", lambda: manifest["base"])
    def git_read(path, *args, **kwargs):
        if args[0] == "rev-parse":
            return True, manifest["release"]
        if args[0] == "diff":
            return True, "alembic/versions/v16_something.py"
        return True, ""
    monkeypatch.setattr(maint, "git_inspect", git_read)
    with pytest.raises(maint.Refused, match="requires_separately_reviewed_migration_or_infra_release"):
        maint.release_preflight()


def test_approval_staged_for_exact_code_release_digest(monkeypatch, state_area):
    stage(state_area, action="deploy_code_only", digest="d" * 64)
    with pytest.raises(maint.Refused, match="approval_plan_mismatch"):
        maint.consume_approval("deploy_code_only", "a" * 64)
    assert maint.APPROVAL.exists()
    maint.consume_approval("deploy_code_only", "d" * 64)
    assert not maint.APPROVAL.exists()


def test_code_release_preflight_checks_base_and_db(monkeypatch):
    manifest = {"base": "a" * 40, "release": "b" * 40,
                "kind": "code_only", "db_revision": "v15_badges",
                "format": 1, "reviewed_pr": 22}
    monkeypatch.setattr(maint, "read_code_release_manifest", lambda: manifest)
    monkeypatch.setattr(maint, "git_sha", lambda: "c" * 40)
    with pytest.raises(maint.Refused, match="release_base_mismatch"):
        maint.release_preflight()
    monkeypatch.setattr(maint, "git_sha", lambda: manifest["base"])
    monkeypatch.setattr(maint, "git_inspect", lambda path, *a, **k:
                        (True, manifest["release"] if a[0] == "rev-parse" else ""))
    monkeypatch.setattr(maint, "database_summary", lambda: {"revision": "v14_seasons"})
    with pytest.raises(maint.Refused, match="release_database_revision_mismatch"):
        maint.release_preflight()


def test_code_release_queued_then_completes_off_request_thread(monkeypatch, state_area):
    import threading
    import time
    stage(state_area, action="deploy_code_only", digest="d" * 64)
    monkeypatch.setattr(maint, "action_digest", lambda action: "d" * 64)
    completed = threading.Event()
    monkeypatch.setattr(maint, "deploy_code_only", lambda: completed.set())
    started = maint.start_code_release()
    assert started["ok"] and started["phase"] == "queued"
    assert completed.wait(timeout=3)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if maint.maintenance_status()["last_action"].get("phase") == "succeeded":
            break
        time.sleep(0.01)
    assert maint.maintenance_status()["last_action"]["phase"] == "succeeded"
    assert not maint.APPROVAL.exists()


def test_interrupted_code_release_marked_failed(monkeypatch, state_area):
    (state_area / "action.json").write_text(json.dumps({
        "operation": "deploy_code_only", "phase": "running",
        "detail": "", "updated_at": maint.now().isoformat()
    }))
    maint.mark_interrupted_release()
    assert maint.maintenance_status()["last_action"]["phase"] == "failed"
    assert maint.maintenance_status()["last_action"]["detail"] == "worker_interrupted"
