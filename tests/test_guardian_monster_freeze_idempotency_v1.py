from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = ROOT / "devsystem" / "monster_wnba_pra_runless_upcoming_gate_closeout_r1.py"


def _load_closeout():
    requests = types.ModuleType("requests")
    requests.get = lambda *args, **kwargs: None
    requests.put = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("registry write must not happen"))
    sys.modules["requests"] = requests

    playwright_pkg = types.ModuleType("playwright")
    playwright_sync = types.ModuleType("playwright.sync_api")
    playwright_sync.sync_playwright = lambda: None
    sys.modules["playwright"] = playwright_pkg
    sys.modules["playwright.sync_api"] = playwright_sync

    browser_qa = types.ModuleType("devsystem.browser_qa_v1")
    browser_qa.BrowserQAFailure = RuntimeError
    browser_qa._body_has_forbidden_error = lambda *args, **kwargs: False
    browser_qa._find_app_frame = lambda *args, **kwargs: (None, [])
    sys.modules["devsystem.browser_qa_v1"] = browser_qa

    registry = types.ModuleType("devsystem.frozen_artifact_registry_v1")
    registry.validate_registry = lambda payload: None
    sys.modules["devsystem.frozen_artifact_registry_v1"] = registry

    spec = importlib.util.spec_from_file_location("guardian_monster_closeout", CLOSEOUT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_existing_freeze_with_identical_blobs_is_read_only_idempotent_across_later_main_sha(monkeypatch):
    closeout = _load_closeout()
    original_sha = "a" * 40
    later_sha = "b" * 40
    artifacts = {path: f"{index:040x}" for index, path in enumerate(closeout.TARGET_ARTIFACTS, start=1)}
    registry = {
        "revision": 7,
        "state_hash": "frozen-state",
        "active_thaws": [],
        "entries": {
            closeout.FREEZE_TOKEN: {
                "status": "FROZEN",
                "checkpoint_id": closeout.FREEZE_TOKEN,
                "source_main_sha": original_sha,
                "artifacts": dict(artifacts),
            }
        },
    }
    monkeypatch.setattr(closeout, "_read_registry", lambda token: (registry, "registry-content-sha"))
    monkeypatch.setattr(closeout, "_git_blob", lambda path: artifacts[path])

    result = closeout.freeze_and_read_back(token="read-only-token", merged_sha=later_sha)

    assert result["idempotent"] is True
    assert result["merged_sha"] == later_sha
    assert result["registry_source_main_sha"] == original_sha
    assert registry["entries"][closeout.FREEZE_TOKEN]["source_main_sha"] == original_sha


def test_existing_freeze_still_fails_closed_when_any_frozen_blob_changes(monkeypatch):
    closeout = _load_closeout()
    artifacts = {path: f"{index:040x}" for index, path in enumerate(closeout.TARGET_ARTIFACTS, start=1)}
    frozen = dict(artifacts)
    changed_path = closeout.TARGET_ARTIFACTS[0]
    frozen[changed_path] = "f" * 40
    registry = {
        "revision": 7,
        "state_hash": "frozen-state",
        "active_thaws": [],
        "entries": {
            closeout.FREEZE_TOKEN: {
                "status": "FROZEN",
                "checkpoint_id": closeout.FREEZE_TOKEN,
                "source_main_sha": "a" * 40,
                "artifacts": frozen,
            }
        },
    }
    monkeypatch.setattr(closeout, "_read_registry", lambda token: (registry, "registry-content-sha"))
    monkeypatch.setattr(closeout, "_git_blob", lambda path: artifacts[path])

    with pytest.raises(closeout.CloseoutFailure, match="frozen baseline conflict"):
        closeout.freeze_and_read_back(token="read-only-token", merged_sha="b" * 40)
