from pathlib import Path

import nba_pra_page2_command_center_v4 as v4


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
MARKER = "MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1_20261026"


def test_root_entrypoint_exposes_one_monster_runtime_convergence_marker() -> None:
    source = APP.read_text(encoding="utf-8")
    assert '_MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1 = "' + MARKER + '"' in source
    assert source.count(MARKER) == 1
    assert "_MONSTER_NBA_PRA_PAGE2_V4_RUNTIME_CONVERGENCE_R1}</span>" in source


def test_v4_css_is_one_closed_style_envelope_with_no_raw_tail() -> None:
    css = v4._css()
    assert css.count("<style>") == 1
    assert css.count("</style>") == 1
    assert css.rstrip().endswith("</style>")
    assert css.rstrip().split("</style>", 1)[1] == ""
    assert "/* MONSTER NBA PRA Page 2 V4 — compact decision terminal */" in css
