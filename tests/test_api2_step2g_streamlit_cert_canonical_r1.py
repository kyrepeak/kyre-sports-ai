from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CERT_PATH = ROOT / "devsystem" / "api2_step2g_streamlit_cert_v1.py"


def _load():
    spec = importlib.util.spec_from_file_location("step2g_cert_canonical_r1", CERT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step2g_live_cert_uses_runtime_v5_canonical_route_keys():
    cert = _load()
    target = cert.production_route_url("NFL", "Game Total")
    assert target == "https://pickvault.streamlit.app/?sport=nfl&market=game-total"
    assert "ks_jump_sport" not in target
    assert "ks_jump_market" not in target


def test_step2g_live_cert_supports_page_specific_positive_and_negative_markers():
    cert = _load()
    body = "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1 NFL GAME TOTALS KYRE TOTAL MODEL RANGE"
    result = cert.evaluate_rendered_body(
        body,
        required_markers=[
            "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1",
            "NFL GAME TOTALS",
            "KYRE TOTAL",
            "MODEL RANGE",
        ],
        forbidden_markers=["STEP 8 OF 10", "projection remains OFF"],
    )
    assert result["live_render_verified"] is True
    assert result["forbidden_markers_present"] == []

    with pytest.raises(cert.Step2GStreamlitCertificationFailure, match="FORBIDDEN_MARKER"):
        cert.evaluate_rendered_body(
            body + " STEP 8 OF 10",
            required_markers=["NFL GAME TOTALS"],
            forbidden_markers=["STEP 8 OF 10", "projection remains OFF"],
        )


def test_step2g_live_cert_cli_is_route_generic_not_jump_helper_specific():
    source = CERT_PATH.read_text(encoding="utf-8")
    assert 'parser.add_argument("--sport"' in source
    assert 'parser.add_argument("--market"' in source
    assert 'parser.add_argument("--forbidden-marker"' in source
    assert "production_route_url(args.sport, args.market)" in source
