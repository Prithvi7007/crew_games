"""Safety checks for the reviewed, root-only v16 watcher policy upgrade."""

from pathlib import Path
import ast

import pytest

from deploy.ops import merge_auto_deploy as auto
from deploy.ops import upgrade_merge_auto_deploy as upgrade


def test_watcher_v16_revision_pin_is_exact():
    assert auto.DB_REVISION == "v16_trophy_tour"


def test_policy_upgrade_is_only_exact_schema_pin_change():
    old = b'REPOSITORY = "Prithvi7007/crew_games"\nDB_REVISION = "v15_badges"\nREQUIRED_STEPS = frozenset()\n'
    new = old.replace(upgrade.BEFORE, upgrade.AFTER)
    upgrade.validate_guard_upgrade(old, new)
    assert upgrade.BEFORE not in new
    for proposed in (old, new + b'\n# unrelated change', new.replace(b"frozenset()", b"None")):
        with pytest.raises(upgrade.UpgradeRefused, match="reviewed_watcher_has_other_changes"):
            upgrade.validate_guard_upgrade(old, proposed)


@pytest.mark.parametrize("installed", [
    b'DB_REVISION = "v16_trophy_tour"',
    b'DB_REVISION = "v14_seasons"',
    b"not a watcher",
    b'DB_REVISION = "v15_badges"\nDB_REVISION = "v15_badges"',
])
def test_policy_upgrade_refuses_unknown_or_already_updated_source(installed):
    with pytest.raises(upgrade.UpgradeRefused, match="unexpected_installed_watcher_version"):
        upgrade.validate_guard_upgrade(installed, installed.replace(upgrade.BEFORE, upgrade.AFTER))


def test_stale_database_revision_stays_blocked_even_if_main_is_current(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(auto.maint, "APPROVAL", tmp_path / "approval.json")
    monkeypatch.setattr(auto.maint, "maintenance_status", lambda: {"last_action": {}})
    monkeypatch.setattr(auto.maint, "git_sha", lambda: "a" * 40)
    monkeypatch.setattr(auto.maint, "database_summary", lambda: {"revision": "v15_badges"})
    monkeypatch.setattr(auto.maint, "service_active", lambda unit: True)
    monkeypatch.setattr(auto.maint, "socket_health", lambda: True)
    monkeypatch.setattr(auto, "main_sha", lambda: pytest.fail("must reject prior schema first"))
    with pytest.raises(auto.Blocked, match="schema_release_requires_manual_plan"):
        auto._run_once_locked()
    monkeypatch.setattr(auto.maint, "database_summary", lambda: {"revision": "v16_trophy_tour"})
    monkeypatch.setattr(auto, "main_sha", lambda: "a" * 40)
    assert auto._run_once_locked()["phase"] == "up_to_date"


def test_root_upgrade_script_has_no_release_or_state_reset():
    source = Path("deploy/ops/upgrade_merge_auto_deploy.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'watcher.merged_pr_number(reviewed_sha)' in source
    assert 'watcher.verify_ci(reviewed_sha)' in source
    assert 'maint.database_summary().get("revision") != "v16_trophy_tour"' in source
    assert 'not stopped(TIMER) or not stopped(SERVICE)' in source
    assert "deploy_code_only(" not in source
    assert "state_write(" not in source
    assert "systemctl\", \"start\"" not in source
