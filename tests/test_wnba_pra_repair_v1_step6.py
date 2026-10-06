from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "wnba_pra_repair_v1_step6_completeness_sweep.py"
STEP2 = ROOT / "wnba_pra_repair_v1_step2_team_identity.py"
STEP3 = ROOT / "wnba_pra_repair_v1_step3_data.py"


def _load_engine():
    assert ENGINE.exists(), "Step 6 completeness sweep engine does not exist yet"
    spec = spec_from_file_location("wnba_pra_repair_v1_step6_completeness_sweep_test", ENGINE)
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


def test_step6_uses_the_same_complete_15_team_registry_as_steps2_and3():
    engine = _load_engine()
    step2 = engine._load_source_module(STEP2, "step2_identity_for_step6_test")
    step3 = engine._load_source_module(STEP3, "step3_data_for_step6_test")
    assert len(step2.TEAM_BY_ID) == 15
    assert len(step3.TEAM_REGISTRY) == 15
    assert set(step2.TEAM_BY_ID) == set(step3.TEAM_REGISTRY)
    assert engine.canonical_team_ids() == set(step2.TEAM_BY_ID)


def test_step6_game_audit_requires_full_canonical_matchup_identity():
    engine = _load_engine()
    result = engine.audit_game(_game())
    assert result["ready"] is True
    assert result["game_id"] == "401000001"
    assert result["away_team_id"] == 1611661319
    assert result["home_team_id"] == 1611661313
    assert result["missing"] == ()


def test_step6_player_audit_requires_identity_and_all_projection_components():
    engine = _load_engine()
    game = _game()
    result = engine.audit_player(_player(1001, 1611661319, "A. Example"), game)
    assert result["ready"] is True
    assert result["player_id"] == 1001
    assert result["missing"] == ()

    broken = _player(1002, 1611661319, "B. Example")
    broken["projected_ast"] = None
    incomplete = engine.audit_player(broken, game)
    assert incomplete["ready"] is False
    assert "projected_ast" in incomplete["missing"]


def test_step6_card_coverage_accepts_every_truthful_step5_terminal_state():
    engine = _load_engine()
    complete = {
        "expected_pra": 29.0,
        "line": 28.5,
        "direction": "OVER",
        "probability": 0.61,
        "decision_source": "CERTIFIED MARKET",
        "line_source": "SPORTSBOOK",
    }
    result = engine.audit_card(complete)
    assert result["covered"] is True
    assert result["decision_source"] == "CERTIFIED MARKET"

    limited = {
        "expected_pra": 29.0,
        "line": None,
        "direction": "N/A",
        "probability": None,
        "decision_source": "DATA LIMITED",
        "line_source": "NONE",
    }
    result = engine.audit_card(limited)
    assert result["covered"] is True
    assert result["truthful_data_limited"] is True


def test_step6_sweeps_every_player_on_both_teams_and_every_card():
    engine = _load_engine()
    game = _game()
    players = [
        _player(1001, 1611661319, "A. Example"),
        _player(1002, 1611661319, "B. Example"),
        _player(2001, 1611661313, "C. Example"),
        _player(2002, 1611661313, "D. Example"),
    ]
    cards = {
        1001: {"expected_pra": 29.0, "line": 28.5, "direction": "OVER", "probability": 0.61, "decision_source": "CERTIFIED MARKET", "line_source": "SPORTSBOOK"},
        1002: {"expected_pra": 29.0, "line": 27.5, "direction": "OVER", "probability": 0.64, "decision_source": "MODEL FALLBACK", "line_source": "REFERENCE"},
        2001: {"expected_pra": 29.0, "line": 29.5, "direction": "UNDER", "probability": 0.60, "decision_source": "HISTORY FALLBACK", "line_source": "REFERENCE"},
        2002: {"expected_pra": 29.0, "line": None, "direction": "N/A", "probability": None, "decision_source": "DATA LIMITED", "line_source": "NONE"},
    }
    result = engine.sweep_game(game, players, cards)
    assert result["ready"] is True
    assert result["players_seen"] == 4
    assert result["players_ready"] == 4
    assert result["cards_covered"] == 4
    assert result["team_player_counts"] == {1611661319: 2, 1611661313: 2}


def test_step6_fails_closed_when_any_player_or_card_is_missing():
    engine = _load_engine()
    game = _game()
    players = [_player(1001, 1611661319, "A. Example"), _player(2001, 1611661313, "C. Example")]
    cards = {1001: {"expected_pra": 29.0, "line": 28.5, "direction": "OVER", "probability": 0.61, "decision_source": "CERTIFIED MARKET", "line_source": "SPORTSBOOK"}}
    result = engine.sweep_game(game, players, cards)
    assert result["ready"] is False
    assert result["players_seen"] == 2
    assert result["cards_covered"] == 1
    assert result["missing_card_player_ids"] == (2001,)
