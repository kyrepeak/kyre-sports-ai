from __future__ import annotations

from datetime import datetime, timezone

from devsystem.verify_nba_spread_page1_opener_v1 import run_probe

TEST_NOW = datetime(2026, 10, 19, 22, 25, 30, tzinfo=timezone.utc)


def _games():
    rows = []
    for away, home in (("BOS", "DET"), ("PHI", "NYK"), ("OKC", "SAS")):
        rows.append({
            "game_key": f"{away}@{home}:2026-10-20",
            "game_date_phoenix": "2026-10-20",
            "away_tricode": away,
            "home_tricode": home,
            "away_name": away,
            "home_name": home,
            "status": "UPCOMING",
            "step9_fair_spread": {
                "verification": "VERIFIED",
                "pregame_model": {
                    "verification": "VERIFIED",
                    "fair_away_spread": -2.0,
                    "fair_home_spread": 2.0,
                    "cover_verification": "VERIFIED",
                    "away_cover_probability": 0.55,
                    "home_cover_probability": 0.45,
                },
            },
            "step10_decision": {"verification": "VERIFIED", "decision_state": "NO_PLAY"},
        })
    return rows


def _verified_market(selected, *, book="DraftKings"):
    observations = []
    for game in selected:
        observations.append({
            "game_key": game["game_key"],
            "game_date_phoenix": "2026-10-20",
            "away_tricode": game["away_tricode"],
            "home_tricode": game["home_tricode"],
            "sportsbook": book,
            "away_spread": -1.5,
            "home_spread": 1.5,
            "retrieved_at_utc": "2026-10-19T22:25:00+00:00",
        })
    return {"verification": "VERIFIED", "diagnostic_state": "OK", "observations": observations}


def test_probe_calls_each_page_level_provider_at_most_once_and_reuses_payloads():
    calls = {"market": 0, "injury": 0, "public": 0}
    games = _games()

    def market_loader(selected):
        calls["market"] += 1
        return _verified_market(selected, book="FanDuel")

    def injury_loader(selected):
        calls["injury"] += 1
        return {"verification": "VERIFIED", "features": []}

    def public_loader(selected):
        calls["public"] += 1
        return {"verification": "UNAVAILABLE", "observations": []}

    result = run_probe(
        schedule_loader=lambda: {"verification": "VERIFIED", "games": games},
        market_loader=market_loader,
        injury_loader=injury_loader,
        public_loader=public_loader,
        credential_resolver=lambda: "present-but-never-returned",
        now_utc=TEST_NOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["credential_resolved"] is True
    assert result["provider_calls"]["market"] == 1
    assert result["provider_calls"]["injury"] == 1
    assert result["provider_calls"]["public"] == 1
    assert result["zero_provider_calls_per_card"] is True
    assert result["all_opener_markets_verified"] is True
    assert calls == {"market": 1, "injury": 1, "public": 1}
    assert len(result["games"]) == 3
    assert result["sportsbook_projection_influence"] == 0.0


def test_probe_allows_verified_fallback_without_sgo_credential():
    called = {"market": 0}

    def market_loader(selected):
        called["market"] += 1
        return _verified_market(selected)

    result = run_probe(
        schedule_loader=lambda: {"verification": "VERIFIED", "games": _games()},
        market_loader=market_loader,
        injury_loader=lambda games: {"verification": "UNAVAILABLE", "features": []},
        public_loader=lambda games: {"verification": "UNAVAILABLE", "observations": []},
        credential_resolver=lambda: None,
        now_utc=TEST_NOW,
    )
    assert result["verification"] == "VERIFIED"
    assert result["credential_resolved"] is False
    assert result["all_opener_markets_verified"] is True
    assert called["market"] == 1


def test_probe_blocks_when_any_opener_market_is_unverified():
    def market_loader(selected):
        payload = _verified_market(selected[:-1])
        return payload

    result = run_probe(
        schedule_loader=lambda: {"verification": "VERIFIED", "games": _games()},
        market_loader=market_loader,
        injury_loader=lambda games: {"verification": "UNAVAILABLE", "features": []},
        public_loader=lambda games: {"verification": "UNAVAILABLE", "observations": []},
        credential_resolver=lambda: None,
        now_utc=TEST_NOW,
    )
    assert result["verification"] == "BLOCKED"
    assert result["blocker"] == "OPENER_MARKET_UNVERIFIED"
    assert result["all_opener_markets_verified"] is False


def test_probe_fails_closed_on_missing_exact_opener_identity():
    games = _games()[:-1]
    result = run_probe(
        schedule_loader=lambda: {"verification": "VERIFIED", "games": games},
        market_loader=lambda games: {},
        injury_loader=lambda games: {},
        public_loader=lambda games: {},
        credential_resolver=lambda: "present",
        now_utc=TEST_NOW,
    )
    assert result["verification"] == "BLOCKED"
    assert result["blocker"] == "OPENER_GAME_IDENTITY_MISSING"
    assert result["missing_matchups"] == ["OKC@SAS"]
