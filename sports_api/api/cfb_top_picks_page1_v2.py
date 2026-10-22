"""Kyre Sports API CFB Top Picks Page 1 S-tier V2 successor.

V2 preserves the frozen V1 ranking/model result and adds decision-intelligence
metadata only. Sportsbook prices remain context-only, book-specific, and never
change the model probability or ranking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.cfb_top_picks_page1_v1 as frozen_v1

router = APIRouter(prefix="/api/v2/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE1 API V2 • S-TIER DECISION INTELLIGENCE"
SCHEMA_VERSION = "cfb_top_picks_page1_v2"
DEFAULT_LIMIT = 10
MAX_LIMIT = 10


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _record_text(record: Mapping[str, Any] | None) -> str | None:
    if not isinstance(record, Mapping):
        return None
    games = int(record.get("games") or 0)
    if games <= 0:
        return None
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    ties = int(record.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _record_win_pct(record: Mapping[str, Any] | None) -> float | None:
    if not isinstance(record, Mapping):
        return None
    games = int(record.get("games") or 0)
    if games <= 0:
        return None
    return (
        float(record.get("wins") or 0)
        + 0.5 * float(record.get("ties") or 0)
    ) / games


def _stat_value(profile: Mapping[str, Any], key: str) -> float | None:
    official = profile.get("official_stats")
    if not isinstance(official, Mapping):
        return None
    item = official.get(key)
    if not isinstance(item, Mapping):
        return None
    for field in ("value_numeric", "value"):
        number = _float(item.get(field))
        if number is not None:
            return number
    return None


def _book_prices(game: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_key = f"{side}_price"
    opening_keys = (
        f"opening_{side}_price",
        f"open_{side}_price",
        f"{side}_opening_price",
    )
    for quote in list(game.get("market_quotes") or []):
        if not isinstance(quote, Mapping):
            continue
        sportsbook = _clean(quote.get("sportsbook"))
        current = _float(quote.get(current_key))
        if not sportsbook or current is None or current == 0:
            continue
        opening = None
        for key in opening_keys:
            opening = _float(quote.get(key))
            if opening is not None and opening != 0:
                break
            opening = None
        rows.append(
            {
                "sportsbook": sportsbook,
                "price": int(round(current)),
                "opening_price": int(round(opening)) if opening is not None else None,
                "market": "moneyline",
                "updated_at": _clean(quote.get("observed_at_utc")) or None,
                "provider_event_id": _clean(quote.get("provider_event_id")) or None,
                "provider_market_id": _clean(quote.get("provider_market_id")) or None,
            }
        )
    return rows


def _line_movement(book_prices: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    for row in book_prices:
        opening = _float(row.get("opening_price"))
        current = _float(row.get("price"))
        if opening is None or current is None or opening == 0 or current == 0:
            continue
        open_implied = frozen_v1._american_implied_probability(opening)
        current_implied = frozen_v1._american_implied_probability(current)
        if open_implied is None or current_implied is None:
            continue
        delta_pp = (current_implied - open_implied) * 100.0
        if abs(delta_pp) < 0.05:
            direction = "UNCHANGED"
        elif delta_pp > 0:
            direction = "TOWARD PICK"
        else:
            direction = "AWAY FROM PICK"
        return {
            "sportsbook": _clean(row.get("sportsbook")),
            "open_price": int(round(opening)),
            "current_price": int(round(current)),
            "implied_move_pp": round(delta_pp, 1),
            "direction": direction,
            "updated_at": _clean(row.get("updated_at")) or None,
        }
    return None


def _verified_availability(
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    side: str,
) -> dict[str, Any] | None:
    candidates: list[Any] = [
        game.get("availability"),
        analysis.get("availability"),
        (analysis.get(side) or {}).get("availability")
        if isinstance(analysis.get(side), Mapping)
        else None,
    ]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        scoped = candidate.get(side) if isinstance(candidate.get(side), Mapping) else candidate
        if not isinstance(scoped, Mapping) or scoped.get("verified") is not True:
            continue
        return {
            "verified": True,
            "status": _clean(scoped.get("status")) or "VERIFIED",
            "summary": _clean(scoped.get("summary")) or None,
            "source": _clean(scoped.get("source")) or None,
            "updated_at": _clean(scoped.get("updated_at")) or None,
        }
    return None


def _reason_factors(
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    side: str,
) -> list[dict[str, str]]:
    other = "away" if side == "home" else "home"
    pick_team = _clean(game.get(f"{side}_team"))
    opp_team = _clean(game.get(f"{other}_team"))
    pick = analysis.get(side) if isinstance(analysis.get(side), Mapping) else {}
    opp = analysis.get(other) if isinstance(analysis.get(other), Mapping) else {}
    factors: list[dict[str, str]] = []

    pick_recent = pick.get("recent_record") if isinstance(pick.get("recent_record"), Mapping) else {}
    opp_recent = opp.get("recent_record") if isinstance(opp.get("recent_record"), Mapping) else {}
    pick_recent_pct = _record_win_pct(pick_recent)
    opp_recent_pct = _record_win_pct(opp_recent)
    pick_recent_text = _clean(pick.get("recent_form")) or _record_text(pick_recent)
    opp_recent_text = _clean(opp.get("recent_form")) or _record_text(opp_recent)
    if (
        pick_recent_pct is not None
        and opp_recent_pct is not None
        and pick_recent_text not in {"", "—"}
        and opp_recent_text not in {"", "—"}
        and pick_recent_pct >= opp_recent_pct + 0.10
    ):
        factors.append(
            {
                "key": "recent_form",
                "label": "Recent form",
                "text": f"{pick_team} has the stronger recent form ({pick_recent_text} vs {opp_recent_text}).",
            }
        )

    split_key = "home_record" if side == "home" else "away_record"
    split_name = "at home" if side == "home" else "on the road"
    split = pick.get(split_key) if isinstance(pick.get(split_key), Mapping) else {}
    split_pct = _record_win_pct(split)
    split_text = _record_text(split)
    if split_pct is not None and split_text and split_pct >= 0.60:
        factors.append(
            {
                "key": "location",
                "label": "Home edge" if side == "home" else "Road form",
                "text": f"{pick_team} has been effective {split_name} ({split_text}).",
            }
        )

    pick_margin = _float(pick.get("point_diff_pg"))
    opp_margin = _float(opp.get("point_diff_pg"))
    if (
        pick_margin is not None
        and opp_margin is not None
        and pick_margin >= opp_margin + 4.0
    ):
        factors.append(
            {
                "key": "scoring_margin",
                "label": "Scoring margin",
                "text": (
                    f"{pick_team} owns the stronger point differential "
                    f"({pick_margin:+.1f} vs {opp_margin:+.1f} points per game)."
                ),
            }
        )

    pick_ppg = _float(pick.get("ppg"))
    opp_allowed = _float(opp.get("points_allowed_pg"))
    if pick_ppg is not None and opp_allowed is not None and pick_ppg >= opp_allowed + 3.0:
        factors.append(
            {
                "key": "offense_matchup",
                "label": "Offensive matchup",
                "text": (
                    f"The scoring matchup favors {pick_team}: it produces {pick_ppg:.1f} points "
                    f"per game while {opp_team} allows {opp_allowed:.1f}."
                ),
            }
        )

    pick_allowed = _float(pick.get("points_allowed_pg"))
    opp_ppg = _float(opp.get("ppg"))
    if pick_allowed is not None and opp_ppg is not None and pick_allowed <= opp_ppg - 3.0:
        factors.append(
            {
                "key": "defense_matchup",
                "label": "Defensive matchup",
                "text": (
                    f"{pick_team}'s defense allows {pick_allowed:.1f} points per game, "
                    f"below {opp_team}'s {opp_ppg:.1f}-point scoring pace."
                ),
            }
        )

    pick_turnovers = _stat_value(pick, "turnover_margin")
    opp_turnovers = _stat_value(opp, "turnover_margin")
    if (
        pick_turnovers is not None
        and opp_turnovers is not None
        and pick_turnovers >= opp_turnovers + 0.5
    ):
        factors.append(
            {
                "key": "turnovers",
                "label": "Turnover edge",
                "text": (
                    f"{pick_team} also holds the stronger verified turnover-margin profile "
                    f"({pick_turnovers:+.1f} vs {opp_turnovers:+.1f})."
                ),
            }
        )

    pick_sos = _float(pick.get("sos_opponent_win_pct"))
    opp_sos = _float(opp.get("sos_opponent_win_pct"))
    if pick_sos is not None and opp_sos is not None and pick_sos >= opp_sos + 0.05:
        factors.append(
            {
                "key": "schedule_strength",
                "label": "Schedule strength",
                "text": f"{pick_team} has built its profile against the stronger opponent win-rate schedule.",
            }
        )

    availability = _verified_availability(game, analysis, side)
    if availability is not None and availability.get("summary"):
        factors.append(
            {
                "key": "availability",
                "label": "Availability",
                "text": str(availability["summary"]),
            }
        )
    return factors[:5]


def _why_text(
    team: str,
    opponent: str,
    factors: list[Mapping[str, str]],
    probability: float,
    reliability: float | None,
) -> str:
    evidence = " ".join(
        _clean(factor.get("text"))
        for factor in factors[:4]
        if _clean(factor.get("text"))
    )
    if evidence:
        conclusion = (
            f" Together, those verified matchup edges support {team} as the stronger "
            f"outright winner over {opponent}."
        )
    else:
        conclusion = (
            f" Verified matchup detail is limited for this slate, so {team} is not given "
            f"an unsupported narrative edge over {opponent}."
        )
    reliability_text = (
        f" with {reliability * 100:.0f}% reliability"
        if reliability is not None
        else ""
    )
    model = (
        f" Kyre's price-independent model supports the call at {probability * 100:.0f}%"
        f"{reliability_text}."
    )
    return (evidence + conclusion + model).strip()


def _confidence_score(
    probability: float,
    reliability: float | None,
    evidence_count: int,
) -> int:
    rel = reliability if reliability is not None else probability
    evidence = min(1.0, max(0.0, evidence_count / 4.0))
    score = 70.0 * probability + 25.0 * rel + 5.0 * evidence
    return int(round(max(0.0, min(100.0, score))))


def _value_status(edge_pp: Any) -> str:
    edge = _float(edge_pp)
    if edge is None:
        return "MARKET PENDING"
    if edge >= 2.5:
        return "MODEL VALUE"
    if edge >= 0:
        return "FAIR MARKET"
    return "PRICE TOO EXPENSIVE"


def _matchup_snapshot(
    game: Mapping[str, Any],
    analysis: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    other = "away" if side == "home" else "home"
    pick = analysis.get(side) if isinstance(analysis.get(side), Mapping) else {}
    opp = analysis.get(other) if isinstance(analysis.get(other), Mapping) else {}
    split_key = "home_record" if side == "home" else "away_record"
    return {
        "pick_record": _clean(pick.get("record_text")) or _record_text(pick.get("record")) if isinstance(pick, Mapping) else None,
        "opponent_record": _clean(opp.get("record_text")) or _record_text(opp.get("record")) if isinstance(opp, Mapping) else None,
        "pick_recent": _clean(pick.get("recent_form")) or _record_text(pick.get("recent_record")) if isinstance(pick, Mapping) else None,
        "opponent_recent": _clean(opp.get("recent_form")) or _record_text(opp.get("recent_record")) if isinstance(opp, Mapping) else None,
        "location_split": _record_text(pick.get(split_key)) if isinstance(pick, Mapping) else None,
        "pick_ppg": _float(pick.get("ppg")) if isinstance(pick, Mapping) else None,
        "opponent_ppg": _float(opp.get("ppg")) if isinstance(opp, Mapping) else None,
        "pick_points_allowed_pg": _float(pick.get("points_allowed_pg")) if isinstance(pick, Mapping) else None,
        "opponent_points_allowed_pg": _float(opp.get("points_allowed_pg")) if isinstance(opp, Mapping) else None,
        "pick_point_diff_pg": _float(pick.get("point_diff_pg")) if isinstance(pick, Mapping) else None,
        "opponent_point_diff_pg": _float(opp.get("point_diff_pg")) if isinstance(opp, Mapping) else None,
    }


def rank_moneyline_games_v2(
    games: list[Mapping[str, Any]],
    analyses: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Add verified decision intelligence without changing frozen V1 ranking."""
    ranked = frozen_v1.rank_moneyline_games(games, analyses, limit=limit)
    game_map = {
        frozen_v1._canonical_event_id(game): game
        for game in games
        if frozen_v1._canonical_event_id(game)
    }
    out: list[dict[str, Any]] = []
    for row in ranked:
        item = dict(row)
        event_id = _clean(item.get("event_id"))
        game = game_map.get(event_id, {})
        analysis = analyses.get(event_id) if isinstance(analyses.get(event_id), Mapping) else {}
        side = _clean(item.get("pick_side")).lower()
        other = "away" if side == "home" else "home"
        probability = _float(item.get("model_probability")) or 0.0
        reliability = _float(item.get("model_reliability"))
        books = _book_prices(game, side)
        factors = _reason_factors(game, analysis, side)
        item.update(
            {
                "confidence_score": _confidence_score(probability, reliability, len(factors)),
                "value_status": _value_status(item.get("model_edge_pp")),
                "book_prices": books,
                "line_movement": _line_movement(books),
                "availability": _verified_availability(game, analysis, side),
                "matchup_snapshot": _matchup_snapshot(game, analysis, side),
                "reason_factors": factors,
                "why": _why_text(
                    _clean(item.get("pick")),
                    _clean(game.get(f"{other}_team")),
                    factors,
                    probability,
                    reliability,
                ),
                "source_health": {
                    "verified_matchup_factors": len(factors),
                    "sportsbook_quotes": len(books),
                    "market_timestamped": any(bool(row.get("updated_at")) for row in books),
                },
            }
        )
        out.append(item)
    return out


def build_page1_payload(
    *,
    game_date: str | None = None,
    limit: int = DEFAULT_LIMIT,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    from sports_api.api import cfb_moneyline_page1_v1 as moneyline_api

    now = now_provider()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        selected_day, raw_games = moneyline_api._resolve_slate_date(
            requested=game_date, now=now
        )
    except ValueError as exc:
        raise ValueError("game_date must be YYYY-MM-DD") from exc

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_games:
        game = dict(raw)
        gid = frozen_v1._canonical_event_id(game)
        if not gid or gid in seen:
            continue
        seen.add(gid)
        unique.append(game)

    market_map, consulted = moneyline_api._market_state(unique)
    games = [
        moneyline_api._public_game(
            game, market_map.get(frozen_v1._canonical_event_id(game), [])
        )
        for game in unique
    ]
    analyses, failures = frozen_v1._analyze_games(
        games, selected_day, moneyline_api._analysis
    )
    picks = rank_moneyline_games_v2(games, analyses, limit=limit)

    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_date": selected_day,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "picks": picks,
        "routing": {
            "application_gateway": "Kyre Sports API",
            "schedule_primary": "NCAA",
            "stats_primary": "NCAA",
            "market_primary": "FanDuel",
            "market_secondary": "The Odds API",
            "provider_calls": consulted,
            "approved_secondary_only_when_needed": True,
            "sportsbook_projection_weight": 0.0,
            "consensus_averaging": False,
            "fabrication": False,
            "null_to_zero": False,
        },
        "source_health": {
            "gateway_live": True,
            "providers_consulted": consulted,
            "provider_count": len(consulted),
            "qualified_picks": len(picks),
            "priced_picks": sum(bool(row.get("book_prices")) for row in picks),
            "verified_reason_picks": sum(bool(row.get("reason_factors")) for row in picks),
        },
        "diagnostics": {
            "slate_games_seen": len(raw_games),
            "unique_games": len(unique),
            "duplicates_removed": max(0, len(raw_games) - len(unique)),
            "analyses_completed": len(analyses),
            "analysis_failures": failures,
            "qualified_unique_picks": len(picks),
            "requested_limit": min(MAX_LIMIT, max(0, int(limit))),
            "complete_top_ten": len(picks) == min(MAX_LIMIT, max(0, int(limit))),
            "frozen_v1_ranking_preserved": True,
        },
    }


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "build_page1_payload",
    "page1",
    "rank_moneyline_games_v2",
    "router",
]
