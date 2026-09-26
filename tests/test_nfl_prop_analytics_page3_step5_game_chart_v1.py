from pathlib import Path

import nfl_prop_analytics_page3_game_chart_v1 as chart

CHART_SRC = Path("nfl_prop_analytics_page3_game_chart_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_chart_spec_classifies_over_under_and_push():
    games = [
        {"official_event_id": "1", "opponent_abbr": "BUF", "date": "2026-09-20", "value": 301},
        {"official_event_id": "2", "opponent_abbr": "MIA", "date": "2026-09-13", "value": 249},
        {"official_event_id": "3", "opponent_abbr": "NE", "date": "2026-09-06", "value": 250.5},
    ]
    spec = chart.build_game_chart_spec(games, line=250.5)
    assert spec["ready"] is True
    assert spec["sample_size"] == 3
    assert spec["over_count"] == 1
    assert spec["under_count"] == 1
    assert spec["push_count"] == 1
    assert [row["outcome"] for row in spec["games"]] == ["over", "under", "push"]


def test_chart_uses_week_when_available_and_date_fallback_otherwise():
    games = [
        {"official_event_id": "10", "opponent_abbr": "KC", "week": 7, "date": "2026-10-18", "value": 88},
        {"official_event_id": "11", "opponent_abbr": "DEN", "date": "2026-10-11", "value": 55},
    ]
    spec = chart.build_game_chart_spec(games, line=60.5)
    assert spec["games"][0]["week_or_date"] == "WEEK 7"
    assert spec["games"][1]["week_or_date"] == "10/11"


def test_chart_fails_closed_without_step4_line():
    spec = chart.build_game_chart_spec(
        [{"official_event_id": "22", "opponent_abbr": "SEA", "value": 120}],
        line=None,
    )
    assert spec["ready"] is False
    assert spec["line"] is None


def test_step5_contract_is_descriptive_only():
    for token in (
        'PAGE3_CHART_STEP = 5',
        'PAGE3_CHART_VERSION = "v1"',
        'SPORTSBOOK_LINE_SOURCE = False',
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'WAGER_ACTIONS = False',
        'data-prop-page3-step5-chart="',
        'data-prop-page3-step5-selected-line="',
        'data-prop-page3-step5-outcome="',
        'data-prop-page3-step5-line-source="manual-step4"',
        'OPPONENT • WEEK/DATE',
    ):
        assert token in CHART_SRC, token


def test_prop_page_wires_chart_to_frozen_step4_line_and_step3_games():
    for token in (
        'from nfl_prop_analytics_page3_game_chart_v1 import (',
        'render_game_chart(',
        'games=history_payload.get("games") or []',
        'line=line_control.get("line")',
        '"game_chart": game_chart',
    ):
        assert token in PAGE_SRC, token
    assert PAGE_SRC.index("render_analysis_line_control(") < PAGE_SRC.index("render_game_chart(")
