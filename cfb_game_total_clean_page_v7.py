"""CFB Game Total Clean Page V7 — compact team evidence flow.

Presentation-only wrapper over certified V6. V6 remains the owner of the frozen
Game Total analysis path. V7 injects compact away/home evidence cards into the
connected Steps 1–10 rail and flattens the old nested team evidence inside V6's
single existing raw-evidence drawer.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v6 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V7 • V155 TEAM EVIDENCE FLOW"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v6"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_TEAM_EVIDENCE_CSS = r"""
<style>
.gt155-team-flow{margin:8px 0 6px}.gt155-team-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt155-team-head b{color:#eef5fb;font-size:.53rem;font-weight:950;letter-spacing:.07em}.gt155-team-head span{color:var(--gt-gray);font-size:.29rem}.gt155-team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt155-team-card{padding:9px;border-radius:11px;background:linear-gradient(145deg,#0a1823,#0b1520);border:1px solid rgba(121,98,191,.20);min-width:0}.gt155-team-title{display:flex;align-items:center;justify-content:space-between;gap:7px}.gt155-team-title b{color:#f5f9fc;font-size:.54rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-record{padding:3px 6px;border-radius:999px;background:rgba(112,73,176,.18);color:var(--gt-purple);font-size:.28rem;font-weight:950;white-space:nowrap}.gt155-team-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:6px}.gt155-team-metric{padding:6px;border-radius:7px;background:#0e202c;border:1px solid rgba(119,139,159,.10);min-width:0}.gt155-team-metric b{display:block;color:#e9f1f6;font-size:.43rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt155-team-metric span{display:block;color:var(--gt-gray);font-size:.20rem;text-transform:uppercase;margin-top:2px}.gt155-team-foot{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.gt155-team-chip{padding:3px 5px;border-radius:6px;background:#0d1c28;color:#9fb0bf;font-size:.24rem}.gt155-team-source{margin-top:6px;color:#75899a;font-size:.26rem;line-height:1.35;overflow-wrap:anywhere}.gt155-team-source strong{color:var(--gt-green)}.gt155-deep-title{margin:3px 0 7px;color:var(--gt-purple);font-size:.58rem;font-weight:950}.gt155-deep-team{margin:8px 0 4px;padding-top:6px;border-top:1px solid rgba(121,146,169,.13);color:#edf4f9;font-size:.52rem;font-weight:950}
@media(max-width:760px){.gt155-team-grid{grid-template-columns:1fr}.gt155-team-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


def _team_card(state: Mapping[str, Any], side: str) -> str:
    team = _clean(state.get("team")) or side.title()
    record = _clean(state.get("record")) or "—"
    recent = _clean(state.get("recent_form")) or "—"
    source = _clean(state.get("data_source")) or _clean(state.get("source")) or "Source unavailable"
    return f"""
<div class="gt155-team-card" data-testid="gt155-team-evidence-{side}">
  <div class="gt155-team-title"><b>{escape(team)}</b><span class="gt155-team-record">{escape(record)}</span></div>
  <div class="gt155-team-metrics">
    <div class="gt155-team-metric"><b>{_num(state.get('ppg'))}</b><span>PPG</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('allowed_pg'))}</b><span>Allowed / game</span></div>
    <div class="gt155-team-metric"><b>{_num(state.get('point_diff_pg'))}</b><span>Point diff</span></div>
    <div class="gt155-team-metric"><b>{escape(recent)}</b><span>Recent form</span></div>
  </div>
  <div class="gt155-team-foot">
    <span class="gt155-team-chip">Home {escape(_clean(state.get('home_split')) or '—')}</span>
    <span class="gt155-team-chip">Away {escape(_clean(state.get('away_split')) or '—')}</span>
    <span class="gt155-team-chip">SOS {_pct(state.get('sos_opponent_win_pct'))}</span>
    <span class="gt155-team-chip">Sample {int(state.get('sample_games') or 0)}</span>
  </div>
  <div class="gt155-team-source"><strong>Data source</strong> • {escape(source)}</div>
</div>
"""


def _render_team_evidence_flow(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    st.markdown(
        _TEAM_EVIDENCE_CSS
        + f"""
<div class="gt155-team-flow" data-testid="gt155-team-evidence-flow">
  <div class="gt155-team-head"><b>👥 TEAM EVIDENCE</b><span>Compact current-team context • full detail below</span></div>
  <div class="gt155-team-grid">{_team_card(away, 'away')}{_team_card(home, 'home')}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_flat_team_evidence(away: Mapping[str, Any], home: Mapping[str, Any]) -> None:
    st.markdown('<div class="gt155-deep-title">🔬 DEEP TEAM EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="gt155-deep-team">{escape(_clean(away.get("team")) or "Away team")}</div>', unsafe_allow_html=True)
    prior.prior._render_team_evidence_body(away)
    st.markdown(f'<div class="gt155-deep-team">{escape(_clean(home.get("team")) or "Home team")}</div>', unsafe_allow_html=True)
    prior.prior._render_team_evidence_body(home)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    old_steps = prior._render_steps_1_10_rail
    old_evidence = prior.prior._render_evidence_center

    def _render_steps_with_team_evidence(
        identity: Mapping[str, Any],
        away: Mapping[str, Any],
        home: Mapping[str, Any],
        display_game: Mapping[str, Any],
    ) -> None:
        old_steps(identity, away, home, display_game)
        _render_team_evidence_flow(away, home)

    prior._render_steps_1_10_rail = _render_steps_with_team_evidence
    prior.prior._render_evidence_center = _render_flat_team_evidence
    try:
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior._render_steps_1_10_rail = old_steps
        prior.prior._render_evidence_center = old_evidence


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V155 Game Total V7 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_flat_team_evidence",
    "_render_team_evidence_flow",
    "render_cfb_hub",
    "render_game_total_hub",
]
