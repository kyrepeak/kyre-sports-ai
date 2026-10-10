from __future__ import annotations

from types import SimpleNamespace

from runless_proof_plane import cfb_game_total_backend_preservation_step2_closeout as closeout


def test_step2_closeout_exact_identity_is_locked():
    assert closeout.SOURCE_MAIN_SHA == "21b6d7a0dad7edd7f6768a3f98a121572fc859fa"
    assert closeout.SOURCE_CANDIDATE_SHA == "e44a0e3b15204033c2003302183da168f2e3d120"
    assert closeout.MAIN_SHA == "a3166e7d980d85b6adb6a064b8ac225befd9b9e3"
    assert closeout.PREMERGE_CHECK_ID == 114326836004
    assert closeout.PREMERGE_DIGEST == "0c1b15c6e54a486393a67c9690d96a02ad129a8d392c877754beec60f81dd53d"
    assert closeout.LEASE_ID == "SCOPE-LEASE-B9CFDFEE71EBED4086F4C3CB"
    assert closeout.FREEZE_TOKEN == "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP2_BACKEND_PRESERVATION_V1_FROZEN"


def test_execute_is_one_pass_and_never_reruns_static_proof(monkeypatch):
    calls = []

    class Client:
        def branch_sha(self, branch):
            return closeout.MAIN_SHA

    app = SimpleNamespace(state=SimpleNamespace(github_client=Client()))
    monkeypatch.setattr(closeout, "_verify_merge", lambda c: calls.append("merge") or {"x": "blob"})
    monkeypatch.setattr(closeout, "_load_premerge_receipt", lambda c: calls.append("receipt") or {"artifact_map": {}, "dependency_map": {}})
    monkeypatch.setattr(closeout, "_verify_premerge_gate", lambda c: calls.append("gate"))
    monkeypatch.setattr(closeout.GithubRegistryBackend, "read_registry", lambda self: calls.append("registry") or {"revision": 1, "state_hash": "h", "active_thaws": []})
    monkeypatch.setattr(closeout, "_ensure_merged_receipt_and_gate", lambda c, **k: calls.append("reuse") or {"receipt": {"digest": "merged"}, "reuse": {"decision": "REUSE_APPROVED"}})
    monkeypatch.setattr(closeout, "_advance_registry_and_freeze", lambda c, **k: calls.append("freeze") or {"already_frozen": False})
    monkeypatch.setattr(closeout, "_release_lease", lambda c: calls.append("lease") or {"released": True})

    result = closeout.execute(app)

    assert calls == ["merge", "receipt", "gate", "registry", "reuse", "freeze", "lease"]
    assert result["status"] == "GREEN"
    assert result["decision"] == "CFB_GAME_TOTAL_BACKEND_PRESERVATION_STEP2_GREEN_FROZEN"
    assert result["static_evidence_reexecuted"] is False
    assert result["github_actions_fallback"] == 0


def test_additive_closeout_has_no_fake_thaw_contract():
    source = closeout.__file__
    assert source
    assert not hasattr(closeout, "THAW_ID")
    assert not hasattr(closeout, "ROUTER_PATH")
