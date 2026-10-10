from types import SimpleNamespace

from runless_proof_plane import cfb_game_total_native_routing_step1_closeout as closeout


def test_exact_closeout_identity_is_locked():
    assert closeout.SOURCE_MAIN_SHA == "11b1dc8fcf071be46afd099268849fa9be4770af"
    assert closeout.SOURCE_CANDIDATE_SHA == "3e28c55fa2dd55e0f9d0238a775c3e12edc1412c"
    assert closeout.MAIN_SHA == "21b6d7a0dad7edd7f6768a3f98a121572fc859fa"
    assert closeout.PREMERGE_PROOF_ID == "cfb-game-total-native-routing-step1-v1-3e28c55fa2dd55e0-0978694a39b7a4a3"
    assert closeout.PREMERGE_DIGEST == "9181f9f1b022b4fe747dbd3a5c600d38874e5526dede645ec485fc374802b392"
    assert closeout.PREMERGE_CHECK_ID == 114288746344
    assert closeout.LEASE_ID == "SCOPE-LEASE-CB8085920DC874CDD2A96A32"
    assert closeout.FREEZE_TOKEN == "CFB_GAME_TOTAL_NATIVE_WEBSITE_ROUTING_STEP1_V1_FROZEN"


def test_execute_is_one_pass_and_never_reexecutes_static_proof(monkeypatch):
    calls = []
    client = object()
    app = SimpleNamespace(state=SimpleNamespace(github_client=client))

    monkeypatch.setattr(closeout, "_verify_merge", lambda c: calls.append("merge") or {"x": "blob"})
    monkeypatch.setattr(closeout, "_load_premerge_receipt", lambda c: calls.append("receipt") or {"artifact_map": {}})
    monkeypatch.setattr(closeout.GithubRegistryBackend, "read_registry", lambda self: calls.append("registry") or {"revision": 1, "state_hash": "h", "active_thaws": []})
    monkeypatch.setattr(closeout, "_ensure_merged_receipt_and_gate", lambda c, **k: calls.append("reuse_gate") or {"receipt": {"digest": "merged"}, "reuse": {"static_evidence_reexecuted": False}, "gate_published": True})
    monkeypatch.setattr(closeout, "_atomic_forward_port_and_freeze", lambda c, **k: calls.append("freeze") or {"already_frozen": False})
    monkeypatch.setattr(closeout, "_release_lease", lambda c: calls.append("lease") or {"released": True})

    class Client:
        def branch_sha(self, branch):
            return closeout.MAIN_SHA

    app.state.github_client = Client()
    result = closeout.execute(app)

    assert calls == ["merge", "receipt", "registry", "reuse_gate", "freeze", "lease"]
    assert result["status"] == "GREEN"
    assert result["decision"] == "CFB_GAME_TOTAL_NATIVE_ROUTING_STEP1_GREEN_FROZEN"
    assert result["static_evidence_reexecuted"] is False
    assert result["github_actions_fallback"] == 0
