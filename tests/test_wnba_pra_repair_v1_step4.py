from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card.py"
CARD = ROOT / "wnba_pra_repair_v1_step4_final_card.py"


def _load_card_module():
    assert CARD.exists(), "Step 4 final-card builder does not exist yet"
    spec = spec_from_file_location("wnba_pra_repair_v1_step4_final_card_test", CARD)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step4_runtime_overlay_is_explicitly_activated():
    assert OVERLAY.exists(), "Step 4 overlay does not exist yet"
    assert CARD.exists(), "Step 4 final-card builder does not exist yet"
    app = APP.read_text(encoding="utf-8")
    assert "WNBA_PRA_REPAIR_V1_STEP4_UNIVERSAL_CARD_RUNTIME" in app
    assert (
        "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card "
        "import record_bootstrap_import_ms, render_app"
    ) in app


def test_step4_overlay_preserves_frozen_step3_parent_and_math_ownership():
    assert OVERLAY.exists(), "Step 4 overlay does not exist yet"
    source = OVERLAY.read_text(encoding="utf-8")
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness"' in source
    for token in (
        "MAY_MODIFY_WNBA_MODEL = False",
        "MAY_MODIFY_PROJECTION_MATH = False",
        "MAY_MODIFY_MARKET_MATH = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_QUALIFICATION = False",
        "MAY_MODIFY_RANKING = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert token in source


def test_step4_final_card_is_universal_and_truthful():
    assert CARD.exists(), "Step 4 final-card builder does not exist yet"
    source = CARD.read_text(encoding="utf-8")
    for token in (
        "Expected PRA",
        "Line",
        "Direction",
        "Probability",
        "N/A",
        "build_final_card",
        "render_final_card",
    ):
        assert token in source
    # Step 4 is presentation/handoff only. Missing market fields must remain N/A;
    # Step 5 owns any later fallback decision logic.
    forbidden = (
        "random.",
        "numpy.random",
        "norm.cdf",
        "sportsbook",
        "monte_carlo",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered


def test_step4_unqualified_player_keeps_expected_pra_and_na_market_fields():
    card = _load_card_module()
    summary = card.build_final_card(
        {"player_id": 42, "player_name": "Test Player", "projected_pra": 31.7},
        None,
        "no_qualified_exact_pra_card",
    )
    assert summary["expected_pra"] == 31.7
    assert summary["line"] is None
    assert summary["direction"] == "N/A"
    assert summary["probability"] is None
    assert summary["market_ready"] is False


def test_step4_qualified_player_reuses_exact_certified_market_values():
    card = _load_card_module()
    summary = card.build_final_card(
        {"player_id": 42, "player_name": "Test Player", "projected_pra": 36.2},
        {
            "prop": {"stat": "pra", "pick": "OVER 34.5", "line": 34.5},
            "model": {"resolved_fair_probability": 0.623},
        },
        "qualified_exact_pra_card",
    )
    assert summary["expected_pra"] == 36.2
    assert summary["line"] == 34.5
    assert summary["direction"] == "OVER"
    assert summary["probability"] == 0.623
    assert summary["market_ready"] is True


def test_step4_overlay_reuses_frozen_player_payload_without_extra_model_work():
    assert OVERLAY.exists(), "Step 4 overlay does not exist yet"
    source = OVERLAY.read_text(encoding="utf-8")
    assert "player_intelligence._exact_pra_card" in source
    assert "player_intelligence.render_player_intelligence" in source
    assert "projection_runs" not in source
    assert "sportsbook_calls" not in source
