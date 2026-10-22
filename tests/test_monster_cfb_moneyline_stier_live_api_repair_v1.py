from pathlib import Path

from fastapi.testclient import TestClient


def test_dedicated_kyre_sports_api_entrypoint_is_root_scoped_and_cfb_only():
    entry = Path("kyre_sports_api_vercel_v1.py")
    config = Path("pyproject.toml")
    assert entry.is_file()
    assert config.is_file()
    source = entry.read_text()
    pyproject = config.read_text()
    assert "FastAPI" in source
    assert "sports_api.api.cfb_moneyline_page1_v1" in source
    assert "app.include_router(cfb_moneyline_router)" in source
    assert "service\": \"Kyre Sports API" in source
    assert "runless_v2" not in source
    assert "espn" not in source.casefold()
    assert "sportsgameodds" not in source.casefold()
    assert "[project]" in pyproject
    assert 'name = "kyre-sports-api"' in pyproject
    for dependency in ("fastapi", "streamlit", "requests", "httpx", "tzdata"):
        assert f'"{dependency}' in pyproject
    assert "entrypoint = \"kyre_sports_api_vercel_v1:app\"" in pyproject


def test_runless_proof_service_no_longer_hosts_cfb_moneyline_bridge():
    schedule = Path("runless_v2/wnba_schedule_v1.py").read_text()
    assert "cfb_moneyline_public_v1" not in schedule
    assert not Path("runless_v2/cfb_moneyline_public_v1.py").exists()


def test_dedicated_gateway_health_and_page_contract(monkeypatch):
    import kyre_sports_api_vercel_v1 as gateway

    payload = {
        "service": "Kyre Sports API",
        "games": [],
        "routing": {"consensus_averaging": False},
    }
    monkeypatch.setattr(gateway.cfb_moneyline_module, "build_page1_payload", lambda **_: payload)
    client = TestClient(gateway.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "Kyre Sports API"
    assert health.json()["direct_app_provider_fallback"] is False
    response = client.get("/api/v1/cfb/moneyline/page1")
    assert response.status_code == 200
    assert response.json() == payload
