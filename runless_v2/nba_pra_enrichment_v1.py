"""Compatibility surface for the Kyre NBA enrichment router."""
from __future__ import annotations

import re

from . import nba_pra_enrichment_core_v1 as _core
from .nba_pra_enrichment_core_v1 import *  # noqa: F401,F403

_TEAM_ALIASES = {"PHO": "PHX", "BRK": "BKN", "CHO": "CHA"}


def _resolve_search_slug(player_name: str, search_html: str) -> str:
    wanted = _core._norm(player_name)
    for match in re.finditer(
        r"<a[^>]+href=[\"']/players/[a-z]/([a-z0-9]+)\.html[\"'][^>]*>(.*?)</a>",
        search_html,
        flags=re.I | re.S,
    ):
        label = _core._strip_html(match.group(2))
        label = re.sub(r"\s*\(\d{4}-\d{4}\)\s*$", "", label)
        if _core._norm(label) == wanted:
            return match.group(1)
    return ""


_original_extract_profile = _core._extract_bref_profile


def _extract_profile(document: str, slug: str, expected_name: str):
    profile = _original_extract_profile(document, slug, expected_name)
    team = str(profile.get("team") or "").upper()
    profile["team"] = _TEAM_ALIASES.get(team, team)
    return profile


_core._resolve_bref_slug = _resolve_search_slug
_core._extract_bref_profile = _extract_profile
