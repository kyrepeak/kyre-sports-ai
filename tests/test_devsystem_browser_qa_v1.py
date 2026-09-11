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
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "FUTURE SLATE COVERAGE ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "OFFICIAL ESPN IDENTITY RECOVERY" in module.CFB_REQUIRED_MARKERS
    assert "NO FUZZY MATCHING" in module.CFB_REQUIRED_MARKERS
    assert "NO SYNTHETIC IDS" in module.CFB_REQUIRED_MARKERS
    assert "STEP 5C MARKET INTELLIGENCE LIVE" not in module.CFB_REQUIRED_MARKERS
    assert "FRESHNESS FIREWALL ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "0.0% PROJECTION INFLUENCE" in module.CFB_REQUIRED_MARKERS
    assert "FROZEN PROJECTION MATH PRESERVED" in module.CFB_REQUIRED_MARKERS
    assert "READABLE STEPS 4-12 ACTIVE" in module.CFB_REQUIRED_MARKERS


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
    assert 'state="visible"' in run_source
    assert module.SELECTOR_TIMEOUT_MS == 5000
    assert module.CFB_RERUN_TIMEOUT_MS == 30000
