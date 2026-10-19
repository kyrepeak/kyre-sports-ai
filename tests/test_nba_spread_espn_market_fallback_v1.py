from __future__ import annotations

from datetime import datetime, timezone


def _schedule():
    return [
        {
            "game_key": "BOS@DET:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": "BOS",
            "home_tricode": "DET",
            "away_name": "Boston Celtics",
            "home_name": "Detroit Pistons",
            "status": "UPCOMING",
        }
    ]


def _espn_payload():
    return {
        "events": [
            {
                "id": "401909088",
                "date": "2026-10-20T23:30:00Z",
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {"displayName": "Boston Celtics", "abbreviation": "BOS"},
                            },
                            {
                                "homeAway": "home",
                                "team": {"displayName": "Detroit Pistons", "abbreviation": "DET"},
                            },
                        ],
                        "odds": [
                            {
                                "provider": {"name": "DraftKings"},
                                "details": "BOS -1.5",
                                "spread": 1.5,
                                "pointSpread": {
                                    "away": {
                                        "close": {"line": "-1.5", "odds": "-105"},
                                        "open": {"line": "+2.5", "odds": "-115"},
                                    },
                                    "home": {
                                        "close": {"line": "+1.5", "odds": "-115"},
                                        "open": {"line": "-2.5", "odds": "-105"},
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }


def test_normalizer_binds_exact_game_and_preserves_current_open_prices():
    import nba_spread_espn_market_fallback_v1 as market

    rows = market.normalize_espn_spread_observations_v1(
        [_espn_payload()],
        _schedule(),
        retrieved_at_utc="2026-10-19T22:50:00Z",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["game_key"] == "BOS@DET:2026-10-20"
    assert row["away_tricode"] == "BOS"
    assert row["home_tricode"] == "DET"
    assert row["sportsbook"] == "DraftKings"
    assert row["away_spread"] == -1.5
    assert row["home_spread"] == 1.5
    assert row["away_price"] == -105
    assert row["home_price"] == -115
    assert row["open_away_spread"] == 2.5
    assert row["open_home_spread"] == -2.5
    assert row["source_transport"] == "ESPN Public Scoreboard"
    assert row["sportsbook_projection_influence"] == 0.0


def test_normalizer_rejects_nonmatching_schedule_identity():
    import nba_spread_espn_market_fallback_v1 as market

    schedule = _schedule()
    schedule[0] = {**schedule[0], "home_name": "Chicago Bulls", "home_tricode": "CHI"}
    rows = market.normalize_espn_spread_observations_v1(
        [_espn_payload()],
        schedule,
        retrieved_at_utc="2026-10-19T22:50:00Z",
    )
    assert rows == []


def test_loader_fetches_each_unique_slate_date_once_and_returns_verified_rows():
    import nba_spread_espn_market_fallback_v1 as market

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _espn_payload()

    def request_get(url, *, params, headers, timeout):
        calls.append((url, dict(params), dict(headers), timeout))
        return Response()

    payload = market.load_verified_espn_spread_observations_v1(
        _schedule(),
        request_get=request_get,
        now_utc=datetime(2026, 10, 19, 22, 50, tzinfo=timezone.utc),
    )
    assert payload["verification"] == "VERIFIED"
    assert payload["diagnostic_state"] == "ESPN_DRAFTKINGS_FALLBACK_OK"
    assert payload["source"] == "ESPN Public Scoreboard"
    assert payload["sportsbook_projection_influence"] == 0.0
    assert len(payload["observations"]) == 1
    assert len(calls) == 1
    assert calls[0][1]["dates"] == "20261020"


def test_live_bridge_uses_espn_when_sgo_credential_is_missing():
    import nba_spread_live_data_repair_v2 as bridge

    expected = {
        "verification": "VERIFIED",
        "diagnostic_state": "ESPN_DRAFTKINGS_FALLBACK_OK",
        "source": "ESPN Public Scoreboard",
        "observations": [{"game_key": "BOS@DET:2026-10-20"}],
        "sportsbook_projection_influence": 0.0,
    }
    result = bridge.load_market_payload_v2(
        _schedule(),
        credential_resolver=lambda: None,
        espn_loader=lambda games: expected,
    )
    assert result["verification"] == "VERIFIED"
    assert result["source"] == "ESPN Public Scoreboard"
    assert result["primary_source_state"] == "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"
    assert result["source_chain"] == ["SportsGameOdds", "ESPN Public Scoreboard"]


def test_live_bridge_keeps_verified_sgo_primary_and_skips_espn():
    import nba_spread_live_data_repair_v2 as bridge

    calls = {"espn": 0}

    def espn_loader(games):
        calls["espn"] += 1
        raise AssertionError("fallback should not run")

    def sgo_loader(games, *, secret_getter):
        assert secret_getter("SPORTSGAMEODDS_API_KEY") == "present"
        return {
            "verification": "VERIFIED",
            "diagnostic_state": "OK",
            "source": "SportsGameOdds",
            "observations": [{"game_key": "BOS@DET:2026-10-20"}],
            "sportsbook_projection_influence": 0.0,
        }

    result = bridge.load_market_payload_v2(
        _schedule(),
        credential_resolver=lambda: "present",
        sgo_loader=sgo_loader,
        espn_loader=espn_loader,
    )
    assert result["verification"] == "VERIFIED"
    assert result["source"] == "SportsGameOdds"
    assert result["source_chain"] == ["SportsGameOdds"]
    assert calls["espn"] == 0
