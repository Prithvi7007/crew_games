"""Fail-closed offline tests for verified-merge auto-deploy watch service."""
from __future__ import annotations

import hashlib
import ast
import json
from pathlib import Path
import stat
import types

import pytest

from deploy.ops import merge_auto_deploy as auto


RELEASE = "b" * 40
BASE = "a" * 40
PREVIOUS = "c" * 40


def pr(number, merge=RELEASE, merger="Prithvi7007"):
    return {
        "number": number, "state": "closed", "draft": False,
        "merged_at": "2026-10-11T07:52:38Z",
        "merge_commit_sha": merge,
        "merged_by": {"login": merger},
        "base": {"ref": "main", "repo": {"full_name": auto.REPOSITORY}},
    }


def ci_evidence(sha=RELEASE, result="success", steps=None):
    run = {"workflow_runs": [{
        "id": 123, "head_sha": sha, "event": "push",
        "head_branch": "main", "workflow_id": auto.CI_WORKFLOW_ID,
        "status": "completed", "conclusion": result,
    }]}
    if steps is None:
        steps = auto.REQUIRED_STEPS
    jobs = {"jobs": [{
        "name": "test-and-audit", "conclusion": "success",
        "steps": [{"name": s, "conclusion": "success"} for s in steps],
    }]}
    return run, jobs


def test_sha_rejects_injection_and_untrusted_commit():
    with pytest.raises(auto.Blocked):
        auto.sha("main")
    with pytest.raises(auto.Blocked):
        auto.sha("b" * 39 + ";")
    with pytest.raises(auto.Blocked):
        auto.sha({"sha": RELEASE})
    assert auto.sha(RELEASE) == RELEASE


def test_exact_merged_pr_and_maintainer_required(monkeypatch):
    monkeypatch.setattr(auto, "github_json", lambda path: (
        [{"number": 24, "merge_commit_sha": RELEASE}]
        if path.endswith("/pulls") else pr(24)))
    assert auto.merged_pr_number(RELEASE) == 24
    monkeypatch.setattr(auto, "github_json", lambda path: (
        [{"number": 24, "merge_commit_sha": RELEASE}]
        if path.endswith("/pulls") else pr(24, merger="unapproved-bot")))
    with pytest.raises(auto.Blocked, match="commit_not_approved"):
        auto.merged_pr_number(RELEASE)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(merged_at=None),
    lambda d: d.update(draft=True),
    lambda d: d.update(merge_commit_sha=PREVIOUS),
    lambda d: d["base"].update(ref="feature/not-main"),
    lambda d: d["base"]["repo"].update(full_name="other/fork"),
])
def test_pr_evidence_fail_closed(monkeypatch, mutate):
    details = pr(24)
    mutate(details)
    monkeypatch.setattr(auto, "github_json", lambda path: (
        [{"number": 24, "merge_commit_sha": RELEASE}]
        if path.endswith("/pulls") else details))
    with pytest.raises(auto.Blocked):
        auto.merged_pr_number(RELEASE)


def test_direct_push_in_first_parent_chain_is_refused(monkeypatch):
    monkeypatch.setattr(auto, "git", lambda *args: PREVIOUS + "\n" + RELEASE)
    called = []
    def check(commit):
        called.append(commit)
        if commit == PREVIOUS:
            raise auto.Blocked("commit_not_approved_pr_merge")
        return 24
    monkeypatch.setattr(auto, "merged_pr_number", check)
    with pytest.raises(auto.Blocked, match="commit_not_approved"):
        auto.verify_merge_chain(BASE, RELEASE)
    assert called == [PREVIOUS]


def test_every_first_parent_merge_must_be_verified(monkeypatch):
    monkeypatch.setattr(auto, "git", lambda *args: PREVIOUS + "\n" + RELEASE)
    seen = []
    def check(commit):
        seen.append(commit)
        return 24
    monkeypatch.setattr(auto, "merged_pr_number", check)
    assert auto.verify_merge_chain(BASE, RELEASE) == 24
    assert seen == [PREVIOUS, RELEASE]


def test_empty_or_huge_or_wrong_chain_refused(monkeypatch):
    for output in ("", PREVIOUS, "\n".join([PREVIOUS] * (auto.MAX_MERGES + 1)) + "\n" + RELEASE):
        monkeypatch.setattr(auto, "git", lambda *args, data=output: data)
        with pytest.raises(auto.Blocked, match="unverified_merge_chain"):
            auto.verify_merge_chain(BASE, RELEASE)


def test_merged_main_ci_with_required_steps_passes(monkeypatch):
    run, jobs = ci_evidence()
    monkeypatch.setattr(auto, "github_json", lambda path: jobs if "/jobs" in path else run)
    auto.verify_ci(RELEASE)


@pytest.mark.parametrize("change", [
    "pr_event", "wrong_sha", "wrong_workflow", "pending", "failed", "missing_steps",
])
def test_ci_evidence_fail_closed(monkeypatch, change):
    run, jobs = ci_evidence()
    item = run["workflow_runs"][0]
    if change == "pr_event":
        item["event"] = "pull_request"
    elif change == "wrong_sha":
        item["head_sha"] = PREVIOUS
    elif change == "wrong_workflow":
        item["workflow_id"] = 1
    elif change == "pending":
        item["status"] = "in_progress"
    elif change == "failed":
        item["conclusion"] = "failure"
    elif change == "missing_steps":
        jobs["jobs"][0]["steps"].pop()
    monkeypatch.setattr(auto, "github_json", lambda path: jobs if "/jobs" in path else run)
    with pytest.raises((auto.Waiting, auto.Blocked)):
        auto.verify_ci(RELEASE)


def test_external_manifest_is_never_overwritten(monkeypatch, tmp_path):
    target = tmp_path / "manifest.json"
    target.write_text("operator configured")
    target.chmod(0o400)
    monkeypatch.setattr(auto, "MANIFEST", target)
    with pytest.raises(auto.Blocked, match="unsafe_existing_manifest"):
        auto.check_existing_manifest({})
    assert target.read_text() == "operator configured"


def test_manual_approval_blocks_automation(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "STATE", tmp_path / "auto_state.json")
    monkeypatch.setattr(auto.maint, "APPROVAL", tmp_path / "approval.json")
    auto.maint.APPROVAL.write_text("{}")
    with pytest.raises(auto.Waiting, match="manual_approval_pending"):
        auto._run_once_locked()


def test_previous_failure_requires_human_review(monkeypatch, tmp_path):
    path = tmp_path / "auto_state.json"
    path.write_text(json.dumps({"phase": "failed"}))
    path.chmod(0o600)
    monkeypatch.setattr(auto, "STATE", path)
    monkeypatch.setattr(auto, "state_read", lambda: {"phase": "failed"})
    with pytest.raises(auto.Blocked, match="previous_release_needs_review"):
        auto._run_once_locked()


def test_successful_eligible_release_uses_reviewed_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "STATE", tmp_path / "auto_state.json")
    monkeypatch.setattr(auto, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(auto.maint, "APPROVAL", tmp_path / "approval.json")
    monkeypatch.setattr(auto.maint, "maintenance_status", lambda: {"last_action": {}})
    monkeypatch.setattr(auto.maint, "git_sha", lambda: BASE)
    monkeypatch.setattr(auto.maint, "database_summary", lambda: {"revision": auto.DB_REVISION})
    monkeypatch.setattr(auto.maint, "service_active", lambda service: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: True)
    monkeypatch.setattr(auto, "main_sha", lambda: RELEASE)
    monkeypatch.setattr(auto, "assert_clean_checkout", lambda path: None)
    monkeypatch.setattr(auto, "verify_merge_chain", lambda base, release: 24)
    monkeypatch.setattr(auto, "verify_ci", lambda release: None)
    executed = []
    def fake_git(path, *args, timeout=120):
        if args[0] in ("rev-parse", "merge-base"):
            return BASE if args[0] == "merge-base" else RELEASE
        if args[0] == "diff":
            return ""
        return ""
    monkeypatch.setattr(auto, "git", fake_git)
    original_manifest = auto.maint.RELEASE_MANIFEST
    def safe_preflight():
        assert auto.maint.RELEASE_MANIFEST == auto.MANIFEST
        executed.append("preflight")
    monkeypatch.setattr(auto.maint, "release_preflight", safe_preflight)
    monkeypatch.setattr(auto.maint, "deploy_code_only", lambda: executed.append("deployed"))
    monkeypatch.setattr(auto, "state_write", lambda state: (tmp_path / "auto_state.json").write_text(json.dumps(state)))
    # Simulate root chown while the sandbox tests run as unprivileged UID.
    monkeypatch.setattr(auto.os, "chown", lambda *args: None)
    result = auto._run_once_locked()
    assert result == {"phase": "succeeded", "release": RELEASE, "reviewed_pr": 24}
    assert executed == ["preflight", "deployed"]
    assert auto.maint.RELEASE_MANIFEST == original_manifest
    manifest = json.loads(auto.MANIFEST.read_text())
    assert manifest == {"format": 1, "kind": "code_only", "base": BASE,
                        "release": RELEASE, "db_revision": "v15_badges", "reviewed_pr": 24}
    assert stat.S_IMODE(auto.MANIFEST.stat().st_mode) == 0o400


def test_non_code_only_diff_never_deploys(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(auto.maint, "APPROVAL", tmp_path / "approval.json")
    monkeypatch.setattr(auto.maint, "maintenance_status", lambda: {"last_action": {}})
    monkeypatch.setattr(auto.maint, "git_sha", lambda: BASE)
    monkeypatch.setattr(auto.maint, "database_summary", lambda: {"revision": auto.DB_REVISION})
    monkeypatch.setattr(auto.maint, "service_active", lambda service: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: True)
    monkeypatch.setattr(auto, "main_sha", lambda: RELEASE)
    monkeypatch.setattr(auto, "assert_clean_checkout", lambda path: None)
    monkeypatch.setattr(auto, "verify_merge_chain", lambda *args: 24)
    monkeypatch.setattr(auto, "verify_ci", lambda *args: None)
    def fake_git(path, *args, **kw):
        if args[0] == "rev-parse": return RELEASE
        if args[0] == "merge-base": return BASE
        if args[0] == "diff": return "alembic/versions/malicious.py"
        return ""
    monkeypatch.setattr(auto, "git", fake_git)
    monkeypatch.setattr(auto.maint, "deploy_code_only", lambda: pytest.fail("deployed"))
    with pytest.raises(auto.Blocked, match="requires_schema_or_infrastructure_release"):
        auto._run_once_locked()


def test_no_release_if_main_matches_production(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(auto.maint, "APPROVAL", tmp_path / "approval.json")
    monkeypatch.setattr(auto.maint, "maintenance_status", lambda: {"last_action": {}})
    monkeypatch.setattr(auto.maint, "git_sha", lambda: BASE)
    monkeypatch.setattr(auto.maint, "database_summary", lambda: {"revision": auto.DB_REVISION})
    monkeypatch.setattr(auto.maint, "service_active", lambda service: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: True)
    monkeypatch.setattr(auto, "main_sha", lambda: BASE)
    assert auto._run_once_locked() == {"phase": "up_to_date", "release": BASE}


def test_operator_installer_never_executes_deploy():
    src = Path("deploy/ops/install_merge_auto_deploy.py").read_text()
    ast.parse(src)
    ast.parse(Path("deploy/ops/merge_auto_deploy.py").read_text())
    assert "enable" in src
    assert "merge-base" in src
    assert "git\", \"clone\"" in src
    assert "reset\", \"--hard\"" not in src
    assert "deploy_code_only(" not in src


def test_manual_manifest_blocks_auto_deployer(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "MANUAL_MANIFEST", tmp_path / "manual.json")
    monkeypatch.setattr(auto, "MANIFEST", tmp_path / "auto.json")
    auto.MANUAL_MANIFEST.write_text("{}")
    with pytest.raises(auto.Blocked, match="manual_release_manifest_present"):
        auto.check_existing_manifest({})
