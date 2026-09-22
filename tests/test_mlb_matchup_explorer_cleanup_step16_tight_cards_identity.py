from pathlib import Path

import mlb_matchup_hub_v56 as step16


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _card(step: int, body: str, badge: str = "DATA • 90/100") -> str:
    return (
        f'<div class="mxv2-step mxv2-step{step}">'
        '<div class="mxv2-top"><div class="mxv2-kicker">STEP</div>'
        f'<div class="mxv2-badge">{badge}</div></div>'
        f'{body}</div>'
    )


def test_router_points_to_step16_presentation():
    source = _text("mlb_matchup_hub_v27.py")
    assert "from mlb_matchup_hub_v56 import" in source
    assert "from mlb_matchup_hub_v55 import" not in source


def test_step16_builds_on_frozen_step14_and_reuses_step15_strength_rules():
    source = _text("mlb_matchup_hub_v56.py")
    assert "import mlb_matchup_hub_v54 as current" in source
    assert "import mlb_matchup_hub_v55 as strength" in source
    assert 'FROZEN_STEP14_PRESENTATION = "mlb_matchup_hub_v54"' in source
    assert 'FROZEN_STEP15_PRESENTATION = "mlb_matchup_hub_v55"' in source
    assert "strength._strength_for_step" in source


def test_player_selection_is_keyed_by_immutable_mlb_player_id():
    players = [
        {"id": 700003, "name": "Three"},
        {"id": 700001, "name": "One"},
        {"id": 700002, "name": "Two"},
    ]
    mapping = step16._player_id_index(players)
    assert mapping == {700003: 0, 700001: 1, 700002: 2}

    source = _text("mlb_matchup_hub_v56.py")
    assert 'player_key = f"mx56_player_id_{game_pk}"' in source
    assert 'st.session_state["mh12_player"] = selected_index' in source
    assert 'st.session_state["mx56_active_player_id"] = selected_pid' in source


def test_selected_game_roster_snapshot_is_stable_across_later_reads():
    first = [
        {"id": 11, "name": "Selected"},
        {"id": 22, "name": "Other"},
    ]
    calls = {"count": 0}

    def original(row):
        calls["count"] += 1
        return [{"id": 99, "name": "Fresh order"}]

    snapshot = {"game_pk": 1234, "players": first}
    wrapped = step16._stable_roster_wrapper(original, snapshot)
    selected = wrapped({"game_pk": 1234})
    assert selected == first
    assert selected is not first
    selected[0]["name"] = "Mutated"
    assert snapshot["players"][0]["name"] == "Selected"
    assert calls["count"] == 0

    other = wrapped({"game_pk": 4321})
    assert other[0]["id"] == 99
    assert calls["count"] == 1


def test_strength_grade_is_guaranteed_next_to_original_data_badge():
    source = _card(
        4,
        '<div><b>Platoon/BvP context index</b> • FAVORABLE • 72/100 • descriptive</div>',
        "STRONG MATCHUP DATA • 88/100",
    )
    decorated = step16._decorate_step(source)
    assert decorated.count("mxv2-badge") == 1
    assert decorated.count("mx56-badges") == 1
    assert decorated.count("mx56-grade") == 1
    assert "STRONG MATCHUP DATA • 88/100" in decorated
    assert "STRONG • BATTER" in decorated


def test_pending_step_still_gets_visible_gray_no_edge_grade():
    source = _card(
        5,
        '<div><b>Pitch-mix verdict</b> • PENDING • — • effective evidence coverage 0.0%</div>',
        "LOW PITCH DATA • 5/100",
    )
    decorated = step16._decorate_step(source)
    assert "PENDING • NO EDGE" in decorated
    assert 'mx56-grade pending' in decorated
    assert "LOW PITCH DATA • 5/100" in decorated


def test_pitcher_side_language_uses_tough_wording_requested_for_mobile_scan():
    assert step16._display_grade({"label": "LEAN PITCHER", "kind": "pitcher"}) == (
        "SLIGHTLY TOUGH • PITCHER",
        "pitcher",
    )
    assert step16._display_grade({"label": "STRONG PITCHER EDGE", "kind": "pitcher"}) == (
        "TOUGH • PITCHER",
        "pitcher",
    )
    assert step16._display_grade({"label": "ELITE PITCHER EDGE", "kind": "pitcher"}) == (
        "VERY TOUGH • PITCHER",
        "pitcher",
    )


def test_step16_decorates_at_step14_owned_final_render_boundary():
    source = _text("mlb_matchup_hub_v56.py")
    assert "original_owned = current._owned_scouting_html" in source
    assert "current._owned_scouting_html = _owned_scouting_wrapper(original_owned)" in source
    assert "current._owned_scouting_html = original_owned" in source
    assert "scouting._scouting_html" not in source


def test_mobile_step_stack_is_tighter_but_keeps_certified_rows():
    source = _text("mlb_matchup_hub_v56.py")
    assert ".mx53-shell .mxv2-step{padding:10px 11px!important;margin:6px 0!important" in source
    assert ".mx53-shell .mxv2-row{font-size:.61rem!important;line-height:1.42!important;margin:4px 0!important}" in source
    assert ".mx53-shell .mxv2-statgrid{gap:5px!important" in source
    assert "Tighten the finished Step cards without removing a single certified evidence row" in source


def test_strength_legend_explains_all_four_states():
    source = _text("mlb_matchup_hub_v56.py")
    assert "GREEN = BATTER" in source
    assert "RED = TOUGH / PITCHER" in source
    assert "GOLD = NEUTRAL" in source
    assert "GRAY = PENDING / NO EDGE" in source


def test_step16_restores_every_temporary_runtime_patch():
    source = _text("mlb_matchup_hub_v56.py")
    assert "selectors._render_stable_selectors = original_selectors" in source
    assert "roster._all_hitters_v14 = original_all_hitters" in source
    assert "current._owned_scouting_html = original_owned" in source
    assert "finally:" in source


def test_step16_is_presentation_and_identity_only_no_model_math_reimplementation():
    source = _text("mlb_matchup_hub_v56.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "monte_carlo_distribution(",
        "5_000_000",
        "np.random",
        "default_rng",
        "render_daily_rankings(",
        "mlb_moneyline_hub",
    ):
        assert forbidden not in source


def test_historical_step15_workflow_is_scoped_to_original_branch():
    source = _text(".github/workflows/mlb-matchup-explorer-cleanup-step15-step-strength.yml")
    assert "Historical exact-scope certification belongs only to Cleanup Step 15." in source
    assert "github.head_ref == 'mlb-matchup-explorer-cleanup-step15-step-strength'" in source
