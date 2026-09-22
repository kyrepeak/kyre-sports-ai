"""WNBA Spread V1.6.3 — Top-5 Card Step 3: team form + venue splits.

Presentation-only wrapper over the verified V1.6.2 Step-2 card layer. Step 3
uses the same official WNBA completed-game schedule payload already verified by
Step 2 and adds current-season form for both teams. It never feeds the protected
V1.6.1 margin model, sportsbook transport, analytical probability, 5,000,000
Monte Carlo, convergence, qualification, selected side, edge/EV or ranking.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v162_core as prior

base = prior.base
MODEL_VERSION = "WNBA SPREAD V1.6.3 • TOP-5 CARD STEP 3 TEAM FORM"
_ORIGINAL_HISTORY_BLOCK = prior._history_block


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _record(wins: int, losses: int) -> str:
    total = int(wins) + int(losses)
    return "—" if total <= 0 else f"{int(wins)}-{int(losses)}"


def _fmt(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _margin(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.1f} pts"


def _team_games_before(results: pd.DataFrame, day, team_id: int) -> pd.DataFrame:
    """One team-perspective row per completed current-season game before slate."""
    if results is None or results.empty or not int(team_id or 0):
        return pd.DataFrame()
    cutoff = pd.to_datetime(day).normalize()
    rows = []
    for _, game in results.iterrows():
        gdate = pd.to_datetime(game.get("game_date"), errors="coerce")
        if pd.isna(gdate) or gdate >= cutoff:
            continue
        away_id = int(_num(game.get("away_team_id"), 0) or 0)
        home_id = int(_num(game.get("home_team_id"), 0) or 0)
        if int(team_id) == home_id:
            pf, pa = _num(game.get("home_score")), _num(game.get("away_score"))
            is_home = True
            opponent = str(game.get("away_team") or game.get("away_abbr") or "Opponent")
        elif int(team_id) == away_id:
            pf, pa = _num(game.get("away_score")), _num(game.get("home_score"))
            is_home = False
            opponent = str(game.get("home_team") or game.get("home_abbr") or "Opponent")
        else:
            continue
        if not np.isfinite(pf) or not np.isfinite(pa):
            continue
        diff = float(pf - pa)
        rows.append({
            "date": gdate, "pf": float(pf), "pa": float(pa), "margin": diff,
            "win": bool(diff > 0), "home": bool(is_home), "opponent": opponent,
        })
    return (
        pd.DataFrame(rows).sort_values("date", ascending=False).reset_index(drop=True)
        if rows else pd.DataFrame()
    )


def _split_record(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return "—"
    wins = int(frame["win"].astype(bool).sum())
    return _record(wins, int(len(frame) - wins))


def _streak(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return "—"
    values = frame["win"].astype(bool).tolist()
    first, count = values[0], 0
    for value in values:
        if value != first:
            break
        count += 1
    return f"{'W' if first else 'L'}{count}"


def _form_profile(results: pd.DataFrame, day, team_id: int, team_name: str) -> dict:
    games = _team_games_before(results, day, team_id)
    if games.empty:
        return {"state":"NO_DATA","team_id":int(team_id or 0),"team":team_name,"games":0}

    gp = int(len(games))
    wins = int(games["win"].astype(bool).sum())
    l10, l5 = games.head(10), games.head(5)
    home = games.loc[games["home"].astype(bool)]
    away = games.loc[~games["home"].astype(bool)]
    season_margin = float(games["margin"].mean())
    l10_margin = float(l10["margin"].mean())
    l5_margin = float(l5["margin"].mean())
    trend_delta = l10_margin - season_margin
    if trend_delta >= 2.5:
        trend, trend_class = "IMPROVING", "good"
    elif trend_delta <= -2.5:
        trend, trend_class = "DECLINING", "bad"
    else:
        trend, trend_class = "STEADY", "mid"

    if gp >= 20:
        reliability, rel_class = "HIGH", "good"
    elif gp >= 10:
        reliability, rel_class = "MEDIUM", "mid"
    else:
        reliability, rel_class = "LOW", "warn"

    last = games.iloc[0]
    dt = last.get("date")
    last_date = dt.strftime("%b %d") if pd.notna(dt) else "—"
    last_result = "W" if bool(last.get("win")) else "L"
    last_text = (
        f"{last_date} • vs {last.get('opponent','Opponent')} • "
        f"{float(last.get('pf')):.0f}–{float(last.get('pa')):.0f} • "
        f"{last_result} {float(last.get('margin')):+.0f}"
    )

    return {
        "state":"READY","team_id":int(team_id),"team":str(team_name or "Team"),"games":gp,
        "record":_record(wins,gp-wins),"win_pct":wins/gp,
        "l10_record":_split_record(l10),"l5_record":_split_record(l5),
        "home_record":_split_record(home),"away_record":_split_record(away),
        "pf":float(games["pf"].mean()),"pa":float(games["pa"].mean()),
        "season_margin":season_margin,"l10_margin":l10_margin,"l5_margin":l5_margin,
        "recent_margins":" • ".join(f"{float(x):+.0f}" for x in l5["margin"].tolist()) or "—",
        "streak":_streak(games),"trend":trend,"trend_class":trend_class,
        "reliability":reliability,"reliability_class":rel_class,"last":last_text,
    }


def _profile_html(profile: dict, role: str) -> str:
    team = escape(str(profile.get("team") or "Team"))
    role_text = escape(str(role))
    tid = int(profile.get("team_id") or 0)
    logo = escape(prior._logo(tid), quote=True)
    img = f'<img src="{logo}" alt="{team} logo">' if logo else "🏀"
    if str(profile.get("state") or "").upper() != "READY":
        return f"""
      <div class="ks-spread163-teamform">
        <div class="ks-spread163-teamhead"><span class="ks-spread163-flogo">{img}</span><span><b>{team}</b><small>{role_text}</small></span></div>
        <div class="ks-spread163-empty">No completed current-season form sample was available before this slate date.</div>
      </div>"""

    win_pct = _num(profile.get("win_pct"), np.nan)
    win_text = "—" if not np.isfinite(win_pct) else f"{100.0*win_pct:.1f}%"
    trend = escape(str(profile.get("trend") or "STEADY"))
    trend_class = escape(str(profile.get("trend_class") or "mid"))
    rel = escape(str(profile.get("reliability") or "LOW"))
    rel_class = escape(str(profile.get("reliability_class") or "warn"))
    return f"""
      <div class="ks-spread163-teamform">
        <div class="ks-spread163-teamhead">
          <span class="ks-spread163-flogo">{img}</span>
          <span><b>{team}</b><small>{role_text} • {int(profile.get('games') or 0)} GP</small></span>
          <span class="ks-spread163-chip {rel_class}">{rel}</span>
        </div>
        <div class="ks-spread163-formgrid">
          <div><small>SEASON RECORD</small><strong>{escape(str(profile.get('record') or '—'))}</strong></div>
          <div><small>WIN %</small><strong>{win_text}</strong></div>
          <div><small>LAST 10</small><strong>{escape(str(profile.get('l10_record') or '—'))}</strong></div>
          <div><small>LAST 5</small><strong>{escape(str(profile.get('l5_record') or '—'))}</strong></div>
          <div><small>HOME RECORD</small><strong>{escape(str(profile.get('home_record') or '—'))}</strong></div>
          <div><small>AWAY RECORD</small><strong>{escape(str(profile.get('away_record') or '—'))}</strong></div>
          <div><small>SEASON PF / PA</small><strong>{_fmt(profile.get('pf'))} / {_fmt(profile.get('pa'))}</strong></div>
          <div><small>SEASON MARGIN</small><strong>{_margin(profile.get('season_margin'))}</strong></div>
          <div><small>L10 MARGIN</small><strong>{_margin(profile.get('l10_margin'))}</strong></div>
          <div><small>L5 MARGIN</small><strong>{_margin(profile.get('l5_margin'))}</strong></div>
          <div><small>CURRENT STREAK</small><strong>{escape(str(profile.get('streak') or '—'))}</strong></div>
          <div><small>FORM TREND</small><strong class="{trend_class}">{trend}</strong></div>
          <div class="wide"><small>LAST 5 GAME MARGINS</small><strong>{escape(str(profile.get('recent_margins') or '—'))}</strong></div>
          <div class="wide"><small>MOST RECENT GAME</small><strong>{escape(str(profile.get('last') or '—'))}</strong></div>
        </div>
      </div>"""


def _form_block(day_str: str, row) -> str:
    try:
        selected_is_home = prior._is_home(row)
        away_id, home_id, identity_source = prior._resolved_team_ids(str(day_str), row)
        if not away_id or not home_id:
            raise ValueError("team IDs could not be resolved from the verified daily schedule")
        away_name = str(row.get("away_team") or "Away")
        home_name = str(row.get("home_team") or "Home")
        selected_id = home_id if selected_is_home else away_id
        opponent_id = away_id if selected_is_home else home_id
        selected_name = str(row.get("best_side") or (home_name if selected_is_home else away_name))
        opponent_name = away_name if selected_is_home else home_name

        results, provider = prior._official_history_results(str(day_str))
        if str((provider or {}).get("state") or "").upper() != "READY":
            raise RuntimeError(str((provider or {}).get("error") or "official WNBA form source unavailable"))
        selected = _form_profile(results, day_str, selected_id, selected_name)
        opponent = _form_profile(results, day_str, opponent_id, opponent_name)
        source = str((provider or {}).get("source") or "WNBA official CDN completed-game scores")
        season = int((provider or {}).get("season") or pd.to_datetime(day_str).year)
    except Exception as exc:
        return f"""
  <div class="ks-spread163-form">
    <div class="ks-spread163-head"><span>STEP 3 • TEAM FORM + HOME / AWAY PERFORMANCE</span><span class="ks-spread163-chip warn">SOURCE CHECK</span></div>
    <div class="ks-spread163-empty">Team-form context is temporarily unavailable. Steps 1–2 and the verified Spread model remain unchanged.</div>
    <div class="ks-spread163-note">Diagnostic • {escape(str(exc)[:180])}</div>
  </div>"""

    available = int(str(selected.get("state")).upper()=="READY") + int(str(opponent.get("state")).upper()=="READY")
    state_class = "good" if available == 2 else "warn"
    state_text = "VERIFIED FORM" if available == 2 else "PARTIAL FORM"
    return f"""
  <div class="ks-spread163-form">
    <div class="ks-spread163-head"><span>STEP 3 • TEAM FORM + HOME / AWAY PERFORMANCE</span><span class="ks-spread163-chip {state_class}">{state_text}</span></div>
    <div class="ks-spread163-scope">{season} current season • completed games strictly before this slate • no future-game leakage</div>
    <div class="ks-spread163-teams">
      {_profile_html(selected,'SELECTED SPREAD SIDE')}
      {_profile_html(opponent,'OPPONENT')}
    </div>
    <div class="ks-spread163-note">Source • {escape(source)} • identity • {escape(str(identity_source))} • descriptive only • NOT FED INTO projected margin, 5M Monte Carlo, edge, EV, qualification, selected side or card ranking. Pace / OffRtg / DefRtg are intentionally reserved for Step 4.</div>
  </div>"""


def _history_plus_form(day_str: str, row) -> str:
    return _ORIGINAL_HISTORY_BLOCK(day_str, row) + _form_block(day_str, row)


def _install_step3() -> None:
    # Only replace V1.6.2's HTML history seam. Production payload/functions remain untouched.
    prior._history_block = _history_plus_form


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_step3()
    prior._install()
    st.markdown("""
<style>
.ks-spread163-form{background:#0b1725;border:1px solid #34526d;border-radius:15px;padding:12px;margin-top:14px}
.ks-spread163-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#9ed9ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.ks-spread163-scope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}
.ks-spread163-teams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.ks-spread163-teamform{background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}
.ks-spread163-teamhead{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:7px;margin-bottom:9px}
.ks-spread163-teamhead b{display:block;color:#f5fbff;font-size:.73rem;line-height:1.15}.ks-spread163-teamhead small{display:block;color:#7890a5;font-size:.44rem;font-weight:900;margin-top:3px;letter-spacing:.03em}
.ks-spread163-flogo{width:32px;height:32px;display:flex;align-items:center;justify-content:center}.ks-spread163-flogo img{max-width:32px;max-height:32px;object-fit:contain}
.ks-spread163-chip{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.45rem;font-weight:950;white-space:nowrap}.ks-spread163-chip.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread163-chip.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread163-chip.warn,.ks-spread163-chip.bad{border-color:#7c5832;background:#352516;color:#ffc984}
.ks-spread163-formgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread163-formgrid div{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:7px}.ks-spread163-formgrid .wide{grid-column:1/-1}.ks-spread163-formgrid small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread163-formgrid strong{display:block;color:#f6fbff;font-size:.67rem;margin-top:3px;line-height:1.3}.ks-spread163-formgrid strong.good{color:#7df2ba}.ks-spread163-formgrid strong.bad{color:#ffb0b7}.ks-spread163-formgrid strong.mid{color:#ffe17a}
.ks-spread163-note{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread163-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread163-head{align-items:flex-start}.ks-spread163-teams{grid-template-columns:1fr}.ks-spread163-chip{font-size:.43rem}}
</style>
""",unsafe_allow_html=True)
    st.caption(
        "🎨 Spread V1.6.3 • Top-5 Card Steps 1–3 ACTIVE • verified model snapshot + official WNBA H2H + "
        "team form/home-away splits • all context remains presentation-only"
    )
    return prior.prior.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
