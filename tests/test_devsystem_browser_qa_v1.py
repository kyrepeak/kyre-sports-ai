from __future__ import annotations

import importlib.util
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
    assert "CFB O/U • CLEAN PAGE V20 ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "STEP 6 MARKET INTELLIGENCE LIVE" in module.CFB_REQUIRED_MARKERS
    assert "FRESHNESS FIREWALL ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "0.0% PROJECTION INFLUENCE" in module.CFB_REQUIRED_MARKERS
    assert "FROZEN PROJECTION MATH PRESERVED" in module.CFB_REQUIRED_MARKERS
    assert "READABLE STEP 9 GAME-DAY ENVIRONMENT ACTIVE" in module.CFB_REQUIRED_MARKERS


def test_runtime_error_detector_fails_on_obvious_python_errors():
    module = _load_module()

    assert module._body_has_forbidden_error("all good") is None
    assert module._body_has_forbidden_error(
        "ModuleNotFoundError: no module named x"
    ) == "ModuleNotFoundError"
