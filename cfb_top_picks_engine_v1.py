"""CFB Top Picks Engine V1 — Step 3 daily ranking/probability/toughness.

Builds one balanced Top-10 board from existing certified CFB model outputs.
Sportsbook/market lines are thresholds/context only and carry 0.0% projection
weight. No existing Moneyline, Over/Under, or Game Total product is modified.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_moneyline_final_v1 as moneyline_final
import cfb_moneyline_slate_v1 as moneyline_slate
import cfb_over_under_final_v1 as ou_final
import cfb_over_under_market_adapter_v3 as total_market
import cfb_over_under_model_v1 as ou_model
import cfb_schedule_v7_future_slate as schedule
import cfb_top_picks_market_context_v1 as market_context

MODEL_VERSION = "CFB TOP PICKS ENGINE V1 • STEP 3"
PHOENIX = ZoneInfo("America/Phoenix")
MARKET_PROJECTION_WEIGHT = 0.0
MAX_LOOKAHEAD_DAYS = 7
DEFAULT_LIMIT = 10
MARKET_QUOTAS = {"MONEYLINE": 4, "SPREAD": 3, "OVER/UNDER": 3}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _identity(game: Mapping[str, Any]) -> str:
    return _clean(
        game.get("espn_event_id")
        or game.get("game_id")
        or game.get("identity_key")
    )


def _abbr(game: Mapping[str, Any], side: str) -> str:
    for key in (
        f"{side}_abbr",
        f"{side}_abbreviation",
        f"{side}_team_abbr",
    ):
        value = _clean(game.get(key))
        if value:
            return value[:6].upper()
    team = _clean(game.get(f"{side}_team"))
    parts = [p for p in team.replace("(", " ").replace(")", " ").split() if p]
    if not parts:
        return side[:1].upper()
    if len(parts) == 1:
        return parts[0][:4].upper()
    return "".join(p[0] for p in parts[:4]).upper()


def _kickoff(game: Mapping[str, Any]) -> str:
    raw = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not raw:
        return "Time TBD"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "Time TBD"
        local = parsed.astimezone(PHOENIX)
        return local.strftime("%a, %I:%M %p").replace(" 0", " ")
    except Exception:
        return "Time TBD"


def _american(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0)))


def _toughness(probability: float) -> tuple[int, str]:
    p = float(probability)
    if p >= 0.70:
        return 2, "Easy"
    if p >= 0.60:
        return 3, "Medium"
    return 4, "Tough"


def _base_row(
    *,
    game: Mapping[str, Any],
    market: str,
    pick: str,
    probability: float,
    odds: str,
    source: str,
    reliability: float,
) -> dict[str, Any]:
    toughness, label = _toughness(probability)
    return {
        "event_id": _identity(game),
        "away": _clean(game.get("away_team")) or "Away",
        "away_abbr": _abbr(game, "away"),
        "home": _clean(game.get("home_team")) or "Home",
        "home_abbr": _abbr(game, "home"),
        "time": _kickoff(game),
        "network": _clean(game.get("broadcast")) or "Broadcast TBD",
        "market": market,
        "pick": pick,
        "odds": odds,
        "probability_value": float(probability),
        "probability": int(round(float(probability) * 100.0)),
        "toughness": toughness,
        "toughness_label": label,
        "source": source,
        "reliability": max(0.0, min(1.0, float(reliability))),
        "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
    }


def _moneyline_candidate(
    row: Mapping[str, Any],
    market: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    game = dict(row.get("game") or {})
    final = dict(row.get("final") or {})
    if not final.get("ready") or not final.get("final_pick_ready"):
        return None

    side = _clean(final.get("winner_side")).lower()
    team = _clean(final.get("winner_team"))
    probability = _f(final.get("winner_probability_final"))
    if side not in {"home", "away"} or not team or probability <= 0.50:
        return None

    market = dict(market or {})
    actual_price = market.get(f"{side}_moneyline")
    fair_price = final.get(f"{side}_fair_moneyline")
    odds = _american(actual_price) if actual_price is not None else f"Fair {_american(fair_price)}"
    source = (
        f"{_clean(market.get('provider'))} market • Kyre Moneyline model"
        if actual_price is not None and _clean(market.get("provider"))
        else "Kyre Moneyline model • fair price"
    )
    return _base_row(
        game=game,
        market="MONEYLINE",
        pick=team,
        probability=probability,
        odds=odds,
        source=source,
        reliability=_f(final.get("reliability")),
    )


def _spread_candidate(
    row: Mapping[str, Any],
    market: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    game = dict(row.get("game") or {})
    final = dict(row.get("final") or {})
    market = dict(market or {})
    if not final.get("ready"):
        return None

    home_spread = market.get("home_spread")
    away_spread = market.get("away_spread")
    if home_spread is None or away_spread is None:
        return None

    mu = _f(final.get("projected_margin_home"))
    sigma = _f((final.get("margin_uncertainty") or {}).get("sigma_points"), 0.0)
    if sigma <= 0:
        return None

    home_line = float(home_spread)
    away_line = float(away_spread)
    p_home = max(0.001, min(0.999, _normal_cdf((mu + home_line) / sigma)))
    if p_home >= 0.50:
        side = "home"
        team = _clean(game.get("home_team"))
        line = home_line
        probability = p_home
    else:
        side = "away"
        team = _clean(game.get("away_team"))
        line = away_line
        probability = 1.0 - p_home

    if not team:
        return None
    price = market.get(f"{side}_spread_price")
    odds = _american(price) if price is not None else _clean(market.get("provider")) or "Market line"
    sign = "+" if line > 0 else ""
    return _base_row(
        game=game,
        market="SPREAD",
        pick=f"{team} {sign}{line:.1f}",
        probability=probability,
        odds=odds,
        source=f"{_clean(market.get('provider')) or 'ESPN odds'} threshold • Kyre margin distribution",
        reliability=_f(final.get("reliability")),
    )


def _ou_candidate(
    row: Mapping[str, Any],
    market: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    game = dict(row.get("game") or {})
    away = dict(row.get("away") or {})
    home = dict(row.get("home") or {})
    market = dict(market or {})

    line = None
    source = ""
    if game.get("market_line_available") is True:
        try:
            line = float(game.get("market_total"))
            source = f"{_clean(game.get('market_sportsbook')) or 'FanDuel'} threshold • Kyre O/U model"
        except (TypeError, ValueError):
            line = None
    if line is None and market.get("total") is not None:
        line = float(market["total"])
        source = f"{_clean(market.get('provider')) or 'ESPN odds'} threshold • Kyre O/U model"
    if line is None:
        return None

    raw = ou_model.project_matchup(game, away, home, line)
    final = ou_final.synthesize(game, raw)
    if not final.get("ready") or not final.get("rank_eligible"):
        return None

    selection = _clean(final.get("selection")).upper()
    probability = _f(final.get("selection_probability"))
    if selection not in {"OVER", "UNDER"} or probability <= 0.50:
        return None

    return _base_row(
        game=game,
        market="OVER/UNDER",
        pick=f"{selection.title()} {line:.1f}",
        probability=probability,
        odds=_clean(game.get("market_sportsbook")) or _clean(market.get("provider")) or "Market line",
        source=source,
        reliability=_f(final.get("reliability")),
    )


def _rank_balanced(
    candidates: list[Mapping[str, Any]],
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    limit = max(0, int(limit))
    by_market: dict[str, list[dict[str, Any]]] = {
        market: [] for market in MARKET_QUOTAS
    }
    for raw in candidates:
        row = dict(raw)
        market = _clean(row.get("market"))
        if market in by_market and _clean(row.get("event_id")):
            by_market[market].append(row)

    for rows in by_market.values():
        rows.sort(
            key=lambda row: (
                -_f(row.get("probability_value")),
                -_f(row.get("reliability")),
                _clean(row.get("event_id")),
            )
        )

    chosen: list[dict[str, Any]] = []
    used_events: set[str] = set()
    used_keys: set[tuple[str, str]] = set()

    for market, quota in MARKET_QUOTAS.items():
        taken = 0
        for row in by_market[market]:
            event_id = _clean(row.get("event_id"))
            if event_id in used_events:
                continue
            chosen.append(row)
            used_events.add(event_id)
            used_keys.add((event_id, market))
            taken += 1
            if taken >= quota or len(chosen) >= limit:
                break

    leftovers = sorted(
        (
            dict(row)
            for row in candidates
            if (_clean(row.get("event_id")), _clean(row.get("market"))) not in used_keys
        ),
        key=lambda row: (
            -_f(row.get("probability_value")),
            -_f(row.get("reliability")),
            _clean(row.get("event_id")),
        ),
    )
    for row in leftovers:
        if len(chosen) >= limit:
            break
        event_id = _clean(row.get("event_id"))
        if not event_id or event_id in used_events:
            continue
        chosen.append(row)
        used_events.add(event_id)

    chosen.sort(
        key=lambda row: (
            -_f(row.get("probability_value")),
            -_f(row.get("reliability")),
            _clean(row.get("event_id")),
        )
    )
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(chosen[:limit], start=1):
        item = dict(row)
        item["rank"] = idx
        out.append(item)
    return out


def resolve_slate(
    start_day: str,
    max_days: int = MAX_LOOKAHEAD_DAYS,
    minimum_games: int = DEFAULT_LIMIT,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Choose a slate capable of supporting the requested Top-N board."""
    start = date.fromisoformat(str(start_day))
    attempts: list[dict[str, Any]] = []
    best_day = str(start_day)
    best_games: list[dict[str, Any]] = []
    best_diag: dict[str, Any] = {}
    best_offset = 0
    target = max(1, int(minimum_games))

    for offset in range(0, max(0, int(max_days)) + 1):
        day = (start + timedelta(days=offset)).isoformat()
        games, diag = schedule.load_with_diagnostics(day)
        verified = [
            dict(game) for game in games
            if (
                game.get("identity_verified")
                and game.get("date_matches_query")
                and ou_model._pregame_status_ready(game)
            )
        ]
        attempts.append({"date": day, "games": len(verified)})

        if len(verified) > len(best_games):
            best_day = day
            best_games = verified
            best_diag = dict(diag or {})
            best_offset = offset

        if len(verified) >= target:
            return day, verified, {
                "status": "GREEN",
                "requested_date": str(start_day),
                "slate_date": day,
                "auto_advanced_days": offset,
                "attempts": attempts,
                "schedule": diag,
                "selection_reason": "earliest_slate_meeting_minimum_games",
                "minimum_games": target,
            }

    if best_games:
        return best_day, best_games, {
            "status": "GREEN",
            "requested_date": str(start_day),
            "slate_date": best_day,
            "auto_advanced_days": best_offset,
            "attempts": attempts,
            "schedule": best_diag,
            "selection_reason": "largest_verified_slate_in_window",
            "minimum_games": target,
        }

    return str(start_day), [], {
        "status": "EMPTY",
        "requested_date": str(start_day),
        "slate_date": str(start_day),
        "auto_advanced_days": 0,
        "attempts": attempts,
        "selection_reason": "no_verified_pregame_slate",
        "minimum_games": target,
    }

@st.cache_data(ttl=600, show_spinner=False)
def build_top_picks(
    start_day: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested = start_day or datetime.now(PHOENIX).date().isoformat()
    slate_day, games, slate_diag = resolve_slate(
        requested,
        minimum_games=max(1, int(limit)),
    )
    if not games:
        return [], {
            "status": "EMPTY",
            "version": MODEL_VERSION,
            "requested_date": requested,
            "slate_date": slate_day,
            "picks": 0,
            "slate": slate_diag,
            "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
        }

    market_map, spread_diag = market_context.load_market_context(slate_day)
    odds_payload, total_diag = total_market.load_odds_for_date(slate_day, "FanDuel")
    games_with_totals, attach_diag = total_market.attach_market_lines(games, odds_payload)

    analyzed, money_diag = moneyline_slate.scan_slate(games_with_totals, slate_day)
    candidates: list[dict[str, Any]] = []
    per_market = {"MONEYLINE": 0, "SPREAD": 0, "OVER/UNDER": 0}

    for row in analyzed:
        game = dict(row.get("game") or {})
        event_id = _identity(game)
        market = market_map.get(event_id) or {}
        for candidate in (
            _moneyline_candidate(row, market),
            _spread_candidate(row, market),
            _ou_candidate(row, market),
        ):
            if candidate is None:
                continue
            candidates.append(candidate)
            per_market[candidate["market"]] += 1

    picks = _rank_balanced(candidates, limit=limit)
    selected_counts = {market: 0 for market in MARKET_QUOTAS}
    for pick in picks:
        selected_counts[pick["market"]] = selected_counts.get(pick["market"], 0) + 1

    return picks, {
        "status": "GREEN" if picks else "NO_QUALIFIED_PICKS",
        "version": MODEL_VERSION,
        "requested_date": requested,
        "slate_date": slate_day,
        "auto_advanced_days": int(slate_diag.get("auto_advanced_days") or 0),
        "games": len(games),
        "games_analyzed": int(money_diag.get("games_analyzed") or 0),
        "candidate_count": len(candidates),
        "candidate_counts": per_market,
        "pick_count": len(picks),
        "selected_counts": selected_counts,
        "market_context": spread_diag,
        "total_market": total_diag,
        "total_attach": attach_diag,
        "moneyline_scan": money_diag,
        "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
        "sportsbook_may_modify_projection": False,
        "ranking_method": "balanced market quotas then probability/reliability; one pick per event",
        "market_quotas": dict(MARKET_QUOTAS),
    }


__all__ = [
    "DEFAULT_LIMIT",
    "MARKET_PROJECTION_WEIGHT",
    "MARKET_QUOTAS",
    "MAX_LOOKAHEAD_DAYS",
    "MODEL_VERSION",
    "_moneyline_candidate",
    "_normal_cdf",
    "_ou_candidate",
    "_rank_balanced",
    "_spread_candidate",
    "_toughness",
    "build_top_picks",
    "resolve_slate",
]
