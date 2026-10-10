"""Unprivileged, read-only CREW operations gateway.

This service deliberately NEVER runs as root, cannot perform migrations or
deployments, and cannot access the protected PostgreSQL backup. The future
privileged deployment worker must be a separate, approval-gated service.
"""
from __future__ import annotations

import grp
import json
import os
from pathlib import Path
import pwd
import signal
import socketserver
import stat
import subprocess

PRODUCTION = Path("/opt/crew")
STAGING = Path("/opt/crew-v15-rehearsal")
EXPECTED_PRODUCTION = "c5a9275629ba4389c2b66a14b61a523868d40673"
EXPECTED_RELEASE = "f4a35026d1df0e86e987d4bca310b8d32aed4134"
SOCKET = Path("/run/crew-ops/ops.sock")
GROUP = "crew-ops"
MAX_REQUEST_BYTES = 2048


def run_fixed(*args: str, timeout: int = 8) -> tuple[bool, str]:
    """Execute only internal fixed argument vectors; never a supplied shell command."""
    proc = None
    try:
        proc = subprocess.Popen(
            args, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, start_new_session=True,
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


def git_inspect(path: Path, *args: str) -> tuple[bool, str]:
    """Git never executes as root; the unit is directly launched as crew."""
    if path not in (PRODUCTION, STAGING):
        return False, ""
    if args not in (("rev-parse", "HEAD"), ("status", "--porcelain")):
        return False, ""
    return run_fixed(
        "/usr/bin/git", "-c", f"safe.directory={path}",
        "-c", "core.fsmonitor=false", "-C", str(path), *args
    )


def preflight() -> dict:
    """Report Git readiness, NOT complete production deployment readiness."""
    prod_ok, prod_sha = git_inspect(PRODUCTION, "rev-parse", "HEAD")
    stage_ok, stage_sha = git_inspect(STAGING, "rev-parse", "HEAD")
    clean_prod, prod_changes = git_inspect(PRODUCTION, "status", "--porcelain")
    clean_stage, stage_changes = git_inspect(STAGING, "status", "--porcelain")
    checks = {
        "expected_production": prod_ok and prod_sha == EXPECTED_PRODUCTION,
        "expected_staging": stage_ok and stage_sha == EXPECTED_RELEASE,
        "production_clean": clean_prod and not prod_changes,
        "staging_clean": clean_stage and not stage_changes,
    }
    return {
        "operation": "release_preflight",
        "ready": False,  # Full release readiness requires privileged backup verification.
        "git_ready": all(checks.values()),
        "checks": checks,
        "privileged_backup_check": "required",
        "migration_rehearsal": "disabled",
        "release_sha": EXPECTED_RELEASE,
    }


class Operations:
    """Finite, read-only RPC. No shell, migration, or production-write actions."""

    def handle(self, request: object) -> dict:
        if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
            return {"ok": False, "error": "invalid_request"}
        op = request["operation"]
        if op == "capabilities" and set(request) == {"operation"}:
            return {
                "ok": True,
                "operations": ["capabilities", "release_preflight"],
                "deployment_enabled": False,
                "rehearsal_enabled": False,
            }
        if op == "release_preflight" and set(request) == {"operation"}:
            return {"ok": True, **preflight()}
        if op == "start_v15_rehearsal" and set(request) == {"operation"}:
            return {"ok": False, "error": "rehearsal_not_enabled"}
        return {"ok": False, "error": "operation_not_allowed"}


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
    expected_uid = pwd.getpwnam("crew").pw_uid
    if os.geteuid() != expected_uid:
        raise SystemExit("Read-only operations gateway must run as crew, never root.")
    if SOCKET.exists() or SOCKET.is_symlink():
        raise SystemExit("Socket already exists; refusing to replace it.")

    runtime_dir = SOCKET.parent
    info = runtime_dir.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_uid:
        raise SystemExit("Unsafe operations runtime directory owner or type.")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise SystemExit("Unsafe operations runtime directory permissions.")
    gid = grp.getgrnam(GROUP).gr_gid
    if os.getegid() != gid:
        raise SystemExit("Unexpected operations service group.")
    with Server(str(SOCKET), Operations()) as server:
        os.chmod(SOCKET, 0o660)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            SOCKET.unlink(missing_ok=True)


if __name__ == "__main__":
    serve()
