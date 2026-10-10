"""One-time, local, root-operated CREW Ops v2 installation from a reviewed Git commit.

NO production checkout reset, app restart, database migration or restore.
Only installs the new independent maintenance host service; connector
registration in /opt/crew-dev-bridge must be reviewed separately.
"""
from __future__ import annotations

import grp
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = "/opt/crew"
DEST = Path("/usr/local/libexec/crew-maint")
UNIT = Path("/etc/systemd/system/crew-maint-v2.service")
STATE = Path("/var/lib/crew-maint")
ENTRIES = {
    "maintenance_v2.py": "deploy/ops/maintenance_v2.py",
    "bridge_maintenance_v2_client.py": "deploy/ops/bridge_maintenance_v2_client.py",
    "crew-maint-v2.service": "deploy/ops/crew-maint-v2.service",
}


def fixed(argv: list[str], *, timeout: int = 30) -> bytes:
    result = subprocess.run(
        argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=timeout, check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
    )
    if result.returncode != 0:
        raise SystemExit("Installation halted: required fixed command failed.")
    return result.stdout


def source_from_git(commit: str, path: str) -> bytes:
    return fixed([
        "/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
        "/usr/bin/git", "-c", f"safe.directory={REPO}", "-C", REPO,
        "show", f"{commit}:{path}",
    ])


def create_secure(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, mode)


def main() -> None:
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise SystemExit("Requires a root-operated interactive VPS terminal.")
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]):
        raise SystemExit("Usage: python3 -I -B install_maintenance_v2.py <reviewed-merge-commit-sha>")
    commit = sys.argv[1]
    if DEST.exists() or DEST.is_symlink() or UNIT.exists() or UNIT.is_symlink():
        raise SystemExit("An Ops v2 installation already exists; refusing to overwrite it.")
    grp.getgrnam("crew-ops")
    blobs = {name: source_from_git(commit, path) for name, path in ENTRIES.items()}
    if not all(blobs.values()):
        raise SystemExit("Empty installation artifact.")
    if b"CREW Ops v2" not in blobs["maintenance_v2.py"]:
        raise SystemExit("Unexpected host-service source.")
    print("CREW Ops v2 — independent host-service install")
    print("Reviewed Git commit:", commit)
    for name, data in blobs.items():
        print(name, hashlib.sha256(data).hexdigest())
    print("This does NOT deploy application code, change PostgreSQL, or restart crew.service.")
    print("This DOES install, enable and start the new crew-maint-v2.service.")
    if input("Type exactly 'INSTALL CREW OPS V2': ") != "INSTALL CREW OPS V2":
        raise SystemExit("Install cancelled.")

    DEST.mkdir(mode=0o700)
    os.chown(DEST, 0, 0)
    os.chmod(DEST, 0o700)
    create_secure(DEST / "maintenance_v2.py", blobs["maintenance_v2.py"], 0o400)
    create_secure(DEST / "bridge_maintenance_v2_client.py",
                  blobs["bridge_maintenance_v2_client.py"], 0o400)
    create_secure(UNIT, blobs["crew-maint-v2.service"], 0o644)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    (STATE / "consumed").mkdir(mode=0o700, exist_ok=True)
    for path in (STATE, STATE / "consumed"):
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
            raise SystemExit("Unsafe state directory; stop before starting the service.")
    fixed(["/usr/bin/systemd-analyze", "verify", str(UNIT)])
    fixed(["/usr/bin/systemctl", "daemon-reload"])
    fixed(["/usr/bin/systemctl", "enable", "--now", "crew-maint-v2.service"])
    fixed(["/usr/bin/systemctl", "is-active", "--quiet", "crew-maint-v2.service"])
    print("Host service installed. Mount /run/crew-maint read-only in the")
    print("separate development bridge and register the fixed MCP client functions.")
    print("NO CREW production database or application release actions performed.")


if __name__ == "__main__":
    main()
