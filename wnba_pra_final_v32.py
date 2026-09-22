"""WNBA PRA V3.2 — Step 9 Final Decision + Daily Master Card.

WNBA-only. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.

Consumes only completed Step-8 Monte Carlo output already stored in Streamlit
session state. It never reruns simulations and makes no sportsbook API request.
Sportsbook prices remain post-model grading inputs only.

Adds:
- BEST BET / STRONG / MONITOR / AVOID decision hierarchy;
- max-five WNBA Daily Master Card, never forced;
- one final pick per game and no repeated player;
- best exact sportsbook offer chosen per player/line;
- automatic removal of stale/non-converged/OUT candidates;
- lineup-pending candidates remain MONITOR rather than being falsely confirmed;
- Why-this-pick breakdown with model, market, simulation and pregame context;
- future connector strip so Points/Rebounds/Assists/Spread/ML/Total can plug into
  the same WNBA Master Card later without replacing this UI.
"""
from __future__ import annotations

from html import escape
import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_monte_carlo_v311 as monte
import wnba_pra_market_v29 as market
import wnba_role_v282 as role

MODEL_VERSION = "PRA V3.2 STEP 9"
MAX_CARD = 5


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _day_key(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _std_key(day):
    return f"wnba_pra_v31_standard::{_day_key(day)}"


def _final_key(day):
    return f"wnba_pra_v31_final::{_day_key(day)}"


def _stored_rows(day):
    std = st.session_state.get(_std_key(day)) or {}
    rows = std.get("rows")
    if rows is None or not isinstance(rows, pd.DataFrame) or rows.empty:
        return pd.DataFrame(), {"source":"NONE"}
    out = rows.copy()
    out["pass_source"] = "5M"

    # If a 10M finalist pass exists, replace matching sportsbook rows with the
    # newer finalist result. Non-finalists retain their verified 5M result.
    fin = st.session_state.get(_final_key(day)) or {}
    frows = fin.get("rows")
    if isinstance(frows, pd.DataFrame) and not frows.empty:
        f = frows.copy()
        f["pass_source"] = "10M"
        keys = ["game_id","player_key","line","book"]
        fkeys = set(tuple(x) for x in f[keys].astype(str).itertuples(index=False, name=None))
        keep = [tuple(x) not in fkeys for x in out[keys].astype(str).itertuples(index=False, name=None)]
        out = pd.concat([out.loc[keep], f], ignore_index=True)
    return out, {"source":"5M/10M" if (isinstance(frows, pd.DataFrame) and not frows.empty) else "5M"}


def _critical_reasons(row):
    reasons = []
    if not bool(row.get("converged")):
        reasons.append("Monte Carlo convergence check failed")
    if str(row.get("freshness") or "").upper() == "STALE":
        reasons.append("sportsbook market is stale")
    if str(row.get("role_label") or "").upper() == "OUT":
        reasons.append("player status is OUT")
    if not np.isfinite(_num(row.get("model_over"), np.nan)):
        reasons.append("model probability unavailable")
    if not np.isfinite(_num(row.get("no_vig_over"), np.nan)):
        reasons.append("same-book no-vig probability unavailable")
    return reasons


def _monitor_reasons(row):
    reasons = []
    if not bool(row.get("lineup_ready")):
        reasons.append("confirmed starting fives are pending")
    if str(row.get("freshness") or "").upper() == "AGING":
        reasons.append("sportsbook quote is aging")
    if "FALLBACK INDEPENDENT" in str(row.get("variance_source") or "").upper():
        reasons.append("empirical covariance sample is unavailable")
    if _num(row.get("context_quality"), 0.0) < 0.70:
        reasons.append("matchup-context quality is below the preferred band")
    return reasons


def _decision_strength(row):
    p = float(np.clip(_num(row.get("model_over"), 0.0), 0.0, 1.0))
    edge = float(np.clip(_num(row.get("edge"), -0.5), -0.5, 0.5))
    data = float(np.clip(_num(row.get("data_quality"), 0.0), 0.0, 1.0))
    ctx = float(np.clip(_num(row.get("context_quality"), 0.0), 0.0, 1.0))
    fresh = float(np.clip(_num(row.get("fresh_score"), 0.0), 0.0, 1.0))
    conv = 1.0 if bool(row.get("converged")) else 0.0
    score = 100.0 * (
        0.46 * p
        + 0.24 * float(np.clip(0.50 + edge, 0.0, 1.0))
        + 0.10 * data
        + 0.08 * ctx
        + 0.07 * fresh
        + 0.05 * conv
    )
    if _monitor_reasons(row):
        score -= 4.0
    return float(np.clip(score, 0.0, 100.0))


def _decision(row):
    critical = _critical_reasons(row)
    if critical:
        return "⛔ AVOID", "avoid", "; ".join(critical)

    if not bool(row.get("model_qualified")):
        return "⛔ NO EDGE", "avoid", "The completed Monte Carlo result does not clear the production probability + no-vig edge gates."

    monitor = _monitor_reasons(row)
    if monitor:
        return "⚠️ MONITOR", "monitor", "; ".join(monitor)

    strength = _decision_strength(row)
    p = _num(row.get("model_over"), 0.0)
    edge = _num(row.get("edge"), 0.0)
    if bool(row.get("final_ready")) and p >= 0.60 and edge >= 0.05 and strength >= 78.0:
        return "🔥 BEST BET", "best", "Elite qualified simulation edge with confirmed pregame checks."
    return "✅ STRONG", "strong", "Qualified production Monte Carlo edge with confirmed pregame checks."


def _price_sort(value):
    o = _num(value, -100000.0)
    return float(o)


def _best_offer_per_player_line(rows):
    if rows is None or rows.empty:
        return pd.DataFrame()
    f = rows.copy()
    f["decision_strength"] = f.apply(_decision_strength, axis=1)
    f["_price"] = f["over_odds"].map(_price_sort)
    f["_fresh"] = f["fresh_score"].map(lambda x: _num(x, 0.0))
    # Prefer model edge first, then the better price/fresher quote. The simulated
    # basketball probability is identical for duplicate same-player/same-line books.
    f = f.sort_values(
        ["game_id","player_key","line","edge","_price","_fresh"],
        ascending=[True,True,True,False,False,False],
    )
    return f.drop_duplicates(subset=["game_id","player_key","line"], keep="first").drop(columns=["_price","_fresh"])


def select_master_card(rows, limit=MAX_CARD):
    offers = _best_offer_per_player_line(rows)
    if offers.empty:
        return offers

    candidates = []
    for _, r in offers.iterrows():
        label, cls, reason = _decision(r)
        if cls == "avoid":
            continue
        obj = r.to_dict()
        obj["decision_label"] = label
        obj["decision_class"] = cls
        obj["decision_reason"] = reason
        obj["decision_strength"] = _decision_strength(r)
        candidates.append(obj)

    candidates.sort(
        key=lambda r: (
            1 if r.get("decision_class") in {"best","strong"} else 0,
            float(r.get("decision_strength") or 0.0),
            float(r.get("model_over") or 0.0),
            float(r.get("edge") or -1.0),
            _price_sort(r.get("over_odds")),
        ),
        reverse=True,
    )

    selected = []
    used_games = set()
    used_players = set()
    for r in candidates:
        gid = str(r.get("game_id") or "")
        player = str(r.get("player_key") or r.get("player") or "").lower()
        # MLB-style slate diversification: one Final Card pick per game and no
        # repeated player. This is intentionally conservative for correlated props.
        if not gid or gid in used_games or player in used_players:
            continue
        selected.append(r)
        used_games.add(gid)
        used_players.add(player)
        if len(selected) >= int(limit):
            break
    return pd.DataFrame(selected)


def _fmt_pct(v):
    try:
        return f"{100*float(v):.1f}%"
    except Exception:
        return "—"


def _fmt_pp(v):
    try:
        return f"{100*float(v):+.1f} pp"
    except Exception:
        return "—"


def _fmt_odds(v):
    try:
        return f"{int(round(float(v))):+d}"
    except Exception:
        return "—"


def _team_logo(day, team_name):
    try:
        schedule = role.schedule_for_date(day)
        if schedule is None or schedule.empty:
            return ""
        target = str(team_name or "").strip().lower()
        for _, g in schedule.iterrows():
            for side in ("away","home"):
                name = str(g.get(f"{side}_team") or "").strip().lower()
                if name == target:
                    return str(role.logo_url(int(g.get(f"{side}_team_id") or 0)) or "")
    except Exception:
        pass
    return ""


def _badge_style(cls):
    styles = {
        "best": ("#082f23", "#76f0b5", "#2b7a59"),
        "strong": ("#092a3c", "#70e3ff", "#2a6b8a"),
        "monitor": ("#3a3109", "#ffe277", "#7b651d"),
        "avoid": ("#421417", "#ff9b9b", "#8b363b"),
    }
    bg, fg, border = styles.get(cls, styles["strong"])
    return f"background:{bg};color:{fg};border:1px solid {border};border-radius:999px;padding:5px 9px;font-size:9px;font-weight:900;display:inline-block"


def _card_html(row, rank, day):
    r = row if isinstance(row, dict) else row.to_dict()
    label = str(r.get("decision_label") or "")
    cls = str(r.get("decision_class") or "strong")
    logo = _team_logo(day, r.get("team"))
    logo_html = f'<img src="{escape(logo)}" style="width:36px;height:36px;object-fit:contain;margin-right:8px">' if logo else ""
    sims = int(_num(r.get("sims"), 0))
    return f'''
<div style="border:1px solid #315a78;background:linear-gradient(145deg,#071a2b,#061420);border-radius:18px;padding:16px;margin:7px 0 4px;min-height:300px">
  <div style="font-size:9px;letter-spacing:1.1px;color:#65dfff;font-weight:900">🏆 DAILY #{rank} • PRA OVER</div>
  <div style="margin:8px 0"><span style="{_badge_style(cls)}">{escape(label)}</span></div>
  <div style="display:flex;align-items:center;margin-top:8px">{logo_html}<div style="font-size:22px;font-weight:1000;color:#fff">{escape(str(r.get('player') or 'Player'))}</div></div>
  <div style="font-size:11px;color:#8ca6ba;margin-top:4px">{escape(str(r.get('team') or ''))} vs {escape(str(r.get('opponent') or ''))}</div>
  <div style="font-size:13px;color:#fff;margin-top:10px">OVER {float(_num(r.get('line'),0.0)):g} PRA • {escape(str(r.get('book') or ''))} {_fmt_odds(r.get('over_odds'))}</div>
  <div style="font-size:34px;font-weight:1000;color:#62dcff;margin-top:12px">{_fmt_pct(r.get('model_over'))}</div>
  <div style="font-size:8px;letter-spacing:.8px;color:#7d9aaf;font-weight:800">TRUE MC OVER PROBABILITY</div>
  <div style="border-left:4px solid #55d8ff;background:#062033;border-radius:8px;padding:9px 10px;margin-top:10px;font-size:11px;color:#c1d2df">Adj PRA {float(_num(r.get('projection'),0.0)):.2f} • MC mean {float(_num(r.get('sim_mean'),0.0)):.2f} • Median {float(_num(r.get('sim_median'),0.0)):g} • 10–90 {float(_num(r.get('p10'),0.0)):g}–{float(_num(r.get('p90'),0.0)):g}</div>
  <div style="border:1px solid #31536a;border-radius:10px;padding:9px 10px;margin-top:9px;font-size:10px;color:#c2d2df">No-vig {_fmt_pct(r.get('no_vig_over'))} • Edge {_fmt_pp(r.get('edge'))} • Fair {_fmt_odds(r.get('fair_over'))}</div>
  <div style="font-size:30px;font-weight:1000;color:#fff;margin-top:12px">{float(_num(r.get('decision_strength'),0.0)):.1f}<span style="font-size:8px;color:#7895aa"> /100 FINAL CARD STRENGTH</span></div>
  <div style="font-size:9px;color:#7f9aaf;margin-top:8px">{sims:,} sims • {int(_num(r.get('batches'),0))} batches • MC SE {100*_num(r.get('mc_se'),0.0):.4f} pp • {escape(str(r.get('pass_source') or '5M'))}</div>
</div>'''


def _why(row):
    r = row if isinstance(row, dict) else row.to_dict()
    label, _cls, reason = _decision(r)
    lines = {
        "🎯 Model case": [
            f"Matchup-adjusted PRA: {_num(r.get('projection'),0.0):.2f} vs sportsbook line {_num(r.get('line'),0.0):g}.",
            f"Monte Carlo mean {_num(r.get('sim_mean'),0.0):.2f}, median {_num(r.get('sim_median'),0.0):g}, 10–90 range {_num(r.get('p10'),0.0):g}–{_num(r.get('p90'),0.0):g}.",
            f"True Over probability {_fmt_pct(r.get('model_over'))}; push {_fmt_pct(r.get('push'))}.",
        ],
        "📈 Market context": [
            f"Best selected offer: {r.get('book','')} {_fmt_odds(r.get('over_odds'))} at PRA {float(_num(r.get('line'),0.0)):g}.",
            f"Same-book no-vig Over {_fmt_pct(r.get('no_vig_over'))}; model edge {_fmt_pp(r.get('edge'))}; fair price {_fmt_odds(r.get('fair_over'))}.",
            f"Quote freshness: {str(r.get('freshness') or 'UNKNOWN')}.",
        ],
        "🧪 Simulation verification": [
            f"Executed {int(_num(r.get('sims'),0)):,} simulations in {int(_num(r.get('batches'),0))} batches with seed {int(_num(r.get('seed'),0))}.",
            f"MC standard error {100*_num(r.get('mc_se'),0.0):.4f} percentage points; max batch difference {100*_num(r.get('max_batch_diff'),0.0):.3f} pp; converged={'YES' if bool(r.get('converged')) else 'NO'}.",
            f"Variance source: {str(r.get('variance_source') or 'unknown')} • historical games {int(_num(r.get('hist_games'),0))}.",
        ],
        "🛰 Pregame + final decision": [
            "Confirmed starting fives: " + ("YES" if bool(r.get('lineup_ready')) else "PENDING"),
            f"Role status: {str(r.get('role_label') or 'ACTIVE')} • context quality {100*_num(r.get('context_quality'),0.0):.0f}% • data quality {100*_num(r.get('data_quality'),0.0):.0f}%.",
            f"Current decision: {label}. {reason}",
        ],
    }
    return lines


def _render_connectors():
    items = [("PRA","✅ LIVE",True),("Points","NEXT",False),("Rebounds","NEXT",False),("Assists","NEXT",False),("Spread","NEXT",False),("Moneyline","NEXT",False),("Total","NEXT",False)]
    cols = st.columns(4)
    for i,(name,state,live) in enumerate(items):
        color = "#64e5aa" if live else "#8aa0b2"
        border = "#276b52" if live else "#30495d"
        cols[i % 4].markdown(
            f'<div style="border:1px solid {border};background:#071827;border-radius:12px;padding:9px;text-align:center;margin:3px 0"><div style="font-size:9px;color:#7895aa;font-weight:900">{escape(name)}</div><div style="font-size:10px;color:{color};font-weight:1000;margin-top:3px">{escape(state)}</div></div>',
            unsafe_allow_html=True,
        )


def render_final_decision(day):
    st.markdown("## 🏆 Step 9 — WNBA Final Decision Screen")
    st.caption(
        "Uses completed Step-8 Monte Carlo only. No extra simulations and no new sportsbook request. "
        "Maximum five picks, never forced; one Final Card pick per game."
    )
    _render_connectors()

    rows, source_meta = _stored_rows(day)
    if rows.empty:
        st.info("Run the Step-8 5,000,000 standard Monte Carlo first. Step 9 will populate automatically from the completed simulation output.")
        return

    selected = select_master_card(rows)
    offers = _best_offer_per_player_line(rows)
    qualified = int(sum(bool(x) for x in offers.get("model_qualified", pd.Series(dtype=bool)).tolist())) if not offers.empty else 0
    final_ready = int(sum(bool(x) for x in offers.get("final_ready", pd.Series(dtype=bool)).tolist())) if not offers.empty else 0
    monitors = 0
    for _, r in offers.iterrows():
        if bool(r.get("model_qualified")) and _decision(r)[1] == "monitor":
            monitors += 1
    active_games = int(rows["game_id"].astype(str).nunique()) if "game_id" in rows.columns else 0
    confirmed_games = int(rows.groupby("game_id")["lineup_ready"].first().sum()) if ("game_id" in rows.columns and "lineup_ready" in rows.columns) else 0

    st.markdown(
        f'''<div style="border:1px solid #315b7a;background:linear-gradient(145deg,#0b1d31,#07131f);border-radius:20px;padding:16px;margin:12px 0">
          <div style="font-size:9px;letter-spacing:1.2px;color:#67ddff;font-weight:950">KYRE SPORTS AI • WNBA DAILY MASTER CARD • V3.2</div>
          <div style="font-size:28px;font-weight:1000;color:#fff;margin-top:4px">🏆 Daily Master Card — Top 5 WNBA Picks</div>
          <div style="font-size:10px;color:#8da5b8;margin-top:5px">PRA production connector live • future WNBA markets will feed this same slate-wide card</div>
          <div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:14px">
            <div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">MC SOURCE</div><div style="font-size:15px;color:#fff;font-weight:1000">{escape(source_meta.get('source','5M'))}</div></div>
            <div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">QUALIFIED</div><div style="font-size:15px;color:#66e5ac;font-weight:1000">{qualified}</div></div>
            <div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">FINAL READY</div><div style="font-size:15px;color:#66e5ac;font-weight:1000">{final_ready}</div></div>
            <div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">MONITOR</div><div style="font-size:15px;color:#ffe178;font-weight:1000">{monitors}</div></div>
            <div style="border:1px solid #29475f;border-radius:11px;padding:9px"><div style="font-size:7px;color:#7995aa">CARD</div><div style="font-size:15px;color:#fff;font-weight:1000">{len(selected)}/5</div><div style="font-size:7px;color:#7895aa">Lineups {confirmed_games}/{active_games}</div></div>
          </div>
        </div>''', unsafe_allow_html=True
    )

    if selected.empty:
        st.warning("🏆 NO QUALIFIED PRA PICKS. The 5M production model did not clear the probability + no-vig + freshness/convergence gates, so the WNBA Final Card is intentionally empty. Nothing is forced.")
        with st.expander("👀 Closest model-vs-market results — NOT Final Card picks", expanded=False):
            watch = offers.sort_values(["model_over","edge"], ascending=[False,False]).head(5).copy()
            if not watch.empty:
                show = pd.DataFrame({
                    "Player":watch["player"],"Book":watch["book"],"Line":watch["line"],
                    "P(Over)":watch["model_over"].map(_fmt_pct),"No-vig":watch["no_vig_over"].map(_fmt_pct),
                    "Edge":watch["edge"].map(_fmt_pp),"Status":[_decision(r)[0] for _,r in watch.iterrows()],
                })
                st.dataframe(show, use_container_width=True, hide_index=True)
        return

    st.markdown("### 🏆 WNBA Final Card")
    records = selected.to_dict("records")
    for i in range(0, len(records), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx >= len(records):
                continue
            r = records[idx]
            with cols[j]:
                st.markdown(_card_html(r, idx+1, day), unsafe_allow_html=True)
                with st.expander("🧠 Why this pick?", expanded=False):
                    for title, lines in _why(r).items():
                        st.markdown(f"**{title}**")
                        for line in lines:
                            st.write("• " + str(line))

    with st.expander("🧠 Final Card decision rules", expanded=False):
        st.write("🔥 BEST BET = production-qualified 5M/10M result + confirmed lineups + fresh market + elite probability/edge band.")
        st.write("✅ STRONG = production-qualified result with confirmed pregame checks.")
        st.write("⚠️ MONITOR = qualified model result, but lineup/freshness/covariance/context still needs confirmation.")
        st.write("⛔ AVOID / NO EDGE = failed convergence, stale market, OUT status, missing no-vig pair, or probability/edge below the production gate.")
        st.write("The Final Card never changes the underlying projection, simulation probability, sportsbook line, or Monte Carlo output. It only selects among already-completed production results.")


__all__ = ["MODEL_VERSION","MAX_CARD","select_master_card","render_final_decision"]
