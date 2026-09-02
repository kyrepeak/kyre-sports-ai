"""MLB Matchup Explorer V5.3 — cleanup Step 9 player spotlight.

Presentation-only wrapper over the certified Cleanup Step 7 surface and Matchup
Intelligence V2. Rebuilds the selected-player hero into a compact, mobile-first
spotlight card with clear prediction tiles and season-stat cards. All projection,
probability, calibration, ranking and Moneyline math remains delegated to the
existing frozen/current modules.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v45 as step4
import mlb_matchup_hub_v46 as step5
import mlb_matchup_hub_v47 as step6
import mlb_matchup_hub_v48 as step7
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.3 • Cleanup Step 9"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP4_PRESENTATION = "mlb_matchup_hub_v45"
FROZEN_STEP5_PRESENTATION = "mlb_matchup_hub_v46"
FROZEN_STEP6_PRESENTATION = "mlb_matchup_hub_v47"
FROZEN_STEP7_PRESENTATION = "mlb_matchup_hub_v48"

_STEP9_CSS = r"""
<style>
.mx49-section{margin:10px 0 6px;display:flex;align-items:center;gap:7px;color:#82a7c8;font-size:.62rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase}
.mx49-section .mx49-star{font-size:.9rem;color:#5da8ff}
.mx49-card{position:relative;overflow:hidden;border:1px solid #2a5074;background:radial-gradient(circle at 85% 0%,rgba(39,101,174,.18),transparent 34%),linear-gradient(145deg,#0d1b2b 0%,#08111d 72%);border-radius:22px;padding:16px;margin:0 0 13px;box-shadow:0 16px 38px rgba(0,0,0,.22)}
.mx49-card:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(120deg,rgba(73,145,224,.06),transparent 45%)}
.mx49-top{position:relative;display:grid;grid-template-columns:116px 1fr;gap:15px;align-items:center}
.mx49-photo-shell{width:116px;height:116px;border-radius:50%;padding:4px;background:linear-gradient(145deg,#4b9cff,#163f72);box-shadow:0 0 0 5px rgba(51,128,214,.10),0 10px 22px rgba(0,0,0,.22)}
.mx49-photo-inner{width:100%;height:100%;border-radius:50%;overflow:hidden;background:#132131;display:flex;align-items:center;justify-content:center}
.mx49-photo{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.mx49-name{font-size:1.55rem;line-height:1.03;font-weight:950;color:#f7fbff;letter-spacing:-.03em;margin-bottom:5px}
.mx49-team{font-size:.72rem;color:#a8bdd0;font-weight:800;margin-bottom:8px}
.mx49-badges{display:flex;gap:6px;flex-wrap:wrap}
.mx49-badge{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:4px 8px;font-size:.53rem;font-weight:900;border:1px solid #36536e;background:#101d2b;color:#bad0e2}
.mx49-badge.confirmed{border-color:#2f6d4a;background:#0d2417;color:#8fe3ad}
.mx49-badge.projected{border-color:#6a5a2c;background:#251f0d;color:#f0d77d}
.mx49-badge.bench{border-color:#555c6b;background:#171b22;color:#bcc5d0}
.mx49-matchup{position:relative;display:flex;align-items:center;gap:9px;margin-top:13px;padding:10px 11px;border:1px solid #263f58;border-radius:14px;background:rgba(5,15,25,.56)}
.mx49-vs{display:inline-flex;align-items:center;justify-content:center;min-width:30px;height:30px;border-radius:50%;border:1px solid #3a5873;color:#82a4c2;font-size:.52rem;font-weight:950}
.mx49-match-main{font-size:.69rem;color:#d9e7f2;line-height:1.35}.mx49-match-main strong{color:#fff;font-weight:900}
.mx49-match-sub{font-size:.55rem;color:#7794ad;margin-top:1px}
.mx49-model{margin-left:auto;white-space:nowrap;border-radius:999px;padding:4px 7px;font-size:.48rem;font-weight:900;letter-spacing:.04em;border:1px solid #31506a;color:#86a8c4;background:#0b1722}
.mx49-model.ready{border-color:#2f6d4a;color:#8fe3ad;background:#0b1d14}
.mx49-primary{position:relative;display:grid;grid-template-columns:1.35fr 1fr 1fr;gap:8px;margin-top:11px}
.mx49-tile{min-width:0;border:1px solid #2a455d;border-radius:16px;padding:11px 10px;background:#0a1520}
.mx49-tile .label{display:flex;align-items:center;gap:5px;font-size:.48rem;text-transform:uppercase;letter-spacing:.055em;color:#7895ad;font-weight:900;line-height:1.2}
.mx49-tile .value{font-size:1.16rem;font-weight:950;color:#f5f9fd;letter-spacing:-.025em;margin-top:7px}
.mx49-tile.prob{border-color:#2f744f;background:linear-gradient(145deg,#0b2317,#0a1712)}.mx49-tile.prob .label{color:#7ad89b}.mx49-tile.prob .value{font-size:1.55rem;color:#9af0b8}
.mx49-tile.conf{border-color:#5a467f;background:linear-gradient(145deg,#191328,#0e101b)}.mx49-tile.conf .label{color:#b39ae7}.mx49-tile.conf .value{color:#c1a7ff}
.mx49-tile.exp{border-color:#795023;background:linear-gradient(145deg,#22170d,#13110f)}.mx49-tile.exp .label{color:#e8a458}.mx49-tile.exp .value{color:#ffb25f}
.mx49-season-head{position:relative;margin:12px 1px 6px;font-size:.50rem;text-transform:uppercase;letter-spacing:.08em;color:#718ea8;font-weight:900}
.mx49-season{position:relative;display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.mx49-season-card{border:1px solid #263e55;border-radius:13px;background:#0a141f;padding:8px 5px;text-align:center}
.mx49-season-card span{display:block;font-size:.43rem;text-transform:uppercase;letter-spacing:.06em;color:#7089a0;font-weight:900}
.mx49-season-card b{display:block;margin-top:4px;font-size:.86rem;color:#edf5fb;font-weight:950}

/* Step 9 owns the selected-player summary, so keep legacy/V2 shell captions out of the way. */
.mx45-hero{display:none!important}

@media(max-width:640px){
  .mx49-section{margin:7px 0 5px;font-size:.56rem}
  .mx49-card{padding:12px;border-radius:18px;margin-bottom:10px}
  .mx49-top{grid-template-columns:94px 1fr;gap:11px}.mx49-photo-shell{width:94px;height:94px;padding:3px}
  .mx49-name{font-size:1.18rem;margin-bottom:4px}.mx49-team{font-size:.61rem;margin-bottom:6px}
  .mx49-badge{font-size:.47rem;padding:3px 6px}.mx49-matchup{gap:7px;margin-top:10px;padding:8px 9px;border-radius:12px}
  .mx49-vs{min-width:26px;height:26px}.mx49-match-main{font-size:.59rem}.mx49-match-sub{font-size:.49rem}.mx49-model{font-size:.42rem;padding:3px 5px}
  .mx49-primary{gap:5px;margin-top:8px}.mx49-tile{padding:8px 7px;border-radius:13px}.mx49-tile .label{font-size:.40rem;gap:3px}.mx49-tile .value{font-size:.88rem;margin-top:5px}.mx49-tile.prob .value{font-size:1.12rem}
  .mx49-season-head{margin-top:9px}.mx49-season{gap:4px}.mx49-season-card{padding:6px 3px;border-radius:11px}.mx49-season-card span{font-size:.38rem}.mx49-season-card b{font-size:.72rem}
}
</style>
"""

_ENGINE_CAPTION_PREFIX = "🧠 Matchup Intelligence V2 COMPLETE"


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _number(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _spotlight_html(context: dict[str, Any], final: dict[str, Any] | None = None) -> str:
    row = context["row"]
    player = context["player"]
    player_id = _safe_int(player.get("id"), 0)
    season = step4._season_year(row)
    stat = ui._season_hitting(player_id, season) if player_id else {}

    role_label, _ = step1._role(player)
    role_key = role_label.lower()
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f"#{slot}" if role_label != "Bench" and 1 <= slot <= 9 else "—"
    team = str(player.get("team") or "—")
    position = str(player.get("position") or "—")
    opponent_pitcher = str(player.get("opponent_pitcher") or "TBD")
    pitcher_id = _safe_int(player.get("opponent_pitcher_id"), 0)
    batter_hand = roster._batter_hand(player_id) if player_id else "—"
    pitcher_hand = roster._pitcher_hand(pitcher_id) if pitcher_id else "—"

    avg = stat.get("avg") or ".000"
    ops = stat.get("ops") or ".000"
    hits = _safe_int(stat.get("hits"), 0)
    homers = _safe_int(stat.get("homeRuns"), 0)

    d = final or {}
    probability = _rate(d.get("final_p1_plus")) if final else "…"
    confidence = f"{_safe_int(d.get('final_confidence'), 0)}%" if final else "…"
    expected_hits = _number(d.get("final_expected_hits"), 2) if final else "…"
    final_status = str(d.get("final_status") or "Calculating") if final else "Calculating"
    grade = str(d.get("final_grade") or "") if final else ""
    model_text = f"V2 {final_status}{' • ' + grade if grade else ''}" if final else "V2 calculating…"
    model_class = " ready" if final else ""

    photo = step4._headshot_url(player_id)
    photo_html = (
        f'<img class="mx49-photo" src="{_esc(photo)}" alt="{_esc(player.get("name") or "MLB player")}">'
        if photo
        else '<div style="font-size:2rem">⚾</div>'
    )

    role_icon = "✓" if role_label == "Confirmed" else ("◷" if role_label == "Projected" else "•")
    slot_badge = f'<span class="mx49-badge">Batting slot <strong>{_esc(slot_text)}</strong></span>' if slot_text != "—" else ""

    return f'''<div class="mx49-section"><span class="mx49-star">☆</span> Player Spotlight</div>
    <div class="mx49-card">
      <div class="mx49-top">
        <div class="mx49-photo-shell"><div class="mx49-photo-inner">{photo_html}</div></div>
        <div>
          <div class="mx49-name">{_esc(player.get('name') or 'Player')}</div>
          <div class="mx49-team">⚾ {_esc(team)} • {_esc(position)}</div>
          <div class="mx49-badges">
            <span class="mx49-badge {_esc(role_key)}">{_esc(role_icon)} {_esc(role_label)}</span>
            {slot_badge}
          </div>
        </div>
      </div>
      <div class="mx49-matchup">
        <span class="mx49-vs">VS</span>
        <div>
          <div class="mx49-match-main">vs <strong>{_esc(opponent_pitcher)}</strong> ({_esc(pitcher_hand)})</div>
          <div class="mx49-match-sub">{_esc(batter_hand)} batter vs {_esc(pitcher_hand)} pitcher</div>
        </div>
        <span class="mx49-model{model_class}">{_esc(model_text)}</span>
      </div>
      <div class="mx49-primary">
        <div class="mx49-tile prob"><div class="label">🎯 1+ Hit</div><div class="value">{_esc(probability)}</div></div>
        <div class="mx49-tile conf"><div class="label">🛡 Confidence</div><div class="value">{_esc(confidence)}</div></div>
        <div class="mx49-tile exp"><div class="label">📈 Exp. Hits</div><div class="value">{_esc(expected_hits)}</div></div>
      </div>
      <div class="mx49-season-head">{season} Season</div>
      <div class="mx49-season">
        <div class="mx49-season-card"><span>AVG</span><b>{_esc(avg)}</b></div>
        <div class="mx49-season-card"><span>OPS</span><b>{_esc(ops)}</b></div>
        <div class="mx49-season-card"><span>Hits</span><b>{hits}</b></div>
        <div class="mx49-season-card"><span>HR</span><b>{homers}</b></div>
      </div>
    </div>'''


def _render_spotlight(slot, context: dict[str, Any] | None, final: dict[str, Any] | None = None) -> None:
    if not context:
        slot.info("Player spotlight is waiting for a verified selection.")
        return
    slot.markdown(_spotlight_html(context, final), unsafe_allow_html=True)


def _step12_profile_with_spotlight(original, slot, context):
    def wrapped(profile: dict[str, Any] | None) -> None:
        _render_spotlight(slot, context, profile)
        return original(profile)
    return wrapped


def _clean_engine_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        if str(body or "").startswith(_ENGINE_CAPTION_PREFIX):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(step7._STEP7_CSS + step7._TITLE_HTML + _STEP9_CSS, unsafe_allow_html=True)
    step6._render_compact_controls(games_df)

    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    _render_spotlight(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_expander = st.expander
    original_caption = st.caption
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.expander = step5._collapsed_expander(original_expander)
    st.caption = _clean_engine_caption(original_caption)
    final_layer._render_step12_profile = _step12_profile_with_spotlight(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.caption = original_caption
        st.expander = original_expander
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP4_PRESENTATION",
    "FROZEN_STEP5_PRESENTATION",
    "FROZEN_STEP6_PRESENTATION",
    "FROZEN_STEP7_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_spotlight_html",
    "_render_spotlight",
    "render_matchup_hub",
]
