# WNBA Live Games V4 — Step 4 historical second-half / Q3 / Q4 profiles.
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_hub_v3 as v3
import wnba_live_hub_v2 as v2
import wnba_live_hub_v1 as v1
import wnba_live_second_half_v1 as hist

MODEL_VERSION = "WNBA LIVE GAMES V4 • STEP 4 SECOND-HALF HISTORY"
ET = ZoneInfo("America/New_York")


def _num(value, digits=1, suffix=""):
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return "—"


def _signed(value, digits=1):
    try:
        return f"{float(value):+.{digits}f}"
    except Exception:
        return "—"


def _pct(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "—"


def _team_card(name: str, role: str, p: dict) -> str:
    rel = str(p.get("reliability") or "THIN")
    cls = "good" if rel == "HIGH" else ("warn" if rel == "MEDIUM" else "thin")
    venue_label = "ROAD" if role == "AWAY" else "HOME"
    last5 = p.get("last5") or []
    ledger = []
    for r in last5:
        try:
            date = pd.to_datetime(r.get("date")).strftime("%b %-d")
        except Exception:
            date = str(r.get("date") or "—")
        margin = _signed(r.get("h2_margin"), 0)
        result_cls = "pos" if float(r.get("h2_margin") or 0) > 0 else ("neg" if float(r.get("h2_margin") or 0) < 0 else "")
        ledger.append(
            f'<div class="kwl4-row"><span>{escape(date)}</span><span>{escape(str(r.get("venue") or ""))} vs {escape(str(r.get("opponent") or "Opponent"))}</span><b class="{result_cls}">{margin}</b></div>'
        )
    ledger_html = "".join(ledger) if ledger else '<div class="kwl4-empty">No verified completed-game sample.</div>'

    return f"""<div class="kwl4-team">
<div class="kwl4-teamhead"><div><b>{escape(name)}</b><small>{escape(role)} • {int(p.get('games') or 0)} VERIFIED GP</small></div><span class="{cls}">{escape(rel)}</span></div>
<div class="kwl4-grid">
<div><small>2H PTS FOR / AGAINST</small><strong>{_num(p.get('h2_for'))} / {_num(p.get('h2_against'))}</strong></div>
<div><small>2H MARGIN</small><strong>{_signed(p.get('h2_margin'))}</strong></div>
<div><small>Q3 FOR / AGAINST</small><strong>{_num(p.get('q3_for'))} / {_num(p.get('q3_against'))}</strong></div>
<div><small>Q3 MARGIN</small><strong>{_signed(p.get('q3_margin'))}</strong></div>
<div><small>Q4 FOR / AGAINST</small><strong>{_num(p.get('q4_for'))} / {_num(p.get('q4_against'))}</strong></div>
<div><small>Q4 MARGIN</small><strong>{_signed(p.get('q4_margin'))}</strong></div>
<div><small>L10 2H MARGIN</small><strong>{_signed(p.get('l10_h2_margin'))}</strong></div>
<div><small>L5 2H MARGIN</small><strong>{_signed(p.get('l5_h2_margin'))}</strong></div>
<div><small>{venue_label} 2H MARGIN</small><strong>{_signed(p.get('venue_h2_margin'))}</strong><em>{int(p.get('venue_games') or 0)} game(s)</em></div>
<div><small>2H OUTSCORE RATE</small><strong>{_pct(p.get('h2_win_rate'))}</strong></div>
<div><small>HALFTIME LEAD HOLD</small><strong>{_pct(p.get('lead_hold_rate'))}</strong><em>{int(p.get('lead_sample') or 0)} lead(s)</em></div>
<div><small>HALFTIME COMEBACK</small><strong>{_pct(p.get('comeback_rate'))}</strong><em>{int(p.get('trail_sample') or 0)} deficit(s)</em></div>
</div>
<div class="kwl4-last"><small>LAST 5 • SECOND-HALF MARGIN</small>{ledger_html}</div>
</div>"""


def _live_h2(game: dict):
    away = game.get("away_lines") or {}
    home = game.get("home_lines") or {}
    periods = [p for p in (3, 4) if p in away and p in home]
    a = sum(int(away.get(p) or 0) for p in periods)
    h = sum(int(home.get(p) or 0) for p in periods)
    return a, h, periods


def _read(game: dict, ap: dict, hp: dict) -> str:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    a_hist, h_hist = ap.get("h2_margin"), hp.get("h2_margin")
    if a_hist is None or h_hist is None:
        hist_text = "Historical second-half comparison is incomplete."
    elif float(a_hist) > float(h_hist):
        hist_text = f"{away} has the stronger season second-half margin profile ({float(a_hist):+.1f} vs {float(h_hist):+.1f})."
    elif float(h_hist) > float(a_hist):
        hist_text = f"{home} has the stronger season second-half margin profile ({float(h_hist):+.1f} vs {float(a_hist):+.1f})."
    else:
        hist_text = "The teams have an even season second-half margin profile."

    a_live, h_live, periods = _live_h2(game)
    if periods:
        live_margin = a_live - h_live
        if live_margin > 0:
            live_text = f"In today's completed/active second-half periods, {away} is +{live_margin} ({a_live}-{h_live})."
        elif live_margin < 0:
            live_text = f"In today's completed/active second-half periods, {home} is +{abs(live_margin)} ({h_live}-{a_live})."
        else:
            live_text = f"Today's second-half scoring is even at {a_live}-{h_live} so far."
    else:
        live_text = "Today's second half has not started."
    return hist_text + " " + live_text + " Historical rates are context only and are not a live prediction."


def _game_html(game: dict, profiles: dict) -> str:
    ap, hp = profiles.get("away") or {}, profiles.get("home") or {}
    meta = profiles.get("meta") or {}
    fetched = "—"
    try:
        fetched = pd.to_datetime(meta.get("fetched_at"), utc=True).tz_convert(ET).strftime("%-I:%M:%S %p ET")
    except Exception:
        pass
    source_state = "READY" if not meta.get("error") and (ap or hp) else "CHECK"
    a_live, h_live, periods = _live_h2(game)
    live_label = f"{a_live}–{h_live}" if periods else "NOT STARTED"

    return f"""<div class="kwl4-game">
<div class="kwl4-head"><div><small>VERIFIED LIVE MATCHUP</small><b>{escape(str(game.get('away_team') or 'Away'))} @ {escape(str(game.get('home_team') or 'Home'))}</b></div><div><strong>{game.get('away_score','—')}–{game.get('home_score','—')}</strong><small>{escape(str(game.get('phase') or 'LIVE'))} • {escape(str(game.get('clock') or ''))}</small></div></div>
<div class="kwl4-badges"><span class="{'good' if source_state == 'READY' else 'warn'}">HISTORY • {source_state}</span><span>ESPN REGULAR SEASON ONLY</span><span>FETCH {fetched}</span><span>LIVE 2H {live_label}</span></div>
<div class="kwl4-teams">{_team_card(str(game.get('away_team') or 'Away'),'AWAY',ap)}{_team_card(str(game.get('home_team') or 'Home'),'HOME',hp)}</div>
<div class="kwl4-read"><small>SECOND-HALF CONTEXT READ • DESCRIPTIVE ONLY</small><p>{escape(_read(game, ap, hp))}</p></div>
<div class="kwl4-note">Completed regular-season games strictly before this live snapshot only. Q3/Q4 and second-half splits exclude overtime. Halftime lead-hold/comeback rates use final game results. No Step-4 history field is fed into a live moneyline, spread, total, probability, Monte Carlo, edge, EV or pick yet.</div>
</div>"""


def _css():
    st.markdown(r"""<style>
.kwl4-hero{border:1px solid #31566f;border-radius:22px;padding:20px;margin:26px 0 14px;background:linear-gradient(145deg,#0a1929,#081522)}.kwl4-eyebrow{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#8ad9ff}.kwl4-hero h3{font-size:1.45rem;margin:8px 0;color:#f6fbff}.kwl4-hero p{margin:0;color:#9bb0c0;line-height:1.55}.kwl4-hero b{color:#fff}
.kwl4-game{border:1px solid #31566f;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl4-head{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid #213b4e;padding-bottom:12px}.kwl4-head div{display:flex;flex-direction:column;gap:4px}.kwl4-head div:last-child{text-align:right}.kwl4-head small{font-size:.64rem;color:#7892a6;font-weight:850;letter-spacing:.06em}.kwl4-head b{font-size:1rem;color:#f5f8fb}.kwl4-head strong{font-size:1.35rem;color:#fff}
.kwl4-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl4-badges span{font-size:.60rem;border:1px solid #28495e;border-radius:999px;padding:6px 8px;color:#9db4c5}.kwl4-badges .good,.kwl4-teamhead .good{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl4-badges .warn,.kwl4-teamhead .warn{border-color:#8a722a;color:#ead879;background:#2a240d}.kwl4-teamhead .thin{border-color:#7b4e3d;color:#f0ad96;background:#2b1814}
.kwl4-teams{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kwl4-team{border:1px solid #29495d;border-radius:17px;padding:12px;background:#07111d}.kwl4-teamhead{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:10px}.kwl4-teamhead div{display:flex;flex-direction:column}.kwl4-teamhead b{color:#f5f8fb}.kwl4-teamhead small{color:#7d95a7;font-size:.58rem;margin-top:3px}.kwl4-teamhead>span{font-size:.57rem;font-weight:950;border:1px solid #31566f;border-radius:999px;padding:5px 7px}
.kwl4-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kwl4-grid>div{border:1px solid #243f52;border-radius:12px;padding:9px;min-height:67px;display:flex;flex-direction:column;justify-content:center}.kwl4-grid small{color:#7f98aa;font-size:.56rem;font-weight:900}.kwl4-grid strong{color:#f6f9fb;font-size:.92rem;margin-top:4px}.kwl4-grid em{color:#7891a3;font-size:.52rem;font-style:normal;margin-top:2px}
.kwl4-last{margin-top:10px;border-top:1px solid #213b4e;padding-top:9px}.kwl4-last>small{color:#91cdec;font-size:.58rem;font-weight:900}.kwl4-row{display:grid;grid-template-columns:58px 1fr 38px;gap:6px;align-items:center;padding:6px 0;border-bottom:1px solid #142b3a;font-size:.57rem;color:#92a8b7}.kwl4-row b{text-align:right;color:#dce8ef}.kwl4-row b.pos{color:#8ce9b4}.kwl4-row b.neg{color:#f0a294}.kwl4-empty{color:#8298a7;font-size:.62rem;padding:8px 0}
.kwl4-read{border:1px solid #34566b;border-radius:15px;padding:12px;margin-top:12px;background:#0a1723}.kwl4-read small{color:#8fcff5;font-size:.61rem;font-weight:950;letter-spacing:.05em}.kwl4-read p{color:#dce8ef;font-size:.73rem;line-height:1.55;margin:6px 0 0}.kwl4-note{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:15px;padding:12px;margin:12px 0 0;font-size:.65rem;line-height:1.5}.kwl4-boundary{border:1px solid #294b65;border-radius:15px;padding:13px;color:#8ea5b5;font-size:.68rem;line-height:1.55;margin:15px 0}
@media(max-width:640px){.kwl4-hero{padding:16px}.kwl4-game{padding:13px}.kwl4-teams{grid-template-columns:1fr}.kwl4-head{align-items:center}.kwl4-head b{font-size:.9rem}}
</style>""", unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v3.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _css()
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    st.markdown(f"""<div class="kwl4-hero">
<div class="kwl4-eyebrow">🕒 {MODEL_VERSION}</div>
<h3>Step 4 • Second-Half + Q3/Q4 Historical Performance</h3>
<p>Historical context only. We use completed <b>regular-season games strictly before the current live state</b> to measure second-half scoring, Q3/Q4 splits, recent second-half margins, home/road context, halftime lead holds and comeback rates. No pick exists yet.</p>
</div>""", unsafe_allow_html=True)

    if st.button("🔄 Refresh Step 4 historical profiles", use_container_width=True, key="wnba_live_v4_refresh"):
        hist.clear_cache()
        try:
            v1._espn_live_snapshot.clear()
        except Exception:
            pass
        st.rerun()

    games, _, _ = v2._verified_live_games(day_str)
    if not games:
        st.info("No Step-1 verified WNBA game is live right now, so Step 4 has no live matchup to attach historical profiles to.")
        st.markdown('<div class="kwl4-boundary">STEP 4 BOUNDARY • NO live projection • NO probability • NO Monte Carlo • NO edge/EV • NO qualification • NO pick</div>', unsafe_allow_html=True)
        return

    for game in games:
        profiles = hist.profiles_for_game(game, int(day_str[:4]))
        st.markdown(_game_html(game, profiles), unsafe_allow_html=True)

    st.markdown('<div class="kwl4-boundary">STEP 4 BOUNDARY • historical second-half / Q3 / Q4 / halftime-state context is DESCRIPTIVE ONLY • sportsbook prices remain isolated in Step 2 • NO live projection • NO probability • NO Monte Carlo • NO recommendation</div>', unsafe_allow_html=True)
