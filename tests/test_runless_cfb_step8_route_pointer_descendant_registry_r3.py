from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runless_proof_plane/cfb_step8_route_pointer_lock_premerge_descendant_r3.py"


def test_cfb_step8_premerge_binds_stale_registry_to_exact_descendant_thaw_authority() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "def _is_ancestor(" in source
    assert 'comparison.get("status") in {"ahead", "identical"}' in source
    assert "pair.get(\"from_blob\")" in source
    assert "pair.get(\"to_blob\")" in source
    assert "_is_ancestor(client, target, effective_main_sha)" in source
    assert "INHERITED_FROZEN_STATE_WITHOUT_EXACT_MERGED_THAW" in source
    assert "prove._verify_frozen_candidate = _verify_frozen_candidate_descendant" in source


def test_cfb_step8_premerge_releases_only_its_dead_owner_lease_on_terminal_error() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "def _release_owned_leases(" in source
    assert "holder.get(\"owner_id\") == r1.OWNER_ID" in source
    assert "r1._release(client, lease_id)" in source
    assert "except Exception:" in source
