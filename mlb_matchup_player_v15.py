"""MLB Matchup Explorer player layer V1.5 — Batter vs Pitcher Step 1.

Adds a dedicated BvP + opposing starter profile card to the existing player
intelligence page. Uses MLB Stats API only; no projection math is changed.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v13 as shell
import mlb_matchup_hub_v14 as v14

VERSION = "MLB Player Intelligence V1.5"


def _i(v, default=0):
    try: return int(float(v))
    except Exception: return default


def _f(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _fmt3(v):
    x=_f(v)
    return "—" if x is None else f"{x:.3f}".replace("0.", ".", 1)


def _fmt2(v):
    x=_f(v)
    return "—" if x is None else f"{x:.2f}"


@st.cache_data(ttl=600, show_spinner=False)
def _pitcher_season(player_id, season):
    if not player_id: return {}
    try:
        d=ui._json(f"{ui.MLB_API}/people/{int(player_id)}/stats",{
            "stats":"season","group":"pitching","season":int(season)
        })
        blocks=d.get("stats") or []
        splits=(blocks[0].get("splits") or []) if blocks else []
        return (splits[0].get("stat") or {}) if splits else {}
    except Exception:
        return {}


def _starter_label(player):
    name=str(player.get("opponent_pitcher") or "TBD")
    # Current schedule layer supplies probable starters. Do not invent confirmation.
    return f"{name} • probable starter" if name != "TBD" else "TBD starter"


def _bvp_card(player, season):
    pid=v14._safe_int(player.get("id"))
    spid=v14._safe_int(player.get("opponent_pitcher_id"))
    bvp=v14._bvp(pid,spid,season) if pid and spid else {}
    pst=_pitcher_season(spid,season) if spid else {}

    ab=_i(bvp.get("atBats")); h=_i(bvp.get("hits")); hr=_i(bvp.get("homeRuns"))
    rbi=_i(bvp.get("rbi")); bb=_i(bvp.get("baseOnBalls")); k=_i(bvp.get("strikeOuts"))
    avg=_f(bvp.get("avg")); ops=_f(bvp.get("ops"))
    if avg is None and ab: avg=h/ab

    era=pst.get("era"); whip=pst.get("whip"); ha=_i(pst.get("hits")); hra=_i(pst.get("homeRuns"))
    pk=_i(pst.get("strikeOuts")); pbb=_i(pst.get("baseOnBalls")); baa=pst.get("avg")
    ip=pst.get("inningsPitched"); gs=_i(pst.get("gamesStarted")); hand=v14._pitcher_hand(spid) if spid else "—"

    bvp_status="NO HISTORY" if ab==0 else ("THIN SAMPLE" if ab<10 else "USABLE SAMPLE" if ab<25 else "STRONGER SAMPLE")
    badge="mx-badge"
    st.markdown(f'''<div class="mx-proj">
      <div class="mx-top">
        <div class="mx-engine">⚔️ BATTER VS PITCHER • STEP 1</div>
        <div class="{badge}">{ui._esc(bvp_status)}</div>
      </div>
      <div class="rk-details" style="margin:4px 0 14px 0">{ui._esc(player.get('name') or '')} vs {ui._esc(_starter_label(player))} ({ui._esc(hand)})</div>
      <div class="mx-grid">
        <div class="mx-cell"><span>BvP AB</span><b>{ab}</b></div>
        <div class="mx-cell"><span>BvP Hits</span><b>{h}</b></div>
        <div class="mx-cell"><span>BvP AVG</span><b>{_fmt3(avg)}</b></div>
        <div class="mx-cell"><span>BvP HR</span><b>{hr}</b></div>
        <div class="mx-cell"><span>BvP RBI</span><b>{rbi}</b></div>
        <div class="mx-cell"><span>BvP BB / K</span><b>{bb} / {k}</b></div>
        <div class="mx-cell"><span>BvP OPS</span><b>{_fmt3(ops)}</b></div>
        <div class="mx-cell"><span>Starter ERA</span><b>{_fmt2(era)}</b></div>
        <div class="mx-cell"><span>Starter WHIP</span><b>{_fmt2(whip)}</b></div>
        <div class="mx-cell"><span>Hits allowed</span><b>{ha}</b></div>
        <div class="mx-cell"><span>HR allowed</span><b>{hra}</b></div>
        <div class="mx-cell"><span>Pitcher K / BB</span><b>{pk} / {pbb}</b></div>
        <div class="mx-cell"><span>AVG allowed</span><b>{_fmt3(baa)}</b></div>
        <div class="mx-cell"><span>IP / GS</span><b>{ui._esc(ip or '—')} / {gs}</b></div>
      </div>
    </div>''',unsafe_allow_html=True)

    if ab==0:
        st.caption("No MLB regular-season batter-vs-pitcher plate appearances found for this season. The starter profile is still shown, but no BvP adjustment should be inferred.")
    elif ab<10:
        st.warning(f"⚠️ BvP sample is only {ab} AB — context only. Do not let this tiny head-to-head sample override the larger projection model.")
    else:
        st.caption(f"BvP sample: {ab} AB. Treat head-to-head history as supporting context, not a standalone projection.")


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    old=shell._all_hitters_for_game
    shell._all_hitters_for_game=v14._all_hitters_v14
    try:
        shell.render_matchup_hub(games_df,section_header,status_info,team_logo,h)
        if games_df is not None and not games_df.empty:
            try:
                gi=int(st.session_state.get("mh12_game",0)); row=games_df.iloc[gi]
                players=v14._all_hitters_v14(row)
                pi=int(st.session_state.get("mh12_player",0))
                if players:
                    p=players[max(0,min(pi,len(players)-1))]
                    season=int(ui._date_str(row)[:4])
                    st.markdown("### ⚔️ Batter vs Pitcher")
                    _bvp_card(p,season)
                    st.markdown("### 🔎 Player Intelligence")
                    v14._context_panel(p,season)
            except Exception as exc:
                st.caption(f"Batter-vs-pitcher intelligence unavailable: {type(exc).__name__}")
        st.caption(f"{VERSION} • Step 1 BvP history + opposing starter season profile • thin-sample protection • production projection engines unchanged")
    finally:
        shell._all_hitters_for_game=old
