"""Compatibility surface for the Kyre NBA enrichment router."""
from __future__ import annotations

import re

from . import nba_pra_enrichment_core_v1 as _core
from .nba_pra_enrichment_core_v1 import *  # noqa: F401,F403


def _resolve_search_slug(player_name: str, search_html: str) -> str:
    wanted = _core._norm(player_name)
    for match in re.finditer(
        r"<a[^>]+href=[\"']/players/[a-z]/([a-z0-9]+)\.html[\"'][^>]*>(.*?)</a>",
        search_html,
        flags=re.I | re.S,
    ):
        label = _core._strip_html(match.group(2))
        # Search results append career years, e.g. "Devin Booker (2016-2026)".
        label = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", label)
        if _core._norm(label) == wanted:
            return match.group(1)
    return ""


# Patch the resolver used by the already-registered route without duplicating
# transport or provider logic.
_core._resolve_bref_slug = _resolve_search_slug
