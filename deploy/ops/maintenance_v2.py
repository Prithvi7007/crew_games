"""CREW Ops v2: finite, independently approved production diagnostics and repairs.

Install only as root-owned code outside the writable CREW checkout.
The Unix RPC exposes no caller-provided command, path, URL, SQL, SHA, or shell.
Existing v15 release worker and its historical status remain untouched.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socketserver
import stat
import subprocess
import sys
import threading
import uuid

SOCKET = Path("/run/crew-maint/maint.sock")
STATE_DIR = Path("/var/lib/crew-maint")
APPROVAL = STATE_DIR / "approval.json"
CONSUMED = STATE_DIR / "consumed"
AUDIT = STATE_DIR / "audit.jsonl"
ACTION_STATE = STATE_DIR / "action.json"
OLD_DEPLOY_STATE = Path("/var/lib/crew-deploy/state.json")
CREW = Path("/opt/crew")
HOST = "cadacrew.fun"
ASSETS = ("player.js", "player.css")
ACTIONS = ("repair_react_assets", "restart_crew", "deploy_code_only")
OPERATIONS = (
    "capabilities", "dashboard", "asset_diagnostics", "incident_summary",
    "maintenance_status", "plan_repair_react_assets", "plan_restart_crew",
    "execute_repair_react_assets", "execute_restart_crew",
    "code_release_plan", "execute_code_release",
)
MAX_REQUEST = 1024
ALLOWED_DETAIL = re.compile(r"^[a-zA-Z0-9_. -]{0,96}$")
LOCK = threading.Lock()
RELEASE_MANIFEST = Path("/usr/local/libexec/crew-maint/code_release_manifest.json")
CANDIDATE = Path("/opt/crew-release-candidate")


class Refused(Exception):
    pass


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def fixed(*args: str, timeout: int = 12) -> tuple[bool, str]:
    """No shell, inherited secrets, arbitrary command paths, or caller argv."""
    try:
        result = subprocess.run(
            args, input="", capture_output=True, text=True, timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
            check=False,
        )
        return result.returncode == 0, result.stdout.strip()[:320]
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def git_sha() -> str:
    ok, sha = fixed(
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={CREW}",
        "-c", "core.fsmonitor=false", "-C", str(CREW), "rev-parse", "HEAD",
    )
    return sha if ok and re.fullmatch(r"[0-9a-f]{40}", sha) else "unavailable"


def service_active(unit: str) -> bool:
    assert unit in ("crew.service", "nginx.service", "crew-deploy.service")
    return fixed("/usr/bin/systemctl", "is-active", "--quiet", unit)[0]


def socket_health() -> bool:
    return fixed(
        "/usr/bin/curl", "--silent", "--show-error", "--fail", "--max-time", "8",
        "--unix-socket", "/run/crew/crew.sock", "-H", f"Host: {HOST}",
        "http://localhost/health/ready",
    )[0]


def database_summary() -> dict:
    # One reviewed SELECT; no usernames, email addresses, user-provided SQL, or writes.
    query = (
        "SELECT (SELECT version_num FROM alembic_version),"
        "(SELECT count(*) FROM profiles),"
        "(SELECT count(*) FROM game_completions),"
        "(SELECT count(*) FROM user_stats)"
    )
    ok, output = fixed(
        "/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/env",
        "-u", "PGHOST", "-u", "PGPORT", "-u", "PGDATABASE",
        "-u", "PGUSER", "-u", "PGPASSWORD",
        "/usr/bin/psql", "-X", "-v", "ON_ERROR_STOP=1",
        "-d", "crew_prod", "-Atqc", query,
    )
    parts = output.split("|")
    if not ok or len(parts) != 4 or not re.fullmatch(r"v[0-9]+_[a-z_]+", parts[0]) or not all(s.isdecimal() for s in parts[1:]):
        return {"available": False}
    return dict(zip(("revision", "profiles", "game_completions", "user_stats"),
                    (parts[0], *(int(v) for v in parts[1:]))))


def read_public_asset(filename: str) -> tuple[int, int, int, str]:
    """Open each directory component without following symlinks, pin the final inode."""
    if filename not in ASSETS:
        raise Refused("asset_not_allowed")
    components = ("opt", "crew", "app", "static", "react")
    dir_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in components:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        file_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    info = os.fstat(file_fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != pwd.getpwnam("crew").pw_uid
            or info.st_gid != grp.getgrnam("www-data").gr_gid):
        os.close(file_fd)
        raise Refused("unsafe_asset_owner_or_type")
    return file_fd, stat.S_IMODE(info.st_mode), info.st_size, filename


def assets_summary() -> dict:
    result = {}
    for filename in ASSETS:
        try:
            fd, mode, size, _ = read_public_asset(filename)
            os.close(fd)
            readable = fixed(
                "/usr/sbin/runuser", "-u", "www-data", "--", "/usr/bin/test",
                "-r", str(CREW / "app" / "static" / "react" / filename),
            )[0]
            # Probe the local reverse proxy, with the public HTTPS hostname.
            ok, output = fixed(
                "/usr/bin/curl", "--silent", "--show-error", "--max-time", "8",
                "--resolve", f"{HOST}:443:127.0.0.1", "-o", "/dev/null",
                "-w", "%{http_code}|%{content_type}",
                f"https://{HOST}/static/react/{filename}",
                timeout=10,
            )
            if not ok or not re.fullmatch(r"[0-9]{3}\|[A-Za-z0-9.+/;= -]+", output):
                output = "unavailable"
            result[filename] = {
                "present": True, "mode": format(mode, "04o"), "bytes": size,
                "nginx_user_readable": readable, "local_https": output,
            }
        except (OSError, Refused):
            result[filename] = {"present": False, "nginx_user_readable": False}
    return result


def _bounded_json(path: Path, keys: tuple[str, ...]) -> dict:
    try:
        if path.stat().st_size > 4096 or path.is_symlink():
            return {}
        source = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(source, dict):
            return {}
        return {
            k: v for k in keys
            if isinstance((v := source.get(k)), str) and ALLOWED_DETAIL.fullmatch(v)
        }
    except (ValueError, OSError, UnicodeError):
        return {}


def incident_summary() -> dict:
    """Classify recent error-log tail; never return raw log text/IPs/credentials."""
    counters = {k: 0 for k in ("permission_denied", "upstream_failure", "file_not_found", "other_errors")}
    try:
        with open("/var/log/nginx/error.log", "rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 131072))
            lines = stream.read(131072).decode("utf-8", errors="replace").splitlines()[-120:]
        for line in lines:
            lower = line.lower()
            if "permission denied" in lower:
                counters["permission_denied"] += 1
            elif "upstream" in lower or "connect() failed" in lower:
                counters["upstream_failure"] += 1
            elif "no such file or directory" in lower:
                counters["file_not_found"] += 1
            elif "[error]" in lower or "[crit]" in lower:
                counters["other_errors"] += 1
    except OSError:
        counters["log_available"] = False
    else:
        counters["log_available"] = True
    return {
        "nginx_error_log_tail": counters,
        "previous_deployment": _bounded_json(
            OLD_DEPLOY_STATE, ("phase", "detail", "release_sha", "updated_at")
        ),
    }


def maintenance_status() -> dict:
    return {
        "last_action": _bounded_json(ACTION_STATE, ("operation", "phase", "detail", "updated_at")),
        "approval_staged": approval_present(),
    }


def approval_present() -> bool:
    try:
        value = APPROVAL.lstat()
        return stat.S_ISREG(value.st_mode) and value.st_uid == 0 and stat.S_IMODE(value.st_mode) == 0o600
    except OSError:
        return False


def asset_fingerprint() -> str:
    h = hashlib.sha256()
    for filename in ASSETS:
        fd, mode, size, _ = read_public_asset(filename)
        try:
            data = os.read(fd, 1024 * 1024)
            if size != len(data):
                raise Refused("oversized_asset")
            h.update(filename.encode() + b"\0" + data + b"\0")
        finally:
            os.close(fd)
    return h.hexdigest()


def action_digest(action: str) -> str:
    if action not in ACTIONS:
        raise Refused("unknown_action")
    sha = git_sha()
    if sha == "unavailable":
        raise Refused("commit_unavailable")
    evidence = (asset_fingerprint() if action == "repair_react_assets" else
                code_release_digest() if action == "deploy_code_only" else "-")
    return hashlib.sha256(f"CREW_MAINT_V2\n{action}\n{sha}\n{evidence}\n".encode()).hexdigest()


def plan(action: str) -> dict:
    changes = {
        "repair_react_assets": ["Set player.js and player.css to 0644, if owned by crew:www-data"],
        "restart_crew": ["Restart crew.service and check readiness"],
        "deploy_code_only": ["Take a fresh verified backup", "Switch to exact reviewed commit",
                             "Verify assets, service health, and unchanged database revision"],
    }
    response = {
        "ok": True, "operation": action, "commit": git_sha(),
        "plan_digest": action_digest(action),
        "approval_required": True, "max_approval_age_seconds": 600,
        "changes": changes[action],
        "database_migration": False,
    }
    if action == "deploy_code_only":
        response["candidate"] = read_code_release_manifest()["release"]
        response["kind"] = "code_only"
    return response


def _safe_state_dir() -> None:
    for path in (STATE_DIR, CONSUMED):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
            raise Refused("unsafe_state_directory")


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def audit(operation: str, outcome: str) -> None:
    event = {"at": now().isoformat(), "operation": operation, "outcome": outcome}
    fd = os.open(AUDIT, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != 0 or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise Refused("unsafe_audit_file")
        os.write(fd, (json.dumps(event, sort_keys=True) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def consume_approval(action: str, digest: str) -> None:
    if not approval_present():
        raise Refused("root_approval_required")
    try:
        payload = json.loads(APPROVAL.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise Refused("invalid_approval")
    if (not isinstance(payload, dict) or set(payload) !=
            {"operation", "plan_digest", "expires_at", "nonce"}):
        raise Refused("invalid_approval")
    if payload["operation"] != action or payload["plan_digest"] != digest:
        raise Refused("approval_plan_mismatch")
    if not isinstance(payload["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", payload["nonce"]):
        raise Refused("invalid_approval")
    try:
        expiry = dt.datetime.fromisoformat(payload["expires_at"])
        if expiry.tzinfo is None or not now() < expiry <= now() + dt.timedelta(minutes=10):
            raise Refused("approval_expired")
    except (ValueError, TypeError):
        raise Refused("invalid_approval")
    target = CONSUMED / (payload["nonce"] + ".json")
    if target.exists():
        raise Refused("approval_replay")
    # Consume before any side effect. Store replay evidence in a root-only directory.
    os.rename(APPROVAL, target)


def repair_react_assets() -> None:
    for filename in ASSETS:
        fd, _, _, _ = read_public_asset(filename)
        try:
            os.fchmod(fd, 0o644)
        finally:
            os.close(fd)
    if not all(a.get("nginx_user_readable") for a in assets_summary().values()):
        raise Refused("asset_readability_not_verified")


def restart_crew() -> None:
    if not fixed("/usr/bin/systemctl", "restart", "crew.service", timeout=90)[0]:
        raise Refused("restart_failed")
    if not service_active("crew.service") or not socket_health():
        raise Refused("post_restart_health_failed")


def execute_action(action: str) -> dict:
    with LOCK:
        # Check digest before consuming authorization; never take MCP-supplied SHA.
        digest = action_digest(action)
        consume_approval(action, digest)
        audit(action, "started")
        _write_json(ACTION_STATE, {"operation": action, "phase": "running", "detail": "",
                                   "updated_at": now().isoformat()})
        try:
            if action == "repair_react_assets":
                repair_react_assets()
            elif action == "restart_crew":
                restart_crew()
            elif action == "deploy_code_only":
                deploy_code_only()
            else:
                raise Refused("unknown_action")
        except (Refused, OSError) as exc:
            detail = (str(exc) if isinstance(exc, Refused)
                      and re.fullmatch(r"[a-z_]{1,64}", str(exc)) else "filesystem_error")
            audit(action, "failed_" + detail)
            _write_json(ACTION_STATE, {"operation": action, "phase": "failed",
                                       "detail": detail, "updated_at": now().isoformat()})
            return {"ok": False, "error": detail, "operation": action}
        audit(action, "succeeded")
        _write_json(ACTION_STATE, {"operation": action, "phase": "succeeded",
                                   "detail": "", "updated_at": now().isoformat()})
        return {"ok": True, "operation": action, "phase": "succeeded"}


def read_code_release_manifest() -> dict:
    """Operator installs a root-owned candidate record; MCP cannot supply a ref."""
    try:
        info = RELEASE_MANIFEST.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o400 or info.st_size > 1024):
            raise Refused("unsafe_release_manifest")
        value = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise Refused("release_manifest_missing_or_invalid")
    if not isinstance(value, dict) or set(value) != {
        "format", "kind", "base", "release", "db_revision", "reviewed_pr"
    }:
        raise Refused("invalid_release_manifest")
    if value["format"] != 1 or value["kind"] != "code_only":
        raise Refused("unsupported_release_kind")
    if (not all(isinstance(value[k], str) and re.fullmatch(r"[0-9a-f]{40}", value[k])
                for k in ("base", "release")) or value["base"] == value["release"]):
        raise Refused("invalid_release_commit")
    if (not isinstance(value["db_revision"], str)
            or not re.fullmatch(r"v[0-9]+_[a-z_]+", value["db_revision"])
            or not isinstance(value["reviewed_pr"], int) or value["reviewed_pr"] < 1):
        raise Refused("invalid_release_evidence")
    return value


def git_inspect(path: Path, *args: str, child_umask: int = -1) -> tuple[bool, str]:
    if path not in (CREW, CANDIDATE):
        raise Refused("invalid_checkout")
    return fixed(
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={path}", "-c", "core.fsmonitor=false",
        "-C", str(path), *args,
        timeout=40,
    ) if child_umask == -1 else git_switch(path, args, child_umask)


def git_switch(path: Path, args: tuple[str, ...], child_umask: int) -> tuple[bool, str]:
    if path != CREW or len(args) != 3 or args[:2] != ("reset", "--hard"):
        raise Refused("unapproved_git_mutation")
    # No shell, environment secrets, or change to the worker's restrictive umask.
    try:
        result = subprocess.run(
            ("/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
             "/usr/bin/git", "-c", f"safe.directory={CREW}",
             "-c", "core.fsmonitor=false", "-C", str(CREW), *args),
            input="", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=120, check=False, umask=child_umask,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
        )
        return result.returncode == 0, result.stdout.strip()[:256]
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def release_preflight() -> dict:
    manifest = read_code_release_manifest()
    before = git_sha()
    if before != manifest["base"]:
        raise Refused("release_base_mismatch")
    prod_clean, changed = git_inspect(CREW, "status", "--porcelain")
    staged_ok, staged = git_inspect(CANDIDATE, "rev-parse", "HEAD")
    stage_clean, stage_changed = git_inspect(CANDIDATE, "status", "--porcelain")
    if not (prod_clean and not changed and staged_ok and
            staged == manifest["release"] and stage_clean and not stage_changed):
        raise Refused("release_checkout_not_ready")
    # Code-only releases must not modify migrations, dependencies or server config.
    ok, changes = git_inspect(
        CANDIDATE, "diff", "--name-only", manifest["base"],
        manifest["release"], "--", "alembic/", "app/migrations.py",
        "requirements.txt", "requirements-dev.txt", "config.py",
        "deploy/crew.service", "deploy/nginx-crew.conf"
    )
    if not ok or changes:
        raise Refused("requires_separately_reviewed_migration_or_infra_release")
    summary = database_summary()
    if summary.get("revision") != manifest["db_revision"]:
        raise Refused("release_database_revision_mismatch")
    if not service_active("crew.service") or not socket_health():
        raise Refused("release_health_not_ready")
    return manifest


def code_release_digest() -> str:
    manifest = release_preflight()
    body = RELEASE_MANIFEST.read_bytes()
    return hashlib.sha256(b"CODE_ONLY_RELEASE_V2\0" + body).hexdigest()


def verified_fresh_backup() -> None:
    """Backups are created by the existing reviewed systemd backup unit."""
    import time
    candidates = list(Path("/var/backups/crew").glob("crew_*.dump"))
    if not candidates:
        raise Refused("backup_missing")
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    info = latest.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or time.time() - info.st_mtime > 10 * 60):
        raise Refused("backup_not_fresh_or_protected")
    signature = Path(str(latest) + ".sha256")
    if signature.is_symlink() or signature.lstat().st_uid != 0:
        raise Refused("backup_checksum_not_protected")
    expected = signature.read_text(encoding="utf-8").split()[0]
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise Refused("backup_checksum_invalid")
    sha = hashlib.sha256()
    with latest.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(data)
    if sha.hexdigest() != expected:
        raise Refused("backup_checksum_mismatch")
    if not fixed("/usr/bin/pg_restore", "--list", str(latest), timeout=60)[0]:
        raise Refused("backup_unreadable")


def deploy_code_only() -> None:
    manifest = release_preflight()
    before = database_summary()
    if not fixed("/usr/bin/systemctl", "start", "crew-backup.service", timeout=180)[0]:
        raise Refused("backup_service_failed")
    verified_fresh_backup()
    # A second immutable-pinned check after backup prevents an altered candidate.
    manifest = release_preflight()
    ok, _ = git_inspect(CREW, "reset", "--hard", manifest["release"], child_umask=0o022)
    if not ok:
        raise Refused("code_checkout_failed")
    assets = assets_summary()
    if not all(v.get("nginx_user_readable") for v in assets.values()):
        raise Refused("deployed_assets_unreadable")
    restart_crew()
    after = database_summary()
    if (after.get("revision") != before.get("revision") or
            any(after.get(k, -1) < before.get(k, 0)
                for k in ("profiles", "game_completions", "user_stats"))):
        raise Refused("post_deploy_data_integrity_failed")
    if git_sha() != manifest["release"]:
        raise Refused("post_deploy_commit_mismatch")


def _finish_code_release() -> None:
    """Detached worker thread; MCP can poll maintenance_status immediately."""
    try:
        _write_json(ACTION_STATE, {"operation": "deploy_code_only", "phase": "running",
                                   "detail": "", "updated_at": now().isoformat()})
        deploy_code_only()
    except (Refused, OSError) as exc:
        detail = (str(exc) if isinstance(exc, Refused)
                  and re.fullmatch(r"[a-z_]{1,64}", str(exc)) else "filesystem_error")
        audit("deploy_code_only", "failed_" + detail)
        _write_json(ACTION_STATE, {"operation": "deploy_code_only", "phase": "failed",
                                   "detail": detail, "updated_at": now().isoformat()})
    except Exception:
        audit("deploy_code_only", "unexpected_error")
        _write_json(ACTION_STATE, {"operation": "deploy_code_only", "phase": "failed",
                                   "detail": "unexpected_error", "updated_at": now().isoformat()})
    else:
        audit("deploy_code_only", "succeeded")
        _write_json(ACTION_STATE, {"operation": "deploy_code_only", "phase": "succeeded",
                                   "detail": "", "updated_at": now().isoformat()})
    finally:
        LOCK.release()


def start_code_release() -> dict:
    if not LOCK.acquire(blocking=False):
        raise Refused("maintenance_busy")
    try:
        digest = action_digest("deploy_code_only")
        consume_approval("deploy_code_only", digest)
        audit("deploy_code_only", "queued")
        _write_json(ACTION_STATE, {"operation": "deploy_code_only", "phase": "queued",
                                   "detail": "", "updated_at": now().isoformat()})
        thread = threading.Thread(target=_finish_code_release, daemon=True,
                                  name="crew-code-only-release")
        thread.start()
        return {"ok": True, "operation": "deploy_code_only", "phase": "queued"}
    except Exception:
        LOCK.release()
        raise


def mark_interrupted_release() -> None:
    previous = _bounded_json(ACTION_STATE, ("operation", "phase", "detail", "updated_at"))
    if previous.get("phase") not in ("running", "queued"):
        return
    audit(previous.get("operation", "deploy_code_only"), "interrupted")
    _write_json(ACTION_STATE, {
        "operation": previous.get("operation", "deploy_code_only"),
        "phase": "failed", "detail": "worker_interrupted",
        "updated_at": now().isoformat(),
    })


def respond(message: object) -> dict:
    if not isinstance(message, dict) or set(message) != {"operation"} or not isinstance(message["operation"], str):
        return {"ok": False, "error": "invalid_request"}
    op = message["operation"]
    if op not in OPERATIONS:
        return {"ok": False, "error": "operation_not_allowed"}
    try:
        if op == "capabilities":
            return {"ok": True, "operations": list(OPERATIONS), "shell_enabled": False,
                    "database_writes_enabled": False, "approval_required_for_writes": True}
        if op == "dashboard":
            return {"ok": True, "production_commit": git_sha(),
                    "services": {unit: service_active(unit) for unit in ("crew.service", "nginx.service", "crew-deploy.service")},
                    "health_ready": socket_health(), "database": database_summary()}
        if op == "asset_diagnostics":
            return {"ok": True, "assets": assets_summary()}
        if op == "incident_summary":
            return {"ok": True, **incident_summary()}
        if op == "maintenance_status":
            return {"ok": True, **maintenance_status()}
        if op == "plan_repair_react_assets":
            return plan("repair_react_assets")
        if op == "plan_restart_crew":
            return plan("restart_crew")
        if op == "execute_repair_react_assets":
            return execute_action("repair_react_assets")
        if op == "execute_restart_crew":
            return execute_action("restart_crew")
        if op == "code_release_plan":
            if not RELEASE_MANIFEST.exists():
                return {"ok": True, "configured": False,
                        "message": "root_owned_pinned_manifest_required"}
            return {"configured": True, **plan("deploy_code_only")}
        if op == "execute_code_release":
            return start_code_release()
    except Refused as exc:
        code = str(exc)
        return {"ok": False, "error": code if re.fullmatch(r"[a-z_]{1,48}", code) else "operation_refused"}
    except Exception:
        return {"ok": False, "error": "internal_error"}
    return {"ok": False, "error": "operation_not_allowed"}


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(12)
        try:
            line = self.rfile.readline(MAX_REQUEST + 1)
            if not line.endswith(b"\n") or len(line) > MAX_REQUEST:
                result = {"ok": False, "error": "request_too_large_or_unframed"}
            else:
                result = respond(json.loads(line))
        except (ValueError, UnicodeError, TimeoutError, OSError):
            result = {"ok": False, "error": "invalid_request"}
        self.wfile.write((json.dumps(result, separators=(",", ":")) + "\n").encode())


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    def __init__(self, path: str):
        super().__init__(path, Handler)


def approve(action: str) -> None:
    if action not in ACTIONS or not sys.stdin.isatty():
        raise SystemExit("A root-operated interactive terminal is required.")
    _safe_state_dir()
    if APPROVAL.exists() or APPROVAL.is_symlink():
        raise SystemExit("A prior approval is staged; do not overwrite it.")
    details = plan(action)
    print("CREW Ops v2 — ONE ACTION APPROVAL")
    print("Operation:", action)
    print("Production commit:", details["commit"])
    print("Plan digest:", details["plan_digest"])
    print("Changes:", ", ".join(details["changes"]))
    print("No database writes. Approval expires in ten minutes.")
    phrase = {"repair_react_assets": "AUTHORIZE CREW ASSET REPAIR",
              "restart_crew": "AUTHORIZE CREW RESTART",
              "deploy_code_only": "DEPLOY CREW REVIEWED CODE"}[action]
    if input(f"Type exactly '{phrase}' to continue: ") != phrase:
        raise SystemExit("Approval not staged.")
    payload = {"operation": action, "plan_digest": details["plan_digest"],
               "expires_at": (now() + dt.timedelta(minutes=10)).isoformat(),
               "nonce": uuid.uuid4().hex}
    # No clobber; root-only file, consumed by the worker on first use.
    fd = os.open(APPROVAL, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    print("One-time approval staged. It does NOT execute anything.")


def serve() -> None:
    if SOCKET.exists() or SOCKET.is_symlink():
        raise SystemExit("Operations socket already exists; refusing to overwrite it.")
    _safe_state_dir()
    mark_interrupted_release()
    runtime = SOCKET.parent.lstat()
    if not stat.S_ISDIR(runtime.st_mode) or runtime.st_uid != 0 or runtime.st_mode & 0o022:
        raise SystemExit("Unsafe runtime directory.")
    with Server(str(SOCKET)) as server:
        os.chown(SOCKET, 0, grp.getgrnam("crew-ops").gr_gid)
        os.chmod(SOCKET, 0o660)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            SOCKET.unlink(missing_ok=True)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("CREW maintenance host process requires root.")
    if sys.argv[1:] == ["serve"]:
        serve()
    elif len(sys.argv) == 3 and sys.argv[1] == "approve" and sys.argv[2] in ACTIONS:
        approve(sys.argv[2])
    else:
        raise SystemExit("Unsupported command.")


if __name__ == "__main__":
    main()
