from __future__ import annotations

import sports_api.api.nfl_rushing_yards_detail_v4 as v4


def test_public_v2_router_builder_is_bound_to_v4_successor() -> None:
    assert v4.base.build_detail_bundle is v4.build_detail_bundle
    assert v4.base.base.build_detail_bundle is v4.build_detail_bundle


def test_v4_health_contract_uses_live_acceptance_version() -> None:
    assert v4.VERSION == "NFL_RUSHING_YARDS_DETAIL_V4_LIVE_ACCEPTANCE"
