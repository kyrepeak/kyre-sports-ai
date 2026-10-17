from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
REQUIREMENTS = ROOT / "requirements.txt"
FAST_SWITCH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
R2 = ROOT / "cfb_game_total_page2_visual_cleanup_r2.py"


def test_r2_public_refresh_forces_a_full_streamlit_rebuild() -> None:
    app = APP.read_text(encoding="utf-8")
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    fast = FAST_SWITCH.read_text(encoding="utf-8")
    r2 = R2.read_text(encoding="utf-8")

    assert (
        "# CFB Game Total Page 2 R2 public full Streamlit redeploy trigger "
        "2026-10-17 R1"
    ) in requirements
    assert (
        "from streamlit_memory_lazy_router_universal_nav_v2 import "
        "record_bootstrap_import_ms, render_app"
    ) in app
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_visual_cleanup_r2"' in fast
    assert 'ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R2_ACTIVE"' in r2
