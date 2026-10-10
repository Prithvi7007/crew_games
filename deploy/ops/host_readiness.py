"""Read-only VPS acceptance inspection for the CREW operations gateway.

This tool does not install services, run a migration, load any secrets into the
process, open production DB connections, or modify system configuration.
It prints only redacted PASS/FAIL/INFO results.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import subprocess
import sys

PROD = Path("/opt/crew")
STAGE = Path("/opt/crew-v15-rehearsal")
BACKUP = Path("/var/backups/crew/crew_20261010T001254Z.dump")
CHECKPOINT = Path("/var/backups/crew/release-checkpoints/pre_v15_20261010T001254Z.dump")
CONFIG = Path("/etc/crew/crew.env")
PROD_SHA = "c5a9275629ba4389c2b66a14b61a523868d40673"
RELEASE_SHA = "f4a35026d1df0e86e987d4bca310b8d32aed4134"


def command(*argv: str, timeout: int = 10) -> tuple[bool, str]:
    """Run fixed argument lists, no shell or inherited secret environment."""
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
            check=False,
        )
        return result.returncode == 0, result.stdout.strip()[:200]
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def git_status(path: Path, *, as_crew: bool) -> tuple[bool, bool]:
    """Never inspect either shared-metadata worktree with root Git privileges."""
    if path not in (PROD, STAGE):
        return False, False
    prefix = ("/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--")
    argv = (*prefix, "/usr/bin/git", "-c", f"safe.directory={path}",
            "-c", "core.fsmonitor=false", "-C", str(path))
    ok, commit = command(*argv, "rev-parse", "HEAD")
    clean_ok, changes = command(*argv, "status", "--porcelain")
    return ok and commit == (PROD_SHA if as_crew else RELEASE_SHA), clean_ok and not changes


def protected_file(path: Path) -> bool:
    """Require a root-owned, ordinary file and safe parent directory."""
    try:
        entry = path.lstat()
        parent = path.parent.lstat()
        return (
            stat.S_ISREG(entry.st_mode)
            and entry.st_uid == 0
            and not (entry.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
            and stat.S_ISDIR(parent.st_mode)
            and parent.st_uid == 0
            and not (parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
        )
    except OSError:
        return False


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def backup_valid() -> bool:
    try:
        checksum_file = Path(str(BACKUP) + ".sha256")
        assert protected_file(CHECKPOINT)
        expected = checksum_file.read_text(encoding="utf-8").split()[0]
        return (
            len(expected) == 64
            and all(c in "0123456789abcdef" for c in expected)
            and digest(BACKUP) == expected
            and digest(CHECKPOINT) == expected
            and command("/usr/bin/pg_restore", "--list", str(CHECKPOINT), timeout=30)[0]
        )
    except (AssertionError, OSError, IndexError, UnicodeError):
        return False


def postgres_safe() -> bool:
    """Check cluster on local socket, without reading CREW DATABASE_URL."""
    sql = (
        "SELECT current_setting('port'),"
        "(SELECT count(*) FROM pg_database WHERE datname='crew_prod'),"
        "(SELECT count(*) FROM pg_database WHERE datname='crew_v15_migration_test')"
    )
    ok, result = command(
        "/usr/sbin/runuser", "-u", "postgres", "--",
        "/usr/bin/env", "-u", "PGHOST", "-u", "PGPORT",
        "-u", "PGUSER", "-u", "PGPASSWORD", "-u", "PGDATABASE",
        "/usr/bin/psql", "-X", "-d", "postgres", "-Atqc", sql,
    )
    return ok and result == "5432|1|0"


def main() -> int:
    results = {
        "production pinned release": git_status(PROD, as_crew=True),
        "staged pinned release": git_status(STAGE, as_crew=False),
    }
    checks = {
        "production commit unchanged": results["production pinned release"][0],
        "production worktree clean": results["production pinned release"][1],
        "staged release pinned": results["staged pinned release"][0],
        "staged worktree clean": results["staged pinned release"][1],
        "production config file protected": protected_file(CONFIG),
        "recovery backup verified": backup_valid(),
        "local PostgreSQL and free scratch DB": postgres_safe(),
        "crew service active": command("/usr/bin/systemctl", "is-active", "--quiet", "crew.service")[0],
    }
    print("CREW Operations Gateway — READ-ONLY HOST PREFLIGHT")
    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
    # Optional items indicate what remains to install, not safety failures.
    group_ok, _ = command("/usr/bin/getent", "group", "crew-ops")
    unit_path = Path("/etc/systemd/system/crew-ops.service")
    print(f"INFO: operations group {'exists' if group_ok else 'not yet installed'}")
    print(f"INFO: operations service {'exists' if unit_path.exists() else 'not yet installed'}")
    socket = Path("/run/crew-ops/ops.sock")
    print(f"INFO: operations socket {'present' if socket.exists() else 'not yet present'}")
    if not all(checks.values()):
        print("STOP: fix failed checks before installing operations gateway.")
        return 1
    print("PASS: Host prerequisites inspected; gateway is NOT installed or enabled by this check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
