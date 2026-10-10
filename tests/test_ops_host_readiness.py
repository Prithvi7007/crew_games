"""Offline safety tests for the CREW host acceptance inspection."""

import hashlib
from pathlib import Path

from deploy.ops import host_readiness as h


def test_git_pins_sha_and_rejects_dirty_checkout(monkeypatch):
    seen = []

    def fixed(*argv, timeout=10):
        seen.append(argv)
        if argv[-2:] == ("rev-parse", "HEAD"):
            return True, h.PROD_SHA
        if argv[-2:] == ("status", "--porcelain"):
            return True, " M app/db.py"
        raise AssertionError(argv)

    monkeypatch.setattr(h, "command", fixed)
    assert h.git_status(Path("/opt/crew"), as_crew=True) == (True, False)
    assert seen[0][:6] == (
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--"
    )


def test_preserved_backup_requires_exact_hash_match(monkeypatch, tmp_path):
    original = tmp_path / "original.dump"
    copy = tmp_path / "checkpoint.dump"
    original.write_bytes(b"saved fake database")
    copy.write_bytes(b"saved fake database")
    (tmp_path / "original.dump.sha256").write_text(
        hashlib.sha256(original.read_bytes()).hexdigest() + " original.dump"
    )
    monkeypatch.setattr(h, "BACKUP", original)
    monkeypatch.setattr(h, "CHECKPOINT", copy)
    monkeypatch.setattr(h, "protected_file", lambda path: True)
    monkeypatch.setattr(h, "command", lambda *args, **kwargs: (True, ""))
    assert h.backup_valid()
    copy.write_bytes(b"tampered")
    assert not h.backup_valid()


def test_cluster_check_requires_local_postgres_and_unused_scratch(monkeypatch):
    monkeypatch.setattr(h, "command", lambda *args, **kwargs: (True, "5432|1|0"))
    assert h.postgres_safe()

    for response in ("5432|1|1", "5433|1|0", "5432|0|0", "5432|1|0\nextra"):
        monkeypatch.setattr(h, "command", lambda *args, **kwargs: (True, response))
        assert not h.postgres_safe()


def test_report_is_read_only_and_hides_secrets(monkeypatch, capsys):
    monkeypatch.setattr(h, "git_status", lambda *args, **kwargs: (True, True))
    monkeypatch.setattr(h, "protected_file", lambda path: True)
    monkeypatch.setattr(h, "backup_valid", lambda: True)
    monkeypatch.setattr(h, "postgres_safe", lambda: True)
    monkeypatch.setattr(h, "command", lambda *args, **kwargs: (True, ""))
    assert h.main() == 0
    captured = capsys.readouterr().out
    assert "PASS: recovery backup verified" in captured
    assert "gateway is NOT installed" in captured
    assert "DATABASE_URL" not in captured
    assert "SECRET_KEY" not in captured


def test_report_fails_closed_on_unverified_backup(monkeypatch, capsys):
    monkeypatch.setattr(h, "git_status", lambda *args, **kwargs: (True, True))
    monkeypatch.setattr(h, "protected_file", lambda path: True)
    monkeypatch.setattr(h, "backup_valid", lambda: False)
    monkeypatch.setattr(h, "postgres_safe", lambda: True)
    monkeypatch.setattr(h, "command", lambda *args, **kwargs: (True, ""))
    assert h.main() == 1
    assert "STOP: fix failed checks" in capsys.readouterr().out


def test_staged_git_inspection_uses_unprivileged_crew(monkeypatch):
    calls = []

    def command(*argv, timeout=10):
        calls.append(argv)
        if argv[-2:] == ("rev-parse", "HEAD"):
            return True, h.RELEASE_SHA
        return True, ""

    monkeypatch.setattr(h, "command", command)
    assert h.git_status(h.STAGE, as_crew=False) == (True, True)
    assert calls
    for call in calls:
        assert call[:6] == (
            "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--"
        )
        assert "core.fsmonitor=false" in call
        assert f"safe.directory={h.STAGE}" in call
