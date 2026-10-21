from datetime import datetime, timezone
from pathlib import Path


def _sample_item():
    return {
        "key": "devinbooker",
        "player_name": "Devin Booker",
        "team": "PHX",
        "position": "G",
        "headshot": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626164.png",
        "stats_source": "NBA Stats",
        "availability": "AVAILABLE",
        "featured_quote": {
            "sportsbook": "FanDuel",
            "line": 38.5,
            "over_price": -110,
            "under_price": -110,
            "observed_at_utc": "2026-10-21T04:20:00Z",
        },
        "quotes": [
            {
                "sportsbook": "FanDuel",
                "line": 38.5,
                "over_price": -110,
                "under_price": -110,
                "observed_at_utc": "2026-10-21T04:20:00Z",
            },
            {
                "sportsbook": "DraftKings",
                "line": 39.5,
                "over_price": -105,
                "under_price": -115,
                "observed_at_utc": "2026-10-21T04:19:40Z",
            },
        ],
        "model": {
            "projection": 42.1,
            "current": {"l5": 42.3, "l10": 40.6, "minutes": 36.4},
        },
        "grade": {"edge": 3.6, "over_probability": 0.64, "lean": "OVER", "confidence": "HIGH"},
    }


def test_page1_hard_redesign_uses_compact_analytics_primitives():
    ui_source = Path("nba_pra_page1_ui_v2.py").read_text(encoding="utf-8")
    page_source = Path("nba_pra_page1_v2.py").read_text(encoding="utf-8")

    assert "def build_leaderboard_row_html" in ui_source
    assert "def build_market_row_html" in ui_source
    assert "def build_kpi_strip_html" in ui_source
    assert "np3-leader-row" in ui_source
    assert "np3-market-row" in ui_source
    assert "np3-kpi-strip" in ui_source
    assert "position:sticky" in ui_source

    assert "build_leaderboard_row_html" in page_source
    assert "build_market_row_html" in page_source
    assert "build_kpi_strip_html" in page_source
    assert "st.columns(len(featured))" not in page_source
    assert "build_player_card_html(item" not in page_source


def test_compact_rows_keep_identity_and_decision_metrics_visible():
    from nba_pra_page1_ui_v2 import build_leaderboard_row_html, build_market_row_html

    now = datetime(2026, 10, 21, 4, 20, 30, tzinfo=timezone.utc)
    leader = build_leaderboard_row_html(_sample_item(), rank=1, now_utc=now)
    market = build_market_row_html(_sample_item(), now_utc=now)

    for html in (leader, market):
        assert "Devin Booker" in html
        assert "1626164.png" in html
        assert "teamlogos/nba/500/phx.png" in html
        assert "38.5" in html
        assert "42.1" in html
        assert "+3.6" in html
        assert "64%" in html
        assert "FanDuel" in html

    assert "KYRE EDGE" in leader
    assert "L5" in leader and "42.3" in leader
    assert "DraftKings" in market and "39.5" in market
    assert "BUILDING" not in leader
    assert "BUILDING" not in market
