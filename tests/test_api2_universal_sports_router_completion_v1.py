from __future__ import annotations

from fastapi.testclient import TestClient

from universal_sports_nav_registry_v1 import SPORTS


REQUIRED = {
    "nfl": {
        "slate", "moneyline", "spread", "game-total", "passing-yards",
        "rushing-yards", "receiving-yards", "receptions", "passing-tds",
        "anytime-td", "daily-picks",
    },
    "cfb": {"moneyline", "spread", "over-under", "game-total", "top-picks", "player-props"},
    "nba": {
        "moneyline", "spread", "totals", "pra", "points", "rebounds",
        "assists", "threes", "player-combos", "history",
    },
    "wnba": {
        "points", "rebounds", "assists", "rebounds-assists", "pra", "spread",
        "moneyline", "game-total", "daily-picks", "history",
    },
}


def test_completion_registry_covers_every_required_api2_sports_page() -> None:
    from sports_api.api import universal_sports_router_completion_v1 as completion

    coverage = completion.coverage_manifest()
    for sport, markets in REQUIRED.items():
        assert markets.issubset(set(coverage[sport]))
        for market in markets:
            owner = coverage[sport][market]
            assert owner["application_gateway"] == "KYRE_SPORTS_API"
            assert owner["mounted"] is True
            assert owner["provider_direct_frontend"] is False
            assert owner["canonical_path"].startswith("/api/v1/")
            assert owner["semantic_empty_states"] is True
            assert owner["field_first_routing"] is True
            assert owner["sportsbook_projection_influence"] == 0.0
    assert completion.validate_router_coverage() == ()


def test_all_live_universal_nav_pages_have_a_router_owner() -> None:
    from sports_api.api import universal_sports_router_completion_v1 as completion

    coverage = completion.coverage_manifest()
    for sport in SPORTS:
        if sport.id not in {"nfl", "cfb", "nba", "wnba"}:
            continue
        for market in sport.markets:
            if market.live:
                assert market.id in coverage[sport.id], f"orphan route: {sport.id}/{market.id}"


def test_field_router_contract_is_zero_blank_and_anti_bypass() -> None:
    from sports_api.api import universal_sports_router_completion_v1 as completion

    contract = completion.resolve_field_route("nfl", "anytime-td", "odds")
    assert contract["application_gateway"] == "KYRE_SPORTS_API"
    assert contract["field"] == "odds"
    assert contract["zero_blank_rule"] is True
    assert contract["fallback_only_when_needed"] is True
    assert contract["provider_direct_frontend"] is False
    assert contract["semantic_empty_states"] is True
    assert contract["prohibited_sources"] == ["SGO", "ESPN", "ESPN BET"]


def test_vercel_entrypoint_mounts_completion_router_and_existing_unmounted_market_routers() -> None:
    import kyre_sports_api_vercel_v1 as entrypoint

    paths = set(entrypoint.app.openapi()["paths"])
    assert "/api/v1/router/coverage" in paths
    assert "/api/v1/router/resolve/{sport}/{market}" in paths
    assert "/api/v1/router/field/{sport}/{market}/{field}" in paths

    # Previously implemented but missing from the Vercel mount table.
    assert any(path.startswith("/api/v1/nfl/moneyline/market") for path in paths)
    assert any(path.startswith("/api/v1/nfl/spread/market") for path in paths)
    assert any(path.startswith("/api/v1/nfl/receiving-yards") for path in paths)
    assert any(path.startswith("/api/v1/nfl/rushing-yards/market") for path in paths)
    assert any(path.startswith("/api/v1/cfb/markets") for path in paths)


def test_router_api_resolves_missing_page_without_404_or_blank_contract() -> None:
    import kyre_sports_api_vercel_v1 as entrypoint

    with TestClient(entrypoint.app) as client:
        response = client.get("/api/v1/router/resolve/nba/moneyline")
        field = client.get("/api/v1/router/field/wnba/points/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sport"] == "nba"
    assert payload["market"] == "moneyline"
    assert payload["mounted"] is True
    assert payload["canonical_path"]
    assert field.status_code == 200
    assert field.json()["semantic_empty_states"] is True


def test_completion_router_contains_no_prohibited_provider_dependency() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "sports_api/api/universal_sports_router_completion_v1.py").read_text()
    assert "sportsgameodds" not in source.lower()
    assert "espn.com" not in source.lower()
    assert "espnbet" not in source.lower()
    assert "runless_v2" not in source
