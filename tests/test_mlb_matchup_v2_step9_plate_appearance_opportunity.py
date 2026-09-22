from pathlib import Path

import mlb_matchup_opportunity_v1 as opportunity
import mlb_matchup_player_v32 as player


def _foundation(slot=1, side="home", confirmed=True, projected=False, season_pa=500, season_ab=445):
    return {
        "player_id": 23,
        "player_name": "Test Hitter",
        "game_pk": 777,
        "game_date": "2026-09-02",
        "team": "Test Club",
        "opponent": "Opponent",
        "side": side,
        "slot": slot,
        "valid_slot": slot is not None and 1 <= slot <= 9,
        "confirmed": confirmed,
        "projected": projected,
        "season_pa": season_pa,
        "season_ab": season_ab,
    }


def _season(games=120, pa_per_game=38.0):
    return {
        "status": "VERIFIED",
        "source": "Official MLB team season hitting",
        "games": games,
        "pa": int(round(games * pa_per_game)),
    }


def _logs(home_pa=39, away_pa=37, games_each=20):
    rows = []
    day = 80
    for i in range(games_each):
        rows.append({"date": f"2026-08-{(day-i)%28+1:02d}", "is_home": True, "pa": home_pa})
    for i in range(games_each):
        rows.append({"date": f"2026-07-{(day-i)%28+1:02d}", "is_home": False, "pa": away_pa})
    return {"status": "VERIFIED", "source": "Official MLB team hitting game logs", "games": rows}


def _bullpen(share=0.40):
    return {"bullpen_inning_share": share, "exposure": {"status": "VERIFIED"}}


def test_integer_batting_cycle_assigns_leftover_pa_to_top_slots_first():
    assert opportunity.slot_pa_from_team_total(36, 1) == 4
    assert opportunity.slot_pa_from_team_total(37, 1) == 5
    assert opportunity.slot_pa_from_team_total(37, 2) == 4
    assert opportunity.slot_pa_from_team_total(41, 5) == 5
    assert opportunity.slot_pa_from_team_total(41, 6) == 4


def test_continuous_expected_team_pa_preserves_order_advantage():
    leadoff = opportunity.slot_pa_from_expected_team_pa(38.5, 1)
    ninth = opportunity.slot_pa_from_expected_team_pa(38.5, 9)
    assert leadoff is not None and ninth is not None
    assert leadoff > ninth
    assert leadoff == 5.0
    assert ninth == 4.0


def test_home_history_changes_opportunity_without_guessing_ninth_inning_penalty():
    home = opportunity.build_opportunity_profile(
        _foundation(slot=1, side="home"), 1, _season(), _logs(home_pa=41, away_pa=35), _bullpen()
    )
    away = opportunity.build_opportunity_profile(
        _foundation(slot=1, side="away"), 1, _season(), _logs(home_pa=41, away_pa=35), _bullpen()
    )
    assert home["location_team_pa_per_game"] == 41
    assert away["location_team_pa_per_game"] == 35
    assert home["expected_pa"] > away["expected_pa"]
    assert "absorbed empirically" in home["ninth_inning_note"]
    assert "no extra guessed penalty" in home["ninth_inning_note"]


def test_expected_ab_uses_player_specific_season_ab_per_pa():
    d = opportunity.build_opportunity_profile(
        _foundation(slot=2, season_pa=600, season_ab=510), 1, _season(), _logs(), _bullpen()
    )
    assert abs(d["ab_per_pa"] - 0.85) < 1e-9
    assert d["expected_pa"] is not None
    assert abs(d["expected_ab"] - d["expected_pa"] * 0.85) < 1e-9


def test_small_hitter_sample_does_not_invent_expected_ab():
    d = opportunity.build_opportunity_profile(
        _foundation(slot=2, season_pa=35, season_ab=30), 1, _season(), _logs(), _bullpen()
    )
    assert d["expected_pa"] is not None
    assert d["ab_per_pa"] is None
    assert d["expected_ab"] is None


def test_step8_inning_share_becomes_nominal_starter_and_bullpen_pa_exposure():
    d = opportunity.build_opportunity_profile(
        _foundation(slot=3), 1, _season(), _logs(), _bullpen(0.375)
    )
    assert d["expected_pa"] is not None
    assert abs(d["nominal_bullpen_pa"] - d["expected_pa"] * 0.375) < 1e-9
    assert abs(d["nominal_starter_pa"] + d["nominal_bullpen_pa"] - d["expected_pa"]) < 1e-9


def test_missing_verified_step8_exposure_stays_blank_not_guessed():
    d = opportunity.build_opportunity_profile(
        _foundation(slot=3), 1, _season(), _logs(), {"bullpen_inning_share": 0.4, "exposure": {"status": "PENDING"}}
    )
    assert d["bullpen_inning_share_step9"] is None
    assert d["nominal_starter_pa"] is None
    assert d["nominal_bullpen_pa"] is None


def test_projected_lineup_keeps_mean_but_is_provisional():
    confirmed = opportunity.build_opportunity_profile(
        _foundation(slot=4, confirmed=True, projected=False), 1, _season(), _logs(), _bullpen()
    )
    projected = opportunity.build_opportunity_profile(
        _foundation(slot=4, confirmed=False, projected=True), 1, _season(), _logs(), _bullpen()
    )
    assert confirmed["opportunity_readiness"] == "READY"
    assert projected["opportunity_readiness"] == "PROVISIONAL"
    assert projected["expected_pa"] == confirmed["expected_pa"]


def test_invalid_lineup_slot_gates_pa_and_ab_instead_of_using_generic_default():
    d = opportunity.build_opportunity_profile(
        _foundation(slot=None), 1, _season(), _logs(), _bullpen()
    )
    assert d["opportunity_readiness"] == "GATED"
    assert d["expected_pa"] is None
    assert d["expected_ab"] is None


def test_empirical_range_requires_real_game_log_sample():
    sparse = {"status": "VERIFIED", "source": "Official MLB team hitting game logs", "games": [
        {"date": f"2026-08-{i+1:02d}", "is_home": True, "pa": 38} for i in range(5)
    ]}
    d = opportunity.build_opportunity_profile(_foundation(slot=1), 1, _season(), sparse, _bullpen())
    assert d["pa_low"] is None
    assert d["pa_high"] is None


def test_recent_team_pa_volume_is_a_descriptive_opportunity_trend():
    rows = [{"date": f"2026-09-{10-i:02d}", "is_home": True, "pa": 43} for i in range(10)]
    rows += [{"date": f"2026-08-{20-i:02d}", "is_home": True, "pa": 36} for i in range(15)]
    payload = {"status": "VERIFIED", "source": "Official MLB team hitting game logs", "games": rows}
    d = opportunity.build_opportunity_profile(_foundation(slot=1), 1, _season(pa_per_game=37), payload, _bullpen())
    assert d["recent_team_pa_per_game"] == 43
    assert d["offense_volume_label"] == "RECENT PA VOLUME ABOVE SEASON"


def test_probability_boundary_is_explicit_and_no_probability_engine_is_added():
    assert player.PROBABILITY_IMPACT == "NONE"
    assert player.STEP9_ROLE == "PLATE_APPEARANCE_OPPORTUNITY_ONLY"
    text = Path("mlb_matchup_opportunity_v1.py").read_text() + Path("mlb_matchup_player_v32.py").read_text()
    forbidden = [
        "def monte_carlo",
        "def fair_odds",
        "p_one_plus_pre_matchup =",
        "p_two_plus =",
        "def _simulate",
        "def _calibration_from_verdict",
    ]
    for token in forbidden:
        assert token.lower() not in text.lower()


def test_steps_1_through_9_accumulate_in_same_v2_panel_and_v1_stays_separate():
    text = Path("mlb_matchup_player_v32.py").read_text()
    assert "with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):" in text
    for call in [
        "step1._render_step1(games_df)",
        "step2._render_step2(games_df)",
        "step3._render_step3(games_df)",
        "step4._render_step4(games_df)",
        "step5._render_step5(games_df)",
        "step6._render_step6(games_df)",
        "step7._render_step7(games_df)",
        "step8._render_step8(games_df)",
        "_render_step9(games_df)",
    ]:
        assert call in text
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in text
    assert "frozen_detail.render_player_layer" in text


def test_hub_and_router_point_to_step9_while_rankings_remain_frozen():
    hub = Path("mlb_matchup_hub_v38.py").read_text()
    router = Path("mlb_matchup_hub_v27.py").read_text()
    assert "import mlb_matchup_player_v32 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v38 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in router
