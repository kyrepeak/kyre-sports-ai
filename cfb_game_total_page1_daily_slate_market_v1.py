"""CFB Game Total Page 1 — deterministic observed-market context V1.

This module is deliberately pure: no network calls, no model imports, and no
synthetic sportsbook prices. It deduplicates the same sportsbook across
transports, keeps opening/pregame/live phases separate, and selects one actual
observed quote nearest the median of independent verified observations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from statistics import median
from typing import Any, Mapping, Sequence

MODEL_VERSION = "CFB GAME TOTAL PAGE1 DAILY SLATE MARKET V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
FABRICATION = False

SPREAD_TOLERANCE = 0.5
GAME_TOTAL_TOLERANCE = 0.5
MONEYLINE_TOLERANCE = 15.0

_MARKETS = {"game_total", "spread", "moneyline"}
_PHASES = {"opening", "pregame", "live"}
_SIDES = {"home", "away"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _timestamp(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def normalize_market_observation(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, Mapping) or row.get("identity_verified") is not True:
        return None
    game_id = _clean(row.get("game_id"))
    sportsbook = _clean(row.get("sportsbook"))
    market_type = _clean(row.get("market_type")).casefold()
    phase = _clean(row.get("phase") or "pregame").casefold()
    if not game_id or not sportsbook or market_type not in _MARKETS or phase not in _PHASES:
        return None

    side = _clean(row.get("side")).casefold() or None
    if market_type == "moneyline" and side is not None and side not in _SIDES:
        return None

    value = _number(row.get("value"))
    if value is None:
        return None

    provider_id = _clean(row.get("provider_id") or sportsbook).casefold().replace(" ", "_")
    if not provider_id:
        return None
    observed = _timestamp(row.get("observed_at_utc"))
    return {
        "game_id": game_id,
        "sportsbook": sportsbook,
        "provider_id": provider_id,
        "market_type": market_type,
        "phase": phase,
        "side": side,
        "value": value,
        "home_value": _number(row.get("home_value")),
        "away_value": _number(row.get("away_value")),
        "observed_at_utc": observed.isoformat() if observed is not None else None,
        "transport": _clean(row.get("transport")) or "unknown",
        "provenance": _clean(row.get("provenance")) or None,
        "identity_verified": True,
        "fabrication": False,
    }


def _dedupe_independent(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for raw in rows:
        normalized = normalize_market_observation(raw)
        if normalized is None:
            continue
        key = normalized["sportsbook"].casefold()
        current = chosen.get(key)
        if current is None:
            chosen[key] = normalized
            continue
        current_time = _timestamp(current.get("observed_at_utc"))
        candidate_time = _timestamp(normalized.get("observed_at_utc"))
        if candidate_time is not None and (current_time is None or candidate_time > current_time):
            chosen[key] = normalized
        elif candidate_time == current_time:
            candidate_key = (normalized["provider_id"], normalized["transport"])
            current_key = (current["provider_id"], current["transport"])
            if candidate_key < current_key:
                chosen[key] = normalized
    return list(chosen.values())


def _freshness_rank(row: Mapping[str, Any]) -> float:
    parsed = _timestamp(row.get("observed_at_utc"))
    return parsed.timestamp() if parsed is not None else float("-inf")


def select_observed_consensus(
    rows: Sequence[Mapping[str, Any]], *, tolerance: float
) -> dict[str, Any]:
    independent = _dedupe_independent(rows)
    if not independent:
        return {
            "status": "UNAVAILABLE",
            "confidence": "Unavailable",
            "independent_source_count": 0,
            "selected_quote": None,
            "observations": [],
            "synthetic_value": False,
            "fabrication": False,
        }

    values = [float(row["value"]) for row in independent]
    center = float(median(values))
    selected = sorted(
        independent,
        key=lambda row: (
            abs(float(row["value"]) - center),
            -_freshness_rank(row),
            str(row["provider_id"]),
            str(row["sportsbook"]).casefold(),
        ),
    )[0]

    if len(independent) == 1:
        confidence = "Limited coverage"
    elif max(values) - min(values) <= float(tolerance):
        confidence = "Strong consensus"
    else:
        confidence = "Mixed market"

    return {
        "status": "VERIFIED",
        "confidence": confidence,
        "independent_source_count": len(independent),
        "selected_quote": dict(selected),
        "observations": sorted(
            (dict(row) for row in independent),
            key=lambda row: (str(row["sportsbook"]).casefold(), str(row["provider_id"])),
        ),
        "synthetic_value": False,
        "fabrication": False,
    }


def _expanded_rows(
    game_id: str, observations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for raw in observations:
        if not isinstance(raw, Mapping) or _clean(raw.get("game_id")) != game_id:
            continue
        if raw.get("identity_verified") is not True:
            continue
        market = _clean(raw.get("market_type")).casefold()
        if market == "moneyline" and not _clean(raw.get("side")):
            for side in ("home", "away"):
                value = _number(raw.get(f"{side}_value"))
                if value is None:
                    continue
                expanded.append({**dict(raw), "side": side, "value": value})
        else:
            expanded.append(dict(raw))
    return expanded


def _empty_phase() -> dict[str, dict[str, Any]]:
    unavailable = select_observed_consensus([], tolerance=GAME_TOTAL_TOLERANCE)
    return {
        "game_total": dict(unavailable),
        "spread": dict(unavailable),
        "moneyline_home": dict(unavailable),
        "moneyline_away": dict(unavailable),
    }


def build_game_market_context(
    game_id: str, observations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    exact_game_id = _clean(game_id)
    phases: dict[str, dict[str, dict[str, Any]]] = {
        "opening": _empty_phase(),
        "pregame": _empty_phase(),
        "live": _empty_phase(),
    }
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in _expanded_rows(exact_game_id, observations):
        normalized = normalize_market_observation(raw)
        if normalized is None:
            continue
        market = normalized["market_type"]
        if market == "moneyline":
            side = normalized.get("side")
            if side not in _SIDES:
                continue
            bucket_name = f"moneyline_{side}"
        else:
            bucket_name = market
        buckets.setdefault((normalized["phase"], bucket_name), []).append(normalized)

    tolerance_by_market = {
        "game_total": GAME_TOTAL_TOLERANCE,
        "spread": SPREAD_TOLERANCE,
        "moneyline_home": MONEYLINE_TOLERANCE,
        "moneyline_away": MONEYLINE_TOLERANCE,
    }
    for (phase, bucket_name), rows in buckets.items():
        phases[phase][bucket_name] = select_observed_consensus(
            rows, tolerance=tolerance_by_market[bucket_name]
        )

    return {
        "game_id": exact_game_id,
        "opening": phases["opening"],
        "pregame": phases["pregame"],
        "current": phases["pregame"],
        "live": phases["live"],
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "fabrication": False,
    }


__all__ = [
    "FABRICATION",
    "GAME_TOTAL_TOLERANCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONEYLINE_TOLERANCE",
    "SPREAD_TOLERANCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_game_market_context",
    "normalize_market_observation",
    "select_observed_consensus",
]
