from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "devsystem" / "production_verify_v1.py"
    spec = importlib.util.spec_from_file_location("devsystem_production_verify_v1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def get(self, url, *, params=None, timeout=None, **kwargs):
        self.requests.append((url, params, timeout, kwargs))
        if url not in self.responses:
            raise AssertionError(f"unexpected request: {url}")
        return self.responses[url]


def _cfb_status():
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 3,
        "model_version": "CFB ODDS API V1 • ODDS INTEGRATION STEP 3",
        "schema_version": "cfb_odds_v1",
        "endpoint_ready": True,
        "endpoint": "/api/v1/cfb/odds",
        "consumer": "Streamlit / Kyre Sports AI",
        "market_scope": ["game_total"],
        "identity_required": True,
        "identity_policy": {
            "synthetic_ids": False,
            "fuzzy_matching": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def _cfb_odds():
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "games": [
            {
                "game_id": "401858213",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "identity_verified": True,
            }
        ],
        "diagnostics": {
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def _api_responses(module, api_base="https://api.example"):
    branch = "mlb-step17b-shared-host-cert"
    commit = "certified-render-commit"
    return {
        api_base + "/health": _FakeResponse(
            200,
            {
                "status": "ok",
                "service": "kyre-sports-api",
                "observability_version": module.OBSERVABILITY_VERSION,
                "deployment": {
                    "branch": branch,
                    "branch_aligned": True,
                    "commit": commit,
                },
            },
        ),
        api_base + "/health/ready": _FakeResponse(
            200,
            {
                "status": "ready",
                "observability_version": module.OBSERVABILITY_VERSION,
                "deployment": {
                    "branch": branch,
                    "aligned": True,
                    "commit": commit,
                },
            },
        ),
        api_base + "/health/details": _FakeResponse(
            200,
            {
                "status": "ok",
                "observability_version": module.OBSERVABILITY_VERSION,
                "runtime": {
                    "deploy_branch": branch,
                    "deploy_commit": commit,
                    "branch_aligned": True,
                },
                "debug_contract": {
                    "request_id_header": "X-Request-ID",
                    "error_fingerprint_field": "error_fingerprint",
                },
            },
        ),
        api_base + "/": _FakeResponse(
            200,
            {
                "name": "Kyre Sports API",
                "status": "online",
                "health_ready": "/health/ready",
                "health_details": "/health/details",
            },
        ),
        api_base + module.CFB_ODDS_STATUS_PATH: _FakeResponse(200, _cfb_status()),
        api_base + "/api/v1/cfb/odds": _FakeResponse(200, _cfb_odds()),
    }


def _validate(module, responses, api_base="https://api.example"):
    return module._validate_api_contract(
        _FakeSession(responses),
        api_base,
        "/api/v1/cfb/odds",
        "mlb-step17b-shared-host-cert",
    )


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


def test_cfb_complete_200_still_requires_full_safe_contract():
    module = _load_module()
    responses = _api_responses(module)

    result = _validate(module, responses)

    assert result["cfb_status_http"] == 200
    assert result["cfb_odds_http"] == 200
    assert result["cfb_odds_state"] == "complete"
    assert result["cfb_game_count"] == 1
    assert result["cfb_projection_weight"] == 0.0
    assert result["cfb_fuzzy_matching"] is False
    assert result["cfb_synthetic_official_ids"] is False
    assert result["cfb_fail_closed"] is True


def test_cfb_exact_incomplete_identity_503_is_accepted_only_as_protected_fail_closed():
    module = _load_module()
    responses = _api_responses(module)
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        503,
        {"detail": module.CFB_INCOMPLETE_IDENTITY_DETAIL},
    )

    result = _validate(module, responses)

    assert result["cfb_status_http"] == 200
    assert result["cfb_odds_http"] == 503
    assert result["cfb_odds_state"] == "protected-fail-closed"
    assert result["cfb_odds_detail"] == module.CFB_INCOMPLETE_IDENTITY_DETAIL
    assert result["cfb_game_count"] is None
    assert result["cfb_projection_weight"] == 0.0
    assert result["cfb_fuzzy_matching"] is False
    assert result["cfb_synthetic_official_ids"] is False
    assert result["cfb_fail_closed"] is True


def test_cfb_503_with_any_other_detail_remains_hard_failure():
    module = _load_module()
    responses = _api_responses(module)
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        503,
        {"detail": "database unavailable"},
    )

    with pytest.raises(
        module.ProductionVerificationFailure,
        match="unrecognized HTTP 503 detail",
    ):
        _validate(module, responses)


def test_cfb_other_5xx_remains_hard_failure():
    module = _load_module()
    responses = _api_responses(module)
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        500,
        {"detail": module.CFB_INCOMPLETE_IDENTITY_DETAIL},
    )

    with pytest.raises(
        module.ProductionVerificationFailure,
        match="unexpected HTTP 500",
    ):
        _validate(module, responses)


def test_cfb_malformed_503_body_remains_hard_failure():
    module = _load_module()
    responses = _api_responses(module)
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        503,
        ValueError("not json"),
    )

    with pytest.raises(
        module.ProductionVerificationFailure,
        match="Expected JSON object.*HTTP 503",
    ):
        _validate(module, responses)


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("identity_policy", "fuzzy_matching", True, "fuzzy matching became enabled"),
        ("identity_policy", "synthetic_ids", True, "synthetic official IDs became enabled"),
        ("identity_policy", "fail_closed", False, "fail-closed identity policy became disabled"),
        ("market_semantics", "projection_weight", 0.01, "projection weight is not 0%"),
        ("market_semantics", "may_modify_projection", True, "market can modify projection"),
    ],
)
def test_cfb_status_safety_drift_hard_fails_before_allowed_503(
    section,
    key,
    value,
    message,
):
    module = _load_module()
    responses = _api_responses(module)
    unsafe = copy.deepcopy(_cfb_status())
    unsafe[section][key] = value
    responses["https://api.example" + module.CFB_ODDS_STATUS_PATH] = _FakeResponse(
        200,
        unsafe,
    )
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        503,
        {"detail": module.CFB_INCOMPLETE_IDENTITY_DETAIL},
    )

    with pytest.raises(module.ProductionVerificationFailure, match=message):
        _validate(module, responses)


def test_cfb_status_schema_drift_hard_fails_before_allowed_503():
    module = _load_module()
    responses = _api_responses(module)
    bad_status = copy.deepcopy(_cfb_status())
    bad_status["schema_version"] = "unexpected"
    responses["https://api.example" + module.CFB_ODDS_STATUS_PATH] = _FakeResponse(
        200,
        bad_status,
    )
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(
        503,
        {"detail": module.CFB_INCOMPLETE_IDENTITY_DETAIL},
    )

    with pytest.raises(module.ProductionVerificationFailure, match="status schema drift"):
        _validate(module, responses)


def test_cfb_200_unsafe_market_contract_still_hard_fails():
    module = _load_module()
    responses = _api_responses(module)
    unsafe_odds = copy.deepcopy(_cfb_odds())
    unsafe_odds["market_semantics"]["projection_weight"] = 0.01
    responses["https://api.example/api/v1/cfb/odds"] = _FakeResponse(200, unsafe_odds)

    with pytest.raises(module.ProductionVerificationFailure, match="projection weight is not 0%"):
        _validate(module, responses)
