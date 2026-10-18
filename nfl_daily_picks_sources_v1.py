from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone
import math
import time
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from nfl_daily_picks_core_v1 import DailyPickCandidate, MarketLoadResult, candidate_is_eligible

MARKET_ORDER = (
    "moneyline",
    "spread",
    "game-total",
    "passing-yards",
    "rushing-yards",
    "receiving-yards",
)
MARKET_LABELS = {
    "moneyline": "Moneyline",
    "spread": "Spread",
    "game-total": "Game Total",
    "passing-yards": "Passing Yards",
    "rushing-yards": "Rushing Yards",
    "receiving-yards": "Receiving Yards",
}
UTC = timezone.utc
ET = ZoneInfo("America/New_York")


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _number(value: Any, default: float | None = None) -> float | None:
    return float(value) if _finite(value) else default


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _kickoff_from_slate(game: Mapping[str, Any], day: date) -> datetime | None:
    direct = _utc(game.get("kickoff_at") or game.get("kickoff_utc") or game.get("start_time"))
    if direct is not None:
        return direct
    tip = _safe(game.get("tip_et")).upper().replace(" ET", "").strip()
    for pattern in ("%I:%M %p", "%I %p"):
        try:
            parsed_time = datetime.strptime(tip, pattern).time()
            local = datetime.combine(day, parsed_time, tzinfo=ET)
            return local.astimezone(UTC)
        except Exception:
            continue
    return None


def _gated(version: str, diagnostic: str) -> dict[str, Any]:
    return {
        "status": "GATED",
        "source_version": version,
        "fresh_at": None,
        "diagnostic": diagnostic,
        "rows": [],
    }


def _moneyline_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    """Read the current certified V8/V12 hot output only; never run the page UI."""
    try:
        import streamlit as st
        import nfl_hub_v1 as nfl
    except Exception as exc:
        return _gated("nfl_moneyline_hub_v8", f"Moneyline source import unavailable: {type(exc).__name__}")

    state = st.session_state
    hot = state.get("nfl_moneyline_v12_model_hot_state") or {}
    if _safe(hot.get("day")) != day.isoformat():
        return _gated("nfl_moneyline_hub_v8", "Certified Moneyline hot snapshot is not primed for this slate date.")
    built_at = _number(hot.get("built_at"))
    ttl = _number(hot.get("ttl_seconds"), 30.0) or 30.0
    if built_at is None:
        return _gated("nfl_moneyline_hub_v8", "Certified Moneyline snapshot has no freshness timestamp.")
    age = max(0.0, time.time() - built_at)
    if age > ttl:
        return _gated("nfl_moneyline_hub_v8", "Certified Moneyline hot snapshot is stale; hidden UI execution is forbidden.")

    finals = state.get("nfl_moneyline_v8_final_outputs") or {}
    edges = state.get("nfl_moneyline_v7_edge_outputs") or {}
    if not finals or not edges:
        return _gated("nfl_moneyline_hub_v8", "Certified Moneyline final/edge outputs are not available in the current source snapshot.")

    games, diag = nfl.load_nfl_slate(day.isoformat())
    if not (diag or {}).get("request_ok"):
        return _gated("nfl_moneyline_hub_v8", "Verified NFL slate is unavailable for Moneyline identity reconciliation.")

    rows: list[dict[str, Any]] = []
    for _, series in games.iterrows():
        game = series.to_dict()
        if _safe(game.get("state"), "pre").lower() != "pre":
            continue
        gid = _safe(game.get("game_id"))
        final = finals.get(gid) or {}
        edge = edges.get(gid) or {}
        final_state = _safe(final.get("state")).upper()
        leader = _safe(final.get("leader_side")).lower()
        if final_state != "QUALIFIED" or leader not in {"away", "home"}:
            continue
        side_out = edge.get(leader) or {}
        if not side_out.get("ready"):
            continue
        kickoff = _kickoff_from_slate(game, day)
        if kickoff is None:
            continue
        team = _safe(game.get(f"{leader}_abbr"))
        opponent_side = "home" if leader == "away" else "away"
        opponent = _safe(game.get(f"{opponent_side}_abbr"))
        quality_label = _safe(edge.get("market_quality"), "MEDIUM").upper()
        quality = 0.95 if quality_label in {"HIGH", "GREEN", "GOOD"} else (0.80 if quality_label in {"MEDIUM", "WATCH"} else 0.65)
        fresh_at = now_utc - timedelta(seconds=age)
        rows.append({
            "game_id": gid,
            "game_date": day,
            "kickoff_at": kickoff,
            "team_id": team,
            "opponent_team_id": opponent,
            "athlete_id": None,
            "subject_label": _safe(game.get(f"{leader}_team"), team),
            "matchup_label": f"{_safe(game.get('away_abbr'))} at {_safe(game.get('home_abbr'))}",
            "side": leader.upper(),
            "market_line": None,
            "model_projection": None,
            "model_probability": side_out.get("model_p"),
            "edge_value": side_out.get("conservative_edge", side_out.get("edge")),
            "source_ready": True,
            "source_fresh_at": fresh_at,
            "source_age_seconds": age,
            "data_quality": quality,
            "uncertainty": abs(float(side_out.get("model_p")) - float(side_out.get("conservative_p"))) if _finite(side_out.get("model_p")) and _finite(side_out.get("conservative_p")) else 0.0,
            "reason_components": tuple(str(item) for item in (final.get("prerequisites") or ()) if str(item).strip()) or ("Certified V8 final grade QUALIFIED",),
            "source_grade": _safe(final.get("leader_grade"), "QUALIFIED"),
            "source_state": final_state,
            "freshness_limit_seconds": ttl,
            "actionable": True,
        })
    return {
        "status": "READY",
        "source_version": "nfl_moneyline_hub_v8",
        "fresh_at": now_utc - timedelta(seconds=age),
        "diagnostic": "Certified V8 final grade + V7 edge snapshot; no Moneyline UI rendered.",
        "rows": rows,
    }


def _spread_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    """Consume the certified Spread market + 5M analytics helpers directly."""
    try:
        import nfl_spread_hub_v1 as transport
        import nfl_spread_hub_v3 as analytics_owner
    except Exception as exc:
        return _gated("nfl_spread_hub_v3", f"Spread source import unavailable: {type(exc).__name__}")

    games, diag = transport.base.load_nfl_slate(day.isoformat())
    if not (diag or {}).get("request_ok"):
        return _gated("nfl_spread_hub_v3", "Verified NFL slate is unavailable for Spread.")
    markets = transport._fetch_markets(games)
    rows: list[dict[str, Any]] = []
    freshest: datetime | None = None
    for _, series in games.iterrows():
        game = series.to_dict()
        if _safe(game.get("state"), "pre").lower() != "pre":
            continue
        gid = _safe(game.get("game_id"))
        market = markets.get(gid) or {}
        books = market.get("books") or []
        book = books[0] if market.get("ready") and books else {}
        if not book:
            continue
        analytics = analytics_owner._analytics_for_game(game, market, day.isoformat())
        if not analytics.get("ready") or not analytics.get("certified_run"):
            continue
        kickoff = _kickoff_from_slate(game, day)
        if kickoff is None:
            continue
        age = max(0.0, float(book.get("age_seconds") or 0.0)) if _finite(book.get("age_seconds")) else 0.0
        fresh_at = now_utc - timedelta(seconds=age)
        if freshest is None or fresh_at > freshest:
            freshest = fresh_at
        quality_label = _safe(analytics.get("model_quality"), "MEDIUM").upper()
        quality = 0.95 if quality_label == "HIGH" else (0.80 if quality_label == "MEDIUM" else 0.65)
        projected_away_margin = _number(analytics.get("projected_away_margin"))
        side_specs = (
            ("away", analytics.get("away_cover_probability"), book.get("away_spread"), -projected_away_margin if projected_away_margin is not None else None),
            ("home", analytics.get("home_cover_probability"), book.get("home_spread"), projected_away_margin),
        )
        for side, probability, line, fair_spread in side_specs:
            if not (_finite(probability) and _finite(line)):
                continue
            team = _safe(game.get(f"{side}_abbr"))
            opponent_side = "home" if side == "away" else "away"
            rows.append({
                "game_id": gid,
                "game_date": day,
                "kickoff_at": kickoff,
                "team_id": team,
                "opponent_team_id": _safe(game.get(f"{opponent_side}_abbr")),
                "athlete_id": None,
                "subject_label": _safe(game.get(f"{side}_team"), team),
                "matchup_label": f"{_safe(game.get('away_abbr'))} at {_safe(game.get('home_abbr'))}",
                "side": side.upper(),
                "market_line": line,
                "model_projection": fair_spread,
                "model_probability": probability,
                "edge_value": 0.0,
                "source_ready": True,
                "source_fresh_at": fresh_at,
                "source_age_seconds": age,
                "data_quality": quality,
                "uncertainty": max(0.0, float(analytics.get("away_cover_mc_se") or 0.0)) if _finite(analytics.get("away_cover_mc_se")) else 0.0,
                "reason_components": (
                    f"Certified {int(analytics.get('simulations') or 0):,} simulation cover probability",
                    "Independent football fair margin; sportsbook line used for settlement only",
                ),
                "source_grade": "CERTIFIED",
                "source_state": "READY",
                "freshness_limit_seconds": 300.0,
                "actionable": True,
            })
    return {
        "status": "READY",
        "source_version": "nfl_spread_hub_v3",
        "fresh_at": freshest,
        "diagnostic": "Certified Spread market + 5M analytics helpers; no Spread UI rendered.",
        "rows": rows,
    }


def _game_total_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    return _gated(
        "nfl_game_totals_market_read_v1",
        "Certified Game Total final read exposes OVER/UNDER/PASS but no source probability-strength contract; Daily Picks will not manufacture probability from projection minus line.",
    )


def _passing_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    return _gated(
        "nfl_passing_yards_market_v1",
        "Certified Passing Yards evaluator owns A/B/C/PASS, probability, edge and EV, but the current production chain exposes them only inside the page composition; Daily Picks refuses hidden page execution or HTML scraping until a render-independent snapshot is available.",
    )


def _rushing_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    return _gated(
        "nfl_rushing_yards_hub_v18",
        "Current Rushing Yards engine certifies FanDuel exact-ID line context and projection only; probability/value grading/recommendation remain OFF, so Daily Picks fails closed.",
    )


def _receiving_provider(day: date, now_utc: datetime) -> dict[str, Any]:
    return _gated(
        "nfl_receiving_yards_hub_v21",
        "Current Receiving Yards engine exposes exact-ID projection/market context but probability/EV/recommendation remain OFF, so Daily Picks fails closed.",
    )


_SOURCE_PROVIDERS: dict[str, Callable[[date, datetime], Mapping[str, Any]]] = {
    "moneyline": _moneyline_provider,
    "spread": _spread_provider,
    "game-total": _game_total_provider,
    "passing-yards": _passing_provider,
    "rushing-yards": _rushing_provider,
    "receiving-yards": _receiving_provider,
}


def _candidate_from_row(market_id: str, row: Mapping[str, Any], *, day: date, now_utc: datetime, source_version: str) -> DailyPickCandidate | None:
    if row.get("actionable") is not True:
        return None
    if market_id == "rushing-yards" and row.get("fanduel_line_ready") is not True:
        return None
    kickoff = _utc(row.get("kickoff_at"))
    fresh_at = _utc(row.get("source_fresh_at"))
    if kickoff is None or fresh_at is None:
        return None
    probability = _number(row.get("model_probability"))
    edge = _number(row.get("edge_value"))
    data_quality = _number(row.get("data_quality"))
    uncertainty = _number(row.get("uncertainty"))
    age = _number(row.get("source_age_seconds"))
    limit = _number(row.get("freshness_limit_seconds"), 300.0)
    if None in (probability, edge, data_quality, uncertainty, age, limit):
        return None
    line = _number(row.get("market_line")) if row.get("market_line") is not None else None
    projection = _number(row.get("model_projection")) if row.get("model_projection") is not None else None
    reasons = row.get("reason_components") or ()
    if isinstance(reasons, str):
        reasons = (reasons,)
    candidate = DailyPickCandidate(
        market_id=market_id,
        market_label=MARKET_LABELS[market_id],
        game_id=_safe(row.get("game_id")),
        game_date=_date(row.get("game_date"), day),
        kickoff_at=kickoff,
        team_id=_safe(row.get("team_id")),
        opponent_team_id=_safe(row.get("opponent_team_id")),
        athlete_id=_safe(row.get("athlete_id")) or None,
        subject_label=_safe(row.get("subject_label")),
        matchup_label=_safe(row.get("matchup_label")),
        side=_safe(row.get("side")).upper(),
        market_line=line,
        model_projection=projection,
        model_probability=float(probability),
        edge_value=float(edge),
        source_ready=bool(row.get("source_ready")),
        source_fresh_at=fresh_at,
        source_age_seconds=float(age),
        data_quality=float(data_quality),
        uncertainty=float(uncertainty),
        source_version=_safe(row.get("source_version"), source_version),
        reason_components=tuple(str(item).strip() for item in reasons if str(item).strip()),
        source_grade=_safe(row.get("source_grade"), "QUALIFIED"),
        source_state=_safe(row.get("source_state"), "READY").upper(),
        freshness_limit_seconds=float(limit),
    )
    eligible, _ = candidate_is_eligible(candidate, now_utc=now_utc)
    return candidate if eligible else None


def _load_market(market_id: str, day: date, *, now_utc: datetime) -> MarketLoadResult:
    provider = _SOURCE_PROVIDERS[market_id]
    try:
        payload = dict(provider(day, now_utc) or {})
    except Exception as exc:
        return MarketLoadResult(
            market_id=market_id,
            status="ERROR",
            candidates=(),
            source_version="provider-error",
            fresh_at=None,
            diagnostic=f"{type(exc).__name__}: {_safe(exc)}"[:220],
        )
    status = _safe(payload.get("status"), "UNAVAILABLE").upper()
    source_version = _safe(payload.get("source_version"), "unknown")
    candidates: list[DailyPickCandidate] = []
    for row in payload.get("rows") or ():
        if not isinstance(row, Mapping):
            continue
        candidate = _candidate_from_row(market_id, row, day=day, now_utc=now_utc, source_version=source_version)
        if candidate is not None:
            candidates.append(candidate)
    return MarketLoadResult(
        market_id=market_id,
        status=status,
        candidates=tuple(candidates),
        source_version=source_version,
        fresh_at=_utc(payload.get("fresh_at")),
        diagnostic=_safe(payload.get("diagnostic")),
    )


def load_moneyline_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("moneyline", day, now_utc=now_utc)


def load_spread_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("spread", day, now_utc=now_utc)


def load_game_total_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("game-total", day, now_utc=now_utc)


def load_passing_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("passing-yards", day, now_utc=now_utc)


def load_rushing_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("rushing-yards", day, now_utc=now_utc)


def load_receiving_yards_candidates(day: date, *, now_utc: datetime) -> MarketLoadResult:
    return _load_market("receiving-yards", day, now_utc=now_utc)


_LOADERS = {
    "moneyline": load_moneyline_candidates,
    "spread": load_spread_candidates,
    "game-total": load_game_total_candidates,
    "passing-yards": load_passing_yards_candidates,
    "rushing-yards": load_rushing_yards_candidates,
    "receiving-yards": load_receiving_yards_candidates,
}


def load_all_market_candidates(
    day: date,
    *,
    now_utc: datetime,
    loaders: Mapping[str, Callable[..., MarketLoadResult]] | None = None,
) -> tuple[MarketLoadResult, ...]:
    active = dict(_LOADERS)
    if loaders:
        active.update(loaders)
    results: list[MarketLoadResult] = []
    for market_id in MARKET_ORDER:
        loader = active[market_id]
        try:
            result = loader(day, now_utc=now_utc)
        except Exception as exc:
            result = MarketLoadResult(
                market_id=market_id,
                status="ERROR",
                candidates=(),
                source_version="loader-error",
                fresh_at=None,
                diagnostic=f"{type(exc).__name__}: {_safe(exc)}"[:220],
            )
        results.append(result)
    return tuple(results)


__all__ = [
    "MARKET_LABELS",
    "MARKET_ORDER",
    "load_all_market_candidates",
    "load_game_total_candidates",
    "load_moneyline_candidates",
    "load_passing_yards_candidates",
    "load_receiving_yards_candidates",
    "load_rushing_yards_candidates",
    "load_spread_candidates",
]
