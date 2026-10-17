from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
FAST_SWITCH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
R2 = ROOT / "cfb_game_total_page2_visual_cleanup_r2.py"


def test_r2_public_refresh_is_owned_by_the_streamlit_entrypoint() -> None:
    app = APP.read_text(encoding="utf-8")
    fast = FAST_SWITCH.read_text(encoding="utf-8")
    r2 = R2.read_text(encoding="utf-8")

    assert (
        'CFB_GAME_TOTAL_PAGE2_R2_PUBLIC_REFRESH_R1 = '
        '"CFB_GAME_TOTAL_PAGE2_R2_PUBLIC_REFRESH_R1_2026_10_17"'
    ) in app
    assert (
        "from streamlit_memory_lazy_router_universal_nav_v2 import "
        "record_bootstrap_import_ms, render_app"
    ) in app
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_visual_cleanup_r2"' in fast
    assert 'ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R2_ACTIVE"' in r2
