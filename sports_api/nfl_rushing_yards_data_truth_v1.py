"""NFL Rushing Yards runtime data-truth overlay.

This module prevents direct-book transport/parser/mapping failures from being
collapsed into a verified unposted market state. FanDuel remains the primary
field source; approved fallbacks may satisfy a missing field, but only explicit
absence proof can become a true no-market state.

No value is fabricated and sportsbook data never influences Kyre projections.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Callable, Mapping, Sequence

from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as direct_book
from sports_api.collectors import nfl_the_odds_api_rushing_yards_v1 as odds_api_fallback

VERSION = "NFL_RUSHING_YARDS_DATA_TRUTH_V2"
PRIMARY_PROVIDER = "FanDuel"
DEFAULT_MARKET_BUDGET_SECONDS = 18.0
DEFAULT_CALL_TIMEOUT_SECONDS = 8
PLAYER_NAME_MATCHING = False
FUZZY_MATCHING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

# Field-specific recovery chain. FanDuel direct remains primary; The Odds API is
# invoked only after primary failure/unverified absence, then routing stops once
# the field is reliably satisfied.
APPROVED_FALLBACK_COLLECTORS: tuple[tuple[str, Callable[..., Any]], ...] = (
    ("The Odds API", odds_api_fallback.collect_the_odds_api_game_markets),
)

_FAILURE_STATES = {
    "PROVIDER_FETCH_FAILURE",
    "PARSER_FAILURE",
    "EVENT_MAPPING_FAILURE",
    "PLAYER_MAPPING_FAILURE",
    "PLAYER_MAPPING_UNAVAILABLE",
    "MARKET_MAPPING_FAILURE",
    "STALE_DATA",
    "SOURCE_CONFLICT",
    "ALL_SOURCES_UNAVAILABLE",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


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
        evidence = raw.get("evidence") if isinstance(raw.get("evidence"), Mapping) else None
        if state == "AVAILABLE" and observations:
            return _bundle(provider, "AVAILABLE", observations, reason=_text(raw.get("reason")), evidence=evidence)
        if state in {"VERIFIED_NOT_POSTED", "VERIFIED_NO_STANDARD_MARKET"} and not observations:
            return _bundle(provider, "VERIFIED_NOT_POSTED", [], reason=_text(raw.get("reason")), evidence=evidence)
        if state in _FAILURE_STATES:
            return _bundle(provider, state, observations, reason=_text(raw.get("reason")), evidence=evidence)
        if observations:
            return _bundle(provider, "AVAILABLE", observations, reason=_text(raw.get("reason")), evidence=evidence)
        return _bundle(provider, "MARKET_MAPPING_FAILURE", [], reason="provider returned an unverified empty result", evidence=evidence)
    if isinstance(raw, list):
        observations = [dict(row) for row in raw if isinstance(row, Mapping)]
        if observations:
            return _bundle(provider, "AVAILABLE", observations)
        # A legacy empty list contains no evidence that the sportsbook did not
        # post the market. Treat it as unresolved rather than fabricating absence.
        return _bundle(provider, "MARKET_MAPPING_FAILURE", [], reason="legacy collector returned empty without absence proof")
    return _bundle(provider, "PARSER_FAILURE", [], reason=f"unexpected provider result type: {type(raw).__name__}")


def _call_provider(provider: str, collector: Callable[..., Any], game: Mapping[str, Any], timeout: int) -> dict[str, Any]:
    try:
        return _normalize_provider_result(provider, collector(game, timeout=max(DEFAULT_CALL_TIMEOUT_SECONDS, int(timeout))))
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
    """Collect per-game markets concurrently while preserving transport truth."""
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

    effective_timeout = max(DEFAULT_CALL_TIMEOUT_SECONDS, int(call_timeout_seconds or 0))
    effective_budget = max(float(budget_seconds or 0.0), float(effective_timeout * direct_book.MAX_MARKET_READ_ATTEMPTS + 2))
    pool = ThreadPoolExecutor(max_workers=min(12, max(1, len(valid_games))))
    futures = {
        pool.submit(_call_provider, PRIMARY_PROVIDER, direct_book.collect_fanduel_game_market_bundle, game, effective_timeout): game
        for game in valid_games
    }
    done, pending = wait(futures, timeout=effective_budget)

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
            timeout=effective_timeout,
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
            reason="primary sportsbook collection exceeded bounded slate-wide time budget",
            evidence={"timeout": True, "budget_seconds": effective_budget},
        )
        results[game_id] = _apply_fallbacks(
            game,
            timeout_result,
            timeout=effective_timeout,
            fallback_collectors=fallback_collectors,
        )

    pool.shutdown(wait=False, cancel_futures=True)
    return results


def market_state(observation: Mapping[str, Any] | None, *, diagnostic_state: str = "MARKET_MAPPING_FAILURE", reason: str = "") -> dict[str, Any]:
    if not observation:
        state = "PLAYER_MAPPING_UNAVAILABLE" if _text(diagnostic_state).upper() in {"PLAYER_MAPPING_FAILURE", "PLAYER_MAPPING_UNAVAILABLE"} else "DATA_UNAVAILABLE"
        return {
            "status": "DATA_UNAVAILABLE",
            "state": state,
            "verified_absence": False,
            "diagnostic_state": _text(diagnostic_state).upper() or "MARKET_MAPPING_FAILURE",
            "reason": _text(reason),
            "sportsbook": None,
            "market": "Rushing Yards",
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "timestamp": None,
            "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        }
    return {
        "status": "VERIFIED",
        "state": "AVAILABLE",
        "verified_absence": False,
        "diagnostic_state": "AVAILABLE",
        "reason": "",
        "sportsbook": _text(observation.get("sportsbook")) or None,
        "market": _text(observation.get("market")) or "Rushing Yards",
        "line": observation.get("line"),
        "over_odds": observation.get("over_odds"),
        "under_odds": observation.get("under_odds"),
        "timestamp": _text(observation.get("source_timestamp")) or None,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def _verified_no_market(*, provider: str, reason: str, identity_verified: bool = False) -> dict[str, Any]:
    return {
        "status": "MARKET_NOT_POSTED",
        "state": "VERIFIED_NO_STANDARD_MARKET",
        "verified_absence": True,
        "diagnostic_state": "VERIFIED_NO_STANDARD_MARKET",
        "reason": _text(reason),
        "sportsbook": _text(provider) or None,
        "market": "Rushing Yards",
        "line": None,
        "over_odds": None,
        "under_odds": None,
        "timestamp": None,
        "identity_verified": bool(identity_verified),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def market_state_from_bundle(bundle: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None, *, player: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if isinstance(bundle, Mapping):
        source_state = _text(bundle.get("state")).upper() or "ALL_SOURCES_UNAVAILABLE"
        observations = [dict(row) for row in (bundle.get("observations") or []) if isinstance(row, Mapping)]
        reason = _text(bundle.get("reason"))
        provider = _text(bundle.get("provider"))
        evidence = dict(bundle.get("evidence") or {}) if isinstance(bundle.get("evidence"), Mapping) else {}
    else:
        observations = [dict(row) for row in (bundle or []) if isinstance(row, Mapping)]
        source_state = "AVAILABLE" if observations else "MARKET_MAPPING_FAILURE"
        reason = "legacy observation list without explicit source state"
        provider = ""

    if source_state == "VERIFIED_NOT_POSTED":
        return _verified_no_market(provider=provider, reason=reason)
    if source_state != "AVAILABLE":
        return market_state(None, diagnostic_state=source_state, reason=reason)

    matched: list[dict[str, Any]] = []
    for row in observations:
        resolved = direct_book.reconcile_observation_to_roster(row, [player])
        if resolved is not None:
            matched.append(row)

    if len(matched) == 1:
        out = market_state(matched[0])
        out["identity_verified"] = True
        return out
    if len(matched) > 1:
        return market_state(None, diagnostic_state="SOURCE_CONFLICT", reason="multiple exact team + jersey + position market observations survived canonical reconciliation")

    # FanDuel exposes a separate event player identity catalog. If the canonical
    # RB is uniquely present there, identity is verified even when that player is
    # not attached to an open standard Rushing Yards market. That is explicit
    # per-player absence evidence, not a mapping failure and not a fabricated line.
    identity_catalog = [dict(row) for row in (evidence.get("identity_catalog") or []) if isinstance(row, Mapping)]
    catalog_matches = [
        row
        for row in identity_catalog
        if direct_book.reconcile_observation_to_roster(row, [player]) is not None
    ]
    if len(catalog_matches) > 1:
        return market_state(None, diagnostic_state="SOURCE_CONFLICT", reason="multiple provider identity rows matched the canonical team + jersey + position")
    if len(catalog_matches) == 1:
        provider_player_id = _text(catalog_matches[0].get("provider_player_id"))
        offered_ids = {_text(value) for value in (evidence.get("offered_provider_player_ids") or []) if _text(value)}
        if provider_player_id and provider_player_id not in offered_ids:
            return _verified_no_market(
                provider=provider or PRIMARY_PROVIDER,
                reason="verified provider player identity is present, but no open standard rushing-yards market is attached",
                identity_verified=True,
            )
        if provider_player_id and provider_player_id in offered_ids:
            return market_state(
                None,
                diagnostic_state="MARKET_MAPPING_FAILURE",
                reason="provider offered a standard rushing-yards market for the exact player identity, but no complete quote survived normalization",
            )

    return market_state(None, diagnostic_state="PLAYER_MAPPING_UNAVAILABLE", reason="provider market bundle did not contain one unique active team + jersey + position match")


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
    "FUZZY_MATCHING",
    "PLAYER_NAME_MATCHING",
    "PRIMARY_PROVIDER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VERSION",
    "collect_markets",
    "install",
    "market_state",
    "market_state_from_bundle",
]
