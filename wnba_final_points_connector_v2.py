"""WNBA Final Decision — Step 2 Points card-feed connector.

Builds on the verified Step-1 read-only connector. This module does not run or
restore Points, request sportsbook data, change Points/PRA projections, or touch
Rebounds. It only merges an already-completed same-day Points 5M/10M payload
into the existing Final Decision selection surface.

Safety contract:
- Points must first pass the Step-1 same-day completed-payload validation.
- Only stored model_qualified/final_ready/convergence/freshness/lineup fields are
  consumed; nothing is regraded here.
- PRA math and stored output are unchanged.
- Existing one-pick-per-game / no-repeat-player / max-five rules remain active
  across PRA + Points together.
- Rebounds stays disconnected until a separate later step.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_final_v32 as final_ui
import wnba_final_points_connector_v1 as step1

MODEL_VERSION = "WNBA FINAL POINTS CONNECTOR V2 • CARD FEED"
STANDARD_SIMS = 5_000_000

# Capture the untouched PRA functions once. Step-1 only patched _render_connectors,
# so these remain the genuine V3.2 implementations when this module imports.
_ORIGINAL_STORED_ROWS = final_ui._stored_rows
_ORIGINAL_BEST_OFFERS = final_ui._best_offer_per_player_line
_ORIGINAL_CARD_HTML = final_ui._card_html
_ORIGINAL_WHY = final_ui._why


def _day(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _std_key(day: str) -> str:
    return f"wnba_points_v19_standard::{_day(day)}"


def _final_key(day: str) -> str:
    return f"wnba_points_v19_final::{_day(day)}"


def _frame(value) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _market_name(row) -> str:
    raw = str((row.get("market") if hasattr(row, "get") else "") or "PRA").strip().upper()
    if raw in {"POINT", "POINTS", "PTS"}:
        return "POINTS"
    return "PRA"


def _points_rows(day):
    """Return only an already-validated same-day Points payload."""
    health = step1.status(day)
    if not bool(health.get("live")):
        return pd.DataFrame(), {"source": "NONE", "health": health}

    day_str = _day(day)
    std = st.session_state.get(_std_key(day_str)) or {}
    rows = _frame(std.get("rows"))
    if rows.empty:
        return pd.DataFrame(), {"source": "NONE", "health": health}

    out = rows.copy()
    out["market"] = "Points"
    out["pass_source"] = "5M"

    # Mirror PRA's replacement behavior: if a 10M finalist row exists, use it
    # only for the matching exact book/line unit; all other rows retain 5M.
    fin = st.session_state.get(_final_key(day_str)) or {}
    frows = _frame(fin.get("rows"))
    if not frows.empty:
        f = frows.copy()
        f["market"] = "Points"
        f["pass_source"] = "10M"
        keys = ["game_id", "player_key", "line", "book"]
        if all(k in out.columns for k in keys) and all(k in f.columns for k in keys):
            fkeys = set(tuple(x) for x in f[keys].astype(str).itertuples(index=False, name=None))
            keep = [tuple(x) not in fkeys for x in out[keys].astype(str).itertuples(index=False, name=None)]
            out = pd.concat([out.loc[keep], f], ignore_index=True)

    # Fail closed if the payload somehow changed after Step-1 validated it.
    required = {
        "game_id", "player_key", "player", "team", "opponent", "line", "book",
        "model_over", "no_vig_over", "edge", "model_qualified", "final_ready",
        "lineup_ready", "freshness", "converged", "sims", "over_odds",
        "projection", "sim_mean", "sim_median", "p10", "p90", "fair_over",
    }
    if required.difference(out.columns):
        return pd.DataFrame(), {"source": "CHECK", "health": health}

    sims = pd.to_numeric(out["sims"], errors="coerce")
    valid = (
        out["market"].astype(str).str.upper().eq("POINTS")
        & sims.ge(STANDARD_SIMS)
        & out["game_id"].astype(str).str.strip().ne("")
        & out["player_key"].astype(str).str.strip().ne("")
    )
    if not bool(valid.all()):
        return pd.DataFrame(), {"source": "CHECK", "health": health}

    source = "5M/10M" if not frows.empty else "5M"
    return out.reset_index(drop=True), {"source": source, "health": health}


def stored_rows_combined(day):
    """Drop-in replacement for Final Decision _stored_rows."""
    pra, pmeta = _ORIGINAL_STORED_ROWS(day)
    if isinstance(pra, pd.DataFrame) and not pra.empty:
        pra = pra.copy()
        if "market" not in pra.columns:
            pra["market"] = "PRA"
        else:
            blank = pra["market"].astype(str).str.strip().eq("")
            pra.loc[blank, "market"] = "PRA"

    points, pts_meta = _points_rows(day)

    frames = [x for x in (pra, points) if isinstance(x, pd.DataFrame) and not x.empty]
    if not frames:
        return pd.DataFrame(), {"source": "NONE", "pra_source": pmeta.get("source", "NONE"), "points_source": pts_meta.get("source", "NONE")}

    combined = pd.concat(frames, ignore_index=True, sort=False)
    labels = []
    if isinstance(pra, pd.DataFrame) and not pra.empty:
        labels.append(f"PRA {pmeta.get('source', '5M')}")
    if not points.empty:
        labels.append(f"PTS {pts_meta.get('source', '5M')}")
    return combined, {
        "source": " + ".join(labels),
        "pra_source": pmeta.get("source", "NONE"),
        "points_source": pts_meta.get("source", "NONE"),
    }


def best_offer_market_aware(rows):
    """Preserve the existing exact-offer logic while separating markets."""
    if rows is None or not isinstance(rows, pd.DataFrame) or rows.empty:
        return pd.DataFrame()
    work = rows.copy()
    if "market" not in work.columns:
        work["market"] = "PRA"

    chunks = []
    for _, part in work.groupby(work["market"].astype(str).str.upper(), dropna=False):
        chosen = _ORIGINAL_BEST_OFFERS(part.copy())
        if isinstance(chosen, pd.DataFrame) and not chosen.empty:
            chunks.append(chosen)
    return pd.concat(chunks, ignore_index=True, sort=False) if chunks else pd.DataFrame()


def _fmt_num(value, digits=2, suffix="") -> str:
    try:
        x = float(value)
        if not np.isfinite(x):
            return "—"
        return f"{x:.{digits}f}{suffix}"
    except Exception:
        return "—"


def card_html_market_aware(row, rank, day):
    """Use the untouched PRA card; render a Points-specific card only for Points."""
    r = row if isinstance(row, dict) else row.to_dict()
    if _market_name(r) != "POINTS":
        return _ORIGINAL_CARD_HTML(row, rank, day)

    label = str(r.get("decision_label") or "")
    cls = str(r.get("decision_class") or "strong")
    logo = final_ui._team_logo(day, r.get("team"))
    logo_html = (
        f'<img src="{escape(logo)}" style="width:36px;height:36px;object-fit:contain;margin-right:8px">'
        if logo else ""
    )
    sims = int(final_ui._num(r.get("sims"), 0))
    line = final_ui._num(r.get("line"), 0.0)
    projection = final_ui._num(r.get("projection"), 0.0)
    sim_mean = final_ui._num(r.get("sim_mean"), 0.0)
    sim_median = final_ui._num(r.get("sim_median"), 0.0)
    p10 = final_ui._num(r.get("p10"), 0.0)
    p90 = final_ui._num(r.get("p90"), 0.0)
    strength = final_ui._num(r.get("decision_strength"), 0.0)
    batches = int(final_ui._num(r.get("batches"), 0))
    mc_se = final_ui._num(r.get("mc_se"), 0.0)

    return f'''
<div style="border:1px solid #315a78;background:linear-gradient(145deg,#071a2b,#061420);border-radius:18px;padding:16px;margin:7px 0 4px;min-height:300px">
  <div style="font-size:9px;letter-spacing:1.1px;color:#65dfff;font-weight:900">🏆 DAILY #{rank} • POINTS OVER</div>
  <div style="margin:8px 0"><span style="{final_ui._badge_style(cls)}">{escape(label)}</span></div>
  <div style="display:flex;align-items:center;margin-top:8px">{logo_html}<div style="font-size:22px;font-weight:1000;color:#fff">{escape(str(r.get('player') or 'Player'))}</div></div>
  <div style="font-size:11px;color:#8ca6ba;margin-top:4px">{escape(str(r.get('team') or ''))} vs {escape(str(r.get('opponent') or ''))}</div>
  <div style="font-size:13px;color:#fff;margin-top:10px">OVER {line:g} PTS • {escape(str(r.get('book') or ''))} {final_ui._fmt_odds(r.get('over_odds'))}</div>
  <div style="font-size:34px;font-weight:1000;color:#62dcff;margin-top:12px">{final_ui._fmt_pct(r.get('model_over'))}</div>
  <div style="font-size:8px;letter-spacing:.8px;color:#7d9aaf;font-weight:800">TRUE MC OVER PROBABILITY</div>
  <div style="border-left:4px solid #55d8ff;background:#062033;border-radius:8px;padding:9px 10px;margin-top:10px;font-size:11px;color:#c1d2df">Adj PTS {projection:.2f} • MC mean {sim_mean:.2f} • Median {sim_median:g} • 10–90 {p10:g}–{p90:g}</div>
  <div style="border:1px solid #31536a;border-radius:10px;padding:9px 10px;margin-top:9px;font-size:10px;color:#c2d2df">No-vig {final_ui._fmt_pct(r.get('no_vig_over'))} • Edge {final_ui._fmt_pp(r.get('edge'))} • Fair {final_ui._fmt_odds(r.get('fair_over'))}</div>
  <div style="font-size:30px;font-weight:1000;color:#fff;margin-top:12px">{strength:.1f}<span style="font-size:8px;color:#7895aa"> /100 FINAL CARD STRENGTH</span></div>
  <div style="font-size:9px;color:#7f9aaf;margin-top:8px">{sims:,} sims • {batches} batches • MC SE {100*mc_se:.4f} pp • {escape(str(r.get('pass_source') or '5M'))}</div>
</div>'''


def why_market_aware(row):
    r = row if isinstance(row, dict) else row.to_dict()
    if _market_name(r) != "POINTS":
        return _ORIGINAL_WHY(row)

    label, _cls, reason = final_ui._decision(r)
    return {
        "🎯 Points model case": [
            f"Matchup-adjusted Points: {_fmt_num(r.get('projection'))} vs sportsbook line {final_ui._num(r.get('line'), 0.0):g}.",
            f"Monte Carlo mean {_fmt_num(r.get('sim_mean'))}, median {final_ui._num(r.get('sim_median'), 0.0):g}, 10–90 range {final_ui._num(r.get('p10'), 0.0):g}–{final_ui._num(r.get('p90'), 0.0):g}.",
            f"True Over probability {final_ui._fmt_pct(r.get('model_over'))}; push {final_ui._fmt_pct(r.get('push'))}.",
        ],
        "📈 Market context": [
            f"Selected offer: {r.get('book','')} {final_ui._fmt_odds(r.get('over_odds'))} at {final_ui._num(r.get('line'),0.0):g} Points.",
            f"Same-book no-vig Over {final_ui._fmt_pct(r.get('no_vig_over'))}; model edge {final_ui._fmt_pp(r.get('edge'))}; fair price {final_ui._fmt_odds(r.get('fair_over'))}.",
            f"Quote freshness: {str(r.get('freshness') or '—')}.",
        ],
        "🧪 Simulation / availability": [
            f"{int(final_ui._num(r.get('sims'),0)):,} simulations; convergence {'passed' if bool(r.get('converged')) else 'failed'}.",
            f"Lineup ready: {'YES' if bool(r.get('lineup_ready')) else 'NO — remains monitor if otherwise qualified'}.",
            f"Variance source: {str(r.get('variance_source') or '—')}.",
        ],
        "🏁 Decision": [
            f"{label}: {reason}",
            "Points competed against PRA under the same max-five, no-repeat-player and one-pick-per-game slate rules.",
        ],
    }


def _connector_tile(name: str, state: str, live: bool, detail: str = "") -> str:
    color = "#64e5aa" if live else ("#ffe178" if "CHECK" in state else "#8aa0b2")
    border = "#276b52" if live else ("#78641f" if "CHECK" in state else "#30495d")
    return (
        f'<div title="{escape(detail, quote=True)}" style="border:1px solid {border};background:#071827;'
        f'border-radius:12px;padding:9px;text-align:center;margin:3px 0">'
        f'<div style="font-size:9px;color:#7895aa;font-weight:900">{escape(name)}</div>'
        f'<div style="font-size:10px;color:{color};font-weight:1000;margin-top:3px">{escape(state)}</div>'
        '</div>'
    )


def render_connectors_step2() -> None:
    day = st.session_state.get("wnba_pra_v2_date")
    points = step1.status(day)
    points_state = "✅ LIVE" if bool(points.get("live")) else str(points.get("state") or "NEXT")
    points_detail = (
        f"Card feed active • {points.get('unique_distributions',0)} distributions • "
        f"{points.get('qualified',0)} qualified • {points.get('final_ready',0)} final ready"
        if bool(points.get("live")) else str(points.get("detail") or "Points not connected.")
    )

    items = [
        ("PRA", "✅ LIVE", True, "PRA production feed remains active and unchanged."),
        ("Points", points_state, bool(points.get("live")), points_detail),
        ("Rebounds", "NEXT", False, "Rebounds remains intentionally paused until Points card-feed integration is verified."),
        ("Assists", "NEXT", False, "Not connected yet."),
        ("Spread", "NEXT", False, "Not connected yet."),
        ("Moneyline", "NEXT", False, "Not connected yet."),
        ("Total", "NEXT", False, "Not connected yet."),
    ]
    cols = st.columns(4)
    for i, (name, state, live, detail) in enumerate(items):
        cols[i % 4].markdown(_connector_tile(name, state, live, detail), unsafe_allow_html=True)

    with st.expander("🔌 Points connector — Step 2 card feed", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Connection", points_state)
        c2.metric("Points distributions", int(points.get("unique_distributions", 0)))
        c3.metric("Qualified", int(points.get("qualified", 0)))
        c4.metric("Final ready", int(points.get("final_ready", 0)))
        st.caption(
            f"Slate {points.get('day') or '—'} • source {points.get('source') or 'NONE'} • "
            f"lineups {points.get('lineup_ready_games',0)}/{points.get('games',0)}"
        )
        if bool(points.get("live")):
            st.success(
                "✅ Points card feed is ACTIVE. Completed same-day Points rows can now compete with PRA for the Daily Master Card."
            )
            st.info(
                "No pick is forced: only rows already marked model-qualified by the Points engine are eligible, and lineup-pending rows remain MONITOR."
            )
        else:
            st.info(
                "Points is not connected. Open WNBA → Points and run/restore its same-day production pass, then return here. PRA does not need to be rerun."
            )
        st.caption(
            "STEP 2 • Read/merge only. No Points simulation, restore, sportsbook request, projection change or regrade occurs on Final Decision. "
            "Existing one-pick-per-game and max-five safeguards apply across PRA + Points. Rebounds is untouched."
        )


def install() -> None:
    """Patch only Final Decision read/selection/presentation hooks."""
    final_ui._stored_rows = stored_rows_combined
    final_ui._best_offer_per_player_line = best_offer_market_aware
    final_ui._card_html = card_html_market_aware
    final_ui._why = why_market_aware
    final_ui._render_connectors = render_connectors_step2


__all__ = [
    "MODEL_VERSION", "stored_rows_combined", "best_offer_market_aware",
    "card_html_market_aware", "why_market_aware", "render_connectors_step2", "install",
]
