from __future__ import annotations

from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nba_pra_page2_v1.py"


def _context() -> dict:
    return {
        "state": "ready",
        "line_moved": False,
        "player_name": "Andrew Nembhard",
        "team": "IND",
        "opponent": "NOP",
        "availability": "AVAILABLE",
        "team_logo": "https://cdn.nba.com/ind.svg",
        "opponent_logo": "https://cdn.nba.com/nop.svg",
        "player": {
            "player_name": "Andrew Nembhard",
            "team": "IND",
            "position": "PG",
            "headshot": "https://example.com/nembhard.png",
            "usage_pct": 24.8,
            "usage_rank": 2,
            "usage_team_size": 15,
            "usage_games": 68,
            "usage_period": "2025-26 REGULAR SEASON",
            "usage_source": "NBA Stats",
            "current_games": [
                {"game_date": "2026-03-29", "opponent": "NOP", "minutes": 36, "points": 15, "rebounds": 3, "assists": 10},
                {"game_date": "2026-03-27", "opponent": "BOS", "minutes": 32, "points": 13, "rebounds": 1, "assists": 10},
                {"game_date": "2026-03-25", "opponent": "MIA", "minutes": 34, "points": 14, "rebounds": 2, "assists": 19},
            ],
            "prior_games": [],
        },
        "game": {"game_id": "g1", "tip_utc": "2026-10-22T00:00:00Z"},
        "selected_quote": {
            "sportsbook": "FanDuel",
            "line": 23.5,
            "over_price": -106,
            "under_price": -125,
            "observed_at_utc": "2026-10-21T18:57:55Z",
        },
        "current_quote": {
            "sportsbook": "FanDuel",
            "line": 23.5,
            "over_price": -106,
            "under_price": -125,
            "observed_at_utc": "2026-10-21T18:57:55Z",
        },
        "quotes": [
            {
                "sportsbook": "FanDuel",
                "line": 23.5,
                "over_price": -106,
                "under_price": -125,
                "observed_at_utc": "2026-10-21T18:57:55Z",
            },
            {
                "sportsbook": "DraftKings",
                "line": 24.5,
                "over_price": -110,
                "under_price": -110,
                "observed_at_utc": "2026-10-21T18:56:00Z",
            },
        ],
    }


def _matchup() -> dict:
    return {
        "points": {"rank": 6, "value": 110.3, "grade": "TOUGH"},
        "rebounds": {"rank": 25, "value": 47.8, "grade": "FAVORABLE"},
        "assists": {"rank": 12, "value": 26.8, "grade": "MEDIUM"},
        "pra_rank": 14,
        "matchup_grade": "MEDIUM",
        "rank_semantics": "NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive",
        "evidence_period": "2026-27 PRESEASON BASELINE",
        "source": "Kyre Sports API",
    }


def test_page2_s_tier_html_has_command_center_usage_context_and_market_hierarchy() -> None:
    from nba_pra_page2_v1 import build_page2_html

    model = {
        "projection": 27.9,
        "sigma": 6.0,
        "current": {"sample": 3, "l5": 30.8, "l10": 26.5, "minutes": 31.3},
        "prior": {"sample": 0},
    }
    line_result = {
        "line": 26.0,
        "edge": 1.9,
        "over_probability": 0.59,
        "under_probability": 0.41,
        "lean": "OVER",
        "confidence": "LEAN",
        "score": 6.9,
        "tier": "LEAN",
    }
    html = build_page2_html(_context(), model, line_result, _matchup(), active_line=26.0)

    for text in (
        "PLAYER COMMAND CENTER",
        "KYRE AI VERDICT",
        "FAST LINE LAB",
        "SPORTSBOOK MARKET",
        "RECENT FORM",
        "OPPONENT ANALYTICS",
        "ANALYTICS CONTEXT",
        "ROLE & USAGE",
        "MODEL SNAPSHOT",
        "FULL GAME LOG",
    ):
        assert text in html
    assert "24.8%" in html
    assert "#2 ON IND" in html
    assert "2025-26 REGULAR SEASON" in html
    assert "FanDuel" in html and "DraftKings" in html
    assert "CURRENT BOOK LINE" in html and "SELECTED THRESHOLD" in html


def test_page2_game_log_has_visual_hit_miss_rows_and_sticky_header() -> None:
    from nba_pra_page2_v1 import build_page2_html

    model = {"projection": 27.9, "sigma": 6.0, "current": {"sample": 3, "l5": 30.8, "l10": 26.5, "minutes": 31.3}, "prior": {"sample": 0}}
    result = {"line": 26.0, "edge": 1.9, "over_probability": 0.59, "under_probability": 0.41, "lean": "OVER", "score": 6.9, "tier": "LEAN"}
    html = build_page2_html(_context(), model, result, _matchup(), active_line=26.0)
    source = PAGE.read_text(encoding="utf-8")

    assert 'class="p2-row-over"' in html
    assert 'class="p2-row-under"' in html
    assert "position:sticky" in source.replace(" ", "")


def test_page2_slider_reruns_only_a_streamlit_fragment_with_no_provider_fetches() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "@st.fragment" in source
    fragment = source.split("@st.fragment", 1)[1]
    assert "evaluate_line(" in fragment
    assert "load_page2_snapshot_v1(" not in fragment
    assert "load_kyre_sports_api_nba_pra_matchup(" not in fragment
    assert "0 external fetches per slider move" in source


def test_official_usage_loader_falls_back_to_prior_season_and_ranks_within_team() -> None:
    from runless_v2.nba_pra_usage_v1 import load_nba_usage_context

    calls: list[tuple[str, str, str]] = []

    class Response:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    def payload(rows: list[list[object]]) -> dict:
        return {
            "resultSets": [
                {
                    "name": "LeagueDashPlayerStats",
                    "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", "USG_PCT"],
                    "rowSet": rows,
                }
            ]
        }

    current = payload([[1, "Current Player", "IND", 1, 22.0, 0.18]])
    preseason = payload([])
    prior = payload(
        [
            [10, "Tyrese Haliburton", "IND", 70, 33.5, 0.271],
            [11, "Andrew Nembhard", "IND", 68, 31.3, 0.248],
            [12, "Pascal Siakam", "IND", 79, 34.0, 0.231],
            [13, "Other Team", "NOP", 80, 30.0, 0.400],
        ]
    )

    def fake_get(url: str, *, params: dict, headers: dict, timeout: float):
        calls.append((url, str(params.get("Season")), str(params.get("SeasonType"))))
        if params.get("Season") == "2026-27" and params.get("SeasonType") == "Regular Season":
            return Response(current)
        if params.get("Season") == "2026-27" and params.get("SeasonType") == "Pre Season":
            return Response(preseason)
        return Response(prior)

    out = load_nba_usage_context(
        date(2026, 10, 21),
        ["Andrew Nembhard"],
        request_get=fake_get,
    )
    row = out["profiles"]["andrewnembhard"]
    assert row["usage_pct"] == 24.8
    assert row["usage_rank"] == 2
    assert row["usage_team_size"] == 3
    assert row["usage_games"] == 68
    assert row["usage_period"] == "2025-26 REGULAR SEASON"
    assert row["usage_source"] == "NBA Stats"
    assert calls == [
        ("https://stats.nba.com/stats/leaguedashplayerstats", "2026-27", "Regular Season"),
        ("https://stats.nba.com/stats/leaguedashplayerstats", "2026-27", "Pre Season"),
        ("https://stats.nba.com/stats/leaguedashplayerstats", "2025-26", "Regular Season"),
    ]


def test_player_context_merges_verified_usage_without_changing_history_owner() -> None:
    from runless_v2.nba_pra_player_context_v1 import collect_nba_pra_player_context

    def official(_day: date, _names: list[str]) -> dict:
        return {
            "status": "HEALTHY",
            "profiles": {
                "andrewnembhard": {
                    "player_name": "Andrew Nembhard",
                    "team": "IND",
                    "position": "PG",
                    "current_games": [{"game_date": "2026-10-20", "minutes": 31, "points": 20, "rebounds": 3, "assists": 8}],
                    "prior_games": [],
                    "stats_source": "NBA Stats",
                }
            },
        }

    def usage(_day: date, _names: list[str]) -> dict:
        return {
            "status": "HEALTHY",
            "diagnostic_state": "OK",
            "profiles": {
                "andrewnembhard": {
                    "usage_pct": 24.8,
                    "usage_rank": 2,
                    "usage_team_size": 15,
                    "usage_games": 68,
                    "usage_period": "2025-26 REGULAR SEASON",
                    "usage_source": "NBA Stats",
                }
            },
        }

    out = collect_nba_pra_player_context(
        date(2026, 10, 21),
        ["Andrew Nembhard"],
        team_codes=["IND"],
        official_loader=official,
        usage_loader=usage,
    )
    profile = out["profiles"]["andrewnembhard"]
    assert profile["usage_pct"] == 24.8
    assert profile["usage_rank"] == 2
    assert profile["stats_source"] == "NBA Stats"
    assert out["provider_health"]["nba_usage"]["status"] == "HEALTHY"
