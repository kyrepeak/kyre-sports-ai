from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import wnba_pra_api_market_bridge_v1 as bridge


ROOT = Path(__file__).resolve().parents[1]


def _schedule():
    return {
        "season": 2026,
        "games": [
            {
                "game_id": "401620001",
                "away": {"full_name": "Las Vegas Aces", "team_tricode": "LVA"},
                "home": {"full_name": "Phoenix Mercury", "team_tricode": "PHX"},
            }
        ],
    }


def _snapshots():
    return {
        "count": 1,
        "snapshots": [
            {
                "snapshot_id": "snap-api-step1",
                "provider_id": "primary-market-provider",
                "feed_source": "Kyre Sports API persisted market feed",
                "date": "2026-09-28",
                "normalized_input_feed": {
                    "offers": [
                        {
                            "sportsbook": "DraftKings",
                            "player_name": "A'ja Wilson",
                            "stat": "pra",
                            "side": "over",
                            "line": 39.5,
                            "american_odds": -110,
                            "market_captured_at_utc": "2026-09-28T23:59:00Z",
                            "source_event_id": "provider-event-1",
                            "away_team": "Las Vegas Aces",
                            "home_team": "Phoenix Mercury",
                        },
                        {
                            "sportsbook": "DraftKings",
                            "player_name": "A'ja Wilson",
                            "stat": "pra",
                            "side": "under",
                            "line": 39.5,
                            "american_odds": -110,
                            "market_captured_at_utc": "2026-09-28T23:59:00Z",
                            "source_event_id": "provider-event-1",
                            "away_team": "Las Vegas Aces",
                            "home_team": "Phoenix Mercury",
                        },
                    ]
                },
            }
        ],
    }


def test_step1_api_snapshot_maps_provider_offer_to_verified_game_identity():
    result = bridge._build_snapshot(
        "2026-09-28",
        _schedule(),
        _snapshots(),
        now=datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc),
    )
    assert result["state"] == "CONNECTED"
    assert result["provider"] == "Kyre Sports API"
    assert result["api_owned"] is True
    assert result["direct_provider_called"] is False
    assert result["matched_games"] == 1
    assert result["schedule_games"] == 1
    assert result["snapshot_id"] == "snap-api-step1"

    props = result["player_props"]
    assert isinstance(props, pd.DataFrame)
    assert len(props) == 2
    assert set(props["game_id"]) == {"401620001"}
    assert set(props["market"]) == {"PRA"}
    assert set(props["side"]) == {"over", "under"}
    assert set(props["book"]) == {"DraftKings"}
    assert set(props["line"]) == {39.5}
    assert set(props["age_seconds"]) == {60.0}


def test_step1_api_snapshot_fails_closed_when_market_identity_cannot_match():
    payload = _snapshots()
    for offer in payload["snapshots"][0]["normalized_input_feed"]["offers"]:
        offer["away_team"] = "Unknown Away"
        offer["home_team"] = "Unknown Home"
    result = bridge._build_snapshot("2026-09-28", _schedule(), payload)
    assert result["state"] == "MATCH_FAILURE"
    assert result["player_props"].empty
    assert result["unmatched_games"] == ["Unknown Away @ Unknown Home"]


def test_step1_api_snapshot_handles_verified_off_day_without_fabricating_markets():
    result = bridge._build_snapshot(
        "2026-09-28",
        {"season": 2026, "games": []},
        _snapshots(),
    )
    assert result["state"] == "NO_WNBA_GAMES"
    assert result["player_props"].empty
    assert result["direct_provider_called"] is False


def test_step1_active_pra_owner_installs_api_market_bridge_before_frozen_render():
    source = (ROOT / "wnba_pra_hub_v3613.py").read_text(encoding="utf-8")
    assert "import wnba_pra_api_market_bridge_v1 as api_market" in source
    assert "api_market.install()" in source
    assert source.index("api_market.install()") < source.index(
        "return frozen.base.render_wnba_pra_hub"
    )


def test_step1_streamlit_market_owner_has_no_direct_sportsbook_secret_dependency():
    bridge_source = (ROOT / "wnba_pra_api_market_bridge_v1.py").read_text(encoding="utf-8")
    active_source = (ROOT / "wnba_pra_hub_v3613.py").read_text(encoding="utf-8")
    assert "SPORTSGAMEODDS_API_KEY" not in bridge_source
    assert "SPORTSGAMEODDS_API_KEY" not in active_source
    assert "requests.get(" not in bridge_source
    assert 'SNAPSHOT_PATH = "/api/v1/wnba/markets/player-props/collection-store/snapshots"' in bridge_source
