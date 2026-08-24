"""WNBA Spread V1.6.2 — Top-5 visual cards, Step 2 team-vs-team history.

Presentation-only wrapper over the verified V1.6.1 Spread production route.
The V1.6.1 margin model, sportsbook transport, analytical probability,
5,000,000-draw Monte Carlo, convergence contract, grading and one-candidate-
per-game selection remain unchanged.

Step 2 adds fail-soft current-season completed team-vs-team history inside the
same cards. History is descriptive only and never feeds the production model.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v161 as prior
import wnba_schedule_v24 as schedule24
import wnba_schedule_v25 as schedule25

base = prior.base
MODEL_VERSION = "WNBA SPREAD V1.6.2 • TOP-5 CARD STEP 2"
_ORIGINAL_STEP7 = base._render_step7


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _line(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.1f}".replace("+0.0", "PK").replace("-0.0", "PK")


def _odds(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x) or x == 0:
        return "—"
    return f"{x:+.0f}"


def _ev(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:+.1f}%"


def _logo(team_id) -> str:
    try:
        return str(schedule25.logo_url(int(float(team_id))) or "")
    except Exception:
        return ""


def _is_home(row) -> bool:
    best = _norm(row.get("best_side"))
    home = _norm(row.get("home_team"))
    away = _norm(row.get("away_team"))
    if best and best == home:
        return True
    if best and best == away:
        return False
    return True


def _strength(row) -> tuple[str, str]:
    grade = str(row.get("grade") or "MONITOR").upper().strip()
    state = str(row.get("mc_state") or "MONITOR").upper().strip()
    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    ev = _num(row.get("best_ev"), np.nan)

    if state == "BLOCKED" or grade == "BLOCKED":
        return "BLOCKED", "blocked"
    if state != "READY" or grade == "MONITOR":
        return "MONITOR", "monitor"
    if grade != "QUALIFIED":
        return "NO PLAY", "nop"

    positive_ev = (not np.isfinite(ev)) or ev > 0
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.62 and edge >= 6.0 and positive_ev:
        return "ELITE", "elite"
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.59 and edge >= 4.0 and positive_ev:
        return "STRONG", "strong"
    return "MEDIUM", "medium"


def _presentation_order(final: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(final, pd.DataFrame) or final.empty:
        return pd.DataFrame()
    work = final.copy()
    grade_rank = {"QUALIFIED": 4, "MONITOR": 3, "NO PLAY": 2, "BLOCKED": 0}
    work["_grade_rank"] = work.get("grade", "MONITOR").astype(str).str.upper().map(grade_rank).fillna(1)
    work["_ready_rank"] = work.get("mc_state", "MONITOR").astype(str).str.upper().eq("READY").astype(int)
    work["_cover_rank"] = pd.to_numeric(work.get("best_cover_no_push"), errors="coerce").fillna(-1.0)
    work["_edge_rank"] = pd.to_numeric(work.get("best_edge_pp"), errors="coerce").fillna(-999.0)
    work["_ev_rank"] = pd.to_numeric(work.get("best_ev"), errors="coerce").fillna(-999.0)
    return (
        work.sort_values(
            ["_grade_rank", "_ready_rank", "_cover_rank", "_edge_rank", "_ev_rank"],
            ascending=False,
            kind="stable",
        )
        .head(5)
        .reset_index(drop=True)
    )


def _score_value(competitor: dict):
    raw = (competitor or {}).get("score")
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("displayValue"))
    return _num(raw, np.nan)


def _parse_espn_events(payload) -> pd.DataFrame:
    rows = []
    for event in (payload or {}).get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        status = (event.get("status") or {}).get("type") or {}
        state = str(status.get("state") or "").lower()
        completed = bool(status.get("completed")) or state == "post" or "FINAL" in str(
            status.get("name") or status.get("description") or status.get("detail") or ""
        ).upper()
        if not completed:
            continue

        sides = {}
        for competitor in comp.get("competitors", []) or []:
            sides[str(competitor.get("homeAway") or "").lower()] = competitor
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        try:
            away_id = int(schedule24._safe_team_id(away_t))
            home_id = int(schedule24._safe_team_id(home_t))
        except Exception:
            continue
        if not schedule24.guarded._is_wnba_team_id(away_id) or not schedule24.guarded._is_wnba_team_id(home_id):
            continue

        away_score = _score_value(away_c)
        home_score = _score_value(home_c)
        if not np.isfinite(away_score) or not np.isfinite(home_score):
            continue

        raw_dt = event.get("date") or comp.get("date")
        rows.append({
            "game_id": str(event.get("id") or ""),
            "game_date": schedule24._event_date_et(raw_dt),
            "away_team_id": away_id,
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "away_abbr": str(away_t.get("abbreviation") or "AWY"),
            "away_score": float(away_score),
            "home_team_id": home_id,
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "home_abbr": str(home_t.get("abbreviation") or "HME"),
            "home_score": float(home_score),
        })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["game_id"], keep="first").reset_index(drop=True)
    return frame


@st.cache_data(ttl=180, show_spinner=False, max_entries=8)
def _season_h2h_results(season: int):
    """Primary ESPN season read. Short cache prevents one timeout from sticking."""
    try:
        payload, request_meta = schedule24._request_json(
            "ESPN WNBA Spread Step-2 history",
            schedule24.ESPN_SCOREBOARD,
            params={"dates": str(int(season)), "limit": 1000},
            timeout=10,
            attempts=3,
        )
    except Exception as exc:
        return pd.DataFrame(), {"state": "UNAVAILABLE", "error": str(exc)[:160]}

    if payload is None:
        return pd.DataFrame(), {
            "state": "UNAVAILABLE",
            "error": str((request_meta or {}).get("error") or "history provider unavailable")[:160],
        }

    frame = _parse_espn_events(payload)
    return frame, {
        "state": "READY",
        "source": "ESPN WNBA completed-game scoreboard",
        "season": int(season),
        "games": int(len(frame)),
    }


@st.cache_data(ttl=300, show_spinner=False, max_entries=64)
def _daily_espn_results(day_yyyymmdd: str) -> pd.DataFrame:
    try:
        payload, _ = schedule24._request_json(
            "ESPN WNBA Spread Step-2 daily fallback",
            schedule24.ESPN_SCOREBOARD,
            params={"dates": str(day_yyyymmdd), "limit": 100},
            timeout=8,
            attempts=2,
        )
    except Exception:
        payload = None
    return _parse_espn_events(payload) if payload is not None else pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False, max_entries=64)
def _fallback_pair_results(day_str: str, selected_id: int, opponent_id: int):
    """Official WNBA schedule -> exact H2H dates -> ESPN daily score fallback."""
    day = pd.to_datetime(day_str).normalize()
    try:
        payload, meta = schedule24._request_json(
            "WNBA official CDN Spread Step-2 fallback",
            schedule25.WNBA_CDN,
            timeout=9,
            attempts=2,
        )
    except Exception as exc:
        return pd.DataFrame(), {"state": "UNAVAILABLE", "error": str(exc)[:160]}

    if payload is None:
        return pd.DataFrame(), {
            "state": "UNAVAILABLE",
            "error": str((meta or {}).get("error") or "official schedule unavailable")[:160],
        }

    candidate_dates = []
    league = (payload or {}).get("leagueSchedule") or {}
    for block in league.get("gameDates", []) or []:
        block_date = block.get("gameDate")
        for game in block.get("games", []) or []:
            try:
                away = game.get("awayTeam") or {}
                home = game.get("homeTeam") or {}
                away_id = int(schedule24._safe_team_id(away, away.get("teamId")))
                home_id = int(schedule24._safe_team_id(home, home.get("teamId")))
            except Exception:
                continue
            if not (
                (away_id == selected_id and home_id == opponent_id)
                or (away_id == opponent_id and home_id == selected_id)
            ):
                continue
            if int(_num(game.get("gameStatus"), 0)) != 3:
                continue
            gdate = schedule24._cdn_game_date(game, block_date)
            gdt = pd.to_datetime(gdate, errors="coerce")
            if pd.notna(gdt) and gdt < day:
                candidate_dates.append(gdt.strftime("%Y%m%d"))

    frames = []
    for date_key in sorted(set(candidate_dates), reverse=True)[:10]:
        daily = _daily_espn_results(date_key)
        if daily is None or daily.empty:
            continue
        away = pd.to_numeric(daily.get("away_team_id"), errors="coerce").fillna(0).astype(int)
        home = pd.to_numeric(daily.get("home_team_id"), errors="coerce").fillna(0).astype(int)
        pair = (
            (away.eq(selected_id) & home.eq(opponent_id))
            | (away.eq(opponent_id) & home.eq(selected_id))
        )
        part = daily.loc[pair].copy()
        if not part.empty:
            frames.append(part)

    if not frames:
        return pd.DataFrame(), {"state": "NO_MEETINGS", "source": "WNBA CDN + ESPN daily fallback"}
    out = pd.concat(frames, ignore_index=True).drop_duplicates("game_id", keep="first")
    return out, {"state": "READY", "source": "WNBA official schedule + ESPN daily score fallback"}


def _record_text(wins: int, losses: int) -> str:
    total = int(wins) + int(losses)
    return "—" if total <= 0 else f"{int(wins)}-{int(losses)}"


def _pair_filter(results: pd.DataFrame, day, selected_id: int, opponent_id: int) -> pd.DataFrame:
    if results is None or results.empty:
        return pd.DataFrame()
    away = pd.to_numeric(results.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(results.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    dates = pd.to_datetime(results.get("game_date"), errors="coerce")
    pair = (
        (away.eq(selected_id) & home.eq(opponent_id))
        | (away.eq(opponent_id) & home.eq(selected_id))
    )
    return results.loc[pair & (dates < day)].copy()


def _history_summary(day_str: str, row) -> dict:
    try:
        selected_is_home = _is_home(row)
        selected_id = int(float(row.get("home_team_id") if selected_is_home else row.get("away_team_id")))
        opponent_id = int(float(row.get("away_team_id") if selected_is_home else row.get("home_team_id")))
        selected_name = str(row.get("best_side") or (row.get("home_team") if selected_is_home else row.get("away_team")) or "Selected team")
        opponent_name = str((row.get("away_team") if selected_is_home else row.get("home_team")) or "Opponent")
        day = pd.to_datetime(day_str).normalize()
    except Exception as exc:
        return {"state": "UNAVAILABLE", "error": str(exc)[:160]}

    results, provider = _season_h2h_results(int(day.year))
    meetings = _pair_filter(results, day, selected_id, opponent_id)

    # If the season-wide ESPN call times out or returns a partial/empty slate,
    # fall back to official WNBA H2H dates and only query those exact dates.
    if meetings.empty:
        fallback, fallback_meta = _fallback_pair_results(str(day_str), selected_id, opponent_id)
        fallback_meetings = _pair_filter(fallback, day, selected_id, opponent_id)
        if not fallback_meetings.empty:
            meetings = fallback_meetings
            provider = fallback_meta
        elif str((provider or {}).get("state") or "").upper() != "READY":
            return {
                "state": "UNAVAILABLE",
                "error": str((provider or {}).get("error") or (fallback_meta or {}).get("error") or "history sources unavailable"),
            }

    if meetings.empty:
        return {"state": "NO_MEETINGS", "season": int(day.year), "games": 0}

    meetings["_date"] = pd.to_datetime(meetings.get("game_date"), errors="coerce")
    meetings = meetings.sort_values("_date", ascending=False).drop_duplicates("game_id", keep="first")

    enriched = []
    for _, game in meetings.iterrows():
        selected_home = int(_num(game.get("home_team_id"), 0)) == selected_id
        if selected_home:
            selected_score = _num(game.get("home_score"), np.nan)
            opponent_score = _num(game.get("away_score"), np.nan)
            selected_abbr = str(game.get("home_abbr") or selected_name[:3]).upper()
            opponent_abbr = str(game.get("away_abbr") or opponent_name[:3]).upper()
        else:
            selected_score = _num(game.get("away_score"), np.nan)
            opponent_score = _num(game.get("home_score"), np.nan)
            selected_abbr = str(game.get("away_abbr") or selected_name[:3]).upper()
            opponent_abbr = str(game.get("home_abbr") or opponent_name[:3]).upper()
        if not np.isfinite(selected_score) or not np.isfinite(opponent_score):
            continue
        margin = float(selected_score - opponent_score)
        enriched.append({
            "date": game.get("_date"),
            "selected_home": bool(selected_home),
            "selected_score": float(selected_score),
            "opponent_score": float(opponent_score),
            "selected_abbr": selected_abbr,
            "opponent_abbr": opponent_abbr,
            "margin": margin,
            "total": float(selected_score + opponent_score),
            "win": margin > 0,
        })

    if not enriched:
        return {"state": "NO_MEETINGS", "season": int(day.year), "games": 0}

    games = pd.DataFrame(enriched).sort_values("date", ascending=False).reset_index(drop=True)
    gp = int(len(games))
    wins = int(games["win"].sum())
    losses = gp - wins
    home_games = games.loc[games["selected_home"]]
    away_games = games.loc[~games["selected_home"]]
    home_w = int(home_games["win"].sum()) if len(home_games) else 0
    away_w = int(away_games["win"].sum()) if len(away_games) else 0
    home_l = int(len(home_games) - home_w)
    away_l = int(len(away_games) - away_w)

    if gp >= 5:
        reliability, reliability_class = "HIGH", "good"
    elif gp >= 3:
        reliability, reliability_class = "MEDIUM", "mid"
    else:
        reliability, reliability_class = "LOW", "warn"

    last5 = games.head(5)
    margins = " • ".join(f"{float(x):+.0f}" for x in last5["margin"].tolist()) or "—"
    meeting_lines = []
    for _, game in last5.iterrows():
        dt = game.get("date")
        date_text = dt.strftime("%b %d") if pd.notna(dt) else "—"
        result = "W" if bool(game.get("win")) else "L"
        meeting_lines.append(
            f"{date_text} • {game.get('selected_abbr')} {float(game.get('selected_score')):.0f}–"
            f"{float(game.get('opponent_score')):.0f} {game.get('opponent_abbr')} • "
            f"{result} {float(game.get('margin')):+.0f}"
        )

    return {
        "state": "READY",
        "season": int(day.year),
        "games": gp,
        "record": _record_text(wins, losses),
        "home_record": _record_text(home_w, home_l),
        "away_record": _record_text(away_w, away_l),
        "avg_margin": float(games["margin"].mean()),
        "avg_total": float(games["total"].mean()),
        "recent_margins": margins,
        "latest": meeting_lines[0] if meeting_lines else "—",
        "meeting_lines": meeting_lines,
        "reliability": reliability,
        "reliability_class": reliability_class,
        "scope": f"{int(day.year)} current season",
        "source": str((provider or {}).get("source") or "verified WNBA/ESPN history"),
    }


def _history_block(day_str: str, row) -> str:
    try:
        summary = _history_summary(day_str, row)
    except Exception as exc:
        summary = {"state": "UNAVAILABLE", "error": str(exc)[:160]}

    state = str(summary.get("state") or "UNAVAILABLE").upper()
    if state == "UNAVAILABLE":
        return """
  <div class="ks-spread162-history">
    <div class="ks-spread162-hhead"><span>STEP 2 • TEAM VS TEAM HISTORY</span><span class="ks-spread162-rel warn">SOURCE CHECK</span></div>
    <div class="ks-spread162-hempty">Historical results are temporarily unavailable. Step 1 and the verified Spread model are unchanged.</div>
    <div class="ks-spread162-hnote">Descriptive layer only • history failure cannot block, alter or rerank the production Spread result.</div>
  </div>
"""
    if state == "NO_MEETINGS":
        season = escape(str(summary.get("season") or "current"))
        return f"""
  <div class="ks-spread162-history">
    <div class="ks-spread162-hhead"><span>STEP 2 • TEAM VS TEAM HISTORY</span><span class="ks-spread162-rel warn">LOW / NONE</span></div>
    <div class="ks-spread162-hempty">No verified completed prior meetings found in the {season} current season before this slate date.</div>
    <div class="ks-spread162-hnote">Descriptive layer only • no history adjustment is applied to projection, 5M Monte Carlo, qualification or ranking.</div>
  </div>
"""

    gp = int(summary.get("games") or 0)
    avg_margin = _num(summary.get("avg_margin"), np.nan)
    avg_total = _num(summary.get("avg_total"), np.nan)
    margin_text = "—" if not np.isfinite(avg_margin) else f"{avg_margin:+.1f} pts"
    total_text = "—" if not np.isfinite(avg_total) else f"{avg_total:.1f}"
    meetings_html = "".join(f"<div>{escape(str(text))}</div>" for text in (summary.get("meeting_lines") or [])) or "<div>—</div>"

    return f"""
  <div class="ks-spread162-history">
    <div class="ks-spread162-hhead"><span>STEP 2 • TEAM VS TEAM HISTORY</span><span class="ks-spread162-rel {escape(str(summary.get('reliability_class') or 'warn'))}">{escape(str(summary.get('reliability') or 'LOW'))} RELIABILITY</span></div>
    <div class="ks-spread162-hscope">{escape(str(summary.get('scope') or 'current season'))} • {gp} verified completed meeting(s) • selected-team perspective</div>
    <div class="ks-spread162-hgrid">
      <div><small>H2H RECORD</small><strong>{escape(str(summary.get('record') or '—'))}</strong></div>
      <div><small>AVG SCORING MARGIN</small><strong>{margin_text}</strong></div>
      <div><small>HOME H2H</small><strong>{escape(str(summary.get('home_record') or '—'))}</strong></div>
      <div><small>AWAY H2H</small><strong>{escape(str(summary.get('away_record') or '—'))}</strong></div>
      <div><small>AVG GAME TOTAL</small><strong>{total_text}</strong></div>
      <div><small>RECENT MARGINS</small><strong>{escape(str(summary.get('recent_margins') or '—'))}</strong></div>
      <div class="wide"><small>MOST RECENT MEETING</small><strong>{escape(str(summary.get('latest') or '—'))}</strong></div>
    </div>
    <div class="ks-spread162-meetings"><small>LAST MEETINGS</small>{meetings_html}</div>
    <div class="ks-spread162-hnote">Source • {escape(str(summary.get('source') or 'verified WNBA/ESPN history'))} • descriptive only • NOT FED INTO projection, 5M Monte Carlo, edge, EV, qualification or card ranking.</div>
  </div>
"""


def _card(row, rank: int, day_str: str) -> str:
    away = str(row.get("away_team") or "Away")
    home = str(row.get("home_team") or "Home")
    best = str(row.get("best_side") or "Team")
    is_home = _is_home(row)

    selected_id = row.get("home_team_id") if is_home else row.get("away_team_id")
    opp_id = row.get("away_team_id") if is_home else row.get("home_team_id")
    opponent = away if is_home else home
    selected_logo = escape(_logo(selected_id), quote=True)
    opp_logo = escape(_logo(opp_id), quote=True)
    selected_img = f'<img src="{selected_logo}" alt="{escape(best)} logo">' if selected_logo else "🏀"
    opp_img = f'<img src="{opp_logo}" alt="{escape(opponent)} logo">' if opp_logo else "🏀"

    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    market = _num(row.get("home_market_novig") if is_home else row.get("away_market_novig"), np.nan)
    fair = row.get("mc_home_fair_odds") if is_home else row.get("mc_away_fair_odds")
    push = _num(row.get("mc_push"), np.nan)
    mean_home = _num(row.get("projected_home_margin"), np.nan)
    side_margin = mean_home if is_home else (-mean_home if np.isfinite(mean_home) else np.nan)
    spread = _num(row.get("best_spread"), np.nan)
    cushion = side_margin + spread if np.isfinite(side_margin) and np.isfinite(spread) else np.nan

    strength, strength_class = _strength(row)
    grade = str(row.get("grade") or "MONITOR").upper()
    converged = bool(row.get("converged"))
    book = str(row.get("book") or "—")
    sims = int(_num(row.get("simulation_count"), 0) or 0)
    venue = str(row.get("venue") or "")
    tip = str(row.get("first_tip_et") or "")
    meta = " • ".join(x for x in [tip, venue] if x)

    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
    edge_text = "—" if not np.isfinite(edge) else f"{edge:+.1f} pp"
    cushion_text = "—" if not np.isfinite(cushion) else f"{cushion:+.1f} pts"
    mean_text = "—" if not np.isfinite(mean_home) else f"{mean_home:+.1f} pts"
    sims_text = f"{sims:,}" if sims else "—"

    return f"""
<div class="ks-spread162-card {('rank1' if rank == 1 else '')}">
  <div class="ks-spread162-rank">{medal} RANK {rank} • <span>{escape(grade)}</span> <b>DISPLAY ORDER ONLY</b></div>
  <div class="ks-spread162-matchup">
    <div class="ks-spread162-side"><div class="ks-spread162-logo">{selected_img}</div><div><div class="ks-spread162-team">{escape(best)}</div><div class="ks-spread162-pick">{escape(best)} {_line(spread)}</div></div></div>
    <div class="ks-spread162-vs">vs</div>
    <div class="ks-spread162-side opp"><div class="ks-spread162-logo">{opp_img}</div><div><div class="ks-spread162-team">{escape(opponent)}</div><div class="ks-spread162-sub">{escape(away)} @ {escape(home)}</div></div></div>
  </div>
  {f'<div class="ks-spread162-meta">{escape(meta)}</div>' if meta else ''}
  <div class="ks-spread162-prob">{_pct(cover)}</div>
  <div class="ks-spread162-probsub">5M MC NO-PUSH COVER PROBABILITY • FAIR {_odds(fair)}</div>
  <div class="ks-spread162-badges">
    <span class="strength {strength_class}">PICK STRENGTH • {escape(strength)}</span>
    <span>PRODUCTION GRADE • {escape(grade)}</span>
    <span class="{('pass' if converged else 'warn')}">CONVERGENCE • {('PASS' if converged else 'CHECK')}</span>
  </div>
  <div class="ks-spread162-grid">
    <div><small>EXACT MARKET</small><strong>{_line(spread)} ({_odds(row.get('best_price'))})</strong></div>
    <div><small>BOOK</small><strong>{escape(book)}</strong></div>
    <div><small>MC COVER</small><strong>{_pct(cover)}</strong></div>
    <div><small>MARKET NO-VIG</small><strong>{_pct(market)}</strong></div>
    <div><small>NO-VIG EDGE</small><strong>{edge_text}</strong></div>
    <div><small>EV</small><strong>{_ev(row.get('best_ev'))}</strong></div>
    <div><small>PROJECTED HOME MARGIN</small><strong>{mean_text}</strong></div>
    <div><small>PROJECTED COVER CUSHION</small><strong>{cushion_text}</strong></div>
    <div><small>PUSH PROBABILITY</small><strong>{_pct(push)}</strong></div>
    <div><small>SIMULATIONS</small><strong>{sims_text}</strong></div>
  </div>
  <div class="ks-spread162-note">CARD STEP 1 • PICK IDENTITY + VERIFIED MODEL SNAPSHOT • existing V1.6.1 side, line, probability, edge, EV, convergence and qualification only. No new spread projection or reranking is fed back into production.</div>
  {_history_block(day_str, row)}
</div>
"""


def _render_top5_step1(day_str: str, final: pd.DataFrame, meta: dict) -> None:
    st.markdown("### 🏆 Strongest WNBA Spread Picks — Top-5 Cards")
    st.caption(
        "CARD STEPS 1–2 • Pick identity/model snapshot + team-vs-team history. "
        "Uses the existing V1.6 one-candidate-per-game final output after the actual 5M pass. "
        "History is descriptive only; no fifth play is forced."
    )
    if not isinstance(final, pd.DataFrame) or final.empty:
        st.info("Top-5 Spread cards are waiting on the current Step-7 5,000,000-draw result. Run the verified Spread Monte Carlo above first.")
        return

    ranked = _presentation_order(final)
    if ranked.empty:
        st.info("No current final Spread candidates are available for Top-5 presentation.")
        return

    st.markdown("""
<style>
.ks-spread162-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 18px}
.ks-spread162-card{background:linear-gradient(145deg,#0b2034,#071521);border:1px solid #315c78;border-radius:22px;padding:17px;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.ks-spread162-card.rank1{border-color:#d5aa18;box-shadow:inset 5px 0 0 #d5aa18,0 8px 24px rgba(0,0,0,.20)}
.ks-spread162-rank{color:#66ddff;font-size:.62rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:12px}.ks-spread162-rank span{color:#9ef3d0}.ks-spread162-rank b{float:right;color:#6f8293;font-size:.48rem}
.ks-spread162-matchup{display:grid;grid-template-columns:1fr 26px 1fr;align-items:center;gap:7px}.ks-spread162-side{display:flex;align-items:center;gap:9px}.ks-spread162-side.opp{justify-content:flex-end;text-align:right}.ks-spread162-logo{width:54px;height:54px;display:flex;align-items:center;justify-content:center}.ks-spread162-logo img{max-width:54px;max-height:54px;object-fit:contain}.ks-spread162-team{color:#fff;font-size:.92rem;font-weight:950;line-height:1.15}.ks-spread162-pick{color:#ffe17a;font-size:.75rem;font-weight:900;margin-top:4px}.ks-spread162-sub{color:#7f95a7;font-size:.58rem;margin-top:4px}.ks-spread162-vs{text-align:center;color:#6e8394;font-size:.68rem;font-weight:900}.ks-spread162-meta{color:#7f95a7;font-size:.60rem;margin:9px 0 3px}
.ks-spread162-prob{font-size:2.75rem;font-weight:1000;color:#fff;line-height:1;margin-top:16px}.ks-spread162-probsub{font-size:.55rem;color:#7890a5;font-weight:900;letter-spacing:.035em;margin-top:5px}
.ks-spread162-badges{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ks-spread162-badges span{border:1px solid #355873;background:#0b1824;color:#bed4e3;border-radius:999px;padding:6px 8px;font-size:.49rem;font-weight:950;letter-spacing:.035em}.ks-spread162-badges .elite,.ks-spread162-badges .strong,.ks-spread162-badges .pass{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread162-badges .medium{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread162-badges .monitor,.ks-spread162-badges .nop,.ks-spread162-badges .warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread162-badges .blocked{border-color:#7a3941;background:#35171b;color:#ff9aa5}
.ks-spread162-grid,.ks-spread162-hgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.ks-spread162-grid div,.ks-spread162-hgrid div{background:#081522;border:1px solid #284b64;border-radius:11px;padding:9px}.ks-spread162-grid small,.ks-spread162-hgrid small,.ks-spread162-meetings small{display:block;color:#718ba0;font-size:.47rem;font-weight:950;letter-spacing:.04em}.ks-spread162-grid strong,.ks-spread162-hgrid strong{display:block;color:#f6fbff;font-size:.78rem;margin-top:3px}.ks-spread162-note{color:#6f8799;font-size:.54rem;line-height:1.45;margin-top:10px}
.ks-spread162-history{background:#091827;border:1px solid #294b64;border-radius:15px;padding:12px;margin-top:14px}.ks-spread162-hhead{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#79d8ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.ks-spread162-rel{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;white-space:nowrap}.ks-spread162-rel.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread162-rel.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread162-rel.warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread162-hscope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}.ks-spread162-hgrid .wide{grid-column:1/-1}.ks-spread162-meetings{margin-top:8px;background:#07131f;border:1px solid #24445c;border-radius:10px;padding:8px}.ks-spread162-meetings div{color:#d7e5ef;font-size:.61rem;line-height:1.5;margin-top:3px}.ks-spread162-hnote{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread162-hempty{color:#c8d7e3;font-size:.66rem;line-height:1.5;margin-top:9px}
@media(max-width:760px){.ks-spread162-wrap{grid-template-columns:1fr}.ks-spread162-rank b{float:none;display:block;margin-top:3px}.ks-spread162-logo{width:48px;height:48px}.ks-spread162-logo img{max-width:48px;max-height:48px}.ks-spread162-prob{font-size:2.45rem}.ks-spread162-hhead{align-items:flex-start}.ks-spread162-rel{font-size:.48rem}}
</style>
""", unsafe_allow_html=True)

    cards = "".join(_card(row, i + 1, day_str) for i, (_, row) in enumerate(ranked.iterrows()))
    st.markdown(f'<div class="ks-spread162-wrap">{cards}</div>', unsafe_allow_html=True)
    qualified = int(ranked.get("grade", pd.Series(dtype=object)).astype(str).str.upper().eq("QUALIFIED").sum())
    st.caption(
        f"Current card set • {len(ranked)} one-per-game candidate(s) • {qualified} QUALIFIED • "
        "visual ordering uses existing production grade → MC cover → no-vig edge → EV only. "
        "Team history is read-only descriptive context; production payload and per-game selection are unchanged."
    )


def _render_step7_with_top5(day_str: str, pregame: pd.DataFrame, board: pd.DataFrame, probability_ready: bool):
    detail, final, meta = _ORIGINAL_STEP7(day_str, pregame, board, probability_ready)
    _render_top5_step1(day_str, final, meta if isinstance(meta, dict) else {})
    return detail, final, meta


def _install() -> None:
    base._render_step7 = _render_step7_with_top5


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎨 Spread V1.6.2 • Top-5 Card Steps 1–2 ACTIVE • exact spread + 5M probability + "
        "pick strength + fail-soft verified team history • production model/ranking unchanged"
    )
    return prior.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
