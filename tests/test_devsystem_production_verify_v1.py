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


def test_production_browser_contract_matches_certified_v30_ui():
    module = _load_module()

    assert module.REQUIRED_SPORTS == (
        "MLB",
        "WNBA",
        "NFL",
        "College Football",
    )
    assert module.CFB_SPORT == "College Football"
    assert module.CFB_MARKET == "Over/Under"
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "FUTURE SLATE COVERAGE ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "OFFICIAL ESPN IDENTITY RECOVERY" in module.CFB_REQUIRED_MARKERS
    assert "NO FUZZY MATCHING" in module.CFB_REQUIRED_MARKERS
    assert "NO SYNTHETIC IDS" in module.CFB_REQUIRED_MARKERS
    assert "FRESHNESS FIREWALL ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "0.0% PROJECTION INFLUENCE" in module.CFB_REQUIRED_MARKERS
    assert "FROZEN PROJECTION MATH PRESERVED" in module.CFB_REQUIRED_MARKERS
    assert "READABLE STEPS 4-12 ACTIVE" in module.CFB_REQUIRED_MARKERS
    assert "STEP 5C MARKET INTELLIGENCE LIVE" not in module.CFB_REQUIRED_MARKERS


def test_production_verifier_requires_observability_identity_contract():
    module = _load_module()

    assert module.OBSERVABILITY_VERSION == "KYRE_OBSERVABILITY_V1"
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert 'api_base + "/health/ready"' in source
    assert 'api_base + "/health/details"' in source
    assert "expected_runtime_branch" in source
    assert "render_deploy_commit" in source
    assert 'debug_contract.get("request_id_header") != "X-Request-ID"' in source
    assert 'debug_contract.get("error_fingerprint_field") != "error_fingerprint"' in source


def test_production_runtime_error_detector():
    module = _load_module()

    assert module._body_has_forbidden_error("everything healthy") is None
    assert module._body_has_forbidden_error(
        "SyntaxError: invalid syntax"
    ) == "SyntaxError:"
