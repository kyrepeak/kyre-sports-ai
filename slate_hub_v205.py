"""V20.5 MLB Slate Command Center.

Adds season record, L10/L5, H2H L10, lineup feed-check timestamps and stricter
full-game total normalization to the V20.4 lineup/pitcher + V20.3 sportsbook
slate experience.
"""

from datetime import datetime
from html import escape

import pandas as pd
import requests
import streamlit as st

import slate_hub_v20 as core
import slate_hub_v203 as market_ui
import slate_hub_v204 as player_ui
from engine import ET
from live_odds_feed import get_api_key as _raw_get_api_key, get_bookmakers
from slate_history_v205 import build_slate_history_context
from slate_lineup_v204 import build_slate_player_context as _build_player_context_v204
from slate_odds_feed_v205 import slate_snapshots_for_games_v205

MODEL_VERSION = "V20.5"
_CONTEXT = {}

V205_CSS = r"""
<style>
.sl-teamrecord{margin-top:4px;color:#7f97b2;font-size:.64rem;font-weight:750}.sl-teamrecord b{color:#dbeafe}
.sl-history{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:10px 0}.sl-history-box{border:1px solid #203a59;background:#091629;border-radius:13px;padding:8px 9px}.sl-history-box span{display:block;color:#708aa8;font-size:.56rem;letter-spacing:.07em;text-transform:uppercase;font-weight:900}.sl-history-box b{display:block;color:#f8fafc;font-size:.74rem;margin-top:2px}.sl-history-box small{display:block;color:#8fa4bd;font-size:.60rem;margin-top:2px}.sl-history-box.h2h{border-color:#315c7f;background:#091a2c}.sl-checked{font-size:.58rem;color:#6f87a2;margin-top:5px;line-height:1.3}.sl-total-note{margin:-2px 0 8px;border:1px dashed #5d4b19;background:#211b08;border-radius:10px;padding:7px 9px;color:#e8cf79;font-size:.63rem}.sl-total-note b{color:#ffe899}
@media(max-width:700px){.sl-history{grid-template-columns:1fr 1fr}.sl-history-box.h2h{grid-column:1/-1}}
</style>
"""


def _safe_pk(row):
    try:
        return int(row.get("game_pk"))
    except Exception:
        return None


def _fmt_diff(v):
    try:
        return f"{float(v):+.2f} R/G"
    except Exception:
        return "diff —"


def _build_context(games_df):
    base = _build_player_context_v204(games_df)
    try:
        history = build_slate_history_context(games_df)
    except Exception:
        history = {}
    checked = datetime.now(ET).strftime("%I:%M %p ET").lstrip("0")
    keys = set(base) | set(history)
    out = {}
    for pk in keys:
        item = dict(base.get(pk) or {})
        item.update(history.get(pk) or {})
        item["lineup_checked_at"] = checked
        out[int(pk)] = item
    return out


def _ctx(row):
    pk = _safe_pk(row)
    return _CONTEXT.get(pk, {}) if pk is not None else {}


def _lineup_html(team, players, label, confirmed, checked_at):
    players = list(players or [])[:9]
    badge_cls = " confirmed" if confirmed else ""
    if not players:
        body = '<div class="sl-lineup-empty">MLB has not posted this batting order yet, and no recent official lineup was available for a safe projection.</div>'
        more = ""
    else:
        body = player_ui._hit_rows(players[:4])
        more = ""
        if len(players) > 4:
            more = '<details class="sl-more"><summary>＋ View hitters 5–9</summary>' + player_ui._hit_rows(players[4:]) + '</details>'
    note = "Official batting order from this game feed." if confirmed else "Projected from the team's most recent official batting order; not a confirmed lineup."
    checked = f"MLB feed checked {checked_at}." if checked_at else ""
    return (
        '<div class="sl-lineup">'
        '<div class="sl-lineup-head">'
        f'<span class="sl-lineup-team">{escape(str(team))}</span>'
        f'<span class="sl-lineup-badge{badge_cls}">{escape(str(label or "LINEUP"))}</span>'
        '</div>'
        f'{body}{more}<div class="sl-source-note">{escape(note)}</div>'
        f'<div class="sl-checked">{escape(checked)}</div>'
        '</div>'
    )


def _team_record_html(ctx, side):
    record = ctx.get(f"{side}_record") or "N/A"
    l10 = (ctx.get(f"{side}_l10") or {}).get("record", "N/A")
    l5 = (ctx.get(f"{side}_l5") or {}).get("record", "N/A")
    return f'<div class="sl-teamrecord"><b>{escape(str(record))}</b> • L10 {escape(str(l10))} • L5 {escape(str(l5))}</div>'


def _history_html(ctx, away, home):
    a10 = ctx.get("away_l10") or {}
    h10 = ctx.get("home_l10") or {}
    h2h = ctx.get("away_h2h") or {}
    h2h_record = h2h.get("record", "N/A")
    h2h_games = int(h2h.get("games", 0) or 0)
    h2h_detail = _fmt_diff(h2h.get("run_diff")) if h2h_games else "No recent meetings"
    return (
        '<div class="sl-history">'
        f'<div class="sl-history-box"><span>{escape(away)} recent</span><b>L10 {escape(str(a10.get("record", "N/A")))}</b><small>{escape(_fmt_diff(a10.get("run_diff")))}</small></div>'
        f'<div class="sl-history-box"><span>{escape(home)} recent</span><b>L10 {escape(str(h10.get("record", "N/A")))}</b><small>{escape(_fmt_diff(h10.get("run_diff")))}</small></div>'
        f'<div class="sl-history-box h2h"><span>Head-to-head • last {h2h_games if h2h_games else 0}</span><b>{escape(away)} {escape(str(h2h_record))}</b><small>{escape(h2h_detail)}</small></div>'
        '</div>'
    )


def _market_html_v205(snap, away, home):
    base = market_ui._market_html(snap, away, home)
    if not snap:
        return base
    status = snap.get("total_market_status")
    warnings = snap.get("total_warnings") or []
    lines = snap.get("total_lines_by_book") or {}
    note = ""
    if status == "split" and lines:
        parts = [f"{book} {line:g}" for book, line in lines.items()]
        note = "Books posted different full-game total lines, so V20.5 does not compare prices across them: " + " • ".join(parts)
    elif warnings:
        note = "Filtered from full-game total comparison: " + " • ".join(warnings)
    return base + (f'<div class="sl-total-note"><b>Totals check:</b> {escape(note)}</div>' if note else "")


def _render_card(row, intel=None, snap=None):
    status = core._state_label(row.get("status"))
    css_state = "live" if status == "LIVE" else "final" if status == "FINAL" else ""
    icon = "🔴" if status == "LIVE" else "🏁" if status == "FINAL" else "⏳"
    away = str(row.get("away_team", "Away")); home = str(row.get("home_team", "Home"))
    away_runs = row.get("away_runs"); home_runs = row.get("home_runs")
    show_score = status in {"LIVE", "FINAL"} and away_runs is not None and home_runs is not None
    away_center = f'<div class="sl-score">{int(away_runs or 0)}</div>' if show_score else ""
    home_center = f'<div class="sl-score">{int(home_runs or 0)}</div>' if show_score else ""
    inning = f" • {escape(str(row.get('inning_state') or ''))} {escape(str(row.get('inning') or ''))}" if status == "LIVE" else ""

    ctx = _ctx(row)
    asp = ctx.get("away_pitcher_stats") or ((intel or {}).get("away_sp") if intel else None)
    hsp = ctx.get("home_pitcher_stats") or ((intel or {}).get("home_sp") if intel else None)

    intel_html = ""
    if intel:
        fav = escape(str(intel.get("favorite") or "—")); p = float(intel.get("favorite_prob", 0) or 0)
        intel_html = (
            '<div class="sl-intel">'
            f'<div class="sl-metric green"><span>Model favorite</span><b>{fav} {p*100:.1f}%</b></div>'
            f'<div class="sl-metric"><span>Fair ML</span><b>{escape(str(intel.get("fair_ml") or "—"))}</b></div>'
            f'<div class="sl-metric cyan"><span>Projected score</span><b>{intel.get("away_score",0):.1f}–{intel.get("home_score",0):.1f}</b></div>'
            f'<div class="sl-metric"><span>Projected total</span><b>{intel.get("projected_total",0):.1f}</b></div>'
            '</div>'
            f'<div class="sl-form">Data {intel.get("data_score",0)}/9 • {escape(str(intel.get("confidence") or "—"))} confidence • Model lineups {"confirmed" if intel.get("lineups") else "not confirmed"}</div>'
        )

    checked = ctx.get("lineup_checked_at")
    lineups_html = (
        '<div class="sl-lineups">'
        + _lineup_html(away, ctx.get("away_lineup"), ctx.get("away_lineup_label"), bool(ctx.get("away_lineup_confirmed")), checked)
        + _lineup_html(home, ctx.get("home_lineup"), ctx.get("home_lineup_label"), bool(ctx.get("home_lineup_confirmed")), checked)
        + '</div>'
    )

    html = (
        f'<div class="sl-card {css_state}">'
        '<div class="sl-top">'
        f'<span class="sl-status {css_state}">{icon} {escape(status)}</span>'
        f'<span class="sl-time">{escape(str(row.get("first_pitch_et") or "TBD"))} ET{inning}</span></div>'
        '<div class="sl-teams">'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("away_team_id"))}"><div class="sl-teamname">{escape(away)}</div>{_team_record_html(ctx,"away")}{away_center}</div>'
        '<div class="sl-at">@</div>'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("home_team_id"))}"><div class="sl-teamname">{escape(home)}</div>{_team_record_html(ctx,"home")}{home_center}</div>'
        '</div>'
        f'<div class="sl-venue">📍 {escape(str(row.get("venue_name") or "Venue TBD"))}</div>'
        f'{_history_html(ctx, away, home)}'
        '<div class="sl-pitchers">'
        f'{player_ui._pitcher_html(row.get("away_pitcher", "TBD"), asp, "Away")}'
        f'{player_ui._pitcher_html(row.get("home_pitcher", "TBD"), hsp, "Home")}'
        '</div>'
        f'{lineups_html}{intel_html}{_market_html_v205(snap, away, home)}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _clean_key(value):
    if value is None:
        return None
    key = str(value).strip()
    if not key:
        return None
    upper = key.upper()
    if any(x in upper for x in ("PASTE_YOUR_KEY_HERE", "YOUR_API_KEY", "YOUR_KEY_HERE", "API_KEY_HERE")):
        return None
    return key


def _safe_snapshots(games_df, api_key, bookmakers):
    try:
        return slate_snapshots_for_games_v205(games_df, api_key, bookmakers)
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (401, 403):
            raise RuntimeError("Odds API rejected the saved key. Regenerate/save ODDS_API_IO_KEY in Streamlit Secrets, then refresh.") from None
        if status == 429:
            raise RuntimeError("Odds API free-plan quota is temporarily exhausted. Markets will resume after the provider resets the quota.") from None
        raise RuntimeError(f"Odds API is temporarily unavailable (HTTP {status or 'error'}).") from None
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("Odds feed could not refresh right now. Your API key was not displayed.") from None


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    global _CONTEXT
    st.markdown(core.SLATE_CSS + market_ui.EXTRA_CSS + player_ui.LINEUP_CSS + V205_CSS, unsafe_allow_html=True)
    rows = core._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    try:
        with st.spinner("Loading records • L10/L5 • H2H • lineups • pitcher stats..."):
            _CONTEXT = _build_context(games_df)
    except Exception:
        _CONTEXT = {}
        st.caption("⚠️ Team/player enrichment is temporarily incomplete; verified schedule and sportsbook markets can still load.")

    live = sum(core._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(core._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id") if r.get(k) is not None and not pd.isna(r.get(k)))
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V20.5</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Records + L10/L5 + H2H + probable starters + batting orders + model pulse + FanDuel/DraftKings markets with matching-line best-price protection.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>', unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v205_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v205_sort_{day}")

    raw = _raw_get_api_key(); key = _clean_key(raw); books = get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • ★ = best listed price only when the market line matches.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.5 SLATE INTELLIGENCE", use_container_width=True, type="primary", key=f"v205_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 Model pulse built {stamp or ''} • quick 40K/game preview • use individual market modules for deep simulations." + (f" • {err} game(s) skipped" if err else ""))

    filtered = []
    for r in rows:
        state = core._state_label(r.get("status"))
        if view == "Live" and state != "LIVE": continue
        if view == "Upcoming" and state != "PREGAME": continue
        if view == "Final" and state != "FINAL": continue
        filtered.append(r)

    if sort_by == "Strongest ML":
        filtered.sort(key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("favorite_prob", 0) or 0), reverse=True)
    elif sort_by == "Highest total":
        filtered.sort(key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("projected_total", 0) or 0), reverse=True)
    elif sort_by == "Data quality":
        filtered.sort(key=lambda r: int((intel.get(int(r["game_pk"])) or {}).get("data_score", 0) or 0), reverse=True)
    else:
        filtered.sort(key=lambda r: core._time_sort(r.get("first_pitch_et")))

    if not filtered:
        st.info(f"No {view.lower()} games are on this verified slate.")
        return

    snaps = {}
    active_rows = [r for r in filtered if core._state_label(r.get("status")) != "FINAL"]
    if key and active_rows:
        try:
            with st.spinner("Syncing full-game ML • run line • totals • best prices..."):
                snaps = _safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games • incompatible totals are filtered from full-game consensus • movement remains refresh-to-refresh.")

    for row in filtered:
        pk = int(row["game_pk"])
        _render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20.5 Slate: descriptive record/L10/L5/H2H context is separate from sportsbook prices. Projected lineups are never labeled confirmed. Best-price comparisons require matching market lines.")
