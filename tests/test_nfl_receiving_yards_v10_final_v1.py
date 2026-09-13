from __future__ import annotations

import inspect
from pathlib import Path

import nfl_receiving_yards_hub_v7 as detailed_page
import nfl_receiving_yards_hub_v9 as prior
import nfl_receiving_yards_hub_v10 as page
import streamlit_memory_lazy_router_v121 as router


def _opponent(team_id: str = "4", abbr: str = "CIN") -> dict:
    return {
        "official_team_id": team_id,
        "team_abbreviation": abbr,
        "team_name": abbr,
    }


def _team(
    *,
    team_id: str = "27",
    opponent_id: str = "4",
    abbr: str = "TB",
    defense: dict | None = None,
) -> dict:
    base_defense = {
        "official_team_id": opponent_id,
        "receptions_allowed_per_game": 25.0,
        "receiving_yards_allowed_per_game": 260.0,
        "yards_per_reception_allowed": 12.0,
        "receiving_touchdowns_allowed_per_game": 1.8,
        "targets_data_available": False,
    }
    if defense is not None:
        base_defense.update(defense)
    return {
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "team_abbreviation": abbr,
        "team_name": abbr,
        "opponent_pass_defense": base_defense,
    }


def test_v10_is_additive_final_display_layer_only() -> None:
    assert page.FROZEN_PRIOR == "nfl_receiving_yards_hub_v9"
    assert page.FROZEN_PROJECTION_ENGINE == "nfl_receiving_yards_projection_v1"
    assert page.PAGE_BUILD_STEP == 10
    assert page.PAGE_BUILD_TOTAL == 10
    assert page.FINAL_PAGE_COMPLETE is True
    assert page.DISPLAY_ONLY is True
    assert page.MATCHUP_CLASSIFICATION_ONLY is True
    assert page.BETTING_GRADE_ENABLED is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert "width:100%!important" in page._STEP10_CSS


def test_v10_reuses_frozen_v9_matchup_classifier() -> None:
    team = _team()
    opponent = _opponent()
    expected = prior._matchup_tier(team, opponent)
    actual = page._grade_for_team_opponent(team, opponent)
    assert actual["tier"] == expected["tier"] == "FAVORABLE"
    assert actual["score"] == expected["score"] == 4
    assert actual["favorable_signals"] == expected["favorable_signals"] == 4


def test_v10_exact_identity_failure_stays_medium_unavailable() -> None:
    team = _team()
    wrong_opponent = _opponent("5", "BAL")
    grade = page._grade_for_team_opponent(team, wrong_opponent)
    assert grade["tier"] == "MEDIUM"
    assert grade["score"] == 0
    assert grade["available"] is False


def test_detailed_ribbon_keeps_exact_ids_and_never_becomes_betting_grade(monkeypatch) -> None:
    monkeypatch.setattr(page, "_ORIGINAL_DETAILED_CARD_V7", lambda _p, _t, _o: '<div class="frozen-v7">STACK</div>')
    player = {
        "official_athlete_id": "4360438",
        "official_team_id": "27",
        "player_name": "Display Name Only",
    }
    team = _team()
    opponent = _opponent()
    html = page._detailed_player_card_v10(player, team, opponent)
    assert 'data-athlete-id="4360438"' in html
    assert 'data-team-id="27"' in html
    assert 'data-opponent-id="4"' in html
    assert 'data-matchup-tier="FAVORABLE"' in html
    assert 'data-detailed-matchup-score="+4"' in html
    assert "4 favorable / 0 tough signals" in html
    assert "matchup classification only • projection unchanged" in html
    assert '<div class="frozen-v7">STACK</div>' in html
    assert "over_odds" not in html
    assert "under_odds" not in html


def test_step10_copy_advances_to_final_state() -> None:
    body = (
        "Step 9 adds transparent FAVORABLE / MEDIUM / TOUGH opponent pass-defense tiers and favorable-first sorting. "
        "Tiers are descriptive matchup classification only and never use FanDuel line or price. "
        '<span class="krecv-chip">✅ MATCHUP TIERS</span> '
        "STEP 9 OF 10 • MATCHUP TIERS LIVE"
    )
    out = page._advance_step10_copy(body)
    assert "Step 10 completes the Receiving Yards page" in out
    assert '<span class="krecv-chip">✅ FINAL CERTIFIED</span>' in out
    assert "STEP 10 OF 10 • FINAL POLISH + SPEED + CERTIFICATION" in out
    assert "STEP 9 OF 10 • MATCHUP TIERS LIVE" not in out


def test_v10_does_not_read_sportsbook_market_for_tier_or_ribbon() -> None:
    grade_source = inspect.getsource(page._grade_for_team_opponent)
    ribbon_source = inspect.getsource(page._detailed_player_card_v10)
    for forbidden in ("over_odds", "under_odds", "market_row", "FanDuel"):
        assert forbidden not in grade_source
        assert forbidden not in ribbon_source
    assert "projection_engine" not in grade_source
    assert "projection_engine" not in ribbon_source


def test_v10_temporarily_patches_and_restores_detailed_card(monkeypatch) -> None:
    original = detailed_page._player_card_v7
    observed = {"patched_card": False, "patched_copy": False}

    def fake_render() -> None:
        observed["patched_card"] = detailed_page._player_card_v7 is page._detailed_player_card_v10
        observed["patched_copy"] = prior._advance_step9_copy is page._advance_step10_copy

    monkeypatch.setattr(prior, "render_nfl_receiving_yards_hub", fake_render)
    page.render_nfl_receiving_yards_hub()
    assert observed == {"patched_card": True, "patched_copy": True}
    assert detailed_page._player_card_v7 is original
    assert prior._advance_step9_copy is page._ORIGINAL_ADVANCE_STEP9_COPY


def test_router_v121_advances_only_receiving_owner() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v120"
    assert router.ACTIVE_RECEIVING_YARDS_HUB == "nfl_receiving_yards_hub_v10"
    assert router.RECEIVING_YARDS_MARKET == "Receiving Yards"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_app_activates_v121_and_preserves_v120_heartbeat() -> None:
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v121 import record_bootstrap_import_ms, render_app" in text
    assert "STREAMLIT_MAIN_V120_NFL_RECEIVING_YARDS_STEP9_MATCHUP_TIERS_2026-09-13" in text
    assert "STREAMLIT_MAIN_V121_NFL_RECEIVING_YARDS_STEP10_FINAL_POLISH_SPEED_CERT_2026-09-13" in text
