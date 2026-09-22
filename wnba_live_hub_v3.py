"""WNBA Live Games V3 — Step 3 current-game quarter + pace analytics.

Preserves V2 (frozen Step 1 + Step 2 market verification) unchanged and appends
one descriptive, read-only current-game basketball layer. Step 3 does not use
sportsbook prices as an input and cannot create/alter a pick or probability.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_hub_v2 as v2
import wnba_live_flow_v1 as flow

MODEL_VERSION = "WNBA LIVE GAMES V3 • STEP 3 CURRENT GAME FLOW + PACE"
ET = ZoneInfo("America/New_York")


def _num(value, digits=1, suffix=""):
    try:
        x = float(value)
        return f"{x:.{digits}f}{suffix}"
    except Exception:
        return "—"


def _pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _secs(value):
    try:
        x = max(0, int(value))
    except Exception:
        return "—"
    m, s = divmod(x, 60)
    return f"{m}:{s:02d}" if m else f"0:{s:02d}"


def _stamp(value):
    if not value:
        return "—"
    try:
        return pd.to_datetime(value, utc=True).tz_convert(ET).strftime("%-I:%M:%S %p ET")
    except Exception:
        return "—"


def _pace_read(value):
    try:
        x = float(value)
    except Exception:
        return "UNAVAILABLE"
    if x >= 84:
        return "VERY FAST"
    if x >= 81:
        return "FAST"
    if x >= 77:
        return "NORMAL"
    if x >= 74:
        return "SLOW"
    return "VERY SLOW"


def _shoot_read(value):
    try:
        x = float(value)
    except Exception:
        return "—"
    if x >= 0.62:
        return "HOT"
    if x <= 0.42:
        return "COLD"
    return "NORMAL"


def _quarter_rows(game: dict) -> str:
    away = game.get("away_lines") or {}
    home = game.get("home_lines") or {}
    current = max(1, int(game.get("period") or 1))
    periods = sorted(set(away) | set(home) | set(range(1, min(max(current, 4), 8) + 1)))
    pieces = []
    for p in periods:
        a = away.get(p, "—")
        h = home.get(p, "—")
        try:
            ai, hi = int(a), int(h)
            total = ai + hi
            margin = ai - hi
            if margin > 0:
                margin_text = f"AWAY +{margin}"
            elif margin < 0:
                margin_text = f"HOME +{abs(margin)}"
            else:
                margin_text = "EVEN"
        except Exception:
            total, margin_text = "—", "—"
        label = f"Q{p}" if p <= 4 else ("OT" if p == 5 else f"{p-4}OT")
        current_cls = " current" if p == current else ""
        pieces.append(
            f'<div class="kwl3-q{current_cls}"><small>{escape(label)}</small>'
            f'<b>{escape(str(a))}–{escape(str(h))}</b><span>TOTAL {escape(str(total))}</span>'
            f'<span>{escape(margin_text)}</span></div>'
        )
    return "".join(pieces)


def _metric(label, value, sub=""):
    sub_html = f"<small>{escape(str(sub))}</small>" if sub else ""
    return f'<div class="kwl3-metric"><span>{escape(str(label))}</span><strong>{escape(str(value))}</strong>{sub_html}</div>'


def _team_efficiency(name: str, metrics: dict) -> str:
    if not metrics:
        return f'''<div class="kwl3-team"><h4>{escape(name)}</h4><div class="kwl3-empty">Live team boxscore detail is temporarily unavailable. Score/clock flow remains verified.</div></div>'''
    return f'''<div class="kwl3-team">
<h4>{escape(name)}</h4>
<div class="kwl3-teamgrid">
{_metric('eFG%', _pct(metrics.get('efg')), _shoot_read(metrics.get('efg')))}
{_metric('TS%', _pct(metrics.get('ts')))}
{_metric('EST. POSS', _num(metrics.get('poss'),1))}
{_metric('PTS / POSS', _num(metrics.get('ppp'),2))}
{_metric('TURNOVERS', _num(metrics.get('tov'),0), f"TOV RATE {_pct(metrics.get('tov_rate'))}")}
{_metric('OFF REB', _num(metrics.get('oreb'),0), f"OREB% {_pct(metrics.get('oreb_rate'))}")}
{_metric('ASSISTS', _num(metrics.get('ast'),0))}
{_metric('FT RATE', _pct(metrics.get('ftr')), 'FTA / FGA')}
</div></div>'''


def _flow_read(game: dict, a: dict) -> str:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    fh_a, fh_h = int(a.get("first_half_away") or 0), int(a.get("first_half_home") or 0)
    sh_a, sh_h = int(a.get("second_half_away") or 0), int(a.get("second_half_home") or 0)
    fh_margin = fh_a - fh_h
    sh_margin = sh_a - sh_h
    if fh_margin > 0:
        fh_text = f"{away} led the first half by {fh_margin}."
    elif fh_margin < 0:
        fh_text = f"{home} led the first half by {abs(fh_margin)}."
    else:
        fh_text = "The first half was even."

    period = int(a.get("current_period") or 0)
    if period >= 3:
        if sh_margin > 0:
            sh_text = f"{away} is +{sh_margin} in second-half scoring so far."
        elif sh_margin < 0:
            sh_text = f"{home} is +{abs(sh_margin)} in second-half scoring so far."
        else:
            sh_text = "Second-half scoring is even so far."
    else:
        sh_text = "Second-half flow has not started yet."

    pace_text = ""
    if a.get("score_pace_total") is not None:
        pace_text = f" The current scoring rate extrapolates to {float(a['score_pace_total']):.1f} regulation points; this is descriptive pace, not a final-score projection."
    poss_text = ""
    if a.get("pace40") is not None:
        poss_text = f" Estimated possession pace is {float(a['pace40']):.1f} per 40 minutes."
    return fh_text + " " + sh_text + pace_text + poss_text


def _game_html(game: dict, a: dict) -> str:
    quality = str(a.get("data_quality") or "CHECK")
    qcls = "good" if quality == "HIGH" else "warn"
    pace_label = _pace_read(a.get("pace40"))
    elapsed = _secs(a.get("elapsed_seconds"))
    remaining = _secs(a.get("regulation_remaining_seconds"))
    box_fetch = _stamp((a.get("summary_meta") or {}).get("fetched_at"))
    state_stamp = _stamp(game.get("captured_at"))
    current_q = int(a.get("current_period") or 0)
    qlabel = f"Q{current_q}" if 0 < current_q <= 4 else ("OT" if current_q == 5 else f"{max(1,current_q-4)}OT")

    return f'''<div class="kwl3-game">
<div class="kwl3-head"><div><small>VERIFIED LIVE MATCHUP</small><b>{escape(str(game.get('away_team') or 'Away'))} @ {escape(str(game.get('home_team') or 'Home'))}</b></div><div><strong>{game.get('away_score','—')}–{game.get('home_score','—')}</strong><small>{escape(str(game.get('phase') or qlabel))} • {escape(str(game.get('clock') or ''))}</small></div></div>
<div class="kwl3-badges"><span class="{qcls}">DATA • {escape(quality)}</span><span>STATE {state_stamp}</span><span>BOX FETCH {box_fetch}</span><span>{escape(qlabel)} FLOW</span></div>
<div class="kwl3-title">QUARTER FLOW</div>
<div class="kwl3-quartergrid">{_quarter_rows(game)}</div>
<div class="kwl3-title">LIVE SCORING + PACE ENVIRONMENT</div>
<div class="kwl3-grid">
{_metric('ELAPSED GAME TIME', elapsed)}
{_metric('REGULATION LEFT', remaining)}
{_metric('TOTAL POINTS NOW', _num(a.get('total_points'),0))}
{_metric('RAW SCORE-PACE TOTAL', _num(a.get('score_pace_total'),1), 'descriptive extrapolation')}
{_metric('CURRENT QUARTER PTS', _num(a.get('current_quarter_total'),0))}
{_metric('CURRENT-Q RATE', _num(a.get('current_quarter_scoring_pace'),1), 'full-period scoring-rate equivalent')}
{_metric('EST. PACE / 40', _num(a.get('pace40'),1), pace_label)}
{_metric('EST. POSS REMAINING', _num(a.get('remaining_possessions'),1), 'regulation only')}
{_metric('1H SCORE', f"{int(a.get('first_half_away') or 0)}–{int(a.get('first_half_home') or 0)}")}
{_metric('2H SCORE SO FAR', f"{int(a.get('second_half_away') or 0)}–{int(a.get('second_half_home') or 0)}")}
</div>
<div class="kwl3-title">LIVE TEAM EFFICIENCY</div>
<div class="kwl3-teams">{_team_efficiency(str(game.get('away_team') or 'Away'), a.get('away') or {})}{_team_efficiency(str(game.get('home_team') or 'Home'), a.get('home') or {})}</div>
<div class="kwl3-read"><small>LIVE FLOW READ • CONTEXT ONLY</small><p>{escape(_flow_read(game, a))}</p></div>
<div class="kwl3-note">Possessions use the basketball estimate <b>FGA + 0.44×FTA − OREB + TO</b> when ESPN's live boxscore fields are available. Score-rate pace and quarter flow always come from the verified Step-1 state. These are descriptive live signals only.</div>
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl3-hero{border:1px solid #31566f;border-radius:22px;padding:20px;margin:26px 0 14px;background:linear-gradient(145deg,#0a1929,#081522)}.kwl3-eyebrow{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#8ad9ff}.kwl3-hero h3{font-size:1.45rem;margin:8px 0;color:#f6fbff}.kwl3-hero p{margin:0;color:#9bb0c0;line-height:1.55}.kwl3-hero b{color:#fff}
.kwl3-game{border:1px solid #31566f;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl3-head{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid #213b4e;padding-bottom:12px}.kwl3-head div{display:flex;flex-direction:column;gap:4px}.kwl3-head div:last-child{text-align:right}.kwl3-head small{font-size:.64rem;color:#7892a6;font-weight:850;letter-spacing:.06em}.kwl3-head b{font-size:1rem;color:#f5f8fb}.kwl3-head strong{font-size:1.35rem;color:#fff}.kwl3-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl3-badges span{font-size:.61rem;border:1px solid #28495e;border-radius:999px;padding:6px 8px;color:#9db4c5}.kwl3-badges .good{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl3-badges .warn{border-color:#8a722a;color:#ead879;background:#2a240d}
.kwl3-title{font-size:.72rem;color:#a8ddff;letter-spacing:.07em;font-weight:950;margin:16px 0 8px}.kwl3-quartergrid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.kwl3-q{border:1px solid #29495d;border-radius:14px;padding:9px;background:#07111d;display:flex;flex-direction:column;gap:4px}.kwl3-q.current{border-color:#3e8c6a;background:#0c261d}.kwl3-q small{color:#7f98aa;font-size:.61rem;font-weight:900}.kwl3-q b{color:#fff;font-size:1rem}.kwl3-q span{color:#8fa4b4;font-size:.57rem}.kwl3-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl3-metric{border:1px solid #29495d;border-radius:14px;padding:10px;background:#07111d;min-height:72px;display:flex;flex-direction:column;justify-content:center}.kwl3-metric span{font-size:.59rem;color:#7f98aa;font-weight:900;letter-spacing:.04em}.kwl3-metric strong{font-size:1.02rem;color:#f6f9fb;margin-top:5px}.kwl3-metric small{color:#8aa0b0;margin-top:3px;font-size:.57rem}.kwl3-teams{display:grid;grid-template-columns:1fr 1fr;gap:9px}.kwl3-team{border:1px solid #29495d;border-radius:16px;padding:11px;background:#07111d}.kwl3-team h4{color:#f3f7fa;margin:0 0 9px;font-size:.86rem}.kwl3-teamgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px}.kwl3-team .kwl3-metric{min-height:65px;padding:8px}.kwl3-empty{color:#8ca0ae;font-size:.68rem;line-height:1.45;border:1px dashed #2d4b5f;border-radius:12px;padding:10px}.kwl3-read{border:1px solid #34566b;border-radius:15px;padding:12px;margin-top:12px;background:#0a1723}.kwl3-read small{color:#8fcff5;font-size:.61rem;font-weight:950;letter-spacing:.05em}.kwl3-read p{color:#dce8ef;font-size:.73rem;line-height:1.55;margin:6px 0 0}.kwl3-note{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:15px;padding:12px;margin:12px 0 0;font-size:.65rem;line-height:1.5}.kwl3-boundary{border:1px solid #294b65;border-radius:15px;padding:13px;color:#8ea5b5;font-size:.68rem;line-height:1.55;margin:15px 0}
@media(max-width:640px){.kwl3-hero{padding:16px}.kwl3-game{padding:13px}.kwl3-quartergrid{grid-template-columns:repeat(2,1fr)}.kwl3-teams{grid-template-columns:1fr}.kwl3-head{align-items:center}.kwl3-head b{font-size:.9rem}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v2.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _css()
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    st.markdown(f'''<div class="kwl3-hero"><div class="kwl3-eyebrow">📊 {MODEL_VERSION}</div><h3>Step 3 • Current Game Quarter + Pace Analysis</h3><p>Read-only basketball context from the <b>verified live score/clock/quarter state</b>, plus ESPN live boxscore fields when available. This layer measures current quarter flow, scoring rate, estimated possessions, shooting efficiency, turnovers, offensive rebounding and free-throw pressure. <b>Sportsbook prices are not inputs.</b></p></div>''', unsafe_allow_html=True)

    if st.button("🔄 Refresh Step 3 live analysis", use_container_width=True, key="wnba_live_v3_refresh"):
        try:
            import wnba_live_hub_v1 as v1
            v1._espn_live_snapshot.clear()
        except Exception:
            pass
        flow.clear_cache()
        try:
            import wnba_live_market_v1 as market
            market.clear_cache()
        except Exception:
            pass
        st.rerun()

    games, diag, live_meta = v2._verified_live_games(day_str)
    if not games:
        st.info("No Step-1 verified WNBA game is live right now, so Step 3 has no current-game flow to analyze.")
        st.markdown('<div class="kwl3-boundary">STEP 3 BOUNDARY • no verified live state = no pace card • NO historical second-half model yet • NO projection • NO Monte Carlo • NO edge/EV • NO pick</div>', unsafe_allow_html=True)
        return

    for game in games:
        analysis = flow.analyze_game(game)
        st.markdown(_game_html(game, analysis), unsafe_allow_html=True)

    st.markdown('<div class="kwl3-boundary">STEP 3 BOUNDARY • current-game flow + pace + live boxscore efficiency are DESCRIPTIVE ONLY • Step 2 sportsbook prices are NOT inputs • NO historical second-half weighting yet • NO projected final score • NO win/cover/total probability • NO Monte Carlo • NO qualification • NO pick</div>', unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "render_wnba_live_hub"]
