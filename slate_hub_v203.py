"""V20.3 MLB Slate Command Center.

Adds corrected totals parsing, best-price highlighting and no-extra-call movement
tracking to the V20 slate while retaining the verified MLB schedule, model pulse
and safe Streamlit-secret handling.
"""

from html import escape

import pandas as pd
import requests
import streamlit as st

import slate_hub_v20 as core
from live_odds_feed import get_api_key as _raw_get_api_key, get_bookmakers
from slate_odds_feed_v203 import slate_snapshots_for_games_v203

MODEL_VERSION = "V20.3"

EXTRA_CSS = r"""
<style>
.sl-market{border-left:0!important;border:1px solid #24537d!important;border-radius:17px!important;background:linear-gradient(135deg,#07192d,#081421)!important;padding:12px!important}
.sl-market-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}.sl-market-title{font-size:.69rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:#59d7ff}.sl-market-age{font-size:.63rem;color:#7892af}
.sl-bestbar{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:8px 0 10px}.sl-best{border:1px solid #24516e;background:#091a2c;border-radius:12px;padding:8px}.sl-best span{display:block;font-size:.57rem;color:#7f96b0;text-transform:uppercase;letter-spacing:.06em;font-weight:900}.sl-best b{display:block;color:#f8fafc;font-size:.72rem;margin-top:2px}.sl-best.green{border-color:#17634b;background:#08251d}.sl-best.green b{color:#73efb9}.sl-best.gold{border-color:#69551b;background:#251f0a}.sl-best.gold b{color:#ffe17a}
.sl-bookrow{border-top:1px solid rgba(143,164,189,.13);padding:7px 0 3px;font-size:.69rem;line-height:1.55;color:#abc0d7}.sl-bookrow:first-of-type{border-top:0}.sl-book{display:inline-block;min-width:74px;color:white;font-weight:900}.sl-odds-label{color:#728aa6;font-size:.61rem;text-transform:uppercase;letter-spacing:.06em;font-weight:850}.sl-odds-strong{color:#f8fafc;font-weight:850}.sl-star{color:#ffd84d;font-weight:950}.sl-move{margin-top:8px;border-top:1px solid rgba(143,164,189,.13);padding-top:8px;color:#8fa8c1;font-size:.65rem}.sl-up{color:#61e6ad;font-weight:850}.sl-down{color:#ff8b96;font-weight:850}.sl-flat{color:#93a7be}.sl-market-empty{margin-top:10px;border:1px dashed #29435f;border-radius:13px;padding:9px 11px;font-size:.68rem;color:#7890aa;background:#081321}
@media(max-width:700px){.sl-bestbar{grid-template-columns:1fr}.sl-bookrow{font-size:.67rem}.sl-book{display:block;min-width:0;margin-bottom:2px}.sl-market-head{align-items:flex-start}}
</style>
"""


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


def _get_api_key():
    return _clean_key(_raw_get_api_key())


def _fmt_ml(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def _fmt_line(value):
    try:
        return f"{float(value):+g}"
    except Exception:
        return "—"


def _fresh_age(rows):
    ages = [r.get("age_seconds") for r in rows if r.get("age_seconds") is not None]
    return min(ages) if ages else None


def _best_text(best_item, side="ml"):
    if not best_item:
        return "—"
    book = escape(str(best_item.get("book") or ""))
    if side == "ml":
        return f"{_fmt_ml(best_item.get('price'))} • {book}"
    return f"{_fmt_line(best_item.get('line'))} {_fmt_ml(best_item.get('price'))} • {book}"


def _movement_piece(label, move, show_line=False):
    if not move:
        return ""
    bits = []
    line_delta = float(move.get("line_delta", 0) or 0)
    price_delta = int(move.get("price_delta", 0) or 0)
    if show_line and abs(line_delta) > 1e-9:
        cls = "sl-up" if line_delta > 0 else "sl-down"
        arrow = "↑" if line_delta > 0 else "↓"
        bits.append(f'<span class="{cls}">{label} line {arrow}{abs(line_delta):g}</span>')
    if price_delta:
        cls = "sl-up" if price_delta > 0 else "sl-down"
        arrow = "↑" if price_delta > 0 else "↓"
        bits.append(f'<span class="{cls}">{label} price {arrow}{abs(price_delta)}</span>')
    return " • ".join(bits)


def _is_best(row, best, key, price_field, line_field=None):
    b = best.get(key) if best else None
    if not b or row.get(price_field) is None:
        return False
    if int(row.get(price_field)) != int(b.get("price")) or str(row.get("Book")) != str(b.get("book")):
        return False
    if line_field is not None and b.get("line") is not None:
        try:
            return abs(float(row.get(line_field)) - float(b.get("line"))) <= 1e-6
        except Exception:
            return False
    return True


def _market_html(snap, away, home):
    if not snap or not snap.get("rows"):
        return ""

    rows = snap.get("rows") or []
    best = snap.get("best") or {}
    movement = snap.get("movement") or {}
    age = _fresh_age(rows)
    age_text = f"{age}s old" if age is not None else "quote time n/a"
    status = str(snap.get("event_status") or "").lower()
    mode = "LIVE MARKET" if "live" in status else "PREGAME MARKET"

    best_away_ml = _best_text(best.get("away_ml"), "ml")
    best_home_ml = _best_text(best.get("home_ml"), "ml")
    over_text = _best_text(best.get("over"), "line")
    under_text = _best_text(best.get("under"), "line")
    total_best = f"O {over_text} / U {under_text}" if best.get("over") or best.get("under") else "Not posted"

    book_rows = []
    for r in rows[:2]:
        book = escape(str(r.get("Book") or "Sportsbook"))
        a_ml_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "away_ml", "Away ML") else ""
        h_ml_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "home_ml", "Home ML") else ""
        a_rl_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "away_rl", "away_rl_price", "away_rl_line") else ""
        h_rl_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "home_rl", "home_rl_price", "home_rl_line") else ""
        o_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "over", "over_price", "total_line") else ""
        u_star = " <span class=\"sl-star\">★</span>" if _is_best(r, best, "under", "under_price", "total_line") else ""
        book_rows.append(
            '<div class="sl-bookrow">'
            f'<span class="sl-book">{book}</span>'
            f'<span class="sl-odds-label"> ML </span><span class="sl-odds-strong">{escape(away)} {_fmt_ml(r.get("Away ML"))}{a_ml_star} · {escape(home)} {_fmt_ml(r.get("Home ML"))}{h_ml_star}</span><br>'
            f'<span class="sl-odds-label">RL </span><span class="sl-odds-strong">{escape(str(r.get("Away RL") or "—"))}{a_rl_star} / {escape(str(r.get("Home RL") or "—"))}{h_rl_star}</span> &nbsp; '
            f'<span class="sl-odds-label">TOTAL </span><span class="sl-odds-strong">{escape(str(r.get("Over") or "—"))}{o_star} / {escape(str(r.get("Under") or "—"))}{u_star}</span>'
            '</div>'
        )

    move_parts = [
        _movement_piece(f"{away} ML", movement.get("away_ml")),
        _movement_piece(f"{home} ML", movement.get("home_ml")),
        _movement_piece("Run line", movement.get("home_rl"), True),
        _movement_piece("Total", movement.get("over"), True),
    ]
    move_parts = [x for x in move_parts if x]
    movement_html = (
        '<div class="sl-move">📈 Since last odds refresh: ' + " • ".join(move_parts) + '</div>'
        if move_parts
        else f'<div class="sl-move">📈 {escape(str(snap.get("movement_label") or "No movement detected yet"))}</div>'
    )

    return (
        '<div class="sl-market">'
        '<div class="sl-market-head">'
        f'<span class="sl-market-title">📡 {mode}</span><span class="sl-market-age">{escape(age_text)}</span>'
        '</div>'
        '<div class="sl-bestbar">'
        f'<div class="sl-best green"><span>Best {escape(away)} ML</span><b>{best_away_ml}</b></div>'
        f'<div class="sl-best green"><span>Best {escape(home)} ML</span><b>{best_home_ml}</b></div>'
        f'<div class="sl-best gold"><span>Consensus total / best price</span><b>{total_best}</b></div>'
        '</div>'
        + ''.join(book_rows)
        + movement_html
        + '</div>'
    )


# Upgrade the core V20 card renderer with V20.3 sportsbook presentation.
core._market_html = _market_html


def _safe_snapshots(games_df, api_key, bookmakers):
    try:
        return slate_snapshots_for_games_v203(games_df, api_key, bookmakers)
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
    st.markdown(core.SLATE_CSS + EXTRA_CSS, unsafe_allow_html=True)
    rows = core._refresh_rows(games_df)
    if not rows:
        st.info("No verified MLB games are available for this selected date.")
        return

    day = str(rows[0].get("game_date") or "")
    live = sum(core._state_label(r.get("status")) == "LIVE" for r in rows)
    upcoming = sum(core._state_label(r.get("status")) == "PREGAME" for r in rows)
    starters = sum(1 for r in rows for k in ("away_pitcher_id", "home_pitcher_id") if r.get(k) is not None and not pd.isna(r.get(k)))
    total_starters = len(rows) * 2

    st.markdown(
        '<div class="sl-hero">'
        '<div class="sl-kicker">KYRE SPORTS AI • MLB DAILY COMMAND CENTER • BEST PRICE + MOVEMENT</div>'
        f'<div class="sl-title">⚾ MLB Slate — {escape(day)}</div>'
        '<div class="sl-sub">Verified games + probable starters + model pulse + FanDuel/DraftKings ML, run line, totals, best-price highlights and refresh-to-refresh movement.</div>'
        '<div class="sl-counts">'
        f'<div class="sl-count"><b>{len(rows)}</b><span>Games</span></div>'
        f'<div class="sl-count"><b>{live}</b><span>Live</span></div>'
        f'<div class="sl-count"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="sl-count"><b>{starters}/{total_starters}</b><span>Probable SP</span></div>'
        '</div></div>', unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        view = st.radio("Slate filter", ["All", "Live", "Upcoming", "Final"], horizontal=True, key=f"v203_filter_{day}")
    with c2:
        intel = st.session_state.get(f"v20_intel_{day}") or {}
        sort_options = ["Game time"] + (["Strongest ML", "Highest total", "Data quality"] if intel else [])
        sort_by = st.selectbox("Sort", sort_options, key=f"v203_sort_{day}")

    raw = _raw_get_api_key()
    key = _get_api_key()
    books = get_bookmakers()
    if raw and not key:
        st.error("🔐 Streamlit Secrets still contains a placeholder API key. Replace it with the real key and save changes.")
    elif key:
        st.caption(f"📡 Odds connected permanently • {books} • ★ marks the best listed price at the displayed line. Movement compares the current quote with the previous slate refresh.")
    else:
        st.caption("📡 Odds are not connected. Add ODDS_API_IO_KEY to Streamlit Secrets to display sportsbook markets.")

    if st.button("⚡ BUILD V20.3 SLATE INTELLIGENCE", use_container_width=True, type="primary", key=f"v203_build_{day}"):
        intel = core._build_intelligence(rows, day)

    if intel:
        stamp = st.session_state.get(f"v20_intel_time_{day}")
        err = int(st.session_state.get(f"v20_intel_errors_{day}", 0) or 0)
        st.caption(f"🧠 Model pulse built {stamp or ''} • quick 40K/game preview • use individual market modules for final deep simulations." + (f" • {err} game(s) skipped" if err else ""))

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
                snaps = _safe_snapshots(pd.DataFrame(active_rows), key, books)
        except Exception as exc:
            st.warning(f"Sportsbook markets could not refresh right now: {exc}")
            snaps = {}
        st.caption(f"📈 Markets matched {len(snaps)}/{len(active_rows)} active games. Totals are parsed from both `Totals` and `Over/Under` provider labels. Movement begins after the next odds refresh in this app session.")

    for row in filtered:
        pk = int(row["game_pk"])
        core._render_card(row, intel.get(pk), snaps.get(pk))

    st.caption("V20.3 Slate is the command-center view. ★ = best listed price at the displayed/consensus line. Movement is refresh-to-refresh market context, not a guarantee of future direction. Model projections remain independent of sportsbook prices.")
