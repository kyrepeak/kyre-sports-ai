from pathlib import Path

import nfl_prop_analytics_page3_line_control_v1 as line

LINE_SRC = Path("nfl_prop_analytics_page3_line_control_v1.py").read_text()
PAGE_SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_line_spec_uses_half_point_default_from_verified_sample():
    games = [{"value": value} for value in (310, 280, 249, 221, 275)]
    spec = line.build_analysis_line_spec(games, "passing_yards")
    assert spec["ready"] is True
    assert spec["increment"] == 0.5
    assert spec["default"] == 275.5
    assert spec["minimum"] < spec["default"] < spec["maximum"]
    assert spec["movable"] is True


def test_anytime_touchdown_uses_fixed_half_point_threshold():
    games = [{"value": value} for value in (0, 1, 0, 2, 1)]
    spec = line.build_analysis_line_spec(games, "anytime_touchdown")
    assert spec["ready"] is True
    assert spec["minimum"] == 0.5
    assert spec["maximum"] == 0.5
    assert spec["default"] == 0.5
    assert spec["movable"] is False


def test_empty_sample_fails_closed():
    spec = line.build_analysis_line_spec([], "receiving_yards")
    assert spec["ready"] is False
    assert spec["values"] == []


def test_step4_is_manual_threshold_only_and_no_sportsbook_logic():
    for token in (
        'PAGE3_LINE_STEP = 4',
        'PAGE3_LINE_VERSION = "v1"',
        'LINE_INCREMENT = 0.5',
        'SPORTSBOOK_LINE_SOURCE = False',
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'WAGER_ACTIONS = False',
        'data-prop-page3-step4-line-control="',
        'data-prop-page3-step4-sportsbook-line="0"',
        'MANUAL ANALYSIS LINE • NOT A SPORTSBOOK LINE',
        'Move analysis line',
        'summarize_history(list(games or []), line=line)',
    ):
        assert token in LINE_SRC, token


def test_prop_page_wires_step4_after_verified_step3_history():
    for token in (
        'from nfl_prop_analytics_page3_line_control_v1 import (',
        'render_analysis_line_control(',
        'games=history_payload.get("games") or []',
        '"line_control": line_control',
        'PAGE3_STEP3_PRE_LINE_SENTINEL = "LINE REQUIRED • STEP 4"',
    ):
        assert token in PAGE_SRC, token

    assert PAGE_SRC.index("history_ready = (") < PAGE_SRC.index("render_analysis_line_control(")
    assert PAGE_SRC.index("render_analysis_line_control(") < PAGE_SRC.index('class="ks-pa3-stats"')


def test_step4_recalculation_matches_step3_hit_rate_engine():
    games = [{"value": value} for value in (310, 280, 249, 221, 275)]
    summary = line.summarize_history(games, line=250.5)
    assert summary["ready"] is True
    assert summary["hit_rate_state"] == "ready"
    assert summary["hit_count"] == 3
    assert summary["hit_rate_pct"] == 60.0
    assert summary["line"] == 250.5
