from pathlib import Path

from mlb_matchup_hub_v51 import _phoenix_time_text, _selected_game_html


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compatibility_router_points_to_cleanup_step11():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v51 import" in source
    assert "render_matchup_hub" in source
    assert "mlb_matchup_hub_v50" not in source


def test_step11_wraps_step10_and_frozen_v2_without_rebuilding_math():
    source = _text("mlb_matchup_hub_v51.py")
    assert "import mlb_matchup_hub_v50 as step10" in source
    assert "import mlb_matchup_hub_v49 as step9" in source
    assert "import mlb_matchup_hub_v41 as current" in source
    assert 'FROZEN_STEP10_PRESENTATION = "mlb_matchup_hub_v50"' in source
    assert 'FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"' in source


def test_phoenix_time_conversion_handles_eastern_daylight_saving():
    summer = {"game_date": "2026-09-02", "first_pitch_et": "10:10 PM ET"}
    winter = {"game_date": "2026-12-02", "first_pitch_et": "10:10 PM ET"}
    assert _phoenix_time_text(summer) == "7:10 PM MST"
    assert _phoenix_time_text(winter) == "8:10 PM MST"
    assert _phoenix_time_text({"game_date": "2026-09-02", "first_pitch_et": "TBD"}) == "TBD"


def test_selected_game_card_includes_both_mlb_team_logos_and_phoenix_label():
    html = _selected_game_html(
        {
            "game_date": "2026-09-02",
            "first_pitch_et": "10:10 PM ET",
            "away_team": "St. Louis Cardinals",
            "home_team": "Los Angeles Dodgers",
            "away_team_id": 138,
            "home_team_id": 119,
            "venue_name": "Dodger Stadium",
            "away_pitcher": "Pitcher A",
            "home_pitcher": "Pitcher B",
            "status": "Pre-Game",
        }
    )
    assert "team-logos/138.svg" in html
    assert "team-logos/119.svg" in html
    assert "7:10 PM MST" in html
    assert "Phoenix time" in html
    assert "St. Louis Cardinals" in html
    assert "Los Angeles Dodgers" in html


def test_step11_uses_one_game_picker_then_one_game_scoped_player_picker():
    source = _text("mlb_matchup_hub_v51.py")
    assert '"1️⃣ Game"' in source
    assert '"2️⃣ Player"' in source
    assert 'player_key = f"mx51_player_{game_pk}"' in source
    assert 'st.session_state["mh12_game"] = game_index' in source
    assert 'st.session_state["mh12_player"] = player_index' in source
    assert 'st.session_state["mx51_active_game_pk"] = game_pk' in source
    assert "step6._render_compact_controls" not in source
    assert "View players" not in source


def test_step11_player_labels_are_lineup_first_and_self_contained():
    source = _text("mlb_matchup_hub_v51.py")
    assert "ordered = step1._ordered_player_indices(players)" in source
    assert "role_label, _ = step1._role(player)" in source
    assert 'slot_text = f"#{slot} • "' in source
    assert "team" in source and "position" in source


def test_step11_hardens_spotlight_html_against_bench_blank_line_parser_bug():
    source = _text("mlb_matchup_hub_v51.py")
    assert "source = step10._clean_loading_spotlight_html(context, final)" in source
    assert 'return "".join(line.strip() for line in source.splitlines() if line.strip())' in source
    assert "bench player has no batting-slot badge" in source.lower()


def test_step11_preserves_collapsed_research_and_restores_temporary_patches():
    source = _text("mlb_matchup_hub_v51.py")
    assert "st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)" in source
    assert "st.text_input = step10._legacy_text_input_passthrough(original_text_input)" in source
    assert "st.markdown = step10._legacy_markdown_passthrough(original_markdown)" in source
    assert "st.expander = step5._collapsed_expander(original_expander)" in source
    assert "finally:" in source
    assert "final_layer._render_step12_profile = original_step12_profile" in source
    assert "st.markdown = original_markdown" in source
    assert "st.selectbox = original_selectbox" in source


def test_step11_is_presentation_only():
    source = _text("mlb_matchup_hub_v51.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "5_000_000",
        "np.random",
        "monte_carlo",
        "def _calibration_from_verdict",
        "def _verdict_score",
        "render_daily_rankings(",
        "mlb_moneyline",
    ):
        assert forbidden not in source


def test_historical_step10_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step10-mobile-layout.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 10" in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step10-mobile-layout'" in source
