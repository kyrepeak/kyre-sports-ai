"""CFB Top Picks Research V2 Step 6 — market-aware football reasoning.

Read-only explanation layer over the frozen Top Picks ranking plus frozen
research Steps 3-5. It cannot change projection, probability, selection,
ranking, sportsbook influence, or API 2 behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 6 • MARKET-AWARE REASONING"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MARKET_REASONING_PROJECTION_WEIGHT = 0.0
API2_USED = False

REQUIRED_SIGNALS = {
    "OVER/UNDER": (
        "combined_scoring_environment",
        "pace_signal",
        "offensive_efficiency_signal",
        "defensive_vulnerability_signal",
        "recent_total_trend",
        "history_total_context",
        "line_clearance_context",
    ),
    "SPREAD": (
        "projected_margin_context",
        "scoring_margin_form",
        "offense_vs_defense_edge",
        "home_away_context",
        "recent_margin_form",
        "history_margin_context",
    ),
    "MONEYLINE": (
        "win_strength_context",
        "offense_vs_defense_edge",
        "turnover_or_possession_context",
        "home_away_context",
        "recent_form",
        "history_winner_context",
    ),
}

ALLOWED_SIGNAL_STATUSES = {
    "VERIFIED",
    "PARTIAL",
    "UNAVAILABLE",
    "VERIFIED_NO_HISTORY",
    "SOURCE_CONFLICT_REVIEW",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(profile: Mapping[str, Any], key: str) -> dict[str, Any]:
    metrics = profile.get("metrics") or {}
    item = metrics.get(key) or {}
    return dict(item) if isinstance(item, Mapping) else {}


def _value(profile: Mapping[str, Any], key: str) -> float | None:
    return _f(_metric(profile, key).get("value"))


def _sources(*items: Mapping[str, Any] | None) -> list[str]:
    out: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        source = _clean(item.get("source"))
        if source and source not in out:
            out.append(source)
    return out


def _observed(*items: Mapping[str, Any] | None, fallback: str = "") -> str:
    for item in items:
        if isinstance(item, Mapping):
            value = _clean(item.get("observed_at"))
            if value:
                return value
    return fallback or _now()


def _signal(
    text: str,
    *,
    status: str = "VERIFIED",
    sources: list[str] | None = None,
    observed_at: str = "",
) -> dict[str, Any]:
    resolved = status if status in ALLOWED_SIGNAL_STATUSES else "UNAVAILABLE"
    return {
        "status": resolved,
        "text": _clean(text) or "Verified evidence unavailable.",
        "sources": [str(s) for s in (sources or []) if _clean(s)],
        "observed_at": observed_at or _now(),
    }


def _row_source(row: Mapping[str, Any]) -> str:
    return _clean(row.get("source")) or "Frozen CFB Top Picks ranking row"


def _selected_side(row: Mapping[str, Any]) -> tuple[str, str]:
    pick = _clean(row.get("pick"))
    away = _clean(row.get("away"))
    home = _clean(row.get("home"))
    if away and pick.casefold().startswith(away.casefold()):
        return "away", away
    if home and pick.casefold().startswith(home.casefold()):
        return "home", home
    return "", ""


def _line(row: Mapping[str, Any]) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", _clean(row.get("pick")))
    return _f(match.group(1)) if match else None


def _profiles(offense: Mapping[str, Any], defense: Mapping[str, Any]):
    return (
        offense.get("away") or {},
        offense.get("home") or {},
        defense.get("away") or {},
        defense.get("home") or {},
    )


def _history(
    row: Mapping[str, Any],
    series: Mapping[str, Any],
    *,
    totals: bool,
    observed_at: str,
) -> dict[str, Any]:
    source = _clean(series.get("source"))
    verified_sources = [str(x) for x in (series.get("sources_verified") or []) if _clean(x)]
    sources = ([source] if source else verified_sources)
    if not bool(series.get("history_ready")):
        if _clean(series.get("status")) == "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION":
            return _signal(
                "No prior meeting was verified after independent history sources were exhausted.",
                status="VERIFIED_NO_HISTORY",
                sources=[str(x) for x in (series.get("sources_attempted") or []) if _clean(x)],
                observed_at=_clean(series.get("observed_at")) or observed_at,
            )
        return _signal(
            "No historical edge is claimed because the multi-source history router did not verify a series.",
            status="SOURCE_CONFLICT_REVIEW",
            sources=[str(x) for x in (series.get("sources_attempted") or []) if _clean(x)],
            observed_at=_clean(series.get("observed_at")) or observed_at,
        )

    meetings = int(_f(series.get("meetings")) or 0)
    if totals:
        avg_total = _f(series.get("avg_combined_total"))
        text = (
            f"Verified series history averages {avg_total:.1f} combined points across {meetings} meetings."
            if avg_total is not None and meetings > 0
            else f"Verified history exists across {meetings} meetings; no series-total average is claimed."
        )
    else:
        side, team = _selected_side(row)
        wins = int(_f(series.get(f"{side}_wins")) or 0) if side else 0
        losses = int(_f(series.get("home_wins" if side == "away" else "away_wins")) or 0) if side else 0
        text = (
            f"{team} is {wins}-{losses} in the verified series across {meetings} meetings."
            if side and meetings > 0
            else f"Verified history exists across {meetings} meetings; no selected-side record is claimed."
        )
    return _signal(
        text,
        sources=sources,
        observed_at=_clean(series.get("observed_at")) or observed_at,
    )


def _offense_vs_defense(
    row: Mapping[str, Any],
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    oa, oh, da, dh = _profiles(offense, defense)
    side, team = _selected_side(row)
    if side == "away":
        selected_o, opponent_d, opponent = oa, dh, _clean(row.get("home"))
    elif side == "home":
        selected_o, opponent_d, opponent = oh, da, _clean(row.get("away"))
    else:
        return _signal(
            "No selected team could be resolved, so no side-specific offense-vs-defense edge is claimed.",
            status="UNAVAILABLE",
            sources=[_row_source(row)],
            observed_at=observed_at,
        )

    ypp = _value(selected_o, "yards_per_play")
    yppa = _value(opponent_d, "yards_per_play_allowed")
    ppg = _value(selected_o, "points_per_game")
    pa = _value(opponent_d, "points_allowed_per_game")
    items = (
        _metric(selected_o, "yards_per_play"),
        _metric(opponent_d, "yards_per_play_allowed"),
        _metric(selected_o, "points_per_game"),
        _metric(opponent_d, "points_allowed_per_game"),
    )
    parts: list[str] = []
    if ypp is not None and yppa is not None:
        parts.append(f"{team} gains {ypp:.2f} yards/play while {opponent} allows {yppa:.2f}.")
    if ppg is not None and pa is not None:
        parts.append(f"{team} scores {ppg:.1f} PPG while {opponent} allows {pa:.1f}.")
    if not parts:
        return _signal(
            "Verified side-specific efficiency evidence is incomplete; no edge is claimed.",
            status="UNAVAILABLE",
            sources=[_row_source(row)],
            observed_at=observed_at,
        )
    return _signal(
        " ".join(parts),
        status="VERIFIED" if len(parts) == 2 else "PARTIAL",
        sources=_sources(*items),
        observed_at=_observed(*items, fallback=observed_at),
    )


def _recent_margin(
    row: Mapping[str, Any],
    offense: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    side, team = _selected_side(row)
    profile = (offense.get(side) or {}) if side else {}
    margins: list[float] = []
    for game in list(profile.get("recent_games") or []):
        if not isinstance(game, Mapping):
            continue
        pf, pa = _f(game.get("points_for")), _f(game.get("points_against"))
        if pf is not None and pa is not None:
            margins.append(pf - pa)
    if not margins:
        return _signal(
            "Recent completed-game scoring margins are unavailable for the selected side.",
            status="UNAVAILABLE",
            sources=[_row_source(row)],
            observed_at=observed_at,
        )
    avg = sum(margins) / len(margins)
    provider = _clean(((profile.get("source_router") or {}).get("recent_scoring") or {}).get("provider"))
    return _signal(
        f"{team} has a {avg:+.1f} average scoring margin across its last {len(margins)} verified completed games.",
        sources=[provider or "ESPN exact-team completed-game schedule"],
        observed_at=_clean(profile.get("observed_at")) or observed_at,
    )


def _home_away(row: Mapping[str, Any], observed_at: str) -> dict[str, Any]:
    side, team = _selected_side(row)
    if side not in {"home", "away"}:
        return _signal(
            "Selected-side home/away identity is unavailable.",
            status="UNAVAILABLE",
            sources=[_row_source(row)],
            observed_at=observed_at,
        )
    opponent = _clean(row.get("away" if side == "home" else "home"))
    venue = "home" if side == "home" else "road"
    return _signal(
        f"{team} is the {venue} side against {opponent}; this is descriptive venue context, not an added model adjustment.",
        sources=[_row_source(row)],
        observed_at=observed_at,
    )


def _over_under(row, offense, defense, series, observed_at):
    oa, oh, da, dh = _profiles(offense, defense)
    away_ppg, home_ppg = _value(oa, "points_per_game"), _value(oh, "points_per_game")
    ppg_items = (_metric(oa, "points_per_game"), _metric(oh, "points_per_game"))
    combined = away_ppg + home_ppg if away_ppg is not None and home_ppg is not None else None
    scoring = (
        _signal(
            f"Season scoring environment: {_clean(row.get('away'))} {away_ppg:.1f} PPG + {_clean(row.get('home'))} {home_ppg:.1f} PPG = {combined:.1f}.",
            sources=_sources(*ppg_items),
            observed_at=_observed(*ppg_items, fallback=observed_at),
        )
        if combined is not None
        else _signal("Combined season scoring data is incomplete.", status="UNAVAILABLE", sources=[_row_source(row)], observed_at=observed_at)
    )

    away_plays, home_plays = _value(da, "plays_per_game"), _value(dh, "plays_per_game")
    pace_items = (_metric(da, "plays_per_game"), _metric(dh, "plays_per_game"))
    pace = (
        _signal(
            f"Verified pace: {_clean(row.get('away'))} {away_plays:.1f} plays/game; {_clean(row.get('home'))} {home_plays:.1f} plays/game.",
            sources=_sources(*pace_items),
            observed_at=_observed(*pace_items, fallback=observed_at),
        )
        if away_plays is not None and home_plays is not None
        else _signal("Verified plays-per-game pace is incomplete.", status="UNAVAILABLE", sources=_sources(*pace_items), observed_at=observed_at)
    )

    away_ypp, home_ypp = _value(oa, "yards_per_play"), _value(oh, "yards_per_play")
    ypp_items = (_metric(oa, "yards_per_play"), _metric(oh, "yards_per_play"))
    efficiency = (
        _signal(
            f"Offensive efficiency: {_clean(row.get('away'))} {away_ypp:.2f} YPP; {_clean(row.get('home'))} {home_ypp:.2f} YPP.",
            sources=_sources(*ypp_items),
            observed_at=_observed(*ypp_items, fallback=observed_at),
        )
        if away_ypp is not None and home_ypp is not None
        else _signal("Verified yards-per-play offense evidence is incomplete.", status="UNAVAILABLE", sources=_sources(*ypp_items), observed_at=observed_at)
    )

    away_pa, home_pa = _value(da, "points_allowed_per_game"), _value(dh, "points_allowed_per_game")
    pa_items = (_metric(da, "points_allowed_per_game"), _metric(dh, "points_allowed_per_game"))
    vulnerability = (
        _signal(
            f"Defensive scoring allowance: {_clean(row.get('away'))} {away_pa:.1f} PPG allowed; {_clean(row.get('home'))} {home_pa:.1f}.",
            sources=_sources(*pa_items),
            observed_at=_observed(*pa_items, fallback=observed_at),
        )
        if away_pa is not None and home_pa is not None
        else _signal("Verified defensive scoring allowance is incomplete.", status="UNAVAILABLE", sources=_sources(*pa_items), observed_at=observed_at)
    )

    ar, hr = _value(oa, "recent_scoring_avg"), _value(oh, "recent_scoring_avg")
    ara, hra = _value(da, "recent_points_allowed_avg"), _value(dh, "recent_points_allowed_avg")
    recent_items = (
        _metric(oa, "recent_scoring_avg"), _metric(oh, "recent_scoring_avg"),
        _metric(da, "recent_points_allowed_avg"), _metric(dh, "recent_points_allowed_avg"),
    )
    recent = (
        _signal(
            f"Recent form: team scoring averages total {ar + hr:.1f}; recent defensive allowance averages total {ara + hra:.1f}.",
            sources=_sources(*recent_items),
            observed_at=_observed(*recent_items, fallback=observed_at),
        )
        if None not in (ar, hr, ara, hra)
        else _signal("Recent scoring/allowance evidence is incomplete; no recent total trend is claimed.", status="UNAVAILABLE", sources=_sources(*recent_items), observed_at=observed_at)
    )

    line = _line(row)
    selection = _clean(row.get("pick")).split(" ", 1)[0].upper()
    line_context = (
        _signal(
            f"{selection.title()} {line:.1f} is the frozen market threshold; combined season PPG is {combined - line:+.1f} points relative to it. This is context, not a projection rewrite.",
            sources=[_row_source(row)] + _sources(*ppg_items),
            observed_at=observed_at,
        )
        if line is not None and combined is not None
        else _signal("A verified total threshold or combined scoring context is incomplete.", status="UNAVAILABLE", sources=[_row_source(row)], observed_at=observed_at)
    )

    return {
        "combined_scoring_environment": scoring,
        "pace_signal": pace,
        "offensive_efficiency_signal": efficiency,
        "defensive_vulnerability_signal": vulnerability,
        "recent_total_trend": recent,
        "history_total_context": _history(row, series, totals=True, observed_at=observed_at),
        "line_clearance_context": line_context,
    }


def _spread(row, offense, defense, series, observed_at):
    line = _line(row)
    probability = _f(row.get("probability_value"))
    if probability is None:
        raw = _f(row.get("probability"))
        probability = raw / 100.0 if raw is not None else None
    margin = (
        _signal(
            f"The frozen margin distribution gives {_clean(row.get('pick'))} a {probability * 100:.0f}% cover probability at the {line:+.1f} threshold. The mean margin is not re-derived here.",
            sources=[_row_source(row)],
            observed_at=observed_at,
        )
        if line is not None and probability is not None
        else _signal("Frozen spread probability/line context is incomplete.", status="UNAVAILABLE", sources=[_row_source(row)], observed_at=observed_at)
    )
    recent = _recent_margin(row, offense, observed_at)
    return {
        "projected_margin_context": margin,
        "scoring_margin_form": recent,
        "offense_vs_defense_edge": _offense_vs_defense(row, offense, defense, observed_at),
        "home_away_context": _home_away(row, observed_at),
        "recent_margin_form": recent,
        "history_margin_context": _history(row, series, totals=False, observed_at=observed_at),
    }


def _moneyline(row, offense, defense, series, observed_at):
    probability = _f(row.get("probability_value"))
    if probability is None:
        raw = _f(row.get("probability"))
        probability = raw / 100.0 if raw is not None else None
    reliability = _f(row.get("reliability"))
    strength = (
        _signal(
            f"The frozen Moneyline model gives {_clean(row.get('pick'))} a {probability * 100:.0f}% win probability"
            + (f" with {reliability * 100:.0f}% reliability." if reliability is not None else "."),
            sources=[_row_source(row)],
            observed_at=observed_at,
        )
        if probability is not None
        else _signal("Frozen Moneyline win probability is unavailable.", status="UNAVAILABLE", sources=[_row_source(row)], observed_at=observed_at)
    )

    _, _, da, dh = _profiles(offense, defense)
    away_plays, home_plays = _value(da, "plays_per_game"), _value(dh, "plays_per_game")
    pace_items = (_metric(da, "plays_per_game"), _metric(dh, "plays_per_game"))
    possession = (
        _signal(
            f"Possession environment: {_clean(row.get('away'))} {away_plays:.1f} plays/game and {_clean(row.get('home'))} {home_plays:.1f}. No turnover edge is claimed because verified turnover evidence is not in the frozen research payload.",
            status="PARTIAL",
            sources=_sources(*pace_items),
            observed_at=_observed(*pace_items, fallback=observed_at),
        )
        if away_plays is not None and home_plays is not None
        else _signal("Verified possession/turnover context is incomplete; no turnover edge is claimed.", status="UNAVAILABLE", sources=[_row_source(row)], observed_at=observed_at)
    )

    return {
        "win_strength_context": strength,
        "offense_vs_defense_edge": _offense_vs_defense(row, offense, defense, observed_at),
        "turnover_or_possession_context": possession,
        "home_away_context": _home_away(row, observed_at),
        "recent_form": _recent_margin(row, offense, observed_at),
        "history_winner_context": _history(row, series, totals=False, observed_at=observed_at),
    }


def build_market_reasoning(
    row: Mapping[str, Any],
    game: Mapping[str, Any],
    offense: Mapping[str, Any],
    defense_pace: Mapping[str, Any],
    series: Mapping[str, Any],
) -> dict[str, Any]:
    market = _clean(row.get("market")).upper()
    observed_at = _clean(offense.get("observed_at")) or _clean(defense_pace.get("observed_at")) or _now()
    if market == "OVER/UNDER":
        signals = _over_under(row, offense, defense_pace, series, observed_at)
    elif market == "SPREAD":
        signals = _spread(row, offense, defense_pace, series, observed_at)
    elif market == "MONEYLINE":
        signals = _moneyline(row, offense, defense_pace, series, observed_at)
    else:
        signals = {}

    required = list(REQUIRED_SIGNALS.get(market, ()))
    verified = sum(
        1 for key in required
        if (signals.get(key) or {}).get("status") in {"VERIFIED", "PARTIAL", "VERIFIED_NO_HISTORY"}
    )
    summary = " ".join(
        _clean((signals.get(key) or {}).get("text"))
        for key in required
        if (signals.get(key) or {}).get("status") in {"VERIFIED", "PARTIAL"}
    )[:3]
    return {
        "version": MODEL_VERSION,
        "market": market,
        "status": "READY" if required and verified == len(required) else "PARTIAL",
        "required_signals": required,
        "signals": signals,
        "summary": summary or "Verified market-specific research is incomplete; no extra football edge is being claimed.",
        "projection_weight": MARKET_REASONING_PROJECTION_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_probability": MAY_MODIFY_PROBABILITY,
        "may_modify_ranking": MAY_MODIFY_RANKING,
        "may_modify_selection": MAY_MODIFY_SELECTION,
        "api2_used": API2_USED,
        "event_id": _clean(game.get("espn_event_id") or game.get("game_id") or row.get("event_id")),
        "observed_at": observed_at,
    }


__all__ = [
    "ALLOWED_SIGNAL_STATUSES", "API2_USED", "MARKET_REASONING_PROJECTION_WEIGHT",
    "MAY_MODIFY_PROBABILITY", "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION", "MODEL_VERSION", "REQUIRED_SIGNALS",
    "SPORTSBOOK_PROJECTION_WEIGHT", "build_market_reasoning",
]
