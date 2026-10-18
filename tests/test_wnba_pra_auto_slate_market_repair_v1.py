from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import wnba_pra_api_market_bridge_v1 as bridge

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-10-18"


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


def _fanduel_snapshot(*, collected_at: datetime | None = None):
    stamp = (collected_at or datetime.now(timezone.utc)).isoformat()
    return {
        "snapshots": [
            {
                "snapshot_id": "fresh-fanduel",
                "provider_id": "fanduel",
                "feed_source": "FanDuel anonymous public WNBA sportsbook JSON",
                "date": DAY,
                "collected_at_utc": stamp,
                "normalized_input_feed": {
                    "offers": [
                        {
                            "sportsbook": "FanDuel",
                            "player_name": "Allisha Gray",
                            "stat": "pra",
                            "side": "over",
                            "line": 20.5,
                            "american_odds": -130,
                            "market_captured_at_utc": stamp,
                            "source_event_id": "fd-event-1",
                            "source_market_id": "fd-market-1",
                            "source_offer_id": "fd-over-1",
                            "away_team": "Atlanta Dream",
                            "home_team": "Golden State Valkyries",
                        },
                        {
                            "sportsbook": "FanDuel",
                            "player_name": "Allisha Gray",
                            "stat": "pra",
                            "side": "under",
                            "line": 20.5,
                            "american_odds": -102,
                            "market_captured_at_utc": stamp,
                            "source_event_id": "fd-event-1",
                            "source_market_id": "fd-market-1",
                            "source_offer_id": "fd-under-1",
                            "away_team": "Atlanta Dream",
                            "home_team": "Golden State Valkyries",
                        },
                    ]
                },
            }
        ]
    }


class _FakeAPI:
    base_url = "https://kyre-sports-api.onrender.com"

    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.reads = 0

    def games_for_date(self, day, season):
        assert day == DAY
        assert season == 2026
        return _schedule()

    def get_json(self, path, *, params=None):
        assert path == bridge.SNAPSHOT_PATH
        self.reads += 1
        return self.snapshots[min(self.reads - 1, len(self.snapshots) - 1)]


def test_pra_hub_uses_automatic_verified_slate_without_manual_date_picker():
    source = (ROOT / "wnba_pra_hub_v3616.py").read_text(encoding="utf-8")
    assert 'st.date_input("WNBA slate date"' not in source
    assert "resolve_active_slate_date" in source
    assert 'ZoneInfo("America/New_York")' in source


def test_market_bridge_keeps_strict_ten_minute_freshness_gate():
    source = (ROOT / "wnba_pra_api_market_bridge_v1.py").read_text(encoding="utf-8")
    assert "SNAPSHOT_MAX_AGE_SECONDS = 600.0" in source
    assert "STALE_STORED_MARKETS" in source


def test_missing_snapshot_triggers_exactly_one_api_owned_fanduel_refresh_then_rereads():
    api = _FakeAPI([{"snapshots": []}, _fanduel_snapshot()])
    refresh_calls = []

    def refresher(client, day):
        assert client is api
        assert day == DAY
        refresh_calls.append(day)
        return {"attempted": True, "status_code": 200, "error": None}

    result = bridge._read_api_snapshot(DAY, api_client=api, refresher=refresher)

    assert refresh_calls == [DAY]
    assert api.reads == 2
    assert result["state"] == "CONNECTED"
    assert result["fanduel_offer_count"] == 2
    assert result["refresh_attempted"] is True
    assert result["refresh_status_code"] == 200


def test_fresh_current_fanduel_snapshot_does_not_trigger_refresh():
    api = _FakeAPI([_fanduel_snapshot()])
    refresh_calls = []

    result = bridge._read_api_snapshot(
        DAY,
        api_client=api,
        refresher=lambda client, day: refresh_calls.append(day),
    )

    assert refresh_calls == []
    assert api.reads == 1
    assert result["state"] == "CONNECTED"
    assert result["fanduel_offer_count"] == 2
    assert result["refresh_attempted"] is False


def test_stale_same_date_snapshot_is_not_accepted_when_refresh_fails():
    stale = datetime.now(timezone.utc) - timedelta(seconds=bridge.SNAPSHOT_MAX_AGE_SECONDS + 60)
    api = _FakeAPI([_fanduel_snapshot(collected_at=stale)])

    result = bridge._read_api_snapshot(
        DAY,
        api_client=api,
        refresher=lambda client, day: {"attempted": True, "status_code": 502, "error": "upstream"},
    )

    assert result["state"] == "STALE_STORED_MARKETS"
    assert result["fanduel_offer_count"] == 0
    assert result["refresh_attempted"] is True
    assert result["refresh_status_code"] == 502
