"""API 2 Step 2E universal sports-router registration contract.

This is the canonical ownership registry for live NFL, CFB, NBA and WNBA page
routes in Universal Runtime V5. It is intentionally data-only: page adapters
remain in ``universal_runtime_v5_loader`` and provider access remains behind
Kyre Sports API. Step 2D data-truth semantics are inherited by every entry.
"""
from __future__ import annotations

from dataclasses import dataclass

from universal_sports_nav_registry_v1 import visible_sports


API2_STEP2E_UNIVERSAL_ROUTER_COMPLETION_V1_FROZEN = True
DATA_GATEWAY = "kyre_sports_api"
DATA_TRUTH_GATE = "api2_step2d_data_truth_gate_v1"
SCOPE_SPORTS = frozenset({"nfl", "cfb", "nba", "wnba"})


@dataclass(frozen=True)
class RouterRegistration:
    sport_id: str
    market_id: str
    adapter_kind: str
    target: str
    data_gateway: str = DATA_GATEWAY
    data_truth_gate: str = DATA_TRUTH_GATE
    frontend_direct_provider: bool = False

    @property
    def route_key(self) -> tuple[str, str]:
        return (self.sport_id, self.market_id)


def _r(sport: str, market: str, kind: str, target: str) -> RouterRegistration:
    return RouterRegistration(sport, market, kind, target)


_REGISTRATIONS = (
    # NFL — every live route is explicit; there is no generic market fallback.
    _r("nfl", "slate", "nfl-slate", "nfl_slate_runtime_v1"),
    _r("nfl", "moneyline", "nfl-moneyline", "nfl_moneyline_hub_v19"),
    _r("nfl", "spread", "nfl-spread", "nfl_spread_hub_v10"),
    _r("nfl", "game-total", "nfl-game-total", "nfl_game_totals_compact_layout_v1"),
    _r("nfl", "passing-yards", "nfl-passing-yards", "nfl_passing_yards_simple_qb_grid_v1"),
    _r("nfl", "rushing-yards", "nfl-dedicated-hub", "nfl_rushing_yards_hub_v17"),
    _r("nfl", "receiving-yards", "nfl-receiving-yards", "nfl_receiving_yards_hub_v22"),
    _r("nfl", "receptions", "nfl-receptions", "nfl_receptions_runtime_v1"),
    _r("nfl", "passing-tds", "nfl-passing-tds", "nfl_passing_tds_runtime_v1"),
    _r("nfl", "anytime-td", "nfl-anytime-td", "nfl_anytime_td_runtime_v1"),
    _r("nfl", "daily-picks", "nfl-daily-picks", "nfl_daily_picks_command_center_v4"),

    # CFB — player props now has a first-class runtime adapter.
    _r("cfb", "moneyline", "terminal-overlay", "cfb_moneyline_clean_page_v8"),
    _r("cfb", "over-under", "cfb-page", "cfb_over_under_clean_page_v38"),
    _r("cfb", "game-total", "cfb-game-total", "cfb_game_total_page1_daily_slate_v1+cfb_game_total_page2_market_completeness_r1"),
    _r("cfb", "top-picks", "cfb-page", "cfb_top_picks_page_v10"),
    _r("cfb", "player-props", "cfb-player-props", "cfb_player_props_runtime_v3"),

    # NBA — PRA is promoted from terminal-only shadow to canonical route ownership.
    _r("nba", "spread", "nba-spread", "nba_spread_page_v6"),
    _r("nba", "pra", "nba-pra", "nba_pra_runtime_v2"),

    # WNBA — legacy renderer remains the presentation owner, but every market is
    # explicitly registered at the universal boundary.
    _r("wnba", "points", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "rebounds", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "assists", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "rebounds-assists", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "pra", "wnba-pra-step9", "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"),
    _r("wnba", "spread", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "moneyline", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "game-total", "wnba-root", "streamlit_memory_lazy_router_v1"),
    _r("wnba", "daily-picks", "wnba-root", "streamlit_memory_lazy_router_v1"),
)

ROUTER_REGISTRY = {registration.route_key: registration for registration in _REGISTRATIONS}


def get_router_registration(sport_id: str, market_id: str) -> RouterRegistration | None:
    key = (str(sport_id or "").strip().lower(), str(market_id or "").strip().lower())
    return ROUTER_REGISTRY.get(key)


def require_registered_route(sport_id: str, market_id: str) -> RouterRegistration:
    registration = get_router_registration(sport_id, market_id)
    if registration is None:
        raise RuntimeError(f"API2_STEP2E_UNREGISTERED_ROUTE:{sport_id}:{market_id}")
    return registration


def covered_route_keys() -> set[tuple[str, str]]:
    return set(ROUTER_REGISTRY)


def _expected_route_keys() -> set[tuple[str, str]]:
    return {
        (sport.id, market.id)
        for sport in visible_sports()
        if sport.id in SCOPE_SPORTS
        for market in sport.markets
        if market.live
    }


def validate_router_registry() -> tuple[str, ...]:
    errors: list[str] = []
    expected = _expected_route_keys()
    actual = covered_route_keys()
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append("missing routes: " + ",".join(f"{s}/{m}" for s, m in missing))
    if extra:
        errors.append("orphan routes: " + ",".join(f"{s}/{m}" for s, m in extra))

    for key, registration in ROUTER_REGISTRY.items():
        if registration.route_key != key:
            errors.append(f"{key}: route identity mismatch")
        if registration.data_gateway != DATA_GATEWAY:
            errors.append(f"{key}: non-Kyre application gateway")
        if registration.data_truth_gate != DATA_TRUTH_GATE:
            errors.append(f"{key}: Step 2D data-truth gate missing")
        if registration.frontend_direct_provider:
            errors.append(f"{key}: direct provider frontend bypass")
        if registration.adapter_kind in {"implicit", "generic-fallback", "fail-closed"}:
            errors.append(f"{key}: implicit/fail-closed registration")
        if not registration.target:
            errors.append(f"{key}: empty target")
    return tuple(errors)


__all__ = [
    "API2_STEP2E_UNIVERSAL_ROUTER_COMPLETION_V1_FROZEN",
    "DATA_GATEWAY",
    "DATA_TRUTH_GATE",
    "ROUTER_REGISTRY",
    "RouterRegistration",
    "SCOPE_SPORTS",
    "covered_route_keys",
    "get_router_registration",
    "require_registered_route",
    "validate_router_registry",
]
