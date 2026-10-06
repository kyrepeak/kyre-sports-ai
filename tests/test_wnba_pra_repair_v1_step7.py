from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "wnba_pra_repair_v1_step7_final_integration.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
APP = ROOT / "app.py"


def _load_engine():
    assert ENGINE.exists(), "Step 7 final integration engine does not exist yet"
    spec = spec_from_file_location("wnba_pra_repair_v1_step7_final_integration_test", ENGINE)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _game():
    return {
        "game_id": "401000001",
        "game_date": "2026-10-06",
        "away_team_id": 1611661319,
        "away_team": "Las Vegas Aces",
        "away_tricode": "LVA",
        "home_team_id": 1611661313,
        "home_team": "New York Liberty",
        "home_tricode": "NYL",
    }


def _player(player_id: int, team_id: int, name: str):
    return {
        "player_id": player_id,
        "player_name": name,
        "team_id": team_id,
        "team_abbreviation": "LVA" if team_id == 1611661319 else "NYL",
        "position": "G",
        "designation": "NO DESIGNATION",
        "role_label": "ACTIVE",
        "projected_minutes": 31.0,
        "projected_pts": 18.0,
        "projected_reb": 5.0,
        "projected_ast": 6.0,
        "projected_pra": 29.0,
    }


def test_step7_game_and_player_context_reuses_frozen_step6_guards():
    engine = _load_engine()
    game = _game()
    players = [
        _player(1001, 1611661319, "A. Example"),
        _player(2001, 1611661313, "B. Example"),
    ]
    result = engine.audit_game_context(game, players)
    assert result["ready"] is True
    assert result["players_seen"] == 2
    assert result["players_ready"] == 2
    assert result["team_player_counts"] == {1611661319: 1, 1611661313: 1}

    selected = engine.audit_selected_player(players[0], game)
    assert selected["ready"] is True


def test_step7_fails_closed_on_incomplete_player_context():
    engine = _load_engine()
    broken = _player(1001, 1611661319, "A. Example")
    broken["projected_pra"] = None
    result = engine.audit_selected_player(broken, _game())
    assert result["ready"] is False
    assert "projected_pra" in result["missing"]


def test_step7_accepts_all_truthful_step5_terminal_card_states():
    engine = _load_engine()
    certified = {
        "expected_pra": 29.0,
        "line": 28.5,
        "direction": "OVER",
        "probability": 0.61,
        "decision_source": "CERTIFIED MARKET",
        "line_source": "SPORTSBOOK",
    }
    limited = {
        "expected_pra": 29.0,
        "line": None,
        "direction": "N/A",
        "probability": None,
        "decision_source": "DATA LIMITED",
        "line_source": "NONE",
    }
    assert engine.audit_final_card(certified)["covered"] is True
    assert engine.audit_final_card(limited)["covered"] is True


def test_step7_router_is_additive_and_restores_every_runtime_patch():
    assert ROUTER.exists(), "Step 7 runtime wrapper does not exist yet"
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback as frozen_parent" in source
    assert "game_center.render_game_center = guarded_game_renderer" in source
    assert "game_center._render_player_card = guarded_player_card" in source
    assert "player_intelligence.render_player_intelligence = guarded_player_renderer" in source
    assert "step5_engine.render_step5_final_card = guarded_final_card_renderer" in source
    assert "game_center.render_game_center = original_game_renderer" in source
    assert "game_center._render_player_card = original_player_card_renderer" in source
    assert "player_intelligence.render_player_intelligence = original_player_renderer" in source
    assert "step5_engine.render_step5_final_card = original_final_card_renderer" in source
    assert "KyreWNBAAPIClient" not in source
    assert "requests." not in source
    assert "httpx." not in source


def test_step7_app_runtime_handoff_is_explicit_and_math_stays_frozen():
    app = APP.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8") if ROUTER.exists() else ""
    assert "WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_RUNTIME" in app
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
        "import record_bootstrap_import_ms, render_app"
    ) in app
    for flag in (
        "MAY_MODIFY_WNBA_MODEL = False",
        "MAY_MODIFY_PROJECTION_MATH = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_QUALIFICATION = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert flag in router
