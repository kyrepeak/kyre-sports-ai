from __future__ import annotations

import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as router


def test_v181_bypasses_nested_active_page_clobber_chain() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v33"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v180"

    source = router._render_exact_game_total_surface.__code__.co_names
    assert "render_owner" in source
    assert "_render_exact_game_total_surface" in source

    # The live render must target the original render owner, not prior V180's
    # forwarding renderer, otherwise V176-V180 can overwrite ACTIVE_PAGE again.
    assert router.render_owner is render_owner


def test_v181_preserves_projection_guardrails() -> None:
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_v181_preserves_v180_jump_consumers() -> None:
    assert router._consume_category_jump_query.__name__ == "_consume_category_jump_query"
    assert router._consume_sport_jump_query.__name__ == "_consume_sport_jump_query"
