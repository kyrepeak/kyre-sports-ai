"""V20.4 MLB Slate lineup + pitcher intelligence layer.

Keeps V20.3 sportsbook best-price/movement presentation and enriches every game
card with starter ERA/WHIP/K9/hand plus confirmed batting orders when MLB has
posted them. Future games fall back to the team's most recent official lineup
and are explicitly labeled PROJECTED.
"""

from html import escape

import pandas as pd
import streamlit as st

import slate_hub_v20 as core
import slate_hub_v203 as previous
from slate_lineup_v204 import build_slate_player_context

MODEL_VERSION = "V20.4"

_CONTEXT = {}

LINEUP_CSS = r"""
<style>
.sl-pitch{position:relative;overflow:hidden}.sl-pitch:after{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:#35c8ff;opacity:.7}.sl-pstats strong{color:#f7fbff}
.sl-lineups{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 2px}.sl-lineup{border:1px solid #203a59;background:linear-gradient(145deg,#09172a,#081421);border-radius:15px;padding:10px 11px}.sl-lineup-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.sl-lineup-team{font-size:.78rem;color:#f8fafc;font-weight:900}.sl-lineup-badge{font-size:.55rem;color:#74d9ff;letter-spacing:.055em;font-weight:900;text-transform:uppercase;text-align:right}.sl-lineup-badge.confirmed{color:#6ce7ac}.sl-hitrow{display:grid;grid-template-columns:20px minmax(0,1fr) 58px 58px;gap:6px;align-items:center;border-top:1px solid rgba(143,164,189,.10);padding:5px 0;font-size:.67rem}.sl-hitrow:first-of-type{border-top:0}.sl-spot{color:#64809d;font-weight:900}.sl-hname{color:#f6f9fd;font-weight:820;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sl-hstat{color:#9bb1c9;text-align:right}.sl-hstat b{color:#dcecff}.sl-more{margin-top:5px;border-top:1px solid rgba(143,164,189,.10);padding-top:5px}.sl-more summary{cursor:pointer;color:#4ed0ff;font-size:.65rem;font-weight:850;list-style:none}.sl-more summary::-webkit-details-marker{display:none}.sl-lineup-empty{font-size:.68rem;color:#8196af;line-height:1.45;padding:4px 0}.sl-source-note{font-size:.62rem;color:#7189a3;margin-top:7px;line-height:1.35}
@media(max-width:700px){.sl-lineups{grid-template-columns:1fr}.sl-hitrow{grid-template-columns:20px minmax(0,1fr) 56px 56px}.sl-lineup-badge{max-width:145px}.sl-pitchers{grid-template-columns:1fr 1fr!important}.sl-pname{font-size:.84rem!important}.sl-pstats{font-size:.65rem!important}}
@media(max-width:520px){.sl-pitchers{grid-template-columns:1fr!important}}
</style>
"""


def _safe_pk(row):
    try:
        return int(row.get("game_pk"))
    except Exception:
        return None


def _ctx(row):
    pk = _safe_pk(row)
    return _CONTEXT.get(pk, {}) if pk is not None else {}


def _fmt_pitch(v, digits=2):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "—"


def _pitcher_html(name, stats, side):
    p = stats or {}
    pname = str(p.get("name") or name or "TBD")
    hand = str(p.get("hand") or "?").upper()
    hand_label = f"{hand}HP" if hand in {"R", "L"} else "Hand —"
    era = _fmt_pitch(p.get("era"))
    whip = _fmt_pitch(p.get("whip"))
    k9 = _fmt_pitch(p.get("k9"), 1)
    record = ""
    if p:
        try:
            record = f" • {int(p.get('wins', 0))}-{int(p.get('losses', 0))}"
        except Exception:
            record = ""
    return (
        '<div class="sl-pitch">'
        f'<div class="sl-label">{escape(side)} probable starter</div>'
        f'<div class="sl-pname">{escape(pname)} <span style="color:#718ba7;font-size:.72rem">• {escape(hand_label)}</span></div>'
        f'<div class="sl-pstats"><strong>ERA {era}</strong> • WHIP {whip} • K/9 {k9}{escape(record)}</div>'
        '</div>'
    )


def _avg_text(v):
    try:
        n = float(v)
        return f"{n:.3f}".lstrip("0")
    except Exception:
        text = str(v or "—")
        return text[1:] if text.startswith("0.") else text


def _ops_text(v):
    try:
        n = float(v)
        return f"{n:.3f}".lstrip("0")
    except Exception:
        text = str(v or "—")
        return text[1:] if text.startswith("0.") else text


def _hit_rows(players):
    parts = []
    for player in players:
        parts.append(
            '<div class="sl-hitrow">'
            f'<span class="sl-spot">{int(player.get("spot") or 0)}</span>'
            f'<span class="sl-hname">{escape(str(player.get("player_name") or "Unknown"))}</span>'
            f'<span class="sl-hstat">AVG <b>{escape(_avg_text(player.get("avg")))}</b></span>'
            f'<span class="sl-hstat">OPS <b>{escape(_ops_text(player.get("ops")))}</b></span>'
            '</div>'
        )
    return "".join(parts)


def _lineup_html(team, players, label, confirmed):
    players = list(players or [])[:9]
    badge_cls = " confirmed" if confirmed else ""
    if not players:
        body = '<div class="sl-lineup-empty">MLB has not posted this batting order yet, and no recent official lineup was available for a safe projection.</div>'
        more = ""
    else:
        body = _hit_rows(players[:4])
        more = (
            '<details class="sl-more"><summary>＋ View hitters 5–9</summary>'
            + _hit_rows(players[4:])
            + '</details>'
            if len(players) > 4 else ""
        )
    note = (
        "Official batting order from this game feed."
        if confirmed
        else "Projected from the team's most recent official batting order; not a confirmed lineup."
    )
    return (
        '<div class="sl-lineup">'
        '<div class="sl-lineup-head">'
        f'<span class="sl-lineup-team">{escape(str(team))}</span>'
        f'<span class="sl-lineup-badge{badge_cls}">{escape(str(label or "LINEUP"))}</span>'
        '</div>'
        f'{body}{more}<div class="sl-source-note">{escape(note)}</div>'
        '</div>'
    )


def _render_card_v204(row, intel=None, snap=None):
    status = core._state_label(row.get("status"))
    css_state = "live" if status == "LIVE" else "final" if status == "FINAL" else ""
    icon = "🔴" if status == "LIVE" else "🏁" if status == "FINAL" else "⏳"
    away = str(row.get("away_team", "Away"))
    home = str(row.get("home_team", "Home"))
    away_runs = row.get("away_runs")
    home_runs = row.get("home_runs")
    show_score = status in {"LIVE", "FINAL"} and away_runs is not None and home_runs is not None
    away_center = f'<div class="sl-score">{int(away_runs or 0)}</div>' if show_score else ""
    home_center = f'<div class="sl-score">{int(home_runs or 0)}</div>' if show_score else ""
    inning = f" • {escape(str(row.get('inning_state') or ''))} {escape(str(row.get('inning') or ''))}" if status == "LIVE" else ""

    ctx = _ctx(row)
    asp = ctx.get("away_pitcher_stats") or ((intel or {}).get("away_sp") if intel else None)
    hsp = ctx.get("home_pitcher_stats") or ((intel or {}).get("home_sp") if intel else None)

    intel_html = ""
    if intel:
        fav = escape(str(intel.get("favorite") or "—"))
        p = float(intel.get("favorite_prob", 0) or 0)
        away_form = intel.get("away_recent")
        home_form = intel.get("home_recent")
        intel_html = (
            '<div class="sl-intel">'
            f'<div class="sl-metric green"><span>Model favorite</span><b>{fav} {p*100:.1f}%</b></div>'
            f'<div class="sl-metric"><span>Fair ML</span><b>{escape(str(intel.get("fair_ml") or "—"))}</b></div>'
            f'<div class="sl-metric cyan"><span>Projected score</span><b>{intel.get("away_score",0):.1f}–{intel.get("home_score",0):.1f}</b></div>'
            f'<div class="sl-metric"><span>Projected total</span><b>{intel.get("projected_total",0):.1f}</b></div>'
            '</div>'
            f'<div class="sl-form"><b>{escape(away)} L10:</b> {core._record(away_form)} • diff {core._fmt((away_form or {}).get("run_diff_per_game"),2)} &nbsp; | &nbsp; '
            f'<b>{escape(home)} L10:</b> {core._record(home_form)} • diff {core._fmt((home_form or {}).get("run_diff_per_game"),2)}<br>'
            f'Data {intel.get("data_score",0)}/9 • {escape(str(intel.get("confidence") or "—"))} confidence • Lineups {"confirmed" if intel.get("lineups") else "not confirmed"}</div>'
        )

    lineups_html = (
        '<div class="sl-lineups">'
        + _lineup_html(away, ctx.get("away_lineup"), ctx.get("away_lineup_label"), bool(ctx.get("away_lineup_confirmed")))
        + _lineup_html(home, ctx.get("home_lineup"), ctx.get("home_lineup_label"), bool(ctx.get("home_lineup_confirmed")))
        + '</div>'
    )

    html = (
        f'<div class="sl-card {css_state}">'
        '<div class="sl-top">'
        f'<span class="sl-status {css_state}">{icon} {escape(status)}</span>'
        f'<span class="sl-time">{escape(str(row.get("first_pitch_et") or "TBD"))} ET{inning}</span></div>'
        '<div class="sl-teams">'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("away_team_id"))}"><div class="sl-teamname">{escape(away)}</div>{away_center}</div>'
        '<div class="sl-at">@</div>'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("home_team_id"))}"><div class="sl-teamname">{escape(home)}</div>{home_center}</div>'
        '</div>'
        f'<div class="sl-venue">📍 {escape(str(row.get("venue_name") or "Venue TBD"))}</div>'
        '<div class="sl-pitchers">'
        f'{_pitcher_html(row.get("away_pitcher", "TBD"), asp, "Away")}'
        f'{_pitcher_html(row.get("home_pitcher", "TBD"), hsp, "Home")}'
        '</div>'
        f'{lineups_html}{intel_html}{core._market_html(snap, away, home)}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


core._render_card = _render_card_v204


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    global _CONTEXT

    st.markdown(core.SLATE_CSS + previous.EXTRA_CSS + LINEUP_CSS, unsafe_allow_html=True)
    rows = core._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    try:
        with st.spinner("Loading MLB lineups, batting averages and starter stats..."):
            _CONTEXT = build_slate_player_context(games_df)
    except Exception:
        _CONTEXT = {}
        st.caption("⚠️ Player-detail enrichment is temporarily unavailable; the verified slate and sportsbook markets will still load.")

    day = str(rows[0].get("game_date") or "")
    live = sum(core._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(core._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(
        1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id")
        if r.get(k) is not None and not pd.isna(r.get(k))
    )
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • LINEUPS + ODDS</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Verified games + probable starters with ERA/WHIP/K9 + batting orders with AVG/OPS + FanDuel/DraftKings prices + best-price and movement tracking.</div>'
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
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v204_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v204_sort_{day}")

    raw = previous._raw_get_api_key()
    key = previous._get_api_key()
    books = previous.get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • ★ marks best listed price • 🧬 V20.4 lineups automatically switch from projected to confirmed when MLB posts them.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.4 SLATE INTELLIGENCE", use_container_width=True, type="primary", key=f"v204_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(
            f"🧠 Model pulse built {stamp or ''} • quick 40K/game preview • use individual market modules for final deep simulations."
            + (f" • {err} game(s) skipped" if err else "")
        )

    filtered = []
    for r in rows:
        state = core._state_label(r.get("status"))
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
        filtered.sort(key=lambda r: core._time_sort(r.get("first_pitch_et")))

    if not filtered:
        st.info(f"No {view.lower()} games are on this verified slate.")
        return

    snaps = {}
    active_rows = [r for r in filtered if core._state_label(r.get("status")) != "FINAL"]
    if key and active_rows:
        try:
            with st.spinner("Syncing ML • run line • totals • best prices..."):
                snaps = previous._safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(
            f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games • player stats come from official MLB feeds • projected batting orders are clearly marked until confirmed."
        )

    for row in filtered:
        pk = int(row["game_pk"])
        core._render_card(row, intel.get(pk), snaps.get(pk))

    st.caption(
        "V20.4 Slate Command Center • confirmed lineups are official MLB batting orders • PROJECTED lineups are the team's most recent official order and are not treated as confirmed • sportsbook prices are market context, while model projections remain independent."
    )
