"""Reference MCP-side client for the separate fixed CREW deployment broker.

This file is NOT installed into the separately hosted development bridge
by a CREW app-repository merge. The actual bridge integration must only
mount the restricted /run/crew-deploy directory and register three functions.
No general command/argument passthrough is permitted.
"""
from __future__ import annotations

import json
import socket

SOCKET_PATH = "/run/crew-deploy/deploy.sock"
ALLOWED = {"release_plan", "release_status", "execute_v15"}


def _fixed_request(operation: str) -> dict:
    if operation not in ALLOWED:
        return {"ok": False, "error": "operation_not_allowed"}
    data = (json.dumps({"operation": operation}) + "\n").encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(20)
            client.connect(SOCKET_PATH)
            client.sendall(data)
            received = b""
            while not received.endswith(b"\n"):
                chunk = client.recv(4096)
                if not chunk or len(received) + len(chunk) > 8192:
                    raise ValueError("unexpected broker response")
                received += chunk
        result = json.loads(received)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("bad response type")
        return result
    except (OSError, ValueError):
        return {"ok": False, "error": "deployment_broker_unavailable"}


def crew_deploy_plan() -> dict:
    """Read fixed release steps and plan digest; no production writes."""
    return _fixed_request("release_plan")


def crew_deploy_status() -> dict:
    """Read last deployment's sanitized phase; no production writes."""
    return _fixed_request("release_status")


def crew_deploy_execute_v15() -> dict:
    """Attempt the exact v15 release. Requires external root-owned approval."""
    return _fixed_request("execute_v15")
