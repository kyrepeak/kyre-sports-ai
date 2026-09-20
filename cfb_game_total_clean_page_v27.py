"""CFB Game Total clean page V27 — visual redesign Step 4 Team Evidence.

Presentation-only successor to V26. V27 replaces only the Team Evidence
presentation hook. Certified data, model math, matchup hero, Game Total
Analysis, provenance, and Steps 1-12 remain delegated and frozen.
"""
from __future__ import annotations

from html import escape
from threading import RLock
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v23 as team_owner
import cfb_game_total_clean_page_v26 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V27 • VISUAL REDESIGN STEP 4 TEAM EVIDENCE"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v26"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • VISUAL REDESIGN STEP 4 TEAM EVIDENCE ACTIVE"
STEP4_TEAM_EVIDENCE_MARKER = "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP4_TEAM_EVIDENCE_ACTIVE"

_PRESENTATION_LOCK = RLock()

STEP4_TEAM_EVIDENCE_CSS = r"""
<style>
.gt227-section{
  margin-top:14px;
  padding:18px;
  border:1px solid rgba(65,160,205,.30);
  border-radius:22px;
  background:
    radial-gradient(circle at 10% 0%,rgba(255,174,64,.08),transparent 30%),
    radial-gradient(circle at 90% 0%,rgba(72,145,255,.09),transparent 30%),
    linear-gradient(145deg,#061823,#071522 58%,#091426);
  box-shadow:0 16px 38px rgba(0,0,0,.18);
  color:#f7fbff;
}
.gt227-head{
  display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px;
}
.gt227-head b{font-size:17px;letter-spacing:.04em;color:#f7fbff}
.gt227-head span{color:#7f99ad;font-size:10px;text-align:right}
.gt227-grid{
  display:grid;grid-template-columns:minmax(0,1fr) 54px minmax(0,1fr);gap:12px;align-items:stretch;
}
.gt227-card{
  position:relative;min-width:0;padding:16px;border:1px solid rgba(91,158,198,.28);
  border-radius:18px;background:linear-gradient(150deg,#091b28,#091a27 64%,#091727);overflow:hidden;
}
.gt227-card.away{
  border-color:rgba(255,182,70,.36);
  box-shadow:inset 3px 0 0 rgba(255,174,64,.78),0 0 24px rgba(255,174,64,.035);
}
.gt227-card.home{
  border-color:rgba(77,151,255,.40);
  box-shadow:inset -3px 0 0 rgba(77,151,255,.82),0 0 24px rgba(77,151,255,.04);
}
.gt227-card:after{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(circle at 88% 0%,rgba(86,183,255,.07),transparent 38%);
}
.gt227-top{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px}
.gt227-id{display:flex;align-items:center;gap:12px;min-width:0}
.gt227-logo{width:58px;height:58px;flex:0 0 58px;display:grid;place-items:center}
.gt227-logo img,.gt227-logo .gt160-evidence-logo{width:54px;height:54px;object-fit:contain;filter:drop-shadow(0 8px 14px rgba(0,0,0,.30))}
.gt227-logo .gt160-evidence-logo-fallback{
  width:52px;height:52px;display:grid;place-items:center;border-radius:14px;background:#10293b;color:#8fcfff;font-weight:950;
}
.gt227-copy{min-width:0}
.gt227-name{font-size:18px;font-weight:1000;color:#f7fbff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt227-meta{margin-top:4px;color:#8ca3b8;font-size:9px;font-weight:800}
.gt227-record{
  flex:0 0 auto;padding:5px 9px;border-radius:999px;border:1px solid rgba(169,104,255,.30);
  background:rgba(91,57,150,.14);color:#d7c4ff;font-size:9px;font-weight:950;
}
.gt227-stats{position:relative;z-index:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:14px}
.gt227-stat{
  min-width:0;padding:11px;border:1px solid rgba(86,160,202,.16);border-radius:13px;background:#0a2230;
}
.gt227-stathead{display:flex;align-items:flex-end;justify-content:space-between;gap:7px}
.gt227-stat b{font-size:19px;line-height:1;color:#f7fbff;font-weight:1000}
.gt227-stat label{color:#8aa0b4;font-size:8px;font-weight:900;text-transform:uppercase;letter-spacing:.05em}
.gt227-state{font-size:7px;color:#45f0ad;font-weight:950}
.gt227-state.pending{color:#ffd24d}
.gt227-track{height:5px;margin-top:9px;border-radius:999px;background:rgba(78,112,137,.18);overflow:hidden}
.gt227-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#27d8d0,#45f0ad)}
.gt227-card.away .gt227-fill{background:linear-gradient(90deg,#ff9c3a,#ffd06d)}
.gt227-card.home .gt227-fill{background:linear-gradient(90deg,#4d8fff,#69c8ff)}
.gt227-form{display:flex;gap:4px;flex-wrap:wrap;margin-top:9px}
.gt227-formchip{
  min-width:20px;height:20px;padding:0 5px;display:grid;place-items:center;border-radius:6px;
  border:1px solid rgba(111,163,194,.20);background:#0a1c29;color:#b7c9d7;font-size:8px;font-weight:1000;
}
.gt227-formchip.w{border-color:rgba(69,240,173,.30);background:rgba(24,111,76,.15);color:#45f0ad}
.gt227-formchip.l{border-color:rgba(255,112,91,.30);background:rgba(122,44,37,.14);color:#ff8c79}
.gt227-foot{
  position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:8px;
  margin-top:12px;padding-top:10px;border-top:1px solid rgba(86,160,202,.13);color:#71899c;font-size:8px;
}
.gt227-source{color:#95aec1;text-align:right}
.gt227-vs{
  align-self:center;width:44px;height:44px;display:grid;place-items:center;border-radius:50%;
  border:1px solid rgba(77,164,205,.30);background:#092231;color:#b7cbd8;font-size:9px;font-weight:1000;
  box-shadow:0 0 0 5px rgba(5,18,28,.30),0 0 20px rgba(39,216,208,.06);
}
@media(max-width:760px){
  .gt227-section{padding:13px;border-radius:18px}
  .gt227-grid{grid-template-columns:minmax(0,1fr) 42px minmax(0,1fr);gap:8px}
  .gt227-card{padding:12px}.gt227-id{gap:8px}.gt227-logo{width:44px;height:44px;flex-basis:44px}
  .gt227-logo img,.gt227-logo .gt160-evidence-logo{width:41px;height:41px}
  .gt227-name{font-size:14px}.gt227-meta,.gt227-record{font-size:7px}.gt227-stat b{font-size:15px}
  .gt227-stat label{font-size:7px}.gt227-vs{width:34px;height:34px;font-size:7px}
}
@media(max-width:560px){
  .gt227-head{align-items:flex-start}.gt227-head b{font-size:14px}.gt227-head span{font-size:8px}
  .gt227-grid{grid-template-columns:1fr}.gt227-vs{justify-self:center;margin:-2px 0}
  .gt227-card.away,.gt227-card.home{box-shadow:inset 3px 0 0 rgba(39,216,208,.65)}
}
</style>
"""


def _clean(value: Any) -> str:
    return team_owner._clean(value)


def _number(value: Any) -> tuple[str, float | None]:
    try:
        numeric = float(value)
        return f"{numeric:.1f}", numeric
    except (TypeError, ValueError):
        return "Pending", None


def _bar_width(value: float | None, scale: float) -> float:
    if value is None:
        return 0.0
    return max(4.0, min(100.0, abs(value) / scale * 100.0))


def _form_html(value: Any) -> tuple[str, bool]:
    text = _clean(value)
    if not text or text == "—":
        return '<span class="gt227-formchip">Pending</span>', False
    outcomes = [char for char in text.upper() if char in {"W", "L", "T"}]
    if not outcomes:
        return f'<span class="gt227-formchip">{escape(text)}</span>', True
    chips = "".join(
        f'<span class="gt227-formchip {outcome.lower()}">{outcome}</span>'
        for outcome in outcomes
    )
    return chips, True


def _team_evidence_html_v27(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    def metric(label: str, value: Any, scale: float) -> str:
        display, numeric = _number(value)
        ready = numeric is not None
        state = "READY" if ready else "PENDING"
        return f"""
<div class="gt227-stat" data-state="{state}">
  <div class="gt227-stathead">
    <div><b>{escape(display)}</b><br><label>{escape(label)}</label></div>
    <span class="gt227-state{' pending' if not ready else ''}">{state}</span>
  </div>
  <div class="gt227-track"><div class="gt227-fill" style="width:{_bar_width(numeric, scale):.1f}%"></div></div>
</div>"""

    def form_metric(value: Any) -> str:
        chips, ready = _form_html(value)
        state = "READY" if ready else "PENDING"
        return f"""
<div class="gt227-stat" data-state="{state}">
  <div class="gt227-stathead">
    <div><b>{escape(_clean(value) or "Pending")}</b><br><label>Recent Form</label></div>
    <span class="gt227-state{' pending' if not ready else ''}">{state}</span>
  </div>
  <div class="gt227-form">{chips}</div>
</div>"""

    def card(team_id: Mapping[str, Any], stats: Mapping[str, Any], side: str) -> str:
        name = _clean(team_id.get("team")) or _clean(stats.get("team")) or "Team"
        conference = _clean(team_id.get("conference")) or "NCAAF"
        record = team_owner._record(stats)
        quality = _clean(stats.get("quality")) or "CHECK"
        try:
            sample = int(stats.get("sample_games") or 0)
        except (TypeError, ValueError):
            sample = 0
        sample_text = f"{sample} completed game{'s' if sample != 1 else ''}" if sample else "Sample pending"
        card_state = "READY" if (
            stats.get("ppg") is not None
            and stats.get("allowed_pg") is not None
            and stats.get("point_diff_pg") is not None
            and _clean(stats.get("recent_form")) not in {"", "—"}
        ) else "PENDING"
        return f"""
<div class="gt227-card {side}" data-team="{escape(name)}" data-state="{card_state}">
  <div class="gt227-top">
    <div class="gt227-id">
      <div class="gt227-logo">{team_owner.presentation_owner._team_logo(team_id)}</div>
      <div class="gt227-copy">
        <div class="gt227-name">{escape(name)}</div>
        <div class="gt227-meta">{escape(conference)} • {escape(quality)} • {escape(card_state)}</div>
      </div>
    </div>
    <span class="gt227-record">{escape(record)}</span>
  </div>
  <div class="gt227-stats">
    {metric("PPG", stats.get("ppg"), 60.0)}
    {metric("Allowed PPG", stats.get("allowed_pg"), 60.0)}
    {metric("Point Diff", stats.get("point_diff_pg"), 30.0)}
    {form_metric(stats.get("recent_form"))}
  </div>
  <div class="gt227-foot">
    <span>{escape(sample_text)}</span>
    <span class="gt227-source">{escape(team_owner._source(stats))}</span>
  </div>
</div>"""

    away_id = identity.get("away") or {}
    home_id = identity.get("home") or {}
    return f"""
<div class="gt227-section" data-testid="gt227-team-evidence"
     data-step4-presentation="{STEP4_TEAM_EVIDENCE_MARKER}">
  <div class="gt227-head">
    <b>🏈 TEAM EVIDENCE</b>
    <span>Scoring • prevention • point differential • current form</span>
  </div>
  <div class="gt227-grid">
    {card(away_id, away, "away")}
    <div class="gt227-vs">VS</div>
    {card(home_id, home, "home")}
  </div>
</div>"""


def _render_with_step4_team_evidence(callback, *args, **kwargs):
    with _PRESENTATION_LOCK:
        original = team_owner._team_evidence_html_v23
        team_owner._team_evidence_html_v23 = _team_evidence_html_v27
        try:
            return callback(*args, **kwargs)
        finally:
            team_owner._team_evidence_html_v23 = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(STEP4_TEAM_EVIDENCE_CSS, unsafe_allow_html=True)
    result = _render_with_step4_team_evidence(
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
        raise ValueError(f"Page V27 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_TEAM_EVIDENCE_CSS",
    "STEP4_TEAM_EVIDENCE_MARKER",
    "_bar_width",
    "_form_html",
    "_render_with_step4_team_evidence",
    "_team_evidence_html_v27",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
