"""Lazy route adapters and bounded prefetch policy for Universal Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib
from typing import Callable, Sequence

from universal_runtime_v5_state import RuntimeRoute
from universal_sports_nav_registry_v1 import get_market


@dataclass(frozen=True)
class DestinationAdapter:
    route_key: tuple[str, str]
    loader: Callable[[], object]
    renderer: Callable[[object], object]
    source_version: str
    ttl_ms: int


@dataclass(frozen=True)
class PrefetchRequest:
    route: RuntimeRoute
    priority: int


def _import(name: str):
    return importlib.import_module(name)


def _market_label(route: RuntimeRoute) -> str:
    market = get_market(route.sport_id, route.market_id)
    return market.legacy_market if market is not None else route.market_id.replace("-", " ").title()


def _wnba_pra_step9_adapter(route: RuntimeRoute) -> DestinationAdapter:
    def loader():
        return (
            _import("streamlit_memory_lazy_router_v1"),
            _import("streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"),
        )

    def renderer(bundle):
        root, step9 = bundle
        game_center = step9.game_center
        step7_precompute = step9.step7_precompute
        step4_cache = step9.step4_cache
        original_game_loader = game_center.load_game_center
        original_warm_one = step7_precompute._warm_one
        original_bundle_loader = step4_cache.load_cached_bundle_pair

        def guarded_game_loader(*args, **kwargs):
            return step9._dedupe_game_center_payload(original_game_loader(*args, **kwargs))

        def handoff_bundle_loader(game_id: str, player_id: int):
            return step9._handoff_loader(original_bundle_loader, game_id, player_id)

        if hasattr(original_game_loader, "clear"):
            guarded_game_loader.clear = original_game_loader.clear

        game_center.load_game_center = guarded_game_loader
        step7_precompute._warm_one = step9._capture_precompute_bundle
        step4_cache.load_cached_bundle_pair = handoff_bundle_loader
        try:
            return root._render_wnba("PRA")
        finally:
            game_center.load_game_center = original_game_loader
            step7_precompute._warm_one = original_warm_one
            step4_cache.load_cached_bundle_pair = original_bundle_loader

    return DestinationAdapter(
        (route.sport_id, route.market_id),
        loader,
        renderer,
        "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard",
        15_000,
    )


def _root_adapter(route: RuntimeRoute, *, ttl_ms: int) -> DestinationAdapter:
    market_label = _market_label(route)

    def loader():
        return _import("streamlit_memory_lazy_router_v1")

    def renderer(root):
        if route.sport_id == "mlb":
            if route.market_id == "live-odds":
                return root._render_mlb_live_odds()
            return root._render_mlb(market_label)
        if route.sport_id == "wnba":
            return root._render_wnba(market_label)
        raise RuntimeError("API2_V5_ROOT_ADAPTER_ROUTE_MISMATCH")

    return DestinationAdapter(
        (route.sport_id, route.market_id), loader, renderer,
        f"streamlit_memory_lazy_router_v1:{route.sport_id}:{route.market_id}", ttl_ms,
    )


def _nfl_game_total_adapter(route: RuntimeRoute) -> DestinationAdapter:
    """Dedicated API2 Game Totals Page1 + selected-game Page2 adapter."""
    def frozen_page1_owner():
        # Compatibility/proof anchor: Page 1 remains the frozen presentation owner.
        return _import("nfl_game_totals_page1_s_tier_v1")

    def loader():
        frozen_page1_owner()
        return _import("nfl_game_totals_hub_v11")

    def renderer(page):
        return page.render_nfl_game_totals_hub()

    return DestinationAdapter(
        (route.sport_id, route.market_id),
        loader,
        renderer,
        "nfl_game_totals_hub_v11",
        20_000,
    )


def _nfl_passing_yards_adapter(route: RuntimeRoute) -> DestinationAdapter:
    """Dedicated Kyre-gateway adapter; legacy NFL slate/data owners are not imported."""
    def loader():
        # Preserve the frozen professional gateway import as a compatibility/proof anchor.
        _import("nfl_passing_yards_professional_v1")
        return _import("nfl_passing_yards_simple_qb_grid_v1")

    def renderer(page):
        return page.render_nfl_passing_yards_simple_qb_grid()

    return DestinationAdapter(
        (route.sport_id, route.market_id), loader, renderer,
        "nfl_passing_yards_simple_qb_grid_v1", 20_000,
    )


def _nfl_adapter(route: RuntimeRoute, target: str, *, ttl_ms: int) -> DestinationAdapter:
    market_label = _market_label(route)

    def loader():
        page = _import(target)
        runtime = _import("nfl_active_slate_runtime_v1")
        nfl = _import("nfl_hub_v1")
        schedule = _import("nfl_passing_yards_next_slate_v1")
        return page, runtime, nfl, schedule

    def renderer(bundle):
        import streamlit as st

        page, runtime, nfl, schedule = bundle
        runtime.prepare_nfl_active_slate(
            st.session_state,
            today_et=datetime.now(nfl.ET).date(),
            primary_loader=nfl.load_nfl_slate,
            calendar_dates=schedule.nflverse_schedule_dates,
        )
        with runtime.install_nfl_date_input_bridge(st.session_state):
            return page.render_nfl_hub(market_label)

    return DestinationAdapter((route.sport_id, route.market_id), loader, renderer, target, ttl_ms)


def _cfb_page_adapter(route: RuntimeRoute, target: str, *, ttl_ms: int) -> DestinationAdapter:
    market_label = _market_label(route)

    def loader():
        return _import(target)

    def renderer(page):
        return page.render_cfb_hub(market_label)

    return DestinationAdapter((route.sport_id, route.market_id), loader, renderer, target, ttl_ms)


def _cfb_game_total_adapter(route: RuntimeRoute) -> DestinationAdapter:
    def loader():
        return (
            _import("cfb_game_total_page1_daily_slate_v1"),
            _import("cfb_game_total_page2_market_completeness_r1"),
        )

    def renderer(bundle):
        import streamlit as st

        page1, page2 = bundle
        event_id = ""
        for key in ("ks_cfb_game_total_event_id", "game_id"):
            raw = st.query_params.get(key)
            if isinstance(raw, (list, tuple)):
                raw = raw[-1] if raw else ""
            event_id = str(raw or "").strip()
            if event_id:
                break
        if not event_id:
            event_id = str(st.session_state.get("ks_cfb_game_total_event_id") or "").strip()
        if event_id:
            return page2.render_cfb_hub("Game Total")
        return page1.render_cfb_hub("Game Total")

    return DestinationAdapter(
        (route.sport_id, route.market_id), loader, renderer,
        "cfb_game_total_page1_daily_slate_v1+cfb_game_total_page2_market_completeness_r1", 30_000,
    )


def _nba_spread_adapter(route: RuntimeRoute) -> DestinationAdapter:
    def loader():
        return (
            _import("nba_spread_page_v6"),
            _import("nba_spread_page_provider_resilience_step3_r1"),
        )

    def renderer(bundle):
        page, provider_bridge = bundle
        bind = getattr(provider_bridge, "_bind_resilient_schedule_loader", None)
        if callable(bind):
            bind()
        return page.render_nba_spread_page()

    return DestinationAdapter((route.sport_id, route.market_id), loader, renderer, "nba_spread_page_v6", 15_000)


def _fail_closed_adapter(route: RuntimeRoute, reason: str) -> DestinationAdapter:
    def loader():
        return reason

    def renderer(message):
        import streamlit as st
        st.warning(str(message))
        return None

    return DestinationAdapter((route.sport_id, route.market_id), loader, renderer, f"fail-closed:{route.sport_id}:{route.market_id}", 0)


def resolve_destination(route: RuntimeRoute) -> DestinationAdapter:
    market = get_market(route.sport_id, route.market_id)
    if market is None:
        return _fail_closed_adapter(route, "This destination is not currently certified.")

    if route.sport_id == "mlb":
        return _root_adapter(route, ttl_ms=5_000 if route.market_id in {"live-game", "live-odds"} else 30_000)
    if route.sport_id == "wnba" and route.market_id == "pra":
        return _wnba_pra_step9_adapter(route)
    if route.sport_id == "wnba":
        return _root_adapter(route, ttl_ms=15_000)
    if route.sport_id == "nba" and route.market_id == "spread":
        return _nba_spread_adapter(route)
    if route.sport_id == "cfb":
        if route.market_id == "moneyline":
            return _cfb_page_adapter(route, "cfb_moneyline_clean_page_v1", ttl_ms=30_000)
        if route.market_id == "over-under":
            return _cfb_page_adapter(route, "cfb_over_under_clean_page_v38", ttl_ms=30_000)
        if route.market_id == "game-total":
            return _cfb_game_total_adapter(route)
        if route.market_id == "top-picks":
            return _cfb_page_adapter(route, "cfb_top_picks_page_v10", ttl_ms=30_000)
    if route.sport_id == "nfl":
        if route.market_id == "game-total":
            return _nfl_game_total_adapter(route)
        if route.market_id == "passing-yards":
            return _nfl_passing_yards_adapter(route)
        targets = {
            "spread": "nfl_spread_hub_v8",
            "rushing-yards": "nfl_rushing_yards_hub_v17",
            "receiving-yards": "nfl_receiving_yards_hub_v21",
        }
        target = targets.get(route.market_id, "nfl_hub_v18")
        ttl = 60_000 if route.market_id == "slate" else 20_000
        return _nfl_adapter(route, target, ttl_ms=ttl)

    return _fail_closed_adapter(route, "This route has no certified V5 adapter yet.")


def load_destination(adapter: DestinationAdapter) -> object:
    return adapter.loader()


def choose_prefetch(
    active: RuntimeRoute,
    candidates: Sequence[RuntimeRoute],
    *,
    limit: int = 2,
) -> tuple[PrefetchRequest, ...]:
    budget = max(0, min(2, int(limit)))
    active_key = (active.sport_id, active.market_id, tuple(sorted(dict(active.params).items())))
    seen = {active_key}
    chosen: list[PrefetchRequest] = []
    for candidate in candidates:
        key = (candidate.sport_id, candidate.market_id, tuple(sorted(dict(candidate.params).items())))
        if key in seen:
            continue
        seen.add(key)
        priority = 0 if candidate.sport_id == active.sport_id else 1
        chosen.append(PrefetchRequest(candidate, priority))
    chosen.sort(key=lambda request: request.priority)
    return tuple(chosen[:budget])


def run_prefetch(
    requests: Sequence[PrefetchRequest],
    load: Callable[[RuntimeRoute], object],
) -> tuple[object, ...]:
    results: list[object] = []
    for request in tuple(requests)[:2]:
        try:
            results.append(load(request.route))
        except Exception:
            continue
    return tuple(results)


__all__ = [
    "DestinationAdapter",
    "PrefetchRequest",
    "choose_prefetch",
    "load_destination",
    "resolve_destination",
    "run_prefetch",
]
