from __future__ import annotations

from pathlib import Path

from sports_api import observability_v1 as obs

ROOT = Path(__file__).resolve().parents[1]


def test_observability_core_is_stable_secret_safe_and_release_aware(monkeypatch):
    first = obs.error_fingerprint(ValueError("one"), path="/health/details")
    second = obs.error_fingerprint(ValueError("two"), path="/health/details")
    assert first == second
    assert first.startswith("KYRE-")

    redacted = obs.sanitize_error_message("token=abc password=xyz api_key=secret")
    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "secret" not in redacted

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "mlb-step17b-shared-host-cert")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "release123")
    runtime = obs.runtime_metadata()
    assert runtime["canonical_source_branch"] == "main"
    assert runtime["expected_runtime_branch"] == "mlb-step17b-shared-host-cert"
    assert runtime["deploy_branch"] == "mlb-step17b-shared-host-cert"
    assert runtime["deploy_commit"] == "release123"
    assert runtime["branch_aligned"] is True


def test_release_entrypoint_installs_observability_without_replacing_runtime():
    source = (ROOT / "sports_api/main.py").read_text(encoding="utf-8")
    assert "from sports_api.observability_v1 import install_observability" in source
    assert "install_observability(app)" in source
    assert "lifespan=step17b_lifespan" in source
    assert '"health_ready": "/health/ready"' in source
    assert '"health_details": "/health/details"' in source


def test_release_health_preserves_cfb_hosted_transport_and_adds_diagnostics():
    source = (ROOT / "sports_api/api/health.py").read_text(encoding="utf-8")

    # Production-only CFB hosted transport / route handoff must survive exactly.
    assert "cfb_render_fanduel_transport_v1" in source
    assert "install_hosted_transport()" in source
    assert "router.routes.extend(cfb_markets_router.routes)" in source
    assert "router.routes.extend(cfb_market_identity_router.routes)" in source
    assert "router.routes.extend(cfb_odds_router.routes)" in source

    # Phase 1 diagnostics are additive around that frozen production handoff.
    assert "OBSERVABILITY_VERSION" in source
    assert '@router.get("/health")' in source
    assert '@router.get("/health/ready")' in source
    assert '@router.get("/health/details")' in source
    assert "runtime_metadata()" in source
    assert "readiness_snapshot()" in source
    assert "diagnostics_snapshot()" in source
