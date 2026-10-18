from __future__ import annotations


def _obs(source, value, *, authoritative=False, freshness="CURRENT", priority=10, identity="g1"):
    from wnba_pra_source_fusion_v1 import SourceObservation
    return SourceObservation(source, "schedule", identity, value, "2026-10-18T00:00:00Z", freshness, priority, authoritative)


def test_two_agreeing_independent_sources_are_multi_source_verified():
    from wnba_pra_source_fusion_v1 import fuse_observations
    out = fuse_observations([_obs("WNBA", "ATL@GSV", authoritative=True, priority=0), _obs("ESPN", "ATL@GSV")])
    assert out.state == "VERIFIED_MULTI_SOURCE"
    assert out.value == "ATL@GSV"
    assert out.sources == ("WNBA", "ESPN")
    assert out.conflicts == ()


def test_single_authoritative_and_single_non_authoritative_states():
    from wnba_pra_source_fusion_v1 import fuse_observations
    assert fuse_observations([_obs("WNBA", "x", authoritative=True)]).state == "VERIFIED_PRIMARY"
    assert fuse_observations([_obs("ESPN", "x")]).state == "SINGLE_SOURCE"


def test_conflict_retains_authoritative_value_and_records_conflict():
    from wnba_pra_source_fusion_v1 import fuse_observations
    out = fuse_observations([_obs("WNBA", "ATL@GSV", authoritative=True, priority=0), _obs("ESPN", "NYL@MIN", priority=5)])
    assert out.state == "CONFLICT"
    assert out.value == "ATL@GSV"
    assert "ESPN" in out.conflicts


def test_all_stale_and_empty_inputs_fail_closed():
    from wnba_pra_source_fusion_v1 import fuse_observations
    stale = fuse_observations([_obs("WNBA", "x", authoritative=True, freshness="STALE")])
    assert stale.state == "STALE"
    assert stale.freshness == "STALE"
    empty = fuse_observations([])
    assert empty.state == "UNAVAILABLE"
    assert empty.value is None
