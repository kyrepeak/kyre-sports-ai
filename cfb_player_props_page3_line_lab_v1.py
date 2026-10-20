"""CFB Player Props Page 3 V1 — user-controlled threshold analysis over frozen projection output."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import math
from statistics import NormalDist
from typing import Any, Mapping

import cfb_player_props_model_v1 as frozen_model
from cfb_player_props_market_v1 import canonical_market_key

LINE_BOUNDS = {
    "passing_yards": (0.5, 500.5, 0.5),
    "rushing_yards": (0.5, 250.5, 0.5),
    "receiving_yards": (0.5, 250.5, 0.5),
    "receiving_receptions": (0.5, 20.5, 0.5),
    "passing_touchdowns": (0.5, 6.5, 0.5),
    "touchdowns": (0.5, 4.5, 0.5),
}
SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def normalize_line(market_key: str, value: Any) -> float | None:
    market = canonical_market_key(market_key)
    if market not in LINE_BOUNDS:
        return None
    number = _finite(value)
    if number is None:
        return None
    low, high, step = LINE_BOUNDS[market]
    number = min(high, max(low, number))
    units = (Decimal(str(number)) - Decimal(str(low))) / Decimal(str(step))
    rounded = units.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    result = Decimal(str(low)) + rounded * Decimal(str(step))
    return float(min(Decimal(str(high)), max(Decimal(str(low)), result)))


def default_line(market_key: str, *, consensus_line: Any = None, handoff_line: Any = None) -> float | None:
    market = canonical_market_key(market_key)
    if market not in LINE_BOUNDS:
        return None
    for candidate in (consensus_line, handoff_line):
        if _finite(candidate) is not None:
            return normalize_line(market, candidate)
    low, high, _ = LINE_BOUNDS[market]
    return normalize_line(market, (low + high) / 2.0)


def evaluate_line(projection: Mapping[str, Any], line: Any, market_key: str) -> dict[str, Any]:
    selected = normalize_line(market_key, line)
    mu = _finite(projection.get("projection"))
    sigma = _finite(projection.get("uncertainty"))
    sample_count = int(projection.get("sample_count") or 0)
    ready = bool(projection.get("model_ready")) and mu is not None and sigma is not None and sigma > 0 and selected is not None
    base = {
        "model_ready": ready,
        "market_key": canonical_market_key(market_key),
        "line": selected,
        "projection": mu,
        "uncertainty": sigma,
        "sample_count": sample_count,
        "margin": (mu - selected) if mu is not None and selected is not None else None,
        "over_probability": None,
        "under_probability": None,
        "side": None,
        "model_probability": None,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }
    if not ready:
        return base
    p_over = 1.0 - NormalDist(mu=mu, sigma=sigma).cdf(selected)
    p_under = 1.0 - p_over
    side = "over" if p_over >= 0.5 else "under"
    return {
        **base,
        "over_probability": p_over,
        "under_probability": p_under,
        "side": side,
        "model_probability": p_over if side == "over" else p_under,
    }


def build_probability_curve(projection: Mapping[str, Any], center_line: Any, market_key: str, *, points: int = 21) -> list[dict[str, Any]]:
    market = canonical_market_key(market_key)
    if market not in LINE_BOUNDS or int(points) <= 0:
        return []
    low, high, step = LINE_BOUNDS[market]
    center = default_line(market, consensus_line=center_line)
    if center is None:
        return []
    count = max(1, int(points))
    half = count // 2
    start = normalize_line(market, center - half * step)
    if start is None:
        return []
    max_start = max(low, high - (count - 1) * step)
    start = min(max_start, max(low, start))
    rows: list[dict[str, Any]] = []
    for index in range(count):
        line = normalize_line(market, start + index * step)
        if line is None or (rows and line <= rows[-1]["line"]):
            continue
        rows.append(evaluate_line(projection, line, market))
    return rows


__all__ = [
    "LINE_BOUNDS", "SPORTSBOOK_PROJECTION_INFLUENCE", "build_probability_curve",
    "default_line", "evaluate_line", "normalize_line",
]
