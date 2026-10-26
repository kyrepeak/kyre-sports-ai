from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "runless_v2" / "api2_step2g_convergence_v1.py"
CERT_PATH = ROOT / "devsystem" / "api2_step2g_streamlit_cert_v1.py"
ENFORCEMENT_PATH = ROOT / "runless_v2" / "api2_step2g_closeout_enforcement_v1.py"
AUTHORITY_PATH = ROOT / "runless_v2" / "api2_step2g_github_authority_v1.py"
INIT_PATH = ROOT / "runless_v2" / "__init__.py"
STREAMLIT_APP_PATH = ROOT / "app.py"
PRODUCTION_TARGETS = ROOT / "devsystem" / "production_targets_v1.json"


def _load(path: Path, name: str):
    assert path.is_file(), f"Step 2G implementation missing: {path.relative_to(ROOT)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(ch: str) -> str:
    return ch * 40


def _digest(ch: str) -> str:
    return "sha256:" + ch * 64


def _evidence() -> dict:
    artifacts = {
        "universal_runtime_v5_loader.py": _sha("1"),
        "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py": _sha("2"),
    }
    return {
        "version": "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1",
        "workstream": "api2-example",
        "freeze_token": "API2_EXAMPLE_FROZEN",
        "candidate_sha": _sha("a"),
        "merged_main_sha": _sha("b"),
        "proof_digest": _digest("c"),
        "approved_artifacts": artifacts,
        "main": {"branch": "main", "sha": _sha("b"), "artifacts": dict(artifacts)},
        "api2_main": {"branch": "api2-main", "sha": _sha("e"), "artifacts": dict(artifacts)},
        "streamlit": {
            "url": "https://pickvault.streamlit.app",
            "source_branch": "main",
            "live_render_verified": True,
            "required_markers": [
                "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1",
                "TOTAL PROJECTION ON",
            ],
            "observed_markers": [
                "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1",
                "TOTAL PROJECTION ON",
            ],
            "forbidden_markers_present": [],
            "body_sha256": "f" * 64,
            "observed_at_utc": "2026-10-26T06:30:00Z",
        },
    }


def test_step2g_module_exists_before_green():
    assert MODULE_PATH.is_file()


def test_step2g_accepts_feature_scoped_convergence_even_when_branch_shas_differ():
    mod = _load(MODULE_PATH, "step2g_contract")
    result = mod.validate_convergence_evidence(_evidence(), production_url="https://pickvault.streamlit.app")
    assert result["status"] == "GREEN"
    assert result["step2g_green"] is True
    assert result["green_frozen_allowed"] is True
    assert result["completion_percent"] == 100.0
    assert result["whole_branch_equality_required"] is False


def test_step2g_rejects_missing_or_stale_api2_main_artifact():
    mod = _load(MODULE_PATH, "step2g_contract_stale")
    evidence = _evidence()
    evidence["api2_main"]["artifacts"]["universal_runtime_v5_loader.py"] = _sha("9")
    with pytest.raises(mod.Step2GConvergenceFailure, match="API2_MAIN_ARTIFACT_DRIFT"):
        mod.validate_convergence_evidence(evidence, production_url="https://pickvault.streamlit.app")


def test_step2g_rejects_missing_or_stale_main_artifact():
    mod = _load(MODULE_PATH, "step2g_contract_main_stale")
    evidence = _evidence()
    del evidence["main"]["artifacts"]["universal_runtime_v5_loader.py"]
    with pytest.raises(mod.Step2GConvergenceFailure, match="MAIN_ARTIFACT_DRIFT"):
        mod.validate_convergence_evidence(evidence, production_url="https://pickvault.streamlit.app")


def test_step2g_rejects_streamlit_without_live_markers():
    mod = _load(MODULE_PATH, "step2g_contract_streamlit")
    evidence = _evidence()
    evidence["streamlit"]["observed_markers"] = ["API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"]
    with pytest.raises(mod.Step2GConvergenceFailure, match="STREAMLIT_REQUIRED_MARKER_MISSING"):
        mod.validate_convergence_evidence(evidence, production_url="https://pickvault.streamlit.app")


def test_step2g_rejects_auth_wall_or_runtime_failure_marker():
    mod = _load(MODULE_PATH, "step2g_contract_forbidden")
    evidence = _evidence()
    evidence["streamlit"]["forbidden_markers_present"] = ["Sign in"]
    with pytest.raises(mod.Step2GConvergenceFailure, match="STREAMLIT_FORBIDDEN_MARKER"):
        mod.validate_convergence_evidence(evidence, production_url="https://pickvault.streamlit.app")


def test_step2g_rejects_sidecar_identity_drift():
    mod = _load(MODULE_PATH, "step2g_contract_identity")
    evidence = _evidence()
    expected = {
        "workstream": "api2-example",
        "freeze_token": "API2_EXAMPLE_FROZEN",
        "candidate_sha": _sha("a"),
        "merged_main_sha": _sha("b"),
        "proof_digest": _digest("c"),
        "approved_artifacts": evidence["approved_artifacts"],
    }
    evidence["candidate_sha"] = _sha("8")
    with pytest.raises(mod.Step2GConvergenceFailure, match="SIDECAR_IDENTITY_DRIFT"):
        mod.require_step2g_closeout(evidence, expected=expected, production_url="https://pickvault.streamlit.app")


def test_streamlit_cert_evaluates_required_and_forbidden_markers():
    cert = _load(CERT_PATH, "step2g_cert")
    result = cert.evaluate_rendered_body(
        "hello API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1 TOTAL PROJECTION ON",
        required_markers=["API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1", "TOTAL PROJECTION ON"],
    )
    assert result["live_render_verified"] is True
    assert result["forbidden_markers_present"] == []
    with pytest.raises(cert.Step2GStreamlitCertificationFailure, match="FORBIDDEN_MARKER"):
        cert.evaluate_rendered_body(
            "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1 Traceback",
            required_markers=["API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"],
        )


def test_streamlit_cert_reads_only_canonical_production_target():
    cert = _load(CERT_PATH, "step2g_cert_target")
    payload = json.loads(PRODUCTION_TARGETS.read_text(encoding="utf-8"))
    assert cert.production_base_url() == payload["streamlit"]["url"].rstrip("/")


def test_step2g_github_readback_requires_branch_specific_integration_markers():
    authority = AUTHORITY_PATH.read_text(encoding="utf-8")
    assert "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1" in authority
    assert '"app.py"' in authority
    assert '"runless_v2/__init__.py"' in authority
    assert "STEP2G_BRANCH_INTEGRATION_MARKER_MISSING" in authority
    assert '_verify_branch_integration(self, "main")' in authority
    assert '_verify_branch_integration(self, "api2-main")' in authority


def test_runless_closeout_permanently_invokes_step2g_for_api2_only():
    enforcement = ENFORCEMENT_PATH.read_text(encoding="utf-8")
    authority = AUTHORITY_PATH.read_text(encoding="utf-8")
    init_source = INIT_PATH.read_text(encoding="utf-8")
    streamlit_app = STREAMLIT_APP_PATH.read_text(encoding="utf-8")
    assert "require_api2_step2g_closeout" in enforcement
    assert 'workstream.startswith("api2-")' in enforcement
    assert "DurableStateStore.closeout_green_frozen = closeout_green_frozen_with_step2g" in enforcement
    assert "read_step2g_convergence_evidence" in authority
    assert "api2-step2g-convergence-evidence" in authority
    assert "api2_step2g_closeout_enforcement_v1" in init_source
    assert "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1" in streamlit_app
