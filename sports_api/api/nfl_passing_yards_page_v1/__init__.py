"""NFL Passing Yards Page 1 S-tier V2 successor overlay.

Loads the frozen V1 implementation under an internal alias, then adds a
book-specific market/decision-support layer without changing projection,
context, distribution, or probability math.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_page_v1.py"
_SPEC = importlib.util.spec_from_file_location("sports_api.api._nfl_passing_yards_page_v1_frozen", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards frozen API implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

# Preserve every frozen public/private symbol unless this successor overrides it below.
for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)

_ORIGINAL_BUILD_PAGE_BUNDLE = _legacy.build_page_bundle
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"
MARKET_PROVIDER_PRIORITY = (
    "FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365",
    "Fanatics Sportsbook", "The Odds API", "OpticOdds", "SportsDataIO",
)
MISSING_TO_ZERO = False
SPORTSBOOK_LINE_AVERAGING = False
_MARKET_HISTORY: dict[tuple[str, str, str], list[dict[str, Any]]] = {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _player_parts(value: Any) -> tuple[str, str]:
    text = re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()
    parts = [part for part in text.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0][:1], parts[0]
    return parts[0][:1], parts[-1]


def _player_matches(expected: Any, candidate: Any) -> bool:
    left = re.sub(r"[^a-z0-9]+", "", _text(expected).casefold())
    right = re.sub(r"[^a-z0-9]+", "", _text(candidate).casefold())
    if left and left == right:
        return True
    lf, ll = _player_parts(expected)
    rf, rl = _player_parts(candidate)
    return bool(ll and ll == rl and lf and lf == rf)


def _book_name(raw_key: Any, raw_title: Any = None) -> str:
    key = _text(raw_key).casefold()
    mapping = {
        "fanduel": "FanDuel", "draftkings": "DraftKings", "betmgm": "BetMGM",
        "williamhill_us": "Caesars", "caesars": "Caesars", "bet365": "bet365",
        "bet365_nj": "bet365", "fanatics": "Fanatics Sportsbook",
        "fanaticssportsbook": "Fanatics Sportsbook",
    }
    return mapping.get(key) or _text(raw_title) or _text(raw_key)


def _the_odds_api_markets(game: dict[str, Any], env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    environment = dict(os.environ if env is None else env)
    api_key = _text(environment.get("THE_ODDS_API_KEY") or environment.get("ODDS_API_KEY"))
    if not api_key:
        return []
    try:
        events_response = requests.get(
            f"{THE_ODDS_API_BASE}/sports/americanfootball_nfl/events",
            params={"apiKey": api_key, "dateFormat": "iso"},
            timeout=_legacy.REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI-NFL/2.0"},
        )
        events_response.raise_for_status()
        events = events_response.json()
        if not isinstance(events, list):
            return []
        away_name = _legacy.TEAM_NAMES.get(game.get("away"), game.get("away"))
        home_name = _legacy.TEAM_NAMES.get(game.get("home"), game.get("home"))
        matches = [
            row for row in events
            if isinstance(row, dict)
            and _text(row.get("away_team")) == _text(away_name)
            and _text(row.get("home_team")) == _text(home_name)
        ]
        if len(matches) != 1:
            return []
        event_id = _text(matches[0].get("id"))
        if not event_id:
            return []
        odds_response = requests.get(
            f"{THE_ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds",
            params={"apiKey": api_key, "regions": "us", "markets": "player_pass_yds", "oddsFormat": "american", "dateFormat": "iso"},
            timeout=_legacy.REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI-NFL/2.0"},
        )
        odds_response.raise_for_status()
        payload = odds_response.json()
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    output: list[dict[str, Any]] = []
    for bookmaker in payload.get("bookmakers") or []:
        if not isinstance(bookmaker, dict):
            continue
        sportsbook = _book_name(bookmaker.get("key"), bookmaker.get("title"))
        if sportsbook not in MARKET_PROVIDER_PRIORITY:
            continue
        for market in bookmaker.get("markets") or []:
            if not isinstance(market, dict) or _text(market.get("key")) != "player_pass_yds":
                continue
            grouped: dict[tuple[str, float], dict[str, Any]] = {}
            for outcome in market.get("outcomes") or []:
                if not isinstance(outcome, dict):
                    continue
                player_name = _text(outcome.get("description"))
                line = _num(outcome.get("point"))
                selection = _text(outcome.get("name")).casefold()
                price = _num(outcome.get("price"))
                if not player_name or line is None or price is None or selection not in {"over", "under"}:
                    continue
                row = grouped.setdefault((player_name, line), {
                    "player_name": player_name, "sportsbook": sportsbook,
                    "market": "Passing Yards", "line": line,
                })
                row[f"{selection}_odds"] = price
            for row in grouped.values():
                if row.get("over_odds") is None or row.get("under_odds") is None:
                    continue
                row["source_timestamp"] = _text(market.get("last_update") or bookmaker.get("last_update")) or _legacy._utc_now()
                row["provider_event_id"] = event_id
                row["source_provider"] = "The Odds API"
                output.append(row)
    return output


def collect_market_observations(game: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for raw in _legacy._fanduel_markets(game):
        row = dict(raw)
        row["sportsbook"] = _text(row.get("sportsbook")) or "FanDuel"
        row["source_provider"] = "FanDuel direct"
        observations.append(row)
    observations.extend(_the_odds_api_markets(game))
    game_id = _text(game.get("game_id") or game.get("source_game_id"))
    for row in observations:
        player_key = re.sub(r"[^a-z0-9]+", "", _text(row.get("player_name")).casefold())
        sportsbook = _text(row.get("sportsbook"))
        if not game_id or not player_key or not sportsbook:
            continue
        key = (game_id, player_key, sportsbook)
        history = _MARKET_HISTORY.setdefault(key, [])
        fingerprint = (row.get("line"), row.get("over_odds"), row.get("under_odds"))
        prior = None if not history else (history[-1].get("line"), history[-1].get("over_odds"), history[-1].get("under_odds"))
        if fingerprint != prior:
            history.append(dict(row))
            del history[:-8]
    flattened: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in observations:
        player_key = re.sub(r"[^a-z0-9]+", "", _text(row.get("player_name")).casefold())
        key = (game_id, player_key, _text(row.get("sportsbook")))
        for item in _MARKET_HISTORY.get(key) or [row]:
            identity = (_text(item.get("player_name")).casefold(), _text(item.get("sportsbook")), item.get("line"), item.get("over_odds"), item.get("under_odds"), _text(item.get("source_timestamp")))
            if identity not in seen:
                seen.add(identity)
                flattened.append(dict(item))
    return flattened


def build_market_snapshot(observations: list[dict[str, Any]], *, qb_name: str, projection_yards: Any = None) -> dict[str, Any]:
    rows = [
        dict(row) for row in observations
        if _player_matches(qb_name, row.get("player_name"))
        and _num(row.get("line")) is not None
        and _num(row.get("over_odds")) is not None
        and _num(row.get("under_odds")) is not None
    ]
    if not rows:
        return {"ready": False, "reason": "No verified two-way Passing Yards market available", "books": [], "line_movement": {"ready": False}}
    rows.sort(key=lambda row: _text(row.get("source_timestamp")))
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[_text(row.get("sportsbook"))] = row
    priority = {name: index for index, name in enumerate(MARKET_PROVIDER_PRIORITY)}
    books = sorted(latest.values(), key=lambda row: (priority.get(_text(row.get("sportsbook")), 999), _text(row.get("sportsbook"))))
    primary = dict(books[0])
    sportsbook = _text(primary.get("sportsbook"))
    same_book = [row for row in rows if _text(row.get("sportsbook")) == sportsbook]
    movement: dict[str, Any] = {"ready": False, "sportsbook": sportsbook, "open_line": None, "current_line": primary.get("line"), "delta": None}
    if len(same_book) >= 2:
        opening = float(same_book[0]["line"])
        current = float(same_book[-1]["line"])
        movement = {"ready": True, "sportsbook": sportsbook, "open_line": opening, "current_line": current, "delta": round(current - opening, 3)}
    projection = _num(projection_yards)
    line = _num(primary.get("line"))
    primary.update({"ready": True, "provider": sportsbook, "sportsbook": sportsbook, "books": books, "line_movement": movement})
    primary["projection_edge_yards"] = projection - line if projection is not None and line is not None else None
    return primary


def _recent_hit_rate(player: dict[str, Any], *, side: str, line: float) -> dict[str, Any]:
    games = list((player.get("profile") or {}).get("recent_games") or [])[:5]
    yards = [value for value in (_num(row.get("passing_yards")) for row in games) if value is not None]
    hits = sum(1 for value in yards if (value > line if side == "OVER" else value < line))
    return {"hits": hits, "sample": len(yards), "rate": hits / len(yards) if yards else None, "yards": yards}


def build_bet_thesis(player: dict[str, Any]) -> dict[str, Any]:
    market = player.get("market") or {}
    line = _num(market.get("line"))
    if not market.get("ready", bool(line is not None)) or line is None:
        return {"ready": False, "side": "NO STRONG SIDE", "line": None, "strength": "CHECK", "positive_factor_count": 0, "factors": [], "recent_hit_rate": {"hits": 0, "sample": 0, "rate": None, "yards": []}, "narrative": "No verified two-way Passing Yards market is available, so Kyre Sports API will not force an Over or Under thesis."}
    evaluation = player.get("market_evaluation") or {}
    projection = _num((player.get("context_projection") or {}).get("context_projection_yards"))
    over_probability = _num(evaluation.get("model_over_probability"))
    under_probability = _num(evaluation.get("model_under_probability"))
    lean = _text(evaluation.get("lean")).upper()
    side = lean if lean in {"OVER", "UNDER"} else ("OVER" if projection is not None and projection - line >= 5 else ("UNDER" if projection is not None and line - projection >= 5 else "NO STRONG SIDE"))
    if side not in {"OVER", "UNDER"}:
        return {"ready": False, "side": "NO STRONG SIDE", "line": line, "strength": "CHECK", "positive_factor_count": 0, "factors": [], "recent_hit_rate": _recent_hit_rate(player, side="OVER", line=line), "narrative": f"Verified market line {line:.1f} is available, but the evidence does not support a strong Over or Under side."}
    hit = _recent_hit_rate(player, side=side, line=line)
    factors: list[dict[str, Any]] = []
    def add(key: str, label: str, positive: bool, detail: str) -> None:
        factors.append({"key": key, "label": label, "positive": bool(positive), "detail": detail})
    edge = projection - line if projection is not None else None
    if edge is not None:
        side_edge = edge if side == "OVER" else -edge
        add("projection_edge", "Projection edge", side_edge >= 5, f"{side_edge:+.1f} yards versus the exact market line")
    if hit["sample"]:
        add("recent_hit_rate", "Recent hit rate", (hit.get("rate") or 0) >= 0.6, f"{hit['hits']} of last {hit['sample']} games")
    defense = player.get("pass_defense") or {}
    rank = _num(defense.get("rank"))
    if rank is not None:
        add("pass_defense", "Pass defense", rank >= 20 if side == "OVER" else rank <= 10, f"opponent ranks {int(rank)} in pass-yards defense")
    pressure = _num((player.get("context_projection") or {}).get("pressure_adjustment_yards"))
    if pressure is not None:
        add("pressure", "Pressure", pressure > -5 if side == "OVER" else pressure <= -8, f"{pressure:+.1f}-yard pressure adjustment")
    availability = player.get("availability") or {}
    if availability.get("verified"):
        receivers = _text(availability.get("receivers")).upper()
        secondary = _text(availability.get("opponent_secondary")).upper()
        offensive_line = _text(availability.get("offensive_line")).upper()
        if receivers:
            add("receivers", "Receiver availability", receivers == ("HEALTHY" if side == "OVER" else "LIMITED"), receivers)
        if secondary:
            add("secondary", "Opponent secondary", secondary == ("DEPLETED" if side == "OVER" else "HEALTHY"), secondary)
        if offensive_line:
            add("offensive_line", "Offensive line", offensive_line == ("STABLE" if side == "OVER" else "LIMITED"), offensive_line)
    environment = player.get("game_environment") or {}
    if environment.get("verified") and _text(environment.get("game_script")).casefold() == "competitive":
        add("game_script", "Game script", side == "OVER", "Competitive game script")
    history = player.get("qb_vs_team_history") or {}
    history_average = _num(history.get("avg_passing_yards"))
    if history.get("available") and history_average is not None:
        add("direct_history", "QB vs defense history", history_average > line if side == "OVER" else history_average < line, f"{history_average:.1f} average passing yards")
    positives = sum(1 for factor in factors if factor["positive"])
    probability = over_probability if side == "OVER" else under_probability
    strength = "STRONG" if positives >= 5 and probability is not None and probability >= 0.62 and hit["sample"] >= 3 else ("MODERATE" if positives >= 3 else "LEAN")
    qb = _text(player.get("qb_name")) or "The quarterback"
    threshold = "topped" if side == "OVER" else "stayed below"
    sentences = [f"{qb} has {threshold} {line:.1f} passing yards in {hit['hits']} of his last {hit['sample']} games." if hit["sample"] else f"Verified recent hit-rate history against {line:.1f} is unavailable."]
    if rank is not None:
        if side == "OVER" and rank >= 20:
            allowed = _num(defense.get("pass_yards_allowed_per_game"))
            allowed_text = f"{allowed:.1f}" if allowed is not None else "an unverified number of"
            sentences.append(f"The opponent pass defense ranks {int(rank)}th and is allowing {allowed_text} passing yards per game, which strengthens the matchup.")
        elif side == "UNDER" and rank <= 10:
            sentences.append(f"The opponent owns a top-{int(rank)} pass defense, making efficient yardage harder to sustain.")
    if pressure is not None:
        if side == "OVER":
            sentences.append(f"The {pressure:+.1f}-yard pressure adjustment keeps pressure from becoming the primary reason to fade the passing volume." if pressure > -5 else f"Pressure is a real counterweight at {pressure:+.1f} yards of adjustment.")
        else:
            sentences.append(f"Pressure creates a {pressure:+.1f}-yard adjustment, adding meaningful downside to the passing projection." if pressure <= -8 else f"Pressure is not a major Under driver at {pressure:+.1f} yards of adjustment.")
    if availability.get("verified"):
        receivers = _text(availability.get("receivers")).upper()
        secondary = _text(availability.get("opponent_secondary")).upper()
        if receivers == "HEALTHY":
            sentences.append("The receivers are verified healthy, supporting the available passing options.")
        elif receivers == "LIMITED":
            sentences.append("The receivers are verified limited, reducing the available passing options.")
        if secondary == "DEPLETED":
            sentences.append("The opponent secondary is verified depleted, which adds another favorable passing factor.")
    if environment.get("verified") and _text(environment.get("game_script")).casefold() == "competitive":
        sentences.append("A competitive game script supports sustained passing volume." if side == "OVER" else "A competitive game script is a counterweight to the Under and is included in the risk balance.")
    sentences.append(f"Taken together, the verified evidence favors the {side.title()} {line:.1f}." if strength in {"STRONG", "MODERATE"} else f"The evidence only supports a cautious {side.title()} lean at {line:.1f}.")
    return {"ready": True, "side": side, "line": line, "strength": strength, "positive_factor_count": positives, "factors": factors, "recent_hit_rate": hit, "narrative": " ".join(sentences)}


def build_game_environment(game: dict[str, Any], *, side: str) -> dict[str, Any]:
    venue = _text(game.get("stadium")) or None
    roof = _text(game.get("roof")) or None
    surface = _text(game.get("surface")) or None
    temperature = _num(game.get("temp"))
    wind = _num(game.get("wind"))
    rest = _num(game.get(f"{side}_rest"))
    verified = any(value is not None and value != "" for value in (venue, roof, surface, temperature, wind, rest))
    indoor = _text(roof).casefold() in {"dome", "closed", "indoors", "indoor"}
    weather = "INDOOR" if indoor else ("VERIFIED CONDITIONS" if temperature is not None or wind is not None else "CHECK")
    return {"verified": verified, "venue": venue, "roof": roof, "surface": surface, "temperature_f": temperature, "wind_mph": wind, "weather": weather, "rest_days": int(rest) if rest is not None and rest.is_integer() else rest, "game_script": None, "source": "NFLverse schedule" if verified else None, "reason": None if verified else "Verified NFL game-environment fields unavailable for this request"}


def build_page1_decision_support(player: dict[str, Any], *, game_date: str) -> dict[str, Any]:
    thesis = build_bet_thesis(player)
    market = player.get("market") or {}
    projection = _num((player.get("context_projection") or {}).get("context_projection_yards"))
    line = _num(market.get("line"))
    recent = [value for value in (_num(row.get("passing_yards")) for row in list((player.get("profile") or {}).get("recent_games") or [])[:5]) if value is not None]
    risks: list[str] = []
    if not market.get("ready", bool(line is not None)):
        risks.append("Verified market unavailable")
    if _text((player.get("distribution") or {}).get("confidence")).upper() == "LOW":
        risks.append("Low model confidence")
    if len(recent) < 5:
        risks.append(f"Limited recent sample ({len(recent)} games)")
    sigma = _num((player.get("distribution") or {}).get("sigma_yards"))
    if sigma is not None and sigma >= 70:
        risks.append("High recent passing-yard variance")
    availability = dict(player.get("availability") or {"verified": False, "status": "CHECK", "reason": "Verified injury/availability feed unavailable"})
    environment = dict(player.get("game_environment") or {"verified": False, "status": "CHECK", "reason": "Verified game-condition feed unavailable"})
    if not availability.get("verified"):
        risks.append("Availability verification pending")
    if not environment.get("verified"):
        risks.append("Environment verification pending")
    movement = dict(market.get("line_movement") or {"ready": False})
    if line is not None and not movement.get("ready"):
        risks.append("Same-book line history building")
    edge = projection - line if projection is not None and line is not None else None
    return {
        "quick_verdict": {"side": thesis.get("side"), "line": line, "sportsbook": market.get("sportsbook"), "projection": projection, "edge_yards": edge, "confidence": (player.get("distribution") or {}).get("confidence"), "strength": thesis.get("strength")},
        "thesis": thesis, "recent_form": {"yards": recent, "sample": len(recent)},
        "line_movement": movement, "book_comparison": list(market.get("books") or []),
        "availability": availability, "environment": environment, "risk_flags": risks,
        "page2": {"date": game_date},
    }


def _schedule_environment(game: dict[str, Any]) -> dict[str, Any]:
    try:
        frame = _legacy._load_games_csv()
        source_id = _text(game.get("source_game_id") or game.get("game_id")).replace("kyre:nfl:game:", "")
        matches = frame[frame["game_id"].astype(str) == source_id]
        if len(matches) == 1:
            return matches.iloc[0].to_dict()
    except Exception:
        pass
    return {}


def _market_evaluation(player: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    if not market.get("ready"):
        return {"ready": False, "grade_ready": False, "lean": "MARKET PENDING", "grade": "CHECK", "reason": "No verified two-way Passing Yards market available", "sportsbook_projection_influence": 0.0}
    return _legacy.market_model.evaluate_market(
        player.get("distribution") or {}, market.get("line"), market.get("over_odds"), market.get("under_odds"),
        source=market.get("sportsbook") or "", market_timestamp=market.get("source_timestamp") or "",
    )


def build_page_bundle(target_date: str | None = None) -> dict[str, Any]:
    bundle = _ORIGINAL_BUILD_PAGE_BUNDLE(target_date)
    if not bundle.get("ready"):
        return bundle
    game = bundle.get("game") or {}
    observations = collect_market_observations(game)
    schedule = _schedule_environment(game)
    for player in bundle.get("players") or []:
        projection = (player.get("context_projection") or {}).get("context_projection_yards")
        snapshot = build_market_snapshot(observations, qb_name=_text(player.get("qb_name")), projection_yards=projection)
        player["market"] = snapshot if snapshot.get("ready") else None
        player["market_evaluation"] = _market_evaluation(player, snapshot)
        player["availability"] = {"verified": False, "status": "CHECK", "reason": "Official injury/availability data not verified for this request"}
        player["game_environment"] = build_game_environment(schedule, side=_text(player.get("side")) or "away")
        player["page1_decision_support"] = build_page1_decision_support(player, game_date=_text(game.get("date")))
    providers = sorted({_text(row.get("source_provider") or row.get("sportsbook")) for row in observations if _text(row.get("source_provider") or row.get("sportsbook"))})
    provenance = bundle.setdefault("provenance", {})
    provenance["market"] = {"provider": " + ".join(providers) or "No verified market source", "source_timestamp": max([_text(row.get("source_timestamp")) for row in observations], default=""), "observations": len(observations)}
    routing = bundle.setdefault("routing", {})
    routing.update({"gateway": "Kyre Sports API", "canonical_ids": True, "sportsbook_line_averaging": False, "missing_to_zero": False, "sportsbook_projection_influence": 0.0, "market_provider_priority": list(MARKET_PROVIDER_PRIORITY)})
    return bundle


# FastAPI's frozen endpoint resolves build_page_bundle from its module globals at call time.
_legacy.build_page_bundle = build_page_bundle

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "MARKET_PROVIDER_PRIORITY", "build_bet_thesis", "build_game_environment",
    "build_market_snapshot", "build_page1_decision_support", "build_page_bundle",
    "collect_market_observations", "router", "page",
})
