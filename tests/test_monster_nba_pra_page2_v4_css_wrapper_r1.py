from __future__ import annotations

import nba_pra_page2_command_center_v4 as v4


def test_v4_css_is_fully_contained_inside_one_style_element() -> None:
    css = v4._css()
    stripped = css.strip()

    assert stripped.startswith("<style>")
    assert stripped.endswith("</style>")
    assert stripped.count("<style>") == 1
    assert stripped.count("</style>") == 1

    close_at = stripped.rfind("</style>")
    marker_at = stripped.index("MONSTER NBA PRA Page 2 V4 — compact decision terminal")
    rule_at = stripped.index(".p2v4-hero")

    assert marker_at < close_at
    assert rule_at < close_at
    assert stripped[close_at + len("</style>") :].strip() == ""
