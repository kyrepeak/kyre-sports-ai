"""V19.2 live intelligence: V19 state model + synced sportsbook board + edge dashboard."""

import math
import re

import numpy as np
import streamlit as st

import live_game_hub_v19 as base
import live_game_hub_v191 as v191
from live_odds_feed import get_bookmakers, render_connection_setup, snapshots_for_games

MODEL_VERSION = "V19.2"
UI_VERSION = "LIVE UI 15.2"

# Use the real V19 model panel captured before V19.1 monkey-patched it.
_ORIGINAL_LIVE_MODEL_PANEL = v191._ORIGINAL_LIVE_MODEL_PANEL
_ALLOWED_RL = [-3.5, -2.5, -1.5, -1.0, 1.0, 1.5, 2.5, 3.5]

DASH_CSS = r"""
<style>
.mk-head{margin:18px 0 10px;padding:15px 16px;border:1px solid #23496d;border-radius:18px;background:linear-gradient(135deg,#0b1c31,#081523)}
.mk-title{font-weight:950;font-size:1.15rem;color:#f8fafc}.mk-sub{font-size:.78rem;color:#91a4bd;margin-top:4px}
.mk-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px}.mk-card{position:relative;overflow:hidden;border:1px solid #28435f;background:linear-gradient(155deg,#102039,#0a1525);border-radius:18px;padding:14px;min-height:164px}.mk-card.green{border-color:#167451;box-shadow:inset 0 0 0 1px rgba(52,211,153,.08)}.mk-card.yellow{border-color:#85691a;box-shadow:inset 0 0 0 1px rgba(250,204,21,.07)}.mk-card.red{border-color:#6d3038}.mk-kicker{font-size:.67rem;letter-spacing:.12em;font-weight:900;color:#7f96b2;text-transform:uppercase}.mk-pick{font-size:1.03rem;font-weight:900;color:white;margin:5px 0}.mk-price{font-size:1.7rem;font-weight:950;color:#f8fafc;line-height:1.05}.mk-edge{font-size:1.05rem;font-weight:950;margin-top:8px}.mk-card.green .mk-edge{color:#5ee8b0}.mk-card.yellow .mk-edge{color:#fde047}.mk-card.red .mk-edge{color:#fb7185}.mk-meta{font-size:.73rem;color:#91a4bd;line-height:1.45;margin-top:6px}.mk-grade{display:inline-block;margin-top:9px;padding:5px 8px;border-radius:999px;font-size:.66rem;font-weight:900;letter-spacing:.06em}.mk-card.green .mk-grade{background:#0b2c21;color:#7df3c2;border:1px solid #176044}.mk-card.yellow .mk-grade{background:#2b2309;color:#fde68a;border:1px solid #765c12}.mk-card.red .mk-grade{background:#2d1418;color:#fda4af;border:1px solid #67303a}.mk-fresh{font-size:.72rem;color:#8fb1cc;margin-top:6px}
@media(max-width:760px){.mk-grid{grid-template-columns:1fr}.mk-card{min-height:auto}}
</style>
"""


def _nearest_run_line(value):
    try:
        value = float(value)
    except Exception:
        return None
    return min(_ALLOWED_RL, key=lambda x: abs(x - value))


def _american_prob(odds):
    try:
        odds = float(odds)
    except Exception:
        return None
    if odds == 0:
        return None
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


def _fmt_odds(value):
    try:
        return f"{int(round(float(value))):+d}"
    except Exception:
        return "—"


def _parse_market_cell(value):
    """Parse strings like '+1.5 (-110)' or 'O 8.5 (-105)' into line, odds."""
    text = str(value or "")
    line_match = re.search(r"(?:O|U)?\s*([+-]?\d+(?:\.\d+)?)", text, re.I)
    odds_match = re.search(r"\(([+-]?\d+)\)", text)
    line = float(line_match.group(1)) if line_match else None
    odds = int(odds_match.group(1)) if odds_match else None
    return line, odds


def _novig_pair(p1, p2):
    if p1 is None or p2 is None:
        return None, None
    total = p1 + p2
    if total <= 0:
        return None, None
    return p1 / total, p2 / total


def _best_price(rows, field):
    vals = []
    for r in rows:
        raw = r.get(field)
        if field in {"Away ML", "Home ML"}:
            try:
                price = int(raw)
            except Exception:
                continue
        else:
            _, price = _parse_market_cell(raw)
            if price is None:
                continue
        vals.append((price, str(r.get("Book") or "Book")))
    return max(vals, key=lambda x: x[0]) if vals else (None, "—")


def _consensus_moneyline(rows):
    away_ps, home_ps = [], []
    for r in rows:
        ap = _american_prob(r.get("Away ML")); hp = _american_prob(r.get("Home ML"))
        a, h = _novig_pair(ap, hp)
        if a is not None:
            away_ps.append(a); home_ps.append(h)
    if not away_ps:
        return None, None
    return float(np.median(away_ps)), float(np.median(home_ps))


def _consensus_spread(rows):
    away_ps, home_ps = [], []
    for r in rows:
        _, ao = _parse_market_cell(r.get("Away RL")); _, ho = _parse_market_cell(r.get("Home RL"))
        a, h = _novig_pair(_american_prob(ao), _american_prob(ho))
        if a is not None:
            away_ps.append(a); home_ps.append(h)
    if not away_ps:
        return None, None
    return float(np.median(away_ps)), float(np.median(home_ps))


def _consensus_total(rows):
    over_ps, under_ps = [], []
    for r in rows:
        _, oo = _parse_market_cell(r.get("Over")); _, uo = _parse_market_cell(r.get("Under"))
        o, u = _novig_pair(_american_prob(oo), _american_prob(uo))
        if o is not None:
            over_ps.append(o); under_ps.append(u)
    if not over_ps:
        return None, None
    return float(np.median(over_ps)), float(np.median(under_ps))


def _grade(edge):
    """Traffic-light grading in percentage points vs no-vig market probability."""
    if edge is None:
        return "red", "NO COMPARISON"
    pts = edge * 100.0
    if pts >= 5.0:
        return "green", "STRONG EDGE"
    if pts >= 2.0:
        return "yellow", "LEAN"
    return "red", "PASS"


def _freshest_age(rows):
    ages = [r.get("age_seconds") for r in rows if r.get("age_seconds") is not None]
    return min(ages) if ages else None


def _market_sync(s, game):
    key = render_connection_setup(f"v192_{game['game_pk']}")
    if not key:
        return None
    try:
        snaps = snapshots_for_games(st.DataFrame([game]) if hasattr(st, "DataFrame") else None, key, get_bookmakers())
    except Exception:
        # Streamlit has no DataFrame constructor; use pandas lazily below.
        import pandas as pd
        try:
            snaps = snapshots_for_games(pd.DataFrame([game]), key, get_bookmakers())
        except Exception as exc:
            st.warning(f"Live sportsbook prices could not refresh right now: {exc}")
            return None
    snap = snaps.get(int(game["game_pk"])) if snaps else None
    if not snap:
        st.caption("📡 No matching in-play sportsbook market is available from the selected books right now.")
        return None

    rows = snap.get("rows") or []
    age = _freshest_age(rows)
    st.markdown(
        f'<div class="mk-head"><div class="mk-title">📡 Live Market Dashboard</div>'
        f'<div class="mk-sub">{get_bookmakers()} • prices refresh about once per minute on the free feed • freshest quote {str(age)+"s old" if age is not None else "timestamp unavailable"}</div></div>',
        unsafe_allow_html=True,
    )

    sync = st.checkbox(
        "🔄 Sync V19.2 settlement lines to current sportsbook spread + total",
        value=True,
        key=f"v192_sync_{game['game_pk']}",
    )
    if sync:
        pk = int(game["game_pk"])
        home_line = _nearest_run_line(snap.get("home_spread"))
        total_line = snap.get("total_line")
        if home_line is not None:
            st.session_state[f"v19_rl_team_{pk}"] = s["home_team"]
            st.session_state[f"v19_rl_{pk}_{s['home_team']}"] = home_line
        current_total = float(s["away_runs"] + s["home_runs"])
        if total_line is not None and float(total_line) >= current_total + 0.5:
            st.session_state[f"v19_total_{pk}"] = float(total_line)
    return snap


def _market_card(title, pick, price, book, model_p, market_p, edge, line2=""):
    css, grade = _grade(edge)
    edge_text = "—" if edge is None else f"{edge*100:+.1f} pts"
    model_text = "—" if model_p is None else f"{model_p*100:.1f}%"
    market_text = "—" if market_p is None else f"{market_p*100:.1f}%"
    return (
        f'<div class="mk-card {css}"><div class="mk-kicker">{title}</div>'
        f'<div class="mk-pick">{pick}</div><div class="mk-price">{_fmt_odds(price)}</div>'
        f'<div class="mk-meta">Best listed: {book}{(" • "+line2) if line2 else ""}<br>Model: <b>{model_text}</b> • Market no-vig: <b>{market_text}</b></div>'
        f'<div class="mk-edge">Model edge {edge_text}</div><span class="mk-grade">{grade}</span></div>'
    )


def _render_edge_dashboard(s, game, snap):
    if not snap:
        return
    saved = st.session_state.get(f"v19_result_{game['game_pk']}")
    if not saved:
        st.info("Run the V19 live model below to unlock model-vs-market edge grades for Moneyline, Run Line and Total.")
        return
    if saved.get("state_key") != base._state_key(s):
        st.warning("⚠️ Game state changed. Re-run V19 before treating the edge dashboard as current.")
        return

    rows = snap.get("rows") or []
    sim = saved.get("sim") or {}

    # MONEYLINE: select the side with the larger positive model-vs-market gap.
    market_away, market_home = _consensus_moneyline(rows)
    ml_options = [
        (s["away_team"], sim.get("p_away"), market_away, "Away ML"),
        (s["home_team"], sim.get("p_home"), market_home, "Home ML"),
    ]
    ml_pick = max(ml_options, key=lambda x: ((x[1] or 0) - (x[2] or 0)))
    ml_edge = None if ml_pick[1] is None or ml_pick[2] is None else ml_pick[1] - ml_pick[2]
    ml_price, ml_book = _best_price(rows, ml_pick[3])

    # RUN LINE: compare the exact side V19 simulated to the current consensus spread market.
    market_a_rl, market_h_rl = _consensus_spread(rows)
    rl_team = saved.get("run_team")
    if rl_team == s["home_team"]:
        rl_model, rl_market, rl_field = sim.get("p_cover"), market_h_rl, "Home RL"
    else:
        rl_model, rl_market, rl_field = sim.get("p_cover"), market_a_rl, "Away RL"
    rl_edge = None if rl_model is None or rl_market is None else rl_model - rl_market
    rl_price, rl_book = _best_price(rows, rl_field)
    rl_pick = f"{rl_team} {float(saved.get('rl', 0)):+g}"

    # TOTAL: choose the stronger model-vs-market side at the synced line.
    market_over, market_under = _consensus_total(rows)
    total_opts = [
        ("OVER", sim.get("p_over"), market_over, "Over"),
        ("UNDER", sim.get("p_under"), market_under, "Under"),
    ]
    total_pick = max(total_opts, key=lambda x: ((x[1] or 0) - (x[2] or 0)))
    total_edge = None if total_pick[1] is None or total_pick[2] is None else total_pick[1] - total_pick[2]
    total_price, total_book = _best_price(rows, total_pick[3])
    total_line = float(saved.get("total_line", snap.get("total_line") or 0))

    st.markdown(
        '<div class="mk-head"><div class="mk-title">⚡ Model vs Market — Live Edge Board</div>'
        '<div class="mk-sub">Green = 5+ percentage-point model edge • Yellow = 2–4.9 pts • Red = pass. Market probability is de-vigged across the connected books.</div></div>',
        unsafe_allow_html=True,
    )
    cards = "".join([
        _market_card("MONEYLINE", ml_pick[0], ml_price, ml_book, ml_pick[1], ml_pick[2], ml_edge),
        _market_card("RUN LINE", rl_pick, rl_price, rl_book, rl_model, rl_market, rl_edge),
        _market_card("GAME TOTAL", f"{total_pick[0]} {total_line:g}", total_price, total_book, total_pick[1], total_pick[2], total_edge),
    ])
    st.markdown(f'<div class="mk-grid">{cards}</div>', unsafe_allow_html=True)
    st.caption("Edge grades compare the V19.2 state-aware model to current no-vig market probability. They are estimates, not guarantees; stale game state or stale quotes should be re-run/refreshed.")


def _enhanced_panel(s, game):
    if s.get("state") != "LIVE":
        return _ORIGINAL_LIVE_MODEL_PANEL(s, game)
    st.markdown(DASH_CSS, unsafe_allow_html=True)
    snap = _market_sync(s, game)
    _ORIGINAL_LIVE_MODEL_PANEL(s, game)
    _render_edge_dashboard(s, game, snap)


# Always replace prior V19/V19.1 panel on import so hot Streamlit reloads upgrade cleanly.
base._live_model_panel = _enhanced_panel
base._v192_market_dashboard_installed = True


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    base._inject_css()
    st.markdown(DASH_CSS, unsafe_allow_html=True)
    verified = base._verified_df(games_df)
    st.markdown(
        '<div class="lv-wrap"><div class="lv-kicker">KYRE SPORTS AI • REAL-TIME MLB • LIVE MODEL + MARKET EDGE</div></div>',
        unsafe_allow_html=True,
    )
    section_header(
        "MLB Live Intelligence — V19.2",
        "Live score/state + current sportsbook ML/run-line/total + state-aware model-vs-market edge dashboard.",
    )
    if verified.empty:
        st.info("No verified games are available on this selected slate.")
        return
    base._body(verified, section_header)
