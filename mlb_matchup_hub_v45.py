"""MLB Matchup Explorer V4.9 — cleanup Step 4 selected-player hero.

Presentation-only wrapper over the certified V2 Step 12 Matchup Explorer.
Builds on Cleanup Step 3 grouped roster access by moving the most important
selected-player context above the deep model blocks, including an MLB player
headshot. Final probability/confidence/expected-hits values are intercepted from
the already-computed certified Step 12 profile so this layer never triggers a
second model run or rewrites model math.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v43 as step2
import mlb_matchup_hub_v44 as step3
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V4.9 • Cleanup Step 4"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP2_PRESENTATION = "mlb_matchup_hub_v43"
FROZEN_STEP3_PRESENTATION = "mlb_matchup_hub_v44"

_HERO_CSS = r"""
<style>
.mx45-hero{border:1px solid #2d4d68;background:linear-gradient(145deg,#0d1b29,#08121d);border-radius:20px;padding:15px 16px;margin:10px 0 16px;box-shadow:0 10px 30px rgba(0,0,0,.16)}
.mx45-main{display:grid;grid-template-columns:118px 1fr;gap:15px;align-items:center}
.mx45-photo-wrap{width:118px;height:118px;border-radius:18px;overflow:hidden;border:1px solid #355976;background:#101c28;display:flex;align-items:center;justify-content:center}
.mx45-photo{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.mx45-kicker{font-size:.56rem;font-weight:900;letter-spacing:.10em;text-transform:uppercase;color:#65dcff;margin-bottom:3px}
.mx45-name{font-size:1.48rem;line-height:1.05;font-weight:950;color:#f8fbff;margin-bottom:5px}
.mx45-line{font-size:.72rem;color:#9db1c5;line-height:1.5}
.mx45-line strong{color:#e8f2fb;font-weight:850}
.mx45-status{display:inline-block;border:1px solid #335675;border-radius:999px;padding:3px 7px;font-size:.55rem;font-weight:850;color:#a9c6dc;margin-top:6px}
.mx45-final{display:grid;grid-template-columns:1.35fr 1fr 1fr;gap:8px;margin-top:13px}
.mx45-final-cell{border:1px solid #27465f;background:#0a1621;border-radius:14px;padding:10px 11px}
.mx45-final-cell span{display:block;font-size:.50rem;text-transform:uppercase;letter-spacing:.07em;color:#7893aa;margin-bottom:3px}
.mx45-final-cell b{font-size:1.08rem;color:#f4f9fd}
.mx45-final-cell.mx45-prob{border-color:#39705b;background:#0b1d16}.mx45-final-cell.mx45-prob b{font-size:1.32rem;color:#effff5}
.mx45-season{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}
.mx45-season-cell{border:1px solid #233d54;background:#0a141f;border-radius:12px;padding:8px;text-align:center}
.mx45-season-cell span{display:block;font-size:.48rem;color:#718aa1;text-transform:uppercase;letter-spacing:.06em}.mx45-season-cell b{font-size:.88rem;color:#edf4fa}
.mx45-note{font-size:.55rem;color:#708aa1;margin-top:8px;line-height:1.35}
@media(max-width:640px){.mx45-hero{padding:12px;border-radius:17px}.mx45-main{grid-template-columns:92px 1fr;gap:11px}.mx45-photo-wrap{width:92px;height:92px;border-radius:15px}.mx45-name{font-size:1.18rem}.mx45-line{font-size:.64rem}.mx45-final{grid-template-columns:1fr 1fr 1fr;gap:6px}.mx45-final-cell{padding:8px}.mx45-final-cell b{font-size:.90rem}.mx45-final-cell.mx45-prob b{font-size:1.06rem}.mx45-season-cell b{font-size:.78rem}}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _fmt_num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _headshot_url(player_id: int | None) -> str:
    if not player_id:
        return ""
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        "w_240,d_people:generic:headshot:silo:current.png,q_auto:best,f_auto/"
        f"v1/people/{int(player_id)}/headshot/67/current"
    )


def _selected_context(games_df) -> dict[str, Any] | None:
    if games_df is None or games_df.empty:
        return None
    game_index = _safe_int(st.session_state.get("mh12_game", 0), 0)
    game_index = max(0, min(game_index, len(games_df) - 1))
    row = games_df.iloc[game_index]
    players = roster._all_hitters_v14(row)
    if not players:
        return None
    player_index = _safe_int(st.session_state.get("mh12_player", 0), 0)
    player_index = max(0, min(player_index, len(players) - 1))
    player = players[player_index]
    return {
        "row": row,
        "players": players,
        "player": player,
        "game_index": game_index,
        "player_index": player_index,
    }


def _season_year(row: Any) -> int:
    try:
        return int(str(row.get("game_date") or "")[:4])
    except Exception:
        return 2026


def _hero_html(context: dict[str, Any], final: dict[str, Any] | None = None) -> str:
    row = context["row"]
    player = context["player"]
    player_id = _safe_int(player.get("id"), 0)
    season = _season_year(row)
    stat = ui._season_hitting(player_id, season) if player_id else {}

    role_label, _ = step1._role(player)
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f"#{slot}" if role_label != "Bench" and 1 <= slot <= 9 else "—"
    team = str(player.get("team") or "—")
    position = str(player.get("position") or "—")
    opponent_pitcher = str(player.get("opponent_pitcher") or "TBD")
    pitcher_id = _safe_int(player.get("opponent_pitcher_id"), 0)
    batter_hand = roster._batter_hand(player_id) if player_id else "—"
    pitcher_hand = roster._pitcher_hand(pitcher_id) if pitcher_id else "—"
    matchup = f"{batter_hand} batter vs {pitcher_hand} pitcher"

    avg = stat.get("avg") or ".000"
    ops = stat.get("ops") or ".000"
    hits = _safe_int(stat.get("hits"), 0)
    homers = _safe_int(stat.get("homeRuns"), 0)

    d = final or {}
    final_status = str(d.get("final_status") or "WAITING")
    probability = _fmt_rate(d.get("final_p1_plus")) if final else "…"
    confidence = f"{_safe_int(d.get('final_confidence'), 0)}/100" if final else "…"
    expected_hits = _fmt_num(d.get("final_expected_hits"), 2) if final else "…"
    grade = str(d.get("final_grade") or "") if final else ""
    status_text = f"{final_status}{' • ' + grade if grade else ''}"

    photo = _headshot_url(player_id)
    photo_html = (
        f'<img class="mx45-photo" src="{_esc(photo)}" alt="{_esc(player.get("name") or "MLB player")}">'
        if photo
        else '<div style="font-size:2.2rem">⚾</div>'
    )

    return f'''<div class="mx45-hero">
      <div class="mx45-main">
        <div class="mx45-photo-wrap">{photo_html}</div>
        <div>
          <div class="mx45-kicker">Selected player • matchup summary</div>
          <div class="mx45-name">{_esc(player.get('name') or 'Player')}</div>
          <div class="mx45-line"><strong>{_esc(team)}</strong> • {_esc(position)} • {_esc(role_label)} • batting slot {_esc(slot_text)}</div>
          <div class="mx45-line">vs <strong>{_esc(opponent_pitcher)}</strong> ({_esc(pitcher_hand)}) • {_esc(matchup)}</div>
          <div class="mx45-status">Final V2: {_esc(status_text)}</div>
        </div>
      </div>
      <div class="mx45-final">
        <div class="mx45-final-cell mx45-prob"><span>Final 1+ hit probability</span><b>{_esc(probability)}</b></div>
        <div class="mx45-final-cell"><span>Confidence</span><b>{_esc(confidence)}</b></div>
        <div class="mx45-final-cell"><span>Expected hits</span><b>{_esc(expected_hits)}</b></div>
      </div>
      <div class="mx45-season">
        <div class="mx45-season-cell"><span>Season AVG</span><b>{_esc(avg)}</b></div>
        <div class="mx45-season-cell"><span>Season OPS</span><b>{_esc(ops)}</b></div>
        <div class="mx45-season-cell"><span>Season hits</span><b>{hits}</b></div>
        <div class="mx45-season-cell"><span>Season HR</span><b>{homers}</b></div>
      </div>
      <div class="mx45-note">The three Final V2 values above are copied from the certified Step 12 result already computed below; this hero card does not run or alter the model.</div>
    </div>'''


def _render_hero(slot, context: dict[str, Any] | None, final: dict[str, Any] | None = None) -> None:
    if not context:
        slot.info("Player summary is waiting for a verified player selection.")
        return
    slot.markdown(_HERO_CSS + _hero_html(context, final), unsafe_allow_html=True)


def _step12_profile_with_hero(original, slot, context):
    def wrapped(profile: dict[str, Any] | None) -> None:
        _render_hero(slot, context, profile)
        return original(profile)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    game_index = step2._render_game_cards(games_df)
    step3._render_roster_groups(games_df, game_index)

    context = _selected_context(games_df)
    hero_slot = st.empty()
    _render_hero(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_step12_profile = final_layer._render_step12_profile
    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    final_layer._render_step12_profile = _step12_profile_with_hero(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP2_PRESENTATION",
    "FROZEN_STEP3_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_headshot_url",
    "_hero_html",
    "_selected_context",
    "render_matchup_hub",
]
