from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
KYRE_HOST = "https://kyre-sports-api.vercel.app"
RUNLESS_HOST = "https://kyre-runless-proof.vercel.app"
CLIENTS = (
    "nba_pra_market_api_v1.py",
    "nba_pra_schedule_api_v1.py",
    "nba_pra_player_context_api_v1.py",
    "nba_pra_injury_api_v1.py",
    "nba_pra_page2_matchup_api_v1.py",
)
PRODUCT_NBA_ROUTE_FILES = (
    "sports_api/api/nba_pra_market_v1.py",
    "sports_api/api/nba_pra_schedule_v1.py",
    "sports_api/api/nba_pra_player_context_v1.py",
    "sports_api/api/nba_pra_injury_v1.py",
    "sports_api/api/nba_pra_matchup_v1.py",
)


def _source(relative: str) -> str:
    path = ROOT / relative
    assert path.exists(), f"required NBA gateway file is not implemented yet: {relative}"
    return path.read_text()


def _market_module():
    path = ROOT / "sports_api/api/nba_pra_market_v1.py"
    assert path.exists(), "NBA PRA market router has not been migrated to Kyre Sports API yet"
    return importlib.import_module("sports_api.api.nba_pra_market_v1")


def test_all_nba_application_clients_default_to_kyre_sports_api_not_runless():
    for relative in CLIENTS:
        source = _source(relative)
        assert f'DEFAULT_API_BASE_URL = "{KYRE_HOST}"' in source, relative
        assert RUNLESS_HOST not in source, relative
        assert "KYRE_NBA_API_BASE_URL" in source, relative


def test_kyre_sports_api_entrypoint_registers_universal_nba_domain_and_current_routes():
    entrypoint = importlib.import_module("kyre_sports_api_vercel_v1")
    paths = set(entrypoint.app.openapi()["paths"])
    expected = {
        "/api/v1/nba/status",
        "/api/v1/nba/pra/market",
        "/api/v1/nba/pra/market/status",
        "/api/v1/nba/pra/schedule",
        "/api/v1/nba/pra/player-context",
        "/api/v1/nba/pra/injuries",
        "/api/v1/nba/pra/matchup",
    }
    assert expected.issubset(paths)


def test_nba_domain_status_declares_kyre_only_future_ready_contract():
    entrypoint = importlib.import_module("kyre_sports_api_vercel_v1")
    with TestClient(entrypoint.app) as client:
        response = client.get("/api/v1/nba/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Kyre Sports API"
    assert payload["sport"] == "nba"
    assert payload["application_gateway"] == "KYRE_SPORTS_API"
    assert payload["runless_product_transport"] is False
    assert payload["provider_direct_frontend"] is False
    assert payload["fabrication"] is False
    assert set(payload["live_capabilities"]) >= {
        "pra.market",
        "pra.schedule",
        "pra.player-context",
        "pra.injuries",
        "pra.matchup",
    }
    assert set(payload["future_market_router_contract"]) >= {
        "points",
        "rebounds",
        "assists",
        "threes",
        "moneyline",
        "spread",
        "totals",
        "player-combos",
    }
    assert payload["prohibited_sources"] == ["SGO", "ESPN", "ESPN BET"]


def _fanduel_document(market_name: str, *, market_type: str = "PLAYER_COMBO"):
    return {
        "attachments": {
            "events": {
                "evt-1": {
                    "eventId": "evt-1",
                    "name": "Los Angeles Lakers @ Phoenix Suns",
                }
            },
            "markets": {
                "market-1": {
                    "marketId": "market-1",
                    "marketName": market_name,
                    "marketType": market_type,
                    "marketStatus": "OPEN",
                    "eventId": "evt-1",
                    "inPlay": False,
                    "runners": [
                        {
                            "runnerStatus": "ACTIVE",
                            "result": {"type": "Over"},
                            "handicap": 35.5,
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOddsInt": -110}
                            },
                        },
                        {
                            "runnerStatus": "ACTIVE",
                            "result": {"type": "Under"},
                            "handicap": 35.5,
                            "winRunnerOdds": {
                                "americanDisplayOdds": {"americanOddsInt": -110}
                            },
                        },
                    ],
                }
            },
        }
    }


def test_fanduel_pra_parser_normalizes_singular_plural_and_full_market_names():
    market = _market_module()
    variants = (
        "LeBron James - Pts + Reb + Ast",
        "LeBron James - Pts + Rebs + Asts",
        "LeBron James - Points + Rebounds + Assists",
    )
    for name in variants:
        rows = market._parse_fanduel_pra_page(
            _fanduel_document(name),
            captured_at_utc="2026-10-24T02:30:00Z",
        )
        assert len(rows) == 2, name
        assert {row["side"] for row in rows} == {"over", "under"}
        assert {row["line"] for row in rows} == {35.5}
        assert {row["player_name"] for row in rows} == {"LeBron James"}


def test_fanduel_pra_parser_keeps_alternative_lines_out_of_standard_market():
    market = _market_module()
    rows = market._parse_fanduel_pra_page(
        _fanduel_document(
            "LeBron James - Points + Rebounds + Assists",
            market_type="ALT_PLAYER_COMBO",
        ),
        captured_at_utc="2026-10-24T02:30:00Z",
    )
    assert rows == []


def test_active_kyre_nba_product_routes_do_not_embed_banned_provider_dependencies_or_runless_transport():
    banned = ("SportsGameOdds", "sportsgameodds", "ESPN BET", "ESPN.com", "espn.com")
    for relative in PRODUCT_NBA_ROUTE_FILES:
        source = _source(relative)
        assert "runless_v2" not in source, relative
        for token in banned:
            assert token not in source, f"{token!r} leaked into {relative}"


def test_nba_gateway_manifest_is_policy_only_and_has_no_runless_transport_import():
    source = _source("sports_api/api/nba_gateway_v1.py")
    assert "runless_v2" not in source
    assert "httpx" not in source
    assert "requests" not in source


def test_existing_non_nba_gateway_routes_remain_registered():
    entrypoint = importlib.import_module("kyre_sports_api_vercel_v1")
    paths = set(entrypoint.app.openapi()["paths"])
    assert "/api/v1/nfl/rushing-yards/slate" in paths
    assert any(path.startswith("/api/v1/nfl/passing") for path in paths)
    assert any(path.startswith("/api/v1/cfb/") for path in paths)
