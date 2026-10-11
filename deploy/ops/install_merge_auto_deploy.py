"""One-time root installation of the separately reviewed CREW merge watcher.

No production checkout reset, migration or application restart. Requires a
reviewed, merged Git SHA. No token, deployment approval or generic shell.
"""
from __future__ import annotations

import grp
import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

REPO = Path("/opt/crew")
HOST = Path("/usr/local/libexec/crew-maint")
CANDIDATE = Path("/opt/crew-release-candidate")
FILES = (
    ("deploy/ops/merge_auto_deploy.py", HOST / "merge_auto_deploy.py", 0o400),
    ("deploy/ops/crew-auto-release.service",
     Path("/etc/systemd/system/crew-auto-release.service"), 0o644),
    ("deploy/ops/crew-auto-release.timer",
     Path("/etc/systemd/system/crew-auto-release.timer"), 0o644),
)
SHA = re.compile(r"^[0-9a-f]{40}$")


def fixed(*argv: str, timeout: int = 120) -> bytes:
    try:
        process = subprocess.run(
            argv, input=b"", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("Required reviewed installation command failed.") from exc
    if process.returncode:
        raise SystemExit("Required reviewed installation command failed.")
    return process.stdout


def crew_git(*args: str) -> bytes:
    return fixed("/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
                 "/usr/bin/git", "-c", f"safe.directory={REPO}",
                 "-C", str(REPO), *args)


def install_new(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit("Installation refused: an auto-release file already exists.")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chown(path, 0, 0)
    os.chmod(path, mode)


def main() -> None:
    if os.geteuid() != 0 or len(sys.argv) != 2 or not SHA.fullmatch(sys.argv[1]):
        raise SystemExit("Run as root with the exact, reviewed merged commit SHA.")
    reviewed = sys.argv[1]
    maintenance = HOST / "maintenance_v2.py"
    state = Path("/var/lib/crew-maint")
    host_info = HOST.lstat()
    maint_info = maintenance.lstat()
    state_info = state.lstat()
    if (not stat.S_ISDIR(host_info.st_mode) or host_info.st_uid != 0
            or stat.S_IMODE(host_info.st_mode) & 0o022
            or not stat.S_ISREG(maint_info.st_mode) or maint_info.st_uid != 0
            or stat.S_IMODE(maint_info.st_mode) & 0o022):
        raise SystemExit("Install the trusted root-only CREW Ops v2 controller first.")
    if (not stat.S_ISDIR(state_info.st_mode) or state_info.st_uid != 0
            or stat.S_IMODE(state_info.st_mode) & 0o077):
        raise SystemExit("Unsafe maintenance state directory.")
    if (CANDIDATE.exists() or CANDIDATE.is_symlink()
            or any(dst.exists() or dst.is_symlink() for _, dst, _ in FILES)):
        raise SystemExit("Installation already present or candidate conflicts; no overwrite.")
    if crew_git("status", "--porcelain").strip():
        raise SystemExit("Production worktree has changes; stop.")
    # Fetch Git objects only; never checkout or reset production here.
    crew_git("fetch", "--no-tags", "origin", "refs/heads/main")
    fixed("/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
          "/usr/bin/git", "-c", f"safe.directory={REPO}", "-C", str(REPO),
          "merge-base", "--is-ancestor", reviewed, "FETCH_HEAD")
    entries = []
    for src, dst, mode in FILES:
        data = crew_git("show", reviewed + ":" + src)
        if not data or len(data) > 100_000:
            raise SystemExit("Invalid source artifact.")
        entries.append((dst, mode, data))
    print("CREW MERGED-PR AUTO DEPLOY — ONE-TIME INSTALL REVIEW")
    print("Reviewed merge SHA:", reviewed)
    for dst, _, data in entries:
        print(dst, hashlib.sha256(data).hexdigest())
    print("Installs a 15-minute watcher of merged PRs with passing main CI.")
    print("No additional VPS deployment approval will be required after installation.")
    print("No migrations, protected config, database writes or rollback are allowed.")
    print("The next timer run MAY deploy already-merged code if all checks pass.")
    if not sys.stdin.isatty() or input("Type 'ENABLE CREW MERGE DEPLOY' to install: ") != "ENABLE CREW MERGE DEPLOY":
        raise SystemExit("Not installed.")

    user = pwd.getpwnam("crew")
    group = grp.getgrnam("www-data")
    CANDIDATE.mkdir(mode=0o750)
    os.chown(CANDIDATE, user.pw_uid, group.gr_gid)
    os.chmod(CANDIDATE, 0o750)
    fixed("/usr/sbin/runuser", "-u", "crew", "-g", "www-data", "--",
          "/usr/bin/git", "clone", "--no-tags", "--branch", "main",
          "https://github.com/Prithvi7007/crew_games.git", str(CANDIDATE), timeout=180)
    for dst, mode, data in entries:
        install_new(dst, data, mode)
    fixed("/usr/bin/systemctl", "daemon-reload")
    fixed("/usr/bin/systemd-analyze", "verify",
          "/etc/systemd/system/crew-auto-release.service",
          "/etc/systemd/system/crew-auto-release.timer")
    fixed("/usr/bin/systemctl", "enable", "--now", "crew-auto-release.timer")
    print("Installed timer. No immediate production deployment or restart performed.")
    print("Check: systemctl list-timers crew-auto-release.timer")


if __name__ == "__main__":
    main()
