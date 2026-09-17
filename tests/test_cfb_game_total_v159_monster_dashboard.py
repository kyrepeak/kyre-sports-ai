from __future__ import annotations

import cfb_game_total_clean_page_v10 as page


def _team(name: str, ppg: float, allowed: float) -> dict[str, object]:
    return {
        "team": name,
        "record": "2-0",
        "ppg": ppg,
        "allowed_pg": allowed,
        "point_diff_pg": ppg - allowed,
        "recent_form": "W2",
        "official_stats": {},
    }


def _final() -> dict[str, object]:
    return {
        "projected_combined_total": 55.5,
        "core_50_range": {"low": 51, "high": 60},
        "most_likely_band": {"label": "52–59"},
        "grade": "A",
        "forecast_strength": 0.81,
        "qualified": True,
    }


def test_v159_keeps_frozen_model_boundaries() -> None:
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.FROZEN_PRESENTATION == "cfb_game_total_clean_page_v8"


def test_monster_dashboard_surfaces_matchup_projection_and_evidence_at_a_glance() -> None:
    html = page._monster_dashboard_html(
        identity={
            "away": {"team": "Away", "rank": "#12", "conference": "SEC", "exact_identity": True},
            "home": {"team": "Home", "rank": "#8", "conference": "Big Ten", "exact_identity": True},
            "venue": "Monster Stadium",
        },
        away=_team("Away", 35.0, 17.0),
        home=_team("Home", 31.0, 20.0),
        display_game={"kickoff": "7:30 PM", "weather": "Clear", "wind_mph": 6},
        statuses={number: "READY" for number in range(1, 11)},
        details={number: "Verified" for number in range(1, 11)},
        raw={"projected_combined_total": 55.5},
        final=_final(),
    )

    assert 'data-testid="gt159-monster-dashboard"' in html
    assert 'data-testid="gt159-matchup-hero"' in html
    assert 'data-testid="gt159-projection-hero"' in html
    assert 'data-testid="gt159-team-comparison"' in html
    assert 'data-testid="gt159-evidence-grid"' in html
    assert 'data-testid="gt159-final-synthesis"' in html
    assert "Away" in html and "Home" in html
    assert "55.5" in html
    assert "51–60" in html
    assert "81.0%" in html
    assert "0.0% sportsbook projection influence" in html


def test_monster_dashboard_compacts_steps_without_removing_any_step() -> None:
    html = page._monster_dashboard_html(
        identity={},
        away=_team("Away", 35.0, 17.0),
        home=_team("Home", 31.0, 20.0),
        display_game={},
        statuses={number: "READY" for number in range(1, 11)},
        details={number: "Verified" for number in range(1, 11)},
        raw={"projected_combined_total": 55.5},
        final=_final(),
    )

    for number in range(1, 13):
        assert f'data-testid="gt159-step-{number}"' in html

    assert "DEEP EVIDENCE STAYS BELOW" in html


def test_v159_css_has_desktop_and_mobile_dashboard_layouts() -> None:
    css = page._V159_CSS
    assert ".gt159-hero" in css
    assert ".gt159-evidence-grid" in css
    assert "@media(max-width:760px)" in css
    assert "grid-template-columns:1fr" in css
