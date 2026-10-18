from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

import wnba_pra_api_market_bridge_v1 as bridge


NOW = datetime(2026, 10, 18, 18, 55, tzinfo=timezone.utc)
DAY = "2026-10-19"


def _schedule():
    return {
        "season": 2026,
        "games": [
            {
                "game_id": "401999001",
                "away": {"full_name": "Atlanta Dream", "team_tricode": "ATL"},
                "home": {"full_name": "Golden State Valkyries", "team_tricode": "GSV"},
            }
        ],
    }


def _offer(side="over", *, captured=None, book="FanDuel"):
    stamp = captured or (NOW - timedelta(minutes=2)).isoformat()
    return {
        "sportsbook": book,
        "player_name": "Allisha Gray",
        "stat": "pra",
        "side": side,
        "line": 31.5,
        "american_odds": -110,
        "market_captured_at_utc": stamp,
        "source_event_id": "fd-event-1",
        "source_market_id": "fd-market-1",
        "source_offer_id": f"fd-{side}-1",
        "away_team": "Atlanta Dream",
        "home_team": "Golden State Valkyries",
    }


def _snapshot(*, date=DAY, collected=None, offers=None, provider="fanduel"):
    return {
        "count": 1,
        "snapshots": [
            {
                "snapshot_id": "snap-current",
                "provider_id": provider,
                "feed_source": "FanDuel anonymous public WNBA sportsbook JSON",
                "date": date,
                "collected_at_utc": collected or (NOW - timedelta(minutes=2)).isoformat(),
                "normalized_input_feed": {"offers": offers or [_offer("over"), _offer("under")]},
            }
        ],
    }


def test_historical_snapshot_cannot_satisfy_current_active_slate():
    old = datetime(2026, 8, 27, 17, 6, tzinfo=timezone.utc)
    payload = _snapshot(date="2026-08-27", collected=old.isoformat())

    result = bridge._build_snapshot(DAY, _schedule(), payload, now=NOW)

    assert result["state"] == "STALE_STORED_MARKETS"
    assert isinstance(result["player_props"], pd.DataFrame) and result["player_props"].empty
    assert result["freshness_state"] == "STALE"
    assert result["snapshot_date"] == "2026-08-27"
    assert result["fanduel_offer_count"] == 0


def test_same_date_snapshot_over_maximum_age_is_stale():
    stale_at = NOW - timedelta(seconds=bridge.SNAPSHOT_MAX_AGE_SECONDS + 1)
    payload = _snapshot(collected=stale_at.isoformat())

    selected, offers = bridge._snapshot_offers(payload, DAY, now=NOW)
    result = bridge._build_snapshot(DAY, _schedule(), payload, now=NOW)

    assert selected is None and offers == []
    assert result["state"] == "STALE_STORED_MARKETS"
    assert result["snapshot_age_seconds"] > bridge.SNAPSHOT_MAX_AGE_SECONDS
    assert result["player_props"].empty


def test_current_same_date_fanduel_snapshot_is_accepted_with_metadata():
    payload = _snapshot()

    result = bridge._build_snapshot(DAY, _schedule(), payload, now=NOW)

    assert result["state"] == "CONNECTED"
    assert result["freshness_state"] == "CURRENT"
    assert result["snapshot_date"] == DAY
    assert result["provider_id"] == "fanduel"
    assert result["fanduel_offer_count"] == 2
    assert 0 <= result["snapshot_age_seconds"] <= bridge.SNAPSHOT_MAX_AGE_SECONDS
    assert set(result["player_props"]["book"]) == {"FanDuel"}
    assert set(result["player_props"]["updated_at"]) == {(NOW - timedelta(minutes=2)).isoformat()}
    assert result["api_owned"] is True
    assert result["direct_provider_called"] is False


def test_non_fanduel_current_snapshot_does_not_claim_fanduel_availability():
    payload = _snapshot(provider="kyre", offers=[_offer("over", book="DraftKings"), _offer("under", book="DraftKings")])

    result = bridge._build_snapshot(DAY, _schedule(), payload, now=NOW)

    assert result["state"] == "CONNECTED"
    assert result["fanduel_offer_count"] == 0
    assert result["freshness_state"] == "CURRENT"
