"""Universal Runtime V5 — compact single-owner Streamlit route authority."""
from __future__ import annotations

import importlib
from time import perf_counter, time
from typing import Mapping, MutableMapping

import streamlit as st
import universal_sports_nav_ui_v2 as nav_ui
from universal_runtime_v5_health import RuntimeEvent, assert_runtime_health, record_event, summarize_health
from universal_runtime_v5_loader_v15 import choose_prefetch, load_destination, resolve_destination
from universal_runtime_v5_scope import RenderScope, can_commit, commit_if_current, new_scope
from universal_runtime_v5_snapshot import VerifiedSnapshot, get_snapshot, put_snapshot, snapshot_key
from universal_runtime_v5_state import RuntimeRoute, RuntimeState, bootstrap_runtime, canonical_query_patch, commit_intent
from universal_runtime_v5_vault import apply_vault_to_session, capture_vault, restore_vault, retire_active_ephemeral_state, store_vault
from universal_sports_nav_compat_v1 import apply_legacy_route_state
from universal_sports_nav_controller_v1 import RouteIntent, RouteState, resolve_route
from universal_sports_nav_registry_v1 import get_sport
from universal_sports_nav_url_v1 import parse_canonical_query

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • SINGLE OWNER"
RUNTIME_MODE_SESSION_KEY = "ks_v5_runtime_mode"
RUNTIME_STATE_SESSION_KEY = "ks_v5_runtime_state"
ACTIVE_SCOPE_SESSION_KEY = "ks_v5_active_scope"
BOOTSTRAP_IMPORT_MS_KEY = "ks_v5_bootstrap_import_ms"
SNAPSHOT_CACHE_SESSION_KEY = "ks_v5_verified_snapshots"
PREFETCHED_SESSION_KEY = "ks_v5_prefetched_routes"
PREFETCH_BUDGET_MS = 125.0
RUNTIME_EVENTS_SESSION_KEY = "ks_v5_runtime_events"
V5_MODE_ACTIVE = "active"
V5_MODE_FALLBACK = "fallback"
DEFAULT_RUNTIME_MODE = V5_MODE_ACTIVE
FALLBACK_RUNTIME_MODULE = "streamlit_memory_lazy_router_api2_nfl_rushing_cleanup_v1"
SITE_SHELL_HTML = """<div id="kyre-top"></div><div data-kyre-universal-runtime-v5-shell class="kyre-universal-runtime-v5-shell"><strong>KYRE SPORTS AI</strong></div><a class="kyre-v5-top" href="#kyre-top">TOP</a><style>.kyre-universal-runtime-v5-shell{position:sticky;top:0;z-index:9999;padding:.55rem 0;background:var(--background-color)}.kyre-v5-top{position:fixed;right:10px;bottom:18px;z-index:9999;font-weight:800;text-decoration:none}</style>"""
DESTINATION_MASK_HTML = """<div class="kyre-v5-destination-mask" aria-hidden="true"></div>"""


def record_bootstrap_import_ms(value: float) -> None:
    st.session_state[BOOTSTRAP_IMPORT_MS_KEY] = max(0.0, float(value))


def _health_events() -> list[RuntimeEvent]:
    events = st.session_state.get(RUNTIME_EVENTS_SESSION_KEY)
    if not isinstance(events, list):
        events = []
        st.session_state[RUNTIME_EVENTS_SESSION_KEY] = events
    return events


def _record_health_event(name: str, generation: int, started: float | None = None, **values: object) -> None:
    payload = dict(values)
    if started is not None:
        payload["duration_ms"] = max(0.0, (perf_counter() - started) * 1000.0)
    record_event(_health_events(), RuntimeEvent(name, int(generation), perf_counter() * 1000.0, payload))


def _assert_active_runtime_health() -> None:
    scope = st.session_state.get(ACTIVE_SCOPE_SESSION_KEY)
    active_scopes = 1 if isinstance(scope, Mapping) else 0
    health = summarize_health(_health_events(), active_owner_count=1, active_scope_count=active_scopes, wrapper_depth=1)
    if active_scopes:
        assert_runtime_health(health)


def _route_to_dict(route: RuntimeRoute) -> dict[str, object]:
    return {
        "sport_id": route.sport_id,
        "market_id": route.market_id,
        "params": dict(route.params),
        "generation": int(route.generation),
        "source": route.source,
    }


def _route_from_dict(raw: Mapping[str, object]) -> RuntimeRoute:
    return RuntimeRoute(
        str(raw.get("sport_id") or "nfl"),
        str(raw.get("market_id") or "slate"),
        {str(k): str(v) for k, v in dict(raw.get("params") or {}).items()},
        int(raw.get("generation") or 0),
        str(raw.get("source") or "default"),
    )


def _runtime_to_dict(runtime: RuntimeState) -> dict[str, object]:
    return {
        "active": _route_to_dict(runtime.active),
        "last_route_by_sport": {key: _route_to_dict(value) for key, value in dict(runtime.last_route_by_sport).items()},
        "generation": int(runtime.generation),
    }


def _runtime_from_dict(raw: Mapping[str, object]) -> RuntimeState | None:
    try:
        active = _route_from_dict(dict(raw.get("active") or {}))
        memory = {
            str(key): _route_from_dict(value)
            for key, value in dict(raw.get("last_route_by_sport") or {}).items()
            if isinstance(value, Mapping)
        }
        return RuntimeState(active, memory, int(raw.get("generation") or active.generation))
    except Exception:
        return None


def _legacy_memory(session: Mapping[str, object]) -> dict[str, str]:
    raw = session.get("ks_universal_last_market_by_sport")
    return {str(k): str(v) for k, v in dict(raw or {}).items()} if isinstance(raw, Mapping) else {}


def _as_route_state(runtime: RuntimeState) -> RouteState:
    return RouteState(
        runtime.active.sport_id,
        runtime.active.market_id,
        runtime.active.source,
        int(runtime.generation),
        {key: value.market_id for key, value in dict(runtime.last_route_by_sport).items()},
    )


def _save_runtime(runtime: RuntimeState) -> None:
    st.session_state[RUNTIME_STATE_SESSION_KEY] = _runtime_to_dict(runtime)


def _persist_compat(runtime: RuntimeState) -> None:
    apply_legacy_route_state(_as_route_state(runtime), st.session_state)
    patch = canonical_query_patch(runtime.active, runtime.active, dict(st.query_params))
    for key, value in patch.items():
        if value is None:
            try:
                del st.query_params[key]
            except Exception:
                pass
        else:
            st.query_params[key] = value


def _bootstrap_runtime() -> RuntimeState:
    parsed = parse_canonical_query(dict(st.query_params))
    route_state = resolve_route(
        canonical_sport=parsed.sport_id,
        canonical_market=parsed.market_id,
        last_market_by_sport=_legacy_memory(st.session_state),
        epoch=0,
    )
    runtime = bootstrap_runtime(route_state, parsed.page_params)
    _save_runtime(runtime)
    _persist_compat(runtime)
    return runtime


def _load_runtime() -> RuntimeState:
    raw = st.session_state.get(RUNTIME_STATE_SESSION_KEY)
    if isinstance(raw, RuntimeState):
        return raw
    if isinstance(raw, Mapping):
        runtime = _runtime_from_dict(raw)
        if runtime is not None:
            return runtime
    return _bootstrap_runtime()


def _apply_current_page_params(route: RuntimeRoute) -> None:
    sport = get_sport(route.sport_id)
    market = next((item for item in tuple(sport.markets) if item.id == route.market_id), None) if sport else None
    if market is None:
        return
    for key in market.page_params:
        value = route.params.get(key)
        if value:
            st.session_state[key] = value
        else:
            st.session_state.pop(key, None)


def _commit_navigation_intent(intent: RouteIntent, params: Mapping[str, str] | None = None) -> RuntimeState:
    started = perf_counter()
    runtime = _load_runtime()
    outgoing = runtime.active
    target_sport = intent.sport_id or outgoing.sport_id
    if target_sport != outgoing.sport_id:
        store_vault(st.session_state, capture_vault(st.session_state, outgoing))
    updated = commit_intent(runtime, intent, params)
    if updated.active.sport_id != outgoing.sport_id:
        retire_active_ephemeral_state(st.session_state, outgoing.sport_id)
        remembered = restore_vault(st.session_state, updated.active.sport_id)
        if remembered is not None and params is None:
            apply_vault_to_session(st.session_state, remembered)
            updated = commit_intent(
                updated,
                RouteIntent(remembered.sport_id, remembered.market_id, "memory"),
                remembered.page_params,
            )
    _apply_current_page_params(updated.active)
    _save_runtime(updated)
    _persist_compat(updated)
    _record_health_event("route_commit", updated.generation, started)
    return updated


def _consume_pending_intent() -> RouteIntent | None:
    raw = st.session_state.pop(getattr(nav_ui, "PENDING_INTENT_KEY", "ks_universal_pending_intent_v2"), None)
    if not isinstance(raw, Mapping):
        return None
    sport = str(raw.get("sport_id") or "").strip().lower() or None
    market = str(raw.get("market_id") or "").strip().lower() or None
    if not sport and not market:
        return None
    return RouteIntent(sport, market, str(raw.get("source") or "tap"))


def _reconcile_query_navigation(runtime: RuntimeState) -> RuntimeState:
    parsed = parse_canonical_query(dict(st.query_params))
    sport = parsed.sport_id or runtime.active.sport_id
    market = parsed.market_id or runtime.active.market_id
    if (
        sport == runtime.active.sport_id
        and market == runtime.active.market_id
        and dict(parsed.page_params) == dict(runtime.active.params)
    ):
        return runtime
    return _commit_navigation_intent(RouteIntent(sport, market, "canonical_url"), parsed.page_params)


def _scope_to_dict(scope: RenderScope) -> dict[str, object]:
    return {
        "scope_id": scope.scope_id,
        "generation": scope.generation,
        "sport_id": scope.sport_id,
        "market_id": scope.market_id,
        "status": scope.status,
    }


def _normalize_active_scope(session: MutableMapping[str, object], runtime: RuntimeState) -> RenderScope:
    raw = session.get(ACTIVE_SCOPE_SESSION_KEY)
    if isinstance(raw, Mapping):
        try:
            scope = RenderScope(
                str(raw.get("scope_id") or ""),
                int(raw.get("generation") or -1),
                str(raw.get("sport_id") or ""),
                str(raw.get("market_id") or ""),
                str(raw.get("status") or "DORMANT"),
            )
            if can_commit(scope, runtime):
                return scope
        except Exception:
            pass
    scope = new_scope(runtime.active)
    session[ACTIVE_SCOPE_SESSION_KEY] = _scope_to_dict(scope)
    return scope


def _render_site_shell() -> None:
    st.markdown(SITE_SHELL_HTML, unsafe_allow_html=True)


def _render_destination_shell(route: RuntimeRoute) -> None:
    started = perf_counter()
    st.markdown(DESTINATION_MASK_HTML, unsafe_allow_html=True)
    nav_ui.render_universal_nav(
        RouteState(route.sport_id, route.market_id, route.source, route.generation, {route.sport_id: route.market_id})
    )
    _record_health_event("shell_visible", route.generation, started)


def _now_epoch_ms() -> int:
    return int(time() * 1000)


def _snapshot_cache() -> MutableMapping[str, object]:
    cache = st.session_state.get(SNAPSHOT_CACHE_SESSION_KEY)
    if not isinstance(cache, MutableMapping):
        cache = {}
        st.session_state[SNAPSHOT_CACHE_SESSION_KEY] = cache
    return cache


def _render_cached_snapshot(snapshot: VerifiedSnapshot) -> None:
    payload = snapshot.payload
    if isinstance(payload, str) and payload.strip():
        st.markdown(payload, unsafe_allow_html=True)
    else:
        st.caption("Verified cached view • refreshing live data")


def _prefetch_candidates(route: RuntimeRoute) -> tuple[RuntimeRoute, ...]:
    sport = get_sport(route.sport_id)
    if sport is None:
        return ()
    values: list[RuntimeRoute] = []
    for market in sport.markets:
        if not market.live or market.id == route.market_id:
            continue
        params = {key: value for key, value in dict(route.params).items() if key in market.page_params}
        values.append(RuntimeRoute(route.sport_id, market.id, params, route.generation, "prefetch"))
    return tuple(values)


def _run_bounded_prefetch(runtime: RuntimeState) -> tuple[tuple[str, str], ...]:
    started = perf_counter()
    loaded: list[tuple[str, str]] = []
    for request in choose_prefetch(runtime.active, _prefetch_candidates(runtime.active), limit=2):
        if (perf_counter() - started) * 1000.0 > PREFETCH_BUDGET_MS:
            break
        try:
            adapter = resolve_destination(request.route)
            load_destination(adapter)
            loaded.append((request.route.sport_id, request.route.market_id))
        except Exception:
            continue
    st.session_state[PREFETCHED_SESSION_KEY] = tuple(loaded)
    return tuple(loaded)


def _render_active_destination(runtime: RuntimeState, scope: RenderScope) -> object | None:
    adapter = resolve_destination(runtime.active)
    cache = _snapshot_cache()
    key = snapshot_key(runtime.active)
    cached_started = perf_counter()
    cached = get_snapshot(
        cache,
        key,
        now_epoch_ms=_now_epoch_ms(),
        expected_source_version=adapter.source_version,
        allow_stale=True,
    )
    if cached is not None:
        _render_cached_snapshot(cached)
        _record_health_event("cached_visible", runtime.generation, cached_started)
    if not can_commit(scope, runtime):
        _record_health_event("stale_commit_attempt", scope.generation)
        return None
    refresh_started = perf_counter()
    loaded = load_destination(adapter)
    current = _load_runtime() if RUNTIME_STATE_SESSION_KEY in st.session_state else runtime
    if not can_commit(scope, current):
        _record_health_event("stale_commit_attempt", scope.generation)
        return None
    result = commit_if_current(scope, current, lambda: adapter.renderer(loaded))
    if can_commit(scope, current):
        payload = {
            "sport_id": runtime.active.sport_id,
            "market_id": runtime.active.market_id,
            "params": dict(runtime.active.params),
        }
        put_snapshot(
            cache,
            VerifiedSnapshot(key, payload, _now_epoch_ms(), int(adapter.ttl_ms), 1, adapter.source_version),
        )
    _record_health_event("live_refresh", runtime.generation, refresh_started)
    return result


def _render_fallback() -> object | None:
    module = importlib.import_module(FALLBACK_RUNTIME_MODULE)
    renderer = getattr(module, "render_app", None) or getattr(module, "render", None)
    return renderer() if callable(renderer) else None


def _render_v5_active() -> object | None:
    runtime = _load_runtime()
    pending = _consume_pending_intent()
    if pending is not None:
        runtime = _commit_navigation_intent(pending)
    runtime = _reconcile_query_navigation(runtime)
    scope = _normalize_active_scope(st.session_state, runtime)
    _render_site_shell()
    _render_destination_shell(runtime.active)
    result = _render_active_destination(runtime, scope)
    _run_bounded_prefetch(runtime)
    _assert_active_runtime_health()
    return result


def render_app() -> object | None:
    mode = str(st.session_state.get(RUNTIME_MODE_SESSION_KEY) or DEFAULT_RUNTIME_MODE).strip().lower()
    if mode == V5_MODE_ACTIVE:
        return _render_v5_active()
    return _render_fallback()


__all__ = [
    "DEFAULT_RUNTIME_MODE",
    "FALLBACK_RUNTIME_MODULE",
    "V5_MODE_ACTIVE",
    "V5_MODE_FALLBACK",
    "record_bootstrap_import_ms",
    "render_app",
]