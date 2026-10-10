"""On-host, root-only explicit release authorization.

This command is intentionally NOT an MCP tool. Run only after independently
reviewing the exact release plan, backup and scratch rehearsal. Approving once
does not authorize future releases and never performs a deployment itself.
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from release_broker import (
    APPROVAL, BASE, RELEASE, approval_plan_digest, deployment_engine_safe,
)

CONFIRMATION = "DEPLOY CREW V15"


def stage_one_approval(input_func=input) -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("root_only")
    if not deployment_engine_safe():
        raise RuntimeError("worker_not_safely_installed")
    parent = APPROVAL.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
        raise RuntimeError("approval_directory_not_protected")
    if APPROVAL.exists() or APPROVAL.is_symlink():
        raise RuntimeError("approval_already_exists")
    print(f"Release SHA: {RELEASE}")
    print(f"Current production SHA required: {BASE}")
    plan_digest = approval_plan_digest()
    print(f"Approved plan digest: {plan_digest}")
    print("Scope: v14 to v15 badge migration, code update, and crew restart")
    print("Requires successful scratch rehearsal and fresh database backup.")
    print("No automatic database restore or downgrade.")
    print("This arms ONE attempt for 15 minutes; it does not deploy anything.")
    typed = input_func(f"Type exactly {CONFIRMATION!r} to approve: ")
    if typed != CONFIRMATION:
        raise RuntimeError("approval_not_granted")
    doc = {
        "operation": "execute_v15",
        "release_sha": RELEASE,
        "production_sha": BASE,
        "confirmation": CONFIRMATION,
        "nonce": secrets.token_hex(16),
        "plan_digest": plan_digest,
        "expires_at": (dt.datetime.now(dt.timezone.utc)
                       + dt.timedelta(minutes=10)).isoformat(),
    }
    # Exclusive create, no symlink and no overwrite of any other approvals.
    fd = os.open(APPROVAL, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        APPROVAL.unlink(missing_ok=True)
        raise
    print("One-time approval staged. Only the fixed v15 release may consume it.")
    return doc


if __name__ == "__main__":
    try:
        stage_one_approval()
    except (RuntimeError, OSError) as exc:
        print(f"APPROVAL DENIED: {exc}", file=sys.stderr)
        raise SystemExit(1)
