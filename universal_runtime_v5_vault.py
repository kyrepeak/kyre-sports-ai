"""Per-sport remembered-state vaults for Universal Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, MutableMapping

from universal_runtime_v5_state import RuntimeRoute
from universal_sports_nav_registry_v1 import get_market, get_sport

VAULT_SESSION_KEY = "ks_v5_sport_vaults"
_TRANSIENT_EXACT = {
    "ks_v5_pending_intent",
    "ks_v5_active_scope",
    "ks_v5_transition_mask",
    "ks_v5_route_commit_inflight",
}
_TRANSIENT_PREFIXES = ("ks_v5_ephemeral_", "ks_v5_transition_", "ks_v5_pending_")


@dataclass(frozen=True)
class SportVault:
    sport_id: str
    market_id: str
    page_params: Mapping[str, str] = field(default_factory=dict)
    local_state: Mapping[str, object] = field(default_factory=dict)
    revision: int = 1


def _safe_value(value: object):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        cleaned = [_safe_value(item) for item in value]
        return cleaned if all(item is not _UNSAFE for item in cleaned) else _UNSAFE
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            cleaned = _safe_value(item)
            if cleaned is _UNSAFE:
                return _UNSAFE
            result[str(key)] = cleaned
        return result
    return _UNSAFE


_UNSAFE = object()


def _owned_local_state(session: Mapping[str, object], sport_id: str) -> dict[str, object]:
    sport = str(sport_id or "").strip().lower()
    prefixes = (f"{sport}_", f"ks_{sport}_")
    result: dict[str, object] = {}
    for raw_key, raw_value in session.items():
        key = str(raw_key)
        if not key.lower().startswith(prefixes):
            continue
        cleaned = _safe_value(raw_value)
        if cleaned is not _UNSAFE:
            result[key] = cleaned
    return result


def _route_page_params(route: RuntimeRoute) -> dict[str, str]:
    market = get_market(route.sport_id, route.market_id)
    if market is None:
        return {}
    result: dict[str, str] = {}
    for key in market.page_params:
        text = str(route.params.get(key) or "").strip()
        if text:
            result[key] = text
    return result


def _raw_vaults(session: Mapping[str, object]) -> dict[str, object]:
    raw = session.get(VAULT_SESSION_KEY)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _content_tuple(sport_id: str, market_id: str, page_params: Mapping[str, str], local_state: Mapping[str, object]):
    return (
        str(sport_id),
        str(market_id),
        tuple(sorted((str(k), str(v)) for k, v in page_params.items())),
        repr(sorted((str(k), repr(v)) for k, v in local_state.items())),
    )


def capture_vault(session: Mapping[str, object], route: RuntimeRoute) -> SportVault:
    page_params = _route_page_params(route)
    local_state = _owned_local_state(session, route.sport_id)
    raw_existing = _raw_vaults(session).get(route.sport_id)
    revision = 1
    if isinstance(raw_existing, Mapping):
        old_revision = int(raw_existing.get("revision") or 0)
        old_content = _content_tuple(
            str(raw_existing.get("sport_id") or route.sport_id),
            str(raw_existing.get("market_id") or ""),
            dict(raw_existing.get("page_params") or {}),
            dict(raw_existing.get("local_state") or {}),
        )
        new_content = _content_tuple(route.sport_id, route.market_id, page_params, local_state)
        revision = old_revision if old_content == new_content else old_revision + 1
        if revision < 1:
            revision = 1
    return SportVault(route.sport_id, route.market_id, dict(page_params), dict(local_state), revision)


def store_vault(session: MutableMapping[str, object], vault: SportVault) -> None:
    vaults = _raw_vaults(session)
    vaults[vault.sport_id] = {
        "sport_id": vault.sport_id,
        "market_id": vault.market_id,
        "page_params": dict(vault.page_params),
        "local_state": dict(vault.local_state),
        "revision": int(vault.revision),
    }
    session[VAULT_SESSION_KEY] = vaults


def restore_vault(session: MutableMapping[str, object], sport_id: str) -> SportVault | None:
    sport = get_sport(sport_id)
    if sport is None:
        return None
    raw = _raw_vaults(session).get(sport.id)
    if not isinstance(raw, Mapping):
        return None
    requested_market = str(raw.get("market_id") or "").strip().lower()
    market = get_market(sport.id, requested_market)
    invalid_market = market is None
    if market is None:
        market = get_market(sport.id, sport.default_market_id)
    if market is None:
        return None
    raw_params = dict(raw.get("page_params") or {})
    page_params: dict[str, str] = {}
    for key in market.page_params:
        text = str(raw_params.get(key) or "").strip()
        if text:
            page_params[key] = text
    local_state = dict(raw.get("local_state") or {})
    if invalid_market:
        local_state = {
            key: value
            for key, value in local_state.items()
            if "market_touch" not in str(key).lower()
        }
    return SportVault(
        sport.id,
        market.id,
        page_params,
        local_state,
        max(1, int(raw.get("revision") or 1)),
    )


def apply_vault_to_session(session: MutableMapping[str, object], vault: SportVault) -> None:
    for key, value in vault.local_state.items():
        session[str(key)] = value
    market = get_market(vault.sport_id, vault.market_id)
    if market is None:
        return
    for key in market.page_params:
        if key in vault.page_params:
            session[key] = vault.page_params[key]
        else:
            session.pop(key, None)


def retire_active_ephemeral_state(
    session: MutableMapping[str, object],
    outgoing_sport_id: str,
) -> tuple[str, ...]:
    del outgoing_sport_id
    removed: list[str] = []
    for raw_key in list(session.keys()):
        key = str(raw_key)
        if key == VAULT_SESSION_KEY:
            continue
        if key in _TRANSIENT_EXACT or key.startswith(_TRANSIENT_PREFIXES):
            session.pop(raw_key, None)
            removed.append(key)
    return tuple(removed)


__all__ = [
    "VAULT_SESSION_KEY",
    "SportVault",
    "apply_vault_to_session",
    "capture_vault",
    "restore_vault",
    "retire_active_ephemeral_state",
    "store_vault",
]
