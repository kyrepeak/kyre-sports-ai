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
