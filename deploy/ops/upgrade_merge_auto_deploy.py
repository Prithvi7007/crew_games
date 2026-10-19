"""One-time, fail-closed upgrade of the root-installed CREW release watcher.

Run ONLY from a reviewed, owner-merged GitHub main commit with passing
post-merge CI. This upgrades the watcher policy pin; it does NOT deploy CREW,
change database state, clear a previous failure, or start the timer.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

HOST = Path("/usr/local/libexec/crew-maint/merge_auto_deploy.py")
BACKUP = Path("/var/lib/crew-maint/merge_auto_before_v16.py")
TIMER = "crew-auto-release.timer"
SERVICE = "crew-auto-release.service"
SHA = re.compile(r"^[0-9a-f]{40}$")
BEFORE = b'DB_REVISION = "v15_badges"'
AFTER = b'DB_REVISION = "v16_trophy_tour"'


class UpgradeRefused(Exception):
    """Fail closed without changing the root-owned controller."""


def fixed(*arguments: str, timeout: int = 120) -> bytes:
    try:
        done = subprocess.run(
            list(arguments), input=b"", stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False, timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpgradeRefused("fixed_command_unavailable") from exc
    if done.returncode:
        raise UpgradeRefused("fixed_command_failed")
    return done.stdout


def git(*arguments: str) -> bytes:
    return fixed(
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", "safe.directory=/opt/crew",
        "-C", "/opt/crew", *arguments,
    )


def stopped(unit: str) -> bool:
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", unit],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpgradeRefused("systemd_status_unavailable") from exc
    return result.returncode != 0


def validate_guard_upgrade(installed: bytes, reviewed: bytes) -> None:
    """Allow ONLY the single reviewed DB revision-pin change."""
    if installed.count(BEFORE) != 1 or AFTER in installed:
        raise UpgradeRefused("unexpected_installed_watcher_version")
    if reviewed != installed.replace(BEFORE, AFTER, 1):
        raise UpgradeRefused("reviewed_watcher_has_other_changes")


def trusted_watcher():
    info = HOST.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o400):
        raise UpgradeRefused("unsafe_installed_watcher")
    spec = importlib.util.spec_from_file_location("crew_installed_auto_watcher", HOST)
    if spec is None or spec.loader is None:
        raise UpgradeRefused("installed_watcher_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_install(reviewed: bytes) -> None:
    stage = HOST.with_name(".merge-auto-v16-" + uuid.uuid4().hex)
    fd = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(reviewed)
            file.flush()
            os.fsync(file.fileno())
        os.chown(stage, 0, 0)
        os.chmod(stage, 0o400)
        os.replace(stage, HOST)
    finally:
        stage.unlink(missing_ok=True)


def upgrade(reviewed_sha: str) -> None:
    if (os.geteuid() != 0 or not sys.stdin.isatty()
            or not SHA.fullmatch(reviewed_sha)):
        raise UpgradeRefused("root_tty_and_reviewed_merge_sha_required")
    if not stopped(TIMER) or not stopped(SERVICE):
        raise UpgradeRefused("stop_auto_timer_and_service_first")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise UpgradeRefused("previous_v16_upgrade_backup_exists")

    watcher = trusted_watcher()
    maint = watcher.maint
    lock_fd = os.open(watcher.LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UpgradeRefused("release_watcher_busy") from exc

        if maint.APPROVAL.exists() or maint.APPROVAL.is_symlink():
            raise UpgradeRefused("manual_release_approval_pending")
        watcher.assert_clean_checkout(maint.CREW)
        installed = HOST.read_bytes()
        if not stopped(TIMER) or not stopped(SERVICE):
            raise UpgradeRefused("auto_release_started_during_review")

        # Verify the review source exists in the exact owner-controlled main
        # history and independently passed merged-main CI.
        git("fetch", "--no-tags", "origin", "refs/heads/main")
        github_main = watcher.main_sha()
        if git("rev-parse", "FETCH_HEAD").decode().strip() != github_main:
            raise UpgradeRefused("github_main_mismatch")
        git("merge-base", "--is-ancestor", reviewed_sha, github_main)
        if git("rev-parse", reviewed_sha).decode().strip() != reviewed_sha:
            raise UpgradeRefused("reviewed_sha_not_present")
        watcher.merged_pr_number(reviewed_sha)
        watcher.verify_ci(reviewed_sha)
        proposed = git("show", reviewed_sha + ":deploy/ops/merge_auto_deploy.py")
        validate_guard_upgrade(installed, proposed)

        if (maint.database_summary().get("revision") != "v16_trophy_tour"
                or not maint.service_active("crew.service")
                or not maint.socket_health()):
            raise UpgradeRefused("live_revision_or_health_mismatch")

        # Preserve any previous failed/blocked state. Clearing release
        # failures always requires a separate human-reviewed procedure.
        phase = watcher.state_read().get("phase", "not_recorded")
        print("CREW AUTO RELEASE WATCHER — REVIEWED DB REVISION UPGRADE")
        print("Reviewed merge:", reviewed_sha)
        print("Installed watcher SHA256:", hashlib.sha256(installed).hexdigest())
        print("Replacement SHA256:", hashlib.sha256(proposed).hexdigest())
        print("Prior watcher state:", phase)
        print("Does not deploy, start the timer, or clear failed state.")
        if input("Type 'UPGRADE CREW WATCHER V16' to continue: ").strip() != "UPGRADE CREW WATCHER V16":
            raise UpgradeRefused("operator_declined")
        if not stopped(TIMER) or not stopped(SERVICE):
            raise UpgradeRefused("auto_release_started_during_review")

        fd = os.open(BACKUP, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "wb") as out:
            out.write(installed)
            out.flush()
            os.fsync(out.fileno())
        os.chown(BACKUP, 0, 0)
        os.chmod(BACKUP, 0o400)
        atomic_install(proposed)
        print("Root-owned watcher updated. Backup retained:", BACKUP)
        print("Timer remains stopped. Diagnose previous watcher failures before re-enabling.")
    finally:
        os.close(lock_fd)


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise UpgradeRefused("exact_reviewed_merge_sha_required")
        upgrade(sys.argv[1])
        return 0
    except (UpgradeRefused, OSError, ValueError) as exc:
        print("Upgrade refused:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
