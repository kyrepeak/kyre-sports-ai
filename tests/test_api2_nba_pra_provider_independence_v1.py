from datetime import date, datetime, timezone
from pathlib import Path

from sports_api.api import nba_pra_market_provider_independence_v1 as api


def _dk_rows():
    stamp = "2026-10-24T01:00:00Z"
    base = {
        "provider": "DraftKings",
        "provider_event_id": "evt-1",
        "provider_market_id": "mkt-1",
        "provider_player_id": "player-1",
        "player_name": "Test Player",
        "sportsbook": "DraftKings",
        "line": 34.5,
        "observed_at_utc": stamp,
        "away_team": "Miami Heat",
        "home_team": "Charlotte Hornets",
    }
    return [
        {**base, "side": "over", "price": -110},
        {**base, "side": "under", "price": -110},
    ]


def _participant_pool():
    return {
        "bamadebayo": {
            "player_name": "Bam Adebayo",
            "team": "MIA",
            "position": "C",
            "headshot": "",
            "provider_ids": {},
            "current_games": [],
            "prior_games": [],
            "season_baseline": {"games": 1, "points": 15.0, "rebounds": 7.0, "assists": 4.0, "pra": 26.0},
            "stats_source": "Basketball-Reference current-season per-game index",
        }
    }


def test_fanduel_no_pra_does_not_gate_global_pra_market(monkeypatch):
    monkeypatch.setattr(api.prior, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(api, "_fetch_draftkings_pra_observations", lambda _day: (_dk_rows(), "DRAFTKINGS_OK"))

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["verification"] == "VERIFIED"
    assert payload["ready"] is True
    assert payload["observation_count"] == 2
    assert payload["player_count"] == 1
    assert {row["sportsbook"] for row in payload["observations"]} == {"DraftKings"}
    assert payload["diagnostic_state"] == "OK"
    health = {row["provider"]: row["state"] for row in payload["provider_health"]}
    assert health["FanDuel"] == "FANDUEL_NO_PRA"
    assert health["DraftKings"] == "DRAFTKINGS_OK"


def test_global_unavailable_requires_all_currently_eligible_routes_to_miss(monkeypatch):
    monkeypatch.setattr(api.prior, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(api, "_fetch_draftkings_pra_observations", lambda _day: ([], "DRAFTKINGS_NO_PRA"))
    monkeypatch.setattr(api, "_reference_recent_participant_profiles", lambda _day: ({}, "NO_RECENT_PARTICIPANTS"))

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["verification"] == "UNAVAILABLE"
    assert payload["ready"] is False
    assert payload["diagnostic_state"] == "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA"
    assert payload["global_market_state_reason"] == "ALL_CURRENTLY_ELIGIBLE_APPROVED_ROUTES_EXHAUSTED"
    health = {row["provider"]: row["state"] for row in payload["provider_health"]}
    assert health == {"FanDuel": "FANDUEL_NO_PRA", "DraftKings": "DRAFTKINGS_NO_PRA"}
    audit = {row["provider"]: row["state"] for row in payload["provider_route_audit"]}
    assert audit["FanDuel"] == "ACTIVE_DIRECT_ROUTE"
    assert audit["DraftKings"] == "ACTIVE_DIRECT_FALLBACK"
    assert audit["OpticOdds"] == "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"
    assert audit["The Odds API"] == "NOT_CONFIGURED_IN_CURRENT_DEPLOYMENT"


def test_global_market_miss_keeps_recent_participant_pool(monkeypatch):
    monkeypatch.setattr(api.prior, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(api, "_fetch_draftkings_pra_observations", lambda _day: ([], "DRAFTKINGS_ACCESS_FAILURE"))
    monkeypatch.setattr(api, "_reference_recent_participant_profiles", lambda _day: (_participant_pool(), "RECENT_PARTICIPANTS_1"))

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["ready"] is False
    assert payload["recent_participant_state"] == "RECENT_PARTICIPANTS_1"
    assert payload["recent_participant_profiles"]["bamadebayo"]["season_baseline"]["pra"] == 26.0
    assert payload["observations"] == []


def test_streamlit_gateway_client_preserves_provider_and_participant_metadata():
    import nba_pra_market_api_v1 as client

    payload = {
        "projection_weight": 0.0,
        "consensus_averaging": False,
        "diagnostic_state": "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA",
        "global_market_state_reason": "ALL_CURRENTLY_ELIGIBLE_APPROVED_ROUTES_EXHAUSTED",
        "player_count": 0,
        "observations": [],
        "provider_health": [
            {"provider": "FanDuel", "state": "FANDUEL_NO_PRA"},
            {"provider": "DraftKings", "state": "DRAFTKINGS_ACCESS_FAILURE"},
        ],
        "provider_route_audit": [{"provider": "FanDuel", "state": "ACTIVE_DIRECT_ROUTE"}],
        "recent_participant_profiles": _participant_pool(),
        "recent_participant_state": "RECENT_PARTICIPANTS_1",
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    result = client.load_kyre_sports_api_pra_observations(
        date(2026, 10, 24),
        request_post=lambda *_args, **_kwargs: Response(),
    )

    assert result["verification"] == "UNAVAILABLE"
    assert len(result["provider_health"]) == 2
    assert result["recent_participant_state"] == "RECENT_PARTICIPANTS_1"
    assert result["recent_participant_profiles"]["bamadebayo"]["season_baseline"]["pra"] == 26.0


def test_zero_market_does_not_zero_player_model_layer():
    from nba_pra_page1_api_only_provider_independence_v1 import load_page1_snapshot_v2
    from nba_pra_page1_provider_independence_v1 import build_items
    from nba_pra_page1_ui_provider_independence_v1 import dashboard_kpis

    schedule = {
        "verification": "VERIFIED",
        "games": [
            {
                "gameStatus": 1,
                "status": "UPCOMING",
                "game_date": "2026-10-24",
                "tip_utc": "2026-10-24T22:00:00Z",
                "away_tricode": "MIA",
                "away_name": "Miami Heat",
                "home_tricode": "CHA",
                "home_name": "Charlotte Hornets",
            }
        ],
    }
    market = {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA",
        "observations": [],
        "provider_health": [
            {"provider": "FanDuel", "state": "FANDUEL_NO_PRA"},
            {"provider": "DraftKings", "state": "DRAFTKINGS_ACCESS_FAILURE"},
        ],
        "recent_participant_profiles": _participant_pool(),
        "recent_participant_state": "RECENT_PARTICIPANTS_1",
        "fabrication": False,
    }

    snapshot = load_page1_snapshot_v2(
        now=datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc),
        schedule_loader=lambda **_: schedule,
        api_loader=lambda _day: market,
        player_context_loader=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("market miss must not require market-name context")),
        injury_loader=lambda *_args, **_kwargs: {"players": {}, "fabrication": False},
    )
    items = build_items(snapshot)
    kpis = dashboard_kpis(items, now_utc=datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc))

    assert snapshot["market"] == {}
    assert "bamadebayo" in snapshot["profiles"]
    assert len(items) == 1
    assert items[0]["player_name"] == "Bam Adebayo"
    assert items[0]["market_state"] == "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA"
    assert items[0]["featured_quote"]["line"] is None
    assert items[0]["model"]["projection"] == 26.0
    assert items[0]["grade"]["edge"] is None
    assert items[0]["grade"]["over_probability"] is None
    assert items[0]["grade"]["lean"] == "PASS"
    assert items[0]["grade"]["confidence"] == "UNAVAILABLE"
    assert kpis["players_tracked"] == 1
    assert kpis["markets_verified"] == 0


def test_kyre_entrypoint_activates_provider_independence_market_router():
    source = Path("kyre_sports_api_vercel_v1.py").read_text()
    assert "nba_pra_market_provider_independence_v1" in source
    assert "nba_pra_market_module.router" in source
