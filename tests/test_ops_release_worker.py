"""Offline security regression tests for the fixed CREW v15 release worker."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import stat

import pytest

from deploy.ops import release_broker as broker
from deploy.ops import release_engine as engine


def test_broker_capabilities_are_finite_and_approval_is_required(monkeypatch):
    obj = broker.Broker()
    caps = obj.respond({"operation": "capabilities"})
    assert caps["approval_required"] is True
    assert caps["arbitrary_shell_enabled"] is False
    assert caps["database_restore_enabled"] is False
    for operation in ("shell", "git_reset", "restore_production", "rollback_db",
                      "approve", "rehearse_database"):
        assert not obj.respond({"operation": operation})["ok"]
    assert not obj.respond({"operation": "execute_v15", "approved": True})["ok"]


def test_release_plan_pins_sha_and_does_not_authorize(monkeypatch):
    monkeypatch.setattr(broker, "deployment_engine_safe", lambda: True)
    monkeypatch.setattr(broker.Broker, "_safe_plan_digest", lambda self: "a" * 64)
    result = broker.Broker().respond({"operation": "release_plan"})
    assert result["production_sha"] == engine.BASE
    assert result["release_sha"] == engine.RELEASE
    assert result["plan_digest"] == "a" * 64
    assert result["approved"] is False
    assert "migrate_additive_schema" in result["steps"]


def test_execution_denied_without_out_of_band_approval(monkeypatch):
    monkeypatch.setattr(broker, "deployment_engine_safe", lambda: True)
    monkeypatch.setattr(broker, "load_status", lambda: {"phase": "not_started"})
    monkeypatch.setattr(broker, "validate_and_consume_approval", lambda: False)
    result = broker.Broker().respond({"operation": "execute_v15"})
    assert result == {"ok": False, "error": "out_of_band_approval_required"}


def test_approval_is_exact_single_use_and_expires(monkeypatch, tmp_path):
    authorization = tmp_path / "approval-v15.json"
    spent = tmp_path / "used-approvals"
    spent.mkdir()
    monkeypatch.setattr(broker, "APPROVAL", authorization)
    monkeypatch.setattr(broker, "SPENT_DIR", spent)
    monkeypatch.setattr(broker, "protected", lambda path, directory=False: True)
    monkeypatch.setattr(broker, "approval_plan_digest", lambda: "b" * 64)
    now = dt.datetime.now(dt.timezone.utc)

    def data(*, release=broker.RELEASE, expiry=None, confirmation="DEPLOY CREW V15",
             plan_digest="b" * 64):
        return {
            "operation": "execute_v15", "release_sha": release,
            "production_sha": broker.BASE,
            "expires_at": (expiry or now + dt.timedelta(minutes=5)).isoformat(),
            "confirmation": confirmation,
            "nonce": "f" * 32, "plan_digest": plan_digest,
        }

    for bad in (
        data(release="a" * 40),
        data(expiry=now - dt.timedelta(seconds=1)),
        data(expiry=now + dt.timedelta(hours=1)),
        data(confirmation="approved"),
        data(plan_digest="c" * 64),
    ):
        authorization.write_text(json.dumps(bad))
        assert not broker.validate_and_consume_approval()
        assert authorization.exists()
    authorization.write_text(json.dumps(data()))
    assert broker.validate_and_consume_approval()
    assert not authorization.exists()
    assert (spent / ("f" * 32 + ".json")).exists()
    authorization.write_text(json.dumps(data()))
    assert not broker.validate_and_consume_approval()


def test_status_hides_any_untrusted_fields(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "phase": "halted", "detail": "migration_failed",
        "password": "not-for-logs",
        "DATABASE_URL": "not-for-logs",
    }))
    monkeypatch.setattr(broker, "STATE", state)
    status = broker.load_status()
    assert status["phase"] == "halted"
    assert "password" not in status
    assert "DATABASE_URL" not in json.dumps(status)


def test_engine_cannot_run_unapproved_git_operations(monkeypatch):
    calls = []
    monkeypatch.setattr(engine, "execute", lambda argv, **kwargs: calls.append(argv) or "")
    with pytest.raises(engine.ReleaseHalted, match="git_operation_rejected"):
        engine.git("fetch", "origin", "main")
    with pytest.raises(engine.ReleaseHalted, match="unrecognized_checkout"):
        engine.git("status", "--porcelain", directory=Path("/root"))
    assert calls == []


def test_engine_git_uses_fixed_unprivileged_identity(monkeypatch):
    commands = []
    monkeypatch.setattr(engine, "execute", lambda argv, **kwargs: commands.append(argv) or engine.BASE)
    assert engine.git("rev-parse", "HEAD") == engine.BASE
    assert commands[0][:6] == (
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--"
    )
    assert "core.fsmonitor=false" in commands[0]


def test_engine_denies_non_root_even_before_lock(monkeypatch):
    monkeypatch.setattr(engine.os, "geteuid", lambda: 10001)
    with pytest.raises(engine.ReleaseHalted, match="requires_host_worker"):
        engine.run_release()


def test_engine_failure_does_not_switch_code_or_downgrade(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.os, "geteuid", lambda: 0)
    monkeypatch.setattr(engine, "LOCK_FILE", tmp_path / "lock")
    calls = []
    phases = []
    monkeypatch.setattr(engine, "state", lambda phase, **kw: phases.append(phase))
    monkeypatch.setattr(engine, "verify_checkout", lambda: None)
    monkeypatch.setattr(engine, "service_health", lambda: None)
    monkeypatch.setattr(engine, "record_counts", lambda: (14, 100, 14))
    monkeypatch.setattr(engine, "protected_script", lambda: None)
    monkeypatch.setattr(engine, "latest_backup", lambda: tmp_path / "backup.dump")
    monkeypatch.setattr(engine, "cli", lambda action, **kw: (
        "v14_seasons" if action == "db-revision" else "ok"
    ))

    def fake_execute(argv, **kwargs):
        calls.append(argv)
        if "v15-migration-rehearsal.sh" in " ".join(argv):
            raise engine.ReleaseHalted("rehearsal_failed")
        return ""

    monkeypatch.setattr(engine, "execute", fake_execute)
    with pytest.raises(engine.ReleaseHalted, match="rehearsal_failed"):
        engine.run_release()
    assert "halted" in phases
    assert "switching_code" not in phases
    assert all("/usr/bin/git" not in argv for argv in calls)
    assert all("db-upgrade" not in argv for argv in calls)


def test_unit_never_modifies_original_readonly_gateway():
    service = (Path(__file__).resolve().parents[1] /
               "deploy/ops/crew-deploy.service").read_text()
    gateway = (Path(__file__).resolve().parents[1] /
               "deploy/ops/crew-ops.service").read_text()
    assert "User=root" in service
    assert "User=crew" in gateway
    assert "NoNewPrivileges=yes" in gateway
    assert "NoNewPrivileges=no" in service
    assert "ExecStart=/usr/bin/python3 -I -B /usr/local/libexec/crew-deploy/release_broker.py" in service
    assert "ExecStart=/usr/bin/python3 -B /usr/local/libexec/crew-ops/host_service.py" in gateway


def test_engine_contains_no_automatic_db_downgrade_or_restore():
    source = (Path(__file__).resolve().parents[1] /
              "deploy/ops/release_engine.py").read_text()
    assert '("reset", "--hard", RELEASE)' in source
    assert '"db-upgrade"' in source
    assert '"db-downgrade"' not in source
    assert '"pg_restore"' not in source
    assert 'state("succeeded")' in source


def test_release_sequence_rehearses_fresh_backup_before_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.os, "geteuid", lambda: 0)
    monkeypatch.setattr(engine, "LOCK_FILE", tmp_path / "lock")
    phases = []
    calls = []
    monkeypatch.setattr(engine, "state",
                        lambda phase, **kwargs: phases.append(phase))
    monkeypatch.setattr(engine, "verify_checkout", lambda: None)
    monkeypatch.setattr(engine, "service_health", lambda: None)
    monkeypatch.setattr(engine, "protected_script", lambda: None)
    monkeypatch.setattr(engine, "record_counts", lambda: (14, 100, 14))
    monkeypatch.setattr(engine, "latest_backup", lambda: tmp_path / "fresh.dump")

    def fake_cli(action, *, cwd):
        calls.append(("cli", action, str(cwd)))
        if action == "db-revision":
            if "switching_code" in phases:
                return "v15_badges"
            return "v15_badges" if cwd == engine.STAGE else "v14_seasons"
        return "ok"

    monkeypatch.setattr(engine, "cli", fake_cli)
    monkeypatch.setattr(engine, "git", lambda *args, **kwargs: (
        engine.RELEASE if args == ("rev-parse", "HEAD") else "updated"
    ))
    monkeypatch.setattr(engine, "execute",
                        lambda argv, **kwargs: calls.append(("cmd", tuple(argv))) or "")
    engine.run_release()
    assert phases == ["validating", "backing_up", "backed_up", "rehearsing",
                      "migrating", "switching_code", "succeeded"]
    backup_index = next(i for i, call in enumerate(calls)
                        if call[0] == "cmd" and "crew-backup.service" in call[1])
    rehearse_index = next(i for i, call in enumerate(calls)
                           if call[0] == "cmd" and str(engine.REHEARSAL) in call[1])
    migrate_index = next(i for i, call in enumerate(calls)
                         if call[0] == "cli" and call[1] == "db-upgrade")
    assert backup_index < rehearse_index < migrate_index


def test_rehearsal_uses_fresh_dump_and_never_prod_restore():
    source = (Path(__file__).resolve().parents[1] /
              "deploy/v15-migration-rehearsal.sh").read_text()
    assert "NOW - BACKUP_TIME <= 1200" in source
    assert 'sha256sum --status --check "$BACKUP.sha256"' in source
    assert 'pg_restore --exit-on-error --no-owner --no-privileges' in source
    assert '--dbname="$TEST_DB" "$BACKUP"' in source
    assert '[[ "$existing" == 0 ]]' in source
    assert 'pg_admin dropdb "$TEST_DB"' in source
