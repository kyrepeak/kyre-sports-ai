"""Compatibility owner for NFL Rushing Yards Page 2.

The frozen Page 1 continues importing this module name. Page 2 implementation
now lives in the decision-first V2 command center.
"""
from nfl_rushing_yards_professional_v2 import CSS, MODEL_VERSION, build_rushing_detail_html, render_page2

__all__ = ["CSS", "MODEL_VERSION", "build_rushing_detail_html", "render_page2"]
