"""NBA Spread Step 5 — fail-closed Sharp Money Game feature.

Sharp Money is defined only from exact Step-3 schedule matches with verified
public-bet percentage, money percentage, and positive authoritative bet volume.
No arbitrary divergence or volume threshold is invented. Current universal
routing fails closed when the exact PUBLIC_BET_COUNT field is unavailable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from devsystem.universal_sports_field_router_v1 import load_router_policy, route_field
from devsystem.universal_sports_provider_registry_v1 import load_registry

MODEL_VERSION = "NBA_SPREAD_STEP5_SHARP_MONEY_V1"
SHARP_MONEY_LABEL = "💰 Sharp Money Game"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_ACTIVATE_SHARP_MONEY = True
MAY_ACTIVATE_INJURIES = False
MAY_ACTIVATE_RANKING = False
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}

_ROOT = Path(__file__).resolve().parent
_PROVIDER_REGISTRY_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"
_FIELD_ROUTER_PATH = _ROOT / "devsystem" / "contracts" / "universal-sports-field-router-v1.json"
_ROUTE_FIELDS = ("public_bet_percentage", "money_percentage", "public_bet_count")


def _tricode(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _percent(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 100 else None


def _valid_splits(row: Mapping[str, object]) -> tuple[int, int, int, int] | None:
    away_bets = _percent(row.get("away_bet_pct"))
    home_bets = _percent(row.get("home_bet_pct"))
    away_money = _percent(row.get("away_money_pct"))
    home_money = _percent(row.get("home_money_pct"))
    if None in {away_bets, home_bets, away_money, home_money}:
        return None
    assert away_bets is not None and home_bets is not None
    assert away_money is not None and home_money is not None
    if away_bets + home_bets != 100 or away_money + home_money != 100:
        return None
    return away_bets, home_bets, away_money, home_money


def _schedule_index(
    schedule_games: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    out: dict[tuple[str, str], Mapping[str, object]] = {}
    for game in schedule_games:
        if str(game.get("status") or "").strip().upper() not in ELIGIBLE_STATES:
            continue
        away = _tricode(game.get("away_tricode"))
        home = _tricode(game.get("home_tricode"))
        if away and home:
            out[(away, home)] = game
    return out


def select_sharp_money_game(
    rows: Iterable[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
) -> dict:
    """Select the unique largest positive money%-minus-bet% divergence.

    Only exact upcoming/delayed Step-3 schedule matches are eligible. A matched
    row without positive authoritative volume makes the ranking unavailable,
    because silently ranking around missing volume would fabricate confidence.
    """
    schedule = _schedule_index(schedule_games)
    matched: list[tuple[int, Mapping[str, object], Mapping[str, object], str, int, int]] = []
    matched_any = False

    for row in rows:
        away = _tricode(row.get("away_tricode"))
        home = _tricode(row.get("home_tricode"))
        if not away or not home:
            continue
        game = schedule.get((away, home))
        if game is None:
            continue
        matched_any = True

        splits = _valid_splits(row)
        if splits is None:
            return {"verification": "UNAVAILABLE", "diagnostic_state": "INVALID_BETTING_SPLITS"}
        volume = _positive_int(row.get("bet_count"))
        if volume is None:
            return {"verification": "UNAVAILABLE", "diagnostic_state": "SHARP_VOLUME_UNVERIFIED"}

        away_bets, home_bets, away_money, home_money = splits
        away_gap = away_money - away_bets
        home_gap = home_money - home_bets
        if away_gap <= 0 and home_gap <= 0:
            continue
        if away_gap >= home_gap:
            sharp_side, sharp_bets, sharp_money, gap = away, away_bets, away_money, away_gap
        else:
            sharp_side, sharp_bets, sharp_money, gap = home, home_bets, home_money, home_gap
        matched.append((gap, row, game, sharp_side, sharp_bets, sharp_money))

    if not matched:
        diagnostic = "NO_SHARP_MONEY_DIVERGENCE" if matched_any else "NO_VERIFIED_SCHEDULE_MATCH"
        return {"verification": "UNAVAILABLE", "diagnostic_state": diagnostic}

    top_gap = max(item[0] for item in matched)
    winners = [item for item in matched if item[0] == top_gap]
    if len(winners) != 1:
        return {"verification": "UNAVAILABLE", "diagnostic_state": "AMBIGUOUS_SHARP_MONEY_GAME"}

    gap, row, game, sharp_side, sharp_bets, sharp_money = winners[0]
    away = str(game.get("away_tricode") or "").upper()
    home = str(game.get("home_tricode") or "").upper()
    sharp_name = str(
        game.get("away_name") if sharp_side == away else game.get("home_name") or sharp_side
    )
    return {
        "verification": "VERIFIED",
        "away_tricode": away,
        "home_tricode": home,
        "away_name": str(game.get("away_name") or away),
        "home_name": str(game.get("home_name") or home),
        "game_date_phoenix": str(game.get("game_date_phoenix") or ""),
        "tip_phoenix": str(game.get("tip_phoenix") or ""),
        "status": str(game.get("status") or "UPCOMING"),
        "sharp_side_tricode": sharp_side,
        "sharp_side_name": sharp_name,
        "sharp_bet_pct": sharp_bets,
        "sharp_money_pct": sharp_money,
        "sharp_gap_pct": gap,
        "bet_count": int(row["bet_count"]),
    }


def resolve_sharp_money_routes(
    *,
    registry: Mapping[str, Any] | None = None,
    router_policy: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    resolved_registry = dict(registry) if registry is not None else load_registry(_PROVIDER_REGISTRY_PATH)
    resolved_policy = (
        dict(router_policy) if router_policy is not None else load_router_policy(_FIELD_ROUTER_PATH)
    )
    return {
        field: route_field(resolved_registry, resolved_policy, sport="nba", field=field)
        for field in _ROUTE_FIELDS
    }


def load_sharp_money_feature(schedule_games: Sequence[Mapping[str, object]]) -> dict:
    """Fail closed until all three exact semantic fields can be verified.

    Step 5 does not scrape or synthesize a substitute volume signal. The current
    frozen universal registry has no configured NBA PUBLIC_BET_COUNT route, so
    production correctly reports the feature unavailable instead of guessing.
    """
    del schedule_games
    try:
        routes = resolve_sharp_money_routes()
    except (OSError, TypeError, ValueError):
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SHARP_ROUTE_UNAVAILABLE",
            "fabrication": False,
            "page_wide_source_authority": False,
        }

    volume_route = routes["public_bet_count"]
    if volume_route.get("status") != "ROUTE_READY":
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SHARP_VOLUME_ROUTE_UNAVAILABLE",
            "semantic_metric_id": "PUBLIC_BET_COUNT",
            "route_id": volume_route.get("route_id"),
            "eligible_provider_ids": list(volume_route.get("eligible_provider_ids") or []),
            "blocked_providers": list(volume_route.get("blocked_providers") or []),
            "active_provider_ids": list(volume_route.get("active_provider_ids") or []),
            "fabrication": False,
            "page_wide_source_authority": False,
        }

    for field in ("public_bet_percentage", "money_percentage"):
        if routes[field].get("status") != "ROUTE_READY":
            return {
                "verification": "UNAVAILABLE",
                "diagnostic_state": "SHARP_PERCENTAGE_ROUTE_UNAVAILABLE",
                "fabrication": False,
                "page_wide_source_authority": False,
            }

    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": "SHARP_OBSERVATIONS_NOT_VERIFIED",
        "fabrication": False,
        "page_wide_source_authority": False,
    }


__all__ = [
    "MODEL_VERSION",
    "SHARP_MONEY_LABEL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_ACTIVATE_SHARP_MONEY",
    "MAY_ACTIVATE_INJURIES",
    "MAY_ACTIVATE_RANKING",
    "load_sharp_money_feature",
    "resolve_sharp_money_routes",
    "select_sharp_money_game",
]
