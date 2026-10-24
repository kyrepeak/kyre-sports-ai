from datetime import date, datetime, timezone

from runless_v2 import nba_pra_market_v1 as api


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


def test_fanduel_no_pra_does_not_gate_global_pra_market(monkeypatch):
    monkeypatch.setattr(api, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(
        api,
        "_fetch_draftkings_pra_observations",
        lambda _day: (_dk_rows(), "DRAFTKINGS_OK"),
        raising=False,
    )

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


def test_global_unavailable_requires_all_approved_configured_routes_to_miss(monkeypatch):
    monkeypatch.setattr(api, "_fetch_fanduel_pra_observations", lambda _day: ([], "FANDUEL_NO_PRA"))
    monkeypatch.setattr(
        api,
        "_fetch_draftkings_pra_observations",
        lambda _day: ([], "DRAFTKINGS_NO_PRA"),
        raising=False,
    )

    payload = api.collect_nba_pra_market(date(2026, 10, 24))

    assert payload["verification"] == "UNAVAILABLE"
    assert payload["ready"] is False
    assert payload["diagnostic_state"] == "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA"
    health = {row["provider"]: row["state"] for row in payload["provider_health"]}
    assert health == {"FanDuel": "FANDUEL_NO_PRA", "DraftKings": "DRAFTKINGS_NO_PRA"}


def test_player_context_accepts_team_only_request_and_returns_recent_participant_pool(monkeypatch):
    from runless_v2 import nba_pra_player_context_v1 as context

    pool = {
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
    monkeypatch.setattr(
        context,
        "_reference_team_player_pool",
        lambda _day, codes: {
            "status": "HEALTHY",
            "diagnostic_state": "RECENT_PARTICIPANTS_1",
            "profiles": pool if "MIA" in codes else {},
        },
        raising=False,
    )

    payload = context.collect_nba_pra_player_context(date(2026, 10, 24), [], team_codes=["MIA", "CHA"])

    assert payload["verification"] in {"VERIFIED", "PARTIAL"}
    assert payload["requested_players"] == 0
    assert payload["identified_players"] == 1
    assert payload["profiles"]["bamadebayo"]["season_baseline"]["pra"] == 26.0
    assert payload["provider_health"]["basketball_reference_team_pool"]["status"] == "HEALTHY"


def test_zero_market_does_not_zero_player_model_layer():
    from nba_pra_page1_api_only_v1 import load_page1_snapshot_v2
    from nba_pra_page1_v2 import build_items

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
        "fabrication": False,
    }

    def player_context(_day, names):
        assert names == []
        return {
            "source": "Kyre Sports API — Vercel",
            "verification": "PARTIAL",
            "diagnostic_state": "RECENT_PARTICIPANT_POOL",
            "profiles": {
                "bamadebayo": {
                    "player_name": "Bam Adebayo",
                    "team": "MIA",
                    "position": "C",
                    "headshot": "",
                    "current_games": [],
                    "prior_games": [],
                    "season_baseline": {"pra": 26.0},
                    "stats_source": "Basketball-Reference current-season per-game index",
                }
            },
            "provider_health": {},
            "requested_players": 0,
            "verified_players": 0,
            "identified_players": 1,
            "fabrication": False,
        }

    snapshot = load_page1_snapshot_v2(
        now=datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc),
        schedule_loader=lambda **_: schedule,
        api_loader=lambda _day: market,
        player_context_loader=player_context,
        injury_loader=lambda *_args, **_kwargs: {"players": {}, "fabrication": False},
    )
    items = build_items(snapshot)

    assert snapshot["market"] == {}
    assert "bamadebayo" in snapshot["profiles"]
    assert len(items) == 1
    assert items[0]["player_name"] == "Bam Adebayo"
    assert items[0]["market_state"] == "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA"
    assert items[0]["featured_quote"]["line"] is None
    assert items[0]["model"]["projection"] == 26.0
    assert items[0]["grade"]["over_probability"] is None
    assert items[0]["grade"]["under_probability"] is None
