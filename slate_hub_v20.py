"""V20 MLB Slate Command Center.

A dedicated, mobile-first slate page built on the verified MLB schedule. It is
fast by default and can optionally enrich every game with the existing Kyre
Sports AI moneyline/run model, probable-starter stats, recent form, and live
sportsbook snapshots when available.
"""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from engine import ET, odds
from live_game_hub_v182 import fetch_live_slate, _priority, _state_label, _time_sort
from live_odds_feed import get_api_key, get_bookmakers, snapshots_for_games
from moneyline_hub_v16 import _scan_game as scan_moneyline_game

MODEL_VERSION = "V20"

SLATE_CSS = r"""
<style>
:root{--sl-bg:#07101f;--sl-card:#0d192c;--sl-card2:#0a1526;--sl-line:#223b5d;--sl-cyan:#35c8ff;--sl-green:#47e0a2;--sl-gold:#ffd84d;--sl-red:#ff6573;--sl-text:#f8fafc;--sl-muted:#8fa4bd}
.sl-hero{border:1px solid #214a73;background:radial-gradient(circle at 8% 10%,rgba(35,190,255,.13),transparent 30%),linear-gradient(135deg,#0b1a31,#07111f);border-radius:24px;padding:18px 19px;margin:8px 0 16px;box-shadow:0 18px 44px rgba(0,0,0,.22)}
.sl-kicker{font-size:.7rem;letter-spacing:.17em;text-transform:uppercase;color:var(--sl-cyan);font-weight:950}.sl-title{font-size:1.75rem;line-height:1.05;font-weight:950;color:white;margin:6px 0}.sl-sub{font-size:.83rem;color:var(--sl-muted);line-height:1.45}
.sl-counts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.sl-count{border:1px solid #213b5b;background:#091629;border-radius:14px;padding:10px}.sl-count b{display:block;font-size:1.25rem;color:white}.sl-count span{font-size:.68rem;color:#849ab5;text-transform:uppercase;letter-spacing:.08em;font-weight:800}
.sl-card{border:1px solid #203956;background:linear-gradient(150deg,#101f35,#0a1526);border-radius:22px;padding:15px 16px;margin:12px 0;box-shadow:0 12px 28px rgba(0,0,0,.16)}.sl-card.live{border-color:#7b2a38}.sl-card.final{opacity:.88}.sl-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.sl-status{display:inline-flex;align-items:center;border:1px solid #2a4a6e;border-radius:999px;padding:5px 9px;font-size:.66rem;font-weight:900;letter-spacing:.06em;color:#cfe6fb;background:#0a1930}.sl-status.live{border-color:#76313b;color:#ffb3bd;background:#2a1118}.sl-status.final{color:#aebdd0}.sl-time{font-size:.78rem;color:#9fb1c6;font-weight:800}
.sl-teams{display:grid;grid-template-columns:1fr 34px 1fr;gap:10px;align-items:center;margin:14px 0}.sl-team{text-align:center;min-width:0}.sl-logo{width:54px;height:54px;object-fit:contain}.sl-teamname{font-size:1.03rem;font-weight:900;color:white;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sl-at{font-weight:950;color:#607a99;text-align:center}.sl-score{font-size:1.8rem;font-weight:950;color:white}.sl-venue{text-align:center;font-size:.72rem;color:#8196af;margin-top:-4px}
.sl-pitchers{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:13px 0}.sl-pitch{border:1px solid #203a59;background:#09172a;border-radius:15px;padding:10px}.sl-label{font-size:.65rem;color:#7f95ae;letter-spacing:.09em;text-transform:uppercase;font-weight:850}.sl-pname{font-size:.9rem;color:white;font-weight:850;margin:3px 0}.sl-pstats{font-size:.7rem;color:#9eb0c7;line-height:1.4}
.sl-intel{border-top:1px solid rgba(143,164,189,.16);margin-top:12px;padding-top:12px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.sl-metric{background:#0a1728;border:1px solid #203653;border-radius:13px;padding:9px}.sl-metric b{display:block;color:white;font-size:.98rem}.sl-metric span{font-size:.64rem;color:#7f95ae;text-transform:uppercase;letter-spacing:.06em;font-weight:800}.sl-metric.cyan b{color:#62ddff}.sl-metric.green b{color:#65e5af}
.sl-form{font-size:.72rem;color:#9bafc6;margin-top:9px;line-height:1.5}.sl-market{margin-top:10px;border-left:3px solid var(--sl-cyan);background:#08182a;border-radius:0 12px 12px 0;padding:9px 11px;font-size:.71rem;color:#afc3d8;line-height:1.5}.sl-market b{color:white}.sl-warn{border:1px solid #725817;background:#2a2109;border-radius:12px;padding:9px 11px;color:#ffe69a;font-size:.73rem;margin:8px 0}
@media(max-width:700px){.sl-hero{border-radius:20px;padding:15px}.sl-title{font-size:1.45rem}.sl-counts{grid-template-columns:1fr 1fr}.sl-teams{grid-template-columns:1fr 24px 1fr}.sl-logo{width:46px;height:46px}.sl-teamname{font-size:.92rem}.sl-pitchers{grid-template-columns:1fr}.sl-intel{grid-template-columns:1fr 1fr}.sl-card{padding:13px}}
</style>
"""


def _logo(team_id):
    try:
        return f"https://www.mlbstatic.com/team-logos/{int(team_id)}.svg"
    except Exception:
        return ""


def _fmt(v, digits=2, fallback="—"):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return fallback


def _record(form):
    if not form or not form.get("games"):
        return "N/A"
    g = int(form.get("games") or 0)
    wins = int(round(float(form.get("win_pct", 0) or 0) * g))
    wins = max(0, min(wins, g))
    return f"{wins}-{g-wins}"


def _refresh_rows(games_df):
    if games_df is None or games_df.empty:
        return []
    verified = games_df.copy()
    if "verified" in verified.columns:
        verified = verified[verified["verified"].fillna(False).astype(bool)].copy()
    if verified.empty:
        return []

    day = str(verified.iloc[0].get("game_date", ""))
    allowed = tuple(sorted(pd.to_numeric(verified["game_pk"], errors="coerce").dropna().astype(int).tolist()))
    try:
        fresh = fetch_live_slate(day, allowed)
    except Exception:
        fresh = {}

    rows = []
    for _, row in verified.iterrows():
        d = row.to_dict()
        try:
            pk = int(d.get("game_pk"))
        except Exception:
            continue
        if pk in fresh:
            d.update(fresh[pk])
        rows.append(d)
    rows.sort(key=lambda r: (_priority(r.get("status")), _time_sort(r.get("first_pitch_et")), str(r.get("away_team", ""))))
    return rows


def _build_intelligence(rows, day):
    out = {}
    errors = 0
    bar = st.progress(0, text="Building V20 slate intelligence...")
    for idx, row in enumerate(rows, 1):
        try:
            status = _state_label(row.get("status"))
            if status == "FINAL":
                bar.progress(idx / len(rows), text=f"Reading game {idx}/{len(rows)}")
                continue
            result = scan_moneyline_game(pd.Series(row), 40_000)
            model = result.get("model") or {}
            out[int(row["game_pk"])] = {
                "favorite": result.get("team"),
                "favorite_prob": float(result.get("win_prob", 0) or 0),
                "fair_ml": result.get("fair_odds"),
                "away_score": float(result.get("away_score", 0) or 0),
                "home_score": float(result.get("home_score", 0) or 0),
                "projected_total": float(result.get("away_score", 0) or 0) + float(result.get("home_score", 0) or 0),
                "confidence": result.get("confidence", "—"),
                "data_score": int(result.get("data_score", 0) or 0),
                "away_recent": model.get("away_recent"),
                "home_recent": model.get("home_recent"),
                "away_sp": model.get("away_starter"),
                "home_sp": model.get("home_starter"),
                "lineups": bool(model.get("away_lineup") and model.get("home_lineup")),
            }
        except Exception:
            errors += 1
        bar.progress(idx / len(rows), text=f"Modeling game {idx}/{len(rows)}")
    bar.empty()
    st.session_state[f"v20_intel_{day}"] = out
    st.session_state[f"v20_intel_time_{day}"] = datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0")
    st.session_state[f"v20_intel_errors_{day}"] = errors
    return out


def _pitcher_html(name, stats, side):
    if not stats:
        detail = "ERA — • WHIP — • K/9 —"
    else:
        detail = f"ERA {_fmt(stats.get('era'))} • WHIP {_fmt(stats.get('whip'))} • K/9 {_fmt(stats.get('k9'),1)} • {escape(str(stats.get('hand') or '?'))}HP"
    return (
        '<div class="sl-pitch">'
        f'<div class="sl-label">{escape(side)} probable starter</div>'
        f'<div class="sl-pname">{escape(str(name or "TBD"))}</div>'
        f'<div class="sl-pstats">{detail}</div></div>'
    )


def _market_html(snap, away, home):
    if not snap or not snap.get("rows"):
        return ""
    r = snap["rows"][0]
    book = escape(str(r.get("Book") or "Sportsbook"))
    return (
        '<div class="sl-market">'
        f'<b>📡 {book}</b> • {escape(away)} ML {escape(str(r.get("Away ML") if r.get("Away ML") is not None else "—"))} • '
        f'{escape(home)} ML {escape(str(r.get("Home ML") if r.get("Home ML") is not None else "—"))}<br>'
        f'RL: {escape(str(r.get("Away RL") or "—"))} / {escape(str(r.get("Home RL") or "—"))} • '
        f'Total: {escape(str(r.get("Over") or "—"))} / {escape(str(r.get("Under") or "—"))}'
        '</div>'
    )


def _render_card(row, intel=None, snap=None):
    status = _state_label(row.get("status"))
    css_state = "live" if status == "LIVE" else "final" if status == "FINAL" else ""
    icon = "🔴" if status == "LIVE" else "🏁" if status == "FINAL" else "⏳"
    away = str(row.get("away_team", "Away")); home = str(row.get("home_team", "Home"))
    away_runs = row.get("away_runs"); home_runs = row.get("home_runs")
    show_score = status in {"LIVE", "FINAL"} and away_runs is not None and home_runs is not None
    away_center = f'<div class="sl-score">{int(away_runs or 0)}</div>' if show_score else ""
    home_center = f'<div class="sl-score">{int(home_runs or 0)}</div>' if show_score else ""
    inning = f" • {escape(str(row.get('inning_state') or ''))} {escape(str(row.get('inning') or ''))}" if status == "LIVE" else ""

    if intel:
        asp = intel.get("away_sp"); hsp = intel.get("home_sp")
    else:
        asp = hsp = None

    intel_html = ""
    if intel:
        fav = escape(str(intel.get("favorite") or "—"))
        p = float(intel.get("favorite_prob", 0) or 0)
        away_form = intel.get("away_recent"); home_form = intel.get("home_recent")
        intel_html = (
            '<div class="sl-intel">'
            f'<div class="sl-metric green"><span>Model favorite</span><b>{fav} {p*100:.1f}%</b></div>'
            f'<div class="sl-metric"><span>Fair ML</span><b>{escape(str(intel.get("fair_ml") or "—"))}</b></div>'
            f'<div class="sl-metric cyan"><span>Projected score</span><b>{intel.get("away_score",0):.1f}–{intel.get("home_score",0):.1f}</b></div>'
            f'<div class="sl-metric"><span>Projected total</span><b>{intel.get("projected_total",0):.1f}</b></div>'
            '</div>'
            f'<div class="sl-form"><b>{escape(away)} L10:</b> {_record(away_form)} • diff {_fmt((away_form or {}).get("run_diff_per_game"),2)} &nbsp; | &nbsp; '
            f'<b>{escape(home)} L10:</b> {_record(home_form)} • diff {_fmt((home_form or {}).get("run_diff_per_game"),2)}<br>'
            f'Data {intel.get("data_score",0)}/9 • {escape(str(intel.get("confidence") or "—"))} confidence • Lineups {"confirmed" if intel.get("lineups") else "not confirmed"}</div>'
        )

    html = (
        f'<div class="sl-card {css_state}">'
        '<div class="sl-top">'
        f'<span class="sl-status {css_state}">{icon} {escape(status)}</span>'
        f'<span class="sl-time">{escape(str(row.get("first_pitch_et") or "TBD"))} ET{inning}</span></div>'
        '<div class="sl-teams">'
        f'<div class="sl-team"><img class="sl-logo" src="{_logo(row.get("away_team_id"))}"><div class="sl-teamname">{escape(away)}</div>{away_center}</div>'
        '<div class="sl-at">@</div>'
        f'<div class="sl-team"><img class="sl-logo" src="{_logo(row.get("home_team_id"))}"><div class="sl-teamname">{escape(home)}</div>{home_center}</div>'
        '</div>'
        f'<div class="sl-venue">📍 {escape(str(row.get("venue_name") or "Venue TBD"))}</div>'
        '<div class="sl-pitchers">'
        f'{_pitcher_html(row.get("away_pitcher", "TBD"), asp, "Away")}'
        f'{_pitcher_html(row.get("home_pitcher", "TBD"), hsp, "Home")}'
        '</div>'
        f'{intel_html}{_market_html(snap, away, home)}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(SLATE_CSS, unsafe_allow_html=True)
    rows = _refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    live = sum(_state_label(r.get("status")) == "LIVE" for r in rows)
    finals = sum(_state_label(r.get("status")) == "FINAL" for r in rows)
    upcoming = sum(_state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id") if r.get(k) is not None and not pd.isna(r.get(k)))
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Verified schedule, game status, probable starters, model pulse and live sportsbook context in one clean page.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v20_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v20_sort_{day}")

    key = get_api_key()
    if key:
        st.caption(f"📡 Live odds connected • {get_bookmakers()} • in-play prices appear automatically on live game cards.")
    else:
        st.caption("📡 Live odds not connected in this session. The slate page still works with verified MLB data and model projections.")

    if st.button("⚡ BUILD V20 SLATE INTELLIGENCE", use_container_width=True, type="primary", key=f"v20_build_{day}"):
        intel = _build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 Model pulse built {stamp or ''} • quick 40K/game preview • use individual market modules for final deep simulations." + (f" • {err} game(s) skipped" if err else ""))

    filtered = []
    for r in rows:
        state = _state_label(r.get("status"))
        if view == "Live" and state != "LIVE":
            continue
        if view == "Upcoming" and state != "PREGAME":
            continue
        if view == "Final" and state != "FINAL":
            continue
        filtered.append(r)

    if sort_by == "Strongest ML":
        filtered.sort(key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("favorite_prob", 0) or 0), reverse=True)
    elif sort_by == "Highest total":
        filtered.sort(key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("projected_total", 0) or 0), reverse=True)
    elif sort_by == "Data quality":
        filtered.sort(key=lambda r: int((intel.get(int(r["game_pk"])) or {}).get("data_score", 0) or 0), reverse=True)
    else:
        filtered.sort(key=lambda r: _time_sort(r.get("first_pitch_et")))

    snaps = {}
    live_rows = [r for r in filtered if _state_label(r.get("status")) == "LIVE"]
    if key and live_rows:
        try:
            snaps = snapshots_for_games(pd.DataFrame(live_rows), key, get_bookmakers())
        except Exception:
            snaps = {}

    if not filtered:
        st.info(f"No {view.lower()} games are on this verified slate.")
        return

    for row in filtered:
        pk = int(row["game_pk"])
        _render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20 Slate is a command-center view. Quick model pulse is for navigation and comparison; use the dedicated Moneyline, Run Line, Totals and Live modules for deeper final simulations and current settlement lines.")
