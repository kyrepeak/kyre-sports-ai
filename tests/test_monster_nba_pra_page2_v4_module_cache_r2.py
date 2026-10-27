from pathlib import Path

import nba_pra_page2_command_center_v4 as v4


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def test_page2_v4_renderer_and_sync_are_evicted_before_cache_invalidation() -> None:
    source = APP.read_text(encoding="utf-8")
    sync_pop = 'sys.modules.pop("nba_pra_page2_sync_v1", None)'
    renderer_pop = 'sys.modules.pop("nba_pra_page2_command_center_v4", None)'
    invalidate = "importlib.invalidate_caches()"
    assert sync_pop in source
    assert renderer_pop in source
    assert source.index(sync_pop) < source.index(invalidate)
    assert source.index(renderer_pop) < source.index(invalidate)
    assert source.count(sync_pop) == 1
    assert source.count(renderer_pop) == 1


def test_page2_v4_renderer_source_remains_the_repaired_single_style_envelope() -> None:
    css = v4._css()
    assert css.count("<style>") == 1
    assert css.count("</style>") == 1
    assert css.rstrip().endswith("</style>")
    assert css.rstrip().split("</style>", 1)[1] == ""
    assert "/* MONSTER NBA PRA Page 2 V4 — compact decision terminal */" in css
