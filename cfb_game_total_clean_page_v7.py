"""CFB Game Total Clean Page V7 — compact team evidence flow.

Presentation-only wrapper over closed V6. V7 keeps the frozen V6 Game Total
analysis path intact and changes only how the already-built team evidence is
presented: two compact cards stay in the connected flow while the full evidence
bodies remain available inside V6's existing collapsed raw-evidence drawer.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v6 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V7 • V155 COMPACT TEAM EVIDENCE"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v6"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3
runtime_display = prior.runtime_display

_V155_TEAM_CSS = r"""
<style>
.gt155-team-flow{margin:8px 0 3px;padding-top:7px;border-top:1px solid rgba(121,146,169,.12)}
.gt155-team-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt155-team-head b{color:#eef5fb;font-size:.50rem;font-weight:950;letter-spacing:.06em}.gt155-team-head span{color:var(--gt-gray);font-size:.27rem}
.gt155-team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt155-team-card{padding:8px 9px;border-radius:11px;background:#0a1823;border:1px solid rgba(116,145,170,.14);min-width:0}.gt155-team-cardhead{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt155-team-name{color:#f4f8fb;font-size:.53rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-record{padding:3px 6px;border-radius:999px;background:rgba(112,73,176,.17);color:var(--gt-purple);font-size:.27rem;font-weight:950;white-space:nowrap}
.gt155-team-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:6px}.gt155-team-metric{padding:5px;border-radius:7px;background:#102330;min-width:0}.gt155-team-metric b{display:block;color:#edf4f9;font-size:.40rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-metric span{display:block;color:var(--gt-gray);font-size:.20rem;font-weight:850;text-transform:uppercase;margin-top:2px}.gt155-team-source{margin-top:6px;color:var(--gt-gray);font-size:.24rem;line-height:1.35;overflow-wrap:anywhere}.gt155-team-source strong{color:var(--gt-green)}
@media(max-width:760px){.gt155-team-grid{grid-template-columns:1fr}.gt155-team-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gt155-team-head{align-items:flex-start;flex-direction:column;gap:2px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _team_card(state: Mapping[str, Any], side: str) -> str:
    team = _clean(state.get("team")) or side.title()
    record = _clean(state.get("record")) or "—"
    source = _clean(state.get("data_source")) or "Completed-game evidence"
    form = _clean(state.get("recent_form")) or "—"
    test_id = "gt155-away-team-card" if side == "away" else "gt155-home-team-card"
    return f"""
<div class="gt155-team-card" data-testid="{test_id}">
  <div class="gt155-team-cardhead">
    <div class="gt155-team-name">{escape(team)}</div>
    <div class="gt155-team-record">{escape(record)}</div>
  </div>
  <div class="gt155-team-metrics">
    <div class="gt155-team-metric"><b>{_num(state.get('ppg'))}</b><span>PPG</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('allowed_pg'))}</b><span>Allowed</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('point_diff_pg'))}</b><span>Point diff</span></div>
    <div class="gt155-team-metric"><b>{escape(form)}</b><span>Recent form</span></div>
  </div>
  <div class="gt155-team-source"><strong>DATA</strong> • {escape(source)}</div>
</div>
"""


def _render_compact_team_cards(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    st.markdown(_V155_TEAM_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="gt155-team-flow" data-testid="gt155-team-evidence-flow">
  <div class="gt155-team-head"><b>🏈 TEAM EVIDENCE</b><span>Key team facts stay visible • full detail stays collapsed</span></div>
  <div class="gt155-team-grid">{_team_card(away, 'away')}{_team_card(home, 'home')}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_raw_team_evidence(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    """Render both full team bodies inside V6's one existing raw drawer."""
    away_team = _clean(away.get("team")) or "Away team"
    home_team = _clean(home.get("team")) or "Home team"
    st.markdown(f"**{away_team} • full evidence**")
    prior.prior._render_team_evidence_body(away)
    st.divider()
    st.markdown(f"**{home_team} • full evidence**")
    prior.prior._render_team_evidence_body(home)


_ORIGINAL_STEPS_1_10 = prior._render_steps_1_10_rail
_ORIGINAL_EVIDENCE_CENTER = prior.prior._render_evidence_center


def _render_steps_1_10_with_team_cards(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
) -> None:
    _ORIGINAL_STEPS_1_10(identity, away, home, display_game)
    _render_compact_team_cards(away, home)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Run frozen V6 with presentation-only evidence hooks, then restore them."""
    original_steps = prior._render_steps_1_10_rail
    original_evidence = prior.prior._render_evidence_center
    prior._render_steps_1_10_rail = _render_steps_1_10_with_team_cards
    prior.prior._render_evidence_center = _render_raw_team_evidence
    try:
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior._render_steps_1_10_rail = original_steps
        prior.prior._render_evidence_center = original_evidence


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V155 Game Total V7 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
]
