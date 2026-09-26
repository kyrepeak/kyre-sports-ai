from pathlib import Path

import nfl_prop_analytics_history_stats_v1 as hist
import nfl_prop_analytics_prop_page_v1 as page3

HIST_SRC = Path("nfl_prop_analytics_history_stats_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_passing_parser_extracts_qb_markets():
    row = (
        ["C/ATT", "YDS", "AVG", "TD", "INT", "SACKS", "QBR", "RTG"],
        ["24/35", "287", "8.2", "3", "1", "2-11", "71.2", "108.6"],
    )
    out = hist._passing_stats(row)
    assert out["completions"] == 24
    assert out["attempts"] == 35
    assert out["passing_yards"] == 287
    assert out["passing_touchdowns"] == 3
    assert out["interceptions"] == 1


def test_rushing_and_receiving_parser_extracts_markets():
    rushing = hist._rushing_stats((
        ["CAR", "YDS", "AVG", "TD", "LONG"],
        ["17", "92", "5.4", "1", "24"],
    ))
    receiving = hist._receiving_stats((
        ["REC", "YDS", "AVG", "TD", "LONG", "TGTS"],
        ["7", "104", "14.9", "1", "41T", "10"],
    ))
    assert rushing["carries"] == 17
    assert rushing["rushing_yards"] == 92
    assert receiving["receptions"] == 7
    assert receiving["receiving_yards"] == 104
    assert receiving["longest_reception"] == 41


def test_history_window_selection_is_exact():
    rows = [
        {
            "event_id": str(i),
            "date": f"2026-09-{20-i:02d}T17:00Z",
            "season": 2026 if i < 6 else 2025,
            "team_ids": ("1", "2" if i % 3 == 0 else "3"),
        }
        for i in range(10)
    ]
    assert len(hist._select_events(rows, "L5", "2")) == 5
    assert len(hist._select_events(rows, "L10", "2")) == 10
    assert all("2" in set(row["team_ids"]) for row in hist._select_events(rows, "H2H", "2"))
    assert all(row["season"] == 2025 for row in hist._select_events(rows, "2025", "2"))


def test_hit_rate_engine_waits_for_real_line_then_calculates():
    games = [{"value": value} for value in (310, 280, 249, 221, 275)]
    no_line = hist.summarize_history(games)
    assert no_line["ready"] is True
    assert no_line["sample_size"] == 5
    assert no_line["average"] == 267
    assert no_line["median"] == 275
    assert no_line["hit_rate_state"] == "awaiting-line"
    assert no_line["hit_rate_pct"] is None

    with_line = hist.summarize_history(games, line=250.5)
    assert with_line["hit_rate_state"] == "ready"
    assert with_line["hit_count"] == 3
    assert with_line["hit_rate_pct"] == 60.0
    assert with_line["line"] == 250.5


def test_step3_page_contract_is_historical_only_and_fail_closed():
    for token in (
        'PAGE3_STATS_STEP = 3',
        'PAGE3_STATS_VERSION = "v1"',
        'data-prop-page3-step3-stats="',
        'data-prop-page3-step3-hit-rate-state="',
        'LINE REQUIRED • STEP 4',
        'HISTORICAL ONLY',
        'load_player_history(',
        'summarize_history(',
    ):
        assert token in PAGE_SRC, token

    for token in (
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'PROJECTION_ENABLED = False',
        'MARKET_ENABLED = False',
        'WAGER_ACTIONS = False',
    ):
        assert token in HIST_SRC, token

    for token in (
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'MAY_MODIFY_PASSING_YARDS = False',
        'data-prop-step8-sportsbook-lines="0"',
        'data-prop-step8-odds="0"',
        'data-prop-step8-projections="0"',
        'data-prop-step8-recommendations="0"',
    ):
        assert token in PAGE_SRC, token


def test_step1_and_step2_contracts_remain_present():
    for token in (
        'PAGE3_POLISH_STEP = 1',
        'PAGE3_HERO_VERSION = "v1"',
        'data-prop-page3-step1-hero="',
        'PAGE3_NAV_STEP = 2',
        'PAGE3_NAV_VERSION = "v1"',
        'data-prop-page3-step2-navigation="',
        'HISTORY_QUERY_KEY = "ks_pa_history"',
    ):
        assert token in PAGE_SRC, token


def test_anchor_season_uses_verified_matchup_date_first():
    assert page3._anchor_season({"target_date": "2026-09-27", "source_records": []}) == 2026
    assert page3._anchor_season({
        "target_date": "",
        "source_records": [{"season": 2025}],
    }) == 2025
