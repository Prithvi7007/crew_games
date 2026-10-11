"""Bounded app readiness, pinned PR #25 incident recovery, and fail-closed gates."""
import ast
from pathlib import Path

import pytest

from deploy.ops import merge_auto_deploy as auto
from deploy.ops import reconcile_merge_auto_pr25 as recovery


def _original_state():
    return {
        "phase": "failed", "base": recovery.FAILED_BASE,
        "release": recovery.FAILED_RELEASE, "reviewed_pr": 25,
        "manifest_sha": "b" * 64,
    }


def _original_manifest():
    return {
        "format": 1, "kind": "code_only",
        "base": recovery.FAILED_BASE, "release": recovery.FAILED_RELEASE,
        "reviewed_pr": 25, "db_revision": "v15_badges",
    }


def _healthy_db():
    return {"revision": "v15_badges", "profiles": 14,
            "game_completions": 111, "user_stats": 14}


def _healthy_assets():
    return {k: {"present": True, "nginx_user_readable": True,
                "local_https": "200|text/css"} for k in ("player.js", "player.css")}


def test_restart_retries_until_actual_socket_readiness(monkeypatch):
    commands = []
    checks = [False, False, True]
    waited = []
    monkeypatch.setattr(auto.maint, "fixed",
                        lambda *a, **kw: (commands.append(a) or True, ""))
    monkeypatch.setattr(auto.maint, "service_active", lambda unit: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: checks.pop(0))
    monkeypatch.setattr(auto.time, "sleep", lambda seconds: waited.append(seconds))
    auto.restart_crew_with_readiness()
    assert len(commands) == 1
    assert commands[0][:3] == ("/usr/bin/systemctl", "restart", "crew.service")
    assert waited == [2, 2]


def test_restart_failure_does_not_claim_success(monkeypatch):
    monkeypatch.setattr(auto.maint, "fixed", lambda *a, **kw: (False, ""))
    monkeypatch.setattr(auto.maint, "socket_health",
                        lambda: pytest.fail("readiness should not be checked"))
    with pytest.raises(auto.maint.Refused, match="restart_failed"):
        auto.restart_crew_with_readiness()


def test_restart_remains_blocked_when_health_never_arrives(monkeypatch):
    count = []
    monkeypatch.setattr(auto.maint, "fixed", lambda *a, **kw: (True, ""))
    monkeypatch.setattr(auto.maint, "service_active", lambda unit: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: False)
    monkeypatch.setattr(auto.time, "sleep", lambda seconds: count.append(seconds))
    with pytest.raises(auto.maint.Refused, match="post_restart_health_failed"):
        auto.restart_crew_with_readiness()
    assert count == [2] * 19


def test_exact_previously_failed_and_now_healthy_pr25_is_reconcilable():
    recovery.validate_recovery(_original_state(), _original_manifest(),
                               recovery.FAILED_RELEASE, _healthy_db(), _healthy_assets())


@pytest.mark.parametrize("field,value", [
    ("phase", "running"), ("phase", "succeeded"),
    ("base", "0" * 40), ("release", "1" * 40),
    ("reviewed_pr", 26),
])
def test_recovery_rejects_unknown_incident(field, value):
    state = _original_state()
    state[field] = value
    with pytest.raises(recovery.RecoveryRefused):
        recovery.validate_recovery(state, _original_manifest(),
                                   recovery.FAILED_RELEASE, _healthy_db(), _healthy_assets())


def test_recovery_refuses_code_that_isnt_live():
    with pytest.raises(recovery.RecoveryRefused, match="wrong_failed_release"):
        recovery.validate_recovery(_original_state(), _original_manifest(),
                                   "f" * 40, _healthy_db(), _healthy_assets())


def test_recovery_refuses_manifest_mismatch():
    manifest = _original_manifest()
    manifest["release"] = "f" * 40
    with pytest.raises(recovery.RecoveryRefused, match="release_manifest_disagrees"):
        recovery.validate_recovery(_original_state(), manifest,
                                   recovery.FAILED_RELEASE, _healthy_db(), _healthy_assets())


@pytest.mark.parametrize("field,value", [
    ("revision", "v14_seasons"), ("profiles", 13),
    ("game_completions", 110), ("user_stats", 13),
])
def test_recovery_refuses_unverified_database(field, value):
    db = _healthy_db()
    db[field] = value
    with pytest.raises(recovery.RecoveryRefused, match="database_integrity_unverified"):
        recovery.validate_recovery(_original_state(), _original_manifest(),
                                   recovery.FAILED_RELEASE, db, _healthy_assets())


@pytest.mark.parametrize("field,value", [
    ("present", False), ("nginx_user_readable", False),
    ("local_https", "403|text/plain"),
])
def test_recovery_refuses_unreadable_assets(field, value):
    assets = _healthy_assets()
    assets["player.css"][field] = value
    with pytest.raises(recovery.RecoveryRefused, match="live_assets_unverified"):
        recovery.validate_recovery(_original_state(), _original_manifest(),
                                   recovery.FAILED_RELEASE, _healthy_db(), assets)


def test_recovery_script_never_executes_deploy_or_git_reset():
    recovery_code = Path("deploy/ops/reconcile_merge_auto_pr25.py").read_text()
    ast.parse(recovery_code)
    assert "maint.deploy_code_only(" not in recovery_code
    assert "reset\", \"--hard" not in recovery_code
    assert "RECONCILE CREW PR25" in recovery_code
    assert "reviewed + \":deploy/ops/merge_auto_deploy.py\"" in recovery_code
    assert "watcher.verify_ci(reviewed)" in recovery_code
    assert "atomic_archive(" in recovery_code
    assert "maintenance._write_json(watcher.STATE" in recovery_code
