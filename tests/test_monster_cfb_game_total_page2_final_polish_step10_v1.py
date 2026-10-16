from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/cfb_game_total_page2_step10_final_cert_v1.py"
RUNTIME = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"
FAST_SWITCH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_cert():
    assert CERT.is_file(), "Step-10 final responsive certification artifact is not implemented yet"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step10_cert", CERT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step10_certification_artifact_exists_before_green() -> None:
    assert CERT.is_file(), "Step-10 final responsive certification artifact is not implemented yet"


def test_step10_cert_declares_required_viewports_markers_and_touch_target() -> None:
    cert = _load_cert()
    assert cert.VIEWPORTS == (390, 430, 768, 1440)
    assert cert.REQUIRED_BREAKPOINTS == (760, 480)
    assert cert.MIN_TOUCH_TARGET_PX == 44
    for marker in (
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
    ):
        assert marker in cert.REQUIRED_MARKERS
    assert "gtp2s7-best-bet" not in cert.REQUIRED_MARKERS


def test_step10_existing_runtime_already_meets_mobile_containment_contract() -> None:
    source = _read(RUNTIME)
    assert "@media(max-width:760px)" in source
    assert "@media(max-width:480px)" in source
    assert ".gtp2s8-final{width:100%;max-width:100%;overflow-x:hidden}" in source
    assert ".gtp2s8-back a{min-height:44px}" in source
    assert ".gtp2s8-final *{max-width:100%;box-sizing:border-box}" in source
    assert "horizontal-scroll" not in source.lower()


def test_step10_preserves_step9_fast_switch_and_current_production_activation() -> None:
    fast = _read(FAST_SWITCH)
    app = _read(APP)
    assert "importlib.import_module(cfb_prior.PAGE2_RUNTIME)" in fast
    assert "cfb_prior._render_page1_navigation_shell()" in fast
    assert "install_games_on_day_step2_visual()" not in fast
    assert "install_game_cards_step6_visual()" not in fast
    assert "install_native_page1_shell_step3_visual()" not in fast
    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 import "
        "record_bootstrap_import_ms, render_app"
    ) in app


def test_step10_certification_is_display_only_and_requires_no_product_mutation() -> None:
    cert = _load_cert()
    assert cert.PRODUCT_MUTATION_REQUIRED is False
    assert cert.MAY_MODIFY_MODEL is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SELECTION is False
    assert cert.MAY_MODIFY_OTHER_SPORTS is False
    assert cert.NETWORK_CALLS_ADDED == 0
    assert cert.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_step10_static_certification_report_passes_all_contract_checks() -> None:
    cert = _load_cert()
    report = cert.certify_static_contract(ROOT)
    assert report["passed"] is True
    assert report["product_mutation_required"] is False
    assert report["viewports"] == [390, 430, 768, 1440]
    assert report["failed_checks"] == []
