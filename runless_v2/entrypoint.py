from __future__ import annotations

if __package__:
    from .app import app as _app
    from .vercel_oidc_bridge import install_vercel_oidc_header_bridge
else:
    from app import app as _app
    from vercel_oidc_bridge import install_vercel_oidc_header_bridge

app = install_vercel_oidc_header_bridge(_app)
