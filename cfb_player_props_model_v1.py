"""CFB Player Props Page 1 V1 — sportsbook-independent projection + line grading."""
from __future__ import annotations

import math
from statistics import NormalDist, median
from typing import Any, Mapping, Sequence

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation, canonical_market_key

MODEL_VERSION = "CFB PLAYER PROPS PAGE 1 • SIGNAL MODEL V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_SAMPLE = 4
MAX_SAMPLE = 8
DECAY = 0.85


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def build_prop_projection(
    history: Sequence[Mapping[str, Any]], market_key: str
) -> dict[str, Any]:
    market = canonical_market_key(market_key)
    values: list[float] = []
    provenance: list[dict[str, str]] = []
    if market is not None:
        for row in history:
            if len(values) >= MAX_SAMPLE:
                break
            if row.get("completed") is not True or str(row.get("market_key") or market) != market:
                continue
            value = _finite(row.get("value"))
            if value is None or value < 0:
                continue
            values.append(value)
            provenance.append({
                "event_id": str(row.get("event_id") or ""),
                "source": str(row.get("source") or ""),
                "game_date": str(row.get("game_date") or ""),
            })
    n = len(values)
    if n == 0:
        projection = None
        uncertainty = None
    else:
        weights = [DECAY**i for i in range(n)]
        total_w = sum(weights)
        projection = sum(w*x for w, x in zip(weights, values)) / total_w
        variance = sum(w*(x-projection)**2 for w, x in zip(weights, values)) / total_w
        uncertainty = 0.0 if max(values) == min(values) else math.sqrt(max(0.0, variance))
    ready = bool(
        n >= MIN_SAMPLE and projection is not None and uncertainty is not None
        and math.isfinite(projection) and math.isfinite(uncertainty) and uncertainty > 0
    )
    return {
        "model_ready": ready,
        "market_key": market,
        "projection": projection,
        "uncertainty": uncertainty,
        "sample_count": n,
        "values": tuple(values),
        "provenance": tuple(provenance),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def _implied(price: int | None) -> float | None:
    if price is None or price == 0:
        return None
    value = float(price)
    return (-value) / ((-value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def build_market_consensus(observations: Sequence[PropObservation]) -> dict[str, Any]:
    verified = [row for row in observations if row.identity_verified and math.isfinite(float(row.line))]
    lines = [float(row.line) for row in verified]
    consensus_line = float(median(lines)) if lines else None
    by_book: dict[str, dict[str, PropObservation]] = {}
    for row in verified:
        by_book.setdefault(row.sportsbook, {})[row.side] = row
    no_vig: dict[str, list[float]] = {"over": [], "under": []}
    paired_books: list[str] = []
    for book, sides in by_book.items():
        over = sides.get("over")
        under = sides.get("under")
        if over is None or under is None or float(over.line) != float(under.line):
            continue
        p_over = _implied(over.price)
        p_under = _implied(under.price)
        if p_over is None or p_under is None or p_over + p_under <= 0:
            continue
        total = p_over + p_under
        no_vig["over"].append(p_over / total)
        no_vig["under"].append(p_under / total)
        paired_books.append(book)
    market_probability = {
        side: (sum(vals)/len(vals) if vals else None)
        for side, vals in no_vig.items()
    }
    return {
        "line": consensus_line,
        "book_count": len({row.sportsbook for row in verified}),
        "paired_books": tuple(sorted(paired_books)),
        "market_probability": market_probability,
        "provenance": tuple(sorted({(row.provider, row.sportsbook, row.observed_at_utc) for row in verified})),
    }


def grade_market_line(
    projection: Mapping[str, Any], consensus: Mapping[str, Any]
) -> dict[str, Any]:
    mu = _finite(projection.get("projection"))
    sigma = _finite(projection.get("uncertainty"))
    line = _finite(consensus.get("line"))
    base = {
        "model_ready": bool(projection.get("model_ready")),
        "projection": mu,
        "uncertainty": sigma,
        "sample_count": int(projection.get("sample_count") or 0),
        "consensus_line": line,
        "side": None,
        "model_probability": None,
        "market_probability": None,
        "edge": None,
    }
    if not base["model_ready"] or mu is None or sigma is None or sigma <= 0 or line is None:
        return base
    p_over = 1.0 - NormalDist(mu=mu, sigma=sigma).cdf(line)
    side = "over" if p_over >= 0.5 else "under"
    model_probability = p_over if side == "over" else 1.0 - p_over
    market_probs = consensus.get("market_probability") or {}
    market_probability = _finite(market_probs.get(side)) if isinstance(market_probs, Mapping) else None
    edge = model_probability - market_probability if market_probability is not None else None
    return {
        **base,
        "side": side,
        "model_probability": model_probability,
        "market_probability": market_probability,
        "edge": edge,
    }


def build_page1_signal(
    player: CanonicalPlayerIdentity,
    market_key: str,
    history: Sequence[Mapping[str, Any]],
    observations: Sequence[PropObservation],
) -> dict[str, Any]:
    projection = build_prop_projection(history, market_key)
    consensus = build_market_consensus(observations)
    grade = grade_market_line(projection, consensus)
    return {
        "player_id": player.official_player_id,
        "player_name": player.canonical_name,
        "team_id": player.official_team_id,
        "position": player.position,
        "market_key": canonical_market_key(market_key),
        **grade,
        "book_count": consensus["book_count"],
        "paired_books": consensus["paired_books"],
        "projection_provenance": projection["provenance"],
        "market_provenance": consensus["provenance"],
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "DECAY", "MAX_SAMPLE", "MIN_SAMPLE", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_market_consensus", "build_page1_signal", "build_prop_projection", "grade_market_line",
]
