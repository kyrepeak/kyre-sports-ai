from __future__ import annotations

import app as _base

from vercel_finalizer.authority_bridge import (
    authority_bridge_health,
    claim_publication_via_bridge,
    complete_publication_via_bridge,
    resolve_authority_via_bridge,
)
from vercel_finalizer.bridge_runtime import install_bridge

_base.authority_bridge_health = authority_bridge_health
_base.claim_publication_via_bridge = claim_publication_via_bridge
_base.complete_publication_via_bridge = complete_publication_via_bridge
_base.resolve_authority_via_bridge = resolve_authority_via_bridge
install_bridge(_base.__dict__)

# bridge_runtime is intentionally generic, so restore the concrete Pydantic body
# annotation before FastAPI builds the final /prove dependency model.
_prove_route = next(
    route for route in _base.app.router.routes
    if getattr(route, "path", None) == "/prove"
)
_prove_endpoint = _prove_route.endpoint
_base.app.router.routes.remove(_prove_route)
_prove_endpoint.__annotations__["request"] = _base.ProveRequest
_base.app.add_api_route("/prove", _prove_endpoint, methods=["POST"])

app = _base.app
