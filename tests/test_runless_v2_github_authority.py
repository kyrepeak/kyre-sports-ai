import copy
from datetime import datetime, timedelta, timezone

import pytest

from runless_v2.config import Settings
from runless_v2.github_authority import GithubAuthority, GithubAuthorityError
from runless_v2.models import ProofRequest
from runless_v2.receipt_contract import build_receipt, validate_receipt

SHA = "a" * 40
MAIN = "b" * 40
BLOB = "c" * 40


def settings(**overrides):
    values = dict(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="svc",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="key",
        proof_auth_token="proof",
    )
    values.update(overrides)
    return Settings(**values)


def request(**overrides):
    values = dict(
        task_id="task-3",
        workstream="ws-3",
        candidate_sha=SHA,
        lease_id="scope-1",
        authorization_id="auth-1",
        expected_main_sha=MAIN,
    )
    values.update(overrides)
    return ProofRequest(**values)


def plan():
    return {
        "workstream": "ws-3",
        "artifacts": ["artifact.py"],
        "dependencies": ["dependency.py"],
        "freeze_token": "FREEZE-TOKEN",
    }


def registry():
    return {
        "revision": 1,
        "state_hash": "registry-hash",
        "source_main_sha": MAIN,
        "entries": {"OLD": {"artifacts": {"frozen.py": BLOB}}},
        "active_thaws": [],
    }


def live_lease():
    return {
        "lease_id": "scope-1",
        "owner": "ws-3",
        "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }


def make_authority():
    authority = GithubAuthority(settings())
    authority.commit = lambda sha: {"sha": sha}
    authority.main_sha = lambda: MAIN
    authority.read_live_scope_lease = lambda lease_id: live_lease()
    authority.read_frozen_registry = lambda: registry()
    return authority


def test_wrong_github_app_id_fails_closed():
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_GITHUB_APP_ID_MISMATCH"):
        GithubAuthority(settings(github_app_id="999"))


def test_step2a_rejects_wrong_candidate_commit():
    authority = make_authority()
    authority.commit = lambda sha: {"sha": "d" * 40}
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_EXACT_HEAD_DRIFT"):
        authority.verify_step2a(request(), plan(), {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": BLOB}, {"frozen.py": BLOB})


def test_step2a_rejects_main_drift():
    authority = make_authority()
    authority.main_sha = lambda: "d" * 40
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_MAIN_IDENTITY_DRIFT"):
        authority.verify_step2a(request(), plan(), {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": BLOB}, {"frozen.py": BLOB})


def test_step2a_allows_registry_source_main_lag_when_frozen_blobs_match():
    authority = make_authority()
    stale_registry = registry()
    stale_registry["source_main_sha"] = "9" * 40
    authority.read_frozen_registry = lambda: stale_registry
    candidate_tree = {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": BLOB}
    main_tree = {"frozen.py": BLOB}

    result = authority.verify_step2a(request(), plan(), candidate_tree, main_tree)

    assert result["main_sha"] == MAIN
    assert result["registry"]["revision"] == 1


def test_step2a_allows_inherited_frozen_main_drift_when_candidate_does_not_touch_path():
    authority = make_authority()
    stale_registry = registry()
    stale_registry["source_main_sha"] = "9" * 40
    authority.read_frozen_registry = lambda: stale_registry
    inherited_blob = "8" * 40
    candidate_tree = {
        "artifact.py": BLOB,
        "dependency.py": BLOB,
        "frozen.py": inherited_blob,
    }
    main_tree = {"frozen.py": inherited_blob}

    result = authority.verify_step2a(request(), plan(), candidate_tree, main_tree)

    assert result["main_sha"] == MAIN
    assert result["registry"]["revision"] == 1


def test_step2a_stale_registry_identity_still_rejects_frozen_baseline_drift():
    authority = make_authority()
    stale_registry = registry()
    stale_registry["source_main_sha"] = "9" * 40
    authority.read_frozen_registry = lambda: stale_registry
    candidate_tree = {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": BLOB}
    main_tree = {"frozen.py": "8" * 40}

    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_FROZEN_BASELINE_DRIFT:frozen.py"):
        authority.verify_step2a(request(), plan(), candidate_tree, main_tree)


def test_dead_scope_lease_fails_closed():
    authority = make_authority()
    authority.read_live_scope_lease = lambda lease_id: (_ for _ in ()).throw(GithubAuthorityError("RUNLESS_V2_SCOPE_LEASE_NOT_LIVE"))
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_SCOPE_LEASE_NOT_LIVE"):
        authority.verify_step2a(request(), plan(), {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": BLOB}, {"frozen.py": BLOB})


def test_frozen_candidate_delta_requires_exact_thaw():
    authority = make_authority()
    candidate_tree = {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": "d" * 40}
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_FROZEN_DELTA_WITHOUT_THAW"):
        authority.verify_step2a(request(), plan(), candidate_tree, {"frozen.py": BLOB})


def test_frozen_candidate_delta_with_exact_thaw_is_allowed():
    authority = make_authority()
    thawed_registry = registry()
    thawed_registry["active_thaws"] = [
        {
            "thaw_id": "THAW-LOCAL",
            "target_head_sha": SHA,
            "files": {
                "frozen.py": {
                    "from_blob": BLOB,
                    "to_blob": "d" * 40,
                }
            },
        }
    ]
    authority.read_frozen_registry = lambda: thawed_registry
    candidate_tree = {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": "d" * 40}

    result = authority.verify_step2a(request(), plan(), candidate_tree, {"frozen.py": BLOB})

    assert result["main_sha"] == MAIN


def test_frozen_candidate_delta_with_ambiguous_thaw_fails_closed():
    authority = make_authority()
    thawed_registry = registry()
    pair = {"from_blob": BLOB, "to_blob": "d" * 40}
    thawed_registry["active_thaws"] = [
        {"thaw_id": "THAW-LOCAL-A", "target_head_sha": SHA, "files": {"frozen.py": pair}},
        {"thaw_id": "THAW-LOCAL-B", "target_head_sha": SHA, "files": {"frozen.py": pair}},
    ]
    authority.read_frozen_registry = lambda: thawed_registry
    candidate_tree = {"artifact.py": BLOB, "dependency.py": BLOB, "frozen.py": "d" * 40}

    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_FROZEN_DELTA_WITHOUT_THAW"):
        authority.verify_step2a(request(), plan(), candidate_tree, {"frozen.py": BLOB})


def test_step2a_returns_exact_artifact_and_dependency_maps():
    authority = make_authority()
    tree = {"artifact.py": "1" * 40, "dependency.py": "2" * 40, "frozen.py": BLOB}
    result = authority.verify_step2a(request(), plan(), tree, {"frozen.py": BLOB})
    assert result["artifact_map"] == {"artifact.py": "1" * 40}
    assert result["dependency_map"] == {"dependency.py": "2" * 40}
    assert result["scope_lease"]["lease_id"] == "scope-1"


def sample_receipt():
    return build_receipt(
        proof_id="proof-1",
        task_id="task-3",
        project="API2",
        workstream="ws-3",
        step="v2",
        candidate_sha=SHA,
        artifact_map={"artifact.py": "1" * 40},
        dependency_map={"dependency.py": "2" * 40},
        registry_before={"revision": 1},
        registry_after={"revision": 1},
        evidence_digests=["evidence"],
        failure_class="NONE",
    )


def test_receipt_digest_detects_tampering():
    receipt = sample_receipt()
    broken = copy.deepcopy(receipt)
    broken["task_id"] = "other"
    with pytest.raises(ValueError, match="RUNLESS_V2_RECEIPT_TAMPERED"):
        validate_receipt(broken)


def test_existing_receipt_identity_collision_fails_closed():
    authority = make_authority()
    receipt = sample_receipt()
    other = copy.deepcopy(receipt)
    other["candidate_sha"] = "d" * 40
    other = build_receipt(**{k: v for k, v in other.items() if k not in ("digest", "created_at")})
    authority._read_receipt = lambda proof_id: other
    with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_RECEIPT_IDENTITY_COLLISION"):
        authority.put_or_read_receipt(receipt)


def test_gate_readback_rejects_wrong_app_sha_or_digest():
    receipt = sample_receipt()
    for check in (
        {"id": 1, "name": "runless-final-gate", "conclusion": "success", "head_sha": SHA, "app": {"id": 999}, "output": {"summary": receipt["digest"]}},
        {"id": 1, "name": "runless-final-gate", "conclusion": "success", "head_sha": "d" * 40, "app": {"id": 5204253}, "output": {"summary": receipt["digest"]}},
        {"id": 1, "name": "runless-final-gate", "conclusion": "success", "head_sha": SHA, "app": {"id": 5204253}, "output": {"summary": "wrong"}},
    ):
        authority = make_authority()
        authority._publish_check = lambda candidate_sha, receipt: {"id": 1}
        authority._check_runs = lambda candidate_sha: [check]
        with pytest.raises(GithubAuthorityError, match="RUNLESS_V2_GATE_READBACK_FAILED"):
            authority.publish_gate_and_readback(SHA, receipt)


def test_gate_readback_accepts_exact_app_sha_and_receipt_digest():
    receipt = sample_receipt()
    check = {"id": 77, "name": "runless-final-gate", "conclusion": "success", "head_sha": SHA, "app": {"id": 5204253}, "output": {"summary": f"runless-v2 receipt={receipt['digest']} proof=proof-1"}}
    authority = make_authority()
    authority._publish_check = lambda candidate_sha, receipt: {"id": 77}
    authority._check_runs = lambda candidate_sha: [check]
    assert authority.publish_gate_and_readback(SHA, receipt)["id"] == 77
