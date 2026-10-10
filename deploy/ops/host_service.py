"""Restricted Unix-socket operations endpoint for the CREW host.

This is a *candidate*, not an installed production service. Deployment and
production database writes are deliberately absent. A root-owned installation
and bridge adapter require separate security review.
"""
from __future__ import annotations

import grp
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socketserver
import stat
import subprocess
import threading
import uuid

PRODUCTION = Path("/opt/crew")
STAGING = Path("/opt/crew-v15-rehearsal")
BACKUP = Path("/var/backups/crew/crew_20261010T001254Z.dump")
CHECKPOINT = Path("/var/backups/crew/release-checkpoints/pre_v15_20261010T001254Z.dump")
EXPECTED_PRODUCTION = "c5a9275629ba4389c2b66a14b61a523868d40673"
EXPECTED_RELEASE = "f4a35026d1df0e86e987d4bca310b8d32aed4134"
SCRIPT = Path("/usr/local/libexec/crew-ops/v15-migration-rehearsal.sh")
SOCKET = Path("/run/crew-ops/ops.sock")
ENABLED = Path("/etc/crew/ops-rehearsal-enabled")
GROUP = "crew-ops"
MAX_REQUEST_BYTES = 2048
VALID_JOB = re.compile(r"[0-9a-f]{32}\Z")


def run_fixed(*args: str, timeout: int = 8) -> tuple[bool, str]:
    """Run an internal fixed argv; terminate the entire process group on timeout.

    The rehearsal invokes multiple subprocesses. Killing its parent shell alone
    could leave orphaned PostgreSQL jobs, so each job gets an isolated session.
    """
    is_rehearsal = args == ("/bin/bash", str(SCRIPT))
    proc = None
    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if is_rehearsal else subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        )
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.communicate()
            return False, ""
    except OSError:
        return False, ""
    return proc.returncode == 0, (output or "").strip()[:256]


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            value.update(chunk)
    return value.hexdigest()


def git_inspect(path: Path, *args: str) -> tuple[bool, str]:
    """Never invoke Git as root on a checkout sharing CREW-writable metadata.

    Both the production and root-created staging worktree reference the same
    repository metadata. Git may execute configured helpers during inspection.
    """
    if path not in (PRODUCTION, STAGING):
        return False, ""
    return run_fixed(
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={path}",
        "-c", "core.fsmonitor=false", "-C", str(path), *args,
    )


def preflight() -> dict:
    """Read-only readiness checks for exactly the pinned v15 release."""
    prod_ok, prod_sha = git_inspect(PRODUCTION, "rev-parse", "HEAD")
    stage_ok, stage_sha = git_inspect(STAGING, "rev-parse", "HEAD")
    clean_prod, prod_changes = git_inspect(PRODUCTION, "status", "--porcelain")
    clean_stage, stage_changes = git_inspect(STAGING, "status", "--porcelain")
    checks = {
        "expected_production": prod_ok and prod_sha == EXPECTED_PRODUCTION,
        "expected_staging": stage_ok and stage_sha == EXPECTED_RELEASE,
        "production_clean": clean_prod and not prod_changes,
        "staging_clean": clean_stage and not stage_changes,
        "checkpoint_matches_original": False,
        "backup_format_readable": False,
    }
    try:
        checksum_file = Path(str(BACKUP) + ".sha256")
        checksum = checksum_file.read_text(encoding="utf-8").split()[0]
        checks["checkpoint_matches_original"] = (
            re.fullmatch(r"[0-9a-f]{64}", checksum) is not None
            and file_digest(BACKUP) == checksum
            and file_digest(CHECKPOINT) == checksum
        )
        readable, _ = run_fixed("/usr/bin/pg_restore", "--list", str(CHECKPOINT),
                                timeout=30)
        checks["backup_format_readable"] = readable
    except (OSError, ValueError, IndexError):
        pass
    return {"operation": "release_preflight", "ready": all(checks.values()), "checks": checks,
            "release_sha": EXPECTED_RELEASE}


def is_root_owned_rehearsal_script(path: Path = SCRIPT) -> bool:
    """Refuse symlinks or writable scripts (executed by a root-owned service)."""
    try:
        info = path.lstat()
        return (
            stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and not (info.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
            and path.parent == Path("/usr/local/libexec/crew-ops")
            and path.parent.stat().st_uid == 0
            and not (path.parent.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH))
            and not path.parent.is_symlink()
        )
    except OSError:
        return False


def rehearsal_enabled() -> bool:
    try:
        s = ENABLED.lstat()
        return (stat.S_ISREG(s.st_mode) and s.st_uid == 0
                and not (s.st_mode & (stat.S_IRWXG | stat.S_IRWXO))
                and ENABLED.read_text(encoding="utf-8").strip() == "enable-v15-rehearsal")
    except OSError:
        return False


class Operations:
    """Finite-operation RPC, never arbitrary command execution."""

    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self.mu = threading.Lock()
        self.active = False

    def handle(self, request: object) -> dict:
        if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
            return {"ok": False, "error": "invalid_request"}
        op = request["operation"]
        if op == "capabilities" and set(request) == {"operation"}:
            return {"ok": True, "operations": [
                "capabilities", "release_preflight",
                "start_v15_rehearsal", "rehearsal_status"
            ], "deployment_enabled": False}
        if op == "release_preflight" and set(request) == {"operation"}:
            return {"ok": True, **preflight()}
        if op == "start_v15_rehearsal" and set(request) == {"operation"}:
            with self.mu:
                if self.active:
                    return {"ok": False, "error": "rehearsal_running"}
                if not rehearsal_enabled() or not is_root_owned_rehearsal_script():
                    return {"ok": False, "error": "rehearsal_not_enabled"}
                if not preflight()["ready"]:
                    return {"ok": False, "error": "preflight_failed"}
                job_id = uuid.uuid4().hex
                self.jobs[job_id] = {"state": "running"}
                self.active = True
                threading.Thread(target=self._rehearse, args=(job_id,), daemon=True).start()
            return {"ok": True, "job_id": job_id, "state": "running"}
        if op == "rehearsal_status" and set(request) == {"operation", "job_id"}:
            job_id = request["job_id"]
            if not isinstance(job_id, str) or not VALID_JOB.fullmatch(job_id):
                return {"ok": False, "error": "invalid_job_id"}
            with self.mu:
                status = self.jobs.get(job_id)
                return {"ok": True, "job_id": job_id, **status} if status else {
                    "ok": False, "error": "unknown_job"
                }
        return {"ok": False, "error": "operation_not_allowed"}

    def _rehearse(self, job_id: str) -> None:
        # No shell=True, no runtime-selected executable, arguments or environment.
        # Intentionally discard all subprocess output rather than exposing secrets.
        successful, _ = run_fixed("/bin/bash", str(SCRIPT), timeout=600)
        with self.mu:
            self.jobs[job_id] = {"state": "passed" if successful else "failed"}
            self.active = False


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(15)
        try:
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                reply = {"ok": False, "error": "request_too_large_or_unframed"}
            else:
                reply = self.server.operations.handle(json.loads(line))
        except (ValueError, TimeoutError, OSError, UnicodeDecodeError):
            reply = {"ok": False, "error": "invalid_request"}
        self.wfile.write((json.dumps(reply, separators=(",", ":")) + "\n").encode())


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: str, operations: Operations):
        self.operations = operations
        super().__init__(address, Handler)


def serve() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Host operations service requires a root-owned, reviewed installation.")
    # Existing socket or symlink must never be unlinked by an untrusted caller.
    if SOCKET.exists() or SOCKET.is_symlink():
        raise SystemExit("Socket already exists; refusing to replace it.")
    runtime_dir = SOCKET.parent
    runtime_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
    info = runtime_dir.stat()
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise SystemExit("Unsafe operations runtime directory.")
    gid = grp.getgrnam(GROUP).gr_gid
    with Server(str(SOCKET), Operations()) as server:
        os.chown(SOCKET, 0, gid)
        os.chmod(SOCKET, 0o660)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            SOCKET.unlink(missing_ok=True)


if __name__ == "__main__":
    serve()
