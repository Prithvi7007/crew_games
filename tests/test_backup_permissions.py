from pathlib import Path


def test_backup_permissions_allow_postgres_restore_verification():
    root = Path(__file__).resolve().parents[1]
    script = (root / "deploy" / "backup-postgres.sh").read_text(encoding="utf-8")

    assert "umask 077" in script
    assert 'install -d -m 0750 -o root -g postgres "$BACKUP_DIR"' in script
    assert 'chown root:postgres "$FINAL"' in script
    assert 'chmod 0640 "$FINAL"' in script
