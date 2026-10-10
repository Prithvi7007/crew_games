"""Safely activate the already-installed CREW Ops v2 socket in the live MCP bridge.

This is a one-time, local-only integration of 11 fixed zero-argument MCP
functions. It never resets the bridge repo, migrates PostgreSQL, deploys CREW,
changes the v15 worker, or introduces command/path/SQL passthrough tools.
"""
from __future__ import annotations

import ast
import datetime as dt
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

BRIDGE = Path("/opt/crew-dev-bridge")
HOST_SOCKET = Path("/run/crew-maint/maint.sock")
SERVER = BRIDGE / "bridge" / "server.py"
COMPOSE = BRIDGE / "compose.yaml"
BACKUP_BASE = Path("/root/crew-bridge-backups")
MARKER = "# BEGIN CREW OPS V2: fixed maintenance tools"
METHODS = {
    "crew_maint_capabilities": "capabilities",
    "crew_maint_dashboard": "dashboard",
    "crew_maint_assets": "asset_diagnostics",
    "crew_maint_incidents": "incident_summary",
    "crew_maint_status": "maintenance_status",
    "crew_maint_plan_asset_repair": "plan_repair_react_assets",
    "crew_maint_plan_restart": "plan_restart_crew",
    "crew_maint_execute_asset_repair": "execute_repair_react_assets",
    "crew_maint_execute_restart": "execute_restart_crew",
    "crew_maint_code_release_plan": "code_release_plan",
    "crew_maint_execute_code_release": "execute_code_release",
}

RPC_CODE = """# BEGIN CREW OPS V2: fixed maintenance tools
import json as _crew_maint_json
import socket as _crew_maint_socket

_CREW_MAINT_SOCK = "/run/crew-maint/maint.sock"
_CREW_MAINT_OPS = frozenset((
    "capabilities", "dashboard", "asset_diagnostics", "incident_summary",
    "maintenance_status", "plan_repair_react_assets", "plan_restart_crew",
    "execute_repair_react_assets", "execute_restart_crew",
    "code_release_plan", "execute_code_release",
))

def _crew_maint_request(operation: str) -> dict:
    if operation not in _CREW_MAINT_OPS:
        return {"ok": False, "error": "operation_not_allowed"}
    try:
        with _crew_maint_socket.socket(_crew_maint_socket.AF_UNIX) as conn:
            conn.settimeout(100 if operation == "execute_restart_crew" else 25)
            conn.connect(_CREW_MAINT_SOCK)
            conn.sendall((_crew_maint_json.dumps({"operation": operation}) + "\\n").encode())
            body = bytearray()
            while not body.endswith(b"\\n"):
                chunk = conn.recv(4096)
                if not chunk or len(body) + len(chunk) > 16384:
                    raise ValueError("invalid_maintenance_response")
                body.extend(chunk)
        data = _crew_maint_json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
            raise ValueError("invalid_maintenance_response")
        return data
    except (OSError, ValueError):
        return {"ok": False, "error": "maintenance_socket_unavailable"}

"""


def tool_registrations() -> str:
    lines = [RPC_CODE]
    for name, operation in METHODS.items():
        lines += [
            "@mcp.tool()\n",
            f"def {name}() -> dict:\n",
            f'    """Fixed CREW maintenance operation: {operation}."""\n',
            f'    return _crew_maint_request("{operation}")\n\n',
        ]
    lines.append("# END CREW OPS V2: fixed maintenance tools\n\n")
    return "".join(lines)


def patch_server(original: str) -> str:
    if MARKER in original:
        raise ValueError("Maintenance tools already present; refusing duplicate registration.")
    if "crew_maint_" in original:
        raise ValueError("Partial maintenance registration found; manual review required.")
    if "@mcp.tool()" not in original or "def crew_deploy_plan" not in original:
        raise ValueError("Unexpected bridge server version; not safe to patch.")
    matches = list(re.finditer(
        r"(?m)^if __name__\s*==\s*['\"]__main__['\"]\s*:", original
    ))
    if len(matches) != 1:
        raise ValueError("Bridge startup anchor not unique.")
    location = matches[0].start()
    updated = original[:location] + tool_registrations() + original[location:]
    ast.parse(updated, filename="bridge/server.py")
    return updated


def patch_compose(original: str) -> str:
    if "/run/crew-maint" in original:
        raise ValueError("Maintenance mount already configured; refusing duplicate.")
    # Existing read-only pinned deployment socket is the only permitted anchor.
    matches = list(re.finditer(
        r"(?m)^(?P<indent>[ \t]*)- /run/crew-deploy:/run/crew-deploy:ro[ \t]*$",
        original,
    ))
    if len(matches) != 1:
        raise ValueError("Expected existing deployment-socket mount not found uniquely.")
    match = matches[0]
    mount = match.group("indent") + "- /run/crew-maint:/run/crew-maint:ro"
    return original[:match.end()] + "\n" + mount + original[match.end():]


def safe_existing_file(path: Path) -> None:
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"Unsafe file type: {path.name}")
    if details.st_uid != 0:
        raise ValueError(f"Expected root-owned file: {path.name}")


def atomic_replace(path: Path, content: str) -> None:
    previous = path.stat()
    fd, tmp_name = tempfile.mkstemp(prefix=".crew-ops-v2-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chown(tmp_name, previous.st_uid, previous.st_gid)
        os.chmod(tmp_name, stat.S_IMODE(previous.st_mode))
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def fixed(*args: str, timeout: int = 120) -> None:
    result = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        timeout=timeout, check=False,
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin",
             "LANG": "C"},
    )
    if result.returncode != 0:
        raise RuntimeError((result.stdout or "Command failed")[-1800:])


def main() -> None:
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise SystemExit("Requires a root-operated interactive VPS terminal.")
    if sys.argv[1:]:
        raise SystemExit("No arguments permitted.")
    if not HOST_SOCKET.is_socket():
        raise SystemExit("Maintenance socket missing. Stop; inspect crew-maint-v2.service.")
    safe_existing_file(SERVER)
    safe_existing_file(COMPOSE)
    before_server = SERVER.read_text(encoding="utf-8")
    before_compose = COMPOSE.read_text(encoding="utf-8")
    try:
        after_server = patch_server(before_server)
        after_compose = patch_compose(before_compose)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"Preflight refused: {exc}")
    print("CREW Ops v2 bridge activation")
    print("Files: bridge/server.py and compose.yaml only.")
    print("New MCP tools:", ", ".join(METHODS))
    print("Preserves all existing MCP tools, worker sockets and runner settings.")
    print("No application changes, PostgreSQL changes or server reboot.")
    if input("Type exactly 'ACTIVATE CREW OPS V2': ") != "ACTIVATE CREW OPS V2":
        raise SystemExit("Cancelled without changes.")

    BACKUP_BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_BASE / ("crew-ops-v2-" + stamp)
    backup.mkdir(mode=0o700)
    for src in (SERVER, COMPOSE):
        shutil.copy2(src, backup / src.name)
    print("Backup location:", backup)
    try:
        atomic_replace(SERVER, after_server)
        atomic_replace(COMPOSE, after_compose)
        fixed("docker", "compose", "-f", str(COMPOSE), "config", "--quiet")
    except Exception as exc:
        atomic_replace(SERVER, before_server)
        atomic_replace(COMPOSE, before_compose)
        raise SystemExit(f"Changes rolled back: {exc}")

    print("Bridge files validated. Rebuilding ONLY the bridge service...")
    try:
        fixed("docker", "compose", "-f", str(COMPOSE), "--project-directory",
              str(BRIDGE), "up", "-d", "--no-deps", "--build", "--force-recreate",
              "bridge", timeout=240)
        fixed("docker", "compose", "-f", str(COMPOSE), "--project-directory",
              str(BRIDGE), "exec", "-T", "bridge", "test", "-S",
              "/run/crew-maint/maint.sock", timeout=20)
        # Also verify RPC permissions: container UID 10001 + group 986 must
        # actually be able to connect and receive the finite method list.
        probe = (
            "import json,socket;"
            "s=socket.socket(socket.AF_UNIX);"
            "s.settimeout(8);"
            "s.connect('/run/crew-maint/maint.sock');"
            "s.sendall(b'{\"operation\":\"capabilities\"}' + bytes((10,)));"
            "d=json.loads(s.makefile().readline());"
            "assert d.get('ok') is True and d.get('shell_enabled') is False;"
            "assert 'dashboard' in d.get('operations',[]);"
            "print('CREW_OPS_V2_RPC_PASS')"
        )
        fixed("docker", "compose", "-f", str(COMPOSE), "--project-directory",
              str(BRIDGE), "exec", "-T", "bridge", "python", "-c",
              probe, timeout=20)
    except Exception as exc:
        # Preserve backups, patched files and error for operator review.
        # Do not touch the production CREW service or trigger migrations.
        raise SystemExit(f"Bridge activation needs inspection: {exc}")
    print("CREW OPS V2 BRIDGE SOCKET CONNECTED")
    print("MCP tools registered in bridge image. Refresh ChatGPT MCP connection.")
    print("No CREW app restart, DB writes, or v15 redeploy performed.")


if __name__ == "__main__":
    main()
