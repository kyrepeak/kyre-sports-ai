"""Canonical URL codec for Universal Sports Navigation V1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from universal_sports_nav_controller_v1 import RouteState
from universal_sports_nav_registry_v1 import get_market, visible_sports


_CANONICAL_KEYS = ("sport", "market")
_PAGE_KEYS = ("date", "game_id", "player_id")


@dataclass(frozen=True)
class CanonicalQuery:
    sport_id: str | None = None
    market_id: str | None = None
    page_params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryPatch:
    set_values: tuple[tuple[str, str], ...] = ()
    delete_keys: tuple[str, ...] = ()


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _page_values(query: Mapping[str, Any]) -> dict[str, str]:
    return {key: _scalar(query.get(key)) for key in _PAGE_KEYS if _scalar(query.get(key))}


def parse_canonical_query(query: Mapping[str, Any]) -> CanonicalQuery:
    sport = _scalar(query.get("sport")).lower() or None
    market = _scalar(query.get("market")).lower() or None
    return CanonicalQuery(sport, market, _page_values(query))


def _sport_from_legacy(value: str):
    wanted = str(value or "").strip().lower()
    for sport in visible_sports():
        if wanted in {sport.id.lower(), sport.label.lower(), sport.legacy_sport.lower()}:
            return sport
    return None


def _market_from_legacy(sport, value: str):
    wanted = str(value or "").strip().lower()
    for market in sport.markets:
        if market.live and wanted in {market.id.lower(), market.label.lower(), market.legacy_market.lower()}:
            return market
    return None


def _filtered_page_params(sport_id: str | None, market_id: str | None, query: Mapping[str, Any]) -> dict[str, str]:
    market = get_market(sport_id or "", market_id or "")
    if market is None:
        return {}
    allowed = set(market.page_params)
    return {key: value for key, value in _page_values(query).items() if key in allowed}


def normalize_legacy_query(
    query: Mapping[str, Any],
    session: Mapping[str, Any],
) -> CanonicalQuery:
    """Normalize migration inputs without allowing stale legacy query state to win."""
    canonical = parse_canonical_query(query)
    if get_market(canonical.sport_id or "", canonical.market_id or "") is not None:
        return CanonicalQuery(
            canonical.sport_id,
            canonical.market_id,
            _filtered_page_params(canonical.sport_id, canonical.market_id, query),
        )

    session_sport = _scalar(session.get("ks_universal_sport")).lower()
    session_market = _scalar(session.get("ks_universal_market")).lower()
    session_source = _scalar(session.get("ks_universal_nav_source")).lower()
    if session_source == "tap" and get_market(session_sport, session_market) is not None:
        return CanonicalQuery(
            session_sport,
            session_market,
            _filtered_page_params(session_sport, session_market, query),
        )

    legacy_sport = _sport_from_legacy(_scalar(query.get("ks_sport")))
    if legacy_sport is None:
        return CanonicalQuery(None, None, {})

    query_market_key = ""
    if legacy_sport.markets:
        query_market_key = legacy_sport.markets[0].legacy_market_key.removesuffix("_touch")
    market = _market_from_legacy(legacy_sport, _scalar(query.get(query_market_key)))
    if market is None:
        market = get_market(legacy_sport.id, legacy_sport.default_market_id)
    return CanonicalQuery(
        legacy_sport.id,
        market.id if market else None,
        _filtered_page_params(legacy_sport.id, market.id if market else None, query),
    )


def _legacy_universal_keys(query: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for raw_key in query.keys():
        key = str(raw_key)
        if key == "ks_sport" or key in {"ks_jump_sport", "ks_jump_market"}:
            keys.add(key)
        elif key.startswith("ks_") and key.endswith("_market"):
            keys.add(key)
    return keys


def query_patch_for_state(state: RouteState, query: Mapping[str, Any]) -> QueryPatch:
    set_values: list[tuple[str, str]] = []
    if _scalar(query.get("sport")).lower() != state.sport_id:
        set_values.append(("sport", state.sport_id))
    if _scalar(query.get("market")).lower() != state.market_id:
        set_values.append(("market", state.market_id))

    delete_keys = set(_legacy_universal_keys(query))
    market = get_market(state.sport_id, state.market_id)
    allowed = set(market.page_params if market else ())
    for key in _PAGE_KEYS:
        if key in query and key not in allowed:
            delete_keys.add(key)

    return QueryPatch(tuple(set_values), tuple(sorted(delete_keys)))


def apply_query_patch(query: MutableMapping[str, Any], patch: QueryPatch) -> bool:
    changed = False
    for key in patch.delete_keys:
        try:
            if key in query:
                del query[key]
                changed = True
        except Exception:
            continue
    for key, value in patch.set_values:
        try:
            if _scalar(query.get(key)) != value:
                query[key] = value
                changed = True
        except Exception:
            continue
    return changed


__all__ = [
    "CanonicalQuery", "QueryPatch", "apply_query_patch", "normalize_legacy_query",
    "parse_canonical_query", "query_patch_for_state",
]
