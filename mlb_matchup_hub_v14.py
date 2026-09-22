"""MLB Matchup Explorer V1.4 — player intelligence layer.

Adds a matchup/player context panel on top of V1.3 without changing frozen
production projection engines. Confirmed/projected lineup status, batting slot,
opposing starter, handedness, season/recent form and BvP history are surfaced
for every browsable hitter. Bench players remain browseable but are never given
fabricated lineup slots or PA assumptions.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v13 as base

VERSION = "MLB Matchup Hub V1.4"

_ORIG_ALL_HITTERS = base._all_hitters_for_game


def _safe_int(v):
    try: return int(v)
    except Exception: return None


def _safe_float(v, default=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception: return default


def _all_hitters_v14(row):
    players = _ORIG_ALL_HITTERS(row)
    for p in players:
        p["game_pk"] = _safe_int(row.get("game_pk"))
        p["game_date"] = ui._date_str(row)
        p["opponent"] = row.get("home_team") if p.get("side") == "away" else row.get("away_team")
        p["opponent_pitcher"] = row.get("home_pitcher") if p.get("side") == "away" else row.get("away_pitcher")
        p["opponent_pitcher_id"] = _safe_int(row.get("home_pitcher_id")) if p.get("side") == "away" else _safe_int(row.get("away_pitcher_id"))
    return players


@st.cache_data(ttl=300, show_spinner=False)
def _pitcher_hand(player_id):
    if not player_id: return "—"
    person = ui._person(int(player_id))
    return str((person.get("pitchHand") or {}).get("code") or (person.get("pitchHand") or {}).get("description") or "—")


@st.cache_data(ttl=300, show_spinner=False)
def _batter_hand(player_id):
    person = ui._person(int(player_id))
    return str((person.get("batSide") or {}).get("code") or (person.get("batSide") or {}).get("description") or "—")


@st.cache_data(ttl=300, show_spinner=False)
def _bvp(player_id, pitcher_id, season):
    if not player_id or not pitcher_id: return {}
    try:
        d = ui._json(f"{ui.MLB_API}/people/{int(player_id)}/stats", {
            "stats":"vsPlayer", "group":"hitting", "season":int(season),
            "opposingPlayerId":int(pitcher_id)
        })
        blocks=d.get("stats") or []
        splits=(blocks[0].get("splits") or []) if blocks else []
        if not splits: return {}
        return splits[0].get("stat") or {}
    except Exception:
        return {}


def _context_panel(player, season):
    pid=_safe_int(player.get("id")); starter_id=_safe_int(player.get("opponent_pitcher_id"))
    stat=ui._season_hitting(pid, season) if pid else {}
    logs=ui._game_logs(pid, season) if pid else []
    recent=logs[:10]
    hits=sum(_safe_int(x.get("H")) or 0 for x in recent)
    hrs=sum(_safe_int(x.get("HR")) or 0 for x in recent)
    runs=sum(_safe_int(x.get("R")) or 0 for x in recent)
    rbis=sum(_safe_int(x.get("RBI")) or 0 for x in recent)
    abs_=sum(_safe_int(x.get("AB")) or 0 for x in recent)
    recent_avg=(hits/abs_) if abs_ else 0.0
    bvp=_bvp(pid, starter_id, season)
    bvp_ab=_safe_int(bvp.get("atBats")) or 0; bvp_h=_safe_int(bvp.get("hits")) or 0
    bvp_avg=(bvp_h/bvp_ab) if bvp_ab else None
    slot=_safe_int(player.get("slot")); lineup=bool(player.get("lineup_role")) and slot is not None and slot < 99
    role=(f"#{slot} batting order" if lineup else "Bench / active roster")
    opp_pitcher=str(player.get("opponent_pitcher") or "TBD")
    bat_hand=_batter_hand(pid) if pid else "—"; pitch_hand=_pitcher_hand(starter_id)
    ops=str(stat.get("ops") or "—")
    st.markdown(f'''<div class="mx-proj"><div class="mx-top"><div class="mx-engine">🧠 PLAYER MATCHUP INTELLIGENCE • V1.4</div><div class="mx-badge">{ui._esc(player.get('source'))}</div></div><div class="mx-grid"><div class="mx-cell"><span>Role</span><b>{ui._esc(role)}</b></div><div class="mx-cell"><span>Opposing starter</span><b>{ui._esc(opp_pitcher)} ({ui._esc(pitch_hand)})</b></div><div class="mx-cell"><span>Batter hand</span><b>{ui._esc(bat_hand)}</b></div><div class="mx-cell"><span>Season OPS</span><b>{ui._esc(ops)}</b></div><div class="mx-cell"><span>Last 10 AVG</span><b>{recent_avg:.3f}</b></div><div class="mx-cell"><span>Last 10 H / HR</span><b>{hits} / {hrs}</b></div><div class="mx-cell"><span>Last 10 R / RBI</span><b>{runs} / {rbis}</b></div><div class="mx-cell"><span>BvP</span><b>{('—' if bvp_avg is None else f'{bvp_h}/{bvp_ab} • {bvp_avg:.3f}')}</b></div></div></div>''', unsafe_allow_html=True)
    if not lineup:
        st.info("🪑 Active-roster player: research data is available, but deep pregame projections remain gated until the player enters a confirmed/projected batting order.")
    elif bvp_ab and bvp_ab < 10:
        st.caption(f"BvP sample is only {bvp_ab} AB — context only, not a primary projection driver.")


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    old=base._all_hitters_for_game
    base._all_hitters_for_game=_all_hitters_v14
    try:
        # V1.3 remains the production renderer/calibration layer.
        base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
        # Context for the currently selected player is rendered as a compact follow-up panel.
        if games_df is not None and not games_df.empty:
            try:
                gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
                players=_all_hitters_v14(row)
                pi=int(st.session_state.get("mh12_player",0))
                if players:
                    p=players[max(0,min(pi,len(players)-1))]
                    season=int(ui._date_str(row)[:4])
                    st.markdown("### 🔎 Player Intelligence")
                    _context_panel(p,season)
            except Exception as exc:
                st.caption(f"Player intelligence context unavailable: {type(exc).__name__}")
        st.caption(f"{VERSION} • confirmed/projected lineup intelligence • opponent starter + handedness • recent form • BvP context • V1.3 calibration preserved")
    finally:
        base._all_hitters_for_game=old
