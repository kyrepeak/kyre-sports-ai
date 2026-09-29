"""CFB Top Picks Engine V1 — Step 3 live daily ranking.

Builds a fail-closed daily Top-10 board from existing certified CFB model
owners. Sportsbook/market information is comparison context only and carries
0.0% projection weight.

Sources:
- Schedule identity: certified CFB Schedule V7.
- Moneyline probability: frozen Moneyline Slate/Final model.
- Over/Under probability: certified O/U Slate V16 using a verified total only
  as a threshold.
- Spread probability: frozen Moneyline projected margin + frozen margin
  uncertainty, compared with an ESPN scoreboard spread threshold.

No sportsbook-implied probability or price is used in ranking.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from statistics import NormalDist
import re
from typing import Any, Mapping

import streamlit as st

import cfb_moneyline_slate_v1 as moneyline_slate
import cfb_over_under_market_adapter_v3 as total_market
import cfb_over_under_slate_v16_cache_stable as over_under_slate
import cfb_schedule_v2 as espn_schedule
import cfb_schedule_v7_future_slate as schedule

MODEL_VERSION = "CFB TOP PICKS ENGINE V1 • STEP 3"
MARKET_PROJECTION_WEIGHT = 0.0
MIN_PICK_PROBABILITY = 0.55
MAX_LOOKAHEAD_DAYS = 7
MAX_PICKS = 10
SPREAD_METHOD = "normal margin threshold from frozen moneyline margin uncertainty"
RANK_WEIGHTS = {"probability": 0.75, "reliability": 0.15, "coverage": 0.10}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _identity(game: Mapping[str, Any]) -> str:
    return _clean(
        game.get("identity_key")
        or game.get("espn_event_id")
        or game.get("event_id")
        or game.get("game_id")
    )


def _event_id(game: Mapping[str, Any]) -> str:
    return _clean(
        game.get("espn_event_id")
        or game.get("event_id")
        or game.get("game_id")
    )


def _coverage(value: Any) -> float:
    if isinstance(value, Mapping):
        value = value.get("score")
    return _clamp(float(_f(value, 0.0) or 0.0), 0.0, 1.0)


def _american(value: Any) -> str:
    number = _f(value)
    if number is None or abs(number) > 100000:
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _spread_text(team: str, line: float) -> str:
    suffix = f"+{line:.1f}" if line > 0 else f"{line:.1f}"
    return f"{team} {suffix}"


def _toughness(probability: float, reliability: float, coverage: float) -> tuple[int, str]:
    """Map model strength to user-facing pick difficulty.

    Toughness is not a guarantee. Higher probability/reliability/coverage means
    lower difficulty.
    """
    strength = (
        0.70 * _clamp(probability, 0.0, 1.0)
        + 0.20 * _clamp(reliability, 0.0, 1.0)
        + 0.10 * _clamp(coverage, 0.0, 1.0)
    )
    if strength >= 0.72:
        return 2, "Easy"
    if strength >= 0.62:
        return 3, "Medium"
    return 4, "Tough"


def _rank_score(probability: float, reliability: float, coverage: float) -> float:
    return (
        RANK_WEIGHTS["probability"] * _clamp(probability, 0.0, 1.0)
        + RANK_WEIGHTS["reliability"] * _clamp(reliability, 0.0, 1.0)
        + RANK_WEIGHTS["coverage"] * _clamp(coverage, 0.0, 1.0)
    )


def _aliases(competitor: Mapping[str, Any]) -> set[str]:
    team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else {}
    values = {
        _clean(team.get("abbreviation")),
        _clean(team.get("shortDisplayName")),
        _clean(team.get("displayName")),
        _clean(team.get("location")),
        _clean(team.get("name")),
    }
    return {re.sub(r"[^a-z0-9]+", "", value.casefold()) for value in values if value}


def _detail_favorite(details: Any, home: Mapping[str, Any], away: Mapping[str, Any]) -> str:
    text = _clean(details)
    match = re.match(r"^(.+?)\s+([+-]?\d+(?:\.\d+)?)\s*$", text)
    if not match:
        return ""
    token = re.sub(r"[^a-z0-9]+", "", match.group(1).casefold())
    if token in _aliases(home):
        return "home"
    if token in _aliases(away):
        return "away"
    return ""


def _normalize_espn_odds(event: Mapping[str, Any]) -> dict[str, Any] | None:
    comps = event.get("competitions") or []
    if not comps or not isinstance(comps[0], Mapping):
        return None
    comp = comps[0]
    event_id = _clean(event.get("id") or comp.get("id"))
    if not event_id:
        return None

    sides: dict[str, Mapping[str, Any]] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).lower()
        if side in {"home", "away"}:
            sides[side] = competitor
    home = sides.get("home") or {}
    away = sides.get("away") or {}
    if not home or not away:
        return None

    candidates = [row for row in (comp.get("odds") or []) if isinstance(row, Mapping)]
    if not candidates:
        return None

    chosen = None
    for row in candidates:
        if any(
            _f(row.get(key)) is not None
            for key in ("overUnder", "spread")
        ) or isinstance(row.get("homeTeamOdds"), Mapping):
            chosen = row
            break
    if chosen is None:
        return None

    home_odds = chosen.get("homeTeamOdds") if isinstance(chosen.get("homeTeamOdds"), Mapping) else {}
    away_odds = chosen.get("awayTeamOdds") if isinstance(chosen.get("awayTeamOdds"), Mapping) else {}
    spread_raw = _f(chosen.get("spread"))
    home_spread = None
    if spread_raw is not None and abs(spread_raw) <= 80:
        magnitude = abs(float(spread_raw))
        if home_odds.get("favorite") is True:
            home_spread = -magnitude
        elif away_odds.get("favorite") is True:
            home_spread = magnitude
        else:
            favorite = _detail_favorite(chosen.get("details"), home, away)
            if favorite == "home":
                home_spread = -magnitude
            elif favorite == "away":
                home_spread = magnitude

    provider = chosen.get("provider") if isinstance(chosen.get("provider"), Mapping) else {}
    return {
        "event_id": event_id,
        "provider": _clean(provider.get("name") or provider.get("id") or "ESPN scoreboard"),
        "details": _clean(chosen.get("details")),
        "total": _f(chosen.get("overUnder")),
        "home_spread": home_spread,
        "away_spread": (-home_spread if home_spread is not None else None),
        "home_moneyline": _f(home_odds.get("moneyLine")),
        "away_moneyline": _f(away_odds.get("moneyLine")),
        "home_spread_odds": _f(home_odds.get("spreadOdds")),
        "away_spread_odds": _f(away_odds.get("spreadOdds")),
        "market_context_only": True,
        "projection_weight": 0.0,
    }


def extract_espn_market_board(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    board: dict[str, dict[str, Any]] = {}
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = _normalize_espn_odds(event)
        if row and row["event_id"] not in board:
            board[row["event_id"]] = row
    return board


def _load_espn_market_board(day: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    try:
        payload, attempts = espn_schedule._fetch_espn_fbs_payload(day)
        board = extract_espn_market_board(payload)
        return board, {
            "status": "GREEN" if board else "EMPTY",
            "games_with_market_context": len(board),
            "attempts": list(attempts or []),
            "projection_weight": 0.0,
        }
    except Exception as exc:
        return {}, {
            "status": "UNAVAILABLE",
            "games_with_market_context": 0,
            "error": f"{type(exc).__name__}: {exc}"[:300],
            "projection_weight": 0.0,
        }


def _resolve_slate(requested_day: str, lookahead_days: int = MAX_LOOKAHEAD_DAYS):
    start = date.fromisoformat(str(requested_day))
    scans: list[dict[str, Any]] = []
    for offset in range(0, max(0, int(lookahead_days)) + 1):
        day = (start + timedelta(days=offset)).isoformat()
        try:
            games, diag = schedule.load_with_diagnostics(day)
        except Exception as exc:
            scans.append({"day": day, "games": 0, "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        verified = [
            dict(game) for game in games
            if bool(game.get("identity_verified") and game.get("date_matches_query"))
        ]
        scans.append({"day": day, "games": len(verified)})
        if verified:
            return day, verified, dict(diag or {}), scans
    return str(requested_day), [], {}, scans


def _attach_total_thresholds(
    games: list[Mapping[str, Any]],
    day: str,
    espn_markets: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    source_games = [dict(game) for game in games]
    diag: dict[str, Any] = {"fanduel_status": "UNAVAILABLE", "fanduel_lines": 0, "espn_fallback_lines": 0}
    try:
        payload, market_diag = total_market.load_odds_for_date(day, "FanDuel")
        attached, attach_diag = total_market.attach_market_lines(source_games, payload)
        source_games = [dict(game) for game in attached]
        diag["fanduel_status"] = _clean(market_diag.get("status")) or "CHECK"
        diag["fanduel_lines"] = int((attach_diag or {}).get("market_lines_attached") or 0)
    except Exception as exc:
        diag["fanduel_error"] = f"{type(exc).__name__}: {exc}"[:260]

    lines: dict[str, float] = {}
    for game in source_games:
        identity = _identity(game)
        if not identity:
            continue
        try:
            line = total_market.market_line(game)
        except Exception:
            line = None
        numeric = _f(line)
        if numeric is None:
            market = espn_markets.get(_event_id(game)) or {}
            numeric = _f(market.get("total"))
            if numeric is not None:
                diag["espn_fallback_lines"] += 1
        if numeric is not None and 10.0 <= numeric <= 120.0:
            lines[identity] = float(numeric)
    diag["usable_total_lines"] = len(lines)
    diag["projection_weight"] = 0.0
    return source_games, lines, diag


def _base_candidate(
    *,
    game: Mapping[str, Any],
    market: str,
    pick: str,
    probability: float,
    reliability: float,
    coverage: float,
    odds: str = "—",
    threshold: float | None = None,
    source: str,
) -> dict[str, Any]:
    toughness, toughness_label = _toughness(probability, reliability, coverage)
    return {
        "identity": _identity(game),
        "event_id": _event_id(game),
        "away": _clean(game.get("away_team") or "Away"),
        "home": _clean(game.get("home_team") or "Home"),
        "kickoff_iso": _clean(game.get("kickoff_iso") or game.get("start_time_utc")),
        "network": _clean(game.get("broadcast")) or "TBD",
        "market": market,
        "pick": pick,
        "odds": odds,
        "probability": float(probability),
        "reliability": float(reliability),
        "coverage": float(coverage),
        "toughness": toughness,
        "toughness_label": toughness_label,
        "rank_score": _rank_score(probability, reliability, coverage),
        "threshold": threshold,
        "source": source,
        "market_projection_weight": 0.0,
    }


def moneyline_candidates(
    rows: list[Mapping[str, Any]],
    market_board: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        game = row.get("game") or {}
        final = row.get("final") or {}
        if not final.get("ready") or not final.get("final_pick_ready"):
            continue
        probability = float(_f(final.get("winner_probability_final"), 0.0) or 0.0)
        if probability < MIN_PICK_PROBABILITY:
            continue
        reliability = float(_f(final.get("reliability"), 0.0) or 0.0)
        coverage = _coverage(final.get("feature_coverage"))
        side = _clean(final.get("winner_side")).lower()
        market = market_board.get(_event_id(game)) or {}
        actual_price = market.get("home_moneyline") if side == "home" else market.get("away_moneyline")
        fair_price = final.get("home_fair_moneyline") if side == "home" else final.get("away_fair_moneyline")
        price = actual_price if _f(actual_price) is not None else fair_price
        out.append(_base_candidate(
            game=game,
            market="MONEYLINE",
            pick=_clean(final.get("winner_team")),
            probability=probability,
            reliability=reliability,
            coverage=coverage,
            odds=_american(price),
            source="Frozen CFB Moneyline final probability • market price 0% ranking weight",
        ))
    return out


def _home_cover_probability(projected_margin_home: float, sigma: float, home_spread: float) -> float:
    sd = max(1.0, float(sigma))
    threshold = -float(home_spread)
    return _clamp(1.0 - NormalDist(mu=float(projected_margin_home), sigma=sd).cdf(threshold), 0.01, 0.99)


def spread_candidates(
    rows: list[Mapping[str, Any]],
    market_board: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        game = row.get("game") or {}
        final = row.get("final") or {}
        if not final.get("ready"):
            continue
        market = market_board.get(_event_id(game)) or {}
        home_spread = _f(market.get("home_spread"))
        if home_spread is None:
            continue
        margin = _f(final.get("projected_margin_home"))
        sigma = _f((final.get("margin_uncertainty") or {}).get("sigma"))
        if margin is None or sigma is None or sigma <= 0:
            continue

        p_home = _home_cover_probability(float(margin), float(sigma), float(home_spread))
        p_away = 1.0 - p_home
        home_team = _clean(game.get("home_team") or "Home")
        away_team = _clean(game.get("away_team") or "Away")
        if p_home >= p_away:
            probability = p_home
            team = home_team
            line = float(home_spread)
            price = market.get("home_spread_odds")
        else:
            probability = p_away
            team = away_team
            line = -float(home_spread)
            price = market.get("away_spread_odds")
        if probability < MIN_PICK_PROBABILITY:
            continue

        reliability = float(_f(final.get("reliability"), 0.0) or 0.0)
        coverage = _coverage(final.get("feature_coverage"))
        out.append(_base_candidate(
            game=game,
            market="SPREAD",
            pick=_spread_text(team, line),
            probability=probability,
            reliability=reliability,
            coverage=coverage,
            odds=_american(price),
            threshold=line,
            source="Frozen CFB projected margin + verified spread threshold • market weight 0%",
        ))
    return out


def over_under_candidates(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        game = row.get("game") or {}
        final = row.get("final") or {}
        if not final.get("ready") or not final.get("rank_eligible"):
            continue
        probability = float(_f(final.get("selection_probability"), 0.0) or 0.0)
        if probability < MIN_PICK_PROBABILITY:
            continue
        line = float(_f(final.get("analysis_line"), 0.0) or 0.0)
        side = _clean(final.get("selection")).upper()
        if side not in {"OVER", "UNDER"}:
            continue
        reliability = float(_f(final.get("reliability"), 0.0) or 0.0)
        coverage = _coverage(final.get("feature_coverage"))
        out.append(_base_candidate(
            game=game,
            market="OVER/UNDER",
            pick=f"{side.title()} {line:.1f}",
            probability=probability,
            reliability=reliability,
            coverage=coverage,
            odds="—",
            threshold=line,
            source="Certified CFB O/U selection probability • total line threshold 0% projection weight",
        ))
    return out


def rank_candidates(candidates: list[Mapping[str, Any]], limit: int = MAX_PICKS) -> list[dict[str, Any]]:
    valid = [
        dict(row) for row in candidates
        if float(_f(row.get("probability"), 0.0) or 0.0) >= MIN_PICK_PROBABILITY
    ]
    valid.sort(key=lambda row: (
        -float(_f(row.get("rank_score"), 0.0) or 0.0),
        -float(_f(row.get("probability"), 0.0) or 0.0),
        str(row.get("kickoff_iso") or ""),
        str(row.get("identity") or ""),
        str(row.get("market") or ""),
    ))
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(valid[: max(0, int(limit))], start=1):
        item = dict(row)
        item["rank"] = rank
        out.append(item)
    return out


def build_daily_board(
    requested_day: str,
    *,
    lookahead_days: int = MAX_LOOKAHEAD_DAYS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved_day, games, schedule_diag, scans = _resolve_slate(requested_day, lookahead_days)
    if not games:
        return [], {
            "version": MODEL_VERSION,
            "status": "NO_SLATE",
            "requested_day": requested_day,
            "resolved_day": resolved_day,
            "schedule_scans": scans,
            "market_projection_weight": 0.0,
        }

    espn_markets, espn_diag = _load_espn_market_board(resolved_day)
    total_games, analysis_lines, total_diag = _attach_total_thresholds(
        games, resolved_day, espn_markets
    )

    ml_rows, ml_diag = moneyline_slate.scan_slate(games, resolved_day)
    if analysis_lines:
        ou_rows, ou_diag = over_under_slate.scan_slate(
            total_games, resolved_day, analysis_lines
        )
    else:
        ou_rows, ou_diag = [], {"games_with_lines": 0, "status": "NO_LINES"}

    candidates = (
        moneyline_candidates(ml_rows, espn_markets)
        + spread_candidates(ml_rows, espn_markets)
        + over_under_candidates(ou_rows)
    )
    ranked = rank_candidates(candidates, MAX_PICKS)

    return ranked, {
        "version": MODEL_VERSION,
        "status": "GREEN" if ranked else "NO_QUALIFIED_PICKS",
        "requested_day": requested_day,
        "resolved_day": resolved_day,
        "auto_advanced": resolved_day != requested_day,
        "games": len(games),
        "candidate_count": len(candidates),
        "pick_count": len(ranked),
        "market_counts": {
            market: sum(1 for row in ranked if row.get("market") == market)
            for market in ("MONEYLINE", "SPREAD", "OVER/UNDER")
        },
        "schedule": schedule_diag,
        "schedule_scans": scans,
        "espn_market": espn_diag,
        "total_market": total_diag,
        "moneyline": ml_diag,
        "over_under": ou_diag,
        "ranking_weights": dict(RANK_WEIGHTS),
        "minimum_pick_probability": MIN_PICK_PROBABILITY,
        "market_projection_weight": MARKET_PROJECTION_WEIGHT,
        "sportsbook_probability_used": False,
        "sportsbook_price_ranking_weight": 0.0,
    }


@st.cache_data(ttl=300, show_spinner=False)
def cached_daily_board(requested_day: str):
    return build_daily_board(str(requested_day))


def clear_cache() -> None:
    try:
        cached_daily_board.clear()
    except Exception:
        pass


__all__ = [
    "MARKET_PROJECTION_WEIGHT",
    "MAX_LOOKAHEAD_DAYS",
    "MAX_PICKS",
    "MIN_PICK_PROBABILITY",
    "MODEL_VERSION",
    "RANK_WEIGHTS",
    "SPREAD_METHOD",
    "_home_cover_probability",
    "_toughness",
    "build_daily_board",
    "cached_daily_board",
    "clear_cache",
    "extract_espn_market_board",
    "moneyline_candidates",
    "over_under_candidates",
    "rank_candidates",
    "spread_candidates",
]
