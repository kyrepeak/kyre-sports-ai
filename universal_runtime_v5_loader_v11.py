"""Current-main CFB Top Picks V11 overlay for Universal Runtime V5."""
from __future__ import annotations

import universal_runtime_v5_loader as prior
from universal_runtime_v5_loader import choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "top-picks":
        return prior._cfb_page_adapter(route, "cfb_top_picks_page_v11", ttl_ms=30_000)
    return prior.resolve_destination(route)


__all__ = ["choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
