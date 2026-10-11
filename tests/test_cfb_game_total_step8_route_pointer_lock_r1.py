from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def test_step8_serializes_shared_route_pointer_swaps() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    # Production evidence showed overlapping Streamlit sessions can observe the
    # shared Page-1/Page-2 module pointers while another render is swapping them.
    # The exact router must serialize every temporary pointer mutation.
    assert "from threading import RLock" in source
    assert "_ROUTE_POINTER_LOCK = RLock()" in source
    assert "with _ROUTE_POINTER_LOCK:" in source

    page1 = source.split("def _render_native_page1()", 1)[1].split("def _clear_auto_event_after_page1", 1)[0]
    page2 = source.split("def render_app()", 1)[1].split("__all__", 1)[0]

    assert "with _ROUTE_POINTER_LOCK:" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE1_NATIVE_ROUTE" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = original_page1" in page1

    assert "with _ROUTE_POINTER_LOCK:" in page2
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in page2
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in page2
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in page2
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in page2
    assert "live_owner.ACTIVE_PAGE = original_live_page" in page2
    assert "render_owner.ACTIVE_PAGE = original_render_page" in page2
