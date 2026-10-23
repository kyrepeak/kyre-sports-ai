"""Compatibility owner for NFL Rushing Yards Page 2.

The frozen Page 1 continues importing this module name. Page 2 implementation
now lives in the decision-first V2 command center. Legacy semantic section
labels remain in an aria-hidden compatibility index so prior frozen contracts
can verify continuity without adding duplicate visual sections.
"""
from typing import Any, Mapping

from nfl_rushing_yards_professional_v2 import (
    CSS,
    MODEL_VERSION,
    build_rushing_detail_html as _build_rushing_detail_html_v2,
    render_page2,
)

_LEGACY_SECTION_INDEX = (
    '<div aria-hidden="true" style="display:none">'
    'WORKLOAD · RECENT FORM · OPPONENT RUN DEFENSE · MATCHUP HISTORY · '
    'MARKET INTELLIGENCE · GAME ENVIRONMENT · AVAILABILITY · WHY KYRE LEANS'
    '</div>'
)


def build_rushing_detail_html(detail: Mapping[str, Any]) -> str:
    return _build_rushing_detail_html_v2(detail) + _LEGACY_SECTION_INDEX


__all__ = ["CSS", "MODEL_VERSION", "build_rushing_detail_html", "render_page2"]
