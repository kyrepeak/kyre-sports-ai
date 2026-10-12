from __future__ import annotations

import requests

import nba_spread_most_bet_v1 as step4


def _schedule():
    return [
        {
            "game_key": "BOS@NYK:2026-10-13",
            "away_tricode": "BOS",
            "home_tricode": "NYK",
            "away_name": "Boston Celtics",
            "home_name": "New York Knicks",
            "game_date_phoenix": "2026-10-13",
            "tip_phoenix": "4:30 PM MST",
            "status": "UPCOMING",
            "source_game_ids": {"NBA Official": "nba-bos-nyk", "ESPN NBA": "espn-bos-nyk"},
        },
        {
            "game_key": "LAL@PHX:2026-10-14",
            "away_tricode": "LAL",
            "home_tricode": "PHX",
            "away_name": "Los Angeles Lakers",
            "home_name": "Phoenix Suns",
            "game_date_phoenix": "2026-10-14",
            "tip_phoenix": "7:00 PM MST",
            "status": "UPCOMING",
            "source_game_ids": {"NBA Official": "nba-lal-phx", "ESPN NBA": "espn-lal-phx"},
        },
    ]


def _rows(high: int = 12500):
    return [
        {
            "away": "Boston Celtics",
            "home": "New York Knicks",
            "bet_count": 8200,
            "away_bet_pct": 44,
            "home_bet_pct": 56,
            "away_money_pct": 41,
            "home_money_pct": 59,
        },
        {
            "away": "Los Angeles Lakers",
            "home": "Phoenix Suns",
            "bet_count": high,
            "away_bet_pct": 67,
            "home_bet_pct": 33,
            "away_money_pct": 62,
            "home_money_pct": 38,
        },
    ]


def test_step4_declares_category_ownership_and_three_provider_chain():
    assert step4.PROVIDER_CHAIN == (
        "Action Network",
        "Covers Consensus",
        "VSiN Betting Splits",
    )
    ownership = step4.SOURCE_OWNERSHIP
    assert ownership["schedule_game_identity"]["owner"] == "Step-3 verified schedule"
    assert ownership["betting_activity"]["primary"] == "Action Network"
    assert ownership["betting_activity"]["secondary"] == "Covers Consensus"
    assert ownership["betting_activity"]["tertiary"] == "VSiN Betting Splits"
    assert ownership["display_timezone"] == "America/Phoenix"


def test_feature_emits_internal_kyre_ids_not_provider_ids_as_master_identity():
    feature = step4.select_most_bet_game(_rows(), _schedule())
    assert feature["verification"] == "VERIFIED"
    assert feature["kyre_game_id"] == "KYRE_NBA_GAME:LAL@PHX:2026-10-14"
    assert feature["kyre_away_team_id"] == "KYRE_NBA_TEAM:LAL"
    assert feature["kyre_home_team_id"] == "KYRE_NBA_TEAM:PHX"
    assert feature["provider_game_ids"] == {
        "NBA Official": "nba-lal-phx",
        "ESPN NBA": "espn-lal-phx",
    }


def test_primary_failure_uses_secondary_and_records_provider_health():
    calls: list[str] = []

    def action():
        calls.append("Action Network")
        raise requests.RequestException("primary unavailable")

    def covers():
        calls.append("Covers Consensus")
        return _rows(13000)

    def vsin():
        calls.append("VSiN Betting Splits")
        return _rows(14000)

    feature = step4.load_most_bet_feature(
        _schedule(),
        provider_fetchers={
            "Action Network": action,
            "Covers Consensus": covers,
            "VSiN Betting Splits": vsin,
        },
    )

    assert feature["verification"] == "VERIFIED"
    assert feature["source"] == "Covers Consensus"
    assert feature["consensus_status"] == "FALLBACK_VERIFIED"
    assert calls == ["Action Network", "Covers Consensus"]
    assert feature["provider_health"] == {
        "Action Network": "DEGRADED",
        "Covers Consensus": "HEALTHY",
        "VSiN Betting Splits": "NOT_NEEDED",
    }


def test_chain_exhaustion_fails_closed_without_manufacturing_data():
    def unavailable():
        return []

    feature = step4.load_most_bet_feature(
        _schedule(),
        provider_fetchers={name: unavailable for name in step4.PROVIDER_CHAIN},
    )

    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "FALLBACK_CHAIN_EXHAUSTED"
    assert feature["provider_health"] == {
        "Action Network": "DEGRADED",
        "Covers Consensus": "DEGRADED",
        "VSiN Betting Splits": "DEGRADED",
    }
    assert "bet_count" not in feature
