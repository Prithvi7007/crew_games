"""Reference client/adapter for the externally hosted CREW MCP bridge.

The bridge container mounts /run/crew-maint:ro (Unix socket only). No host
root, database socket, Docker socket, credentials, or arbitrary commands.
Register the fixed functions below as explicit zero-argument MCP tools.
"""
from __future__ import annotations

import json
import socket

SOCKET = "/run/crew-maint/maint.sock"
ALLOWED = {
    "capabilities", "dashboard", "asset_diagnostics", "incident_summary",
    "maintenance_status", "plan_repair_react_assets", "plan_restart_crew",
    "execute_repair_react_assets", "execute_restart_crew",
    "code_release_plan", "execute_code_release",
}


def request(operation: str) -> dict:
    if operation not in ALLOWED:
        return {"ok": False, "error": "operation_not_allowed"}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(100 if operation == "execute_restart_crew" else 25)
            conn.connect(SOCKET)
            conn.sendall((json.dumps({"operation": operation}) + "\n").encode())
            chunks = bytearray()
            while not chunks.endswith(b"\n"):
                part = conn.recv(4096)
                if not part or len(chunks) + len(part) > 16384:
                    raise ValueError("unexpected response")
                chunks.extend(part)
        result = json.loads(chunks)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("invalid response")
        return result
    except (OSError, ValueError):
        return {"ok": False, "error": "maintenance_socket_unavailable"}


def crew_maint_capabilities() -> dict:
    return request("capabilities")


def crew_maint_dashboard() -> dict:
    return request("dashboard")


def crew_maint_assets() -> dict:
    return request("asset_diagnostics")


def crew_maint_incidents() -> dict:
    return request("incident_summary")


def crew_maint_status() -> dict:
    return request("maintenance_status")


def crew_maint_plan_asset_repair() -> dict:
    return request("plan_repair_react_assets")


def crew_maint_plan_restart() -> dict:
    return request("plan_restart_crew")


def crew_maint_execute_asset_repair() -> dict:
    return request("execute_repair_react_assets")


def crew_maint_execute_restart() -> dict:
    return request("execute_restart_crew")

def crew_maint_code_release_plan() -> dict:
    return request("code_release_plan")


def crew_maint_execute_code_release() -> dict:
    return request("execute_code_release")
