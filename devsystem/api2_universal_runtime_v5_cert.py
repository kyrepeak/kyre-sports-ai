"""Deterministic final certification for API2 Universal Runtime V5."""
from universal_sports_nav_controller_v1 import RouteIntent
from universal_runtime_v5_loader_v11 import choose_prefetch, resolve_destination
from universal_runtime_v5_scope import commit_if_current, new_scope
from universal_runtime_v5_state import RuntimeRoute, RuntimeState, commit_intent


def certify() -> None:
    nfl = RuntimeRoute("nfl", "rushing-yards", {"game_id": "g1"}, 0, "default")
    runtime = RuntimeState(nfl, {"nfl": nfl}, 0)
    runtime = commit_intent(runtime, RouteIntent("nba", "spread", "tap"), {"game_id": "n1"})
    assert runtime.active.sport_id == "nba" and runtime.active.generation == 1

    stale_scope = new_scope(nfl)
    painted: list[str] = []
    assert commit_if_current(stale_scope, runtime, lambda: painted.append("stale")) is None
    assert painted == []

    top = RuntimeRoute("cfb", "top-picks", {}, runtime.generation + 1, "cert")
    adapter = resolve_destination(top)
    assert adapter.source_version == "cfb_top_picks_page_v11"
    choices = choose_prefetch(
        top,
        (
            RuntimeRoute("cfb", "moneyline", {}, 0, "cert"),
            RuntimeRoute("cfb", "game-total", {}, 0, "cert"),
            RuntimeRoute("nba", "spread", {}, 0, "cert"),
        ),
        limit=2,
    )
    assert len(choices) <= 2

    import streamlit_memory_lazy_router_universal_runtime_v5 as terminal
    assert terminal.DEFAULT_RUNTIME_MODE == terminal.V5_MODE_ACTIVE
    assert terminal.FALLBACK_RUNTIME_MODULE == "streamlit_memory_lazy_router_api2_nfl_rushing_cleanup_v1"
    print("API2_UNIVERSAL_RUNTIME_V5_CERT_GREEN")


if __name__ == "__main__":
    certify()
