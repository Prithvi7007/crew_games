"""Conservative offline source patcher for CREW Development Bridge.

Run against a COPY of the bridge repo first. Never touches production.
Refuses unknown source layouts and keeps timestamped backups.
"""
from pathlib import Path
import argparse
import ast
import shutil
import time

RUNNER_HOOK = '''
        if kind == 'react_build' and code == 0:
            # Only the supervisor copies bounded, known outputs out of the
            # unprivileged, network-disabled build checkout.
            import hashlib
            import stat
            import uuid
            allowed = ('app/static/react/player.js', 'app/static/react/player.css')
            export_root = QUEUE / 'artifacts' / job_id
            export_root.mkdir(parents=True, exist_ok=False)
            manifest = {}
            try:
                for rel in allowed:
                    path = working / rel
                    st = path.lstat()
                    if not stat.S_ISREG(st.st_mode) or st.st_size > 250_000:
                        raise ValueError('Unsafe or oversized frontend artifact')
                    raw = path.read_bytes()
                    raw.decode('utf-8')
                    if len(raw) > 250_000:
                        raise ValueError('Oversized frontend artifact')
                    dest = export_root / Path(rel).name
                    dest.write_bytes(raw)
                    manifest[rel] = hashlib.sha256(raw).hexdigest()
                (export_root / 'manifest.json').write_text(json.dumps(manifest))
            except Exception:
                shutil.rmtree(export_root, ignore_errors=True)
                raise
'''

CORE_HOOK = '''

def sync_frontend_assets(job_id: str) -> dict:
    """Import verified outputs of a passing isolated React build.

    This is intentionally limited to two checked-in UTF-8 build assets.
    It never runs repository code, accesses production, or commits anything.
    """
    import stat
    if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise BridgeError('Invalid job id')
    allowed = ('app/static/react/player.js', 'app/static/react/player.css')
    with locked():
        active = validate_branch(branch())
        result_path = QUEUE / 'results' / (job_id + '.json')
        if not result_path.is_file():
            raise BridgeError('Build result not found')
        result = json.loads(result_path.read_text())
        if (result.get('job_id') != job_id or result.get('kind') != 'react_build'
                or result.get('state') != 'passed' or result.get('exit_code') != 0
                or result.get('branch') != active or result.get('fingerprint') != fingerprint()):
            raise BridgeError('Build result does not match current workspace')
        root = QUEUE / 'artifacts' / job_id
        manifest_path = root / 'manifest.json'
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise BridgeError('Missing artifact manifest')
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict) or set(manifest) != set(allowed):
            raise BridgeError('Unexpected artifact manifest')
        pending = {}
        for rel in allowed:
            source = root / Path(rel).name
            st = source.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
                raise BridgeError('Unsafe or oversized build output')
            raw = source.read_bytes()
            raw.decode('utf-8')
            if hashlib.sha256(raw).hexdigest() != manifest[rel]:
                raise BridgeError('Build artifact checksum mismatch')
            target = safe_path(rel)
            if not target.is_file() or target.is_symlink():
                raise BridgeError('Missing or unsafe target asset')
            pending[rel] = raw
        # Stage both files before changing either. Roll back if any replacement
        # fails, including errors during the second replacement.
        staged = {}
        originals = {}
        replaced = []
        try:
            for rel, raw in pending.items():
                target = safe_path(rel)
                originals[rel] = target.read_bytes()
                temp = target.with_name('.bridge-' + uuid.uuid4().hex)
                staged[rel] = temp
                with temp.open('xb') as handle:
                    handle.write(raw)
                os.chmod(temp, 0o644)
            for rel in allowed:
                os.replace(staged[rel], safe_path(rel))
                replaced.append(rel)
        except Exception as exc:
            rollback_errors = []
            for rel in reversed(replaced):
                target = safe_path(rel)
                restore = target.with_name('.bridge-rollback-' + uuid.uuid4().hex)
                try:
                    restore.write_bytes(originals[rel])
                    os.chmod(restore, 0o644)
                    os.replace(restore, target)
                except Exception as rollback_exc:
                    rollback_errors.append(type(rollback_exc).__name__)
                finally:
                    restore.unlink(missing_ok=True)
            if rollback_errors:
                raise BridgeError('Asset import failed; rollback incomplete; inspect workspace before continuing') from exc
            raise BridgeError('Asset import failed; previous assets restored') from exc
        finally:
            for temp in staged.values():
                temp.unlink(missing_ok=True)
        audit('sync_frontend_assets', branch=active, job_id=job_id, paths=list(allowed))
        return {'branch': active, 'job_id': job_id, 'paths': list(allowed),
                'fingerprint': fingerprint(), 'requires_new_checks': True}
'''

SERVER_HOOK = '''
@mcp.tool()
def crew_sync_frontend_assets(job_id: str) -> dict:
    """Import checked React build outputs from a matching passing sandbox job."""
    return core.sync_frontend_assets(job_id)

'''

def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise ValueError(f'Expected one {label} anchor, found {source.count(old)}')
    return source.replace(old, new, 1)


def patch(root: Path, dry_run: bool):
    paths = [root / 'runner/worker.py', root / 'bridge/core.py', root / 'bridge/server.py']
    originals = [p.read_text() for p in paths]
    runner, core, server = originals
    runner = replace_once(runner,
        "        code, output = _run_check(cmd, cwd, env)\n        return {'job_id': job_id,",
        "        code, output = _run_check(cmd, cwd, env)\n" + RUNNER_HOOK + "        return {'job_id': job_id,",
        'runner build hook')
    core = replace_once(core, '\ndef commit_and_push(message: str) -> dict:', CORE_HOOK + '\ndef commit_and_push(message: str) -> dict:', 'core sync hook')
    server = replace_once(server, '\n@mcp.tool()\ndef crew_commit_and_push(', '\n' + SERVER_HOOK + '@mcp.tool()\ndef crew_commit_and_push(', 'MCP tool hook')
    updated = [runner, core, server]
    for path, content in zip(paths, updated):
        ast.parse(content, filename=str(path))
    if dry_run:
        print('PASS: all anchors found; patched Python parses; no files changed')
        return
    backups = []
    written = []
    try:
        for path, old, new in zip(paths, originals, updated):
            backup = path.with_name(path.name + '.before-artifact-sync-' + str(int(time.time())))
            shutil.copy2(path, backup)
            backups.append((path, backup))
            tmp = path.with_name(path.name + '.artifact-sync-tmp')
            try:
                tmp.write_text(new)
                tmp.chmod(path.stat().st_mode & 0o777)
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
            written.append(path)
        print('Patched:', ', '.join(str(p) for p in paths))
        print('Backups:', ', '.join(str(b) for _, b in backups))
    except Exception:
        for path, backup in backups:
            if path in written:
                shutil.copy2(backup, path)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', type=Path, help='bridge repository root (not production)')
    parser.add_argument('--apply', action='store_true', help='modify files after validation')
    args = parser.parse_args()
    patch(args.repo, not args.apply)
