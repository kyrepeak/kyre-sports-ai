"""Kyre Sports API — CFB Top Picks Page 2 adaptive analytics contract.

Kyre Sports API is the only application-facing gateway. Page 2 uses field-first
routing: official NCAA identity/team evidence and exact sportsbook observations
already owned by approved backend adapters are reused; fallbacks are consulted
only for the affected field family. Sportsbook context has zero projection
weight, missing data is never converted to zero, and a specific semantic state
is returned when an approved field cannot be verified.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

from fastapi import APIRouter, Query

import cfb_over_under_model_v1 as total_model
import cfb_player_props_fanduel_bound_v2 as fanduel_props
import cfb_player_props_odds_api_v1 as odds_props
import sports_api.api.cfb_game_total_page1_v1 as game_api
import sports_api.api.cfb_moneyline_page1_v1 as ml_api
import sports_api.api.cfb_top_picks_page1_v3 as page1_math
import sports_api.api.cfb_top_picks_page1_v4 as page1_v4

router = APIRouter(prefix="/api/v1/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE2 API V1 • S-TIER FIELD-FIRST SEMANTIC CONTRACT"
SCHEMA_VERSION = "cfb_top_picks_page2_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
FORBIDDEN_PROVIDERS = ("SGO", "ESPN", "ESPN BET")
STATUSES = {
    "READY", "PARTIAL", "SEMANTIC_EMPTY", "NOT_APPLICABLE",
    "SOURCE_DEGRADED", "IDENTITY_UNAVAILABLE",
}
MODULES = (
    "kyre_verdict", "line_lab", "projection", "drivers", "matchup",
    "recent_form", "history", "market_board", "line_movement",
    "availability", "game_environment", "risks", "flip_conditions", "sources",
)


def _c(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _n(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _m(status: str = "SEMANTIC_EMPTY", **values: Any) -> dict[str, Any]:
    return {"status": status, **values}


def _semantic(state: str, reason: str, **values: Any) -> dict[str, Any]:
    return {
        "status": "SEMANTIC_EMPTY",
        "semantic_state": _c(state).upper(),
        "reason": _c(reason),
        **values,
    }


def _day(snapshot: Mapping[str, Any]) -> str:
    direct = _c(snapshot.get("selected_date"))
    return direct or _c(snapshot.get("kickoff_iso"))[:10]


def _key(value: Any) -> str:
    text = _c(value).casefold().replace("&", " and ")
    text = re.sub(r"\buniversity\b", "", text)
    text = re.sub(r"\bthe\b", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def resolve_candidate(candidate_id: str, kind: str | None = None, game_date: str | None = None) -> dict[str, Any]:
    payload = page1_v4.build_page1_payload(game_date=game_date, limit=10)
    rows = list(payload.get("game_picks") or []) + list(payload.get("player_props") or [])
    exact = [dict(row) for row in rows if _c(row.get("candidate_id")) == _c(candidate_id)]
    if kind:
        exact = [
            row for row in exact
            if ("player-prop" if row.get("player_name") else "game-pick") == kind
        ]
    if len(exact) != 1:
        return {
            "status": "IDENTITY_UNAVAILABLE",
            "selection_snapshot": None,
            "reason": "Exact Page 1 candidate was not uniquely resolved.",
        }
    row = exact[0]
    row["kind"] = "player-prop" if row.get("player_name") else "game-pick"
    row["selected_date"] = _c(payload.get("selected_date") or game_date or _day(row))
    return {
        "status": "READY",
        "selection_snapshot": row,
        "page1_schema": payload.get("schema_version"),
    }


def _game_context(snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the exact verified NCAA game and NCAA-owned team evidence.

    ``game_api._load_ncaa_games`` calls the date-scoped NCAA scoreboard path.
    ``ml_api._analysis`` ultimately calls the NCAA season schedule/stats/ranking
    functions directly; its sportsbook observations never enter those profiles.
    """
    day = _day(snapshot)
    event_id = _c(snapshot.get("event_id") or snapshot.get("official_game_id"))
    games = game_api._load_ncaa_games(day)
    matches = [
        dict(game) for game in games
        if _c(game.get("game_id") or game.get("identity_key")) == event_id
    ]
    if len(matches) != 1:
        return {}, {}
    game = matches[0]
    try:
        analysis = dict(ml_api._analysis(game, day) or {})
    except Exception:
        analysis = {}
    return game, analysis


def _stat(profile: Mapping[str, Any], key: str) -> float | None:
    raw = (profile.get("official_stats") or {}).get(key) or {}
    return _n(raw.get("value_numeric") if isinstance(raw, Mapping) else raw)


def _turnover_margin_per_game(profile: Mapping[str, Any]) -> tuple[float | None, bool]:
    raw = (profile.get("official_stats") or {}).get("turnover_margin") or {}
    if not isinstance(raw, Mapping):
        return _n(raw), False
    value = _n(raw.get("value_numeric"))
    if value is None:
        return None, False
    headers = [_c(item).casefold() for item in raw.get("headers") or []]
    final_header = headers[-1] if headers else ""
    if any(token in final_header for token in ("per game", "avg", "average")):
        return value, False
    games = _n((profile.get("record") or {}).get("games"))
    if games and games > 0:
        return value / games, True
    return value, False


def _recent_item(profile: Mapping[str, Any]) -> dict[str, Any] | None:
    games = int(_n((profile.get("recent_record") or {}).get("games")) or 0)
    if games <= 0:
        return None
    wins = int(_n((profile.get("recent_record") or {}).get("wins")) or 0)
    losses = int(_n((profile.get("recent_record") or {}).get("losses")) or 0)
    ties = int(_n((profile.get("recent_record") or {}).get("ties")) or 0)
    record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    ppg = _n(profile.get("recent_ppg"))
    allowed = _n(profile.get("recent_points_allowed_pg"))
    pieces = [record]
    if ppg is not None:
        pieces.append(f"{ppg:.1f} PPG")
    if allowed is not None:
        pieces.append(f"{allowed:.1f} allowed")
    return {"title": _c(profile.get("team")) or "Verified team", "record": record, "value": " • ".join(pieces)}


def _recent_form(away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    items = [item for item in (_recent_item(away), _recent_item(home)) if item]
    if not items:
        return _semantic("NO_QUALIFYING_GAMES", "No Qualifying Games", items=[])
    return _m("READY", items=items, source="NCAA verified completed-game logs")


def _history(away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    home_name = _key(home.get("team"))
    rows: list[dict[str, Any]] = []
    for raw in away.get("completed_games") or []:
        if not isinstance(raw, Mapping) or _key(raw.get("opponent")) != home_name:
            continue
        rows.append({
            "date": _c(raw.get("date")),
            "opponent": _c(raw.get("opponent")),
            "result": _c(raw.get("result")),
            "score": _c(raw.get("score")),
            "title": _c(raw.get("date")) or "Verified prior meeting",
            "text": " • ".join(part for part in (_c(raw.get("result")), _c(raw.get("score"))) if part),
        })
    if not rows:
        return _semantic(
            "NO_PREVIOUS_MEETINGS",
            "No Previous Meetings in the verified current-season NCAA sample.",
            rows=[],
        )
    return _m("READY", rows=rows, source="NCAA verified completed-game history")


def _environment(snapshot: Mapping[str, Any], game: Mapping[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    kickoff = _c(snapshot.get("kickoff_iso") or game.get("kickoff_iso"))
    venue = _c(game.get("venue") or game.get("venue_name") or game.get("site"))
    if kickoff:
        items.append({"title": "Kickoff", "value": kickoff})
    if venue:
        items.append({"title": "Venue", "value": venue})
    reason = "Verified kickoff/venue context. Weather is shown only after an approved weather observation is attached to this game identity."
    return _m("PARTIAL", items=items, reason=reason, source="NCAA verified schedule") if items else _semantic(
        "PREGAME_ENVIRONMENT_PENDING", "Pregame environment verification in progress.", items=[]
    )


def _game_analysis(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    game, analysis = _game_context(snapshot)
    if not game:
        empty = _semantic("GAME_IDENTITY_NOT_VERIFIED", "Verified game identity could not be resolved for this selection.")
        return {
            key: dict(empty)
            for key in ("projection", "drivers", "matchup", "recent_form", "history", "game_environment", "risks", "flip_conditions")
        } | {"line_scenarios": [], "sources": dict(empty)}

    final = dict(analysis.get("final") or {})
    away = dict(analysis.get("away") or {})
    home = dict(analysis.get("home") or {})
    ph = _n(final.get("projected_home_points"))
    pa = _n(final.get("projected_away_points"))
    margin = _n(final.get("projected_margin_home"))
    projected_total = _n(final.get("projected_total"))
    selected_probability = _n(snapshot.get("probability"))
    projection = _m(
        "READY" if final.get("ready") else "PARTIAL",
        projected_home_points=ph,
        projected_away_points=pa,
        projected_margin_home=margin,
        projected_total=projected_total,
        selected_probability=selected_probability,
        reliability=final.get("reliability"),
        model_owner="Kyre certified CFB model",
    )

    drivers: list[dict[str, Any]] = []
    for title, key in (
        ("Scoring offense", "scoring_offense"),
        ("Total offense", "total_offense"),
        ("Scoring defense", "scoring_defense"),
        ("Total defense", "total_defense"),
    ):
        away_value, home_value = _stat(away, key), _stat(home, key)
        if away_value is not None or home_value is not None:
            drivers.append({
                "title": title,
                "away": away_value,
                "home": home_value,
                "source": "NCAA official team stats",
            })
    away_to, away_derived = _turnover_margin_per_game(away)
    home_to, home_derived = _turnover_margin_per_game(home)
    if away_to is not None or home_to is not None:
        drivers.append({
            "title": "Turnover margin / game" if (away_derived or home_derived) else "Turnover margin",
            "away": away_to,
            "home": home_to,
            "source": "NCAA official team stats" + (" • safely normalized by verified games played" if (away_derived or home_derived) else ""),
        })

    matchup = _m(
        "READY" if drivers else "SEMANTIC_EMPTY",
        rows=drivers,
        away_team=snapshot.get("away_team"),
        home_team=snapshot.get("home_team"),
        reason="No Qualifying Games" if not drivers else "",
    )

    market = _c(snapshot.get("market_type")).upper()
    selected = _n(snapshot.get("line"))
    side = _c(snapshot.get("side")).upper()
    scenarios: list[dict[str, Any]] = []
    if selected is not None and market == "SPREAD" and margin is not None and side in {"HOME", "AWAY"}:
        for line in (selected - 4, selected - 2, selected, selected + 2, selected + 4):
            scenarios.append({
                "line": round(line, 1),
                "selected_side_probability": page1_math._spread_probability(margin, line, home_side=side == "HOME"),
                "model_owner": "Kyre certified CFB spread distribution",
            })
    elif selected is not None and market == "TOTAL":
        for line in (selected - 4, selected - 2, selected, selected + 2, selected + 4):
            try:
                result = total_model.project_matchup(game, away, home, line)
            except Exception:
                continue
            if result.get("ready") is True:
                scenarios.append({
                    "line": round(line, 1),
                    "over_probability": _n(result.get("over_probability")),
                    "under_probability": _n(result.get("under_probability")),
                    "model_owner": "Kyre certified CFB total model",
                })

    risks: list[dict[str, Any]] = []
    if final.get("reliability") is not None:
        risks.append({"title": "Model reliability", "value": final.get("reliability")})
    flips: list[dict[str, Any]] = []
    if market == "SPREAD" and selected is not None:
        flips.append({"title": "Spread threshold", "text": f"Recalculate if the verified selected line moves materially away from {selected:+g}."})
    if market == "TOTAL" and selected is not None:
        flips.append({"title": "Total threshold", "text": f"Recalculate if the verified total moves materially away from {selected:g}."})

    return {
        "projection": projection,
        "drivers": _m("READY", items=drivers) if drivers else _semantic("NO_QUALIFYING_GAMES", "No Qualifying Games", items=[]),
        "matchup": matchup,
        "recent_form": _recent_form(away, home),
        "history": _history(away, home),
        "game_environment": _environment(snapshot, game),
        "risks": _m("READY", items=risks),
        "flip_conditions": _m("READY", items=flips),
        "line_scenarios": scenarios,
        "sources": _m("READY", sources=[
            {"provider": "NCAA", "role": "canonical game identity + official team stats + completed-game history"},
            {"provider": "Kyre certified CFB model", "role": "projection + probabilities"},
        ]),
    }


def _prop_analysis(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    game, analysis = _game_context(snapshot)
    home = dict(analysis.get("home") or {})
    away = dict(analysis.get("away") or {})
    team = _c(snapshot.get("player_team"))
    opponent = _c(snapshot.get("opponent"))
    opponent_profile = home if _c(home.get("team")) == opponent else away if _c(away.get("team")) == opponent else {}
    items: list[dict[str, Any]] = []
    for title, key in (("Opponent total defense", "total_defense"), ("Opponent scoring defense", "scoring_defense")):
        value = _stat(opponent_profile, key)
        if value is not None:
            items.append({"title": title, "value": value, "source": "NCAA official team stats"})
    identity_ok = _c(snapshot.get("player_identity_status")) == "VERIFIED" or bool(_c(snapshot.get("player_id")))
    return {
        "projection": _m(
            "PARTIAL",
            selected_hit_probability=_n(snapshot.get("probability")),
            projected_stat=None,
            reason="Page 1 hit probability is preserved; a verified player-history projection is not attached to this selection.",
        ),
        "drivers": _m("READY", items=items) if items else _semantic("NO_QUALIFYING_GAMES", "No Qualifying Games", items=[]),
        "matchup": _m("READY", player_team=team, opponent=opponent, items=items, source="NCAA") if game else _semantic("GAME_IDENTITY_NOT_VERIFIED", "Verified game identity could not be resolved."),
        "recent_form": _semantic("NO_HISTORICAL_SAMPLE", "No Historical Sample from an approved player game-log route.", rows=[]),
        "history": _semantic("NO_PREVIOUS_MEETINGS", "No Previous Meetings are verified for this player/opponent identity.", rows=[]),
        "game_environment": _environment(snapshot, game) if game else _semantic("PREGAME_ENVIRONMENT_PENDING", "Pregame environment verification in progress."),
        "risks": _m("READY", items=[{"title": "Player-history coverage", "value": "Historical player-log enrichment is not yet verified for this selection."}]),
        "flip_conditions": _m("READY", items=[{"title": "Official availability", "text": "Recalculate if an approved official availability observation changes before kickoff."}]),
        "line_scenarios": [],
        "sources": _m("READY" if identity_ok else "PARTIAL", sources=[
            {"provider": "Official team athletics roster", "role": "current player identity"},
            {"provider": "NCAA", "role": "game + opponent context"},
            {"provider": "Kyre Page 1 model", "role": "selected hit probability"},
        ]),
    }


def _freshness(timestamp: Any) -> str:
    text = _c(timestamp)
    if not text:
        return "TIMESTAMP_NOT_REPORTED"
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "TIMESTAMP_UNPARSEABLE"
    return "OBSERVED_TIMESTAMP_PRESENT"


def _quote_from_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    stamp = snapshot.get("market_timestamp")
    return {
        "sportsbook": _c(snapshot.get("sportsbook")),
        "market": _c(snapshot.get("market_type") or snapshot.get("market_key")),
        "side": _c(snapshot.get("side")),
        "selection": _c(snapshot.get("selection")),
        "line": snapshot.get("line"),
        "american_odds": snapshot.get("american_odds"),
        "observed_at_utc": stamp,
        "event_timestamp": snapshot.get("kickoff_iso"),
        "freshness_status": _freshness(stamp),
        "source_provider": _c(snapshot.get("source_provider") or snapshot.get("sportsbook")),
    }


def _append_quote(quotes: list[dict[str, Any]], raw: Mapping[str, Any], *, market: str, side: str, line: Any, price: Any, stamp: Any) -> None:
    if price is None:
        return
    quotes.append({
        "sportsbook": _c(raw.get("sportsbook")),
        "market": market,
        "side": side,
        "selection": None,
        "line": line,
        "american_odds": price,
        "observed_at_utc": stamp,
        "event_timestamp": raw.get("start_time_utc"),
        "freshness_status": _freshness(stamp),
        "source_provider": _c(raw.get("source_provider") or raw.get("sportsbook")),
    })


def _market(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    quotes = [_quote_from_snapshot(snapshot)]
    movement = _semantic(
        "OPENING_LINE_NOT_VERIFIED",
        "Opening Line Not Independently Verified. Current sportsbook observations remain valid and are kept separate from any future opener.",
    )
    if snapshot.get("kind") == "player-prop":
        game = {
            "game_id": snapshot.get("event_id"),
            "official_game_id": snapshot.get("event_id"),
            "away_team": snapshot.get("away_team"),
            "home_team": snapshot.get("home_team"),
            "kickoff_iso": snapshot.get("kickoff_iso"),
        }
        for fetch in (fanduel_props.fetch_fanduel_cfb_player_props, odds_props.fetch_odds_api_cfb_player_props):
            try:
                rows = fetch([game])
            except Exception:
                rows = []
            for row in rows:
                if _c(row.get("player_name")).casefold() != _c(snapshot.get("player_name")).casefold():
                    continue
                if _c(row.get("stat_id") or row.get("market_key")).casefold() != _c(snapshot.get("market_key")).casefold():
                    continue
                _append_quote(
                    quotes,
                    row,
                    market=_c(row.get("stat_id") or row.get("market_key")),
                    side=_c(row.get("side")),
                    line=row.get("line"),
                    price=row.get("price"),
                    stamp=row.get("observed_at_utc"),
                )
    else:
        game, _analysis = _game_context(snapshot)
        if game:
            try:
                matched, _consulted = game_api._market_state([game])
                raw_rows = matched.get(_c(game.get("game_id") or game.get("identity_key")), [])
            except Exception:
                raw_rows = []
            market_type = _c(snapshot.get("market_type")).upper()
            side = _c(snapshot.get("side")).upper()
            for row in raw_rows:
                stamp = row.get("observed_at_utc")
                if market_type == "MONEYLINE":
                    price = row.get("home_moneyline") if side == "HOME" else row.get("away_moneyline")
                    line = None
                elif market_type == "SPREAD":
                    price = row.get("home_spread_price") if side == "HOME" else row.get("away_spread_price")
                    line = row.get("home_spread") if side == "HOME" else row.get("away_spread")
                else:
                    price = row.get("over_price") if side == "OVER" else row.get("under_price")
                    line = row.get("total_line")
                _append_quote(quotes, row, market=market_type, side=side, line=line, price=price, stamp=stamp)

    chosen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for quote in quotes:
        key = (
            _c(quote.get("sportsbook")),
            _c(quote.get("market")).casefold(),
            _c(quote.get("side")).casefold(),
            quote.get("line"),
        )
        incumbent = chosen.get(key)
        if incumbent is None or _c(quote.get("observed_at_utc")) >= _c(incumbent.get("observed_at_utc")):
            chosen[key] = quote
    rows = list(chosen.values())
    selected_line = snapshot.get("line")
    comparable = [quote for quote in rows if quote.get("line") == selected_line or selected_line is None]

    def score(quote: Mapping[str, Any]) -> float:
        number = _n(quote.get("american_odds"))
        return -999999.0 if number is None else number

    best = max(comparable, key=score) if comparable else None
    market_board = _m("READY", quotes=rows, best_available_price=best) if rows else _semantic(
        "MARKET_NOT_POSTED_YET", "Market Not Posted Yet", quotes=[]
    )
    return {"market_board": market_board, "line_movement": movement}


def _implied(price: Any) -> float | None:
    number = _n(price)
    if number is None or number == 0 or (-100 < number < 100):
        return None
    return (-number) / ((-number) + 100) if number < 0 else 100 / (number + 100)


def _fair(probability: Any) -> int | None:
    p = _n(probability)
    if p is None or p <= 0 or p >= 1:
        return None
    return int(round(-100 * p / (1 - p))) if p >= .5 else int(round(100 * (1 - p) / p))


def _decision(snapshot: Mapping[str, Any], analysis: Mapping[str, Any]) -> dict[str, Any]:
    probability = _n(snapshot.get("probability"))
    implied = _implied(snapshot.get("american_odds"))
    edge = None if probability is None or implied is None else probability - implied
    verdict = (
        "DECISION PENDING VERIFIED PRICE" if edge is None
        else "BETTABLE EDGE" if edge >= .03
        else "WATCH" if edge >= 0
        else "PASS AT THIS PRICE"
    )
    verdict_module = _m(
        "READY" if probability is not None and implied is not None else "PARTIAL",
        outcome_confidence=probability,
        market_implied_probability=implied,
        market_value_edge=edge,
        model_fair_price=_fair(probability),
        selected_price=snapshot.get("american_odds"),
        verdict=verdict,
    )
    market_type = _c(snapshot.get("market_type")).upper()
    scenarios = list(analysis.get("line_scenarios") or [])
    if market_type == "MONEYLINE" and probability is not None:
        selected = int(snapshot.get("american_odds") or -110)
        prices = sorted(set((selected - 100, selected - 50, selected, selected + 50, selected + 100)))
        rows = []
        for price in prices:
            market_probability = _implied(price)
            if market_probability is None:
                continue
            rows.append({
                "american_odds": price,
                "implied_probability": market_probability,
                "model_probability": probability,
                "market_value_edge": probability - market_probability,
            })
        lab = _m("READY", lab_type="PRICE", scenarios=rows)
    elif scenarios:
        lab = _m("READY", lab_type="LINE", scenarios=scenarios)
    else:
        lab = _semantic(
            "ALTERNATE_LINE_NOT_OFFERED",
            "No certified alternate-line scenarios are available for this market family.",
            lab_type="LINE",
            scenarios=[],
        )
    return {"kyre_verdict": verdict_module, "line_lab": lab}


def _moneyline_price_flip(lab: Mapping[str, Any]) -> dict[str, str]:
    rows = [dict(row) for row in lab.get("scenarios") or [] if isinstance(row, Mapping)]
    positive = [row for row in rows if (_n(row.get("market_value_edge")) or 0) > 0 and _n(row.get("american_odds")) is not None]
    if not positive:
        return {
            "title": "Price threshold",
            "text": "No positive-value price appears inside the certified price ladder currently tested.",
        }
    # The first positive edge encountered moving from expensive to better prices
    # is a model-supported threshold, not a guessed sportsbook recommendation.
    threshold = min(int(round(float(row["american_odds"]))) for row in positive)
    return {
        "title": "Price threshold",
        "text": f"Positive model value begins at {threshold:+d} or better in the certified price ladder.",
    }


def _availability(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    status = _c(snapshot.get("availability_status"))
    source = _c(snapshot.get("availability_source"))
    stamp = _c(snapshot.get("availability_observed_at"))
    approved = source.casefold().startswith(("official team", "official conference", "rotowire", "sportsdataio")) if source else False
    if status and approved and stamp:
        return _m("READY", player_status=status, source=source, observed_at=stamp, freshness_status=_freshness(stamp))
    return _semantic(
        "OFFICIAL_AVAILABILITY_NOT_VERIFIED",
        "Official availability has not yet been verified for this player identity.",
    )


def build_page2_payload(candidate_id: str, kind: str | None = None, game_date: str | None = None) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    resolved = resolve_candidate(candidate_id, kind, game_date)
    if resolved["status"] != "READY":
        identity_empty = _semantic("IDENTITY_UNAVAILABLE", _c(resolved.get("reason")) or "Exact selection identity could not be verified.")
        return {
            "service": "Kyre Sports API",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "generated_at_utc": generated_at,
            "identity": resolved,
            **{key: dict(identity_empty) for key in MODULES},
        }

    snapshot = dict(resolved["selection_snapshot"])
    analysis = _prop_analysis(snapshot) if snapshot["kind"] == "player-prop" else _game_analysis(snapshot)
    market = _market(snapshot)
    decision = _decision(snapshot, analysis)
    availability = _availability(snapshot) if snapshot["kind"] == "player-prop" else _m(
        "NOT_APPLICABLE",
        semantic_state="NOT_APPLICABLE_TO_GAME_PICK",
        reason="Player availability is not applicable to this game-pick card.",
    )

    flips = dict(analysis.get("flip_conditions") or _m("READY", items=[]))
    flip_items = [dict(row) for row in flips.get("items") or [] if isinstance(row, Mapping)]
    if _c(snapshot.get("market_type")).upper() == "MONEYLINE":
        flip_items.insert(0, _moneyline_price_flip(decision["line_lab"]))
    flips["items"] = flip_items

    out: dict[str, Any] = {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": generated_at,
        "selection_snapshot": snapshot,
        "identity": resolved,
        **decision,
        **market,
        "availability": availability,
    }
    for key in ("projection", "drivers", "matchup", "recent_form", "history", "game_environment", "risks"):
        out[key] = analysis.get(key, _semantic("NOT_VERIFIED", "Verified evidence has not been attached to this module yet."))
    out["flip_conditions"] = flips
    out["sources"] = _m(
        "READY",
        gateway="Kyre Sports API",
        modules={key: out[key].get("status") for key in MODULES if isinstance(out.get(key), Mapping)},
        source_contract=analysis.get("sources"),
        forbidden_providers=list(FORBIDDEN_PROVIDERS),
        provider_complexity_frontend_visible=False,
        null_is_not_zero=True,
        sportsbook_projection_influence=0.0,
        conflict_resolution="field-first; exact-book prices preserved; no sportsbook averaging",
        opening_current_separated=True,
        generated_at_utc=generated_at,
    )
    return out


@router.get("/page2")
def get_page2(
    candidate_id: str = Query(..., min_length=1),
    kind: str | None = Query(default=None),
    game_date: str | None = Query(default=None),
) -> dict[str, Any]:
    return build_page2_payload(candidate_id, kind, game_date)


__all__ = [
    "FORBIDDEN_PROVIDERS", "MODEL_VERSION", "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_decision", "_moneyline_price_flip",
    "_n", "_semantic", "build_page2_payload", "resolve_candidate", "router",
]
