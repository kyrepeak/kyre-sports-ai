"""Pure NBA Spread Page-1 Professional Decision Board data adapter.

This module is presentation/data-shaping only. It never modifies Step-9 model
math, Step-10 decision thresholds, probability math, or ranking.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import math
from statistics import median
from typing import Any

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAX_MARKET_AGE_SECONDS = 300


def _clean(value: object) -> str:
    return str(value or "").strip()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(value: object) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh(row: Mapping[str, object], now_utc: datetime) -> bool:
    stamp = _as_utc(row.get("observed_at_utc")) or _as_utc(row.get("retrieved_at_utc"))
    if stamp is None:
        return False
    age = (now_utc - stamp).total_seconds()
    return -30 <= age <= MAX_MARKET_AGE_SECONDS


def _unavailable_market(diagnostic: str = "MARKET_UNAVAILABLE", *, coverage: str = "UNAVAILABLE") -> dict[str, Any]:
    label = "Market data stale" if coverage == "STALE" else "Market verification pending"
    return {
        "verification": "UNAVAILABLE",
        "coverage": coverage,
        "sportsbook_count": 0,
        "label": label,
        "diagnostic_state": diagnostic,
        "away_spread": None,
        "home_spread": None,
        "away_price": None,
        "home_price": None,
        "books": [],
    }


def _dedupe_book_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        book = _clean(row.get("sportsbook"))
        away = _number(row.get("away_spread"))
        home = _number(row.get("home_spread"))
        if not book or away is None or home is None or not math.isclose(away + home, 0.0, abs_tol=1e-9):
            continue
        grouped[book.casefold()].append(dict(row))
    out: list[dict[str, object]] = []
    for key in sorted(grouped):
        values = grouped[key]
        pairs = {(float(item["away_spread"]), float(item["home_spread"])) for item in values}
        if len(pairs) != 1:
            continue
        values.sort(key=lambda item: _as_utc(item.get("observed_at_utc")) or _as_utc(item.get("retrieved_at_utc")) or datetime.min.replace(tzinfo=timezone.utc))
        out.append(values[-1])
    return out


def build_market_by_game(
    games: Sequence[Mapping[str, Any]],
    payload: Mapping[str, Any],
    *,
    now_utc: datetime,
) -> dict[str, dict[str, Any]]:
    now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    game_index = {_clean(game.get("game_key")): dict(game) for game in games if _clean(game.get("game_key"))}
    result = {
        key: _unavailable_market(_clean(payload.get("diagnostic_state")) or "MARKET_UNAVAILABLE")
        for key in game_index
    }
    if _clean(payload.get("verification")).upper() != "VERIFIED":
        return result

    observations = payload.get("observations") or []
    rows = [dict(row) for row in observations if isinstance(row, Mapping)] if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) else []
    by_game: dict[str, list[dict[str, object]]] = defaultdict(list)
    stale_by_game: set[str] = set()
    for row in rows:
        key = _clean(row.get("game_key"))
        game = game_index.get(key)
        if game is None:
            continue
        if _clean(row.get("game_date_phoenix")) != _clean(game.get("game_date_phoenix")):
            continue
        if _clean(row.get("away_tricode")).upper() != _clean(game.get("away_tricode")).upper():
            continue
        if _clean(row.get("home_tricode")).upper() != _clean(game.get("home_tricode")).upper():
            continue
        if not _fresh(row, now):
            stale_by_game.add(key)
            continue
        by_game[key].append(row)

    for key in game_index:
        verified_rows = _dedupe_book_rows(by_game.get(key, []))
        if not verified_rows:
            if key in stale_by_game:
                result[key] = _unavailable_market("STALE_MARKET", coverage="STALE")
            continue
        verified_rows.sort(key=lambda row: _clean(row.get("sportsbook")).casefold())
        count = len(verified_rows)
        if count == 1:
            row = verified_rows[0]
            result[key] = {
                "verification": "VERIFIED",
                "coverage": "LIMITED",
                "consensus": False,
                "sportsbook_count": 1,
                "label": "1 book verified",
                "away_spread": float(row["away_spread"]),
                "home_spread": float(row["home_spread"]),
                "away_price": row.get("away_price"),
                "home_price": row.get("home_price"),
                "sportsbook": _clean(row.get("sportsbook")),
                "books": [_clean(row.get("sportsbook"))],
                "observed_at_utc": row.get("observed_at_utc") or row.get("retrieved_at_utc"),
                "diagnostic_state": "LIMITED_BOOK_COVERAGE",
            }
            continue
        away_spread = float(median([float(row["away_spread"]) for row in verified_rows]))
        home_spread = float(median([float(row["home_spread"]) for row in verified_rows]))
        result[key] = {
            "verification": "VERIFIED",
            "coverage": "CONSENSUS",
            "consensus": True,
            "sportsbook_count": count,
            "label": f"{count} books verified",
            "away_spread": away_spread,
            "home_spread": home_spread,
            "away_price": None,
            "home_price": None,
            "books": [_clean(row.get("sportsbook")) for row in verified_rows],
            "observed_at_utc": max(
                (_clean(row.get("observed_at_utc") or row.get("retrieved_at_utc")) for row in verified_rows),
                default="",
            ) or None,
            "diagnostic_state": "OK",
        }
    return result


def _consumer_reason(code: object) -> str:
    value = _clean(code).upper()
    if value == "INSUFFICIENT_VERIFIED_HISTORY":
        return "Fair model waiting for verified history"
    if "MARKET" in value or "SPORTSGAMEODDS" in value or "CREDENTIAL" in value:
        return "Market verification pending"
    if "SOURCE_CONFLICT" in value:
        return "Model source verification pending"
    return "Model verification pending"


def _fair_and_cover(game: Mapping[str, Any], market: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    record = dict(game.get("step9_fair_spread") or {})
    model_raw = record.get("pregame_model")
    if record.get("verification") != "VERIFIED" or not isinstance(model_raw, Mapping):
        return (
            {"verification": "UNAVAILABLE", "reason": _consumer_reason(record.get("diagnostic_state")), "diagnostic_state": record.get("diagnostic_state")},
            {"verification": "UNAVAILABLE", "reason": "Cover probability waiting for verified fair model and market"},
        )
    model = dict(model_raw)
    fair_away = _number(model.get("fair_away_spread"))
    fair_home = _number(model.get("fair_home_spread"))
    if model.get("verification") != "VERIFIED" or fair_away is None or fair_home is None:
        return (
            {"verification": "UNAVAILABLE", "reason": _consumer_reason(model.get("diagnostic_state") or record.get("diagnostic_state"))},
            {"verification": "UNAVAILABLE", "reason": "Cover probability waiting for verified fair model and market"},
        )
    fair = {"verification": "VERIFIED", "away_spread": fair_away, "home_spread": fair_home}

    if model.get("cover_verification") != "VERIFIED" or market.get("verification") != "VERIFIED":
        return fair, {"verification": "UNAVAILABLE", "reason": "Cover probability waiting for verified market threshold"}
    away_prob = _number(model.get("away_cover_probability"))
    home_prob = _number(model.get("home_cover_probability"))
    if away_prob is None or home_prob is None:
        return fair, {"verification": "UNAVAILABLE", "reason": "Cover probability waiting for verified market threshold"}
    model_market_home = _number(model.get("market_home_spread"))
    displayed_home = _number(market.get("home_spread"))
    if model_market_home is not None and displayed_home is not None and not math.isclose(model_market_home, displayed_home, abs_tol=1e-9):
        return fair, {"verification": "UNAVAILABLE", "reason": "Cover probability refreshing for current market line"}
    return fair, {"verification": "VERIFIED", "away_probability": away_prob, "home_probability": home_prob}


def _count_summary(code: str, side: Mapping[str, Any] | None) -> str:
    counts = dict((side or {}).get("counts") or {})
    pieces: list[str] = []
    labels = (("OUT", "OUT"), ("DOUBTFUL", "D"), ("QUESTIONABLE", "Q"), ("PROBABLE", "P"))
    for raw, short in labels:
        try:
            count = int(counts.get(raw) or 0)
        except (TypeError, ValueError):
            count = 0
        if count:
            pieces.append(f"{count} {short}")
    return f"{code}: {' • '.join(pieces) if pieces else 'clear'}"


def _injuries_for_game(game: Mapping[str, Any], injury_payload: Mapping[str, Any]) -> dict[str, Any]:
    key = _clean(game.get("game_key"))
    away = _clean(game.get("away_tricode")).upper()
    home = _clean(game.get("home_tricode")).upper()
    for feature in injury_payload.get("features") or []:
        if not isinstance(feature, Mapping) or _clean(feature.get("game_key")) != key:
            continue
        if not _clean(feature.get("verification")).upper().startswith("VERIFIED"):
            break
        return {
            "verification": "VERIFIED",
            "away_summary": _count_summary(away, feature.get("away") if isinstance(feature.get("away"), Mapping) else {}),
            "home_summary": _count_summary(home, feature.get("home") if isinstance(feature.get("home"), Mapping) else {}),
        }
    return {
        "verification": "UNAVAILABLE",
        "away_summary": f"{away}: status pending",
        "home_summary": f"{home}: status pending",
    }


def _public_for_game(game: Mapping[str, Any], public_payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if _clean(public_payload.get("verification")).upper() != "VERIFIED":
        return None
    away = _clean(game.get("away_tricode")).upper()
    home = _clean(game.get("home_tricode")).upper()
    for row in public_payload.get("observations") or []:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("away_tricode")).upper() == away and _clean(row.get("home_tricode")).upper() == home:
            return {"verification": "VERIFIED", **dict(row)}
    return None


def _fmt_line(value: object) -> str:
    parsed = _number(value)
    if parsed is None:
        return "—"
    return f"{parsed:+g}" if parsed != 0 else "PK"


def _line_movement(game_key: str, current: Mapping[str, Any], market_history: Mapping[str, Any] | None) -> dict[str, Any] | None:
    history = list((market_history or {}).get(game_key) or [])
    valid = [
        dict(item)
        for item in history
        if isinstance(item, Mapping)
        and _clean(item.get("verification")).upper() == "VERIFIED"
        and _number(item.get("away_spread")) is not None
        and _as_utc(item.get("observed_at_utc")) is not None
    ]
    if not valid or current.get("verification") != "VERIFIED":
        return None
    valid.sort(key=lambda item: _as_utc(item.get("observed_at_utc")))
    first = _number(valid[0].get("away_spread"))
    latest = _number(current.get("away_spread"))
    if first is None or latest is None or math.isclose(first, latest, abs_tol=1e-9):
        return None
    return {
        "verification": "VERIFIED",
        "kind": "FIRST_SEEN",
        "first_away_spread": first,
        "current_away_spread": latest,
        "label": f"First seen {_fmt_line(first)} → Current {_fmt_line(latest)}",
    }


def build_decision_board_state(
    games: Sequence[Mapping[str, Any]],
    market_payload: Mapping[str, Any],
    injury_payload: Mapping[str, Any],
    public_payload: Mapping[str, Any],
    *,
    now_utc: datetime,
    market_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    markets = build_market_by_game(games, market_payload, now_utc=now_utc)
    cards: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    for raw_game in games:
        game = dict(raw_game)
        key = _clean(game.get("game_key"))
        market = markets.get(key) or _unavailable_market()
        fair, cover = _fair_and_cover(game, market)
        fair_home = _number(fair.get("home_spread")) if fair.get("verification") == "VERIFIED" else None
        market_home = _number(market.get("home_spread")) if market.get("verification") == "VERIFIED" else None
        edge = abs(fair_home - market_home) if fair_home is not None and market_home is not None else None
        decision = dict(game.get("step10_decision") or {})
        if decision.get("verification") != "VERIFIED" or decision.get("decision_state") != "PLAY":
            decision.setdefault("consumer_reason", cover.get("reason") or fair.get("reason") or market.get("label") or "No verified play")
        card = {
            "game_key": key,
            "date": _clean(game.get("game_date_phoenix")),
            "game_date_phoenix": _clean(game.get("game_date_phoenix")),
            "away_tricode": _clean(game.get("away_tricode")).upper(),
            "home_tricode": _clean(game.get("home_tricode")).upper(),
            "away_name": _clean(game.get("away_name")) or _clean(game.get("away_tricode")).upper(),
            "home_name": _clean(game.get("home_name")) or _clean(game.get("home_tricode")).upper(),
            "tip_phoenix": _clean(game.get("tip_phoenix")),
            "venue": _clean(game.get("venue")),
            "market": market,
            "fair": fair,
            "cover": cover,
            "edge_points": edge,
            "injuries": _injuries_for_game(game, injury_payload),
            "decision": decision,
            "line_movement": _line_movement(key, market, market_history),
            "public_betting": _public_for_game(game, public_payload),
        }
        cards.append(card)
        if decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY":
            opportunities.append(
                {
                    "game_key": key,
                    "slate_rank": decision.get("slate_rank"),
                    "pick_text": decision.get("pick_text"),
                    "pick_strength": decision.get("pick_strength"),
                    "production_grade": decision.get("production_grade"),
                    "market": market,
                    "fair": fair,
                    "cover": cover,
                    "edge_points": edge,
                }
            )
    return {
        "verification": "VERIFIED" if cards else "UNAVAILABLE",
        "games": cards,
        "best_opportunities": opportunities,
        "market_diagnostic_state": market_payload.get("diagnostic_state"),
        "injury_diagnostic_state": injury_payload.get("diagnostic_state"),
        "public_diagnostic_state": public_payload.get("diagnostic_state"),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "build_market_by_game",
    "build_decision_board_state",
]
