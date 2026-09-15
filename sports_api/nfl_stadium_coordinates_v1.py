"""Canonical NFL home-stadium registry for Game Totals environment routing.

The registry is intentionally small and static: team, canonical venue label,
coordinates, and a roof/indoor boolean used only when exact event metadata does
not already provide stronger venue truth. Shared-stadium teams intentionally
carry identical coordinates.
"""
from __future__ import annotations

from typing import Any

STADIUMS: tuple[dict[str, Any], ...] = (
    {"team": "ARI", "venue": "State Farm Stadium", "latitude": 33.5276, "longitude": -112.2626, "indoor": True},
    {"team": "ATL", "venue": "Mercedes-Benz Stadium", "latitude": 33.7554, "longitude": -84.4008, "indoor": True},
    {"team": "BAL", "venue": "M&T Bank Stadium", "latitude": 39.2780, "longitude": -76.6227, "indoor": False},
    {"team": "BUF", "venue": "Highmark Stadium", "latitude": 42.7738, "longitude": -78.7868, "indoor": False},
    {"team": "CAR", "venue": "Bank of America Stadium", "latitude": 35.2258, "longitude": -80.8528, "indoor": False},
    {"team": "CHI", "venue": "Soldier Field", "latitude": 41.8623, "longitude": -87.6167, "indoor": False},
    {"team": "CIN", "venue": "Paycor Stadium", "latitude": 39.0954, "longitude": -84.5160, "indoor": False},
    {"team": "CLE", "venue": "Huntington Bank Field", "latitude": 41.5061, "longitude": -81.6995, "indoor": False},
    {"team": "DAL", "venue": "AT&T Stadium", "latitude": 32.7473, "longitude": -97.0945, "indoor": True},
    {"team": "DEN", "venue": "Empower Field at Mile High", "latitude": 39.7439, "longitude": -105.0201, "indoor": False},
    {"team": "DET", "venue": "Ford Field", "latitude": 42.3400, "longitude": -83.0456, "indoor": True},
    {"team": "GB", "venue": "Lambeau Field", "latitude": 44.5013, "longitude": -88.0622, "indoor": False},
    {"team": "HOU", "venue": "NRG Stadium", "latitude": 29.6847, "longitude": -95.4107, "indoor": True},
    {"team": "IND", "venue": "Lucas Oil Stadium", "latitude": 39.7601, "longitude": -86.1639, "indoor": True},
    {"team": "JAX", "venue": "EverBank Stadium", "latitude": 30.3239, "longitude": -81.6373, "indoor": False},
    {"team": "KC", "venue": "GEHA Field at Arrowhead Stadium", "latitude": 39.0489, "longitude": -94.4839, "indoor": False},
    {"team": "LV", "venue": "Allegiant Stadium", "latitude": 36.0908, "longitude": -115.1830, "indoor": True},
    {"team": "LAC", "venue": "SoFi Stadium", "latitude": 33.9535, "longitude": -118.3392, "indoor": True},
    {"team": "LAR", "venue": "SoFi Stadium", "latitude": 33.9535, "longitude": -118.3392, "indoor": True},
    {"team": "MIA", "venue": "Hard Rock Stadium", "latitude": 25.9580, "longitude": -80.2389, "indoor": False},
    {"team": "MIN", "venue": "U.S. Bank Stadium", "latitude": 44.9736, "longitude": -93.2575, "indoor": True},
    {"team": "NE", "venue": "Gillette Stadium", "latitude": 42.0909, "longitude": -71.2643, "indoor": False},
    {"team": "NO", "venue": "Caesars Superdome", "latitude": 29.9511, "longitude": -90.0812, "indoor": True},
    {"team": "NYG", "venue": "MetLife Stadium", "latitude": 40.8135, "longitude": -74.0745, "indoor": False},
    {"team": "NYJ", "venue": "MetLife Stadium", "latitude": 40.8135, "longitude": -74.0745, "indoor": False},
    {"team": "PHI", "venue": "Lincoln Financial Field", "latitude": 39.9008, "longitude": -75.1675, "indoor": False},
    {"team": "PIT", "venue": "Acrisure Stadium", "latitude": 40.4468, "longitude": -80.0158, "indoor": False},
    {"team": "SEA", "venue": "Lumen Field", "latitude": 47.5952, "longitude": -122.3316, "indoor": False},
    {"team": "SF", "venue": "Levi's Stadium", "latitude": 37.4030, "longitude": -121.9700, "indoor": False},
    {"team": "TB", "venue": "Raymond James Stadium", "latitude": 27.9759, "longitude": -82.5033, "indoor": False},
    {"team": "TEN", "venue": "Nissan Stadium", "latitude": 36.1665, "longitude": -86.7713, "indoor": False},
    {"team": "WAS", "venue": "Northwest Stadium", "latitude": 38.9077, "longitude": -76.8645, "indoor": False},
)


def _norm(value: Any) -> str:
    return " ".join(str(value if value is not None else "").strip().lower().split())


def lookup_stadium(venue_name: str, home_abbr: str) -> dict[str, Any] | None:
    """Resolve a canonical stadium, preferring exact home-team identity."""
    team = str(home_abbr or "").strip().upper()
    if team:
        matches = [entry for entry in STADIUMS if entry["team"] == team]
        if len(matches) == 1:
            return dict(matches[0])

    venue = _norm(venue_name)
    if not venue:
        return None
    matches = [entry for entry in STADIUMS if _norm(entry["venue"]) == venue]
    if not matches:
        return None
    first = matches[0]
    if any(
        (entry["latitude"], entry["longitude"], entry["indoor"])
        != (first["latitude"], first["longitude"], first["indoor"])
        for entry in matches[1:]
    ):
        return None
    return dict(first)


__all__ = ["STADIUMS", "lookup_stadium"]
