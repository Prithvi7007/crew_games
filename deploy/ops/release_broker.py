"""CREW v15 one-time-approved deployment broker — host installation candidate.

A privileged, independent host service. It exposes only release_plan,
release_status and execute_v15 for one pinned release. It NEVER accepts shell
commands, executable paths, migrations, URLs, dynamic Git revisions or
environment variables from MCP.

execute_v15 requires an independently created, root-owned, non-symlinked
0600 approval file. The file is moved into a root-owned consumed directory
BEFORE executing, preventing replay. ChatGPT/user-supplied "approved=true"
has no effect.

Not installed by merging this file. A distinct root-owned systemd service
and explicit host acceptance review are mandatory.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import socketserver
import stat
import subprocess
import threading
import uuid

RELEASE = "f4a35026d1df0e86e987d4bca310b8d32aed4134"
BASE = "c5a9275629ba4389c2b66a14b61a523868d40673"
SOCKET = Path("/run/crew-deploy/deploy.sock")
APPROVAL = Path("/var/lib/crew-deploy/approval-v15.json")
WORKER_DIR = Path("/usr/local/libexec/crew-deploy")
ENGINE = WORKER_DIR / "release_engine.py"
REHEARSAL = WORKER_DIR / "v15-migration-rehearsal.sh"
CHECKPOINT = Path("/var/backups/crew/release-checkpoints/pre_v15_20261010T001254Z.dump")
STATE = Path("/var/lib/crew-deploy/state.json")
SPENT_DIR = Path("/var/lib/crew-deploy/used-approvals")
MAX_REQUEST_BYTES = 1024
MAX_APPROVAL_AGE_SECONDS = 900


def protected(path: Path, *, directory: bool = False) -> bool:
    try:
        s = path.lstat()
        if s.st_uid != 0 or s.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
        return stat.S_ISDIR(s.st_mode) if directory else (
            stat.S_ISREG(s.st_mode) and not (s.st_mode & (stat.S_IRWXG | stat.S_IRWXO))
        )
    except OSError:
        return False


def deployment_engine_safe() -> bool:
    return protected(WORKER_DIR, directory=True) and protected(ENGINE, directory=False)



def approval_plan_digest() -> str:
    """Bind operator approval to the reviewed executor, migration and backup."""
    import stat as stat_mod
    if not (deployment_engine_safe() and protected(REHEARSAL, directory=False)):
        raise OSError("release code not securely installed")
    b = CHECKPOINT.lstat()
    if not (stat_mod.S_ISREG(b.st_mode) and b.st_uid == 0
            and not (b.st_mode & (stat_mod.S_IWGRP | stat_mod.S_IWOTH))):
        raise OSError("checkpoint permissions unsafe")
    def digest(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    plan = {
        "operation": "execute_v15",
        "release_sha": RELEASE,
        "production_sha": BASE,
        "migration_revision": "v15_badges",
        "script_sha256": digest(REHEARSAL),
        "engine_sha256": digest(ENGINE),
        "checkpoint_sha256": digest(CHECKPOINT),
        "recovery_rule": "code_only_no_automatic_db_restore_or_downgrade",
    }
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_status() -> dict:
    try:
        with STATE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if (not isinstance(data, dict) or
            data.get("phase") not in {
                "validating", "rehearsing", "backing_up", "backed_up",
                "migrating", "switching_code", "succeeded", "halted"
            }):
            return {"phase": "unknown"}
        return {
            "phase": data["phase"],
            "release_sha": RELEASE,
            "detail": str(data.get("detail", ""))[:100],
        }
    except (OSError, ValueError, TypeError):
        return {"phase": "not_started", "release_sha": RELEASE}


def validate_and_consume_approval() -> bool:
    """Root-owned on-host authorization is an independent trust boundary."""
    if not (protected(APPROVAL) and protected(APPROVAL.parent, directory=True)
            and protected(SPENT_DIR, directory=True)):
        return False
    try:
        data = json.loads(APPROVAL.read_text(encoding="utf-8"))
        now = dt.datetime.now(dt.timezone.utc)
        if not isinstance(data, dict) or set(data) != {
            "operation", "release_sha", "production_sha", "expires_at",
            "confirmation", "nonce", "plan_digest"
        }:
            return False
        if (data["plan_digest"] != approval_plan_digest()
            or data["operation"] != "execute_v15"
            or data["release_sha"] != RELEASE
            or data["production_sha"] != BASE
            or data["confirmation"] != "DEPLOY CREW V15"):
            return False
        nonce = data["nonce"]
        if not isinstance(nonce, str) or re.fullmatch("[a-f0-9]{32}", nonce) is None:
            return False
        expires = dt.datetime.fromisoformat(data["expires_at"])
        if expires.tzinfo is None or not (now < expires <= now + dt.timedelta(seconds=MAX_APPROVAL_AGE_SECONDS)):
            return False
        # Atomic rename: a one-time capability. Previously consumed nonce
        # prevents replay even if another root process recreates that file.
        spent = SPENT_DIR / (nonce + ".json")
        if spent.exists() or spent.is_symlink():
            return False
        os.rename(APPROVAL, spent)
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


class Broker:
    def __init__(self) -> None:
        self.guard = threading.Lock()
        self.active = False

    def respond(self, request: object) -> dict:
        if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
            return {"ok": False, "error": "invalid_request"}
        op = request["operation"]
        if op == "capabilities" and set(request) == {"operation"}:
            return {
                "ok": True,
                "operations": ["capabilities", "release_plan", "release_status", "execute_v15"],
                "release_sha": RELEASE,
                "approval_required": True,
                "arbitrary_shell_enabled": False,
                "database_restore_enabled": False,
            }
        if op == "release_plan" and set(request) == {"operation"}:
            return {
                "ok": True, "release_sha": RELEASE, "production_sha": BASE,
                "steps": ["verify_checkout_and_schema", "rehearse_on_scratch",
                          "fresh_backup", "migrate_additive_schema",
                          "update_code", "restart_crew", "verify_health"],
                "approved": False, "approval_source": "root_only_host_file",
                "worker_installed": deployment_engine_safe(),
                "plan_digest": self._safe_plan_digest(),
            }
        if op == "release_status" and set(request) == {"operation"}:
            return {"ok": True, **load_status()}
        if op == "execute_v15" and set(request) == {"operation"}:
            with self.guard:
                if self.active or load_status().get("phase") in (
                    "validating", "rehearsing", "backing_up", "backed_up",
                    "migrating", "switching_code", "succeeded",
                ):
                    return {"ok": False, "error": "release_running_or_already_deployed"}
                if not deployment_engine_safe():
                    return {"ok": False, "error": "worker_not_safely_installed"}
                if not validate_and_consume_approval():
                    return {"ok": False, "error": "out_of_band_approval_required"}
                self.active = True
                threading.Thread(target=self._start, daemon=True).start()
            return {"ok": True, "phase": "starting", "release_sha": RELEASE}
        return {"ok": False, "error": "operation_not_allowed"}

    @staticmethod
    def _safe_plan_digest() -> str | None:
        try:
            return approval_plan_digest()
        except (OSError, ValueError):
            return None

    def _start(self) -> None:
        try:
            # No shell, command arguments or data from MCP.
            result = subprocess.run(
                ("/usr/bin/python3", "-I", "-B", str(ENGINE)),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False,
                env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
            )
            if result.returncode:
                # A crash may bypass the engine's own exception recording.
                if load_status().get("phase") != "halted":
                    self._write_start_failed()
        except OSError:
            self._write_start_failed()
        finally:
            with self.guard:
                self.active = False

    @staticmethod
    def _write_start_failed() -> None:
        STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = STATE.with_suffix(".start-failed")
        with temp.open("w", encoding="utf-8") as f:
            json.dump({"phase": "halted", "detail": "worker_start_failed"}, f)
        os.chmod(temp, 0o600)
        os.replace(temp, STATE)


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(15)
        try:
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                reply = {"ok": False, "error": "invalid_framing"}
            else:
                reply = self.server.broker.respond(json.loads(line))
        except (ValueError, OSError, TimeoutError):
            reply = {"ok": False, "error": "invalid_request"}
        self.wfile.write((json.dumps(reply, separators=(",", ":")) + "\n").encode())


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    def __init__(self, path: str, broker: Broker):
        self.broker = broker
        super().__init__(path, Handler)


def serve() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Deployment broker must run as root on the VPS.")
    if not deployment_engine_safe():
        raise SystemExit("Deployment engine is missing or has unsafe ownership.")
    if SOCKET.exists() or SOCKET.is_symlink():
        raise SystemExit("Refusing to replace existing deployment socket.")
    import grp
    runtime = SOCKET.parent
    runtime.mkdir(mode=0o750, parents=True, exist_ok=True)
    s = runtime.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise SystemExit("Unsafe deployment socket directory.")
    SPENT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not protected(SPENT_DIR, directory=True):
        raise SystemExit("Unsafe consumed approval directory.")
    with Server(str(SOCKET), Broker()) as server:
        os.chown(SOCKET, 0, grp.getgrnam("crew-ops").gr_gid)
        os.chmod(SOCKET, 0o660)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            SOCKET.unlink(missing_ok=True)


if __name__ == "__main__":
    serve()
