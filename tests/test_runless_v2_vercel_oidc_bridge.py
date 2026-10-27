from fastapi import FastAPI
from fastapi.testclient import TestClient
from vercel.headers import get_headers

from runless_v2.vercel_oidc_bridge import install_vercel_oidc_header_bridge


def test_vercel_oidc_header_is_bound_only_for_request_scope():
    app = FastAPI()
    install_vercel_oidc_header_bridge(app)

    @app.get("/probe")
    def probe():
        headers = get_headers() or {}
        return {"oidc": headers.get("x-vercel-oidc-token")}

    assert get_headers() is None
    with TestClient(app) as client:
        response = client.get("/probe", headers={"x-vercel-oidc-token": "opaque-test-token"})
    assert response.status_code == 200
    assert response.json() == {"oidc": "opaque-test-token"}
    assert get_headers() is None


def test_bridge_install_is_idempotent():
    app = FastAPI()
    first = install_vercel_oidc_header_bridge(app)
    second = install_vercel_oidc_header_bridge(app)
    assert first is app
    assert second is app
    assert app.state._vercel_oidc_header_bridge_installed is True
