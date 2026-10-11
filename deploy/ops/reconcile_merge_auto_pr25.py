"""One-time, reviewed recovery of the PR #25 auto-release health race.

Root operator runs this file only after the fix PR has been human-merged
and its push-triggered main quality gate passed. It never writes the app
checkout, database or GitHub, and never forces an unverified release.
The only recoverable incident is the precise PR #25 health-probe race.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

HOST_WATCHER = Path("/usr/local/libexec/crew-maint/merge_auto_deploy.py")
REPO = Path("/opt/crew")
ARCHIVE = Path("/var/lib/crew-maint/merge_auto_pr25_failed_snapshot.json")
ORIGINAL_WATCHER_SHA256 = "6cc3a8e66e1c915ed1075c78571f9f60745eb4f3adb102379feee098d3956565"
FAILED_BASE = "f4a35026d1df0e86e987d4bca310b8d32aed4134"
FAILED_RELEASE = "5e53a3d3d281dd039fd5d1edd1bc550a2189f9b1"
SHA = re.compile(r"^[0-9a-f]{40}$")


class RecoveryRefused(Exception):
    pass


def fixed(*args: str, timeout: int = 120) -> bytes:
    try:
        task = subprocess.run(
            args, input=b"", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RecoveryRefused("fixed_command_unavailable") from exc
    if task.returncode:
        raise RecoveryRefused("fixed_command_failed")
    return task.stdout


def crew_git(*args: str) -> bytes:
    return fixed(
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={REPO}", "-C", str(REPO), *args,
    )


def auto_service_running() -> bool:
    result = subprocess.run(
        ["/usr/bin/systemctl", "is-active", "--quiet", "crew-auto-release.service"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=8, check=False,
    )
    return result.returncode == 0


def trusted_watcher():
    info = HOST_WATCHER.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o400):
        raise RecoveryRefused("unsafe_installed_watcher")
    spec = importlib.util.spec_from_file_location("crew_recovery_watcher", HOST_WATCHER)
    if spec is None or spec.loader is None:
        raise RecoveryRefused("watcher_unavailable")
    watcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watcher)
    return watcher


def validate_recovery(state: dict, manifest: dict, current_sha: str,
                      database: dict, assets: dict) -> None:
    """A *single* already-deployed and independently healthy incident only."""
    if not isinstance(state, dict) or not isinstance(manifest, dict):
        raise RecoveryRefused("invalid_recovery_state")
    if (state.get("phase") != "failed"
            or state.get("base") != FAILED_BASE
            or state.get("release") != FAILED_RELEASE
            or state.get("reviewed_pr") != 25
            or current_sha != FAILED_RELEASE):
        raise RecoveryRefused("wrong_failed_release")
    if (manifest.get("base") != FAILED_BASE
            or manifest.get("release") != FAILED_RELEASE
            or manifest.get("reviewed_pr") != 25
            or manifest.get("db_revision") != "v15_badges"):
        raise RecoveryRefused("release_manifest_disagrees")
    if (database.get("revision") != "v15_badges"
            or any(type(database.get(k)) is not int or database[k] < lower
                   for k, lower in (("profiles", 14), ("game_completions", 111),
                                    ("user_stats", 14)))):
        raise RecoveryRefused("database_integrity_unverified")
    for name in ("player.js", "player.css"):
        entry = assets.get(name)
        if (not isinstance(entry, dict) or not entry.get("present")
                or entry.get("nginx_user_readable") is not True
                or not str(entry.get("local_https", "")).startswith("200|")):
            raise RecoveryRefused("live_assets_unverified")


def atomic_archive(payload: dict) -> None:
    fd = os.open(ARCHIVE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(ARCHIVE, 0, 0)
    os.chmod(ARCHIVE, 0o600)


def atomic_install(source: bytes) -> None:
    stage = HOST_WATCHER.with_name(".merge-auto-recovery-" + uuid.uuid4().hex)
    fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(stage, 0, 0)
        os.chmod(stage, 0o400)
        os.replace(stage, HOST_WATCHER)
    finally:
        stage.unlink(missing_ok=True)


def recover(reviewed: str) -> None:
    if (os.geteuid() != 0 or not sys.stdin.isatty()
            or not SHA.fullmatch(reviewed)):
        raise RecoveryRefused("root_interactive_reviewed_sha_required")

    watcher = trusted_watcher()
    maintenance = watcher.maint
    if (ARCHIVE.exists() or ARCHIVE.is_symlink()
            or maintenance.APPROVAL.exists() or maintenance.APPROVAL.is_symlink()):
        raise RecoveryRefused("existing_recovery_or_manual_approval")
    if auto_service_running():
        raise RecoveryRefused("auto_release_running")

    # Confirm the new source is an owner-merged commit on GitHub main with
    # successful *post-merge* CI; not just a local branch or green PR build.
    crew_git("fetch", "--no-tags", "origin", "refs/heads/main")
    if crew_git("rev-parse", "FETCH_HEAD").decode().strip() != reviewed:
        raise RecoveryRefused("reviewed_sha_not_main_tip")
    if watcher.main_sha() != reviewed:
        raise RecoveryRefused("github_main_tip_changed")
    watcher.merged_pr_number(reviewed)
    watcher.verify_ci(reviewed)

    prior = HOST_WATCHER.read_bytes()
    if hashlib.sha256(prior).hexdigest() != ORIGINAL_WATCHER_SHA256:
        raise RecoveryRefused("installed_watcher_not_original_reviewed_version")
    proposed = crew_git("show", reviewed + ":deploy/ops/merge_auto_deploy.py")
    if (not 1000 <= len(proposed) <= 100000
            or b"def restart_crew_with_readiness()" not in proposed
            or proposed == prior):
        raise RecoveryRefused("reviewed_readiness_fix_missing")

    # Require journal evidence for the precise failure. Do not reconcile a
    # different failure that merely left the app code on the target commit.
    fixed("/usr/bin/journalctl", "-u", "crew-auto-release.service",
          "--no-pager", "-o", "cat", "--grep", "post_restart_health_failed",
          "-n", "3", timeout=20)

    def verify_current() -> dict:
        state = watcher.state_read()
        watcher.check_existing_manifest(state)
        manifest = json.loads(watcher.MANIFEST.read_text(encoding="utf-8"))
        watcher.assert_clean_checkout(maintenance.CREW)
        live = watcher.sha(maintenance.git_sha())
        if (not maintenance.service_active("crew.service")
                or not maintenance.service_active("nginx.service")
                or not maintenance.socket_health()):
            raise RecoveryRefused("production_readiness_not_confirmed")
        database = maintenance.database_summary()
        assets = maintenance.assets_summary()
        validate_recovery(state, manifest, live, database, assets)
        action = maintenance.maintenance_status().get("last_action", {})
        if isinstance(action, dict) and action.get("phase") in ("queued", "running"):
            raise RecoveryRefused("maintenance_is_busy")
        if watcher.merged_pr_number(live) != 25:
            raise RecoveryRefused("old_merge_provenance_unverified")
        watcher.verify_ci(live)
        return state

    state = verify_current()
    print("CREW PR #25 — VERIFIED POST-RESTART RECOVERY")
    print("Failed release:", FAILED_BASE[:7], "->", FAILED_RELEASE[:7])
    print("Live app:", FAILED_RELEASE[:7], "healthy, database and assets verified")
    print("Reviewed repair:", reviewed)
    print("New watcher SHA-256:", hashlib.sha256(proposed).hexdigest())
    print("Archives the failed state, installs the reviewed bounded readiness")
    print("check, and reconciles only the verified PR #25 incident.")
    print("It DOES NOT restart the app, change code in /opt/crew, or write DB.")
    print("The next timer tick may deploy already-merged PRs with green CI.")
    if input("Type 'RECONCILE CREW PR25' to proceed: ") != "RECONCILE CREW PR25":
        raise RecoveryRefused("recovery_not_confirmed")

    fixed("/usr/bin/systemctl", "stop", "crew-auto-release.timer")
    lock_fd = os.open(watcher.LOCK_FILE,
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # The service must not be running; a stopped timer alone does not
        # necessarily stop a release already underway.
        if auto_service_running():
            raise RecoveryRefused("auto_release_running")
        state = verify_current()
        # Preserve exact prior failure record before changing any state.
        atomic_archive({
            "previous_state": state,
            "observed_failure": "post_restart_health_failed",
            "reviewed_repair_commit": reviewed,
            "reconciled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        atomic_install(proposed)
        maintenance._write_json(watcher.STATE, {
            **state, "phase": "succeeded", "reconciled_from": "failed",
            "reconciled_reason": "post_restart_health_failed",
            "reconciled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repair_sha": reviewed,
        })
    finally:
        os.close(lock_fd)
    fixed("/usr/bin/systemctl", "start", "crew-auto-release.timer")
    print("Reconciled PR #25. Reviewed watcher installed, timer resumed.")
    print("Next run will independently re-check PR merges, CI, backup and health.")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RecoveryRefused("expected_exact_reviewed_sha")
        recover(sys.argv[1])
    except (RecoveryRefused, OSError, ValueError) as error:
        print("CREW recovery refused:", str(error), file=sys.stderr)
        sys.exit(1)
