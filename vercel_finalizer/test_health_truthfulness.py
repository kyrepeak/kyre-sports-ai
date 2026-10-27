from fastapi.testclient import TestClient

import app as target


def test_health_reports_degraded_when_authority_configuration_is_missing(monkeypatch):
    for key in (
        "GITHUB_APP_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_PRIVATE_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    response = TestClient(target.app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["status"] == "degraded"
