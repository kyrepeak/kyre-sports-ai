"""CFB Game Total Page 2 — network-free verified-data presentation bridge.

Consumes only evidence already loaded by Page 1. It never starts a provider
request from the selected Page-2 render path and never mutates model truth.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from statistics import fmean
from threading import RLock
from typing import Any

import cfb_game_total_page2_live_data_unified_repair_v1 as prior

MODEL_VERSION = "MONSTER CFB PAGE2 NETWORK-FREE DATA BRIDGE V2"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_NETWORK_FREE_V2_ACTIVE"
NETWORK_CALLS_ADDED = 0
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_LOCK = RLock()
page2_runtime = prior.page2_runtime


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    return prior._number(value)


def _official_row(profile: Mapping[str, Any], key: str) -> dict[str, Any]:
    stats = profile.get("official_stats")
    if not isinstance(stats, Mapping):
        return {}
    row = stats.get(key)
    return dict(row) if isinstance(row, Mapping) else {}


def _official_number(profile: Mapping[str, Any], key: str) -> float | None:
    row = _official_row(profile, key)
    for field in ("value_numeric", "value", "display_value", "stat"):
        value = _number(row.get(field))
        if value is not None:
            return value
    return None


def _red_zone_rate(profile: Mapping[str, Any]) -> float | None:
    for key in ("red_zone_rate", "red_zone_td_rate"):
        value = _number(profile.get(key))
        if value is not None:
            return value / 100.0 if value > 1.0 else value
    row = _official_row(profile, "red_zone")
    match = prior._SCORE_RE.search(str(row.get("display_value") or row.get("value") or ""))
    if not match:
        return None
    made, attempts = float(match.group(1)), float(match.group(2))
    return made / attempts if attempts > 0 and 0 <= made <= attempts else None


def _profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    explicit_allowed = _number(profile.get("recent_points_allowed_pg"))
    out = prior.normalize_profile_history(profile)
    if explicit_allowed is not None:
        out["points_allowed_pg"] = explicit_allowed
    elif _number(out.get("points_allowed_pg")) is None:
        prior._fill_number(out, "points_allowed_pg", out.get("points_allowed"))

    prior._fill_number(out, "plays_per_game", _official_number(out, "plays_per_game"))
    prior._fill_number(out, "yards_per_play", _official_number(out, "yards_per_play"))
    if _number(out.get("red_zone_rate")) is None and _number(out.get("red_zone_td_rate")) is None:
        rate = _red_zone_rate(out)
        if rate is not None:
            out["red_zone_rate"] = rate
    return out


def _already_verified_splits(raw: Mapping[str, Any]) -> dict[str, Any]:
    scoring = raw.get("scoring_breakdown")
    if not isinstance(scoring, Mapping):
        return {}
    keys = ("away_1h", "home_1h", "away_2h", "home_2h", "q1", "q2", "q3", "q4")
    return {key: value for key in keys if (value := _number(scoring.get(key))) is not None}


def enrich_preloaded_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten verified in-memory evidence for Page 2 without any network I/O."""
    out = deepcopy(dict(payload))
    away = _profile(_mapping(out.get("away")))
    home = _profile(_mapping(out.get("home")))
    raw = deepcopy(_mapping(out.get("raw")))

    if _number(raw.get("red_zone_finishing")) is None:
        rates = [value for value in (_red_zone_rate(away), _red_zone_rate(home)) if value is not None]
        if rates:
            raw["red_zone_finishing"] = float(fmean(rates))

    splits = _already_verified_splits(raw)
    if splits:
        raw["scoring_breakdown"] = splits

    prior._apply_favorable(raw, away, home)
    out["away"], out["home"], out["raw"] = away, home, raw
    return out


@contextmanager
def install_page2_live_data_repair():
    """Temporarily install the network-free payload adapter for selected Page 2."""
    with _LOCK:
        original = page2_runtime._live_payload

        def network_free_live_payload(raw, final, display_game, statuses, ready_count):
            return enrich_preloaded_payload(original(raw, final, display_game, statuses, ready_count))

        page2_runtime._live_payload = network_free_live_payload
        try:
            yield
        finally:
            page2_runtime._live_payload = original


__all__ = [
    "ACTIVE_MARKER",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_preloaded_payload",
    "install_page2_live_data_repair",
]
