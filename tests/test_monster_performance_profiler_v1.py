from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api import monster_performance_profiler_v1 as perf
from sports_api import observability_v1 as obs

ROOT = Path(__file__).resolve().parents[1]


def test_diagnosis_names_market_bottleneck_and_share():
    trace = perf.PerformanceTrace(surface="streamlit", path="cfb-over-under")
    trace.add("market.load_odds_for_date", 1200.0, calls=1)
    trace.add("analysis.prewarm.parallel", 350.0, calls=1)
    trace.add("render.cards", 175.0, calls=8)

    diagnosis = perf.diagnose_trace(trace, total_ms=2000.0)

    assert diagnosis["bottleneck"] == "market.load_odds_for_date"
    assert diagnosis["bottleneck_category"] == "market"
    assert diagnosis["bottleneck_ms"] == 1200.0
    assert diagnosis["bottleneck_share_pct"] == 60.0
    assert diagnosis["grade"] == "SLOW"
    assert diagnosis["projection_weight"] == 0.0
    assert diagnosis["may_modify_projection"] is False
    assert "sportsbook/market fetch latency" in diagnosis["guidance"]


def test_existing_cfb_stage_rows_can_be_consumed_without_mutation():
    rows = [
        {"stage": "analysis.prewarm.parallel", "calls": 1, "total_ms": 700.0, "max_ms": 700.0},
        {"stage": "market.attach_market_lines", "calls": 2, "total_ms": 120.0, "max_ms": 80.0},
    ]
    original = [dict(row) for row in rows]
    trace = perf.PerformanceTrace(surface="streamlit")

    perf.add_stage_rows(trace, rows)
    diagnosis = perf.diagnose_trace(trace, total_ms=1000.0)

    assert rows == original
    assert diagnosis["bottleneck"] == "analysis.prewarm.parallel"
    assert diagnosis["bottleneck_category"] == "analysis"
    assert diagnosis["top_spans"][0]["calls"] == 1


def test_context_span_records_named_inner_work_and_resets_cleanly():
    trace, token = perf.start_trace("test", path="/profile")
    try:
        with perf.span("api.fake_upstream", category="api"):
            time.sleep(0.002)
        assert perf.current_trace() is trace
        assert trace.spans
        assert trace.spans[0].name == "api.fake_upstream"
        assert trace.spans[0].duration_ms > 0.0
    finally:
        perf.reset_trace(token)

    assert perf.current_trace() is None


def test_header_tokens_strip_unsafe_characters():
    assert perf.header_token("market / odds\nslow") == "market_odds_slow"
    assert " " not in perf.header_token("a b c")


def test_fastapi_middleware_exposes_grade_and_exact_inner_bottleneck(monkeypatch):
    monkeypatch.setenv("KYRE_PERF_SLOW_REQUEST_MS", "0")
    monkeypatch.setenv("KYRE_PERF_CRITICAL_REQUEST_MS", "999999")

    app = FastAPI()
    obs.install_observability(app)

    @app.get("/profile")
    async def profiled_route():
        with perf.span("api.fake_upstream", category="api"):
            time.sleep(0.003)
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/profile")

    assert response.status_code == 200
    assert response.headers["X-Kyre-Perf-Grade"] == "SLOW"
    assert response.headers["X-Kyre-Perf-Bottleneck"] == "api.fake_upstream"
    assert float(response.headers["X-Kyre-Duration-Ms"]) >= 0.0


def test_streamlit_entrypoint_consumes_existing_profiler_snapshots():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    obs_source = (ROOT / "sports_api" / "observability_v1.py").read_text(encoding="utf-8")

    assert 'st.session_state.get("cfb_ou_perf_v1_last")' in app_source
    assert 'st.session_state.get("cfb_ou_cold_start_v1_last")' in app_source
    assert 'st.session_state["monster_performance_profiler_v1_last"]' in app_source
    assert "⚡ Monster Performance Diagnosis" in app_source
    assert "X-Kyre-Perf-Grade" in obs_source
    assert "X-Kyre-Perf-Bottleneck" in obs_source

    # Step 2 must preserve the certified active router/page contract rather than
    # rewriting frozen CFB behavior.
    assert "from streamlit_memory_lazy_router_v77 import record_bootstrap_import_ms, render_app" in app_source
    assert "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11" in app_source
    assert 'OBSERVABILITY_VERSION = "KYRE_OBSERVABILITY_V1"' in obs_source
