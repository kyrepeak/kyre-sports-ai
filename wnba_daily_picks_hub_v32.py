"""WNBA Daily Picks V32 — Step 11 source-native finalization + visual Daily Picks board.

V32 preserves the verified V31.1 checkpointed Run-All-7 controller and all seven
source-model simulation contracts. It adds only post-controller production
materialization and presentation:

1) Finalize the source-owned post-Monte-Carlo layers that the controller intentionally
   stopped before (Rebounds 18-20, Assists 18-20, Moneyline 8, Game Total 8).
2) Re-use the existing seven-market read-only connectors and existing common-schema,
   safety, protection, ranking, selection and final guard pipeline.
3) Render a visual market-best board plus the guarded overall Daily Picks board with
   ESPN/WNBA player headshots and ESPN team logos when a player id is already present
   in the loaded source state.

No projection/probability/Monte-Carlo math is copied or changed. No simulation is
launched in Step 11. No pick is forced. Existing source qualification and Daily Picks
ranking/guard logic remain the sole owners of qualification and selection.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import re
import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v311 as v311
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_spread_connector_v1 as spread_feed
import wnba_daily_picks_moneyline_connector_v1 as money_feed
import wnba_daily_picks_game_total_connector_v1 as total_feed
import wnba_daily_picks_game_total_integration_v1 as seven

import wnba_rebounds_hub_v27 as rebounds18
import wnba_rebounds_hub_v28 as rebounds19
import wnba_rebounds_hub_v29 as rebounds20
import wnba_assists_hub_v20 as assists20
import wnba_moneyline_hub_v15 as money15
import wnba_game_total_hub_v15 as total15

MODEL_VERSION = "WNBA DAILY PICKS V32 • STEP 11 FINALIZE 7 FEEDS + VISUAL DAILY PICKS"
_ET = v311.base._ET
_FINALIZE_KEY = "ks_daily_picks_step11_finalize_v32"

_MARKET_ORDER = ("PRA", "POINTS", "REBOUNDS", "ASSISTS", "SPREAD", "MONEYLINE", "GAME TOTAL")
_FEEDS = {
    "PRA": pra_feed,
    "POINTS": points_feed,
    "REBOUNDS": rebounds_feed,
    "ASSISTS": assists_feed,
    "SPREAD": spread_feed,
    "MONEYLINE": money_feed,
    "GAME TOTAL": total_feed,
}
_MARKET_ICONS = {
    "PRA": "🧮", "POINTS": "🎯", "REBOUNDS": "🧱", "ASSISTS": "🧠",
    "SPREAD": "🏀", "MONEYLINE": "💰", "GAME TOTAL": "📊",
}

_TEAM_SLUG = {
    "ATL": "atl", "ATLANTA DREAM": "atl",
    "CHI": "chi", "CHICAGO SKY": "chi",
    "CON": "con", "CONNECTICUT SUN": "con",
    "DAL": "dal", "DALLAS WINGS": "dal",
    "IND": "ind", "INDIANA FEVER": "ind",
    "LVA": "lv", "LAS VEGAS ACES": "lv",
    "LAS": "la", "LOS ANGELES SPARKS": "la",
    "MIN": "min", "MINNESOTA LYNX": "min",
    "NYL": "ny", "NEW YORK LIBERTY": "ny",
    "PHX": "phx", "PHOENIX MERCURY": "phx",
    "SEA": "sea", "SEATTLE STORM": "sea",
    "WAS": "wsh", "WASHINGTON MYSTICS": "wsh",
    "GSV": "gs", "GOLDEN STATE VALKYRIES": "gs",
    "POR": "por", "PORTLAND FIRE": "por",
    "TOR": "tor", "TORONTO TEMPO": "tor",
}


def _today() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, (list, tuple)):
        try:
            return pd.DataFrame(list(value))
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _num(value: Any, default=np.nan) -> float:
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _master_complete(day: str) -> bool:
    master = st.session_state.get(v311._MASTER_RUN_KEY)
    return bool(
        isinstance(master, dict)
        and str(master.get("status") or "") == "7/7 COMPLETE"
        and str(master.get("day") or "") == str(day)
        and int(master.get("completed_markets") or 0) == 7
    )


def _status_snapshot(day: str) -> dict[str, dict[str, Any]]:
    return {market: dict(_FEEDS[market].status(day) or {}) for market in _MARKET_ORDER}


def _finalize_rebounds(day: str) -> tuple[bool, str]:
    if str(st.session_state.get("wnba_rebounds_step1_day") or "") != day:
        return False, "Rebounds source slate is not the current controller day."

    p18, l18, i18 = rebounds18._build_step18()
    r18 = bool(i18.get("ready"))
    st.session_state["wnba_rebounds_step18_ready"] = r18
    st.session_state["wnba_rebounds_step18_players"] = p18.to_dict("records") if not p18.empty else []
    st.session_state["wnba_rebounds_step18_lines"] = l18.to_dict("records") if not l18.empty else []
    if not r18:
        return False, str(i18.get("reason") or "native Rebounds Step 18 did not verify")

    p19, s19, i19 = rebounds19._build_step19()
    r19 = bool(i19.get("ready"))
    st.session_state["wnba_rebounds_step19_ready"] = r19
    st.session_state["wnba_rebounds_step19_players"] = p19.to_dict("records") if not p19.empty else []
    st.session_state["wnba_rebounds_step19_sides"] = s19.to_dict("records") if not s19.empty else []
    if not r19:
        return False, str(i19.get("reason") or "native Rebounds Step 19 did not verify")

    verified, qualified, final, _boards, i20 = rebounds20._build_step20()
    r20 = bool(i20.get("ready"))
    st.session_state["wnba_rebounds_step20_ready"] = r20
    st.session_state["wnba_rebounds_step20_all_sides"] = verified.to_dict("records") if not verified.empty else []
    st.session_state["wnba_rebounds_step20_qualified"] = qualified.to_dict("records") if not qualified.empty else []
    st.session_state["wnba_rebounds_step20_final_card"] = final.to_dict("records") if not final.empty else []
    if not r20:
        return False, str(i20.get("reason") or "native Rebounds Step 20 did not verify")
    return True, f"native Steps 18-20 verified • {int(i20.get('final_card') or 0)} final-card row(s)"


def _finalize_assists(day: str) -> tuple[bool, str]:
    # Assists V20 already owns the exact Step18→19→20 chain and standardized
    # production payload. Render it in a disposable slot so the source module,
    # not Daily Picks, remains the owner of its final qualification logic. The
    # existing Step-17 snapshot is reused; no Step-17 button is clicked here.
    for key in (
        f"wnba_assists_v20_candidates::{day}",
        f"wnba_assists_v20_qualified::{day}",
        f"wnba_assists_v20_top5::{day}",
        f"wnba_assists_v20_standard::{day}",
        f"wnba_assists_v20_diag::{day}",
    ):
        st.session_state.pop(key, None)

    slot = st.empty()
    try:
        with slot.container():
            assists20.render_wnba_assists_hub(None, None, None, None)
    finally:
        slot.empty()

    state = assists_feed.status(day)
    if not state.get("connected"):
        return False, str(state.get("detail") or "native Assists Step 20 did not produce a valid connector payload")
    return True, f"native Step 20 verified • {int(state.get('production_picks') or 0)} production pick(s)"


def _finalize_moneyline(day: str) -> tuple[bool, str]:
    mc = _frame(st.session_state.get("wnba_moneyline_v14_mc_detail"))
    meta = st.session_state.get("wnba_moneyline_v14_mc_meta")
    meta = dict(meta) if isinstance(meta, dict) else {}
    sim_ready = bool(
        str(st.session_state.get("wnba_moneyline_v14_mc_day") or "") == day
        and meta.get("simulation_ready")
        and str(meta.get("state") or "").upper() == "READY"
        and not mc.empty
    )
    sides, final, grade = money15._final_grade(mc, sim_ready)
    ready = bool(grade.get("grading_ready"))
    st.session_state["wnba_moneyline_v15_day"] = day
    st.session_state["wnba_moneyline_v15_grading_ready"] = ready
    st.session_state["wnba_moneyline_v15_final_card"] = final.to_dict("records") if not final.empty else []
    st.session_state["wnba_moneyline_v15_qualified_card"] = (
        final.loc[final.get("grade", pd.Series("", index=final.index)).astype(str).str.upper().eq("QUALIFIED")].to_dict("records")
        if not final.empty else []
    )
    st.session_state["wnba_moneyline_v15_grade_meta"] = dict(grade)
    if not ready:
        return False, "native Moneyline Step 8 final grading did not verify"
    return True, f"native Step 8 verified • {int(grade.get('qualified') or 0)} qualified game(s)"


def _finalize_game_total(day: str) -> tuple[bool, str]:
    mc = _frame(st.session_state.get("wnba_game_total_v14_mc_records"))
    if mc.empty:
        mc = _frame(st.session_state.get("wnba_game_total_v14_mc_rows"))
    meta = st.session_state.get("wnba_game_total_v14_mc_meta")
    meta = dict(meta) if isinstance(meta, dict) else {}
    sim_ready = bool(
        str(st.session_state.get("wnba_game_total_v14_mc_day") or "") == day
        and meta.get("simulation_ready")
        and str(meta.get("state") or "").upper() == "READY"
        and not mc.empty
    )
    sides, final, grade = total15._final_grade(mc, sim_ready)
    ready = bool(grade.get("grading_ready"))
    st.session_state["wnba_game_total_v15_day"] = day
    st.session_state["wnba_game_total_v15_grading_ready"] = ready
    st.session_state["wnba_game_total_v15_final_rows"] = final.to_dict("records") if not final.empty else []
    st.session_state["wnba_game_total_v15_grading_meta"] = dict(grade)
    if not ready:
        return False, "native Game Total Step 8 final grading did not verify"
    return True, f"native Step 8 verified • {int(grade.get('qualified') or 0)} qualified game(s)"


def _run_finalize(day: str) -> dict[str, Any]:
    if not _master_complete(day):
        return {
            "state": "BLOCKED", "day": day, "connected": 0,
            "reason": "Run All 7 must be COMPLETE on the current ET slate first.", "audit": [],
        }

    audit: list[dict[str, Any]] = []

    # PRA / Points / Spread already publish the source payload consumed by their
    # connector at the verified controller boundary. Re-check only; do not rerun.
    for market in ("PRA", "POINTS"):
        s = _FEEDS[market].status(day)
        audit.append({
            "Market": market, "Finalization": "SOURCE OUTPUT ALREADY OWNED",
            "State": "PASS" if s.get("connected") else "CHECK",
            "Detail": str(s.get("detail") or ""), "New simulations": 0,
        })

    for market, fn in (
        ("REBOUNDS", _finalize_rebounds),
        ("ASSISTS", _finalize_assists),
    ):
        try:
            ok, detail = fn(day)
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        audit.append({
            "Market": market, "Finalization": "NATIVE POST-MC SOURCE LAYERS",
            "State": "PASS" if ok else "CHECK", "Detail": detail, "New simulations": 0,
        })
        if not ok:
            return {
                "state": "STOPPED", "day": day, "connected": 0,
                "reason": f"{market} finalization failed: {detail}", "audit": audit,
            }

    spread = spread_feed.status(day)
    audit.append({
        "Market": "SPREAD", "Finalization": "SOURCE STEP 7 ALREADY FINAL-GRADED",
        "State": "PASS" if spread.get("connected") else "CHECK",
        "Detail": str(spread.get("detail") or ""), "New simulations": 0,
    })
    if not spread.get("connected"):
        return {
            "state": "STOPPED", "day": day, "connected": 0,
            "reason": "SPREAD connector is not healthy after the completed controller run.", "audit": audit,
        }

    for market, fn in (
        ("MONEYLINE", _finalize_moneyline),
        ("GAME TOTAL", _finalize_game_total),
    ):
        try:
            ok, detail = fn(day)
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        audit.append({
            "Market": market, "Finalization": "NATIVE FINAL GRADING",
            "State": "PASS" if ok else "CHECK", "Detail": detail, "New simulations": 0,
        })
        if not ok:
            return {
                "state": "STOPPED", "day": day, "connected": 0,
                "reason": f"{market} finalization failed: {detail}", "audit": audit,
            }

    feeds = _status_snapshot(day)
    connected = sum(int(bool(x.get("connected"))) for x in feeds.values())
    state = "7/7 CONNECTED" if connected == 7 else "CHECK"
    missing = [m for m, s in feeds.items() if not s.get("connected")]
    return {
        "state": state,
        "day": day,
        "connected": connected,
        "reason": "" if connected == 7 else "Connector validation waiting on: " + ", ".join(missing),
        "audit": audit,
        "finished_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        "new_simulations": 0,
    }


def _player_id_index() -> dict[str, int]:
    """Read already-loaded source state only; never performs a player lookup request."""
    out: dict[str, int] = {}
    name_cols = ("PLAYER_NAME", "Player", "player", "full_name", "display_name", "name")
    id_cols = ("PLAYER_ID", "Player ID", "player_id", "athlete_id", "person_id", "id")

    def inspect(frame: pd.DataFrame):
        if frame is None or frame.empty:
            return
        name_col = next((c for c in name_cols if c in frame.columns), None)
        id_col = next((c for c in id_cols if c in frame.columns), None)
        if not name_col or not id_col:
            return
        for _, r in frame[[name_col, id_col]].head(800).iterrows():
            name = _norm_name(r.get(name_col))
            pid = int(_num(r.get(id_col), 0) or 0)
            if name and pid > 0:
                out.setdefault(name, pid)

    for key in list(st.session_state.keys()):
        try:
            value = st.session_state.get(key)
        except Exception:
            continue
        if isinstance(value, pd.DataFrame):
            inspect(value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            try:
                inspect(pd.DataFrame(value[:800]))
            except Exception:
                pass
        elif isinstance(value, dict) and any(c in value for c in name_cols) and any(c in value for c in id_cols):
            try:
                inspect(pd.DataFrame([value]))
            except Exception:
                pass
    return out


def _team_logo(team: Any) -> str:
    raw = str(team or "").strip().upper()
    slug = _TEAM_SLUG.get(raw)
    if not slug:
        norm = re.sub(r"\s+", " ", raw).strip()
        slug = _TEAM_SLUG.get(norm)
    return f"https://a.espncdn.com/i/teamlogos/wnba/500/{slug}.png" if slug else ""


def _headshot(player: Any, ids: dict[str, int]) -> tuple[str, str]:
    pid = int(ids.get(_norm_name(player), 0) or 0)
    if pid <= 0:
        return "", ""
    espn = f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png"
    wnba = f"https://cdn.nba.com/headshots/wnba/latest/1040x760/{pid}.png"
    return espn, wnba


def _fmt_odds(value: Any) -> str:
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    return f"{int(round(x)):+d}"


def _fmt_pct(value: Any, signed: bool = False) -> str:
    x = _num(value)
    if not np.isfinite(x):
        return "—"
    # Common schema stores probabilities/edges as fractions.
    pct = 100.0 * x if abs(x) <= 1.5 else x
    return f"{pct:+.1f}%" if signed else f"{pct:.1f}%"


def _candidate_text(row: pd.Series) -> str:
    market = str(row.get("Market") or "").upper()
    side = str(row.get("Side") or "").upper()
    line = _num(row.get("Line"))
    if market == "SPREAD":
        return f"{row.get('Team')} {line:+g}" if np.isfinite(line) else f"{row.get('Team')} spread"
    if market == "MONEYLINE":
        return f"{row.get('Team')} ML"
    if market == "GAME TOTAL":
        return f"{side} {line:g}" if np.isfinite(line) else f"{side} game total"
    player = str(row.get("Player") or "Player")
    return f"{player} {side} {line:g}" if np.isfinite(line) else f"{player} {side}"


def _card(row: pd.Series, ids: dict[str, int], badge: str) -> str:
    market = str(row.get("Market") or "").upper()
    player = str(row.get("Player") or "").strip()
    team = str(row.get("Team") or "").strip()
    opp = str(row.get("Opponent") or "").strip()
    book = str(row.get("Book") or "").strip()
    prob = row.get("Model probability")
    fair = row.get("Fair odds")
    edge = row.get("Edge ranked") if pd.notna(row.get("Edge ranked")) else row.get("Edge")
    confidence = str(row.get("Confidence") or "—")
    sims = int(_num(row.get("Simulation count"), 0) or 0)
    candidate = _candidate_text(row)
    posted = _fmt_odds(row.get("Posted odds"))
    projection = _num(row.get("Projection"))

    logo = _team_logo(team)
    player_market = market in {"PRA", "POINTS", "REBOUNDS", "ASSISTS"}
    photo, wnba_fallback = _headshot(player, ids) if player_market else ("", "")
    if photo:
        photo_html = (
            f'<img class="dp32-head" src="{escape(photo)}" '
            f'onerror="this.onerror=null;this.src=\'{escape(wnba_fallback)}\';">'
        )
    elif logo:
        photo_html = f'<img class="dp32-head dp32-logohead" src="{escape(logo)}">'
    else:
        photo_html = '<div class="dp32-sil">◉</div>'
    logo_html = f'<img class="dp32-logo" src="{escape(logo)}">' if logo else ""
    proj_text = "—" if not np.isfinite(projection) else f"{projection:.2f}"

    return f"""
    <div class="dp32-card">
      <div class="dp32-kicker">{escape(_MARKET_ICONS.get(market,'🎟️'))} {escape(market)} • {escape(badge)}</div>
      <div class="dp32-main">
        <div class="dp32-photo">{photo_html}</div>
        <div class="dp32-who">
          <div class="dp32-name">{escape(player if player_market else team)}</div>
          <div class="dp32-match">{logo_html}{escape(team)} vs {escape(opp)}</div>
          <div class="dp32-pick">{escape(candidate)} <span>{escape(book)} {escape(posted)}</span></div>
        </div>
      </div>
      <div class="dp32-grid">
        <div><b>{_fmt_pct(prob)}</b><span>True probability</span></div>
        <div><b>{escape(_fmt_odds(fair))}</b><span>Fair odds</span></div>
        <div><b>{_fmt_pct(edge, signed=True)}</b><span>No-vig edge</span></div>
        <div><b>{escape(confidence)}</b><span>Confidence</span></div>
        <div><b>{escape(proj_text)}</b><span>Projection</span></div>
        <div><b>{sims:,}</b><span>Simulations</span></div>
      </div>
    </div>
    """


def _visual_bundle(day: str):
    bundle = seven.build_seven_market_selection(day)
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    if not isinstance(ranked, pd.DataFrame):
        ranked = pd.DataFrame()
    if not isinstance(selected, pd.DataFrame):
        selected = pd.DataFrame()
    guarded = seven.evaluate_seven_market(selected, day, feeds=feeds, now_et=datetime.now(_ET))
    if not isinstance(guarded, pd.DataFrame):
        guarded = pd.DataFrame()
    ready = seven.ready_rows(guarded)
    if not isinstance(ready, pd.DataFrame):
        ready = pd.DataFrame()
    return bundle, ranked, guarded, ready


def _market_best(ranked: pd.DataFrame, market: str) -> pd.DataFrame:
    if ranked is None or ranked.empty or "Market" not in ranked.columns:
        return pd.DataFrame()
    d = ranked.loc[ranked["Market"].astype(str).str.upper().eq(market)].copy()
    if "Rank state" in d.columns:
        d = d.loc[d["Rank state"].astype(str).str.upper().eq("RANKED")]
    if "Safety state" in d.columns:
        d = d.loc[d["Safety state"].astype(str).str.upper().eq("SAFE")]
    if d.empty:
        return d
    sort_cols = [c for c in ("Ranking score", "Model probability", "Edge ranked", "Edge", "EV / $100 ranked", "EV / $100") if c in d.columns]
    if sort_cols:
        d = d.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last", kind="mergesort")
    return d.head(1).copy()


def _render_visual_board(day: str):
    feeds = _status_snapshot(day)
    connected = sum(int(bool(s.get("connected"))) for s in feeds.values())
    st.markdown("## 🏆 Daily Picks Visual Command Center")
    st.caption(
        "Best source-qualified row from each connected market plus the existing guarded cross-market Top 5. "
        "Player headshots use already-loaded player IDs with ESPN primary / WNBA fallback; team logos use ESPN. "
        "No image lookup changes any model or ranking."
    )

    if connected < 7:
        missing = [m.title() for m, s in feeds.items() if not s.get("connected")]
        st.info("Visual publishing is waiting for all seven source connectors: " + ", ".join(missing) + ".")
        return

    try:
        bundle, ranked, guarded, ready = _visual_bundle(day)
    except Exception as exc:
        st.error(f"⛔ VISUAL BOARD CHECK • {type(exc).__name__}: {exc}")
        return

    ids = _player_id_index()
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    if not isinstance(common, pd.DataFrame): common = pd.DataFrame()
    if not isinstance(selected, pd.DataFrame): selected = pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Connected markets", f"{connected}/7")
    c2.metric("Common qualified rows", int(len(common)))
    c3.metric("Overall selected", int(len(selected)))
    c4.metric("FINAL READY", f"{int(len(ready))}/5")

    st.markdown("### ⭐ Best Qualified Pick From Each Market")
    st.caption("A market with zero source-qualified rows shows NO QUALIFIED PICK. Nothing is invented to fill the board.")
    st.markdown("""
    <style>
    .dp32-card{margin:12px 0;padding:17px;border:1px solid rgba(34,211,238,.28);border-radius:20px;background:linear-gradient(135deg,rgba(7,24,42,.98),rgba(8,34,50,.98));box-shadow:0 10px 24px rgba(0,0,0,.16)}
    .dp32-kicker{font-size:.72rem;font-weight:950;letter-spacing:.09em;color:#67e8f9;margin-bottom:9px}.dp32-main{display:flex;align-items:center;gap:13px}.dp32-photo{width:78px;height:78px;border-radius:50%;overflow:hidden;border:1px solid rgba(103,232,249,.32);display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,.6)}.dp32-head{width:78px;height:78px;object-fit:cover;object-position:center top}.dp32-logohead{object-fit:contain;padding:9px;box-sizing:border-box}.dp32-sil{font-size:42px;color:#64748b}.dp32-who{flex:1}.dp32-name{font-size:1.2rem;font-weight:950;color:#f8fafc}.dp32-match{display:flex;align-items:center;gap:6px;color:#94a3b8;font-weight:750;margin:3px 0 8px}.dp32-logo{width:22px;height:22px;object-fit:contain}.dp32-pick{font-weight:950;color:#e2e8f0}.dp32-pick span{display:inline-block;margin-left:7px;border-radius:999px;padding:4px 8px;background:rgba(148,163,184,.12);color:#cbd5e1;font-size:.72rem}.dp32-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:13px}.dp32-grid div{padding:9px 6px;border:1px solid rgba(148,163,184,.12);border-radius:11px;text-align:center;background:rgba(15,23,42,.35)}.dp32-grid b{display:block;color:#f8fafc;font-size:.92rem}.dp32-grid span{display:block;color:#7f91aa;font-size:.62rem;margin-top:2px}@media(max-width:760px){.dp32-grid{grid-template-columns:repeat(3,1fr)}}
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(2)
    for idx, market in enumerate(_MARKET_ORDER):
        best = _market_best(ranked, market)
        with cols[idx % 2]:
            if best.empty:
                st.info(f"{_MARKET_ICONS[market]} {market.title()} • NO QUALIFIED PICK")
            else:
                st.markdown(_card(best.iloc[0], ids, "MARKET #1"), unsafe_allow_html=True)

    st.markdown("### 🏁 Overall Daily Picks — Final Production Guard")
    if ready.empty:
        st.info("No cross-market selection is FINAL READY right now. The system will not force a Top 5.")
    else:
        d = ready.copy()
        rank_col = "Daily rank" if "Daily rank" in d.columns else ("Rank" if "Rank" in d.columns else None)
        if rank_col:
            d = d.sort_values(rank_col, ascending=True, na_position="last", kind="mergesort")
        for i, (_, row) in enumerate(d.head(5).iterrows(), start=1):
            st.markdown(_card(row, ids, "BEST OVERALL" if i == 1 else f"OVERALL #{i}"), unsafe_allow_html=True)

    if not guarded.empty:
        with st.expander("🛡️ Final-guard audit"):
            cols_show = [c for c in (
                "Daily rank", "Rank", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
                "Model probability", "Edge", "Ranking score", "Guard state", "Guard reasons"
            ) if c in guarded.columns]
            st.dataframe(guarded[cols_show], use_container_width=True, hide_index=True)


def _render_step11():
    day = _today()
    st.markdown("## 🔗 Step 11 — Finalize 7 Production Feeds + Build Daily Picks")
    st.caption(
        "Post-controller only. Reuses the completed 5M source snapshots, runs only native post-Monte-Carlo grading/finalization, "
        "then reads the existing seven connector contracts. New simulations = 0; source projection/Monte Carlo math is unchanged."
    )

    master_ok = _master_complete(day)
    before = _status_snapshot(day)
    before_connected = sum(int(bool(x.get("connected"))) for x in before.values())

    a, b, c, d = st.columns(4)
    a.metric("Run All 7", "COMPLETE" if master_ok else "REQUIRED")
    b.metric("Feeds connected", f"{before_connected}/7")
    c.metric("New simulations", "0")
    d.metric("Visual board", "READY" if before_connected == 7 else "WAITING")

    if not master_ok:
        st.warning("⚠️ STEP 11 LOCKED • complete Run All 7 on the current ET slate first.")
    if st.button(
        "🔗 FINALIZE ALL 7 + CONNECT DAILY PICKS",
        key="ks_daily_picks_finalize_all_7_v32",
        disabled=not master_ok,
        use_container_width=True,
        type="primary",
        help="Runs zero Monte Carlo simulations. It materializes only source-owned post-MC grading layers and validates all seven existing read-only connectors.",
    ):
        with st.spinner("Finalizing source-owned post-Monte-Carlo layers and validating all seven Daily Picks feeds…"):
            st.session_state[_FINALIZE_KEY] = _run_finalize(day)
        st.rerun()

    result = st.session_state.get(_FINALIZE_KEY)
    if isinstance(result, dict) and str(result.get("day") or "") == day:
        token = str(result.get("state") or "")
        if token == "7/7 CONNECTED":
            st.success("✅ STEP 11 PASSED • all 7 source feeds are connected to the existing guarded Daily Picks pipeline. New simulations: 0.")
        elif token in {"STOPPED", "BLOCKED", "CHECK"}:
            st.error("⛔ STEP 11 CHECK • " + str(result.get("reason") or token))
        audit = result.get("audit") or []
        if audit:
            with st.expander("🧾 Step-11 source finalization audit", expanded=token != "7/7 CONNECTED"):
                st.dataframe(pd.DataFrame(audit), use_container_width=True, hide_index=True)

    after = _status_snapshot(day)
    after_connected = sum(int(bool(x.get("connected"))) for x in after.values())
    rows = []
    for market in _MARKET_ORDER:
        s = after[market]
        rows.append({
            "Market": market,
            "State": s.get("state"),
            "Connected": bool(s.get("connected")),
            "Qualified": int(s.get("qualified") or s.get("production_picks") or 0),
            "Final ready": int(s.get("final_ready") or 0),
            "Completed sims": int(s.get("completed_sims") or 0),
            "Source": s.get("source"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if after_connected == 7:
        st.success("🏁 SEVEN-FEED CONNECTOR READY • 7/7 connected. Visual Daily Picks can publish only rows that survive the existing safety/ranking/final guard.")
        _render_visual_board(day)
    else:
        missing = [m.title() for m, s in after.items() if not s.get("connected")]
        st.info("Waiting on connector completion: " + ", ".join(missing) + ".")

    st.caption(
        "Step 11 V32 contract • native source qualification preserved • new simulations 0 • no backfills • no forced picks • "
        "existing common schema/safety/protection/ranking/selection/final guard preserved • image layer is presentation-only"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # V31.1 patches V31's Step-10 renderer on import. Render that verified master
    # controller first, then Step 11, then the complete frozen V21 seven-market
    # production/verification surface so its status cards reflect the new source state.
    v311.base._render_step10()
    _render_step11()
    return v311.base.v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
