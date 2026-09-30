from __future__ import annotations

from pathlib import Path

import wnba_api_client_v1 as api


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "wnba_api_client_v1.py"
STEP2_PATH = ROOT / "wnba_pra_speed_v3_step2_transport.py"
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step2.py"
PUBLIC_PATH = ROOT / "devsystem" / "wnba_pra_speed_v3_step2_public_profile.py"
APP_PATH = ROOT / "app.py"


def test_step2_pooled_transport_surface_exists():
    assert STEP2_PATH.exists(), "Step-2 transport wrapper is missing"
    assert ROUTER_PATH.exists(), "Step-2 router is missing"
    assert PUBLIC_PATH.exists(), "Step-2 public proof is missing"


def test_step2_api_client_uses_one_persistent_https_session():
    source = CLIENT_PATH.read_text(encoding="utf-8")
    assert "HTTP_POOL_CONNECTIONS = 8" in source
    assert "HTTP_POOL_MAXSIZE = 16" in source
    assert "_HTTP_SESSION = requests.Session()" in source
    assert "_HTTP_SESSION.mount(" in source
    assert "_HTTP_SESSION.get(" in source
    assert "response = requests.get(" not in source


def test_step2_pool_adapter_has_bounded_pool_and_no_hidden_retries():
    assert api.HTTP_POOL_CONNECTIONS == 8
    assert api.HTTP_POOL_MAXSIZE == 16
    adapter = api._HTTP_SESSION.get_adapter("https://")
    assert adapter._pool_connections == 8
    assert adapter._pool_maxsize == 16
    assert adapter.max_retries.total == 0


def test_step2_get_json_uses_shared_session_without_changing_request_contract():
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"status": "ok"}

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse()

    fake = FakeSession()
    original = api._HTTP_SESSION
    api._HTTP_SESSION = fake
    try:
        client = api.KyreWNBAAPIClient(timeout_seconds=5.0, attempts=1)
        body = client.get_json("/health", params={"probe": "1"})
    finally:
        api._HTTP_SESSION = original

    assert body == {"status": "ok"}
    assert len(fake.calls) == 1
    url, kwargs = fake.calls[0]
    assert url == "https://kyre-sports-api.onrender.com/health"
    assert kwargs["params"] == {"probe": "1"}
    assert kwargs["headers"]["accept"] == "application/json"
    assert kwargs["headers"]["user-agent"] == "kyre-sports-ai-streamlit-step7f/1"
    assert kwargs["timeout"] == 5.0
    assert kwargs["allow_redirects"] is True


def test_step2_layers_over_frozen_step1_and_exposes_deployment_marker():
    step2 = STEP2_PATH.read_text(encoding="utf-8")
    router = ROUTER_PATH.read_text(encoding="utf-8")
    assert 'data-wnba-pra-speed-v3-step2="pooled-http"' in step2
    assert '"projection_math_changed": False' in step2
    assert '"market_math_changed": False' in step2
    assert '"sportsbook_projection_influence": 0.0' in step2
    assert '"network_reads_added": 0' in step2
    assert "import streamlit_memory_lazy_router_wnba_pra_speed_v3_step1 as frozen_step1" in router
    assert "import wnba_pra_speed_v3_step1_profiler as profiler" in router
    assert "transport.render_step2_route" in router
    assert "MAY_MODIFY_WNBA_MODEL = False" in router


def test_app_activates_step2_and_keeps_step1_compatibility():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step2 import record_bootstrap_import_ms, render_app" in source
    assert "Frozen WNBA PRA Speed V3 Step 1 compatibility" in source


def test_step2_full_redeploy_closeout_contract():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "wnba-pra-speed-v3-step2-pooled-http.yml").read_text(encoding="utf-8")
    verifier = PUBLIC_PATH.read_text(encoding="utf-8")

    assert "# WNBA PRA Speed V3 Step 2 control-plane full-redeploy trigger 2026-09-30 R1" in requirements
    assert "DEPLOYMENT_WAIT_SECONDS = 600.0" in verifier
    assert '- "requirements.txt"' in workflow


def test_step2_public_profile_uses_step2_local_parser_for_nested_timing():
    verifier = PUBLIC_PATH.read_text(encoding="utf-8")
    assert "def _step2_profile(" in verifier
    assert "profile = _step2_profile(marker)" in verifier
    assert "    _profile,\n" not in verifier
    assert "Profiler loader timing exceeds total render" not in verifier
