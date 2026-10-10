"""Fixed CREW v15 production release engine (host-installed candidate).

SECURITY: no user-supplied shell, repo, database, path, or commit. This module
must be copied into a root-owned non-writable installation outside /opt/crew.
It is NOT a general deployment tool. Operator approval is verified by the
separate broker and consumed BEFORE this engine is invoked.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time

BASE = "c5a9275629ba4389c2b66a14b61a523868d40673"
RELEASE = "f4a35026d1df0e86e987d4bca310b8d32aed4134"
PRODUCTION = Path("/opt/crew")
STAGE = Path("/opt/crew-v15-rehearsal")
BACKUPS = Path("/var/backups/crew")
REHEARSAL = Path("/usr/local/libexec/crew-deploy/v15-migration-rehearsal.sh")
STATE_FILE = Path("/var/lib/crew-deploy/state.json")
LOCK_FILE = Path("/run/lock/crew-deploy-v15.lock")
APP_ROLE = "crew"
TIMEOUT = 120


class ReleaseHalted(RuntimeError):
    """Safe-to-display failure code; never expose command stderr or secrets."""


def execute(argv: tuple[str, ...], *, timeout: int = TIMEOUT) -> str:
    """Execute a developer-defined argv, never a caller-provided command."""
    try:
        finished = subprocess.run(
            argv, input="", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=timeout, check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseHalted("step_unavailable_or_timed_out") from exc
    if finished.returncode:
        raise ReleaseHalted("step_failed")
    return finished.stdout.strip()[:1000]


def git(*args: str, directory: Path = PRODUCTION) -> str:
    if directory not in (PRODUCTION, STAGE):
        raise ReleaseHalted("unrecognized_checkout")
    if args not in (
        ("rev-parse", "HEAD"), ("status", "--porcelain"),
        ("reset", "--hard", RELEASE),
    ):
        raise ReleaseHalted("git_operation_rejected")
    return execute((
        "/usr/sbin/runuser", "-u", APP_ROLE, "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={directory}",
        "-c", "core.fsmonitor=false", "-C", str(directory), *args,
    ))


def require(cond: bool, name: str) -> None:
    if not cond:
        raise ReleaseHalted(name)


def verify_checkout() -> None:
    require(git("rev-parse", "HEAD") == BASE, "unexpected_production_commit")
    require(git("status", "--porcelain") == "", "production_dirty")
    require(git("rev-parse", "HEAD", directory=STAGE) == RELEASE,
            "unexpected_staging_commit")
    require(git("status", "--porcelain", directory=STAGE) == "", "staging_dirty")


def protected_script() -> None:
    import stat
    for file in (REHEARSAL,):
        s = file.lstat()
        require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and
                not (s.st_mode & (stat.S_IWGRP | stat.S_IWOTH)),
                "unsafe_rehearsal_script")
    p = REHEARSAL.parent.lstat()
    require(stat.S_ISDIR(p.st_mode) and p.st_uid == 0 and
            not (p.st_mode & (stat.S_IWGRP | stat.S_IWOTH)),
            "unsafe_rehearsal_directory")


def latest_backup() -> Path:
    import hashlib
    candidates = list(BACKUPS.glob("crew_*.dump"))
    require(bool(candidates), "backup_missing")
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    require(not latest.is_symlink(), "backup_symlink")
    require(time.time() - latest.stat().st_mtime < 20 * 60,
            "backup_not_fresh")
    sha_file = Path(str(latest) + ".sha256")
    expected = sha_file.read_text(encoding="utf-8").split()[0]
    require(bool(re.fullmatch("[0-9a-f]{64}", expected)), "backup_checksum_invalid")
    digest = hashlib.sha256()
    with latest.open("rb") as fh:
        for part in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(part)
    require(digest.hexdigest() == expected, "backup_checksum_mismatch")
    execute(("/usr/bin/pg_restore", "--list", str(latest)), timeout=60)
    return latest


def cli(action: str, *, cwd: Path) -> str:
    require(action in ("db-revision", "db-integrity-check", "db-upgrade"),
            "cli_not_allowed")
    require(cwd in (PRODUCTION, STAGE), "invalid_cli_directory")
    return execute((
        "/usr/bin/systemd-run", "--quiet", "--wait", "--pipe", "--collect",
        "-p", "User=crew", "-p", "Group=www-data",
        "-p", f"WorkingDirectory={cwd}",
        "-p", "EnvironmentFile=/etc/crew/crew.env",
        "/usr/bin/env", "CREW_ENV=production", "AUTO_DB_MIGRATE=false",
        "PYTHONDONTWRITEBYTECODE=1",
        "/opt/crew/.venv/bin/flask", "--app", "app", action,
    ), timeout=180)


def record_counts() -> tuple[int, int, int]:
    """Read only key production counters over the local root-managed socket."""
    sql = (
        "SELECT (SELECT count(*) FROM profiles),"
        "(SELECT count(*) FROM game_completions),"
        "(SELECT count(*) FROM user_stats)"
    )
    raw = execute((
        "/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/env",
        "-u", "PGHOST", "-u", "PGPORT", "-u", "PGDATABASE",
        "-u", "PGUSER", "-u", "PGPASSWORD",
        "/usr/bin/psql", "-X", "-v", "ON_ERROR_STOP=1",
        "-d", "crew_prod", "-Atqc", sql,
    ))
    parts = raw.split("|")
    require(len(parts) == 3 and all(v.isdecimal() for v in parts),
            "unreadable_record_counts")
    return tuple(int(v) for v in parts)


def service_health() -> None:
    execute(("/usr/bin/systemctl", "is-active", "--quiet", "crew.service"))
    execute((
        "/usr/bin/curl", "--silent", "--show-error", "--fail",
        "--max-time", "15",
        "--unix-socket", "/run/crew/crew.sock",
        "-H", "Host: cadacrew.fun",
        "http://localhost/health/ready",
    ), timeout=20)


def state(phase: str, *, detail: str = "") -> None:
    """Atomic root-only status file. No sensitive process output."""
    STATE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "phase": phase, "detail": detail,
        "release_sha": RELEASE,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    tmp = STATE_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream)
    os.replace(tmp, STATE_FILE)


def run_release() -> None:
    """Do not call until separate root-only approval broker consumed approval."""
    if os.geteuid() != 0:
        raise ReleaseHalted("requires_host_worker")
    with LOCK_FILE.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReleaseHalted("deployment_already_running") from exc
        try:
            state("validating")
            verify_checkout()
            service_health()
            require(cli("db-revision", cwd=PRODUCTION).endswith("v14_seasons"),
                    "unexpected_database_revision")
            cli("db-integrity-check", cwd=PRODUCTION)
            before_records = record_counts()

            state("backing_up")
            execute(("/usr/bin/systemctl", "start", "crew-backup.service"), timeout=180)
            current_backup = latest_backup()
            state("backed_up", detail=current_backup.name)

            # Rehearse the exact fresh backup, including current player rows,
            # before touching the live schema. The fixed script chooses the
            # newest checksum-verified backup internally, never from MCP input.
            state("rehearsing")
            protected_script()
            execute(("/bin/bash", str(REHEARSAL)), timeout=660)

            # Source application code is run only as the unprivileged service
            # user. An additive migration precedes the app-code switch.
            state("migrating")
            cli("db-upgrade", cwd=STAGE)
            require(cli("db-revision", cwd=STAGE).endswith("v15_badges"),
                    "migration_revision_unverified")

            state("switching_code")
            git("reset", "--hard", RELEASE)
            execute(("/usr/bin/systemctl", "restart", "crew.service"), timeout=90)
            service_health()
            require(git("rev-parse", "HEAD") == RELEASE, "deployed_commit_mismatch")
            require(cli("db-revision", cwd=PRODUCTION).endswith("v15_badges"),
                    "deployed_database_revision_mismatch")
            after_records = record_counts()
            require(all(after >= before for after, before in zip(after_records, before_records)),
                    "production_record_counts_decreased")
            state("succeeded")
        except (OSError, ReleaseHalted) as exc:
            # No automatic database downgrade, restore, or code rollback.
            # A failed release is an operator-reviewed incident.
            code = exc.args[0] if isinstance(exc, ReleaseHalted) else "filesystem_error"
            state("halted", detail=str(code))
            raise
        except Exception:
            # Fail closed on all unexpected interpreter errors, too. Never
            # include exception text, which might contain sensitive data.
            state("halted", detail="unexpected_worker_error")
            raise


if __name__ == "__main__":
    try:
        run_release()
    except ReleaseHalted as err:
        print(f"RELEASE HALTED: {err}", flush=True)
        raise SystemExit(1)
