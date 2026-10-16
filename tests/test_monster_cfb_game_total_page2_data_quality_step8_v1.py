from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"
DATA_QUALITY = ROOT / "cfb_game_total_page2_data_quality_step8_v1.py"


def _data_quality() -> ModuleType:
    assert DATA_QUALITY.exists(), "Step-8 data-quality presentation helper is not implemented yet"
    spec = importlib.util.spec_from_file_location("cfb_game_total_page2_data_quality_step8_v1", DATA_QUALITY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime() -> ModuleType:
    return importlib.import_module("cfb_game_total_page2_step8_final_runtime_v1")


def test_step8_formats_owned_numbers_without_long_float_leakage() -> None:
    data_quality = _data_quality()
    assert data_quality.format_optional_number(69.46167500000001) == "69.5"
    assert data_quality.format_optional_number(13.0) == "13.0"
    assert data_quality.format_optional_number(0) == "0.0"
    assert data_quality.format_optional_number(None) is None
    assert data_quality.format_optional_percent(0.69461675) == "69.5%"


def test_step8_distinguishes_missing_from_real_zero() -> None:
    data_quality = _data_quality()
    assert data_quality.display_number(None, missing="No verified market total available") == "No verified market total available"
    assert data_quality.display_number("", missing="No verified market total available") == "No verified market total available"
    assert data_quality.display_number(0, missing="No verified market total available") == "0.0"


def test_step8_quality_states_are_verified_partial_or_unavailable() -> None:
    data_quality = _data_quality()
    assert data_quality.pair_quality(71.2, 68.9) == "VERIFIED"
    assert data_quality.pair_quality(71.2, None) == "PARTIAL"
    assert data_quality.pair_quality(None, None) == "UNAVAILABLE"

    assert data_quality.market_quality(52.5, identity_verified=True, projection_weight=0.0) == "VERIFIED"
    assert data_quality.market_quality(52.5, identity_verified=False, projection_weight=0.0) == "PARTIAL"
    assert data_quality.market_quality(None, identity_verified=False, projection_weight=0.0) == "UNAVAILABLE"

    assert data_quality.trends_quality(recent_available=True, splits_available=True) == "VERIFIED"
    assert data_quality.trends_quality(recent_available=True, splits_available=False) == "PARTIAL"
    assert data_quality.trends_quality(recent_available=False, splits_available=False) == "UNAVAILABLE"


def test_step8_quality_strip_exposes_all_required_statuses() -> None:
    data_quality = _data_quality()
    html = data_quality.build_data_quality_strip_html(
        market="VERIFIED",
        pace="PARTIAL",
        explosives="UNAVAILABLE",
        red_zone="VERIFIED",
        trends="PARTIAL",
    )
    assert 'data-testid="gtp2s8-data-quality"' in html
    for label in ("Market", "Pace", "Explosives", "Red Zone", "Trends"):
        assert label in html
    assert 'data-quality="VERIFIED"' in html
    assert 'data-quality="PARTIAL"' in html
    assert 'data-quality="UNAVAILABLE"' in html


def test_step8_market_missing_no_bet_copy_preserves_owned_lean() -> None:
    data_quality = _data_quality()
    assert data_quality.market_unavailable_rationale("OVER") == (
        "Model favors Over, but verified market data is unavailable, so no official bet is issued."
    )
    assert data_quality.market_unavailable_rationale("UNDER") == (
        "Model favors Under, but verified market data is unavailable, so no official bet is issued."
    )


def test_step8_runtime_preserves_missing_red_zone_and_formats_trend_drivers() -> None:
    runtime = _runtime()
    assert runtime._display_profile_percent(None) is None
    assert runtime._display_profile_percent(0.69461675) == "69.5%"
    assert runtime._display_trend_number(
        69.46167500000001,
        missing="No verified explosive-scoring data available",
    ) == "69.5"
    assert runtime._display_trend_number(
        None,
        missing="No verified scoring-opportunity data available",
    ) == "No verified scoring-opportunity data available"
    assert runtime._display_trend_percent(
        0.69461675,
        missing="No verified red-zone finishing data available",
    ) == "69.5%"


def test_step8_market_missing_no_bet_uses_owned_probability_lean() -> None:
    runtime = _runtime()
    recommendation = runtime._recommendation(
        {
            "projected_combined_total": 58.0,
            "over_probability": 0.61,
            "under_probability": 0.39,
        },
        {
            "ready": True,
            "forecast_ready": True,
            "projected_combined_total": 58.0,
        },
        {
            "market_total": None,
            "market_identity_verified": False,
            "market_projection_weight": 0.0,
        },
    )
    assert recommendation["side"] == "NO BET"
    assert recommendation["rationale"] == (
        "Model favors Over, but verified market data is unavailable, so no official bet is issued."
    )


def test_step8_runtime_uses_data_quality_layer_without_recomputing_model() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert "import cfb_game_total_page2_data_quality_step8_v1 as data_quality" in source
    assert "data_quality.build_data_quality_strip_html" in source
    assert "data_quality.market_unavailable_rationale" in source
    assert "data_quality.format_optional_number" in source
    assert "data_quality.format_optional_percent" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "NETWORK_CALLS_ADDED = 0" in source


def test_step8_rendered_page2_output_applies_normalization_quality_and_no_bet_copy(monkeypatch) -> None:
    runtime = _runtime()

    monkeypatch.setattr(
        runtime.step4,
        "build_outlook_projection_summary_html",
        lambda **kwargs: (
            "<outlook>"
            f"{kwargs['over_probability']}|{kwargs['under_probability']}|"
            f"{kwargs['projected_total']}|{kwargs['market_line']}|{kwargs['edge']}"
            "</outlook>"
        ),
    )
    monkeypatch.setattr(
        runtime.step5,
        "build_team_snapshot_key_drivers_html",
        lambda **kwargs: (
            "<snapshot>"
            f"{kwargs['away_pace']}|{kwargs['home_pace']}|"
            f"{kwargs['away_explosive']}|{kwargs['home_explosive']}|"
            f"{kwargs['away_red_zone']}|{kwargs['home_red_zone']}|"
            f"{kwargs['away_defense']}|{kwargs['home_defense']}"
            "</snapshot>"
        ),
    )
    monkeypatch.setattr(runtime.step6, "build_trends_scoring_breakdown_html", lambda **kwargs: "<trends/>")
    monkeypatch.setattr(runtime.step7, "build_line_lab_html", lambda **kwargs: "<line-lab/>")
    monkeypatch.setattr(
        runtime.stage5,
        "build_best_bet_html",
        lambda recommendation: f"<best-bet>{recommendation['rationale']}</best-bet>",
    )
    monkeypatch.setattr(runtime, "_matchup_contract", lambda *args, **kwargs: {})
    monkeypatch.setattr(runtime.stage6, "build_tough_favorable_html", lambda contract: "<tough-favorable/>")

    payload = {
        "identity": {
            "away": {"team": "Away State"},
            "home": {"team": "Home State"},
        },
        "away": {
            "plays_per_game": 71.234,
            "yards_per_play": 0.184,
            "red_zone_td_rate": 0.631,
            "points_allowed_pg": 13.0,
        },
        "home": {
            "red_zone_td_rate": 0.552,
            "points_allowed_pg": 0,
        },
        "display_game": {
            "event_id": "step8-render-proof",
            "market_identity_verified": False,
            "market_projection_weight": 0.0,
        },
        "raw": {
            "over_probability": 0.69461675,
            "under_probability": 0.30538325,
            "recent_totals": [67.0, 72.0],
            "scoring_breakdown": {},
        },
        "final": {
            "ready": True,
            "forecast_ready": True,
            "projected_total": 69.46167500000001,
        },
    }

    html = runtime.build_page2_body_html(payload)

    assert "69.5%|30.5%|69.5|No verified market total available|No verified edge available" in html
    assert "71.2|None|18.4%|None|63.1%|55.2%|13.0|0.0" in html
    assert "69.46167500000001" not in html

    assert '<span>Market</span><strong>Unavailable</strong>' in html
    assert '<span>Pace</span><strong>Partial</strong>' in html
    assert '<span>Explosives</span><strong>Partial</strong>' in html
    assert '<span>Red Zone</span><strong>Verified</strong>' in html
    assert '<span>Trends</span><strong>Partial</strong>' in html

    assert (
        "Model favors Over, but verified market data is unavailable, so no official bet is issued."
        in html
    )
