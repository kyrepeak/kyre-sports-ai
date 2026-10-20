"""Pure helpers for Universal Atomic Navigation V1."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "MONSTER UNIVERSAL ATOMIC NAVIGATION V1"


def route_identity(route: Any) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Return the canonical visual destination identity for a route-like object."""
    sport_id = str(getattr(route, "sport_id", "") or "").strip().lower()
    market_id = str(getattr(route, "market_id", "") or "").strip().lower()
    raw_params = getattr(route, "params", {}) or {}
    params: Mapping[Any, Any] = raw_params if isinstance(raw_params, Mapping) else {}
    canonical_params = tuple(sorted((str(key), str(value)) for key, value in params.items()))
    return sport_id, market_id, canonical_params


def is_route_transition(before: Any | None, after: Any | None) -> bool:
    """True only when an already-rendered destination changes identity."""
    if before is None or after is None:
        return False
    return route_identity(before) != route_identity(after)


def transition_markup(route: Any) -> str:
    """Opaque, pointer-blocking loading surface for a destination handoff."""
    sport_id, market_id, _ = route_identity(route)
    sport = escape((sport_id or "sports").replace("-", " ").upper())
    market = escape((market_id or "page").replace("-", " ").upper())
    return f"""
<div data-kyre-atomic-transition="v1" style="
    position:fixed; inset:0; z-index:900;
    background:#070b12; pointer-events:all;
    display:grid; place-items:center; min-height:100vh;
">
  <div style="text-align:center;padding:1.25rem 1.5rem;max-width:32rem;color:#f8fafc;">
    <div style="font-size:.78rem;font-weight:900;letter-spacing:.16em;opacity:.82;">KYRE SPORTS AI</div>
    <div style="font-size:1.25rem;font-weight:900;margin-top:.6rem;">Loading {sport} {market}</div>
    <div style="font-size:.86rem;opacity:.62;margin-top:.4rem;">Preparing the selected analytics page…</div>
  </div>
</div>
""".strip()


__all__ = ["MODEL_VERSION", "is_route_transition", "route_identity", "transition_markup"]
