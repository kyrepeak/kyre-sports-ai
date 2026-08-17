"""V20.7 MLB Slate Command Center — adds an at-a-glance slate summary.

Builds on V20.6. The summary ranks the strongest model-vs-market comparison
for Moneyline, Run Line and Game Total across the currently displayed active
slate, plus the game with the strongest data-confidence profile. It does not
change any projection or sportsbook matching logic.
"""

from html import escape

import pandas as pd
import streamlit as st

import slate_hub_v20 as core
import slate_hub_v204 as player_ui
import slate_hub_v205 as base205
import slate_hub_v206 as base206
from live_odds_feed import get_api_key as _raw_get_api_key, get_bookmakers

MODEL_VERSION = "V20.7"

V207_CSS = r"""
<style>
.sl-summary-wrap{border:1px solid #22507b;background:radial-gradient(circle at 8% 0%,rgba(50,205,255,.10),transparent 34%),linear-gradient(145deg,#0b1b31,#071321);border-radius:18px;padding:12px;margin:12px 0 15px;box-shadow:0 14px 32px rgba(0,0,0,.18)}
.sl-summary-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:9px}.sl-summary-head b{color:#f8fafc;font-size:.86rem}.sl-summary-head span{color:#7891ab;font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900}
.sl-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.sl-summary-card{border:1px solid #243d5a;background:#081627;border-radius:13px;padding:9px 10px;min-width:0}.sl-summary-card.good{border-color:#17644b;background:linear-gradient(145deg,#08251d,#081627)}.sl-summary-card.watch{border-color:#705a1b;background:linear-gradient(145deg,#231c08,#081627)}.sl-summary-card.pass{border-color:#2b425d}.sl-summary-label{color:#7e96b0;font-size:.54rem;text-transform:uppercase;letter-spacing:.08em;font-weight:950}.sl-summary-pick{color:#f8fafc;font-size:.73rem;font-weight:920;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sl-summary-edge{font-size:1.02rem;font-weight:950;margin-top:2px;color:#d8e7f7}.sl-summary-card.good .sl-summary-edge{color:#70ebb3}.sl-summary-card.watch .sl-summary-edge{color:#ffe079}.sl-summary-game{color:#8fa5be;font-size:.58rem;line-height:1.4;margin-top:4px}.sl-summary-game b{color:#d9e9f9}.sl-summary-lock{border:1px dashed #29445f;background:#081523;border-radius:14px;padding:11px;color:#839ab3;font-size:.68rem;margin:10px 0 14px}
@media(max-width:760px){.sl-summary-grid{grid-template-columns:1fr 1fr}.sl-summary-wrap{padding:10px}}@media(max-width:480px){.sl-summary-grid{grid-template-columns:1fr}}
</style>
"""


def _summary_edge_card(title, entry):
    if not entry:
        return (
            '<div class="sl-summary-card pass">'
            f'<div class="sl-summary-label">{escape(title)}</div>'
            '<div class="sl-summary-pick">No matching edge yet</div>'
            '<div class="sl-summary-edge">—</div>'
            '<div class="sl-summary-game">Waiting for both model intelligence and a compatible sportsbook line.</div>'
            '</div>'
        )
    item = entry["item"]
    edge = float(item.get("edge", 0) or 0)
    css, grade = base206._edge_grade(edge)
    game = entry["game"]
    return (
        f'<div class="sl-summary-card {css}">'
        f'<div class="sl-summary-label">{escape(title)} • {escape(grade)}</div>'
        f'<div class="sl-summary-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-summary-edge">{edge*100:+.1f} pts</div>'
        f'<div class="sl-summary-game"><b>{escape(game)}</b><br>Model {float(item.get("model_prob",0) or 0)*100:.1f}% • {escape(str(item.get("book") or "Book"))} {base206._fmt_price(item.get("market_price"))}</div>'
        '</div>'
    )


def _confidence_card(entry):
    if not entry:
        return (
            '<div class="sl-summary-card pass"><div class="sl-summary-label">Highest confidence</div>'
            '<div class="sl-summary-pick">Model not built</div><div class="sl-summary-edge">—</div>'
            '<div class="sl-summary-game">Run the slate intelligence scan to score data quality.</div></div>'
        )
    intel = entry["intel"]
    game = entry["game"]
    fav = str(intel.get("favorite") or "—")
    favp = float(intel.get("favorite_prob", 0) or 0) * 100
    score = int(intel.get("data_score", 0) or 0)
    conf = str(intel.get("confidence") or "—")
    css = "good" if score >= 8 else "watch" if score >= 6 else "pass"
    return (
        f'<div class="sl-summary-card {css}"><div class="sl-summary-label">Highest data confidence</div>'
        f'<div class="sl-summary-pick">{escape(game)}</div><div class="sl-summary-edge">{score}/9 • {escape(conf)}</div>'
        f'<div class="sl-summary-game">Model favorite <b>{escape(fav)} {favp:.1f}%</b></div></div>'
    )


def _summary_entries(rows, intel, snaps):
    buckets = {"ml": [], "rl": [], "total": []}
    confidence = []
    for row in rows:
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        i = intel.get(pk)
        if not i:
            continue
        game = f'{row.get("away_team","Away")} @ {row.get("home_team","Home")}'
        confidence.append({"game": game, "intel": i})
        comp = base206._model_market(i, snaps.get(pk), row)
        if not comp:
            continue
        for market in ("ml", "rl", "total"):
            item = comp.get(market)
            if item:
                buckets[market].append({"game": game, "item": item})

    def strongest(items):
        if not items:
            return None
        return max(items, key=lambda x: float((x.get("item") or {}).get("edge", -99)))

    def conf_key(x):
        i = x["intel"]
        return (int(i.get("data_score", 0) or 0), abs(float(i.get("favorite_prob", .5) or .5) - .5))

    return {
        "ml": strongest(buckets["ml"]),
        "rl": strongest(buckets["rl"]),
        "total": strongest(buckets["total"]),
        "confidence": max(confidence, key=conf_key) if confidence else None,
    }


def _render_summary(rows, intel, snaps):
    if not intel:
        st.markdown(
            '<div class="sl-summary-lock">⚡ <b>Slate Summary:</b> run <b>BUILD V20.7 MODEL + MARKET INTELLIGENCE</b> to unlock the strongest Moneyline, Run Line, Total and highest-data-confidence game across the slate.</div>',
            unsafe_allow_html=True,
        )
        return
    entries = _summary_entries(rows, intel, snaps)
    html = (
        '<div class="sl-summary-wrap"><div class="sl-summary-head"><b>⚡ V20.7 Slate Summary</b><span>best current model-vs-market signals</span></div>'
        '<div class="sl-summary-grid">'
        + _summary_edge_card("Best ML edge", entries.get("ml"))
        + _summary_edge_card("Best Run Line edge", entries.get("rl"))
        + _summary_edge_card("Best Total edge", entries.get("total"))
        + _confidence_card(entries.get("confidence"))
        + '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(core.SLATE_CSS + base205.market_ui.EXTRA_CSS + player_ui.LINEUP_CSS + base205.V205_CSS + base206.V206_CSS + V207_CSS, unsafe_allow_html=True)
    rows = core._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    try:
        with st.spinner("Loading records • L10/L5 • H2H • lineups • pitcher stats..."):
            base205._CONTEXT = base205._build_context(games_df)
    except Exception:
        base205._CONTEXT = {}
        st.caption("⚠️ Team/player enrichment is temporarily incomplete; verified schedule and sportsbook markets can still load.")

    live = sum(core._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(core._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id") if r.get(k) is not None and not pd.isna(r.get(k)))
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V20.7</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Complete matchup context + sportsbook board + model-vs-market intelligence + an instant whole-slate signal summary.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>', unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v207_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v207_sort_{day}")

    raw = _raw_get_api_key(); key = base205._clean_key(raw); books = get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • model projections remain independent from sportsbook prices.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.7 MODEL + MARKET INTELLIGENCE", use_container_width=True, type="primary", key=f"v207_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 V20.7 pulse built {stamp or ''} • quick 40K/game navigation model • deep market pages remain the final-analysis engines." + (f" • {err} game(s) skipped" if err else ""))

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
                snaps = base205._safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games • incompatible totals stay filtered • summary and card edge grades use matching listed prices only.")

    _render_summary(active_rows, intel, snaps)

    for row in filtered:
        pk = int(row["game_pk"])
        base206._render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20.7 Slate Summary ranks the strongest currently available comparison in each market; it is not a guarantee or a substitute for the deep Moneyline/Run Line/Total engines. MODEL EDGE ≥5 pts • CLOSE/WATCH 2–4.9 pts • NO EDGE <2 pts.")
