from __future__ import annotations

from pathlib import Path

import cfb_game_total_page2_data_quality_step8_v1 as data_quality

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"


def test_step8_formats_owned_numbers_without_long_float_leakage() -> None:
    assert data_quality.format_optional_number(69.46167500000001) == "69.5"
    assert data_quality.format_optional_number(13.0) == "13.0"
    assert data_quality.format_optional_number(0) == "0.0"
    assert data_quality.format_optional_number(None) is None
    assert data_quality.format_optional_percent(0.69461675) == "69.5%"


def test_step8_distinguishes_missing_from_real_zero() -> None:
    assert data_quality.display_number(None, missing="No verified market total available") == "No verified market total available"
    assert data_quality.display_number("", missing="No verified market total available") == "No verified market total available"
    assert data_quality.display_number(0, missing="No verified market total available") == "0.0"


def test_step8_quality_states_are_verified_partial_or_unavailable() -> None:
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
    assert data_quality.market_unavailable_rationale("OVER") == (
        "Model favors Over, but verified market data is unavailable, so no official bet is issued."
    )
    assert data_quality.market_unavailable_rationale("UNDER") == (
        "Model favors Under, but verified market data is unavailable, so no official bet is issued."
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
