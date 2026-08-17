from datetime import datetime
import math

import numpy as np
import pandas as pd
import streamlit as st

from engine import ET, clamp, odds
from live_game_hub_v182 import (
    _priority,
    _state_label,
    _time_sort,
    _verified_df,
    fetch_live_feed,
    fetch_live_slate,
)
from spread_engine import build_game_model, pitcher_stats, _pitcher_run_multiplier, _stable_seed

MODEL_VERSION = "V19"
UI_VERSION = "LIVE UI 15"


LIVE_CSS = r"""
<style>
:root{
  --lv-bg:#07101f; --lv-card:#0d192c; --lv-card2:#101f35; --lv-line:#223a5e;
  --lv-blue:#38bdf8; --lv-cyan:#22d3ee; --lv-green:#34d399; --lv-red:#fb5a67;
  --lv-gold:#facc15; --lv-text:#f8fafc; --lv-muted:#91a4bd;
}
.lv-wrap{margin-top:.45rem}
.lv-kicker{font-size:.73rem;letter-spacing:.16em;font-weight:900;color:var(--lv-cyan);text-transform:uppercase;margin-bottom:.45rem}
.lv-scoreboard{position:relative;overflow:hidden;border:1px solid #26466f;background:linear-gradient(135deg,#0a1730 0%,#0b1b31 52%,#07101f 100%);border-radius:24px;padding:18px 18px 16px;box-shadow:0 16px 42px rgba(0,0,0,.28);margin:10px 0 16px}
.lv-scoreboard:before{content:"";position:absolute;inset:-35% auto auto -8%;width:250px;height:250px;border-radius:50%;background:rgba(34,211,238,.07);filter:blur(2px)}
.lv-topline{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:12px;position:relative}
.lv-livepill,.lv-pill{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:6px 10px;font-size:.72rem;font-weight:850;letter-spacing:.05em;border:1px solid #2b4468;background:#0b1830;color:#cfe8ff}
.lv-livepill{color:#ffd8dd;border-color:#6d2934;background:#2a1118}.lv-dot{width:8px;height:8px;border-radius:50%;background:var(--lv-red);box-shadow:0 0 0 0 rgba(251,90,103,.75);animation:lvpulse 1.5s infinite}
@keyframes lvpulse{0%{box-shadow:0 0 0 0 rgba(251,90,103,.7)}70%{box-shadow:0 0 0 8px rgba(251,90,103,0)}100%{box-shadow:0 0 0 0 rgba(251,90,103,0)}}
.lv-teamrow{display:grid;grid-template-columns:minmax(0,1fr) 60px;gap:12px;align-items:center;padding:10px 0;position:relative}.lv-teamrow+.lv-teamrow{border-top:1px solid rgba(145,164,189,.14)}
.lv-team{display:flex;align-items:center;gap:12px;min-width:0}.lv-logo{width:42px;height:42px;object-fit:contain}.lv-teamname{font-size:1.12rem;font-weight:850;color:var(--lv-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lv-sub{font-size:.77rem;color:var(--lv-muted);margin-top:2px}.lv-score{font-size:2.55rem;line-height:1;font-weight:950;text-align:right;color:white;font-variant-numeric:tabular-nums}
.lv-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0 18px}.lv-stat{border:1px solid #213958;background:linear-gradient(180deg,#0d1b30,#0a1526);border-radius:16px;padding:12px}.lv-label{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:#7f96b2;font-weight:800}.lv-value{font-size:1.15rem;font-weight:900;color:#f8fafc;margin-top:3px}.lv-value.blue{color:var(--lv-cyan)}
.lv-section{font-size:1.18rem;font-weight:900;color:#f8fafc;margin:20px 0 10px;display:flex;align-items:center;gap:8px}
.lv-matchup{display:grid;grid-template-columns:1fr 1fr;gap:10px}.lv-person{border:1px solid #223c60;background:linear-gradient(145deg,#0f1d32,#0a1628);border-radius:18px;padding:14px}.lv-role{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:#7f96b2;font-weight:850}.lv-name{font-size:1.12rem;font-weight:900;color:white;margin:5px 0}.lv-detail{font-size:.8rem;color:#9eb0c7;line-height:1.45}
.lv-basegrid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.lv-base{border:1px solid #25415f;background:#0c192b;border-radius:14px;padding:11px;text-align:center}.lv-base.on{border-color:#1689b5;background:linear-gradient(180deg,#0b2a43,#0d1f35);box-shadow:inset 0 0 0 1px rgba(34,211,238,.13)}.lv-baseicon{font-size:1.1rem;color:#68819f}.lv-base.on .lv-baseicon{color:var(--lv-cyan)}.lv-basename{font-size:.77rem;color:#d7e4f2;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lv-play{border-left:3px solid var(--lv-cyan);background:#091829;border-radius:0 14px 14px 0;padding:12px 14px;color:#d8e7f6;line-height:1.45}
.lv-market-head{border:1px solid #294466;background:linear-gradient(135deg,#0d1b30,#0b1525);border-radius:20px;padding:15px;margin:14px 0 8px}.lv-market-title{font-size:1.15rem;font-weight:950}.lv-market-sub{font-size:.78rem;color:#91a4bd;margin-top:3px}
.lv-projgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}.lv-proj{border:1px solid #27415f;background:linear-gradient(180deg,#102038,#0a1626);border-radius:17px;padding:13px}.lv-proj.big{border-color:#176b89;box-shadow:inset 0 0 0 1px rgba(34,211,238,.08)}.lv-projnum{font-size:1.65rem;font-weight:950;color:white;margin-top:3px}.lv-projnum.good{color:#5ee8b0}.lv-projnum.cyan{color:#67e8f9}.lv-projsmall{font-size:.73rem;color:#93a7bf;margin-top:2px}
.lv-stale{border:1px solid #6c4c17;background:#2b2109;color:#ffe6a3;padding:10px 12px;border-radius:12px;font-size:.8rem;margin:8px 0}.lv-fresh{border:1px solid #166044;background:#0b2a20;color:#9ff1ce;padding:9px 12px;border-radius:12px;font-size:.8rem;margin:8px 0}
.lv-live-list{display:grid;gap:8px;margin:8px 0 14px}.lv-gamechip{border:1px solid #1f4667;background:linear-gradient(90deg,#0b2239,#0c1728);border-radius:14px;padding:11px 13px;color:#dff5ff}.lv-gamechip b{color:white}
@media(max-width:700px){.lv-scoreboard{border-radius:20px;padding:15px}.lv-teamrow{grid-template-columns:minmax(0,1fr) 48px}.lv-logo{width:36px;height:36px}.lv-teamname{font-size:1rem}.lv-score{font-size:2.15rem}.lv-strip{grid-template-columns:1fr 1fr}.lv-matchup{grid-template-columns:1fr}.lv-projgrid{grid-template-columns:1fr 1fr}.lv-projgrid .lv-proj:first-child{grid-column:1/-1}.lv-basegrid{grid-template-columns:1fr}.lv-topline{align-items:flex-start;flex-direction:column}}
</style>
"""


def _logo(team_id):
    try:
        return f"https://www.mlbstatic.com/team-logos/{int(team_id)}.svg"
    except Exception:
        return ""


def _name(obj, fallback="—"):
    if not isinstance(obj, dict):
        return fallback
    return obj.get("fullName") or obj.get("name") or fallback


def _parse_inning(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    try:
        return max(1, int(digits))
    except Exception:
        return 1


def _state(feed):
    game_data = feed.get("gameData") or {}
    live = feed.get("liveData") or {}
    linescore = live.get("linescore") or {}
    plays = live.get("plays") or {}
    current = plays.get("currentPlay") or {}
    matchup = current.get("matchup") or {}
    count = current.get("count") or {}
    offense = linescore.get("offense") or {}
    defense = linescore.get("defense") or {}
    ls_teams = linescore.get("teams") or {}
    away_ls = ls_teams.get("away") or {}
    home_ls = ls_teams.get("home") or {}
    teams = game_data.get("teams") or {}
    away = teams.get("away") or {}
    home = teams.get("home") or {}
    status = (game_data.get("status") or {}).get("detailedState", "Unknown")

    events = current.get("playEvents") or []
    pitches = [e for e in events if e.get("isPitch")]
    pitch = pitches[-1] if pitches else None
    pitch_desc = pitch_type = None
    pitch_speed = None
    if pitch:
        details = pitch.get("details") or {}
        pitch_desc = details.get("description")
        pitch_type = (details.get("type") or {}).get("description")
        pitch_speed = (pitch.get("pitchData") or {}).get("startSpeed")

    def runner(base):
        obj = offense.get(base)
        return _name(obj, "Empty") if obj else "Empty"

    recent = []
    for play in (plays.get("allPlays") or [])[-5:]:
        about = play.get("about") or {}
        result = play.get("result") or {}
        recent.append({
            "Inning": f"{str(about.get('halfInning') or '').title()} {about.get('inning') or ''}".strip(),
            "Play": result.get("description") or result.get("event") or "—",
            "Score": f"{result.get('awayScore', away_ls.get('runs', 0))}-{result.get('homeScore', home_ls.get('runs', 0))}",
        })

    inning_text = linescore.get("currentInningOrdinal") or linescore.get("currentInning") or "—"
    inning_state = linescore.get("inningState") or "—"
    return {
        "state": _state_label(status), "status": status,
        "away_team": away.get("name", "Away"), "home_team": home.get("name", "Home"),
        "away_team_id": away.get("id"), "home_team_id": home.get("id"),
        "away_runs": int(away_ls.get("runs", 0) or 0), "home_runs": int(home_ls.get("runs", 0) or 0),
        "away_hits": int(away_ls.get("hits", 0) or 0), "home_hits": int(home_ls.get("hits", 0) or 0),
        "away_errors": int(away_ls.get("errors", 0) or 0), "home_errors": int(home_ls.get("errors", 0) or 0),
        "inning": inning_text, "inning_num": _parse_inning(linescore.get("currentInning") or inning_text),
        "inning_state": inning_state,
        "balls": int(count.get("balls", linescore.get("balls", 0)) or 0),
        "strikes": int(count.get("strikes", linescore.get("strikes", 0)) or 0),
        "outs": int(count.get("outs", linescore.get("outs", 0)) or 0),
        "batter": _name(matchup.get("batter") or offense.get("batter")),
        "batter_id": (matchup.get("batter") or {}).get("id"),
        "pitcher": _name(matchup.get("pitcher") or defense.get("pitcher")),
        "pitcher_id": (matchup.get("pitcher") or {}).get("id"),
        "on_deck": _name(offense.get("onDeck")), "in_hole": _name(offense.get("inHole")),
        "first": runner("first"), "second": runner("second"), "third": runner("third"),
        "last_play": (current.get("result") or {}).get("description") or "Waiting for live play data…",
        "last_pitch_desc": pitch_desc, "last_pitch_type": pitch_type, "last_pitch_speed": pitch_speed,
        "recent": recent,
        "updated": datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0"),
    }


# Approximate MLB run expectancy to end of inning by outs and occupied bases.
_RE = {
    0: {(0,0,0):.50,(1,0,0):.90,(0,1,0):1.14,(0,0,1):1.35,(1,1,0):1.50,(1,0,1):1.78,(0,1,1):2.00,(1,1,1):2.31},
    1: {(0,0,0):.27,(1,0,0):.53,(0,1,0):.69,(0,0,1):.95,(1,1,0):.91,(1,0,1):1.18,(0,1,1):1.39,(1,1,1):1.58},
    2: {(0,0,0):.10,(1,0,0):.23,(0,1,0):.33,(0,0,1):.38,(1,1,0):.45,(1,0,1):.49,(0,1,1):.57,(1,1,1):.73},
    3: {(0,0,0):0.0,(1,0,0):0.0,(0,1,0):0.0,(0,0,1):0.0,(1,1,0):0.0,(1,0,1):0.0,(0,1,1):0.0,(1,1,1):0.0},
}


def _base_tuple(s):
    return (int(s["first"] != "Empty"), int(s["second"] != "Empty"), int(s["third"] != "Empty"))


def _current_half_re(s, batting_fullgame_mean):
    outs = min(max(int(s.get("outs", 0)), 0), 3)
    base = _RE.get(outs, _RE[2]).get(_base_tuple(s), 0.0)
    quality = clamp(float(batting_fullgame_mean) / 4.40, 0.72, 1.35)
    pitch_mult = 1.0
    pid = s.get("pitcher_id")
    if pid:
        try:
            p = pitcher_stats(int(pid))
            pitch_mult = clamp(_pitcher_run_multiplier(p)[0], 0.88, 1.12)
        except Exception:
            pass
    return base * quality * pitch_mult


def _remaining_means(s, pre_away, pre_home):
    inn = max(1, int(s.get("inning_num", 1)))
    half = str(s.get("inning_state", "")).lower()
    future_innings = max(0, 9 - inn)

    if "top" in half:
        away_rem = future_innings * pre_away / 9.0 + _current_half_re(s, pre_away)
        home_rem = (future_innings + 1) * pre_home / 9.0
    elif "bottom" in half:
        away_rem = future_innings * pre_away / 9.0
        home_rem = future_innings * pre_home / 9.0 + _current_half_re(s, pre_home)
    else:
        # Between innings / review fallback.
        away_rem = max(0.0, (9 - inn + 0.5) * pre_away / 9.0)
        home_rem = max(0.0, (9 - inn + 0.5) * pre_home / 9.0)

    return max(0.0, away_rem), max(0.0, home_rem)


def _state_key(s):
    return (
        s.get("away_runs"), s.get("home_runs"), s.get("inning_num"), s.get("inning_state"),
        s.get("outs"), s.get("balls"), s.get("strikes"), s.get("first"), s.get("second"), s.get("third"),
        s.get("pitcher_id"), s.get("batter_id"),
    )


@st.cache_data(ttl=15, show_spinner=False)
def simulate_live(away_score, home_score, away_remaining, home_remaining, inning_num, inning_state, n, seed, run_line_team, run_line, total_line):
    rng = np.random.default_rng(int(seed))
    n = int(n)
    dispersion = 4.8
    shared = rng.lognormal(mean=-0.5 * 0.11**2, sigma=0.11, size=n)

    if away_remaining > 0:
        a_lam = rng.gamma(dispersion, away_remaining / dispersion, size=n) * shared
        a_rem = rng.poisson(a_lam).astype(np.int16)
    else:
        a_rem = np.zeros(n, dtype=np.int16)
    if home_remaining > 0:
        h_lam = rng.gamma(dispersion, home_remaining / dispersion, size=n) * shared
        h_rem = rng.poisson(h_lam).astype(np.int16)
    else:
        h_rem = np.zeros(n, dtype=np.int16)

    inning_num = int(inning_num)
    half = str(inning_state).lower()

    # Bottom 9+ walk-off: home scoring stops when the winning run scores.
    if inning_num >= 9 and "bottom" in half:
        need = max(1, int(away_score) - int(home_score) + 1)
        wins_now = int(home_score) + h_rem > int(away_score)
        h_rem[wins_now] = np.minimum(h_rem[wins_now], need)

    # Top 9+: if home remains ahead after the visiting half, no bottom half is played.
    if inning_num >= 9 and "top" in half:
        after_away = int(away_score) + a_rem
        skip_bottom = int(home_score) > after_away
        h_rem[skip_bottom] = 0

    af = int(away_score) + a_rem
    hf = int(home_score) + h_rem

    tied = af == hf
    if np.any(tied):
        idx = np.flatnonzero(tied)
        hp = home_remaining / max(home_remaining + away_remaining, 1e-6)
        hp = clamp(hp, 0.45, 0.58)
        home_extra = rng.random(len(idx)) < hp
        hf[idx[home_extra]] += 1
        af[idx[~home_extra]] += 1

    p_away = float(np.mean(af > hf))
    p_home = 1.0 - p_away
    totals = af + hf
    p_over = float(np.mean(totals > float(total_line) + 1e-9))
    p_under = float(np.mean(totals < float(total_line) - 1e-9))
    p_push_total = float(np.mean(np.abs(totals.astype(float) - float(total_line)) <= 1e-9))

    margin = (hf - af) if run_line_team == "home" else (af - hf)
    settle = margin + float(run_line)
    p_cover = float(np.mean(settle > 1e-9))
    p_push_rl = float(np.mean(np.abs(settle) <= 1e-9))

    return {
        "p_away": p_away, "p_home": p_home,
        "p_over": p_over, "p_under": p_under, "p_push_total": p_push_total,
        "p_cover": p_cover, "p_push_rl": p_push_rl,
        "away_final": float(np.mean(af)), "home_final": float(np.mean(hf)),
        "expected_total": float(np.mean(totals)),
        "median_total": int(np.median(totals)),
        "n": n, "seed": int(seed),
    }


def _inject_css():
    st.markdown(LIVE_CSS, unsafe_allow_html=True)


def _scoreboard(s):
    state = s["state"]
    status_html = '<span class="lv-livepill"><span class="lv-dot"></span> LIVE</span>' if state == "LIVE" else f'<span class="lv-pill">{state}</span>'
    inning = f"{s['inning_state']} {s['inning']}".strip()
    st.markdown(f'''
    <div class="lv-scoreboard">
      <div class="lv-topline"><div>{status_html}</div><div class="lv-pill">{inning} • Updated {s['updated']}</div></div>
      <div class="lv-teamrow"><div class="lv-team"><img class="lv-logo" src="{_logo(s['away_team_id'])}"><div><div class="lv-teamname">{s['away_team']}</div><div class="lv-sub">R/H/E • {s['away_runs']}/{s['away_hits']}/{s['away_errors']}</div></div></div><div class="lv-score">{s['away_runs']}</div></div>
      <div class="lv-teamrow"><div class="lv-team"><img class="lv-logo" src="{_logo(s['home_team_id'])}"><div><div class="lv-teamname">{s['home_team']}</div><div class="lv-sub">R/H/E • {s['home_runs']}/{s['home_hits']}/{s['home_errors']}</div></div></div><div class="lv-score">{s['home_runs']}</div></div>
    </div>
    ''', unsafe_allow_html=True)


def _active_layout(s):
    st.markdown(f'''
    <div class="lv-strip">
      <div class="lv-stat"><div class="lv-label">Inning</div><div class="lv-value blue">{s['inning_state']} {s['inning']}</div></div>
      <div class="lv-stat"><div class="lv-label">Outs</div><div class="lv-value">{s['outs']}</div></div>
      <div class="lv-stat"><div class="lv-label">Count</div><div class="lv-value">{s['balls']}-{s['strikes']}</div></div>
      <div class="lv-stat"><div class="lv-label">Status</div><div class="lv-value">LIVE</div></div>
    </div>
    <div class="lv-section">⚔️ Current matchup</div>
    <div class="lv-matchup">
      <div class="lv-person"><div class="lv-role">At bat</div><div class="lv-name">{s['batter']}</div><div class="lv-detail">On deck: {s['on_deck']}<br>In the hole: {s['in_hole']}</div></div>
      <div class="lv-person"><div class="lv-role">On the mound</div><div class="lv-name">{s['pitcher']}</div><div class="lv-detail">Last pitch: {s['last_pitch_desc'] or '—'}{(' • ' + str(s['last_pitch_type'])) if s['last_pitch_type'] else ''}{(' • ' + format(float(s['last_pitch_speed']), '.1f') + ' mph') if s['last_pitch_speed'] is not None else ''}</div></div>
    </div>
    <div class="lv-section">◇ Base state</div>
    <div class="lv-basegrid">
      <div class="lv-base {'on' if s['first'] != 'Empty' else ''}"><div class="lv-baseicon">◆ 1B</div><div class="lv-basename">{s['first']}</div></div>
      <div class="lv-base {'on' if s['second'] != 'Empty' else ''}"><div class="lv-baseicon">◆ 2B</div><div class="lv-basename">{s['second']}</div></div>
      <div class="lv-base {'on' if s['third'] != 'Empty' else ''}"><div class="lv-baseicon">◆ 3B</div><div class="lv-basename">{s['third']}</div></div>
    </div>
    <div class="lv-section">📝 Current play</div><div class="lv-play">{s['last_play']}</div>
    ''', unsafe_allow_html=True)
    if s.get("recent"):
        with st.expander("📜 Last 5 plays", expanded=False):
            st.dataframe(pd.DataFrame(s["recent"]), use_container_width=True, hide_index=True)


def _final_layout(s):
    winner = s["away_team"] if s["away_runs"] > s["home_runs"] else s["home_team"]
    st.markdown(f'''
    <div class="lv-strip">
      <div class="lv-stat"><div class="lv-label">Winner</div><div class="lv-value blue">{winner}</div></div>
      <div class="lv-stat"><div class="lv-label">Margin</div><div class="lv-value">{abs(s['away_runs']-s['home_runs'])}</div></div>
      <div class="lv-stat"><div class="lv-label">Total runs</div><div class="lv-value">{s['away_runs']+s['home_runs']}</div></div>
      <div class="lv-stat"><div class="lv-label">Status</div><div class="lv-value">FINAL</div></div>
    </div><div class="lv-section">🏁 Final play</div><div class="lv-play">{s['last_play']}</div>
    ''', unsafe_allow_html=True)
    if s.get("recent"):
        with st.expander("📜 Last 5 plays", expanded=False):
            st.dataframe(pd.DataFrame(s["recent"]), use_container_width=True, hide_index=True)


def _live_model_panel(s, game):
    if s["state"] != "LIVE":
        return
    st.markdown('<div class="lv-market-head"><div class="lv-market-title">🧠 V19 Live Betting Engine</div><div class="lv-market-sub">Uses the current score + inning + outs + occupied bases + current pitcher, then simulates the rest of the game. Sportsbook prices are not model inputs.</div></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        run_team = st.selectbox("Run-line team", [s["home_team"], s["away_team"]], key=f"v19_rl_team_{game['game_pk']}")
    with c2:
        default_rl = -1.5 if (run_team == s["home_team"] and s["home_runs"] > s["away_runs"]) or (run_team == s["away_team"] and s["away_runs"] > s["home_runs"]) else 1.5
        rl = st.selectbox("Live run line", [-3.5,-2.5,-1.5,-1.0,1.0,1.5,2.5,3.5], index=[-3.5,-2.5,-1.5,-1.0,1.0,1.5,2.5,3.5].index(default_rl), key=f"v19_rl_{game['game_pk']}_{run_team}")
    with c3:
        current_total = s["away_runs"] + s["home_runs"]
        total_line = st.number_input("Live game total", min_value=float(current_total)+0.5, max_value=float(current_total)+20.5, value=float(current_total)+2.5, step=0.5, key=f"v19_total_{game['game_pk']}")

    depth = st.selectbox("Live simulation depth", ["Quick — 100K", "Standard — 500K", "Deep — 1M"], index=1, key=f"v19_depth_{game['game_pk']}")
    n = {"Quick — 100K":100_000,"Standard — 500K":500_000,"Deep — 1M":1_000_000}[depth]

    if st.button("🔥 RUN V19 LIVE MODEL", use_container_width=True, type="primary", key=f"v19_run_{game['game_pk']}"):
        with st.spinner("Rebuilding from the live base-out state..."):
            try:
                model = build_game_model(int(game["game_pk"]), int(game["away_team_id"]), int(game["home_team_id"]), game.get("away_pitcher_id"), game.get("home_pitcher_id"), game.get("venue_name", "Unknown"))
                pre_a = float(model["away_model"]["expected_runs"])
                pre_h = float(model["home_model"]["expected_runs"])
                a_rem, h_rem = _remaining_means(s, pre_a, pre_h)
                side = "home" if run_team == s["home_team"] else "away"
                seed = _stable_seed(int(game["game_pk"]), 1900 + int(s["inning_num"])*31 + int(s["outs"])*7 + int(s["away_runs"])*3 + int(s["home_runs"])*5)
                sim = simulate_live(s["away_runs"], s["home_runs"], a_rem, h_rem, s["inning_num"], s["inning_state"], n, seed, side, float(rl), float(total_line))
                st.session_state[f"v19_result_{game['game_pk']}"] = {"sim":sim,"state_key":_state_key(s),"a_rem":a_rem,"h_rem":h_rem,"run_team":run_team,"rl":float(rl),"total_line":float(total_line)}
            except Exception as exc:
                st.error(f"V19 could not complete this live state: {exc}")

    saved = st.session_state.get(f"v19_result_{game['game_pk']}")
    if not saved:
        return
    sim = saved["sim"]
    stale = saved.get("state_key") != _state_key(s)
    st.markdown('<div class="lv-stale">⚠️ The game state changed after this model run. Re-run V19 before using these probabilities.</div>' if stale else '<div class="lv-fresh">● LIVE MODEL SYNCED TO CURRENT STATE</div>', unsafe_allow_html=True)

    home_p = sim["p_home"]
    away_p = sim["p_away"]
    rl_settled = max(1e-9, 1.0 - sim["p_push_rl"])
    total_settled = max(1e-9, 1.0 - sim["p_push_total"])
    cover_cond = sim["p_cover"] / rl_settled
    over_cond = sim["p_over"] / total_settled
    under_cond = sim["p_under"] / total_settled
    st.markdown(f'''
    <div class="lv-projgrid">
      <div class="lv-proj big"><div class="lv-label">Projected final</div><div class="lv-projnum cyan">{s['away_team']} {sim['away_final']:.1f} — {sim['home_final']:.1f} {s['home_team']}</div><div class="lv-projsmall">Expected final total {sim['expected_total']:.2f}</div></div>
      <div class="lv-proj"><div class="lv-label">{s['home_team']} ML</div><div class="lv-projnum">{home_p*100:.1f}%</div><div class="lv-projsmall">Fair {odds(home_p)}</div></div>
      <div class="lv-proj"><div class="lv-label">{s['away_team']} ML</div><div class="lv-projnum">{away_p*100:.1f}%</div><div class="lv-projsmall">Fair {odds(away_p)}</div></div>
      <div class="lv-proj"><div class="lv-label">{saved['run_team']} {saved['rl']:+g}</div><div class="lv-projnum good">{sim['p_cover']*100:.1f}%</div><div class="lv-projsmall">Push {sim['p_push_rl']*100:.1f}% • Fair {odds(cover_cond)}</div></div>
      <div class="lv-proj"><div class="lv-label">Over {saved['total_line']:g}</div><div class="lv-projnum">{sim['p_over']*100:.1f}%</div><div class="lv-projsmall">Fair {odds(over_cond)}</div></div>
      <div class="lv-proj"><div class="lv-label">Under {saved['total_line']:g}</div><div class="lv-projnum">{sim['p_under']*100:.1f}%</div><div class="lv-projsmall">Push {sim['p_push_total']*100:.1f}% • Fair {odds(under_cond)}</div></div>
    </div>
    ''', unsafe_allow_html=True)
    st.caption(f"V19 • {sim['n']:,} simulations • seed {sim['seed']} • remaining xRuns {s['away_team']} {saved['a_rem']:.2f}, {s['home_team']} {saved['h_rem']:.2f}. Prototype live model; use backtesting before trusting it with real money.")


def _render_selected(game, section_header):
    try:
        feed = fetch_live_feed(int(game["game_pk"]))
        s = _state(feed)
    except Exception as exc:
        st.error(f"MLB live feed could not be loaded: {exc}")
        return
    _scoreboard(s)
    if s["state"] == "LIVE":
        _active_layout(s)
        _live_model_panel(s, game)
    elif s["state"] == "FINAL":
        _final_layout(s)
    else:
        st.info("⏳ Pregame. The page will switch to the live dashboard as soon as MLB marks the game in progress.")


def _body(verified, section_header):
    game_date = str(verified.iloc[0].get("game_date", datetime.now(ET).date().isoformat()))
    allowed = tuple(sorted(pd.to_numeric(verified["game_pk"], errors="coerce").dropna().astype(int).tolist()))
    try:
        fresh = fetch_live_slate(game_date, allowed)
    except Exception:
        fresh = {}

    rows = []
    for _, row in verified.iterrows():
        d = row.to_dict()
        pk = int(d["game_pk"])
        if pk in fresh:
            d.update(fresh[pk])
        rows.append(d)
    rows.sort(key=lambda r: (_priority(r.get("status")), _time_sort(r.get("first_pitch_et")), str(r.get("away_team", ""))))

    live = [r for r in rows if _state_label(r.get("status")) == "LIVE"]
    delayed = [r for r in rows if _state_label(r.get("status")) == "DELAYED"]
    upcoming = [r for r in rows if _state_label(r.get("status")) == "PREGAME"]
    finals = [r for r in rows if _state_label(r.get("status")) == "FINAL"]
    st.caption(f"📡 {len(live)} LIVE • ⚠️ {len(delayed)} delayed • ⏳ {len(upcoming)} upcoming • 🏁 {len(finals)} final")

    if live:
        chips = ''.join([f'<div class="lv-gamechip"><b>{r["away_team"]} {int(r.get("away_runs",0) or 0)} — {int(r.get("home_runs",0) or 0)} {r["home_team"]}</b> • {str(r.get("inning_state","")).strip()} {str(r.get("inning","")).strip()}</div>' for r in live])
        st.markdown(f'<div class="lv-section">🔴 Live right now</div><div class="lv-live-list">{chips}</div>', unsafe_allow_html=True)

    labels=[]
    for r in rows:
        state=_state_label(r.get("status")); icon={"LIVE":"🔴","DELAYED":"⚠️","PREGAME":"⏳","FINAL":"🏁"}.get(state,"⚾")
        score=f" • {int(r.get('away_runs',0) or 0)}-{int(r.get('home_runs',0) or 0)}" if state in {"LIVE","FINAL"} else ""
        labels.append(f"{icon} {state} • {r['away_team']} @ {r['home_team']}{score} • {r.get('first_pitch_et','TBD')} ET")
    choice=st.selectbox("Choose game",labels,key="v19_live_game")
    game=rows[labels.index(choice)]
    selected_state=_state_label(game.get("status"))

    if st.button("🔄 REFRESH LIVE CENTER",use_container_width=True,key="v19_refresh"):
        fetch_live_feed.clear(); fetch_live_slate.clear(); st.rerun()

    fragment=getattr(st,"fragment",None)
    if callable(fragment) and selected_state=="LIVE":
        @fragment(run_every="10s")
        def live_panel():
            _render_selected(game,section_header)
        live_panel()
    else:
        _render_selected(game,section_header)


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    _inject_css()
    verified=_verified_df(games_df)
    st.markdown('<div class="lv-wrap"><div class="lv-kicker">KYRE SPORTS AI • REAL-TIME MLB</div></div>',unsafe_allow_html=True)
    section_header("MLB Live Intelligence — V19","Premium live game center + state-aware moneyline, run-line and total simulation.")
    if verified.empty:
        st.info("No verified games are available on this selected slate.")
        return
    _body(verified,section_header)
