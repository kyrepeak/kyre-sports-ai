from __future__ import annotations

from pathlib import Path


CERT = Path("devsystem/cfb_top_picks_nav_step3_public_cert_v1.py").read_text(encoding="utf-8")
WORKFLOW = Path(".github/workflows/cfb-top-picks-nav-step3-public-freeze-v1.yml").read_text(encoding="utf-8")


def test_step3_targets_current_public_host():
    assert 'PUBLIC_URL = "https://pickvault.streamlit.app"' in CERT


def test_step3_certifies_normal_navigation_not_query_only():
    assert 'normal app -> College Football -> Top Picks' in CERT
    assert 'CFB_TOP_PICKS_NAV_STEP3_PUBLIC_DROPDOWN_GREEN' in CERT
    assert 'CFB_TOP_PICKS_NAV_STEP3_PUBLIC_V5_ROUTE_GREEN' in CERT


def test_step3_freeze_markers_exist():
    assert 'CFB_TOP_PICKS_NAV_STEPS1_3_PUBLIC_GREEN' in CERT
    assert 'CFB_TOP_PICKS_NAV_STEPS1_3_FROZEN_GREEN' in CERT


def test_step3_workflow_runs_on_pr_and_main_push():
    assert "pull_request:" in WORKFLOW
    assert "push:" in WORKFLOW
    assert "branches: [main]" in WORKFLOW


def test_step3_resolves_public_option_portal_in_frame_or_page():
    assert "def _visible_options(page, frame" in CERT
    assert "for scope in (frame, page):" in CERT
    assert "def _click_option(page, frame, value: str)" in CERT
    assert "deadline = time.monotonic() + 20.0" in CERT
    assert "page.wait_for_timeout(250)" in CERT


def test_step3_waits_for_streamlit_query_sync():
    assert "def _assert_query(page, timeout_seconds: float = 15.0)" in CERT
    assert "page.wait_for_timeout(250)" in CERT
    assert "already-rendered V5 route" in CERT


def test_step3_public_query_is_telemetry_not_route_gate():
    assert "query = _query(page)" in CERT
    assert "URL query persistence is telemetry only" in CERT
    flow = CERT.split("def _attempt_normal_flow", 1)[1]
    assert "query = _assert_query(page)" not in flow
