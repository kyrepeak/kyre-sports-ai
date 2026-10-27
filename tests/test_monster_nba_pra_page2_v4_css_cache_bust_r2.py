from __future__ import annotations

from pathlib import Path


def test_app_evicts_nba_pra_page2_modules_before_lazy_router_import() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    router_import = source.index(
        "from streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1 import"
    )
    invalidate = source.index("importlib.invalidate_caches()")

    required = (
        'sys.modules.pop("nba_pra_runtime_v2", None)',
        'sys.modules.pop("nba_pra_page2_sync_v1", None)',
        'sys.modules.pop("nba_pra_page2_command_center_v4", None)',
    )
    for statement in required:
        assert statement in source
        assert source.index(statement) < invalidate < router_import


def test_v4_css_source_remains_sealed_inside_single_style_element() -> None:
    import nba_pra_page2_command_center_v4 as v4

    css = v4._css().strip()
    assert css.startswith("<style>")
    assert css.endswith("</style>")
    assert css.count("<style>") == 1
    assert css.count("</style>") == 1
    assert css.index("MONSTER NBA PRA Page 2 V4 — compact decision terminal") < css.rfind("</style>")
