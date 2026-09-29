"""CFB Top Picks market context V1.

Read-only ESPN scoreboard market context for Top Picks. Official ESPN event IDs
remain the join key. Sportsbook lines are comparison thresholds/context only and
carry 0.0% projection weight.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v2 as schedule_source

MODEL_VERSION = "CFB TOP PICKS MARKET CONTEXT V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(v) for v in value.values() if isinstance(v, Mapping)]
    if isinstance(value, list):
        return [dict(v) for v in value if isinstance(v, Mapping)]
    return []


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _american(value: Any) -> int | None:
    number = _finite(value)
    if number is None or number == 0 or abs(number) < 100:
        return None
    return int(round(number))


def _side_price(side: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = side.get(key)
        price = _american(value)
        if price is not None:
            return price
    return None


def _favorite(side: Mapping[str, Any]) -> bool:
    return side.get("favorite") is True


def _details_favorite(details: str, away_abbr: str, home_abbr: str) -> str:
    text = _clean(details).upper()
    if not text:
        return ""
    prefix = re.split(r"\s+-?\d", text, maxsplit=1)[0].strip()
    if away_abbr and prefix == away_abbr.upper():
        return "away"
    if home_abbr and prefix == home_abbr.upper():
        return "home"
    return ""


def _extract_event_market(event: Mapping[str, Any]) -> dict[str, Any] | None:
    event_id = _clean(event.get("id"))
    if not event_id.isdigit():
        return None
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return None
    comp = competitions[0]

    sides: dict[str, Mapping[str, Any]] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).casefold()
        if side in {"away", "home"}:
            sides[side] = competitor
    if set(sides) != {"away", "home"}:
        return None

    away_team = sides["away"].get("team") or {}
    home_team = sides["home"].get("team") or {}
    away_abbr = _clean(away_team.get("abbreviation"))
    home_abbr = _clean(home_team.get("abbreviation"))

    odds_rows = _rows(comp.get("odds"))
    if not odds_rows:
        return {
            "event_id": event_id,
            "away_abbr": away_abbr,
            "home_abbr": home_abbr,
            "market_available": False,
            "projection_weight": PROJECTION_WEIGHT,
        }

    chosen = None
    for row in odds_rows:
        if any(row.get(k) is not None for k in ("spread", "overUnder", "details", "homeTeamOdds", "awayTeamOdds")):
            chosen = row
            break
    if chosen is None:
        chosen = odds_rows[0]

    provider_obj = chosen.get("provider") if isinstance(chosen.get("provider"), Mapping) else {}
    provider = _clean((provider_obj or {}).get("name") or chosen.get("providerName") or "ESPN odds")
    home_odds = chosen.get("homeTeamOdds") if isinstance(chosen.get("homeTeamOdds"), Mapping) else {}
    away_odds = chosen.get("awayTeamOdds") if isinstance(chosen.get("awayTeamOdds"), Mapping) else {}

    spread_abs = _finite(chosen.get("spread"))
    if spread_abs is not None:
        spread_abs = abs(spread_abs)
        if spread_abs > 100:
            spread_abs = None

    home_spread = away_spread = None
    favorite_side = ""
    if _favorite(home_odds) and not _favorite(away_odds):
        favorite_side = "home"
    elif _favorite(away_odds) and not _favorite(home_odds):
        favorite_side = "away"
    else:
        favorite_side = _details_favorite(_clean(chosen.get("details")), away_abbr, home_abbr)

    if spread_abs is not None and favorite_side == "home":
        home_spread, away_spread = -spread_abs, spread_abs
    elif spread_abs is not None and favorite_side == "away":
        away_spread, home_spread = -spread_abs, spread_abs

    total = _finite(chosen.get("overUnder"))
    if total is not None and not (20.0 <= total <= 100.0):
        total = None

    return {
        "event_id": event_id,
        "away_abbr": away_abbr,
        "home_abbr": home_abbr,
        "provider": provider,
        "market_available": True,
        "details": _clean(chosen.get("details")),
        "away_spread": away_spread,
        "home_spread": home_spread,
        "away_spread_price": _side_price(away_odds, "spreadOdds"),
        "home_spread_price": _side_price(home_odds, "spreadOdds"),
        "away_moneyline": _side_price(away_odds, "moneyLine", "moneyline"),
        "home_moneyline": _side_price(home_odds, "moneyLine", "moneyline"),
        "total": total,
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def extract_market_context(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = _extract_event_market(event)
        if row and row["event_id"] not in out:
            out[row["event_id"]] = row
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_market_context(target_date: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    try:
        payload, attempts = schedule_source._fetch_espn_fbs_payload(str(target_date))
        markets = extract_market_context(payload)
        spread_ready = sum(
            row.get("home_spread") is not None and row.get("away_spread") is not None
            for row in markets.values()
        )
        total_ready = sum(row.get("total") is not None for row in markets.values())
        return markets, {
            "status": "GREEN",
            "version": MODEL_VERSION,
            "date": str(target_date),
            "events": len(markets),
            "spread_ready": spread_ready,
            "total_ready": total_ready,
            "attempts": attempts,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
        }
    except Exception as exc:
        return {}, {
            "status": "UNAVAILABLE",
            "version": MODEL_VERSION,
            "date": str(target_date),
            "events": 0,
            "spread_ready": 0,
            "total_ready": 0,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "_extract_event_market",
    "extract_market_context",
    "load_market_context",
]
