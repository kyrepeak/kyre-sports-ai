from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "production_verify_v1.py"
    spec = importlib.util.spec_from_file_location("devsystem_production_verify_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_target_registry_is_explicit():
    module = _load_module()
    targets = module._load_targets()

    assert targets["streamlit"]["url"] == "https://kyre-sports-ai.streamlit.app"
    assert targets["render_api"]["url"] == "https://kyre-sports-api.onrender.com"
    assert targets["render_api"]["service_id"] == "srv-da84q6ifngtc73bdbm6g"
    assert targets["render_api"]["source_branch"] == "mlb-step17b-shared-host-cert"
    assert targets["render_api"]["auto_deploy"] is False
    assert targets["contracts"]["cfb_projection_weight"] == 0.0


def test_production_browser_contract_matches_certified_ui():
    module = _load_module()

    assert module.REQUIRED_SPORTS == (
        "MLB",
        "WNBA",
        "NFL",
        "College Football",
    )
    assert module.CFB_SPORT == "College Football"
    assert module.CFB_MARKET == "Over/Under"
    assert "CFB O/U • CLEAN PAGE V18 ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "FROZEN PROJECTION MATH PRESERVED" in module.CFB_REQUIRED_MARKERS


def test_production_runtime_error_detector():
    module = _load_module()

    assert module._body_has_forbidden_error("everything healthy") is None
    assert module._body_has_forbidden_error(
        "SyntaxError: invalid syntax"
    ) == "SyntaxError:"
