from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V36 = ROOT / "nfl_passing_yards_hub_v36.py"


def test_v36_has_phone_safe_breakpoints_and_touch_targets() -> None:
    source = V36.read_text(encoding="utf-8")

    assert "@media(max-width:760px)" in source
    assert "@media(max-width:480px)" in source
    assert "min-height:44px" in source
    assert "overflow-wrap:anywhere" in source
    assert "overflow-x:auto" in source


def test_v36_stacks_dense_surfaces_on_narrow_phones() -> None:
    source = V36.read_text(encoding="utf-8")

    assert ".monster-qb-hero-grid,.monster-why-wrap,.monster-deep-wrap{grid-template-columns:1fr}" in source
    assert ".monster-qb-hero .kpy10-hero{grid-template-columns:repeat(2,minmax(0,1fr))!important}" in source
    assert ".monster-why-projection{grid-template-columns:1fr}" in source
    assert ".monster-evidence-body .kpy-xmetrics" in source
