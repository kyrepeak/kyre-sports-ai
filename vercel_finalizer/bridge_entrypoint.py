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

app = _base.app
