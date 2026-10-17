"""MONSTER CFB Game Total Page 2 — visual cleanup R2.

Presentation-only successor to the frozen Page 2 Complete Repair R1. R2 keeps
R1's exact selected-event, multi-source, model, probability, market, Line Lab,
and Best Bet behavior and replaces only the Stage 6/7 presentation surface.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
import re
from threading import RLock
from typing import Any, Callable

import streamlit as st

import cfb_game_total_clean_page_v23 as team_evidence_ui
import cfb_game_total_page2_complete_repair_r1 as prior
import cfb_game_total_page2_stage6_tough_favorable_v1 as stage6

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 VISUAL CLEANUP R2"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R2_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R2_FROZEN"
R1_PARENT = "cfb_game_total_page2_complete_repair_r1"
MARKET = prior.MARKET
SELECTED_GAME_ONLY = True
MULTI_SOURCE_REQUIRED = True
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

_PRESENTATION_LOCK = RLock()

CLEANUP_CSS = r"""
<style>
.gtp2r2-stage6,.gtp2r2-team-wrap{max-width:1180px;margin:0 auto 18px;color:#f7fbff}
.gtp2r2-stage6{overflow:hidden;border:1px solid rgba(91,192,255,.28);border-radius:18px;background:linear-gradient(180deg,rgba(7,28,43,.98),rgba(4,15,24,.99));box-shadow:0 14px 34px rgba(0,0,0,.22)}
.gtp2r2-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;padding:15px 17px 12px;border-bottom:1px solid rgba(82,174,211,.16)}
.gtp2r2-kicker{display:block;margin-bottom:4px;color:#76dfff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}
.gtp2r2-head h3{margin:0;color:#fff;font-size:20px;font-weight:1000}.gtp2r2-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:760;line-height:1.4}
.gtp2r2-pill{flex:0 0 auto;padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;text-transform:uppercase;white-space:nowrap}
.gtp2r2-battles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;padding:14px}
.gtp2r2-battle{min-width:0;padding:14px;border:1px solid rgba(91,170,203,.20);border-radius:14px;background:rgba(7,29,44,.74)}
.gtp2r2-battle span{display:block;color:#7899ac;font-size:8px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.gtp2r2-battle strong{display:block;margin-top:7px;color:#fff;font-size:18px;font-weight:1000}.gtp2r2-battle p{margin:7px 0 0;color:#9db5c3;font-size:9px;font-weight:760;line-height:1.5}
.gtp2r2-battle.tough{border-color:rgba(255,105,120,.32);background:rgba(89,29,39,.22)}.gtp2r2-battle.tough strong{color:#ff8995}.gtp2r2-battle.fav{border-color:rgba(72,224,177,.36);background:rgba(9,75,61,.25)}.gtp2r2-battle.fav strong{color:#7aefbf}
.gtp2r2-limited{grid-column:1/-1;padding:10px 12px;border-radius:11px;background:rgba(82,94,106,.13);color:#9fb1bc;font-size:9px;font-weight:800}
.gtp2r2-team-wrap{overflow:hidden;border:1px solid rgba(91,192,255,.28);border-radius:18px;background:linear-gradient(180deg,rgba(7,28,43,.98),rgba(4,15,24,.99));box-shadow:0 14px 34px rgba(0,0,0,.22)}
.gtp2r2-team-title{padding:15px 17px 12px;border-bottom:1px solid rgba(82,174,211,.16)}.gtp2r2-team-title span{display:block;color:#76dfff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}.gtp2r2-team-title h3{margin:5px 0 0;color:#fff;font-size:20px;font-weight:1000}.gtp2r2-team-title p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:760}
.gtp2r2-team-wrap .gt204-sectionhead{display:none!important}
.gtp2r2-team-wrap .gt204-section{margin:0!important;padding:14px!important;border:0!important;border-radius:0!important;background:transparent!important}
.gtp2r2-team-wrap .gt204-grid{gap:10px!important}.gtp2r2-team-wrap .gt204-card{padding:12px!important;border-radius:13px!important}
.gtp2r2-team-wrap .gt204-logo img,.gtp2r2-team-wrap .gt204-logo .gt160-evidence-logo{width:46px!important;height:46px!important;max-width:46px!important;max-height:46px!important;object-fit:contain!important}
.gtp2r2-team-wrap .gt204-logo .gt160-evidence-logo-fallback{width:46px!important;height:46px!important;max-width:46px!important;max-height:46px!important}
.gtp2r2-team-wrap .gt204-name{font-size:16px!important;line-height:1.15!important}.gtp2r2-team-wrap .gt204-meta,.gtp2r2-team-wrap .gt204-record{font-size:10px!important}.gtp2r2-team-wrap .gt204-value{font-size:15px!important}.gtp2r2-team-wrap .gt204-label{font-size:8px!important}.gtp2r2-team-wrap .gt204-state{font-size:7px!important}.gtp2r2-team-wrap .gt204-foot span{font-size:9px!important;line-height:1.35!important}.gtp2r2-team-wrap .gt204-foot .source{max-width:66%;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
@media(max-width:760px){.gtp2r2-battles{grid-template-columns:1fr}.gtp2r2-limited{grid-column:auto}.gtp2r2-head{align-items:flex-start;flex-direction:column}.gtp2r2-team-wrap .gt204-grid{grid-template-columns:1fr!important}.gtp2r2-team-wrap .gt204-stats{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
@media(max-width:480px){.gtp2r2-stage6,.gtp2r2-team-wrap{border-radius:15px}.gtp2r2-battles,.gtp2r2-team-wrap .gt204-section{padding:10px!important}.gtp2r2-team-wrap .gt204-foot{align-items:flex-start!important;flex-direction:column!important}.gtp2r2-team-wrap .gt204-foot .source{max-width:100%;text-align:left!important}}
</style>
"""


def _visible_text(value: Any, fallback: str = "—") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"<[^>]*>", "", text).strip()
    return escape(text) if text else fallback


def build_stage6_clean_html(matchup: Mapping[str, Any] | None) -> str:
    """Render the already-verified Stage 6 contract without legacy HTML fragments."""
    row = stage6.build_tough_favorable_contract(matchup)
    limited = ""
    if not row.get("ready"):
        limited = '<div class="gtp2r2-limited">Verified matchup evidence is limited; no side is invented.</div>'
    return f"""
<section class="gtp2r2-stage6" data-testid="gtp2r2-stage6" data-value-ownership="verified-matchup-read">
  <header class="gtp2r2-head">
    <div><span class="gtp2r2-kicker">Stage 6 • Matchup Read</span><h3>Tough Matchup + Favorable Team</h3><p>Verified offense-vs-defense reads summarized without changing the model.</p></div>
    <span class="gtp2r2-pill">Display only • fail soft</span>
  </header>
  <div class="gtp2r2-battles">
    <article class="gtp2r2-battle tough"><span>Tough Matchup</span><strong>{_visible_text(row.get('tough_team'))}</strong><p>{_visible_text(row.get('tough_read'), 'No verified tough matchup')} • {_visible_text(row.get('tough_reason'))}</p></article>
    <article class="gtp2r2-battle fav"><span>Favorable Team</span><strong>{_visible_text(row.get('favorable_team'))}</strong><p>{_visible_text(row.get('favorable_read'), 'No verified favorable matchup')} • {_visible_text(row.get('favorable_reason'))}</p></article>
    {limited}
  </div>
</section>"""


def _team_profile(stats: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(stats) if isinstance(stats, Mapping) else {}
    ppg = row.get("ppg", row.get("points_per_game"))
    allowed = row.get("allowed_pg", row.get("points_allowed_pg", row.get("points_allowed")))
    diff = row.get("point_diff_pg", row.get("point_diff"))
    if diff is None:
        try:
            diff = float(ppg) - float(allowed)
        except (TypeError, ValueError):
            diff = None
    return {
        **row,
        "ppg": ppg,
        "allowed_pg": allowed,
        "point_diff_pg": diff,
        "recent_form": row.get("recent_form", row.get("form")),
    }


def build_stage7_clean_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    cards = team_evidence_ui._team_evidence_html_v23(
        identity,
        _team_profile(away),
        _team_profile(home),
    )
    return f"""
<section class="gtp2r2-team-wrap" data-testid="gtp2r2-team-evidence">
  <header class="gtp2r2-team-title">
    <span>Stage 7 • Team Evidence</span>
    <h3>Team Evidence</h3>
    <p>Scoring profile, prevention, differential, current form, and verified source context.</p>
  </header>
  {cards}
</section>"""


def _render_clean_matchup_and_team_evidence(payload: Mapping[str, Any]) -> None:
    identity, away, home, display_game, _, _, _, _ = prior._profile_values(payload)
    matchup = prior.page2._matchup_contract(identity, away, home, display_game)
    st.markdown(team_evidence_ui.STEP4_TEAM_EVIDENCE_CSS + CLEANUP_CSS, unsafe_allow_html=True)
    st.markdown(build_stage6_clean_html(matchup), unsafe_allow_html=True)
    st.markdown(build_stage7_clean_html(identity, away, home), unsafe_allow_html=True)


def _with_clean_presentation(callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with _PRESENTATION_LOCK:
        original = prior._render_matchup_and_team_evidence
        prior._render_matchup_and_team_evidence = _render_clean_matchup_and_team_evidence
        try:
            return callback(*args, **kwargs)
        finally:
            prior._render_matchup_and_team_evidence = original


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _with_clean_presentation(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page 2 Visual Cleanup R2 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell() -> Any:
    return _with_clean_presentation(prior.render_selected_in_shared_shell)


__all__ = [
    "ACTIVE_MARKER",
    "CLEANUP_CSS",
    "FREEZE_TOKEN",
    "MARKET",
    "MODEL_VERSION",
    "MULTI_SOURCE_REQUIRED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_stage6_clean_html",
    "build_stage7_clean_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
