from __future__ import annotations

import cfb_game_total_step2_profile_v1 as step2


def _identity():
    return {
        "away": {"team": "Coastal Carolina"},
        "home": {"team": "Delaware"},
    }


def _away():
    return {
        "team": "Coastal Carolina",
        "record": "2-1",
        "sample_games": 3,
        "ppg": 31.3,
        "allowed_pg": 22.0,
        "point_diff_pg": 9.3,
        "recent_form": "W-W-L",
    }


def _home():
    return {
        "team": "Delaware",
        "record": "3-0",
        "sample_games": 3,
        "ppg": 28.7,
        "allowed_pg": 17.3,
        "point_diff_pg": 11.4,
        "recent_form": "W-W-W",
    }


def test_step2_contract_is_presentation_only():
    assert step2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step2.MAY_MODIFY_PROJECTION is False
    assert step2.STEP2_REQUIRED_FIELDS == (
        "team",
        "sample_games",
        "ppg",
        "allowed_pg",
        "point_diff_pg",
        "recent_form",
    )


def test_step2_complete_pair_is_ready():
    contract = step2.build_step2_contract(_identity(), _away(), _home())
    assert contract["ready"] is True
    assert contract["away"]["missing_fields"] == []
    assert contract["home"]["missing_fields"] == []


def test_step2_missing_core_profile_field_fails_closed():
    away = _away()
    away["recent_form"] = ""
    contract = step2.build_step2_contract(_identity(), away, _home())
    assert contract["ready"] is False
    assert "recent_form" in contract["away"]["missing_fields"]


def test_step2_render_is_connected_collapsible_profile():
    html = step2.render_step2_html("READY", _identity(), _away(), _home())
    assert '<details class="gt159-step gt166-step2 ready"' in html
    assert 'data-testid="gt157-step-2"' in html
    assert "Team Profile" in html
    assert "Record • Sample Games • Points/Game • Allowed/Game • Point Diff/Game • Recent Form" in html
    assert "Coastal Carolina" in html
    assert "Delaware" in html
    assert "31.3" in html
    assert "22.0" in html
    assert "W-W-L" in html
    assert "PROFILE READY" in html


def test_step2_css_keeps_connected_full_width_layout():
    assert ".gt166-step2{grid-column:1/-1!important" in step2.STEP2_CSS
    assert ".gt166-team-pair{display:grid" in step2.STEP2_CSS
