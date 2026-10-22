"""Kyre Sports API CFB Top Picks Page 1.

The application receives one normalized ranked board from this route. Schedule,
team evidence, market fallback, and model analysis stay server-side. Market
quotes are preserved book-by-book and never blended into projection inputs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE1 API V1 • KYRE SPORTS API"
SCHEMA_VERSION = "cfb_top_picks_page1_v1"
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


def _canonical_event_id(game: Mapping[str, Any]) -> str:
    """Use only normalized NCAA/Kyre identity fields for board uniqueness."""
    return _clean(game.get("game_id") or game.get("identity_key"))


def _american_implied_probability(price: Any) -> float | None:
    odds = _float(price)
    if odds is None or odds == 0:
        return None
    if odds < 0:
        return (-odds) / ((-odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _fair_price(probability: float) -> int | None:
    p = _float(probability)
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _best_quote(
    quotes: list[Mapping[str, Any]], side: str
) -> dict[str, Any] | None:
    key = f"{side}_price"
    candidates: list[dict[str, Any]] = []
    for quote in quotes:
        sportsbook = _clean(quote.get("sportsbook"))
        price = _float(quote.get(key))
        if not sportsbook or price is None or price == 0:
            continue
        candidates.append(
            {
                "sportsbook": sportsbook,
                "price": int(round(price)),
                "market": "moneyline",
                "updated_at": _clean(quote.get("observed_at_utc")) or None,
                "provider_event_id": _clean(quote.get("provider_event_id")) or None,
                "provider_market_id": _clean(quote.get("provider_market_id")) or None,
            }
        )
    if not candidates:
        return None
    # For American odds, the numerically highest quote is always the better
    # payout for the bettor: -105 beats -110 and +125 beats +115.
    return max(candidates, key=lambda row: int(row["price"]))


def _edge_tier(edge_pp: float | None) -> str:
    if edge_pp is None:
        return "MARKET PENDING"
    if edge_pp >= 8.0:
        return "ELITE EDGE"
    if edge_pp >= 5.0:
        return "STRONG EDGE"
    if edge_pp >= 2.5:
        return "PLAYABLE"
    if edge_pp >= 0:
        return "LEAN"
    return "MARKET AHEAD"


def _why_line(team: str, probability: float, reliability: float | None) -> str:
    reliability_text = (
        f" with {reliability * 100:.0f}% model reliability"
        if reliability is not None
        else ""
    )
    return (
        f"Kyre model makes {team} the winner at {probability * 100:.0f}%"
        f"{reliability_text}; sportsbook prices are market context only."
    )


def rank_moneyline_games(
    games: list[Mapping[str, Any]],
    analyses: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Return the strongest unique model-ready moneyline selections."""
    cap = max(0, min(MAX_LIMIT, int(limit)))
    unique_games: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for game in games:
        event_id = _canonical_event_id(game)
        if not event_id or event_id in seen:
            continue
        seen.add(event_id)
        unique_games.append(game)

    candidates: list[dict[str, Any]] = []
    for game in unique_games:
        event_id = _canonical_event_id(game)
        analysis = dict(analyses.get(event_id) or {})
        final = dict(analysis.get("final") or {})
        if not final.get("ready") or not final.get("final_pick_ready"):
            continue

        side = _clean(final.get("winner_side")).lower()
        team = _clean(final.get("winner_team"))
        probability = _float(final.get("winner_probability_final"))
        if side not in {"away", "home"} or not team or probability is None:
            continue
        if not 0.5 < probability < 1.0:
            continue

        reliability = _float(final.get("reliability"))
        if reliability is not None:
            reliability = max(0.0, min(1.0, reliability))
        quotes = [
            dict(row) for row in list(game.get("market_quotes") or [])
            if isinstance(row, Mapping)
        ]
        best_price = _best_quote(quotes, side)
        implied = (
            _american_implied_probability(best_price.get("price"))
            if best_price is not None
            else None
        )
        edge_pp = (
            (probability - implied) * 100.0
            if implied is not None
            else None
        )
        fair_raw = final.get(f"{side}_fair_moneyline")
        fair = _float(fair_raw)
        fair_price = int(round(fair)) if fair is not None else _fair_price(probability)

        selected_side_team = _clean(game.get(f"{side}_team"))
        if selected_side_team and selected_side_team.casefold() != team.casefold():
            # Fail closed on side/team contamination rather than silently
            # attaching a model pick to the wrong event participant.
            continue

        candidates.append(
            {
                "event_id": event_id,
                "away": _clean(game.get("away_team")),
                "home": _clean(game.get("home_team")),
                "away_abbr": _clean(game.get("away_abbr") or game.get("away_abbreviation")),
                "home_abbr": _clean(game.get("home_abbr") or game.get("home_abbreviation")),
                "away_logo": _clean(game.get("away_logo") or game.get("away_logo_url")) or None,
                "home_logo": _clean(game.get("home_logo") or game.get("home_logo_url")) or None,
                "kickoff_iso": _clean(game.get("kickoff_iso")) or None,
                "broadcast": _clean(game.get("broadcast")) or None,
                "market": "MONEYLINE",
                "pick": team,
                "pick_side": side,
                "model_probability": probability,
                "model_probability_pct": round(probability * 100.0, 1),
                "model_reliability": reliability,
                "model_fair_price": fair_price,
                "best_price": best_price,
                "market_implied_probability": implied,
                "market_implied_probability_pct": round(implied * 100.0, 1) if implied is not None else None,
                "model_edge_pp": round(edge_pp, 1) if edge_pp is not None else None,
                "edge_tier": _edge_tier(edge_pp),
                "sportsbook_quote_count": len(quotes),
                "why": _why_line(team, probability, reliability),
            }
        )

    candidates.sort(
        key=lambda row: (
            -float(row["model_probability"]),
            -float(row.get("model_reliability") or 0.0),
            str(row["event_id"]),
        )
    )
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(candidates[:cap], start=1):
        item = dict(row)
        item["rank"] = rank
        out.append(item)
    return out


def _analyze_games(
    games: list[dict[str, Any]], selected_day: str, analyzer: Callable[[Mapping[str, Any], str], Mapping[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    analyses: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}

    def run(game: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        gid = _canonical_event_id(game)
        return gid, dict(analyzer(game, selected_day))

    workers = min(8, max(1, len(games)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, game): game for game in games}
        for future in as_completed(futures):
            game = futures[future]
            gid = _canonical_event_id(game)
            try:
                found_id, analysis = future.result()
                if found_id:
                    analyses[found_id] = analysis
            except Exception as exc:
                failures[gid or "unknown"] = type(exc).__name__
    return analyses, failures


def build_page1_payload(
    *,
    game_date: str | None = None,
    limit: int = DEFAULT_LIMIT,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    # Import the certified Moneyline Kyre API owner lazily so the pure ranking
    # contract remains unit-testable without opening network/provider paths.
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
        gid = _canonical_event_id(game)
        if not gid or gid in seen:
            continue
        seen.add(gid)
        unique.append(game)

    market_map, consulted = moneyline_api._market_state(unique)
    games = [
        moneyline_api._public_game(game, market_map.get(_canonical_event_id(game), []))
        for game in unique
    ]
    analyses, failures = _analyze_games(games, selected_day, moneyline_api._analysis)
    picks = rank_moneyline_games(games, analyses, limit=limit)

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
            "consensus_averaging": False,
            "fabrication": False,
            "null_to_zero": False,
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
    "rank_moneyline_games",
    "router",
]
