from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import nba_pra_page1_api_only_provider_independence_v1 as data


LIVE_PAGE1_CLOSURE = (
    "nba_pra_runtime_v2.py",
    "nba_pra_page1_provider_independence_v1.py",
    "nba_pra_page1_api_only_provider_independence_v1.py",
    "nba_pra_page1_api_only_v1.py",
    "nba_pra_market_api_v1.py",
    "nba_pra_schedule_api_v1.py",
    "nba_pra_player_context_api_v1.py",
    "nba_pra_injury_api_v1.py",
)


def test_active_page1_runtime_closure_is_kyre_api_only_and_has_no_prohibited_provider_path():
    banned = re.compile(r"sportsgameodds|espn bet|\bespn\b|\bsgo\b", re.IGNORECASE)
    for filename in LIVE_PAGE1_CLOSURE:
        source = Path(filename).read_text()
        assert banned.search(source) is None, filename

    assert "from nba_pra_page1_provider_independence_v1 import render_nba_pra_page1_v2" in Path("nba_pra_runtime_v2.py").read_text()
    assert "from nba_pra_page1_api_only_provider_independence_v1 import load_page1_snapshot_v2" in Path("nba_pra_page1_provider_independence_v1.py").read_text()
    assert "import nba_pra_page1_api_only_v1 as prior" in Path("nba_pra_page1_api_only_provider_independence_v1.py").read_text()

    for filename in ("nba_pra_market_api_v1.py", "nba_pra_schedule_api_v1.py", "nba_pra_player_context_api_v1.py", "nba_pra_injury_api_v1.py"):
        source = Path(filename).read_text()
        urls = re.findall(r'https?://[^"\']+', source)
        assert urls == ["https://kyre-sports-api.vercel.app"], (filename, urls)


def test_verified_book_specific_pra_pair_survives_into_page1_market_without_direct_provider_fallback():
    now = datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)
    calls: list[str] = []
    schedule = {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "games": [{
            "gameStatus": 1,
            "status": "UPCOMING",
            "game_date_phoenix": "2026-10-24",
            "tip_utc": "2026-10-25T02:00:00Z",
            "away_tricode": "GSW",
            "away_name": "Golden State Warriors",
            "home_tricode": "PHX",
            "home_name": "Phoenix Suns",
        }],
        "fabrication": False,
    }
    market = {
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "global_market_state_reason": "MARKET_AVAILABLE",
        "observations": [
            {"provider":"FanDuel","player_name":"Khaman Maluach","sportsbook":"FanDuel","side":"over","line":19.5,"price":-125,"observed_at_utc":"2026-10-24T05:25:53Z","away_team":"Golden State Warriors","home_team":"Phoenix Suns"},
            {"provider":"FanDuel","player_name":"Khaman Maluach","sportsbook":"FanDuel","side":"under","line":19.5,"price":-106,"observed_at_utc":"2026-10-24T05:25:53Z","away_team":"Golden State Warriors","home_team":"Phoenix Suns"},
        ],
        "fabrication": False,
        "sportsbook_projection_influence": 0.0,
    }
    context = {
        "source": "Kyre Sports API — Vercel",
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "profiles": {
            "khamanmaluach": {
                "player_name": "Khaman Maluach",
                "team": "PHX",
                "position": "C",
                "current_games": [],
                "prior_games": [],
                "season_baseline": {"pra": 20.0},
            }
        },
        "fabrication": False,
    }

    snapshot = data.load_page1_snapshot_v2(
        now=now,
        schedule_loader=lambda **_: calls.append("kyre_schedule") or schedule,
        api_loader=lambda _day: calls.append("kyre_market") or market,
        player_context_loader=lambda _day, names: calls.append("kyre_context") or context,
        injury_loader=lambda *_args, **_kwargs: calls.append("kyre_injuries") or {"verification":"VERIFIED","players":{},"fabrication":False},
    )

    assert calls == ["kyre_schedule", "kyre_market", "kyre_context", "kyre_injuries"]
    assert snapshot["sportsbook_projection_influence"] == 0.0
    assert snapshot["sources"]["kyre_sports_api"]["diagnostic_state"] == "OK"
    quote = snapshot["market"]["khamanmaluach"]["featured_quote"]
    assert quote == {
        "sportsbook": "FanDuel",
        "line": 19.5,
        "over_price": -125,
        "under_price": -106,
        "provider": "FanDuel",
        "observed_at_utc": "2026-10-24T05:25:53Z",
    }
