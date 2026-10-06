from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ENGINE = ROOT / "wnba_pra_repair_v1_step5_decision_fallback.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback.py"


def _load_engine():
    assert ENGINE.exists(), "Step 5 decision fallback engine does not exist yet"
    spec = spec_from_file_location("wnba_pra_repair_v1_step5_decision_fallback_test", ENGINE)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _history(*pra_values: int):
    rows = []
    for index, pra in enumerate(pra_values, start=1):
        rows.append({
            "game_date": f"2026-09-{30-index:02d}",
            "points": pra,
            "rebounds": 0,
            "assists": 0,
        })
    return {"games": rows}


def test_step5_exact_certified_market_always_wins():
    engine = _load_engine()
    base = {
        "player_id": 42,
        "player_name": "Test Player",
        "expected_pra": 31.7,
        "line": 30.5,
        "direction": "OVER",
        "probability": 0.641,
        "market_ready": True,
        "card_state": "qualified_exact_pra_card",
    }
    result = engine.build_step5_decision(base, _history(35, 33, 31, 29, 27), None)
    assert result["line"] == 30.5
    assert result["direction"] == "OVER"
    assert result["probability"] == 0.641
    assert result["decision_source"] == "CERTIFIED MARKET"
    assert result["line_source"] == "SPORTSBOOK"
    assert result["fallback_used"] is False


def test_step5_model_fallback_uses_reference_line_and_frozen_step5f_probability():
    engine = _load_engine()
    base = {
        "player_id": 42,
        "player_name": "Test Player",
        "expected_pra": 29.2,
        "line": None,
        "direction": "N/A",
        "probability": None,
        "market_ready": False,
        "card_state": "no_qualified_exact_pra_card",
    }
    probability_payload = {
        "primary_result": {
            "fair_odds": {
                "over": {"available": True, "fair_probability": 0.66},
                "under": {"available": True, "fair_probability": 0.34},
            }
        }
    }
    result = engine.build_step5_decision(
        base,
        _history(30, 28, 26, 24, 22),
        probability_payload,
    )
    assert result["line"] == 26.5
    assert result["direction"] == "OVER"
    assert result["probability"] == 0.66
    assert result["decision_source"] == "MODEL FALLBACK"
    assert result["line_source"] == "REFERENCE"
    assert result["fallback_used"] is True
    assert result["reference_line_is_sportsbook"] is False


def test_step5_history_fallback_uses_official_hit_rate_when_model_unavailable():
    engine = _load_engine()
    base = {
        "player_id": 42,
        "player_name": "Test Player",
        "expected_pra": 29.2,
        "line": None,
        "direction": "N/A",
        "probability": None,
        "market_ready": False,
        "card_state": "consumer_not_ready",
    }
    result = engine.build_step5_decision(base, _history(30, 28, 26, 24, 22), None)
    assert result["line"] == 26.5
    assert result["direction"] == "UNDER"
    assert result["probability"] == 0.6
    assert result["decision_source"] == "HISTORY FALLBACK"
    assert result["line_source"] == "REFERENCE"
    assert result["history_games_used"] == 5


def test_step5_fully_unavailable_fails_closed_without_inventing_probability():
    engine = _load_engine()
    base = {
        "player_id": 42,
        "player_name": "Test Player",
        "expected_pra": 29.2,
        "line": None,
        "direction": "N/A",
        "probability": None,
        "market_ready": False,
        "card_state": "consumer_not_ready",
    }
    result = engine.build_step5_decision(base, None, None)
    assert result["line"] is None
    assert result["direction"] == "N/A"
    assert result["probability"] is None
    assert result["decision_source"] == "DATA LIMITED"
    assert result["fallback_used"] is False


def test_step5_renderer_contract_is_source_aware():
    engine = _load_engine()
    assert callable(engine.render_step5_final_card)
    source = ENGINE.read_text(encoding="utf-8")
    for token in (
        "CERTIFIED MARKET",
        "MODEL FALLBACK",
        "HISTORY FALLBACK",
        "DATA LIMITED",
        "Reference Line",
        "Sportsbook Line",
    ):
        assert token in source


def test_step5_overlay_is_additive_above_frozen_step4_and_uses_hosted_step5f():
    assert OVERLAY.exists(), "Step 5 overlay does not exist yet"
    source = OVERLAY.read_text(encoding="utf-8")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card"' in source
    assert "player_intelligence.load_player_intelligence" in source
    assert "step4_final_card.build_final_card" in source
    assert "step4_final_card.render_final_card" in source
    assert "/prop-threshold-probability" in source
    assert "KyreWNBAAPIClient" in source
    assert "get_player_game_prop_threshold_probability" not in source
    assert "MAY_MODIFY_PROJECTION_MATH = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert "MAY_MODIFY_QUALIFICATION = False" in source
    assert "MAY_MODIFY_RANKING = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step5_runtime_activation_is_explicit():
    assert OVERLAY.exists(), "Step 5 overlay does not exist yet"
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP5_DECISION_FALLBACK_RUNTIME" in app
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback "
        "import record_bootstrap_import_ms, render_app"
    ) in app
