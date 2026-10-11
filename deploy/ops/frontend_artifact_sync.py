"""Fixed frontend artifact publisher for the isolated CREW development runner.

Integrate as a dedicated, parameter-free bridge operation. The runner must
supply its trusted checkout path; callers cannot choose paths or commands.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

ARTIFACTS = ("app/static/react/player.js", "app/static/react/player.css")


class ArtifactSyncRefused(RuntimeError):
    pass


def _run(*args: str, cwd: Path, timeout: int = 180) -> str:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        check=False, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode:
        raise ArtifactSyncRefused("frontend_sync_step_failed")
    return result.stdout.strip()


def synchronize_frontend_assets(checkout: Path) -> dict:
    """Build and commit only generated assets on the current feature branch.

    Invoke from a trusted runner after branch creation; never expose checkout
    as a user-supplied MCP argument.
    """
    checkout = checkout.resolve(strict=True)
    branch = _run("git", "symbolic-ref", "--quiet", "--short", "HEAD", cwd=checkout)
    if not re.fullmatch(r"feature/[a-zA-Z0-9._/-]+", branch):
        raise ArtifactSyncRefused("feature_branch_required")
    if ".." in branch or branch.endswith("/") or "//" in branch:
        raise ArtifactSyncRefused("invalid_branch")
    status = _run("git", "status", "--porcelain", cwd=checkout)
    if status:
        raise ArtifactSyncRefused("clean_checkout_required")
    _run("npm", "ci", cwd=checkout / "frontend", timeout=180)
    _run("npm", "run", "build", cwd=checkout / "frontend", timeout=180)
    changed = _run("git", "status", "--porcelain", cwd=checkout)
    if not changed:
        return {"ok": True, "changed": False, "branch": branch}
    # Fail closed if build produced anything beyond the two approved artifacts.
    paths = _run("git", "status", "--porcelain", "--untracked-files=all", cwd=checkout)
    for line in paths.splitlines():
        if line[3:] not in ARTIFACTS:
            raise ArtifactSyncRefused("unexpected_build_output")
    _run("git", "add", "--", *ARTIFACTS, cwd=checkout)
    staged = _run("git", "diff", "--cached", "--name-only", cwd=checkout).splitlines()
    if not staged or not set(staged).issubset(ARTIFACTS):
        raise ArtifactSyncRefused("invalid_staged_files")
    _run("git", "-c", "user.name=CREW Build Bot",
         "-c", "user.email=crew-build-bot@users.noreply.github.com",
         "commit", "-m", "build: synchronize React assets", cwd=checkout)
    _run("git", "push", "origin", f"HEAD:refs/heads/{branch}", cwd=checkout)
    return {"ok": True, "changed": True, "branch": branch, "files": staged}
