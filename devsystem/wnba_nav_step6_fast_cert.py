"""Fast exact-head cert for WNBA Navigation V2 Step 6."""
from __future__ import annotations
import ast, py_compile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=[
 ROOT/"wnba_pra_responsive_v2_step6.py",
 ROOT/"streamlit_memory_lazy_router_wnba_nav_v2_step6.py",
 ROOT/"wnba_pra_navigation_v2_step1.py",
 ROOT/"wnba_pra_slate_v2_step2.py",
 ROOT/"wnba_pra_game_center_v2_step3.py",
 ROOT/"wnba_pra_player_intelligence_v2_step4.py",
 ROOT/"wnba_pra_performance_v2_step5.py",
 ROOT/"app.py",
]
def require(v,m):
    if not v: raise AssertionError(m)
def main():
    for p in FILES: py_compile.compile(str(p),doraise=True)
    resp=FILES[0].read_text(encoding="utf-8")
    router=FILES[1].read_text(encoding="utf-8")
    nav=FILES[2].read_text(encoding="utf-8")
    s2=FILES[3].read_text(encoding="utf-8")
    s3=FILES[4].read_text(encoding="utf-8")
    s4=FILES[5].read_text(encoding="utf-8")
    s5=FILES[6].read_text(encoding="utf-8")
    app=FILES[7].read_text(encoding="utf-8")
    require("CERTIFIED_VIEWPORTS = (390, 768, 1440)" in resp,"viewports")
    require('"fresh_browser_session_per_viewport": True' in resp,"fresh sessions")
    require('"zero_horizontal_overflow_required": True' in resp,"overflow")
    require("MIN_TOUCH_TARGET_PX = 44" in resp,"touch")
    require(":focus-visible" in resp,"focus")
    require("@media (prefers-reduced-motion:reduce)" in resp,"reduced motion")
    for token in (".wn2-card",".wn3-player",".wn3-metrics",".wn4-hero",".wn4-strip",".wn4-grid",".wn4-games"):
        require(token in resp,f"responsive selector {token}")
    require("query-first state, then session state" in nav,"state persistence")
    require("return NavigationState(page=PAGE_GAME, game_id=safe.game_id)" in nav,"player back")
    require('"step": "2/7"' in s2 and '"step": "3/7"' in s3 and '"step": "4/7"' in s4 and '"step": "5/7"' in s5,"frozen steps")
    require('"native_on_click_single_rerun": True' in s5,"step5 transport")
    require('FROZEN_PERFORMANCE = "wnba_pra_performance_v2_step5"' in router,"step5 freeze")
    require("MAY_MODIFY_WNBA_MODEL = False" in router,"model guard")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router,"sport guard")
    require("from streamlit_memory_lazy_router_wnba_nav_v2_step6 import record_bootstrap_import_ms, render_app" in app,"activation")
    print("WNBA_NAV_STEP6_FAST_CERT_GREEN")
    return 0
if __name__=="__main__": raise SystemExit(main())
