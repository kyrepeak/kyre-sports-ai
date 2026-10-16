from __future__ import annotations

import inspect

import cfb_game_total_page2_step7_line_lab_best_bet_v1 as step7
import cfb_game_total_page2_step8_final_runtime_v1 as step8


def _scenarios():
    return [
        {"line": 55.5, "over_probability": "67.0%", "under_probability": "33.0%"},
        {"line": 58.5, "over_probability": "61.0%", "under_probability": "39.0%"},
        {"line": 61.5, "over_probability": "54.0%", "under_probability": "46.0%"},
    ]


def test_step5_line_lab_switches_precomputed_scenarios_without_script() -> None:
    html = step7.build_line_lab_best_bet_html(
        line_scenarios=_scenarios(),
        selected_line=58.5,
        recommendation={
            "side": "OVER",
            "line": 58.5,
            "probability": "61.0%",
            "expected_total": 62.0,
            "edge": 3.5,
            "confidence": "B+",
            "rationale": "Caller-owned recommendation",
        },
    )

    assert html.count('type="radio" name="gtp2s7-line-choice"') == 3
    for index, line in enumerate(("55.5", "58.5", "61.5")):
        assert f'id="gtp2s7-line-{index}"' in html
        assert f'for="gtp2s7-line-{index}"' in html
        assert f'class="gtp2s7-scenario gtp2s7-scenario-{index}"' in html
        assert f'data-scenario-line="{line}"' in html
        assert (
            f'#gtp2s7-line-{index}:checked~.gtp2s7-scenario-stage '
            f'.gtp2s7-scenario-{index}' + '{display:grid}'
        ) in html
    assert 'id="gtp2s7-line-1" type="radio" name="gtp2s7-line-choice" checked' in html
    assert "<script" not in html.lower()
    assert 'type="range"' not in html


def test_step5_fallback_builds_three_distribution_owned_lines() -> None:
    raw = {
        "distribution_ready": True,
        "distribution": [
            {"total": 54.0, "probability": 0.10},
            {"total": 56.0, "probability": 0.20},
            {"total": 58.0, "probability": 0.25},
            {"total": 60.0, "probability": 0.20},
            {"total": 62.0, "probability": 0.15},
            {"total": 64.0, "probability": 0.10},
        ],
    }
    rows = step8._line_scenarios(raw, {"market_total": 58.5})

    assert [row["line"] for row in rows] == [55.5, 58.5, 61.5]
    assert [(row["over_probability"], row["under_probability"]) for row in rows] == [
        ("90.0%", "10.0%"),
        ("45.0%", "55.0%"),
        ("25.0%", "75.0%"),
    ]


def test_step5_supplied_line_scenarios_remain_authoritative() -> None:
    supplied = _scenarios()
    raw = {
        "line_scenarios": supplied,
        "distribution_ready": True,
        "distribution": [{"total": 58.0, "probability": 1.0}],
    }
    assert step8._line_scenarios(raw, {"market_total": 58.5}) == supplied


def test_step5_remains_display_only_and_no_new_network_or_model_authority() -> None:
    assert step7.NETWORK_CALLS_ADDED == 0
    assert step7.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step7.MAY_MODIFY_MODEL is False
    assert step7.MAY_MODIFY_PROJECTION is False
    assert step7.MAY_MODIFY_PROBABILITY is False
    assert step7.RECOMMENDATION_LOGIC_ADDED is False
    assert step8.NETWORK_CALLS_ADDED == 0
    assert step8.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step8.MAY_MODIFY_MODEL is False
    assert step8.MAY_MODIFY_PROJECTION is False
    assert step8.MAY_MODIFY_PROBABILITY is False
    source = inspect.getsource(step8._line_scenarios)
    assert "requests." not in source
    assert "httpx." not in source
