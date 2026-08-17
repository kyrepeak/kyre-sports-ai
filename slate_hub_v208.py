"""V20.8 MLB Slate Command Center — no-vig calibration protection.

Builds on V20.7. V20.8 keeps the independent projection stack unchanged, but
makes model-vs-market grading more honest by displaying both raw listed-edge
and same-book two-way no-vig edge. Summary/card grades and rankings prefer the
no-vig edge when both sides of a matching market are available. It also exposes
an exact sportsbook quote timestamp plus quote age when supplied by the feed.
"""

from html import escape

import pandas as pd
import streamlit as st

import slate_hub_v20 as core
import slate_hub_v204 as player_ui
import slate_hub_v205 as base205
import slate_hub_v206 as base206
import slate_hub_v207 as base207
from engine import odds
from live_odds_feed import get_api_key as _raw_get_api_key, get_bookmakers

MODEL_VERSION = "V20.8"

V208_CSS = r"""
<style>
.sl-nv-badge{display:inline-flex;align-items:center;border:1px solid #2f526f;background:#0a1c2c;color:#8fe8ff;border-radius:999px;padding:3px 7px;font-size:.52rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;margin-left:4px}
.sl-edge-cal{font-size:.61rem;color:#a8bdd1;line-height:1.55;margin-top:5px}.sl-edge-cal b{color:#e8f6ff}.sl-edge-cal .nv{color:#77efb9;font-weight:950}.sl-edge-cal .listed{color:#ffe079;font-weight:850}.sl-fresh{color:#76a9cb;font-size:.56rem;margin-top:5px}.sl-fresh b{color:#b9dcf2}.sl-cal-note{border:1px solid #234965;background:#081a29;border-radius:12px;padding:8px 10px;color:#93abc2;font-size:.62rem;line-height:1.45;margin:7px 0 11px}.sl-cal-note b{color:#bcecff}
.sl-summary-cal{font-size:.56rem;color:#9ab1c8;line-height:1.45;margin-top:4px}.sl-summary-cal .nv{color:#72ebb4;font-weight:950}.sl-summary-cal .raw{color:#ffe079;font-weight:850}.sl-summary-fresh{font-size:.53rem;color:#6f9bbb;margin-top:4px}
</style>
"""


def _implied(price):
    return base206._implied_american(price)


def _same_book_row(snap, market_item, market, side):
    if not snap or not market_item:
        return None
    book = str(market_item.get("book") or "")
    target_line = market_item.get("line")
    for row in snap.get("rows") or []:
        if str(row.get("Book") or "") != book:
            continue
        if market == "rl":
            field = "away_rl_line" if side == "away" else "home_rl_line"
            line = row.get(field)
            if target_line is not None and (line is None or abs(float(line) - float(target_line)) > 1e-6):
                continue
        elif market == "total":
            line = row.get("total_line")
            if target_line is not None and (line is None or abs(float(line) - float(target_line)) > 1e-6):
                continue
        return row
    return None


def _freshness(row):
    if not row:
        return {"age_seconds": None, "updated_at_et": None}
    age = row.get("age_seconds")
    try:
        age = max(0, int(round(float(age)))) if age is not None else None
    except Exception:
        age = None
    stamp = None
    raw = row.get("updatedAt")
    if raw:
        try:
            ts = pd.to_datetime(raw, utc=True)
            stamp = ts.tz_convert("America/New_York").strftime("%I:%M:%S %p ET").lstrip("0")
        except Exception:
            stamp = None
    return {"age_seconds": age, "updated_at_et": stamp}


def _pair_prices(row, market, side):
    if not row:
        return None, None
    if market == "ml":
        selected = row.get("Away ML") if side == "away" else row.get("Home ML")
        opposite = row.get("Home ML") if side == "away" else row.get("Away ML")
    elif market == "rl":
        selected = row.get("away_rl_price") if side == "away" else row.get("home_rl_price")
        opposite = row.get("home_rl_price") if side == "away" else row.get("away_rl_price")
    else:
        selected = row.get("over_price") if side == "over" else row.get("under_price")
        opposite = row.get("under_price") if side == "over" else row.get("over_price")
    return selected, opposite


def _candidate_v208(label, model_prob, market_item, snap, market, side):
    if market_item is None or model_prob is None:
        return None
    p = base206._safe_prob(model_prob)
    if p is None:
        return None
    listed_price = market_item.get("price")
    listed_implied = _implied(listed_price)
    if listed_implied is None:
        return None

    row = _same_book_row(snap, market_item, market, side)
    selected_price, opposite_price = _pair_prices(row, market, side)
    selected_implied = _implied(selected_price)
    opposite_implied = _implied(opposite_price)
    no_vig_prob = None
    hold = None
    if selected_implied is not None and opposite_implied is not None:
        denom = selected_implied + opposite_implied
        if denom > 0:
            no_vig_prob = selected_implied / denom
            hold = denom - 1.0

    listed_edge = p - listed_implied
    no_vig_edge = p - no_vig_prob if no_vig_prob is not None else None
    fresh = _freshness(row)
    return {
        "label": label,
        "model_prob": p,
        "fair": odds(p),
        "market_price": listed_price,
        "book": market_item.get("book") or "Sportsbook",
        "line": market_item.get("line"),
        "market_implied": listed_implied,
        "listed_edge": listed_edge,
        "no_vig_prob": no_vig_prob,
        "no_vig_edge": no_vig_edge,
        "hold": hold,
        "edge": no_vig_edge if no_vig_edge is not None else listed_edge,
        **fresh,
    }


def _pick_best(items):
    items = [x for x in items if x]
    if not items:
        return None
    return max(items, key=lambda x: float(x.get("edge", -99)))


def _model_market_v208(intel, snap, row):
    if not intel:
        return None
    away = str(row.get("away_team", "Away"))
    home = str(row.get("home_team", "Home"))
    fav = str(intel.get("favorite") or "")
    fav_p = base206._safe_prob(intel.get("favorite_prob"))
    if fav_p is None:
        return None
    if fav == home:
        home_p, away_p = fav_p, 1.0 - fav_p
    elif fav == away:
        away_p, home_p = fav_p, 1.0 - fav_p
    else:
        away_p = home_p = 0.5

    best = (snap or {}).get("best") or {}
    ml = _pick_best([
        _candidate_v208(away, away_p, best.get("away_ml"), snap, "ml", "away"),
        _candidate_v208(home, home_p, best.get("home_ml"), snap, "ml", "home"),
    ])

    away_rl = best.get("away_rl")
    home_rl = best.get("home_rl")
    total_line = best.get("consensus_total")
    sims = base206._quick_market_probabilities(
        int(row.get("game_pk")),
        float(intel.get("away_score", 0) or 0),
        float(intel.get("home_score", 0) or 0),
        (away_rl or {}).get("line"),
        (home_rl or {}).get("line"),
        total_line,
    )

    rl = _pick_best([
        _candidate_v208(f"{away} {base206._fmt_line((away_rl or {}).get('line'))}", sims.get("away_rl_prob"), away_rl, snap, "rl", "away"),
        _candidate_v208(f"{home} {base206._fmt_line((home_rl or {}).get('line'))}", sims.get("home_rl_prob"), home_rl, snap, "rl", "home"),
    ])
    total = _pick_best([
        _candidate_v208(f"OVER {float(total_line):g}" if total_line is not None else "OVER", sims.get("over_prob"), best.get("over"), snap, "total", "over"),
        _candidate_v208(f"UNDER {float(total_line):g}" if total_line is not None else "UNDER", sims.get("under_prob"), best.get("under"), snap, "total", "under"),
    ])
    return {"ml": ml, "rl": rl, "total": total, "sims": sims, "away_prob": away_p, "home_prob": home_p}


def _fresh_text(item):
    if not item:
        return ""
    stamp = item.get("updated_at_et")
    age = item.get("age_seconds")
    if stamp and age is not None:
        return f"Quote {stamp} • {age}s old"
    if stamp:
        return f"Quote {stamp}"
    if age is not None:
        return f"Quote {age}s old"
    return "Quote time unavailable"


def _edge_card_v208(title, item):
    if not item:
        return (
            '<div class="sl-edge pass"><div class="sl-edge-top">'
            f'<span class="sl-edge-market">{escape(title)}</span><span class="sl-edge-grade">NO MARKET</span></div>'
            '<div class="sl-edge-pick">Waiting for matching line</div>'
            '<div class="sl-edge-detail">A calibrated comparison appears when the model and a compatible two-way sportsbook market are both available.</div></div>'
        )
    edge = float(item.get("edge", 0) or 0)
    css, grade = base206._edge_grade(edge)
    nv = item.get("no_vig_edge")
    raw = float(item.get("listed_edge", 0) or 0)
    nv_prob = item.get("no_vig_prob")
    hold = item.get("hold")
    model_p = float(item.get("model_prob", 0) or 0) * 100
    book = escape(str(item.get("book") or "Sportsbook"))
    primary = float(nv if nv is not None else raw) * 100
    nv_line = f'<span class="nv">No-vig {float(nv)*100:+.1f} pts</span>' if nv is not None else '<span class="nv">No-vig unavailable</span>'
    fair_market = f'{float(nv_prob)*100:.1f}%' if nv_prob is not None else "—"
    hold_txt = f'{float(hold)*100:.1f}%' if hold is not None else "—"
    return (
        f'<div class="sl-edge {css}">'
        f'<div class="sl-edge-top"><span class="sl-edge-market">{escape(title)}</span><span class="sl-edge-grade">{escape(grade)}</span></div>'
        f'<div class="sl-edge-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-edge-main">{primary:+.1f} pts</div>'
        f'<div class="sl-edge-detail">Model <b>{model_p:.1f}%</b> • Fair <b>{escape(str(item.get("fair") or "—"))}</b><br>{book} <b>{base206._fmt_price(item.get("market_price"))}</b></div>'
        f'<div class="sl-edge-cal">{nv_line} • <span class="listed">Listed {raw*100:+.1f} pts</span><br>No-vig market <b>{fair_market}</b> • book hold <b>{hold_txt}</b></div>'
        f'<div class="sl-fresh">📡 <b>{escape(_fresh_text(item))}</b></div>'
        '</div>'
    )


def _model_snapshot_html_v208(intel, comparison):
    if not intel:
        return '<div class="sl-edge-lock">⚡ Tap <b>BUILD V20.8 MODEL + MARKET INTELLIGENCE</b> above to unlock projected score, fair prices and no-vig model-vs-market grading.</div>'
    fav = escape(str(intel.get("favorite") or "—"))
    fav_p = float(intel.get("favorite_prob", 0) or 0) * 100
    return (
        '<div class="sl-model-head"><b>🧠 V20.8 Model Snapshot</b><span>projection remains market-independent</span></div>'
        '<div class="sl-model-snapshot">'
        f'<div class="sl-model-cell green"><span>Model favorite</span><b>{fav} {fav_p:.1f}%</b></div>'
        f'<div class="sl-model-cell"><span>Fair ML</span><b>{escape(str(intel.get("fair_ml") or "—"))}</b></div>'
        f'<div class="sl-model-cell cyan"><span>Projected score</span><b>{float(intel.get("away_score",0) or 0):.1f}–{float(intel.get("home_score",0) or 0):.1f}</b></div>'
        f'<div class="sl-model-cell"><span>Projected total</span><b>{float(intel.get("projected_total",0) or 0):.1f}</b></div>'
        '</div>'
        '<div class="sl-model-head"><b>📊 Model vs Market <span class="sl-nv-badge">No-vig calibrated</span></b><span>same-book matching-line normalization</span></div>'
        '<div class="sl-edge-board">'
        + _edge_card_v208("Moneyline", (comparison or {}).get("ml"))
        + _edge_card_v208("Run Line", (comparison or {}).get("rl"))
        + _edge_card_v208("Game Total", (comparison or {}).get("total"))
        + '</div>'
        '<div class="sl-cal-note"><b>Calibration protection:</b> V20.8 grades/ranks by no-vig edge when the same sportsbook posts both sides of the exact market. The raw listed-implied edge stays visible for reference.</div>'
        f'<div class="sl-edge-note">Quick comparison uses the V20 40K/game slate projection plus 40K settlement simulations at the posted run line/total. Deep market pages remain the final-analysis engines. Data {int(intel.get("data_score",0) or 0)}/9 • {escape(str(intel.get("confidence") or "—"))} confidence.</div>'
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
        comp = _model_market_v208(i, snaps.get(pk), row)
        if not comp:
            continue
        for market in ("ml", "rl", "total"):
            item = comp.get(market)
            if item:
                buckets[market].append({"game": game, "item": item})

    def strongest(items):
        return max(items, key=lambda x: float((x.get("item") or {}).get("edge", -99))) if items else None

    def conf_key(x):
        i = x["intel"]
        return (int(i.get("data_score", 0) or 0), abs(float(i.get("favorite_prob", .5) or .5) - .5))

    return {
        "ml": strongest(buckets["ml"]),
        "rl": strongest(buckets["rl"]),
        "total": strongest(buckets["total"]),
        "confidence": max(confidence, key=conf_key) if confidence else None,
    }


def _summary_edge_card(title, entry):
    if not entry:
        return base207._summary_edge_card(title, entry)
    item = entry["item"]
    edge = float(item.get("edge", 0) or 0)
    css, grade = base206._edge_grade(edge)
    game = entry["game"]
    nv = item.get("no_vig_edge")
    raw = float(item.get("listed_edge", 0) or 0)
    primary = float(nv if nv is not None else raw)
    nv_text = f'No-vig <span class="nv">{float(nv)*100:+.1f}</span>' if nv is not None else 'No-vig unavailable'
    return (
        f'<div class="sl-summary-card {css}">'
        f'<div class="sl-summary-label">{escape(title)} • {escape(grade)}</div>'
        f'<div class="sl-summary-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-summary-edge">{primary*100:+.1f} pts</div>'
        f'<div class="sl-summary-game"><b>{escape(game)}</b><br>Model {float(item.get("model_prob",0) or 0)*100:.1f}% • {escape(str(item.get("book") or "Book"))} {base206._fmt_price(item.get("market_price"))}</div>'
        f'<div class="sl-summary-cal">{nv_text} • Listed <span class="raw">{raw*100:+.1f}</span></div>'
        f'<div class="sl-summary-fresh">📡 {escape(_fresh_text(item))}</div>'
        '</div>'
    )


def _render_summary(rows, intel, snaps):
    if not intel:
        st.markdown(
            '<div class="sl-summary-lock">⚡ <b>Slate Summary:</b> run <b>BUILD V20.8 MODEL + MARKET INTELLIGENCE</b> to unlock no-vig calibrated Moneyline, Run Line, Total and highest-data-confidence signals.</div>',
            unsafe_allow_html=True,
        )
        return
    entries = _summary_entries(rows, intel, snaps)
    html = (
        '<div class="sl-summary-wrap"><div class="sl-summary-head"><b>⚡ V20.8 Slate Summary</b><span>no-vig calibrated • live quote freshness</span></div>'
        '<div class="sl-summary-grid">'
        + _summary_edge_card("Best ML edge", entries.get("ml"))
        + _summary_edge_card("Best Run Line edge", entries.get("rl"))
        + _summary_edge_card("Best Total edge", entries.get("total"))
        + base207._confidence_card(entries.get("confidence"))
        + '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_card(row, intel=None, snap=None):
    old_market = base206._model_market
    old_snapshot = base206._model_snapshot_html
    try:
        base206._model_market = _model_market_v208
        base206._model_snapshot_html = _model_snapshot_html_v208
        base206._render_card(row, intel, snap)
    finally:
        base206._model_market = old_market
        base206._model_snapshot_html = old_snapshot


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(core.SLATE_CSS + base205.market_ui.EXTRA_CSS + player_ui.LINEUP_CSS + base205.V205_CSS + base206.V206_CSS + base207.V207_CSS + V208_CSS, unsafe_allow_html=True)
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
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • V20.8</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Complete matchup context + sportsbook board + independent model intelligence + no-vig calibrated edges + live quote freshness.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>', unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v208_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v208_sort_{day}")

    raw = _raw_get_api_key(); key = base205._clean_key(raw); books = get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • V20.8 grades by same-book no-vig probability when both sides are available; listed edge remains visible.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.8 MODEL + MARKET INTELLIGENCE", use_container_width=True, type="primary", key=f"v208_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 V20.8 pulse built {stamp or ''} • quick 40K/game navigation model • no-vig market calibration • deep market pages remain the final-analysis engines." + (f" • {err} game(s) skipped" if err else ""))

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
            with st.spinner("Syncing full-game ML • run line • totals • no-vig pairs • quote freshness..."):
                snaps = base205._safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games • incompatible totals stay filtered • no-vig normalization uses the opposite side from the same sportsbook and exact line.")

    _render_summary(active_rows, intel, snaps)

    for row in filtered:
        pk = int(row["game_pk"])
        _render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20.8 calibration rule: primary grade/rank = model probability minus same-book no-vig probability when available; listed-implied edge is shown separately. MODEL EDGE ≥5 pts • CLOSE/WATCH 2–4.9 pts • NO EDGE <2 pts. Deep market modules remain the final probability engines.")
