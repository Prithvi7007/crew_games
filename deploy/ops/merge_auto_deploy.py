"""CREW merged-PR code-only release watcher.

Root-installed, fixed-policy component. No caller-provided ref, command, path,
credentials, SQL, or approval bypass via the MCP socket. Runs from systemd timer.
The only release authority is a merged GitHub PR on main plus successful
post-merge CI on that exact commit. Never runs source code from the candidate.
"""
from __future__ import annotations

import fcntl
import importlib.util
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

if __package__:
    from . import maintenance_v2 as maint
else:
    # -I intentionally excludes the script directory from sys.path.
    trusted_path = Path("/usr/local/libexec/crew-maint/maintenance_v2.py")
    trusted_info = trusted_path.lstat()
    if (not stat.S_ISREG(trusted_info.st_mode) or trusted_info.st_uid != 0
            or stat.S_IMODE(trusted_info.st_mode) & 0o022):
        raise SystemExit("Untrusted root maintenance controller")
    spec = importlib.util.spec_from_file_location("crew_host_maint", trusted_path)
    if spec is None or spec.loader is None:
        raise SystemExit("Missing root maintenance controller")
    maint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maint)

REPOSITORY = "Prithvi7007/crew_games"
GITHUB_API = "https://api.github.com/repos/" + REPOSITORY
REMOTE_URLS = frozenset(("https://github.com/" + REPOSITORY + ".git",
                        "https://github.com/" + REPOSITORY))
REVIEWER = "Prithvi7007"
CI_WORKFLOW_ID = 358221353
REQUIRED_STEPS = frozenset((
    "Frontend build", "Verify committed frontend build", "Python tests",
    "Migration smoke test", "Dependency audit",
))
DB_REVISION = "v16_trophy_tour"
MAX_MERGES = 32
SHA = re.compile(r"^[0-9a-f]{40}$")
STATE = Path("/var/lib/crew-maint/merge_auto_state.json")
LOCK_FILE = Path("/var/lib/crew-maint/merge_auto.lock")
# Keep the manually approved MCP controller's root-owned manifest untouched.
# The watcher reuses its code-only engine with a separate root-only manifest
# in the already writable maintenance state directory.
MANUAL_MANIFEST = maint.RELEASE_MANIFEST
MANIFEST = maint.STATE_DIR / "merge_auto_manifest.json"


class Blocked(Exception):
    """Sanitized, fail-closed condition requiring operator attention."""


class Waiting(Exception):
    """No verified release yet; safe to retry on a later timer tick."""


def github_json(endpoint: str):
    """Only fixed GitHub REST endpoints, HTTPS + bounded UTF-8 JSON."""
    if not endpoint.startswith("/") or not re.fullmatch(r"/[A-Za-z0-9_./?=&-]+", endpoint):
        raise Blocked("invalid_github_endpoint")
    req = urllib.request.Request(
        GITHUB_API + endpoint,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "crew-verified-merge-watcher",
                 "X-GitHub-Api-Version": "2022-11-28"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            final_url = urlsplit(response.geturl())
            if final_url.scheme != 'https' or final_url.hostname != 'api.github.com':
                raise Blocked('unexpected_github_redirect')
            if response.status != 200:
                raise Waiting("github_evidence_unavailable")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise Blocked("github_response_too_large")
            return json.loads(data.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise Waiting("github_evidence_unavailable") from exc


def git(path: Path, *args: str, timeout: int = 120) -> str:
    if path not in (maint.CREW, maint.CANDIDATE):
        raise Blocked("unexpected_checkout")
    cmd = ["/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
           "/usr/bin/git", "-c", f"safe.directory={path}",
           "-c", "core.fsmonitor=false", "-C", str(path), *args]
    try:
        run = subprocess.run(
            cmd, input="", capture_output=True, text=True, check=False,
            timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Waiting("git_unavailable") from exc
    if run.returncode:
        raise Blocked("git_operation_failed")
    return run.stdout.strip()


def sha(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise Blocked("untrusted_commit")
    return value


def assert_clean_checkout(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != pwd.getpwnam('crew').pw_uid:
        raise Blocked("unsafe_checkout")
    if git(path, "remote", "get-url", "origin") not in REMOTE_URLS:
        raise Blocked("untrusted_git_remote")
    if git(path, "status", "--porcelain"):
        raise Blocked("dirty_checkout")


def main_sha() -> str:
    info = github_json("/git/ref/heads/main")
    return sha(info["object"]["sha"])


def merged_pr_number(commit: str) -> int:
    """Require exact GitHub merge SHA, target main, human maintainer merge."""
    linked = github_json("/commits/" + sha(commit) + "/pulls")
    if not isinstance(linked, list):
        raise Waiting("pull_request_evidence_unavailable")
    for item in linked[:20]:
        if not isinstance(item, dict) or item.get("merge_commit_sha") != commit:
            continue
        number = item.get("number")
        if not isinstance(number, int) or number < 1:
            continue
        pr = github_json("/pulls/" + str(number))
        base = pr.get("base") or {}
        repo = base.get("repo") or {}
        by = pr.get("merged_by") or {}
        if (pr.get("state") == "closed" and pr.get("merged_at")
                and pr.get("merge_commit_sha") == commit
                and pr.get("draft") is False
                and base.get("ref") == "main"
                and repo.get("full_name") == REPOSITORY
                and by.get("login") == REVIEWER):
            return number
    raise Blocked("commit_not_approved_pr_merge")


def verify_merge_chain(base: str, release: str) -> int:
    """Verify every first-parent change came from a human-merged PR."""
    first_parent = git(maint.CANDIDATE, "rev-list", "--first-parent",
                       "--reverse", base + ".." + release).splitlines()
    if not 1 <= len(first_parent) <= MAX_MERGES or first_parent[-1] != release:
        raise Blocked("unverified_merge_chain")
    last_pr = 0
    for commit in first_parent:
        last_pr = merged_pr_number(sha(commit))
    return last_pr


def verify_ci(release: str) -> None:
    """Do not trust a green PR check as a substitute for merged-main CI."""
    data = github_json("/actions/runs?per_page=100")
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        raise Waiting("ci_evidence_unavailable")
    relevant = [run for run in runs if isinstance(run, dict)
                and run.get("head_sha") == release
                and run.get("event") == "push"
                and run.get("head_branch") == "main"
                and run.get("workflow_id") == CI_WORKFLOW_ID]
    if len(relevant) != 1 or relevant[0].get("status") != "completed":
        raise Waiting("main_ci_not_finished")
    run = relevant[0]
    if run.get("conclusion") != "success":
        raise Blocked("main_ci_failed")
    run_id = run.get("id")
    if not isinstance(run_id, int) or run_id < 1:
        raise Blocked("invalid_ci_run")
    jobs = github_json(f"/actions/runs/{run_id}/jobs?per_page=100")
    items = jobs.get("jobs") if isinstance(jobs, dict) else None
    if not isinstance(items, list):
        raise Waiting("ci_jobs_unavailable")
    completed = [job for job in items if isinstance(job, dict)
                 and job.get("name") == "test-and-audit"
                 and job.get("conclusion") == "success"]
    if len(completed) != 1:
        raise Blocked("missing_successful_quality_gate")
    passed = {step.get("name") for step in completed[0].get("steps", [])
              if isinstance(step, dict) and step.get("conclusion") == "success"}
    if not REQUIRED_STEPS.issubset(passed):
        raise Blocked("required_ci_steps_missing")


def state_read() -> dict:
    if not STATE.exists():
        return {}
    info = STATE.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise Blocked("unsafe_auto_state")
    try:
        result = json.loads(STATE.read_text())
    except (OSError, ValueError) as exc:
        raise Blocked("invalid_auto_state") from exc
    if not isinstance(result, dict):
        raise Blocked("invalid_auto_state")
    return result


def state_write(data: dict) -> None:
    maint._write_json(STATE, data)


def check_existing_manifest(state: dict) -> None:
    if MANUAL_MANIFEST.exists() or MANUAL_MANIFEST.is_symlink():
        raise Blocked('manual_release_manifest_present')
    if not MANIFEST.exists() and not MANIFEST.is_symlink():
        if state.get("manifest_sha"):
            raise Blocked("manifest_removed_unexpectedly")
        return
    info = MANIFEST.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o400:
        raise Blocked("unsafe_existing_manifest")
    expected = state.get("manifest_sha")
    if not isinstance(expected, str) or hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != expected:
        raise Blocked("external_release_manifest_present")


def write_manifest(base: str, release: str, pr: int, state: dict) -> dict:
    check_existing_manifest(state)
    body = json.dumps(
        {"format": 1, "kind": "code_only", "base": base, "release": release,
         "db_revision": DB_REVISION, "reviewed_pr": pr},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    name = MANIFEST.with_name(".merge-release-" + uuid.uuid4().hex)
    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.chown(name, 0, 0)
        os.chmod(name, 0o400)
        os.replace(name, MANIFEST)
    finally:
        name.unlink(missing_ok=True)
    updated = {**state, "manifest_sha": hashlib.sha256(body).hexdigest()}
    state_write(updated)
    return updated


def restart_crew_with_readiness() -> None:
    """Wait for the app socket after systemd reports restart success.

    systemctl restart can complete before the app binds its Unix socket.
    Keep a bounded, fail-closed readiness window; never skip the actual probe.
    """
    if not maint.fixed("/usr/bin/systemctl", "restart", "crew.service", timeout=90)[0]:
        raise maint.Refused("restart_failed")
    for attempt in range(20):
        if maint.service_active("crew.service") and maint.socket_health():
            return
        if attempt < 19:
            time.sleep(2)
    raise maint.Refused("post_restart_health_failed")


def run_once() -> dict:
    if os.geteuid() != 0:
        raise Blocked("root_only")
    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise Waiting("another_auto_release_running") from exc
    try:
        return _run_once_locked()
    finally:
        os.close(lock_fd)


def _run_once_locked() -> dict:
    state = state_read()
    if state.get("phase") in ("failed", "running", "blocked"):
        raise Blocked("previous_release_needs_review")
    if maint.APPROVAL.exists() or maint.APPROVAL.is_symlink():
        raise Waiting("manual_approval_pending")
    action = maint.maintenance_status().get("last_action", {})
    if isinstance(action, dict) and action.get("phase") in ("queued", "running"):
        raise Waiting("maintenance_operation_running")
    live = sha(maint.git_sha())
    if maint.database_summary().get("revision") != DB_REVISION:
        raise Blocked("schema_release_requires_manual_plan")
    if not maint.service_active("crew.service") or not maint.socket_health():
        raise Waiting("production_unhealthy")
    target = main_sha()
    if target == live:
        return {"phase": "up_to_date", "release": live}
    assert_clean_checkout(maint.CREW)
    assert_clean_checkout(maint.CANDIDATE)
    git(maint.CANDIDATE, "fetch", "--no-tags", "origin", "refs/heads/main", timeout=180)
    if git(maint.CANDIDATE, "rev-parse", "FETCH_HEAD") != target:
        raise Waiting("upstream_changed_during_fetch")
    git(maint.CANDIDATE, "checkout", "--detach", target)
    assert_clean_checkout(maint.CANDIDATE)
    if git(maint.CANDIDATE, "merge-base", live, target) != live:
        raise Blocked("target_not_descendant")
    pr = verify_merge_chain(live, target)
    verify_ci(target)
    # No migrations, dependencies, service or reverse-proxy configuration.
    forbidden = git(maint.CANDIDATE, "diff", "--name-only", live, target,
                    "--", "alembic/", "app/migrations.py", "requirements.txt",
                    "requirements-dev.txt", "config.py", "deploy/crew.service",
                    "deploy/nginx-crew.conf")
    if forbidden:
        raise Blocked("requires_schema_or_infrastructure_release")
    # Ensure production can switch only to objects fetched from the same main.
    git(maint.CREW, "fetch", "--no-tags", "origin", "refs/heads/main", timeout=180)
    if git(maint.CREW, "rev-parse", "FETCH_HEAD") != target:
        raise Waiting("upstream_changed_during_fetch")
    if main_sha() != target or sha(maint.git_sha()) != live:
        raise Waiting("release_changed_during_validation")
    state = write_manifest(live, target, pr, state)
    # Reuse the existing guarded code-only engine: fresh verified backup,
    # clean candidate, static asset checks, restart, DB revision/count checks.
    # Use a separate manifest for this one trusted in-process invocation,
    # never altering the manual maintenance daemon or its approval policy.
    if maint.RELEASE_MANIFEST != MANUAL_MANIFEST:
        raise Blocked("unexpected_maintenance_manifest")
    maint.RELEASE_MANIFEST = MANIFEST
    try:
        maint.release_preflight()
        state_write({**state, "phase": "running", "base": live,
                     "release": target, "reviewed_pr": pr})
        original_restart = maint.restart_crew
        # Only this trusted auto-release invocation gets the bounded wait.
        # The separately running maintenance daemon remains untouched.
        maint.restart_crew = restart_crew_with_readiness
        try:
            try:
                maint.deploy_code_only()
            except Exception:
                state_write({**state, "phase": "failed", "base": live,
                             "release": target, "reviewed_pr": pr})
                raise
        finally:
            maint.restart_crew = original_restart
        state_write({**state, "phase": "succeeded", "base": live,
                     "release": target, "reviewed_pr": pr})
        return {"phase": "succeeded", "release": target, "reviewed_pr": pr}
    finally:
        maint.RELEASE_MANIFEST = MANUAL_MANIFEST


def main() -> int:
    try:
        print(json.dumps(run_once(), sort_keys=True))
        return 0
    except Waiting as exc:
        print(json.dumps({"phase": "waiting", "reason": str(exc)}))
        return 0
    except (Blocked, maint.Refused) as exc:
        print(json.dumps({"phase": "blocked", "reason": str(exc)}))
        return 1
    except Exception:
        # No traceback or command stderr in shared logs.
        print(json.dumps({"phase": "blocked", "reason": "unexpected_error"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
