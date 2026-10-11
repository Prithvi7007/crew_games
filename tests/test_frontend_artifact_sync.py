from pathlib import Path

import pytest

from deploy.ops import frontend_artifact_sync as sync


def test_refuses_main_without_running_build(monkeypatch, tmp_path):
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        return "main"
    monkeypatch.setattr(sync, "_run", fake)
    with pytest.raises(sync.ArtifactSyncRefused, match="feature_branch_required"):
        sync.synchronize_frontend_assets(tmp_path)
    assert len(calls) == 1


def test_no_changes_after_build(monkeypatch, tmp_path):
    outputs = iter(["feature/trophy", "", "", "", ""])
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        return next(outputs)
    monkeypatch.setattr(sync, "_run", fake)
    result = sync.synchronize_frontend_assets(tmp_path)
    assert result == {"ok": True, "changed": False, "branch": "feature/trophy"}
    assert not any("push" in call for call in calls)


def test_rejects_unexpected_build_files(monkeypatch, tmp_path):
    outputs = iter(["feature/trophy", "", "", "", " M app/config.py", " M app/config.py"])
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        return next(outputs)
    monkeypatch.setattr(sync, "_run", fake)
    with pytest.raises(sync.ArtifactSyncRefused, match="unexpected_build_output"):
        sync.synchronize_frontend_assets(tmp_path)
    assert not any("push" in call for call in calls)


def test_pushes_only_expected_assets(monkeypatch, tmp_path):
    outputs = iter([
        "feature/trophy", "", "", "", " M app/static/react/player.css",
        " M app/static/react/player.css", "",
        "app/static/react/player.css", "", "",
    ])
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        return next(outputs)
    monkeypatch.setattr(sync, "_run", fake)
    result = sync.synchronize_frontend_assets(tmp_path)
    assert result["files"] == ["app/static/react/player.css"]
    assert any(call[:2] == ("git", "push") for call in calls)
    assert not any("main" in call for call in calls)


def test_rejects_branch_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "_run", lambda *a, **kw: "feature/../main")
    with pytest.raises(sync.ArtifactSyncRefused, match="invalid_branch"):
        sync.synchronize_frontend_assets(tmp_path)
