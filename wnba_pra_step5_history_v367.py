"""WNBA PRA V3.6.7 — Step-5 player-vs-opponent matchup history layer.

Presentation-only wrapper over V3.6.6. Reuses the existing cached ESPN WNBA
season schedule and per-game summary parser already used by the PRA player-pool
fallback. For each Step-5 Top-5 player it summarizes verified current-season
appearances for the player's current team against today's opponent.

Displayed history never writes into projections or model features. Missing
history is shown explicitly, and 1-2 game samples are labeled small.

No PRA projection, availability, minutes/usage, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import math

import pandas as pd
import streamlit as st

import wnba_pra_step5_defense_v366 as prior
import wnba_pra_step5_identity_v363 as cards
import wnba_players_v25 as players

MODEL_VERSION = "PRA V3.6.7 • STEP-5 MATCHUP HISTORY • MODEL PRESERVED"

_HISTORY_MEMO = {}


def _num(value, default=float("nan")):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value)
    return "N/A" if not math.isfinite(x) else f"{x:.{digits}f}"


def _int_id(value):
    try:
        return int(float(value))
    except Exception:
        return 0


def _board_history_map(day, picks, defenses):
    """Return display-only current-season H2H summaries for the Step-5 board."""
    day_key = prior._day_key(day)
    signature = tuple(
        (str(p.get("name") or ""), str(p.get("team") or ""), str(p.get("opponent") or ""))
        for p in (picks or [])
    )
    memo_key = (day_key, signature)
    if memo_key in _HISTORY_MEMO:
        return _HISTORY_MEMO[memo_key]

    selected = pd.to_datetime(day_key, errors="coerce")
    season = int(selected.year) if pd.notna(selected) else pd.Timestamp.now().year
    try:
        schedule = players._espn_season_schedule(season)
    except Exception:
        schedule = pd.DataFrame()

    if schedule is not None and not schedule.empty and pd.notna(selected):
        dates = pd.to_datetime(schedule.get("game_date"), errors="coerce")
        schedule = schedule.loc[dates < selected].copy()
        schedule["_DATE"] = dates.loc[schedule.index]
    else:
        schedule = pd.DataFrame()

    requirements = []
    jobs = {}
    for p in picks or []:
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        team_obj = defenses.get(prior._norm(team), {}) if isinstance(defenses, dict) else {}
        opp_obj = defenses.get(prior._norm(opponent), {}) if isinstance(defenses, dict) else {}
        team_id = _int_id(team_obj.get("TEAM_ID"))
        opp_id = _int_id(opp_obj.get("TEAM_ID"))

        pair = pd.DataFrame()
        if team_id and opp_id and schedule is not None and not schedule.empty:
            away = pd.to_numeric(schedule.get("away_team_id"), errors="coerce")
            home = pd.to_numeric(schedule.get("home_team_id"), errors="coerce")
            mask = ((away == team_id) & (home == opp_id)) | ((away == opp_id) & (home == team_id))
            pair = schedule.loc[mask].copy().sort_values("_DATE", ascending=False).head(8)

        game_rows = []
        if pair is not None and not pair.empty:
            for _, game in pair.iterrows():
                gid = str(game.get("game_id") or "")
                gdate = str(game.get("game_date") or "")
                if gid:
                    game_rows.append((gid, gdate))
                    jobs[gid] = gdate

        requirements.append({
            "key": cards._player_key(name),
            "name": name,
            "team": team,
            "opponent": opponent,
            "team_id": team_id,
            "opp_id": opp_id,
            "games": game_rows,
            "team_meetings": len(game_rows),
        })

    summaries = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(jobs)))) as pool:
            futures = {
                pool.submit(players._espn_game_summary, gid, gdate): gid
                for gid, gdate in jobs.items()
            }
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    frame = future.result()
                    summaries[gid] = frame if frame is not None else pd.DataFrame()
                except Exception:
                    summaries[gid] = pd.DataFrame()

    result = {}
    for req in requirements:
        rows = []
        player_key = cards._player_key(req["name"])
        for gid, _gdate in req["games"]:
            frame = summaries.get(gid, pd.DataFrame())
            if frame is None or frame.empty:
                continue
            part = frame.copy()
            if req["team_id"] and "TEAM_ID" in part.columns:
                team_ids = pd.to_numeric(part["TEAM_ID"], errors="coerce")
                part = part.loc[team_ids == req["team_id"]].copy()
            if part.empty or "PLAYER_NAME" not in part.columns:
                continue
            name_mask = part["PLAYER_NAME"].map(cards._player_key).eq(player_key)
            part = part.loc[name_mask]
            if part.empty:
                continue
            row = part.iloc[0]
            mins = _num(row.get("MIN"))
            pts = _num(row.get("PTS"))
            reb = _num(row.get("REB"))
            ast = _num(row.get("AST"))
            if not all(math.isfinite(x) for x in (pts, reb, ast)):
                continue
            rows.append({
                "date": row.get("GAME_DATE"),
                "min": mins,
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "pra": pts + reb + ast,
            })

        if rows:
            def avg(field):
                vals = [r[field] for r in rows if math.isfinite(_num(r[field]))]
                return sum(vals) / len(vals) if vals else float("nan")

            result[req["key"]] = {
                "games": len(rows),
                "team_meetings": req["team_meetings"],
                "avg_min": avg("min"),
                "avg_pts": avg("pts"),
                "avg_reb": avg("reb"),
                "avg_ast": avg("ast"),
                "avg_pra": avg("pra"),
                "recent_pra": [r["pra"] for r in rows[:5]],
                "season": season,
                "source": "ESPN WNBA cached game summaries",
                "scope": "current-team current-season meetings",
            }
        else:
            result[req["key"]] = {
                "games": 0,
                "team_meetings": req["team_meetings"],
                "season": season,
                "source": "ESPN WNBA cached game summaries",
                "scope": "current-team current-season meetings",
            }

    _HISTORY_MEMO[memo_key] = result
    return result


def _history_box(obj: dict, opponent: str) -> str:
    obj = obj if isinstance(obj, dict) else {}
    games = int(_num(obj.get("games"), 0) or 0)
    team_meetings = int(_num(obj.get("team_meetings"), 0) or 0)
    season = int(_num(obj.get("season"), 0) or 0)

    if games <= 0:
        return (
            '<div style="border:1px solid #5a476f;background:#141126;border-radius:10px;'
            'padding:8px;margin-top:8px">'
            f'<b style="color:#eadcff;font-size:.5rem">📚 VS {escape(opponent)} • MATCHUP HISTORY</b>'
            '<div style="color:#a899ba;font-size:.47rem;margin-top:6px;line-height:1.45">'
            'No current-season player matchup history available.'
            f' Team meetings found: {team_meetings}.</div>'
            '<div style="font-size:.34rem;color:#756684;margin-top:5px">'
            'Current-team meetings only • missing history never affects ranking or projection'</n            '</div></div>'
        )

    def metric(label, value):
        return (
            '<div style="border:1px solid #3a3150;border-radius:8px;padding:6px 7px;'
            'background:#0d1020;min-width:0">'
            f'<span style="display:block;color:#8f7aa8;font-size:.36rem;font-weight:900;'
            f'letter-spacing:.04em">{escape(label)}</span>'
            f'<b style="display:block;color:#f4edff;font-size:.58rem;margin-top:2px">{escape(value)}</b>'
            '</div>'
        )

    recent = obj.get("recent_pra") or []
    recent_text = " • ".join(_fmt(x, 0) for x in recent) if recent else "N/A"
    warning = (
        '<span style="color:#ffe083;font-weight:900">⚠️ Small H2H sample</span>'
        if games <= 2 else
        '<span style="color:#b59aca;font-weight:900">Recent matchup sample</span>'
    )

    return (
        '<div style="border:1px solid #5a476f;background:#141126;border-radius:10px;'
        'padding:8px;margin-top:8px">'
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px">'
        f'<b style="color:#eadcff;font-size:.5rem">📚 VS {escape(opponent)} • MATCHUP HISTORY</b>'
        f'<span style="font-size:.4rem">{warning}</span>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin-top:6px">'
        f'{metric("PLAYER GP", str(games))}'
        f'{metric("AVG MIN", _fmt(obj.get("avg_min"),1))}'
        f'{metric("AVG PRA", _fmt(obj.get("avg_pra"),1))}'
        f'{metric("AVG PTS", _fmt(obj.get("avg_pts"),1))}'
        f'{metric("AVG REB", _fmt(obj.get("avg_reb"),1))}'
        f'{metric("AVG AST", _fmt(obj.get("avg_ast"),1))}'
        '</div>'
        '<div style="display:flex;justify-content:space-between;gap:6px;margin-top:6px;align-items:flex-start">'
        f'<span style="font-size:.4rem;color:#aa96bd"><b>Recent PRA:</b> {escape(recent_text)}</span>'
        f'<span style="font-size:.39rem;color:#8f7aa8;white-space:nowrap">{season} TEAM MTGS {team_meetings}</span>'
        '</div>'
        '<div style="font-size:.34rem;color:#756684;margin-top:4px;line-height:1.35">'
        'Existing cached ESPN WNBA game summaries • current-team/current-season appearances • display only'
        '</div></div>'
    )


def _render_top5_v367(picks):
    """Inherited Step-5 order/math + identity + defense + display-only H2H."""
    if not picks:
        st.markdown('<div class="w2-empty">No eligible Step 5 projections are available.</div>', unsafe_allow_html=True)
        return

    day = st.session_state.get("wnba_pra_v2_date")
    player_ids, teams = cards._identity_maps(day)
    defenses = prior._opponent_context_map(day)
    histories = _board_history_map(day, picks, defenses)
    rendered = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = "STARTER" if p["starter"] else p["status"] if p["status"] != "NO DESIGNATION" else "ACTIVE"
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        pid = player_ids.get(cards._player_key(name))
        tm = cards._team_meta(teams, team)
        om = cards._team_meta(teams, opponent)
        defense = defenses.get(prior._norm(opponent), {})
        history = histories.get(cards._player_key(name), {})

        headshot = cards._headshot_html(pid, name)
        team_logo = cards._logo_html(tm, team, f"{team} logo")
        opp_logo = cards._logo_html(om, opponent, f"{opponent} logo")
        defense_html = prior._defense_box(defense, opponent)
        history_html = _history_box(history, opponent)

        rendered.append(
            f'<div class="w28-pick{first}">'
            f'<div class="w28-rank">#{i} STEP-5 PRA • 🖼️ IDENTITY • 🛡️ DEFENSE • 📚 HISTORY</div>'
            '<div style="display:flex;align-items:center;gap:10px;margin-top:7px;min-width:0">'
            f'{headshot}'
            '<div style="min-width:0;flex:1">'
            f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
            '<div style="display:flex;align-items:center;gap:6px;margin-top:6px;min-width:0">'
            f'{team_logo}<span style="color:#8da3b8;font-size:.5rem;font-weight:800">vs</span>{opp_logo}'
            '</div></div></div>'
            f'<div class="w28-meta" style="margin-top:7px">{escape(team)} vs {escape(opponent)} • {escape(status)} • {p["min"]:.1f} MIN</div>'
            f'<div class="w28-pra">{p["pra"]:.1f} <span>Projected PRA</span></div>'
            '<div class="w28-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div>'
            f'<div><span>REB</span><b>{p["r"]:.1f}</b></div>'
            f'<div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'<div><span>USG</span><b>{cards.v28._fmt(p["usg"],1)}</b></div>'
            '</div>'
            f'{defense_html}{history_html}'
            '<div style="font-size:.4rem;color:#577892;margin-top:7px;letter-spacing:.04em">'
            'ESPN WNBA PLAYER IMAGE • VERIFIED SLATE IDENTITY • DEFENSE + HISTORY DISPLAY ONLY'
            '</div></div>'
        )

    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">First adjusted ranking: current availability, projected team minutes and role/USG changes are active. Player identity, opponent defensive context and matchup history are presentation-only. They do not alter these projections, qualification or ranking.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div></div>',
        unsafe_allow_html=True,
    )


def install():
    """Patch only the inherited V2.8 Step-5 HTML renderer."""
    prior.install()
    cards.v28._render_top5 = _render_top5_v367
    cards.v28._v367_step5_matchup_history_installed = True


def begin_render():
    """Reset presentation memos and install identity + defense + history."""
    _HISTORY_MEMO.clear()
    prior.begin_render()
    install()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
