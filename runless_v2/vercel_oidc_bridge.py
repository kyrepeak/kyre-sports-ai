from __future__ import annotations

from typing import Any

from vercel.headers import HeadersContext


def install_vercel_oidc_header_bridge(app: Any) -> Any:
    if getattr(app.state, "_vercel_oidc_header_bridge_installed", False):
        return app

    @app.middleware("http")
    async def _bind_vercel_headers(request: Any, call_next: Any) -> Any:
        headers = {str(key): str(value) for key, value in request.headers.items()}
        with HeadersContext(headers).use():
            return await call_next(request)

    app.state._vercel_oidc_header_bridge_installed = True
    return app
