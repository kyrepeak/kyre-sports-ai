from __future__ import annotations

import cfb_game_total_step1_identity_v1 as step1


def _complete_identity():
    return {
        "away": {
            "team": "Coastal Carolina",
            "team_id": "324",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/324.png",
            "exact_identity": True,
            "conference": "Sun Belt",
            "rank": "UNRANKED",
        },
        "home": {
            "team": "Delaware",
            "team_id": "48",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/48.png",
            "exact_identity": True,
            "conference": "CUSA",
            "rank": "UNRANKED",
        },
    }


def _complete_game():
    return {
        "game_date": "2026-09-19",
        "away_mascot": "Chanticleers",
        "home_mascot": "Blue Hens",
        "away_classification": "FBS",
        "home_classification": "FBS",
        "away_record": "2-1 (0-0)",
        "home_record": "3-0 (0-0)",
        "away_head_coach": "Tim Beck",
        "home_head_coach": "Ryan Carty",
    }


def test_step1_contract_is_universal_and_projection_neutral():
    assert step1.STEP1_REQUIRED_FIELDS == (
        "logo",
        "team",
        "mascot",
        "conference",
        "classification",
        "record",
        "rank",
        "head_coach",
        "home_away",
        "season",
        "identity_verified",
    )
    assert step1.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step1.MAY_MODIFY_PROJECTION is False


def test_step1_complete_pair_is_ready_only_when_all_required_fields_exist():
    contract = step1.build_step1_contract(
        _complete_identity(),
        {"team": "Coastal Carolina", "record": "2-1 (0-0)"},
        {"team": "Delaware", "record": "3-0 (0-0)"},
        _complete_game(),
    )
    assert contract["ready"] is True
    assert contract["identity_verified"] is True
    assert contract["away"]["missing_fields"] == []
    assert contract["home"]["missing_fields"] == []
    assert contract["away"]["home_away"] == "AWAY"
    assert contract["home"]["home_away"] == "HOME"
    assert contract["away"]["season"] == "2026"
    assert contract["home"]["season"] == "2026"


def test_step1_missing_profile_data_fails_to_check_without_guessing():
    identity = _complete_identity()
    contract = step1.build_step1_contract(identity, {}, {}, {"game_date": "2026-09-19"})
    assert contract["ready"] is False
    assert contract["identity_verified"] is True
    assert "mascot" in contract["away"]["missing_fields"]
    assert "classification" in contract["away"]["missing_fields"]
    assert "head_coach" in contract["away"]["missing_fields"]
    assert "mascot" in contract["home"]["missing_fields"]
    assert contract["away"]["rank"] == "UNRANKED"


def test_step1_render_is_open_connected_accordion_and_contains_both_team_cards():
    html = step1.render_step1_html(
        "READY",
        _complete_identity(),
        {"team": "Coastal Carolina", "record": "2-1 (0-0)"},
        {"team": "Delaware", "record": "3-0 (0-0)"},
        _complete_game(),
    )
    assert '<details class="gt159-step gt165-step1 ready"' in html
    assert 'data-testid="gt157-step-1" open' in html
    assert "Team Identity" in html
    assert "Logo • Team • Mascot • Conference • FBS/FCS • Record • Rank • Coach • Home/Away • Season • Identity Verified" in html
    assert "Coastal Carolina" in html
    assert "Delaware" in html
    assert "Chanticleers" in html
    assert "Blue Hens" in html
    assert "Tim Beck" in html
    assert "Ryan Carty" in html
    assert "IDENTITY VERIFIED" in html


def test_step1_css_keeps_step_one_full_width_inside_existing_connected_grid():
    assert ".gt165-step1{grid-column:1/-1!important" in step1.STEP1_CSS
    assert ".gt165-team-pair{display:grid" in step1.STEP1_CSS



def test_step1_skips_placeholder_record_and_reads_verified_record_summary():
    identity = _complete_identity()
    contract = step1.build_step1_contract(
        identity,
        {"record": "—", "division_context": "FBS", "head_coach": "Tim Beck", "mascot": "Chanticleers"},
        {"record": "—", "division_context": "FBS", "head_coach": "Ryan Carty", "mascot": "Blue Hens"},
        {
            "game_date": "2026-09-19",
            "away_record_summary": "2-1",
            "home_record_summary": "3-0",
        },
    )
    assert contract["away"]["record"] == "2-1"
    assert contract["home"]["record"] == "3-0"
    assert contract["away"]["classification"] == "FBS"
    assert contract["home"]["classification"] == "FBS"
