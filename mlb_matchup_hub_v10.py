"""MLB Daily Matchup Hub V1.0

Game-first, player-first browsing layer inspired by modern prop research UIs.
Uses official MLB Stats API for today's verified matchups, rosters, season stats
and game logs. Existing deep projection engines remain isolated and untouched.
"""
from __future__ import annotations

from datetime import datetime
import html
import math
import re

import pandas as pd
import requests
import streamlit as st

from engine import MLB_API, ET

VERSION = "MLB Matchup Hub V1.0"


def _esc(x):
    return html.escape(str(x or ""))


def _num(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _date_str(row):
    raw = str(row.get("game_date") or "")[:10]
    return raw or datetime.now(ET).date().isoformat()


@st.cache_data(ttl=45, show_spinner=False)
def _json(url, params=None):
    r = requests.get(url, params=params or {}, timeout=18, headers={"User-Agent":"KyreSportsAI/MatchupHub1.0","Accept":"application/json"})
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=45, show_spinner=False)
def _boxscore(game_pk):
    try:
        return _json(f"{MLB_API}/game/{int(game_pk)}/boxscore")
    except Exception:
        return {}


@st.cache_data(ttl=180, show_spinner=False)
def _active_roster(team_id, day):
    try:
        data = _json(f"{MLB_API}/teams/{int(team_id)}/roster", {"rosterType":"active", "date":str(day)})
    except Exception:
        return []
    out = []
    for item in data.get("roster", []) or []:
        person = item.get("person") or {}
        try: pid = int(person.get("id"))
        except Exception: continue
        out.append({"id":pid, "name":str(person.get("fullName") or f"Player {pid}"), "position":str((item.get("position") or {}).get("abbreviation") or "")})
    return out


def _official_hitters(game_pk, side):
    box = _boxscore(game_pk)
    team = ((box.get("teams") or {}).get(side) or {})
    players = team.get("players") or {}
    order = []
    for _, p in players.items():
        if not isinstance(p, dict):
            continue
        bo = p.get("battingOrder")
        if bo in (None, "", 0, "0"):
            continue
        person = p.get("person") or {}
        try: pid = int(person.get("id"))
        except Exception: continue
        try: slot = int(str(bo)) // 100
        except Exception: slot = 99
        pos = str((p.get("position") or {}).get("abbreviation") or "")
        order.append({"id":pid, "name":str(person.get("fullName") or f"Player {pid}"), "position":pos, "slot":slot})
    order.sort(key=lambda x: (x["slot"], x["name"]))
    return order


@st.cache_data(ttl=300, show_spinner=False)
def _person(player_id):
    try:
        d = _json(f"{MLB_API}/people/{int(player_id)}", {"hydrate":"currentTeam"})
        return (d.get("people") or [{}])[0]
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _season_hitting(player_id, season):
    try:
        d = _json(f"{MLB_API}/people/{int(player_id)}/stats", {"stats":"season", "group":"hitting", "season":int(season)})
        splits = (((d.get("stats") or [{}])[0]).get("splits") or [])
        return (splits[0].get("stat") or {}) if splits else {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _game_logs(player_id, season):
    try:
        d = _json(f"{MLB_API}/people/{int(player_id)}/stats", {"stats":"gameLog", "group":"hitting", "season":int(season)})
        blocks = d.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
    except Exception:
        return []
    rows = []
    for s in splits:
        stat = s.get("stat") or {}
        opp = s.get("opponent") or {}
        rows.append({
            "date":str(s.get("date") or ""),
            "opp":str(opp.get("name") or "OPP"),
            "H":int(_num(stat.get("hits"))),
            "HR":int(_num(stat.get("homeRuns"))),
            "TB":int(_num(stat.get("totalBases"))),
            "RBI":int(_num(stat.get("rbi"))),
            "R":int(_num(stat.get("runs"))),
            "AB":int(_num(stat.get("atBats"))),
        })
    rows.sort(key=lambda x: x["date"], reverse=True)
    for r in rows:
        r["H+R+RBI"] = r["H"] + r["R"] + r["RBI"]
    return rows


def _logo(team_id):
    try:
        return f"https://www.mlbstatic.com/team-logos/{int(team_id)}.svg"
    except Exception:
        return ""


def _css():
    st.markdown("""
    <style>
      .mh-hero{border:1px solid #27415f;border-radius:26px;padding:22px 24px;background:linear-gradient(135deg,#0d1a31,#09111f);margin:8px 0 18px}
      .mh-eyebrow{font-size:12px;letter-spacing:2px;font-weight:800;color:#55d9ff;text-transform:uppercase}
      .mh-title{font-size:34px;line-height:1.05;font-weight:900;color:#f7f9ff;margin:8px 0 8px}.mh-sub{color:#9fb0c7;font-size:15px}
      .mh-game{border:1px solid #284562;border-radius:22px;background:#0d1a2e;padding:18px 20px;margin:8px 0 16px}.mh-teamrow{display:grid;grid-template-columns:1fr 52px 1fr;align-items:center;gap:12px}
      .mh-team{text-align:center;color:white;font-size:20px;font-weight:850}.mh-team img{height:64px;max-width:84px;display:block;margin:0 auto 8px}.mh-at{text-align:center;color:#65829f;font-weight:900;font-size:22px}.mh-meta{text-align:center;color:#8298b0;font-size:12px;margin-top:12px}
      .mh-player{border:1px solid #304b68;border-radius:24px;padding:18px;background:#0a1423;margin:12px 0}.mh-name{font-size:28px;font-weight:900;color:#fff}.mh-small{font-size:13px;color:#8ea4bd}
      .mh-season{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px}.mh-stat{background:#121f31;border:1px solid #2a4059;border-radius:14px;padding:10px;text-align:center}.mh-stat b{display:block;color:#f6f8ff;font-size:20px}.mh-stat span{color:#8299b4;font-size:10px;text-transform:uppercase;letter-spacing:1px}
      .mh-bars{display:flex;align-items:flex-end;gap:10px;height:230px;padding:18px 6px 4px;overflow-x:auto}.mh-col{min-width:72px;text-align:center;color:#d8e4f4}.mh-barwrap{height:150px;display:flex;align-items:flex-end;justify-content:center}.mh-bar{width:46px;border-radius:8px 8px 3px 3px;background:linear-gradient(#20bd55,#0b7f32);display:flex;align-items:flex-start;justify-content:center;color:white;font-weight:900;padding-top:5px;min-height:4px}.mh-zero{background:#273444;color:#aebdce}.mh-opp{font-size:11px;font-weight:800;margin-top:6px}.mh-date{font-size:10px;color:#7389a2}
      @media(max-width:700px){.mh-title{font-size:28px}.mh-season{grid-template-columns:repeat(3,1fr)}.mh-team{font-size:17px}.mh-team img{height:52px}}
    </style>
    """, unsafe_allow_html=True)


def _game_label(row):
    return f"{row.get('away_team')} @ {row.get('home_team')} • {row.get('first_pitch_et','TBD')}"


def _hitters_for_game(row):
    pk = int(row.get("game_pk"))
    day = _date_str(row)
    out = []
    for side, tid, tname in (("away", row.get("away_team_id"), row.get("away_team")), ("home", row.get("home_team_id"), row.get("home_team"))):
        official = _official_hitters(pk, side)
        if official:
            pool, source = official, "CONFIRMED LINEUP"
        else:
            pool, source = _active_roster(tid, day), "ACTIVE ROSTER"
        for p in pool:
            if str(p.get("position") or "").upper() == "P":
                continue
            out.append({**p, "team":tname, "team_id":tid, "side":side, "source":source})
    return out


def _recent_chart(logs, metric):
    recent = list(reversed(logs[:10]))
    if not recent:
        st.info("No recent MLB game-log rows are available for this player yet.")
        return
    vals = [int(r.get(metric,0)) for r in recent]
    maxv = max(max(vals), 1)
    cols = []
    for r, v in zip(recent, vals):
        height = max(4, int(138 * v / maxv)) if v else 4
        cls = "mh-bar mh-zero" if v == 0 else "mh-bar"
        short_opp = re.sub(r"[^A-Za-z0-9 ]", "", r.get("opp","OPP")).split()
        short_opp = " ".join(short_opp[-2:]) if short_opp else "OPP"
        d = str(r.get("date") or "")
        d = d[5:].replace("-","/") if len(d)>=10 else d
        cols.append(f'<div class="mh-col"><div class="mh-barwrap"><div class="{cls}" style="height:{height}px">{v}</div></div><div class="mh-opp">vs {_esc(short_opp)}</div><div class="mh-date">{_esc(d)}</div></div>')
    st.markdown('<div class="mh-bars">'+''.join(cols)+'</div>', unsafe_allow_html=True)


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    if games_df is None or games_df.empty:
        st.info("No verified MLB games are available for the selected date.")
        return

    day = _date_str(games_df.iloc[0])
    st.markdown('<div class="mh-hero"><div class="mh-eyebrow">KYRE SPORTS AI • DAILY PLAYER MATCHUPS</div><div class="mh-title">⚾ MLB Matchup Explorer</div><div class="mh-sub">Tap a matchup, choose a hitter, then move between Hits, Home Runs, Total Bases, RBIs, Runs and H+R+RBI without leaving the page.</div></div>', unsafe_allow_html=True)

    labels = [_game_label(r) for _, r in games_df.iterrows()]
    idx = st.selectbox("TODAY'S MATCHUPS", range(len(labels)), format_func=lambda i: labels[i], key="mh_game")
    row = games_df.iloc[int(idx)]
    st.markdown(f'<div class="mh-game"><div class="mh-teamrow"><div class="mh-team"><img src="{_logo(row.get("away_team_id"))}">{_esc(row.get("away_team"))}</div><div class="mh-at">@</div><div class="mh-team"><img src="{_logo(row.get("home_team_id"))}">{_esc(row.get("home_team"))}</div></div><div class="mh-meta">{_esc(row.get("first_pitch_et"))} ET • {_esc(row.get("venue_name"))} • {_esc(row.get("status"))}<br>{_esc(row.get("away_pitcher"))} vs {_esc(row.get("home_pitcher"))}</div></div>', unsafe_allow_html=True)

    players = _hitters_for_game(row)
    if not players:
        st.warning("No eligible hitters were returned for this matchup yet.")
        return
    pidx = st.selectbox("PLAYER", range(len(players)), format_func=lambda i: f"{players[i]['name']} • {players[i]['team']} • {players[i].get('source','')}", key="mh_player")
    p = players[int(pidx)]
    season = pd.to_datetime(day).year
    stat = _season_hitting(p["id"], season)
    logs = _game_logs(p["id"], season)

    games = int(_num(stat.get("gamesPlayed")))
    avg = stat.get("avg") or ".000"
    hr = int(_num(stat.get("homeRuns")))
    rbi = int(_num(stat.get("rbi")))
    ops = stat.get("ops") or ".000"
    st.markdown(f'<div class="mh-player"><div class="mh-small">{_esc(p.get("team"))} • {_esc(p.get("position"))} • {_esc(p.get("source"))}</div><div class="mh-name">{_esc(p.get("name"))}</div><div class="mh-season"><div class="mh-stat"><span>Games</span><b>{games}</b></div><div class="mh-stat"><span>AVG</span><b>{_esc(avg)}</b></div><div class="mh-stat"><span>HR</span><b>{hr}</b></div><div class="mh-stat"><span>RBI</span><b>{rbi}</b></div><div class="mh-stat"><span>OPS</span><b>{_esc(ops)}</b></div></div></div>', unsafe_allow_html=True)

    tabs = st.tabs(["Hits", "Home Runs", "Total Bases", "RBIs", "Runs", "H+R+RBI", "Game Log"])
    metrics = ["H","HR","TB","RBI","R","H+R+RBI"]
    titles = ["Hits","Home Runs","Total Bases","RBIs","Runs","H+R+RBI"]
    season_fields = ["avg","homeRuns","totalBases","rbi","runs",None]
    for tab, metric, title, sf in zip(tabs[:6], metrics, titles, season_fields):
        with tab:
            if metric == "H":
                st.caption(f"2026 season AVG: {avg}")
            elif sf:
                st.caption(f"2026 season {title}: {stat.get(sf,'—')}")
            elif logs:
                st.caption(f"Recent 10 H+R+RBI average: {sum(r['H+R+RBI'] for r in logs[:10])/len(logs[:10]):.2f}")
            _recent_chart(logs, metric)
            if metric in ("H","HR","H+R+RBI"):
                engine = {"H":"1+ Hit V13.3", "HR":"Home Run V1.1", "H+R+RBI":"H+R+RBI V1.0.1"}[metric]
                st.info(f"Deep projection engine available: {engine}. V1.1 of this Matchup Explorer will surface its projection card directly inside this tab.")
    with tabs[6]:
        if not logs:
            st.info("No game log available.")
        else:
            df = pd.DataFrame(logs[:20])[["date","opp","AB","H","HR","TB","RBI","R","H+R+RBI"]]
            st.dataframe(df, hide_index=True, use_container_width=True)

    st.caption(f"{VERSION} • Official MLB Stats API • selected slate {day} • existing deep market engines remain isolated")
