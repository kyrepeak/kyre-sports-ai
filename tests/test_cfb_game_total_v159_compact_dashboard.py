from __future__ import annotations

import cfb_game_total_clean_page_v9 as page


def _team(name: str) -> dict[str, object]:
    return {
        "team": name,
        "record": "2-0",
        "ppg": 35.5,
        "allowed_pg": 10.5,
        "point_diff_pg": 25.0,
        "recent_form": "WW",
        "official_stats": {
            "pace": {"label": "Plays per game", "value": "73.5", "rank": 22},
            "red_zone": {"label": "Red zone attempts-scores", "value": "5-6"},
        },
    }


def test_v159_is_presentation_only_and_keeps_frozen_contract() -> None:
    assert "V159" in page.MODEL_VERSION
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v8"


def test_game_total_hero_matches_compact_scoreboard_contract() -> None:
    html = page._game_total_hero_html(
        {"ready": True, "projected_combined_total": 57.1},
        {"ready": True, "projected_combined_total": 57.1, "grade": "C", "forecast_strength": 0.748},
        {"total": 56.5},
        {},
        11,
    )

    assert 'data-testid="gt159-game-total-hero"' in html
    assert "Projected Total" in html
    assert "57.1" in html
    assert "Market Total" in html
    assert "56.5" in html
    assert "Over +0.6" in html
    assert "74.8%" in html
    assert "Grade: C" in html
    assert "0.0% sportsbook projection influence" in html
    assert "1/12 Data Check" in html


def test_market_total_fails_closed_when_not_verified() -> None:
    html = page._game_total_hero_html(
        {"ready": True, "projected_combined_total": 57.1},
        {"ready": True, "projected_combined_total": 57.1, "grade": "B", "forecast_strength": 0.8},
        {},
        {},
        12,
    )

    assert "Market total unavailable" in html
    assert "Over +" not in html
    assert "Under -" not in html


def test_steps_render_as_compact_two_column_expandable_cards() -> None:
    away = _team("Syracuse")
    home = _team("Pittsburgh")
    statuses = {number: "READY" for number in range(1, 11)}
    statuses[8] = "CHECK"
    details = {number: f"Step {number} verified" for number in range(1, 11)}
    html = page._combined_flow_html(
        statuses,
        details,
        {"ready": True, "projected_combined_total": 57.1},
        {
            "ready": True,
            "projected_combined_total": 57.1,
            "core_50_range": {"low": 48, "high": 67},
            "most_likely_band": {"label": "50–59"},
            "grade": "C",
            "forecast_strength": 0.748,
        },
        {"away": {"team": "Syracuse", "conference": "ACC"}, "home": {"team": "Pittsburgh", "conference": "ACC"}},
        away,
        home,
        {"weather": "Partly Cloudy", "temperature": 77, "wind": "NW 6 mph", "history": "8-2"},
    )

    assert 'class="gt159-stepgrid"' in html
    assert html.count("<details class=\"gt159-step") == 12
    assert "DATA LIMITED" in html
    assert "FINAL MODEL SUMMARY" in html
    assert "KEY SUPPORTS" in html
    assert "KEY CONCERNS" in html
    assert "TOP-5 SLATE SCANNER" in html


def test_target_css_keeps_two_column_step_grid_on_phone() -> None:
    assert ".gt159-stepgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in page._V159_CSS
    assert "@media(max-width:420px)" in page._V159_CSS
