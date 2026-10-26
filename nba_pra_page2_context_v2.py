'''NBA PRA Page 2 context V2 — verified role/availability enrichment.'''
from __future__ import annotations

from typing import Any, Mapping

from nba_pra_page2_context_v1 import build_page2_context as _build_page2_context_v1
from nba_pra_page2_data_completeness_v1 import enrich_role_availability_context


VERSION = "API2_NBA_PRA_PAGE2_CONTEXT_V2"


def build_page2_context(
    snapshot: Mapping[str, Any],
    selected_player_key: str,
    *,
    selected_quote: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = _build_page2_context_v1(
        snapshot,
        selected_player_key,
        selected_quote=selected_quote,
    )
    if context.get("state") not in {"ready", "line_moved"}:
        return context
    return enrich_role_availability_context(context, snapshot)
