"""Successor overlay for the NFL Passing Yards simple QB grid.

Page 1 remains owned by the verified legacy grid. Only the selected-quarterback
detail handoff is replaced with the Page 2 analytics command center.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_simple_qb_grid_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "_nfl_passing_yards_simple_qb_grid_v1_verified",
    _LEGACY_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards Page 1 implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)


def _render_detail(st: Any, card: dict[str, Any]) -> None:
    from nfl_passing_yards_page2_command_center_v1 import render_page2

    render_page2(st, card)


# The verified Page 1 renderer resolves _render_detail from its module globals.
_legacy._render_detail = _render_detail

render_simple_qb_grid = _legacy.render_simple_qb_grid
build_qb_card_html = _legacy.build_qb_card_html
CSS = _legacy.CSS

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "CSS",
    "_render_detail",
    "build_qb_card_html",
    "render_simple_qb_grid",
})
