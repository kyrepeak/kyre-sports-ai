"""NFL Rushing Yards runtime data-truth overlay.

This module prevents direct-book transport/parser/mapping failures from being
collapsed into MARKET_NOT_POSTED. It is deliberately generic at the source-chain
boundary: a primary provider may fail, an approved fallback may satisfy the
field, and only an explicitly VERIFIED_NOT_POSTED source result may become a
true unposted market state.

No value is fabricated and sportsbook data never influences Kyre projections.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import re
from typing import Any, Callable, Mapping, Sequence

from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as direct_book
from sports_api.nfl_data_nflverse_v1 import canonical_team_abbr

VERSION = "NFL_RUSHING_YARDS_DATA_TRUTH_V1"
PRIMARY_PROVIDER = "FanDuel"
DEFAULT_MARKET_BUDGET_SECONDS = 4.0
DEFAULT_CALL_TIMEOUT_SECONDS = 2

# Runtime may register additional approved providers without changing the page.
# Each collector must accept (game, timeout=...) and return either a list of
# canonical observations or a structured {state, observations} result.
APPROVED_FALLBACK_COLLECTORS: tuple[tuple[str, Callable[..., Any]], ...] = ()

_FAILURE_STATES = {
    "PROVIDER_FETCH_FAILURE",
    "PARSER_FAILURE",
    "EVENT_MAPPING_FAILURE",
    "PLAYER_MAPPING_FAILURE",
    "MARKET_MAPPING_FAILURE",
    "STALE_DATA",
    "SOURCE_CONFLICT",
    "ALL_SOURCES_UNAVAILABLE",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _bundle(provider: str, state: str, observations: Sequence[Mapping[str, Any]] | None = None, *, reason: str = "", evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "provider": _text(provider),
        "state": _text(state).upper(),
        "observations": [dict(row) for row in (observations or []) if isinstance(row, Mapping)],
        "reason": _text(reason),
        "evidence": dict(evidence or {}),
        "fabricated": False,
    }


def _normalize_provider_result(provider: str, raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        state = _text(raw.get("state")).upper()
        observations = [dict(row) for row in (raw.get("observations") or []) if isinstance(row, Mapping)]
        if state == "AVAILABLE" and observations:
            return _bundle(provider, "AVAILABLE", observations, reason=_text(raw.get("reason")), evidence=raw.get("evidence") if isinstance(raw.get("evidence"), Mapping) else None)
        if state == "VERIFIED_NOT_POSTED" and not observations:
            return _bundle(provider, "VERIFIED_NOT_POSTED", [], reason=_text(raw.get("reason")), evidence=raw.get("evidence") if isinstance(raw.get("evidence"), Mapping) else None)
        if state in _FAILURE_STATES:
            return _bundle(provider, state, observations, reason=_text(raw.get("reason")), evidence=raw.get("evidence") if isinstance(raw.get("evidence"), Mapping) else None)
        if observations:
            return _bundle(provider, "AVAILABLE", observations, reason=_text(raw.get("reason")))
        return _bundle(provider, "MARKET_MAPPING_FAILURE", [], reason="provider returned an unverified empty result")
    if isinstance(raw, list):
        observations = [dict(row) for row in raw if isinstance(row, Mapping)]
        if observations:
            return _bundle(provider, "AVAILABLE", observations)
        # A legacy empty list contains no evidence that the sportsbook did not
        # post the market. Treat it as an unresolved mapping/parse outcome.
        return _bundle(provider, "MARKET_MAPPING_FAILURE", [], reason="legacy collector returned empty without absence proof")
    return _bundle(provider, "PARSER_FAILURE", [], reason=f"unexpected provider result type: {type(raw).__name__}")


def _call_provider(provider: str, collector: Callable[..., Any], game: Mapping[str, Any], timeout: int) -> dict[str, Any]:
    try:
        return _normalize_provider_result(provider, collector(game, timeout=int(timeout)))
    except Exception as exc:
        return _bundle(
            provider,
            "PROVIDER_FETCH_FAILURE",
            [],
            reason=f"{type(exc).__name__}: {_text(exc)}"[:300],
            evidence={"exception_type": type(exc).__name__},
        )


def _apply_fallbacks(game: Mapping[str, Any], current: dict[str, Any], *, timeout: int, fallback_collectors: Sequence[tuple[str, Callable[..., Any]]]) -> dict[str, Any]:
    if current.get("state") == "AVAILABLE":
        return current
    attempts = [dict(current)]
    for provider, collector in fallback_collectors:
        result = _call_provider(provider, collector, game, timeout)
        attempts.append(dict(result))
        if result.get("state") == "AVAILABLE":
            out = dict(result)
            out["fallback_used"] = True
            out["provider_attempts"] = attempts
            return out
    # VERIFIED_NOT_POSTED is only accepted when every successfully reached,
    # parsed and matched provider in the supplied approved chain explicitly
    # certifies absence and no technical failure is present.
    states = [str(item.get("state") or "") for item in attempts]
    if states and all(state == "VERIFIED_NOT_POSTED" for state in states):
        return _bundle(
            "multi-source",
            "VERIFIED_NOT_POSTED",
            [],
            reason="all approved source results explicitly verified market absence",
            evidence={"provider_states": states},
        )
    out = dict(current)
    out["provider_attempts"] = attempts
    return out


def collect_markets(
    games: list[dict[str, Any]],
    *,
    budget_seconds: float = DEFAULT_MARKET_BUDGET_SECONDS,
    call_timeout_seconds: int = DEFAULT_CALL_TIMEOUT_SECONDS,
    fallback_collectors: Sequence[tuple[str, Callable[..., Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Collect per-game markets while preserving transport/parser truth."""
    fallback_collectors = tuple(fallback_collectors if fallback_collectors is not None else APPROVED_FALLBACK_COLLECTORS)
    valid_games = [dict(game) for game in (games or []) if game.get("source_game_id")]
    results: dict[str, dict[str, Any]] = {
        str(game["source_game_id"]): _bundle(
            PRIMARY_PROVIDER,
            "ALL_SOURCES_UNAVAILABLE",
            [],
            reason="market collection not completed",
        )
        for game in valid_games
    }
    if not valid_games:
        return results

    pool = ThreadPoolExecutor(max_workers=min(12, max(1, len(valid_games))))
    futures = {
        pool.submit(_call_provider, PRIMARY_PROVIDER, direct_book.collect_fanduel_game_markets, game, int(call_timeout_seconds)): game
        for game in valid_games
    }
    done, pending = wait(futures, timeout=max(0.0, float(budget_seconds)))

    for future in done:
        game = futures[future]
        game_id = str(game["source_game_id"])
        try:
            primary = dict(future.result())
        except Exception as exc:  # defensive: _call_provider already catches provider failures
            primary = _bundle(PRIMARY_PROVIDER, "PROVIDER_FETCH_FAILURE", [], reason=f"executor failure: {type(exc).__name__}")
        results[game_id] = _apply_fallbacks(
            game,
            primary,
            timeout=int(call_timeout_seconds),
            fallback_collectors=fallback_collectors,
        )

    for future in pending:
        game = futures[future]
        game_id = str(game["source_game_id"])
        future.cancel()
        timeout_result = _bundle(
            PRIMARY_PROVIDER,
            "PROVIDER_FETCH_FAILURE",
            [],
            reason="primary sportsbook collection exceeded slate-wide time budget",
            evidence={"timeout": True},
        )
        results[game_id] = _apply_fallbacks(
            game,
            timeout_result,
            timeout=int(call_timeout_seconds),
            fallback_collectors=fallback_collectors,
        )

    pool.shutdown(wait=False, cancel_futures=True)
    return results


def market_state(observation: Mapping[str, Any] | None, *, diagnostic_state: str = "MARKET_MAPPING_FAILURE", reason: str = "") -> dict[str, Any]:
    if not observation:
        return {
            "status": "DATA_UNAVAILABLE",
            "diagnostic_state": _text(diagnostic_state).upper() or "MARKET_MAPPING_FAILURE",
            "reason": _text(reason),
            "sportsbook": None,
            "market": "Rushing Yards",
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "timestamp": None,
        }
    return {
        "status": "VERIFIED",
        "diagnostic_state": "AVAILABLE",
        "reason": "",
        "sportsbook": _text(observation.get("sportsbook")) or None,
        "market": _text(observation.get("market")) or "Rushing Yards",
        "line": observation.get("line"),
        "over_odds": observation.get("over_odds"),
        "under_odds": observation.get("under_odds"),
        "timestamp": _text(observation.get("source_timestamp")) or None,
    }


def market_state_from_bundle(bundle: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None, *, player: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(bundle, Mapping):
        state = _text(bundle.get("state")).upper() or "ALL_SOURCES_UNAVAILABLE"
        observations = [dict(row) for row in (bundle.get("observations") or []) if isinstance(row, Mapping)]
        reason = _text(bundle.get("reason"))
    else:
        observations = [dict(row) for row in (bundle or []) if isinstance(row, Mapping)]
        state = "AVAILABLE" if observations else "MARKET_MAPPING_FAILURE"
        reason = "legacy observation list without explicit source state"

    if state == "VERIFIED_NOT_POSTED":
        return {
            "status": "MARKET_NOT_POSTED",
            "diagnostic_state": "VERIFIED_NOT_POSTED",
            "reason": reason,
            "sportsbook": _text(bundle.get("provider")) if isinstance(bundle, Mapping) else None,
            "market": "Rushing Yards",
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "timestamp": None,
        }
    if state != "AVAILABLE":
        return market_state(None, diagnostic_state=state, reason=reason)

    team = canonical_team_abbr(player.get("team_abbr"))
    name = _norm(player.get("player_name"))
    matched = [
        row
        for row in observations
        if canonical_team_abbr(row.get("team_abbr")) == team
        and _norm(row.get("player_name")) == name
        and _text(row.get("position")).upper() in {"RB", "RUNNING BACK"}
    ]
    if len(matched) == 1:
        return market_state(matched[0])
    if len(matched) > 1:
        return market_state(None, diagnostic_state="SOURCE_CONFLICT", reason="multiple exact player market observations survived normalization")
    return market_state(None, diagnostic_state="MARKET_MAPPING_FAILURE", reason="provider market bundle did not contain an exact player/team match")


def _market_for_player(player: Mapping[str, Any], bundle: Any) -> dict[str, Any]:
    return market_state_from_bundle(bundle, player=player)


def install(legacy: Any) -> Any:
    """Install Step 2D runtime semantics after any transport fastpath overlay."""
    legacy._collect_markets = collect_markets
    legacy._market_for_player = _market_for_player
    legacy.market_state = market_state
    return legacy


__all__ = [
    "APPROVED_FALLBACK_COLLECTORS",
    "DEFAULT_CALL_TIMEOUT_SECONDS",
    "DEFAULT_MARKET_BUDGET_SECONDS",
    "PRIMARY_PROVIDER",
    "VERSION",
    "collect_markets",
    "install",
    "market_state",
    "market_state_from_bundle",
]
