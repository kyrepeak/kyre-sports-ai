from __future__ import annotations

from pathlib import Path
from time import perf_counter

import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_explosive_engine_v1 as explosive_engine
import cfb_over_under_final_v1 as final_model
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_matchup_engine_v1 as matchup_engine
import cfb_over_under_model_v1 as raw_model
import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_over_under_red_zone_engine_v1 as red_zone_engine
import cfb_over_under_slate_v11 as step12
import cfb_over_under_third_down_engine_v1 as third_down_engine
import cfb_over_under_turnover_engine_v1 as turnover_engine

ROOT = Path(__file__).resolve().parents[1]
FAST = ROOT / "cfb_over_under_fast_line_lab_v1.py"
PAGE = ROOT / "cfb_over_under_clean_page_v42.py"
LOADER = ROOT / "universal_runtime_v5_loader_v20.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_ou_v4.py"
APP = ROOT / "app.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _profiles() -> tuple[dict, dict, dict]:
    game = {
        "identity_key": "away@home:2026-10-20",
        "game_id": "12345",
        "identity_verified": True,
        "date_matches_query": True,
        "status": "scheduled",
        "away_team": "Away",
        "home_team": "Home",
    }
    away = {
        "team": "Away",
        "ppg": 31.0,
        "points_allowed_pg": 21.0,
        "recent_ppg": 33.0,
        "recent_points_allowed_pg": 20.0,
        "record": {"games": 6, "wins": 4, "losses": 2},
        "data_quality": {"grade": "GREEN"},
    }
    home = {
        "team": "Home",
        "ppg": 27.0,
        "points_allowed_pg": 24.0,
        "recent_ppg": 28.0,
        "recent_points_allowed_pg": 23.0,
        "record": {"games": 6, "wins": 3, "losses": 3},
        "data_quality": {"grade": "GREEN"},
    }
    return game, away, home


def _engine_stub() -> dict:
    return {"ready": True, "model_ready": False, "status": "CHECK", "reason": "fixture gate"}


def _build_result(line: float) -> dict:
    game, away, home = _profiles()
    matchup = _engine_stub()
    pace = _engine_stub()
    explosive = _engine_stub()
    red_zone = _engine_stub()
    third_down = _engine_stub()
    turnover = _engine_stub()
    environment = _engine_stub()
    history = _engine_stub()
    form = _engine_stub()

    raw0 = raw_model.project_matchup(game, away, home, line)
    raw3 = matchup_engine.apply_to_raw(raw0, matchup)
    raw4 = pace_engine.apply_to_raw(raw3, pace)
    raw5 = explosive_engine.apply_to_raw(raw4, explosive)
    raw6 = red_zone_engine.apply_to_raw(raw5, red_zone)
    raw7 = third_down_engine.apply_to_raw(raw6, third_down)
    raw8 = turnover_engine.apply_to_raw(raw7, turnover)
    raw9 = environment_engine.apply_to_raw(raw8, environment)
    raw10 = history_engine.apply_to_raw(raw9, history)
    raw11 = form_engine.apply_to_raw(raw10, form)

    out = {
        "version": "CFB OVER/UNDER SLATE V14 • DIRECT RUNTIME DATA",
        "game": game,
        "away": away,
        "home": home,
        "raw": dict(raw11),
        "final": dict(final_model.synthesize(game, raw11)),
        "team_diag": {"runtime_status": "GREEN"},
        "analysis_line": float(line),
        "base_raw": dict(raw0),
        "matchup_engine": matchup,
        "analysis_line_matchup_weight": 0.0,
        "step3_raw": dict(raw3),
        "pace_engine": pace,
        "analysis_line_pace_weight": 0.0,
        "step4_raw": dict(raw4),
        "explosive_engine": explosive,
        "analysis_line_explosive_weight": 0.0,
        "step5_raw": dict(raw5),
        "red_zone_engine": red_zone,
        "analysis_line_red_zone_weight": 0.0,
        "step6_raw": dict(raw6),
        "third_down_engine": third_down,
        "analysis_line_third_down_weight": 0.0,
        "step7_raw": dict(raw7),
        "turnover_engine": turnover,
        "analysis_line_turnover_weight": 0.0,
        "projected_total_turnover_weight": 0.0,
        "step8_raw": dict(raw8),
        "environment_engine": environment,
        "analysis_line_environment_weight": 0.0,
        "projected_total_environment_weight": 0.0,
        "injury_model_weight": 0.0,
        "step9_raw": dict(raw9),
        "history_engine": history,
        "analysis_line_history_weight": 0.0,
        "projected_total_history_weight": 0.0,
        "selection_history_weight": 0.0,
        "step10_raw": dict(raw10),
        "form_strength_engine": form,
        "analysis_line_form_weight": 0.0,
        "direct_selection_form_weight": 0.0,
        "deep_data_reconciled": True,
        "runtime_data_direct": True,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "new_model_formula_added": False,
    }
    out = step12._attach_certificate(out)
    out["version"] = "CFB OVER/UNDER SLATE V14 • DIRECT RUNTIME DATA"
    out["analysis_line"] = float(line)
    return out


def test_fast_line_lab_is_pure_reline_with_no_provider_builders() -> None:
    source = _source(FAST)
    assert "MAY_FETCH_EXTERNAL_DATA = False" in source
    assert "PROJECTION_MATH_CHANGED = False" in source
    assert "raw_model._line_probabilities" in source
    assert "reconcile_matchup(" not in source
    assert "build_matchup_engine(" not in source
    assert "build_pace_engine(" not in source
    assert "build_environment_engine(" not in source
    assert "build_history_engine(" not in source


def test_fast_reline_matches_frozen_pipeline_for_new_threshold() -> None:
    import cfb_over_under_fast_line_lab_v1 as fast

    baseline = _build_result(45.5)
    actual = fast.reline_result(baseline, 52.5)
    expected = _build_result(52.5)

    for key in (
        "projected_away_points",
        "projected_home_points",
        "projected_total",
        "structural_total_sigma",
        "analysis_line",
        "over_probability",
        "under_probability",
        "push_probability",
        "model_lean",
        "reliability",
        "feature_coverage",
    ):
        assert actual["raw"].get(key) == expected["raw"].get(key), key

    for key in (
        "selection",
        "selection_probability",
        "grade",
        "tier",
        "analysis_line",
        "projection_line_distance",
        "over_probability",
        "under_probability",
    ):
        assert actual["final"].get(key) == expected["final"].get(key), key

    assert actual["certification"]["status"] == expected["certification"]["status"]
    assert actual["certification"]["projection_fingerprint"] == expected["certification"]["projection_fingerprint"]
    assert actual["fast_line_lab"] is True
    assert actual["external_fetches"] == 0


def test_fast_reline_does_not_mutate_frozen_projection_components() -> None:
    import cfb_over_under_fast_line_lab_v1 as fast

    baseline = _build_result(45.5)
    actual = fast.reline_result(baseline, 60.5)
    assert actual["raw"]["projected_total"] == baseline["raw"]["projected_total"]
    assert actual["raw"]["projected_away_points"] == baseline["raw"]["projected_away_points"]
    assert actual["raw"]["projected_home_points"] == baseline["raw"]["projected_home_points"]
    assert actual["raw"]["components"] == baseline["raw"]["components"]
    assert actual["raw"]["analysis_line"] == 60.5


def test_fast_reline_compute_path_is_sub_20ms_average_in_process() -> None:
    import cfb_over_under_fast_line_lab_v1 as fast

    baseline = _build_result(45.5)
    started = perf_counter()
    for idx in range(100):
        fast.reline_result(baseline, 30.5 + float(idx % 50) * 0.5)
    elapsed = perf_counter() - started
    assert elapsed < 2.0, elapsed


def test_v42_isolates_slider_in_fragment_and_reuses_one_baseline_analysis() -> None:
    source = _source(PAGE)
    assert "import cfb_over_under_clean_page_v41 as frozen_page" in source
    assert "import cfb_over_under_fast_line_lab_v1 as fast_line" in source
    assert "@st.fragment" in source
    assert "fast_line.reline_result(base_result, float(line))" in source
    assert "runtime_slate.analyze_game(selected_game, day, baseline_line)" in source
    fragment = source.split("@st.fragment", 1)[1]
    assert "runtime_slate.analyze_game" not in fragment
    assert "market_adapter.load_odds_for_date" not in fragment
    assert "schedule_v6.load_with_diagnostics" not in fragment


def test_v42_overlaps_selected_game_prewarm_with_market_wait() -> None:
    source = _source(PAGE)
    assert "ThreadPoolExecutor(max_workers=2)" in source
    assert "prewarm.warm_selected_game" in source
    assert "market_adapter.load_odds_for_date" in source
    assert "analysis.prewarm.parallel" in source
    assert "analysis.prewarm.wait_after_market" in source


def test_v42_keeps_scan_explicit_and_slider_path_network_free() -> None:
    source = _source(PAGE)
    assert "runtime_slate.scan_slate(" in source
    assert "Run O/U scan" in source
    assert "FAST LINE LAB" in source
    assert "0 external fetches per slider move" in source


def test_loader_v20_routes_only_cfb_over_under_to_v42() -> None:
    source = _source(LOADER)
    assert "import universal_runtime_v5_loader_v19 as prior" in source
    assert 'route.sport_id == "cfb" and route.market_id == "over-under"' in source
    assert 'importlib.import_module("cfb_over_under_clean_page_v42")' in source
    assert "return base.renderer(page)" in source
    assert "return prior.resolve_destination(route)" in source


def test_terminal_v4_and_app_advance_only_cfb_ou_handoff() -> None:
    source = _source(TERMINAL)
    assert "import streamlit_memory_lazy_router_universal_runtime_v5 as prior" in source
    assert "from universal_runtime_v5_loader_v20 import choose_prefetch, load_destination, resolve_destination" in source
    assert "prior.choose_prefetch = choose_prefetch" in source
    assert "prior.load_destination = load_destination" in source
    assert "prior.resolve_destination = resolve_destination" in source
    assert "return prior.render_app()" in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_ou_v4" in _source(APP)
