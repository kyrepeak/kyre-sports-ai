"""V20.1 MLB Slate Command Center.

Extends V20 with date-scoped pregame + live sportsbook odds directly on every
active game card while preserving the verified MLB schedule and quick model
pulse.
"""

from html import escape

import pandas as pd
import streamlit as st

import slate_hub_v20 as base
from live_odds_feed import get_api_key, get_bookmakers
from slate_odds_feed_v201 import slate_snapshots_for_games

MODEL_VERSION = "V20.1"

EXTRA_CSS = r"""
<style>
.sl-market{border-left:0!important;border:1px solid #24537d!important;border-radius:15px!important;background:linear-gradient(135deg,#081a2e,#091522)!important;padding:11px 12px!important}
.sl-market-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.sl-market-title{font-size:.7rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#59d7ff}.sl-market-age{font-size:.64rem;color:#7892af}.sl-bookrow{border-top:1px solid rgba(143,164,189,.13);padding:7px 0 3px;font-size:.7rem;line-height:1.55;color:#abc0d7}.sl-bookrow:first-of-type{border-top:0}.sl-book{display:inline-block;min-width:74px;color:white;font-weight:900}.sl-odds-label{color:#728aa6;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;font-weight:850}.sl-odds-strong{color:#f8fafc;font-weight:850}.sl-market-empty{margin-top:10px;border:1px dashed #29435f;border-radius:13px;padding:9px 11px;font-size:.68rem;color:#7890aa;background:#081321}
@media(max-width:700px){.sl-bookrow{font-size:.68rem}.sl-book{display:block;min-width:0;margin-bottom:2px}.sl-market-head{align-items:flex-start}}
</style>
"""


def _fmt_ml(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def _fresh_age(rows):
    ages = [r.get("age_seconds") for r in rows if r.get("age_seconds") is not None]
    return min(ages) if ages else None


def _market_html(snap, away, home):
    if not snap or not snap.get("rows"):
        return ""

    rows = snap.get("rows") or []
    age = _fresh_age(rows)
    age_text = f"{age}s old" if age is not None else "quote time n/a"
    event_status = str(snap.get("event_status") or "").lower()
    mode = "LIVE MARKET" if "live" in event_status else "PREGAME MARKET"

    book_rows = []
    for r in rows[:2]:
        book = escape(str(r.get("Book") or "Sportsbook"))
        away_ml = _fmt_ml(r.get("Away ML"))
        home_ml = _fmt_ml(r.get("Home ML"))
        away_rl = escape(str(r.get("Away RL") or "—"))
        home_rl = escape(str(r.get("Home RL") or "—"))
        over = escape(str(r.get("Over") or "—"))
        under = escape(str(r.get("Under") or "—"))
        book_rows.append(
            '<div class="sl-bookrow">'
            f'<span class="sl-book">{book}</span>'
            f'<span class="sl-odds-label"> ML </span><span class="sl-odds-strong">{escape(away)} {away_ml} · {escape(home)} {home_ml}</span><br>'
            f'<span class="sl-odds-label">RL </span><span class="sl-odds-strong">{away_rl} / {home_rl}</span> &nbsp; '
            f'<span class="sl-odds-label">TOTAL </span><span class="sl-odds-strong">{over} / {under}</span>'
            '</div>'
        )

    return (
        '<div class="sl-market">'
        '<div class="sl-market-head">'
        f'<span class="sl-market-title">📡 {mode}</span><span class="sl-market-age">{escape(age_text)}</span>'
        '</div>'
        + ''.join(book_rows)
        + '</div>'
    )


# V20's card renderer resolves this module-global helper on the base module at
# runtime, so patching it upgrades card presentation without duplicating cards.
base._market_html = _market_html


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(base.SLATE_CSS + EXTRA_CSS, unsafe_allow_html=True)
    rows = base._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    live = sum(base._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(base._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(
        1
        for r in rows
        for k in ("away_pitcher_id", "home_pitcher_id")
        if r.get(k) is not None and not pd.isna(r.get(k))
    )
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • ODDS SYNC</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Verified games + probable starters + model pulse + FanDuel/DraftKings pregame and live markets directly on each matchup card.</div>'
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
        view = st.radio(
            "Slate filter",
            ["All", "Live", "Upcoming", "Final"],
            horizontal=True,
            key=f"v201_filter_{day}",
        )
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v201_sort_{day}")

    key = get_api_key()
    books = get_bookmakers()
    if key:
        st.caption(f"📡 Odds connected permanently • {books} • V20.1 loads pregame markets for future slates and switches to in-play prices when games go live.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display pregame and live markets on slate cards.")

    if st.button(
        "⚡ BUILD V20.1 SLATE INTELLIGENCE",
        use_container_width=True,
        type="primary",
        key=f"v201_build_{day}",
    ):
        intel = base._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(
            f"🧠 Model pulse built {stamp or ''} • quick 40K/game preview • use individual market modules for final deep simulations."
            + (f" • {err} game(s) skipped" if err else "")
        )

    filtered = []
    for r in rows:
        state = base._state_label(r.get("status"))
        if view == "Live" and state != "LIVE":
            continue
        if view == "Upcoming" and state != "PREGAME":
            continue
        if view == "Final" and state != "FINAL":
            continue
        filtered.append(r)

    if sort_by == "Strongest ML":
        filtered.sort(
            key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("favorite_prob", 0) or 0),
            reverse=True,
        )
    elif sort_by == "Highest total":
        filtered.sort(
            key=lambda r: float((intel.get(int(r["game_pk"])) or {}).get("projected_total", 0) or 0),
            reverse=True,
        )
    elif sort_by == "Data quality":
        filtered.sort(
            key=lambda r: int((intel.get(int(r["game_pk"])) or {}).get("data_score", 0) or 0),
            reverse=True,
        )
    else:
        filtered.sort(key=lambda r: base._time_sort(r.get("first_pitch_et")))

    if not filtered:
        st.info(f"No {view.lower()} games are on this verified slate.")
        return

    snaps = {}
    active_rows = [r for r in filtered if base._state_label(r.get("status")) != "FINAL"]
    if key and active_rows:
        try:
            with st.spinner("Syncing slate sportsbook markets..."):
                snaps = slate_snapshots_for_games(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}

        st.caption(
            f"📈 Sportsbook markets matched {len(snaps)}/{len(active_rows)} active games on this slate. "
            "If a card has no odds yet, the connected books have not posted a matching market or the free feed has not published it yet."
        )

    for row in filtered:
        pk = int(row["game_pk"])
        base._render_card(row, intel.get(pk), snaps.get(pk))

    st.caption(
        "V20.1 Slate is the command-center view. Sportsbook odds are market context; quick model probabilities remain independent of sportsbook prices. Use Moneyline, Run Line, Totals and Live for deeper final simulations."
    )
