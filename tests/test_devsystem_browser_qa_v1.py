from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "browser_qa_v1.py"
    spec = importlib.util.spec_from_file_location("devsystem_browser_qa_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_browser_qa_contract_is_explicit_and_safe():
    module = _load_module()

    assert module.REQUIRED_SPORTS == (
        "MLB",
        "WNBA",
        "NFL",
        "College Football",
    )
    assert module.CFB_SPORT == "College Football"
    assert module.CFB_MARKET == "Over/Under"
    assert module.CFB_MARKET_LABEL == "🎯 CFB Market"

    markers = module.CFB_REQUIRED_MARKERS
    assert "CFB O/U • CLEAN PAGE V39 ACTIVE" in markers
    assert "COMPACT EVIDENCE RENDERER" in markers
    assert "VERIFIED IDENTITY ≠ MISSING STEP METRIC" in markers
    assert "0.0% SPORTSBOOK PROJECTION INFLUENCE" in markers
    assert "Matchup Foundation" in markers
    assert "Steps 1–4 • compact verified evidence" in markers
    assert "Frozen O/U math • Mutation OFF • Sportsbook 0.0%" in markers
    assert "Step 5 • Explosive Plays" in markers
    assert "Step 10 • Historical Matchup" in markers
    assert "Steps 11–12 • current form + certification" in markers

    assert "CFB O/U • CLEAN PAGE V38 ACTIVE" not in markers
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" not in markers
    assert "FUTURE SLATE COVERAGE ACTIVE" not in markers
    assert "OFFICIAL ESPN IDENTITY RECOVERY" not in markers
    assert "NO FUZZY MATCHING" not in markers
    assert "NO SYNTHETIC IDS" not in markers
    assert "FRESHNESS FIREWALL ACTIVE" not in markers
    assert "FROZEN PROJECTION MATH PRESERVED" not in markers
    assert "READABLE STEPS 4-12 ACTIVE" not in markers


def test_runtime_error_detector_fails_on_obvious_python_errors():
    module = _load_module()

    assert module._body_has_forbidden_error("all good") is None
    assert module._body_has_forbidden_error(
        "ModuleNotFoundError: no module named x"
    ) == "ModuleNotFoundError"


def test_selector_helpers_are_readiness_driven_not_fixed_sleep_driven():
    module = _load_module()

    read_source = inspect.getsource(module._read_sport_options)
    choose_source = inspect.getsource(module._choose)
    run_source = inspect.getsource(module.run_browser_qa)

    assert "wait_for_timeout" not in read_source
    assert "wait_for_timeout" not in choose_source
    assert 'wait_for(state="visible"' in read_source
    assert 'page.keyboard.type(value)' in choose_source
    assert 'page.keyboard.press("Enter")' in choose_source
    assert "CFB_MARKET_LABEL" in run_source
    assert "CFB_RERUN_TIMEOUT_MS" in run_source
    assert "CFB_REQUIRED_MARKERS[-1]" in run_source
    assert "CFB_REQUIRED_MARKERS[0]" not in run_source
    assert 'state="visible"' in run_source
    assert module.SELECTOR_TIMEOUT_MS == 5000
    assert module.CFB_RERUN_TIMEOUT_MS == 30000


def test_cfb_marker_wait_is_event_driven_not_polling_driven():
    module = _load_module()

    wait_source = inspect.getsource(module._wait_for_text)

    assert 'get_by_text(text, exact=False).first' in wait_source
    assert 'wait_for(' in wait_source
    assert 'state="visible"' in wait_source
    assert 'wait_for_timeout' not in wait_source
    assert 'time.monotonic' not in wait_source
    assert 'while ' not in wait_source
    assert 'inner_text(timeout=5000)' in wait_source


def test_browser_qa_enters_cfb_over_under_through_certified_fast_route():
    module = _load_module()
    run_source = inspect.getsource(module.run_browser_qa)

    assert module._cfb_over_under_url("http://127.0.0.1:8501") == (
        "http://127.0.0.1:8501/?ks_sport=College+Football&ks_cfb_market=Over%2FUnder"
    )
    assert "page.goto(_cfb_over_under_url(base_url)" in run_source
    assert "_find_app_frame(page)" in run_source
    assert "_choose(page, frame, 0, CFB_SPORT)" not in run_source
    assert "_choose(page, frame, 1, CFB_MARKET)" not in run_source
