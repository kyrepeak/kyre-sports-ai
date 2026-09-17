from __future__ import annotations

import cfb_game_total_clean_page_v9 as page


def _team(name: str, rows: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "team": name,
        "record": "2-0",
        "ppg": 35.0,
        "allowed_pg": 17.0,
        "point_diff_pg": 18.0,
        "recent_form": "W2",
        "official_stats": rows,
    }


def test_official_rows_surface_verified_label_value_and_rank() -> None:
    team = _team(
        "Away",
        {
            "pace": {"label": "Plays per game", "value": "74.2", "rank": 18},
            "red_zone": {"label": "Red zone TD rate", "display_value": "71%", "rank": 12},
        },
    )

    rows = page._official_rows(team, "pace", "plays per game")

    assert rows == [("Plays per game", "74.2", "18")]


def test_step_evidence_cards_show_real_team_rows_not_presence_only() -> None:
    away = _team("Away", {"pace": {"label": "Plays per game", "value": "74.2", "rank": 18}})
    home = _team("Home", {"tempo": {"label": "Tempo", "value": "68.1", "rank": 61}})

    html = page._step_evidence_html(
        4,
        "Pace",
        "READY",
        "Verified pace/tempo rows present",
        {},
        away,
        home,
        {},
        {},
    )

    assert "Away" in html
    assert "Plays per game" in html
    assert "74.2" in html
    assert "Home" in html
    assert "Tempo" in html
    assert "68.1" in html
    assert "DATA LIMITED" not in html


def test_missing_turnover_rows_are_labeled_data_limited() -> None:
    html = page._step_evidence_html(
        8,
        "Turnovers",
        "CHECK",
        "No verified turnover row in current evidence",
        {},
        _team("Away", {}),
        _team("Home", {}),
        {},
        {},
    )

    assert "DATA LIMITED" in html
    assert "No verified turnover row" in html


def test_v158_presentation_contract_does_not_change_frozen_model_flags() -> None:
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v8"


def test_v159_dashboard_matches_compact_two_column_target_without_expanded_step_bodies() -> None:
    statuses = {number: "READY" for number in range(1, 11)}
    statuses[8] = "CHECK"
    details = {number: f"Verified step {number}" for number in range(1, 11)}
    details[8] = "No verified turnover row in current evidence"
    identity = {
        "away": {"team": "Syracuse", "conference": "ACC", "exact_identity": True},
        "home": {"team": "Pittsburgh", "conference": "ACC", "exact_identity": True},
        "venue": "Acrisure Stadium",
    }
    away = _team(
        "Syracuse",
        {
            "pace": {"label": "Plays per game", "value": "82.5"},
            "explosive": {"label": "Yards per play", "value": "5.8"},
            "red_zone": {"label": "Red Zone Attempts-Scores", "value": "11-14"},
            "third_down": {"label": "Third Down Conversions", "value": "0.51724"},
        },
    )
    home = _team(
        "Pittsburgh",
        {
            "pace": {"label": "Plays per game", "value": "73.5"},
            "explosive": {"label": "Yards per play", "value": "6.5"},
            "red_zone": {"label": "Red Zone Attempts-Scores", "value": "5-6"},
            "third_down": {"label": "Third Down Conversions", "value": "0.41379"},
        },
    )
    raw = {"ready": True, "projected_combined_total": 57.1, "reasons": ["Model + data quality"]}
    final = {
        "ready": True,
        "projected_combined_total": 57.1,
        "core_50_range": {"low": 48, "high": 67},
        "most_likely_band": {"label": "50–59"},
        "grade": "C",
        "forecast_strength": 0.748,
    }
    display_game = {
        "weather": "Partly cloudy",
        "temperature": "77°",
        "wind": "NW 6 mph",
        "history": "meetings: 82 • leader: Pittsburgh • record: 45-33-3",
    }

    html = page._combined_flow_html(
        statuses,
        details,
        raw,
        final,
        identity,
        away,
        home,
        display_game,
    )

    assert "V159" in page.MODEL_VERSION
    assert 'data-testid="gt159-dashboard"' in html
    assert 'class="gt159-stepgrid"' in html
    assert 'data-testid="gt159-step-4"' in html
    assert "Plays per game • 82.5 vs 73.5" in html
    assert "DATA LIMITED" in html
    assert "gt158-body" not in html
    assert "FINAL MODEL SUMMARY" in html
    assert "KEY SUPPORTS" in html
    assert "KEY CONCERNS" in html
    assert "TOP-5 SLATE SCANNER" in html


def test_v159_css_keeps_two_columns_until_phone_breakpoint() -> None:
    assert ".gt159-stepgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in page._V159_CSS
    assert "@media(max-width:700px)" in page._V159_CSS
    assert ".gt159-stepgrid{grid-template-columns:1fr}" in page._V159_CSS
