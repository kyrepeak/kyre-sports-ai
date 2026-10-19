"""Exact NBA team identity helpers for the Spread decision board."""
from __future__ import annotations

NBA_TRICODES = frozenset({
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
})


def resolve_nba_team_logo(tricode: str) -> str | None:
    code = str(tricode or "").strip().upper()
    if code not in NBA_TRICODES:
        return None
    return f"https://a.espncdn.com/i/teamlogos/nba/500/{code.lower()}.png"


__all__ = ["NBA_TRICODES", "resolve_nba_team_logo"]
