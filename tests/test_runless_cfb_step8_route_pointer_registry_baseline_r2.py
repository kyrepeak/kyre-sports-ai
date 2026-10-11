from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runless_proof_plane/cfb_step8_route_pointer_lock_premerge_registry_baseline_r2.py"


def test_cfb_step8_route_pointer_premerge_accepts_certified_parent_registry_only_with_exact_main_router_blob() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'REGISTRY_BASE_MAIN_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"' in source
    assert "registry_source not in {REGISTRY_BASE_MAIN_SHA, r1.MAIN_SHA}" in source
    assert "main_tree.get(r1.ROUTER_PATH) != r1.FROM_BLOB" in source
    assert 'raise r1.RoutePointerPremergeFailure("MAIN_ROUTER_BASELINE_DRIFT")' in source
    assert "r1._ensure_thaw = _ensure_thaw" in source
