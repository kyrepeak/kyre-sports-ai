"""V20.6 MLB Slate Command Center.

Builds on V20.5 and turns the slate into a true model-vs-market dashboard.
Sportsbook prices remain outputs/comparison inputs only: they never alter the
pregame run model. V20.6 adds compact ML/run-line/total probability comparisons,
model fair odds, listed implied probability, edge grading and a cleaner model
snapshot on every enriched game card.
"""

from html import escape

import pandas as pd
import streamlit as st

import slate_hub_v20 as core
import slate_hub_v204 as player_ui
import slate_hub_v205 as base
from engine import odds
from live_odds_feed import get_api_key as _raw_get_api_key, get_bookmakers
from spread_engine import _stable_seed, simulate_run_line
from totals_hub_v17 import simulate_total

MODEL_VERSION = "V20.6"

V206_CSS = r"""
<style>
.sl-model-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin:13px 0 7px}.sl-model-head b{font-size:.78rem;color:#f8fafc}.sl-model-head span{font-size:.60rem;color:#7890aa;text-transform:uppercase;letter-spacing:.07em;font-weight:850}
.sl-model-snapshot{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:7px 0 10px}.sl-model-cell{border:1px solid #213d5d;background:#08182a;border-radius:12px;padding:8px 9px}.sl-model-cell span{display:block;color:#7890aa;font-size:.56rem;text-transform:uppercase;letter-spacing:.06em;font-weight:900}.sl-model-cell b{display:block;color:#f8fafc;font-size:.80rem;margin-top:2px}.sl-model-cell.cyan b{color:#64ddff}.sl-model-cell.green b{color:#70ebb4}
.sl-edge-board{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:7px 0 11px}.sl-edge{border:1px solid #253b56;background:#081422;border-radius:14px;padding:9px 10px;min-height:112px}.sl-edge.good{border-color:#17634b;background:linear-gradient(145deg,#08241c,#081723)}.sl-edge.watch{border-color:#6a571c;background:linear-gradient(145deg,#211b09,#081723)}.sl-edge.pass{border-color:#2b4058}.sl-edge-top{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}.sl-edge-market{font-size:.58rem;color:#7e96b1;text-transform:uppercase;letter-spacing:.07em;font-weight:950}.sl-edge-grade{font-size:.54rem;font-weight:950;border-radius:999px;padding:3px 6px;white-space:nowrap}.sl-edge.good .sl-edge-grade{background:#0b432f;color:#79efb9}.sl-edge.watch .sl-edge-grade{background:#4a3b0d;color:#ffe079}.sl-edge.pass .sl-edge-grade{background:#17283b;color:#a9bdd2}.sl-edge-pick{font-size:.78rem;color:#f8fafc;font-weight:920;margin-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sl-edge-main{font-size:1.03rem;color:white;font-weight:950;margin-top:2px}.sl-edge.good .sl-edge-main{color:#73efb9}.sl-edge.watch .sl-edge-main{color:#ffe079}.sl-edge-detail{font-size:.60rem;color:#91a8c0;line-height:1.5;margin-top:5px}.sl-edge-detail b{color:#dcecff}.sl-edge-lock{border:1px dashed #29435f;border-radius:13px;padding:9px 11px;color:#7f96b0;background:#081321;font-size:.67rem;margin:9px 0}.sl-edge-note{font-size:.59rem;color:#71869e;line-height:1.4;margin:3px 0 10px}
@media(max-width:760px){.sl-edge-board{grid-template-columns:1fr}.sl-model-snapshot{grid-template-columns:1fr 1fr}.sl-edge{min-height:0}}
</style>
"""


def _implied_american(price):
    try:
        p = float(price)
    except Exception:
        return None
    if p == 0:
        return None
    return 100.0 / (p + 100.0) if p > 0 else (-p) / ((-p) + 100.0)


def _edge_grade(edge):
    if edge is None:
        return "pass", "NO MARKET"
    if edge >= 0.05:
        return "good", "MODEL EDGE"
    if edge >= 0.02:
        return "watch", "CLOSE / WATCH"
    return "pass", "NO EDGE"


def _fmt_line(value):
    try:
        return f"{float(value):+g}"
    except Exception:
        return "—"


def _fmt_price(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def _safe_prob(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _quick_market_probabilities(game_pk, away_mean, home_mean, away_rl_line, home_rl_line, total_line):
    """40K settlement sims using the same run-distribution family as the deep modules."""
    out = {}
    n = 40_000
    away_mean = float(away_mean)
    home_mean = float(home_mean)

    if away_rl_line is not None:
        sim = simulate_run_line(
            away_mean,
            home_mean,
            n,
            _stable_seed(int(game_pk), 2061 + int(round(float(away_rl_line) * 10))),
            "away",
            float(away_rl_line),
        )
        settled = max(1.0 - float(sim.get("p_push", 0) or 0), 1e-9)
        out["away_rl_prob"] = float(sim.get("p_cover", 0) or 0) / settled
        out["away_rl_push"] = float(sim.get("p_push", 0) or 0)

    if home_rl_line is not None:
        sim = simulate_run_line(
            away_mean,
            home_mean,
            n,
            _stable_seed(int(game_pk), 2062 + int(round(float(home_rl_line) * 10))),
            "home",
            float(home_rl_line),
        )
        settled = max(1.0 - float(sim.get("p_push", 0) or 0), 1e-9)
        out["home_rl_prob"] = float(sim.get("p_cover", 0) or 0) / settled
        out["home_rl_push"] = float(sim.get("p_push", 0) or 0)

    if total_line is not None:
        sim = simulate_total(
            away_mean,
            home_mean,
            float(total_line),
            n,
            _stable_seed(int(game_pk), 2063 + int(round(float(total_line) * 10))),
        )
        settled = max(1.0 - float(sim.get("p_push", 0) or 0), 1e-9)
        out["over_prob"] = float(sim.get("p_over", 0) or 0) / settled
        out["under_prob"] = float(sim.get("p_under", 0) or 0) / settled
        out["total_push"] = float(sim.get("p_push", 0) or 0)
    return out


def _candidate(label, model_prob, market_item, line=None):
    if market_item is None or model_prob is None:
        return None
    price = market_item.get("price")
    implied = _implied_american(price)
    if implied is None:
        return None
    p = _safe_prob(model_prob)
    if p is None:
        return None
    return {
        "label": label,
        "model_prob": p,
        "fair": odds(p),
        "market_price": price,
        "book": market_item.get("book") or "Sportsbook",
        "line": market_item.get("line") if market_item.get("line") is not None else line,
        "market_implied": implied,
        "edge": p - implied,
    }


def _pick_best(candidates):
    candidates = [x for x in candidates if x]
    if not candidates:
        return None
    return max(candidates, key=lambda x: float(x.get("edge", -99)))


def _model_market(intel, snap, row):
    if not intel:
        return None
    away = str(row.get("away_team", "Away"))
    home = str(row.get("home_team", "Home"))
    fav = str(intel.get("favorite") or "")
    fav_p = _safe_prob(intel.get("favorite_prob"))
    if fav_p is None:
        return None
    if fav == home:
        home_p, away_p = fav_p, 1.0 - fav_p
    elif fav == away:
        away_p, home_p = fav_p, 1.0 - fav_p
    else:
        home_p = away_p = 0.5

    best = (snap or {}).get("best") or {}
    ml = _pick_best([
        _candidate(away, away_p, best.get("away_ml")),
        _candidate(home, home_p, best.get("home_ml")),
    ])

    away_rl = best.get("away_rl")
    home_rl = best.get("home_rl")
    total_line = best.get("consensus_total")
    sims = _quick_market_probabilities(
        int(row.get("game_pk")),
        float(intel.get("away_score", 0) or 0),
        float(intel.get("home_score", 0) or 0),
        (away_rl or {}).get("line"),
        (home_rl or {}).get("line"),
        total_line,
    )

    rl = _pick_best([
        _candidate(f"{away} {_fmt_line((away_rl or {}).get('line'))}", sims.get("away_rl_prob"), away_rl),
        _candidate(f"{home} {_fmt_line((home_rl or {}).get('line'))}", sims.get("home_rl_prob"), home_rl),
    ])
    total = _pick_best([
        _candidate(f"OVER {float(total_line):g}" if total_line is not None else "OVER", sims.get("over_prob"), best.get("over")),
        _candidate(f"UNDER {float(total_line):g}" if total_line is not None else "UNDER", sims.get("under_prob"), best.get("under")),
    ])
    return {"ml": ml, "rl": rl, "total": total, "sims": sims, "away_prob": away_p, "home_prob": home_p}


def _edge_card(title, item):
    if not item:
        return (
            '<div class="sl-edge pass"><div class="sl-edge-top">'
            f'<span class="sl-edge-market">{escape(title)}</span><span class="sl-edge-grade">NO MARKET</span></div>'
            '<div class="sl-edge-pick">Waiting for matching line</div>'
            '<div class="sl-edge-detail">The model stays independent; a comparison appears when a compatible sportsbook market is posted.</div></div>'
        )
    css, grade = _edge_grade(item.get("edge"))
    edge_pts = float(item.get("edge", 0) or 0) * 100
    model_p = float(item.get("model_prob", 0) or 0) * 100
    implied = float(item.get("market_implied", 0) or 0) * 100
    book = escape(str(item.get("book") or "Sportsbook"))
    return (
        f'<div class="sl-edge {css}">'
        '<div class="sl-edge-top">'
        f'<span class="sl-edge-market">{escape(title)}</span><span class="sl-edge-grade">{escape(grade)}</span></div>'
        f'<div class="sl-edge-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-edge-main">{edge_pts:+.1f} pts</div>'
        f'<div class="sl-edge-detail">Model <b>{model_p:.1f}%</b> • Fair <b>{escape(str(item.get("fair") or "—"))}</b><br>'
        f'{book} <b>{_fmt_price(item.get("market_price"))}</b> • listed implied {implied:.1f}%</div>'
        '</div>'
    )


def _model_snapshot_html(intel, comparison):
    if not intel:
        return '<div class="sl-edge-lock">⚡ Tap <b>BUILD V20.6 MODEL + MARKET INTELLIGENCE</b> above to unlock projected score, fair prices and model-vs-market grading.</div>'
    fav = escape(str(intel.get("favorite") or "—"))
    fav_p = float(intel.get("favorite_prob", 0) or 0) * 100
    return (
        '<div class="sl-model-head"><b>🧠 V20.6 Model Snapshot</b><span>sportsbook odds do not drive projection</span></div>'
        '<div class="sl-model-snapshot">'
        f'<div class="sl-model-cell green"><span>Model favorite</span><b>{fav} {fav_p:.1f}%</b></div>'
        f'<div class="sl-model-cell"><span>Fair ML</span><b>{escape(str(intel.get("fair_ml") or "—"))}</b></div>'
        f'<div class="sl-model-cell cyan"><span>Projected score</span><b>{float(intel.get("away_score",0) or 0):.1f}–{float(intel.get("home_score",0) or 0):.1f}</b></div>'
        f'<div class="sl-model-cell"><span>Projected total</span><b>{float(intel.get("projected_total",0) or 0):.1f}</b></div>'
        '</div>'
        '<div class="sl-model-head"><b>📊 Model vs Market</b><span>best listed matching price</span></div>'
        '<div class="sl-edge-board">'
        + _edge_card("Moneyline", (comparison or {}).get("ml"))
        + _edge_card("Run Line", (comparison or {}).get("rl"))
        + _edge_card("Game Total", (comparison or {}).get("total"))
        + '</div>'
        f'<div class="sl-edge-note">Quick comparison uses the V20 40K/game slate projection plus 40K settlement simulations at the posted run line/total. Deep market pages remain the final-analysis engines. Data {int(intel.get("data_score",0) or 0)}/9 • {escape(str(intel.get("confidence") or "—"))} confidence.</div>'
    )


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

    ctx = base._ctx(row)
    asp = ctx.get("away_pitcher_stats") or ((intel or {}).get("away_sp") if intel else None)
    hsp = ctx.get("home_pitcher_stats") or ((intel or {}).get("home_sp") if intel else None)
    checked = ctx.get("lineup_checked_at")
    lineups_html = (
        '<div class="sl-lineups">'
        + base._lineup_html(away, ctx.get("away_lineup"), ctx.get("away_lineup_label"), bool(ctx.get("away_lineup_confirmed")), checked)
        + base._lineup_html(home, ctx.get("home_lineup"), ctx.get("home_lineup_label"), bool(ctx.get("home_lineup_confirmed")), checked)
        + '</div>'
    )
    comparison = _model_market(intel, snap, row) if intel else None

    html = (
        f'<div class="sl-card {css_state}">'
        '<div class="sl-top">'
        f'<span class="sl-status {css_state}">{icon} {escape(status)}</span>'
        f'<span class="sl-time">{escape(str(row.get("first_pitch_et") or "TBD"))} ET{inning}</span></div>'
        '<div class="sl-teams">'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("away_team_id"))}"><div class="sl-teamname">{escape(away)}</div>{base._team_record_html(ctx,"away")}{away_center}</div>'
        '<div class="sl-at">@</div>'
        f'<div class="sl-team"><img class="sl-logo" src="{core._logo(row.get("home_team_id"))}"><div class="sl-teamname">{escape(home)}</div>{base._team_record_html(ctx,"home")}{home_center}</div>'
        '</div>'
        f'<div class="sl-venue">📍 {escape(str(row.get("venue_name") or "Venue TBD"))}</div>'
        f'{base._history_html(ctx, away, home)}'
        '<div class="sl-pitchers">'
        f'{player_ui._pitcher_html(row.get("away_pitcher", "TBD"), asp, "Away")}'
        f'{player_ui._pitcher_html(row.get("home_pitcher", "TBD"), hsp, "Home")}'
        '</div>'
        f'{lineups_html}{_model_snapshot_html(intel, comparison)}{base._market_html_v205(snap, away, home)}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(core.SLATE_CSS + base.market_ui.EXTRA_CSS + player_ui.LINEUP_CSS + base.V205_CSS + V206_CSS, unsafe_allow_html=True)
    rows = core._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    try:
        with st.spinner("Loading records • L10/L5 • H2H • lineups • pitcher stats..."):
            base._CONTEXT = base._build_context(games_df)
    except Exception:
        base._CONTEXT = {}
        st.caption("⚠️ Team/player enrichment is temporarily incomplete; verified schedule and sportsbook markets can still load.")

    live = sum(core._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(core._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id") if r.get(k) is not None and not pd.isna(r.get(k)))
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V20.6</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Complete game context + projected lineups + sportsbook board + model-vs-market ML/run-line/total intelligence in one mobile-first card.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>', unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v206_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v206_sort_{day}")

    raw = _raw_get_api_key(); key = base._clean_key(raw); books = get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • V20.6 compares the independent model with the best listed matching price; sportsbook prices never alter the projection.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.6 MODEL + MARKET INTELLIGENCE", use_container_width=True, type="primary", key=f"v206_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 V20.6 pulse built {stamp or ''} • quick 40K/game navigation model • deep Moneyline/Run Line/Total pages remain the final-analysis engines." + (f" • {err} game(s) skipped" if err else ""))

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
            with st.spinner("Syncing full-game ML • run line • totals • best prices..."):
                snaps = base._safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games • incompatible totals stay filtered • edge grades are model probability minus the listed price's implied probability.")

    for row in filtered:
        pk = int(row["game_pk"])
        _render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20.6 Slate is a navigation/decision-support layer: MODEL EDGE ≥5 pts • CLOSE/WATCH 2–4.9 pts • NO EDGE <2 pts. Listed implied probability includes sportsbook hold; deep market modules remain the final probability engines.")
