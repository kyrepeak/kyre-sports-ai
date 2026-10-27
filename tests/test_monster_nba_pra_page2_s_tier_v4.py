from __future__ import annotations

import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "nba_pra_page2_sync_v1.py"


def _context() -> dict:
    games = [
        {"game_date": f"2026-10-{24-i:02d}", "opponent": opp, "minutes": 30.0 + i, "points": pts, "rebounds": reb, "assists": ast}
        for i, (opp, pts, reb, ast) in enumerate(
            [
                ("HOU", 20, 4, 5), ("CHO", 18, 3, 4), ("ORL", 25, 4, 6), ("CLE", 17, 5, 4), ("NYK", 24, 3, 5),
                ("BRK", 22, 4, 7), ("BOS", 16, 4, 6), ("SAC", 27, 5, 4), ("MIA", 21, 3, 8), ("DET", 19, 6, 5),
            ]
        )
    ]
    return {
        "state": "ready",
        "player_name": "Nickeil Alexander-Walker",
        "team": "ATL",
        "opponent": "HOU",
        "availability": "NO OFFICIAL INJURY DESIGNATION",
        "availability_verification": "VERIFIED",
        "availability_source": "NBA Official Injury Report",
        "team_logo": "https://cdn.nba.com/atl.svg",
        "opponent_logo": "https://cdn.nba.com/hou.svg",
        "player": {
            "player_name": "Nickeil Alexander-Walker",
            "team": "ATL",
            "position": "PG",
            "headshot": "https://example.com/naw.png",
            "usage_pct": 18.7,
            "usage_rank": 4,
            "usage_period": "2026-27 REGULAR SEASON",
            "usage_source": "NBA Stats",
            "current_games": games[:3],
            "prior_games": games[3:],
        },
        "quotes": [
            {"sportsbook": "FanDuel", "line": 24.5, "over_price": -122, "under_price": -104, "observed_at_utc": "2026-10-27T00:02:07Z"},
            {"sportsbook": "DraftKings", "line": 25.5, "over_price": 100, "under_price": -120, "observed_at_utc": "2026-10-27T00:01:00Z"},
        ],
        "selected_quote": {"sportsbook": "FanDuel", "line": 24.5, "over_price": -122, "under_price": -104},
        "current_quote": {"sportsbook": "FanDuel", "line": 24.5, "over_price": -122, "under_price": -104},
        "teammate_injuries": [],
    }


def _model() -> dict:
    return {"projection": 29.6, "sigma": 6.9, "current": {"sample": 3, "l5": 29.0, "l10": 29.0, "minutes": 29.7}, "prior": {"sample": 7}}


def _result() -> dict:
    return {"line": 24.5, "edge": 5.1, "over_probability": 0.77, "under_probability": 0.23, "lean": "OVER", "score": 10.0, "tier": "ELITE"}


def _matchup() -> dict:
    return {
        "points": {"rank": 11, "grade": "MEDIUM"},
        "rebounds": {"rank": 2, "grade": "TOUGH"},
        "assists": {"rank": 11, "grade": "MEDIUM"},
        "pra_rank": 8,
        "matchup_grade": "TOUGH",
        "rank_semantics": "NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive",
        "evidence_period": "2026-27 REGULAR SEASON",
        "source": "Kyre Sports API",
    }


def test_v4_is_monster_only_presentation_successor_with_no_provider_io() -> None:
    import nba_pra_page2_command_center_v4 as v4

    source = inspect.getsource(v4)
    assert v4.VERSION == "MONSTER_NBA_PRA_PAGE2_S_TIER_V4"
    assert v4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert "requests" not in source
    assert "httpx" not in source
    assert "stats.nba.com" not in source
    assert "espn" not in source.lower()
    assert "sgo" not in source.lower()


def test_v4_command_center_and_decision_terminal_are_compact_and_decision_first() -> None:
    import nba_pra_page2_command_center_v4 as v4

    html = v4.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=24.5)
    for token in (
        "PLAYER COMMAND CENTER",
        "Nickeil Alexander-Walker",
        "ATL",
        "HOU",
        "ACTIVE",
        "VERIFIED",
        "OVER 24.5 PRA",
        "29.6",
        "77%",
        "+5.1",
        "10.0",
        "#8 PRA MATCHUP",
    ):
        assert token in html
    assert 'data-ks-section="decision-terminal"' in html
    assert "p2v4-evidence-meter" in html


def test_v4_has_l10_threshold_chart_and_projection_range_visual() -> None:
    import nba_pra_page2_command_center_v4 as v4

    html = v4.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=24.5)
    assert "L10 PRA TREND" in html
    assert "ACTIVE LINE 24.5" in html
    assert "p2v4-trend-svg" in html
    assert "projection-range" in html
    assert "22.7" in html and "29.6" in html and "36.5" in html


def test_v4_market_role_drivers_and_kyre_read_use_verified_data_only() -> None:
    import nba_pra_page2_command_center_v4 as v4

    html = v4.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=24.5)
    for token in (
        "MARKET INTELLIGENCE",
        "FanDuel",
        "DraftKings",
        "BEST OVER",
        "ROLE & AVAILABILITY",
        "18.7%",
        "MODEL DRIVERS",
        "RECENT FORM",
        "MINUTES",
        "MATCHUP",
        "ROLE / USAGE",
        "AVAILABILITY",
        "KYRE READ",
        "PRIMARY EDGE",
        "PRIMARY CAUTION",
    ):
        assert token in html
    assert "CONSENSUS" in html
    assert "SPORTSBOOK_PROJECTION_INFLUENCE" not in html


def test_v4_deep_evidence_is_collapsible_and_mobile_game_log_uses_cards() -> None:
    import nba_pra_page2_command_center_v4 as v4

    html = v4.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=24.5)
    css = v4._css()
    assert "DEEP VERIFIED EVIDENCE" in html
    assert "<details" in html and "<summary" in html
    assert "FULL GAME LOG" in html
    assert "p2v4-game-card" in html
    assert "@media(max-width:700px)" in css.replace(" ", "")
    assert "p2v4-game-table" in css


def test_v4_missing_usage_and_single_book_do_not_fabricate_consensus_or_active_status() -> None:
    import nba_pra_page2_command_center_v4 as v4

    context = _context()
    context["player"] = dict(context["player"])
    context["player"].pop("usage_pct")
    context["quotes"] = [context["quotes"][0]]
    context["availability"] = "UNVERIFIED"
    context["availability_verification"] = "UNVERIFIED"
    html = v4.build_page2_html(context, _model(), _result(), _matchup(), active_line=24.5)
    assert "USAGE NOT VERIFIED" in html
    assert "1 VERIFIED BOOK" in html
    assert "CONSENSUS" not in html
    assert ">ACTIVE<" not in html


def test_live_sync_activates_v4_and_preserves_zero_fetch_slider_fragment() -> None:
    source = SYNC.read_text(encoding="utf-8")
    assert "from nba_pra_page2_command_center_v4 import _css, build_page2_html" in source
    assert "@st.fragment" in source
    fragment = source.split("@st.fragment", 1)[1]
    assert "evaluate_line(" in fragment
    assert "load_page2_snapshot_v1(" not in fragment
    assert "load_kyre_sports_api_nba_pra_matchup(" not in fragment
    assert "0 external fetches per slider move" in fragment
