"""Example bridge-side client for the restricted CREW host operations socket.

Only calls a finite list of operations. Do not expose a generic
run(command=...) MCP tool. To be copied into the separate development bridge
only after reviewing host socket access, Docker mounts and permissions.
"""
from __future__ import annotations

import json
import re
import socket

SOCKET_PATH = "/run/crew-ops/ops.sock"
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")


class OpsUnavailable(RuntimeError):
    pass


def _request(operation: str, *, job_id: str | None = None) -> dict:
    if operation not in {"capabilities", "release_preflight",
                         "start_v15_rehearsal", "rehearsal_status"}:
        raise ValueError("Operation not allowed")
    payload = {"operation": operation}
    if operation == "rehearsal_status":
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise ValueError("Invalid job ID")
        payload["job_id"] = job_id
    elif job_id is not None:
        raise ValueError("Unexpected job ID")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(40)
            sock.connect(SOCKET_PATH)
            sock.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            received = b""
            while not received.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk or len(received) + len(chunk) > 16384:
                    raise OpsUnavailable("Invalid operations response")
                received += chunk
        reply = json.loads(received)
    except (OSError, ValueError) as exc:
        raise OpsUnavailable("CREW host operations runner is unavailable") from exc
    if not isinstance(reply, dict) or not isinstance(reply.get("ok"), bool):
        raise OpsUnavailable("Invalid operations response")
    return reply


def crew_ops_capabilities() -> dict:
    return _request("capabilities")


def crew_release_preflight() -> dict:
    return _request("release_preflight")


def crew_start_v15_rehearsal() -> dict:
    return _request("start_v15_rehearsal")


def crew_v15_rehearsal_status(job_id: str) -> dict:
    return _request("rehearsal_status", job_id=job_id)
