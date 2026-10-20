"""NBA Spread Page-1 market intelligence adapter V2.

V2 is presentation/data shaping only. It wraps the frozen V1 decision board and
adds verified per-book quotes, consensus, best available lines/prices and real
open-to-current movement when provider evidence exists. No model, probability,
ranking or decision math is changed.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import math
from statistics import median
from typing import Any

import nba_spread_decision_board_data_v1 as prior

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAX_MARKET_AGE_SECONDS = prior.MAX_MARKET_AGE_SECONDS

_BOOK_PRIORITY = {
    "fanduel": 0,
    "draftkings": 1,
    "betmgm": 2,
    "caesars": 3,
    "pinnacle": 4,
    "espn bet": 5,
    "espnbet": 5,
    "fanatics": 6,
    "bet365": 7,
}


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


def _book_rank(name: object) -> tuple[int, str]:
    clean = _clean(name)
    return _BOOK_PRIORITY.get(clean.casefold(), 50), clean.casefold()


def _price_rank(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1000000


def _fmt_line(value: object) -> str:
    parsed = _number(value)
    if parsed is None:
        return "—"
    return "PK" if math.isclose(parsed, 0.0, abs_tol=1e-9) else f"{parsed:+g}"


def _dedupe_rows(rows: Sequence[Mapping[str, object]], now_utc: datetime) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in rows:
        if not isinstance(raw, Mapping) or not _fresh(raw, now_utc):
            continue
        book = _clean(raw.get("sportsbook"))
        away = _number(raw.get("away_spread"))
        home = _number(raw.get("home_spread"))
        if not book or away is None or home is None or not math.isclose(away + home, 0.0, abs_tol=1e-9):
            continue
        grouped[book.casefold()].append(dict(raw))
    deduped: list[dict[str, object]] = []
    for values in grouped.values():
        values.sort(
            key=lambda row: _as_utc(row.get("observed_at_utc"))
            or _as_utc(row.get("retrieved_at_utc"))
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        deduped.append(values[-1])
    deduped.sort(key=lambda row: _book_rank(row.get("sportsbook")))
    return deduped


def _best_quote(rows: Sequence[Mapping[str, object]], side: str) -> dict[str, object] | None:
    spread_key = f"{side}_spread"
    price_key = f"{side}_price"
    usable = [row for row in rows if _number(row.get(spread_key)) is not None]
    if not usable:
        return None
    # For a bettor, a larger spread number is always preferable on the same side
    # (+5 beats +4.5; -4 beats -4.5). Price breaks a line tie.
    usable.sort(
        key=lambda row: (
            -float(_number(row.get(spread_key)) or 0.0),
            -_price_rank(row.get(price_key)),
            _book_rank(row.get("sportsbook")),
        )
    )
    best = usable[0]
    return {
        "sportsbook": _clean(best.get("sportsbook")),
        "spread": float(_number(best.get(spread_key))),
        "price": best.get(price_key),
        "source_transport": _clean(best.get("source_transport")) or None,
    }


def _movement(rows: Sequence[Mapping[str, object]], *, away_code: str, current_away: float) -> dict[str, object] | None:
    opens = [float(value) for value in (_number(row.get("open_away_spread")) for row in rows) if value is not None]
    if not opens:
        return None
    opening = float(median(opens))
    if math.isclose(opening, current_away, abs_tol=1e-9):
        return {
            "verification": "VERIFIED",
            "kind": "OPEN_TO_CURRENT",
            "open_away_spread": opening,
            "current_away_spread": current_away,
            "delta_points": 0.0,
            "label": f"{away_code} {_fmt_line(opening)} → {_fmt_line(current_away)}",
        }
    return {
        "verification": "VERIFIED",
        "kind": "OPEN_TO_CURRENT",
        "open_away_spread": opening,
        "current_away_spread": current_away,
        "delta_points": current_away - opening,
        "label": f"{away_code} {_fmt_line(opening)} → {_fmt_line(current_away)}",
    }


def build_market_intelligence_by_game(
    games: Sequence[Mapping[str, Any]],
    market_payload: Mapping[str, Any],
    *,
    now_utc: datetime,
) -> dict[str, dict[str, Any]]:
    now = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    rows_raw = market_payload.get("observations") or []
    rows = [dict(row) for row in rows_raw if isinstance(row, Mapping)] if isinstance(rows_raw, Sequence) and not isinstance(rows_raw, (str, bytes)) else []
    output: dict[str, dict[str, Any]] = {}
    for game in games:
        key = _clean(game.get("game_key"))
        game_rows = [
            row for row in rows
            if _clean(row.get("game_key")) == key
            and _clean(row.get("game_date_phoenix")) == _clean(game.get("game_date_phoenix"))
            and _clean(row.get("away_tricode")).upper() == _clean(game.get("away_tricode")).upper()
            and _clean(row.get("home_tricode")).upper() == _clean(game.get("home_tricode")).upper()
        ]
        verified = _dedupe_rows(game_rows, now)
        if not verified:
            output[key] = {"verification": "UNAVAILABLE", "sportsbook_count": 0, "quotes": []}
            continue
        away_values = [float(row["away_spread"]) for row in verified]
        home_values = [float(row["home_spread"]) for row in verified]
        consensus_away = float(median(away_values))
        consensus_home = float(median(home_values))
        quotes = [
            {
                "sportsbook": _clean(row.get("sportsbook")),
                "away_spread": float(row["away_spread"]),
                "home_spread": float(row["home_spread"]),
                "away_price": row.get("away_price"),
                "home_price": row.get("home_price"),
                "source_transport": _clean(row.get("source_transport")) or None,
                "observed_at_utc": row.get("observed_at_utc") or row.get("retrieved_at_utc"),
            }
            for row in verified
        ]
        output[key] = {
            "verification": "VERIFIED",
            "sportsbook_count": len(verified),
            "consensus_away_spread": consensus_away,
            "consensus_home_spread": consensus_home,
            "best_away": _best_quote(verified, "away"),
            "best_home": _best_quote(verified, "home"),
            "quotes": quotes,
            "movement": _movement(
                verified,
                away_code=_clean(game.get("away_tricode")).upper(),
                current_away=consensus_away,
            ),
            "source_chain": list(market_payload.get("source_chain") or []),
        }
    return output


def build_decision_board_state_v2(
    games: Sequence[Mapping[str, Any]],
    market_payload: Mapping[str, Any],
    injury_payload: Mapping[str, Any],
    public_payload: Mapping[str, Any],
    *,
    now_utc: datetime,
    market_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = prior.build_decision_board_state(
        games,
        market_payload,
        injury_payload,
        public_payload,
        now_utc=now_utc,
        market_history=market_history,
    )
    intelligence = build_market_intelligence_by_game(games, market_payload, now_utc=now_utc)
    cards: list[dict[str, Any]] = []
    for raw in state.get("games") or []:
        card = dict(raw)
        key = _clean(card.get("game_key"))
        card["market_intelligence"] = intelligence.get(key) or {"verification": "UNAVAILABLE", "sportsbook_count": 0, "quotes": []}
        cards.append(card)
    result = dict(state)
    result["games"] = cards
    result["market_source_chain"] = list(market_payload.get("source_chain") or [])
    result["sportsbook_projection_influence"] = 0.0
    return result


build_decision_board_state = build_decision_board_state_v2
build_market_by_game = prior.build_market_by_game

__all__ = [
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_decision_board_state",
    "build_decision_board_state_v2",
    "build_market_by_game",
    "build_market_intelligence_by_game",
]
