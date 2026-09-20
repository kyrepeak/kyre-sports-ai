"""CFB Game Total clean page V23 — page cleanup Step 4 Team Evidence UI.

Presentation-only successor to V22. Step 3 data stays frozen. V23 only replaces
the Team Evidence renderer with explicit stateful cards and responsive layout.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v10 as presentation_owner
import cfb_game_total_clean_page_v22 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V23 • PAGE CLEANUP STEP 4 TEAM EVIDENCE UI"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v22"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 4 TEAM EVIDENCE UI ACTIVE"
STEP4_TEAM_EVIDENCE_UI_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP4_TEAM_EVIDENCE_UI_ACTIVE"

_PRESENTATION_LOCK = RLock()

STEP4_TEAM_EVIDENCE_CSS = r"""
<style>
.gt204-section{
  margin-top:10px;
  padding:11px;
  border:1px solid rgba(91,158,198,.25);
  border-radius:15px;
  background:linear-gradient(180deg,#081724,#07131e);
}
.gt204-sectionhead{
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:10px;
  margin-bottom:9px;
}
.gt204-sectionhead b{
  color:#f2f7fd;
  font-size:.49rem;
  font-weight:950;
  letter-spacing:.06em;
}
.gt204-sectionhead span{
  color:#7890a5;
  font-size:.25rem;
  text-align:right;
}
.gt204-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:9px;
}
.gt204-card{
  position:relative;
  min-width:0;
  padding:10px;
  border:1px solid rgba(84,154,193,.26);
  border-left:3px solid #ff704f;
  border-radius:12px;
  background:linear-gradient(150deg,#0a1d2a,#0b2332);
  overflow:hidden;
}
.gt204-card.home{border-left-color:#5489ff}
.gt204-card::after{
  content:"";
  position:absolute;
  inset:0;
  pointer-events:none;
  background:radial-gradient(circle at 85% 0%,rgba(93,160,255,.08),transparent 36%);
}
.gt204-top{
  position:relative;
  z-index:1;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:9px;
}
.gt204-id{
  display:flex;
  align-items:center;
  gap:9px;
  min-width:0;
}
.gt204-logo img,
.gt204-logo .gt160-evidence-logo{
  width:42px;
  height:42px;
  object-fit:contain;
}
.gt204-logo .gt160-evidence-logo-fallback{
  width:42px;
  height:42px;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius:10px;
  background:#10293b;
  color:#8fcfff;
  font-weight:950;
}
.gt204-copy{min-width:0}
.gt204-name{
  color:#f2f7fd;
  font-size:.48rem;
  font-weight:950;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.gt204-meta{
  margin-top:2px;
  color:#8ca2b7;
  font-size:.25rem;
}
.gt204-record{
  flex:0 0 auto;
  padding:4px 8px;
  border-radius:999px;
  border:1px solid rgba(167,128,255,.30);
  background:rgba(100,71,193,.18);
  color:#d4c0ff;
  font-size:.25rem;
  font-weight:950;
}
.gt204-stats{
  position:relative;
  z-index:1;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:6px;
  margin-top:9px;
}
.gt204-stat{
  min-width:0;
  padding:8px 7px;
  border:1px solid rgba(87,151,188,.18);
  border-radius:9px;
  background:#0e2939;
}
.gt204-stat[data-state="READY"]{border-color:rgba(98,239,182,.22)}
.gt204-stat[data-state="PENDING"]{
  border-color:rgba(244,206,99,.32);
  background:rgba(87,67,16,.18);
}
.gt204-value{
  display:block;
  color:#edf5fb;
  font-size:.45rem;
  font-weight:950;
  line-height:1.05;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.gt204-stat.diff.positive .gt204-value{color:#62efb6}
.gt204-stat.diff.negative .gt204-value{color:#ff8b80}
.gt204-stat[data-state="PENDING"] .gt204-value{color:#f4ce63}
.gt204-label{
  display:block;
  margin-top:3px;
  color:#7790a4;
  font-size:.18rem;
  text-transform:uppercase;
  letter-spacing:.03em;
}
.gt204-state{
  display:inline-flex;
  margin-top:5px;
  padding:2px 5px;
  border-radius:999px;
  border:1px solid rgba(98,239,182,.26);
  background:rgba(20,105,73,.14);
  color:#62efb6;
  font-size:.16rem;
  font-weight:950;
}
.gt204-state.pending{
  border-color:rgba(244,206,99,.30);
  background:rgba(113,84,9,.16);
  color:#f4ce63;
}
.gt204-foot{
  position:relative;
  z-index:1;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:7px;
  margin-top:8px;
  padding-top:7px;
  border-top:1px solid rgba(82,145,183,.14);
}
.gt204-foot span{
  color:#8198ab;
  font-size:.20rem;
  min-width:0;
}
.gt204-foot .source{
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  text-align:right;
}
@media(max-width:850px){
  .gt204-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:620px){
  .gt204-grid{grid-template-columns:1fr}
  .gt204-sectionhead{align-items:flex-start;flex-direction:column}
}
@media(max-width:420px){
  .gt204-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .gt204-foot{align-items:flex-start;flex-direction:column}
  .gt204-foot .source{text-align:left;white-space:normal}
}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> tuple[str, bool]:
    try:
        return f"{float(value):.1f}", True
    except (TypeError, ValueError):
        return "Pending", False


def _form(value: Any) -> tuple[str, bool]:
    text = _clean(value)
    if text and text != "—":
        return text, True
    return "Pending", False


def _record(stats: Mapping[str, Any]) -> str:
    return _clean(stats.get("record")) or "Record pending"


def _source(stats: Mapping[str, Any]) -> str:
    return (
        _clean(stats.get("source"))
        or _clean(stats.get("team_evidence_source"))
        or "Verified team evidence"
    )


def _team_evidence_html_v23(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    def stat_tile(key: str, label: str, value: Any, diff: bool = False) -> str:
        if key == "recent-form":
            display, ready = _form(value)
            numeric = None
        else:
            display, ready = _num(value)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = None

        state = "READY" if ready else "PENDING"
        state_class = "" if ready else " pending"
        classes = ["gt204-stat"]
        if diff:
            classes.append("diff")
            if numeric is not None:
                classes.append("positive" if numeric >= 0 else "negative")
        return (
            f'<div class="{" ".join(classes)}" data-stat="{escape(key)}" '
            f'data-state="{state}">'
            f'<b class="gt204-value">{escape(display)}</b>'
            f'<span class="gt204-label">{escape(label)}</span>'
            f'<span class="gt204-state{state_class}">{state}</span>'
            f'</div>'
        )

    def card(
        team_id: Mapping[str, Any],
        stats: Mapping[str, Any],
        home_side: bool,
    ) -> str:
        name = _clean(team_id.get("team")) or _clean(stats.get("team")) or "Team"
        conference = _clean(team_id.get("conference")) or "NCAAF"
        record = _record(stats)
        sample = int(stats.get("sample_games") or 0)
        quality = _clean(stats.get("quality")) or "CHECK"
        sample_text = f"{sample} completed game{'s' if sample != 1 else ''}" if sample else "Sample pending"
        card_state = "READY" if (
            stats.get("ppg") is not None
            and stats.get("allowed_pg") is not None
            and stats.get("point_diff_pg") is not None
            and _clean(stats.get("recent_form")) not in {"", "—"}
        ) else "PENDING"
        home_class = " home" if home_side else ""

        return f"""
<div class="gt204-card{home_class}" data-team="{escape(name)}" data-state="{card_state}">
  <div class="gt204-top">
    <div class="gt204-id">
      <div class="gt204-logo">{presentation_owner._team_logo(team_id)}</div>
      <div class="gt204-copy">
        <div class="gt204-name">{escape(name)}</div>
        <div class="gt204-meta">{escape(conference)} • {escape(quality)}</div>
      </div>
    </div>
    <span class="gt204-record">{escape(record)}</span>
  </div>
  <div class="gt204-stats">
    {stat_tile("ppg", "PPG", stats.get("ppg"))}
    {stat_tile("allowed", "Allowed / Game", stats.get("allowed_pg"))}
    {stat_tile("point-diff", "Point Diff / Game", stats.get("point_diff_pg"), True)}
    {stat_tile("recent-form", "Recent Form", stats.get("recent_form"))}
  </div>
  <div class="gt204-foot">
    <span>{escape(sample_text)}</span>
    <span class="source">{escape(_source(stats))}</span>
  </div>
</div>"""

    away_id = identity.get("away") or {}
    home_id = identity.get("home") or {}
    return f"""
<div class="gt204-section" data-testid="gt204-team-evidence"
     data-step4-presentation="{STEP4_TEAM_EVIDENCE_UI_MARKER}">
  <div class="gt204-sectionhead">
    <b>🏈 TEAM EVIDENCE</b>
    <span>Scoring profile • prevention • differential • current form</span>
  </div>
  <div class="gt204-grid">
    {card(away_id, away, False)}
    {card(home_id, home, True)}
  </div>
</div>"""


def _render_with_step4_team_evidence_ui(callback, *args, **kwargs):
    with _PRESENTATION_LOCK:
        original = presentation_owner._target_team_evidence_html
        presentation_owner._target_team_evidence_html = _team_evidence_html_v23
        try:
            return callback(*args, **kwargs)
        finally:
            presentation_owner._target_team_evidence_html = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP4_TEAM_EVIDENCE_CSS, unsafe_allow_html=True)
    result = _render_with_step4_team_evidence_ui(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )
    st.markdown(STEP4_TEAM_EVIDENCE_CSS, unsafe_allow_html=True)
    return result


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V23 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_TEAM_EVIDENCE_CSS",
    "STEP4_TEAM_EVIDENCE_UI_MARKER",
    "_render_with_step4_team_evidence_ui",
    "_team_evidence_html_v23",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
