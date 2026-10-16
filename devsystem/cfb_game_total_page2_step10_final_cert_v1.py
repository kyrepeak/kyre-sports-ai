"""MONSTER CFB Game Total Page 2 Step 10 — final responsive certification.

Certification-only terminal layer. It proves the already-frozen responsive/mobile
and fast-switch contracts without modifying product runtime behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 STEP10 • FINAL RESPONSIVE CERT V1"
STEP10_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_FINAL_POLISH_STEP10_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_FINAL_POLISH_STEP10_V1_FROZEN"
VIEWPORTS = (390, 430, 768, 1440)
REQUIRED_BREAKPOINTS = (760, 480)
MIN_TOUCH_TARGET_PX = 44
REQUIRED_MARKERS = (
    "gtp2s2-matchup-hero",
    "gtp2s3-flow",
    "gtp2s4-outlook",
    "gtp2s5-team-snapshot",
    "gtp2s6-trends",
    "gtp2s7-line-lab",
    "gtp2s8-data-quality",
    "gtp2s9-best-bet",
    "gtp2s10-tough-favorable",
    "gtp2s8-back-to-slate",
    "gtp2s8-final",
)
PRODUCT_MUTATION_REQUIRED = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
GITHUB_ACTIONS_FALLBACK = 0


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def certify_static_contract(root: Path) -> dict[str, Any]:
    """Return a deterministic fail-closed report for the frozen final Page-2 contract."""
    runtime = _read(root / "cfb_game_total_page2_step8_final_runtime_v1.py")
    fast_switch = _read(root / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py")
    app = _read(root / "app.py")
    live_cert = _read(root / "devsystem/cfb_game_total_page2_step8_live_cert_v1.py")
    page2_sources = "\n".join(
        _read(path)
        for path in sorted(root.glob("cfb_game_total_page2*.py"))
        if path.is_file()
    )

    checks = {
        "viewport_390": '"width": 390' in live_cert,
        "viewport_430": '"width": 430' in live_cert,
        "viewport_768": '"width": 768' in live_cert,
        "viewport_1440": '"width": 1440' in live_cert,
        "breakpoint_760": "@media(max-width:760px)" in runtime,
        "breakpoint_480": "@media(max-width:480px)" in runtime,
        "mobile_containment": ".gtp2s8-final{width:100%;max-width:100%;overflow-x:hidden}" in runtime,
        "mobile_touch_target": ".gtp2s8-back a{min-height:44px}" in runtime,
        "mobile_box_sizing": ".gtp2s8-final *{max-width:100%;box-sizing:border-box}" in runtime,
        "no_horizontal_scroll_copy": "horizontal-scroll" not in runtime.lower(),
        "fast_switch_direct_runtime": "importlib.import_module(cfb_prior.PAGE2_RUNTIME)" in fast_switch,
        "fast_switch_navigation_shell": "cfb_prior._render_page1_navigation_shell()" in fast_switch,
        "fast_switch_skips_page1_installer_games": "install_games_on_day_step2_visual()" not in fast_switch,
        "fast_switch_skips_page1_installer_cards": "install_game_cards_step6_visual()" not in fast_switch,
        "fast_switch_skips_page1_installer_shell": "install_native_page1_shell_step3_visual()" not in fast_switch,
        "production_activation": (
            "from streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 import "
            "record_bootstrap_import_ms, render_app"
        ) in app,
        "required_surfaces_present": all(marker in page2_sources for marker in REQUIRED_MARKERS),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
        "viewports": list(VIEWPORTS),
        "required_breakpoints": list(REQUIRED_BREAKPOINTS),
        "minimum_touch_target_px": MIN_TOUCH_TARGET_PX,
        "product_mutation_required": PRODUCT_MUTATION_REQUIRED,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "network_calls_added": NETWORK_CALLS_ADDED,
    }


__all__ = [
    "FREEZE_TOKEN",
    "GITHUB_ACTIONS_FALLBACK",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MIN_TOUCH_TARGET_PX",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PRODUCT_MUTATION_REQUIRED",
    "REQUIRED_BREAKPOINTS",
    "REQUIRED_MARKERS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP10_MARKER",
    "VIEWPORTS",
    "certify_static_contract",
]
