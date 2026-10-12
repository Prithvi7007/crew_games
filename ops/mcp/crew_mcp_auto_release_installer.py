#!/usr/bin/env python3
"""Install a fixed MCP trigger for the existing CREW merged-PR release watcher.

Run as root on the CREW VPS, review source first. Does not start a release.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone

MAINT = Path('/usr/local/libexec/crew-maint/maintenance_v2.py')
BRIDGE = Path('/opt/crew-dev-bridge/bridge/server.py')
CLIENT = Path('/usr/local/libexec/crew-maint/bridge_maintenance_v2_client.py')
COMPOSE_DIR = Path('/opt/crew-dev-bridge')
BACKUP_ROOT = Path('/root/crew-mcp-autorelease-backups')

HOST_HELPERS = '''
# BEGIN CREW MCP AUTO RELEASE: fixed, no-argument existing systemd unit trigger
_AUTO_RELEASE_UNIT = "crew-auto-release.service"
_AUTO_RELEASE_LOCK = threading.Lock()


def auto_release_status() -> dict:
    """Read current unit state, not a guarantee that a new release completed."""
    ok, details = fixed(
        "/usr/bin/systemctl", "show", "--no-pager",
        "--property=LoadState,ActiveState,SubState,Result,ExecMainStatus",
        _AUTO_RELEASE_UNIT,
    )
    if not ok:
        return {"ok": False, "error": "auto_release_status_unavailable"}
    fields = dict(
        line.split("=", 1) for line in details.splitlines() if "=" in line
    )
    return {
        "ok": True,
        "unit": _AUTO_RELEASE_UNIT,
        "load_state": fields.get("LoadState", "unknown"),
        "active_state": fields.get("ActiveState", "unknown"),
        "sub_state": fields.get("SubState", "unknown"),
        "last_result": fields.get("Result", "unknown"),
        "last_exit_status": fields.get("ExecMainStatus", "unknown"),
        "production_commit": git_sha(),
    }


def trigger_auto_release() -> dict:
    """Queue ONLY the already installed, verified, merged-PR watcher.

    Installing this root-owned handler is the one-time operator authorization.
    The watcher still makes the final release/no-op decision. This function
    never accepts a commit, path, command, or caller-supplied arguments.
    """
    with _AUTO_RELEASE_LOCK:
        ok, loaded = fixed(
            "/usr/bin/systemctl", "show", "--property=LoadState",
            "--value", _AUTO_RELEASE_UNIT,
        )
        if not ok or loaded != "loaded":
            return {"ok": False, "error": "auto_release_unit_unavailable"}
        previous = git_sha()
        active, _ = fixed(
            "/usr/bin/systemctl", "is-active", "--quiet", _AUTO_RELEASE_UNIT,
        )
        if active:
            return {"ok": True, "state": "already_running",
                    "production_commit_at_request": previous}
        ok, _ = fixed(
            "/usr/bin/systemctl", "start", "--no-block", _AUTO_RELEASE_UNIT,
        )
        if not ok:
            return {"ok": False, "error": "auto_release_start_failed"}
        print("crew_mcp_auto_release_requested", file=sys.stderr, flush=True)
        return {"ok": True, "state": "queued",
                "production_commit_at_request": previous,
                "note": "queued_only_check_status_to_confirm_completion"}
# END CREW MCP AUTO RELEASE

'''

BRIDGE_TOOLS = '''
# BEGIN CREW MCP AUTO RELEASE: zero-argument operations only
@mcp.tool()
def crew_trigger_auto_release() -> dict:
    """Queue the fixed, verified merged-PR code-only watcher; no SHA/command inputs."""
    return _crew_maint_request("trigger_auto_release")


@mcp.tool()
def crew_auto_release_status() -> dict:
    """Inspect watcher status and production SHA; queued does not mean deployed."""
    return _crew_maint_request("auto_release_status")
# END CREW MCP AUTO RELEASE

'''

CLIENT_TOOLS = '''
# BEGIN CREW MCP AUTO RELEASE: reference adapter

def crew_trigger_auto_release() -> dict:
    return request("trigger_auto_release")


def crew_auto_release_status() -> dict:
    return request("auto_release_status")
# END CREW MCP AUTO RELEASE
'''


def replace_one(value: str, before: str, after: str, label: str) -> str:
    if value.count(before) != 1:
        raise ValueError(f'{label}: expected exactly one insertion anchor; found {value.count(before)}')
    return value.replace(before, after, 1)


def patch_maint(value: str) -> str:
    if 'BEGIN CREW MCP AUTO RELEASE' in value:
        raise ValueError('maintenance handler already contains the auto-release integration')
    value = replace_one(value,
        '    "code_release_plan", "execute_code_release",\n',
        '    "code_release_plan", "execute_code_release",\n'
        '    "auto_release_status", "trigger_auto_release",\n', 'maintenance ops')
    anchor = 'def respond(message: object) -> dict:\n'
    value = replace_one(value, anchor, HOST_HELPERS + anchor, 'maintenance helpers')
    anchor = '        if op == "execute_code_release":\n            return start_code_release()\n'
    value = replace_one(value, anchor,
        anchor + '        if op == "auto_release_status":\n'
                 '            return auto_release_status()\n'
                 '        if op == "trigger_auto_release":\n'
                 '            return trigger_auto_release()\n', 'maintenance dispatch')
    return value


def patch_bridge(value: str) -> str:
    if 'BEGIN CREW MCP AUTO RELEASE' in value:
        raise ValueError('bridge already contains the auto-release integration')
    anchor = '    "code_release_plan", "execute_code_release",\n'
    value = replace_one(value, anchor, anchor +
                        '    "auto_release_status", "trigger_auto_release",\n', 'bridge allowlist')
    anchor = '@mcp.tool()\ndef crew_maint_capabilities() -> dict:\n'
    value = replace_one(value, anchor, BRIDGE_TOOLS + anchor, 'bridge functions')
    value = replace_one(value,
        'Never operate on production or merge PRs.',
        'Never merge PRs or use arbitrary production commands. Only the fixed auto-release trigger may request the existing verified release watcher.',
        'bridge instructions')
    return value


def patch_client(value: str) -> str:
    if 'BEGIN CREW MCP AUTO RELEASE' in value:
        raise ValueError('maintenance reference client already contains the auto-release integration')
    anchor = '    "code_release_plan", "execute_code_release",\n'
    value = replace_one(value, anchor, anchor +
                        '    "auto_release_status", "trigger_auto_release",\n', 'reference allowlist')
    return value.rstrip() + '\n\n' + CLIENT_TOOLS


def root_owned_regular_file(path: Path) -> None:
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or path.is_symlink():
        raise ValueError(f'{path}: expected root-owned regular file (no symlinks)')


def check_command(args: list[str], *, cwd: Path | None = None) -> None:
    print('Running:', ' '.join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True, timeout=240,
                   env={'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin', 'LANG': 'C'})


def atomic_write(path: Path, content: str) -> None:
    st = path.stat()
    tmp = path.with_name('.' + path.name + f'.mcp-new-{os.getpid()}')
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                     stat.S_IMODE(st.st_mode))
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chown(tmp, st.st_uid, st.st_gid)
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='actually install and restart ONLY maintenance gateway + bridge')
    args = parser.parse_args()
    if os.geteuid() != 0:
        print('Run as root', file=sys.stderr)
        return 1

    files = [(MAINT, patch_maint), (BRIDGE, patch_bridge), (CLIENT, patch_client)]
    updates = {}
    for path, patch in files:
        root_owned_regular_file(path)
        original = path.read_text(encoding='utf-8')
        transformed = patch(original)
        compile(transformed, str(path), 'exec')
        updates[path] = transformed
        print(f'Validated patch: {path} ({len(original)} -> {len(transformed)} chars)')
    if not args.apply:
        print('DRY RUN PASSED. No files changed, no services restarted.')
        return 0

    print('\nThis enables a remote MCP request to START the existing auto-release watcher.')
    print('The watcher will still apply its own verified merged-PR checks.')
    phrase = input('Type ENABLE CREW MCP AUTO RELEASE to install: ').strip()
    if phrase != 'ENABLE CREW MCP AUTO RELEASE':
        print('Cancelled. No changes made.')
        return 2

    backup = BACKUP_ROOT / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(backup, 0o700)
    for i, (path, _) in enumerate(files):
        shutil.copy2(path, backup / f'{i}-{path.name}', follow_symlinks=False)
    print('Backup:', backup)

    try:
        for path, _ in files:
            atomic_write(path, updates[path])
        check_command(['/usr/bin/python3', '-m', 'py_compile', str(MAINT), str(BRIDGE), str(CLIENT)])
        check_command(['/usr/bin/systemctl', 'restart', 'crew-maint-v2.service'])
        check_command(['/usr/bin/docker', 'compose', 'up', '-d', '--build', '--no-deps', 'bridge'], cwd=COMPOSE_DIR)
        check_command(['/usr/bin/systemctl', 'is-active', '--quiet', 'crew-maint-v2.service'])
        print('INSTALLED: maintenance gateway and MCP bridge updated.')
        print('The auto-release service was NOT started.')
        print('Backup retained at:', backup)
    except (Exception, KeyboardInterrupt) as e:
        print('ERROR, restoring original files:', e, file=sys.stderr)
        for i, (path, _) in enumerate(files):
            atomic_write(path, (backup / f'{i}-{path.name}').read_text(encoding='utf-8'))
        print('Original files restored. Restarting original gateway and bridge.', file=sys.stderr)
        for cmd, cwd in [(['/usr/bin/systemctl', 'restart', 'crew-maint-v2.service'], None),
                         (['/usr/bin/docker', 'compose', 'up', '-d', '--build', '--no-deps', 'bridge'], COMPOSE_DIR)]:
            try:
                check_command(cmd, cwd=cwd)
            except Exception as recovery_error:
                print('Recovery restart failed:', recovery_error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
