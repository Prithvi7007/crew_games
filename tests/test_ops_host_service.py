"""Safety tests for the proposed, uninstalled CREW operations host gateway."""

import hashlib
import re
import time

from deploy.ops import host_service as ops


def test_rejects_arbitrary_commands_and_unknown_arguments():
    service = ops.Operations()
    for request in (
        {"operation": "shell", "command": "rm -rf /"},
        {"operation": "deploy_release", "release_sha": "a" * 40},
        {"operation": "release_preflight", "command": "whoami"},
        {"operation": "start_v15_rehearsal", "database": "crew_prod"},
        ["release_preflight"],
        {"operation": 1},
    ):
        reply = service.handle(request)
        assert reply["ok"] is False
    capabilities = service.handle({"operation": "capabilities"})
    assert capabilities["ok"] is True
    assert capabilities["deployment_enabled"] is False
    assert "deploy_release" not in capabilities["operations"]


def test_preflight_checks_exact_shas_and_verifies_checkpoint(monkeypatch, tmp_path):
    source = tmp_path / "backup.dump"
    copy = tmp_path / "checkpoint.dump"
    checksum = tmp_path / "backup.dump.sha256"
    source.write_bytes(b"synthetic data")
    copy.write_bytes(b"synthetic data")
    checksum.write_text(hashlib.sha256(source.read_bytes()).hexdigest() + "  backup.dump\n")
    monkeypatch.setattr(ops, "BACKUP", source)
    monkeypatch.setattr(ops, "CHECKPOINT", copy)

    def successful_commands(*args, timeout=8):
        if args[-2:] == ("rev-parse", "HEAD"):
            return True, (ops.EXPECTED_PRODUCTION if not any("crew-v15-rehearsal" in a for a in args)
                          else ops.EXPECTED_RELEASE)
        if args[-2:] == ("status", "--porcelain"):
            return True, ""
        if args[0] == "/usr/bin/pg_restore":
            return True, ""
        raise AssertionError(args)

    monkeypatch.setattr(ops, "run_fixed", successful_commands)
    assert ops.preflight()["ready"]

    copy.write_bytes(b"modified")
    result = ops.preflight()
    assert not result["ready"]
    assert not result["checks"]["checkpoint_matches_original"]


def test_preflight_blocks_dirty_worktree(monkeypatch, tmp_path):
    source = tmp_path / "backup.dump"
    checkpoint = tmp_path / "checkpoint.dump"
    source.write_bytes(b"x")
    checkpoint.write_bytes(b"x")
    (tmp_path / "backup.dump.sha256").write_text(
        hashlib.sha256(b"x").hexdigest() + "  backup.dump\n"
    )
    monkeypatch.setattr(ops, "BACKUP", source)
    monkeypatch.setattr(ops, "CHECKPOINT", checkpoint)

    def command(*args, timeout=8):
        if args[-2:] == ("rev-parse", "HEAD"):
            return True, (ops.EXPECTED_RELEASE if any("crew-v15-rehearsal" in a for a in args)
                          else ops.EXPECTED_PRODUCTION)
        if args[-2:] == ("status", "--porcelain"):
            return True, " M untracked" if any("crew-v15-rehearsal" in a for a in args) else ""
        return True, ""

    monkeypatch.setattr(ops, "run_fixed", command)
    assert not ops.preflight()["ready"]
    assert not ops.preflight()["checks"]["staging_clean"]


def test_rehearsal_denied_without_host_enablement(monkeypatch):
    service = ops.Operations()
    monkeypatch.setattr(ops, "rehearsal_enabled", lambda: False)
    monkeypatch.setattr(ops, "is_root_owned_rehearsal_script", lambda: True)
    assert service.handle({"operation": "start_v15_rehearsal"}) == {
        "ok": False, "error": "rehearsal_not_enabled"
    }
    assert not service.active


def test_rehearsal_requires_passing_preflight(monkeypatch):
    service = ops.Operations()
    monkeypatch.setattr(ops, "rehearsal_enabled", lambda: True)
    monkeypatch.setattr(ops, "is_root_owned_rehearsal_script", lambda: True)
    monkeypatch.setattr(ops, "preflight", lambda: {"ready": False})
    assert service.handle({"operation": "start_v15_rehearsal"}) == {
        "ok": False, "error": "preflight_failed"
    }
    assert not service.active


def test_completed_rehearsal_status_uses_opaque_job_id(monkeypatch):
    service = ops.Operations()
    monkeypatch.setattr(ops, "rehearsal_enabled", lambda: True)
    monkeypatch.setattr(ops, "is_root_owned_rehearsal_script", lambda: True)
    monkeypatch.setattr(ops, "preflight", lambda: {"ready": True})
    monkeypatch.setattr(ops, "run_fixed", lambda *args, **kwargs: (True, ""))

    started = service.handle({"operation": "start_v15_rehearsal"})
    assert started["ok"] is True
    job = started["job_id"]
    assert re.fullmatch(r"[a-f0-9]{32}", job)

    for _ in range(100):
        reply = service.handle({"operation": "rehearsal_status", "job_id": job})
        if reply["state"] == "passed":
            break
        time.sleep(0.01)

    assert reply == {"ok": True, "job_id": job, "state": "passed"}
    assert service.handle({"operation": "rehearsal_status", "job_id": "x"}) == {
        "ok": False, "error": "invalid_job_id"
    }
    assert service.handle({"operation": "rehearsal_status",
                           "job_id": "0" * 32}) == {
        "ok": False, "error": "unknown_job"
    }
