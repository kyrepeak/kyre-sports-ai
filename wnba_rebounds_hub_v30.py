"""WNBA Rebounds V3.0 — production readiness hardening after the complete 1–20 model.

This layer does NOT create Step 21 and does NOT change any Steps 1–20 math.
It wraps the verified V2.9 final card with production safeguards:
- analysis timestamp in Eastern Time and UTC;
- exact selected slate-date audit and historical-slate hold;
- upcoming-game eligibility audit for every final-card selection;
- exact Step-14 quote timestamp reconciliation and freshness tiers;
- stale/unknown market holds instead of presenting an old quote as live-ready;
- duplicate player / duplicate exact-market protection;
- best-effort runtime final-card snapshot history and line/price movement audit;
- a compact production-cleared final-card panel;
- one-click market-cache refresh without rebooting the whole app.

The underlying player projection remains market-independent. This layer never
changes a projection, probability, edge, EV, ranking score, or qualification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v29 as base
import wnba_rebounds_hub_v22 as sgo_base
import wnba_rebounds_hub_v221 as sgo_tier
import wnba_schedule_v25 as schedule_v25

MODEL_VERSION = "WNBA REBOUNDS V3.0 • PRODUCTION READINESS GUARD • STEPS 1–20 PRESERVED"

ET = ZoneInfo("America/New_York")
QUOTE_FRESH_SECONDS = 5 * 60
QUOTE_STALE_SECONDS = 10 * 60
HISTORY_PATH = Path("wnba_rebounds_card_history.csv")
MAX_HISTORY_ROWS = 1500

HISTORY_COLUMNS = [
    "snapshot_id", "fingerprint", "created_at_et", "created_at_utc", "slate_day",
    "production_state", "hold_reason", "rank", "player", "team", "opponent",
    "book", "bookmaker_id", "line", "side", "posted_odds", "model_probability",
    "no_vig_edge", "expected_roi", "worst_edge", "confidence_grade",
    "quote_updated", "quote_age_seconds", "quote_freshness", "game_status",
    "tip_et",
]


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _now_pair():
    now_utc = datetime.now(timezone.utc)
    return now_utc, now_utc.astimezone(ET)


def _safe_day(value):
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(ET).strftime("%Y-%m-%d")


def _parse_utc(value):
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(ts) else ts
    except Exception:
        return None


def _quote_freshness(age_seconds):
    age = _num(age_seconds)
    if not np.isfinite(age):
        return "UNKNOWN"
    if age <= QUOTE_FRESH_SECONDS:
        return "FRESH ≤5m"
    if age <= QUOTE_STALE_SECONDS:
        return "WATCH 5–10m"
    return "STALE >10m"


def _slate(day: str):
    try:
        frame = schedule_v25.schedule_for_date(day)
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _game_context(team, opponent, slate: pd.DataFrame):
    if slate is None or slate.empty:
        return {"status": "UNKNOWN", "tip_et": "", "venue": "", "matched": False}
    t, o = _norm(team), _norm(opponent)
    for _, r in slate.iterrows():
        away = _norm(r.get("away_team"))
        home = _norm(r.get("home_team"))
        if {t, o} == {away, home}:
            return {
                "status": str(r.get("status") or "UNKNOWN").upper(),
                "tip_et": str(r.get("first_tip_et") or ""),
                "venue": str(r.get("venue") or ""),
                "matched": True,
            }
    return {"status": "UNKNOWN", "tip_et": "", "venue": "", "matched": False}


def _quote_for_pick(pick: pd.Series, quotes: pd.DataFrame):
    if quotes is None or quotes.empty:
        return None
    player = _norm(pick.get("Player"))
    team = _norm(pick.get("Team"))
    book = _norm(pick.get("Book"))
    book_id = _norm(pick.get("Bookmaker ID"))
    line = _num(pick.get("Line"))
    side = str(pick.get("Side") or "").upper()

    candidates = []
    for _, q in quotes.iterrows():
        if _norm(q.get("Player")) != player or _norm(q.get("Team")) != team:
            continue
        q_book = _norm(q.get("Book"))
        q_book_id = _norm(q.get("Bookmaker ID"))
        if book_id:
            if q_book_id != book_id:
                continue
        elif book and q_book != book:
            continue
        q_line = _num(q.get("Line"))
        if not np.isfinite(line) or not np.isfinite(q_line) or not math.isclose(line, q_line, abs_tol=1e-9):
            continue
        stamp_raw = q.get("Over updated") if side == "OVER" else q.get("Under updated")
        stamp = _parse_utc(stamp_raw)
        candidates.append((stamp, str(stamp_raw or ""), q))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0].value if x[0] is not None else -1, reverse=True)
    stamp, stamp_raw, row = candidates[0]
    return {"timestamp": stamp, "timestamp_raw": stamp_raw, "row": row}


def _chain_health():
    step1 = str(st.session_state.get("wnba_rebounds_step1_state") or "")
    step20 = bool(st.session_state.get("wnba_rebounds_step20_ready"))
    exposed = []
    failed = []
    for n in range(2, 21):
        key = f"wnba_rebounds_step{n}_ready"
        if key in st.session_state:
            ok = bool(st.session_state.get(key))
            exposed.append((n, ok))
            if not ok:
                failed.append(n)
    ok = bool(step1.startswith("VERIFIED") and step20 and not failed)
    return {
        "ok": ok,
        "step1": step1,
        "step20": step20,
        "exposed": len(exposed),
        "failed": failed,
    }


def _enrich_final_card(final: pd.DataFrame, quotes: pd.DataFrame, slate: pd.DataFrame, now_utc):
    if final is None or final.empty:
        return pd.DataFrame()
    rows = []
    for _, p in final.iterrows():
        out = p.to_dict()
        q = _quote_for_pick(p, quotes)
        stamp = q.get("timestamp") if q else None
        age = max(0.0, (pd.Timestamp(now_utc) - stamp).total_seconds()) if stamp is not None else np.nan
        freshness = _quote_freshness(age)
        game = _game_context(p.get("Team"), p.get("Opponent"), slate)
        game_status = str(game.get("status") or "UNKNOWN").upper()
        quote_ok = bool(np.isfinite(_num(age)) and _num(age) <= QUOTE_STALE_SECONDS)
        game_ok = bool(game.get("matched") and game_status == "UPCOMING")
        pick_ready = bool(quote_ok and game_ok)
        hold_parts = []
        if not q:
            hold_parts.append("QUOTE TIMESTAMP NOT RECONCILED")
        elif not quote_ok:
            hold_parts.append(f"QUOTE {freshness}")
        if not game.get("matched"):
            hold_parts.append("GAME NOT RECONCILED")
        elif not game_ok:
            hold_parts.append(f"GAME {game_status}")

        out.update({
            "Quote updated": q.get("timestamp_raw", "") if q else "",
            "Quote age sec": age,
            "Quote freshness": freshness,
            "Game status": game_status,
            "Tip ET": str(game.get("tip_et") or ""),
            "Venue": str(game.get("venue") or ""),
            "Production pick state": "READY" if pick_ready else "HOLD",
            "Production hold reason": "" if pick_ready else " • ".join(hold_parts),
        })
        rows.append(out)
    return pd.DataFrame(rows)


def _load_history():
    if not HISTORY_PATH.exists():
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    try:
        df = pd.read_csv(HISTORY_PATH)
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    for c in HISTORY_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HISTORY_COLUMNS]


def _write_history(df: pd.DataFrame):
    try:
        work = df.copy()
        for c in HISTORY_COLUMNS:
            if c not in work.columns:
                work[c] = np.nan
        work = work[HISTORY_COLUMNS].tail(MAX_HISTORY_ROWS)
        work.to_csv(HISTORY_PATH, index=False)
        return True
    except Exception:
        return False


def _card_fingerprint(card: pd.DataFrame, day: str, production_state: str):
    payload = []
    if card is not None and not card.empty:
        for _, r in card.sort_values("Rank" if "Rank" in card.columns else "Player").iterrows():
            payload.append({
                "player": str(r.get("Player") or ""),
                "book": str(r.get("Book") or ""),
                "bookmaker_id": str(r.get("Bookmaker ID") or ""),
                "line": _num(r.get("Line"), None),
                "side": str(r.get("Side") or ""),
                "odds": str(r.get("Posted odds") or ""),
                "quote": str(r.get("Quote updated") or ""),
                "pick_state": str(r.get("Production pick state") or ""),
            })
    else:
        payload = [{"state": "NO QUALIFIED PLAY"}]
    raw = json.dumps({"day": day, "production": production_state, "card": payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _append_snapshot(card: pd.DataFrame, day: str, production_state: str, hold_reason: str, now_utc, now_et):
    history = _load_history()
    fingerprint = _card_fingerprint(card, day, production_state)
    if not history.empty and history["fingerprint"].astype(str).eq(fingerprint).any():
        return history, fingerprint, False

    snapshot_id = now_et.strftime("%Y%m%dT%H%M%S%z")
    rows = []
    if card is None or card.empty:
        rows.append({
            "snapshot_id": snapshot_id, "fingerprint": fingerprint,
            "created_at_et": now_et.isoformat(), "created_at_utc": now_utc.isoformat(),
            "slate_day": day, "production_state": production_state, "hold_reason": hold_reason,
            "rank": 0, "player": "NO QUALIFIED PLAY",
        })
    else:
        for i, r in card.iterrows():
            rows.append({
                "snapshot_id": snapshot_id,
                "fingerprint": fingerprint,
                "created_at_et": now_et.isoformat(),
                "created_at_utc": now_utc.isoformat(),
                "slate_day": day,
                "production_state": production_state,
                "hold_reason": hold_reason,
                "rank": int(_num(r.get("Rank"), i + 1)),
                "player": str(r.get("Player") or ""),
                "team": str(r.get("Team") or ""),
                "opponent": str(r.get("Opponent") or ""),
                "book": str(r.get("Book") or ""),
                "bookmaker_id": str(r.get("Bookmaker ID") or ""),
                "line": _num(r.get("Line")),
                "side": str(r.get("Side") or ""),
                "posted_odds": str(r.get("Posted odds") or ""),
                "model_probability": _num(r.get("Model decision probability")),
                "no_vig_edge": _num(r.get("No-vig edge")),
                "expected_roi": _num(r.get("Expected ROI")),
                "worst_edge": _num(r.get("Sensitivity worst edge")),
                "confidence_grade": str(r.get("Confidence grade") or ""),
                "quote_updated": str(r.get("Quote updated") or ""),
                "quote_age_seconds": _num(r.get("Quote age sec")),
                "quote_freshness": str(r.get("Quote freshness") or ""),
                "game_status": str(r.get("Game status") or ""),
                "tip_et": str(r.get("Tip ET") or ""),
            })

    merged = pd.concat([history, pd.DataFrame(rows)], ignore_index=True, sort=False)
    ok = _write_history(merged)
    return (_load_history() if ok else history), fingerprint, bool(ok)


def _previous_snapshot(history: pd.DataFrame, day: str, current_fingerprint: str):
    if history is None or history.empty:
        return pd.DataFrame()
    part = history[
        history["slate_day"].astype(str).eq(str(day))
        & ~history["fingerprint"].astype(str).eq(str(current_fingerprint))
    ].copy()
    if part.empty:
        return pd.DataFrame()
    part["_created"] = pd.to_datetime(part["created_at_utc"], utc=True, errors="coerce")
    latest_id = part.sort_values("_created").iloc[-1]["snapshot_id"]
    return part[part["snapshot_id"].astype(str).eq(str(latest_id))].drop(columns=["_created"], errors="ignore")


def _movement_audit(previous: pd.DataFrame, current: pd.DataFrame):
    if previous is None or previous.empty:
        return pd.DataFrame()
    prev = previous[~previous["player"].astype(str).eq("NO QUALIFIED PLAY")].copy()
    curr = current.copy() if current is not None else pd.DataFrame()
    prev_map = {(_norm(r.get("player")), _norm(r.get("book")), str(r.get("side") or "").upper()): r for _, r in prev.iterrows()}
    curr_map = {(_norm(r.get("Player")), _norm(r.get("Book")), str(r.get("Side") or "").upper()): r for _, r in curr.iterrows()} if not curr.empty else {}
    rows = []
    for key in sorted(set(prev_map) | set(curr_map)):
        p = prev_map.get(key)
        c = curr_map.get(key)
        if p is None and c is not None:
            rows.append({"Player": c.get("Player"), "Book": c.get("Book"), "Side": c.get("Side"), "Change": "ADDED", "Previous line": np.nan, "Current line": c.get("Line"), "Previous odds": "", "Current odds": c.get("Posted odds")})
        elif c is None and p is not None:
            rows.append({"Player": p.get("player"), "Book": p.get("book"), "Side": p.get("side"), "Change": "DROPPED", "Previous line": p.get("line"), "Current line": np.nan, "Previous odds": p.get("posted_odds"), "Current odds": ""})
        else:
            prev_line, curr_line = _num(p.get("line")), _num(c.get("Line"))
            prev_odds, curr_odds = str(p.get("posted_odds") or ""), str(c.get("Posted odds") or "")
            line_moved = not (np.isfinite(prev_line) and np.isfinite(curr_line) and math.isclose(prev_line, curr_line, abs_tol=1e-9))
            odds_moved = prev_odds != curr_odds
            if line_moved or odds_moved:
                rows.append({"Player": c.get("Player"), "Book": c.get("Book"), "Side": c.get("Side"), "Change": "LINE + PRICE" if line_moved and odds_moved else "LINE" if line_moved else "PRICE", "Previous line": prev_line, "Current line": curr_line, "Previous odds": prev_odds, "Current odds": curr_odds})
    return pd.DataFrame(rows)


def _render_production_guard():
    now_utc, now_et = _now_pair()
    day = _safe_day(st.session_state.get("wnba_rebounds_step1_day") or now_et.date())
    today_et = now_et.strftime("%Y-%m-%d")

    # Production-only rollover state. Never mutate any Streamlit widget key.
    previous_day = str(st.session_state.get("wnba_rebounds_prod_guard_day") or "")
    if previous_day and previous_day != day:
        for key in ("wnba_rebounds_prod_guard_fingerprint", "wnba_rebounds_prod_guard_state"):
            st.session_state.pop(key, None)
    st.session_state["wnba_rebounds_prod_guard_day"] = day

    final = pd.DataFrame(st.session_state.get("wnba_rebounds_step20_final_card") or [])
    quotes = pd.DataFrame(st.session_state.get("wnba_rebounds_step14_quotes") or [])
    slate = _slate(day)
    chain = _chain_health()
    card = _enrich_final_card(final, quotes, slate, now_utc)

    duplicate_player = bool(not card.empty and card["Player"].astype(str).duplicated().any())
    duplicate_market = bool(
        not card.empty
        and card.duplicated(subset=[c for c in ["Player", "Book", "Line", "Side"] if c in card.columns]).any()
    )
    historical = day < today_et
    future = day > today_et
    pick_holds = int(card.get("Production pick state", pd.Series(dtype=str)).astype(str).eq("HOLD").sum()) if not card.empty else 0
    stale = int(card.get("Quote freshness", pd.Series(dtype=str)).astype(str).eq("STALE >10m").sum()) if not card.empty else 0
    unknown_quotes = int(card.get("Quote freshness", pd.Series(dtype=str)).astype(str).eq("UNKNOWN").sum()) if not card.empty else 0
    watch = int(card.get("Quote freshness", pd.Series(dtype=str)).astype(str).eq("WATCH 5–10m").sum()) if not card.empty else 0

    holds = []
    if not chain.get("ok"):
        holds.append("FULL 1–20 CHAIN NOT VERIFIED")
    if historical:
        holds.append("HISTORICAL SLATE DATE")
    if duplicate_player:
        holds.append("DUPLICATE PLAYER ON FINAL CARD")
    if duplicate_market:
        holds.append("DUPLICATE EXACT MARKET")
    if pick_holds:
        holds.append(f"{pick_holds} PICK(S) FAIL LIVE QUOTE/GAME ELIGIBILITY")

    if not final.empty:
        production_ready = bool(not holds)
        production_state = "READY" if production_ready else "HOLD"
    else:
        production_ready = bool(chain.get("ok") and not historical)
        production_state = "READY • NO PLAY" if production_ready else "HOLD"
        if not chain.get("ok") and "FULL 1–20 CHAIN NOT VERIFIED" not in holds:
            holds.append("FULL 1–20 CHAIN NOT VERIFIED")

    hold_reason = " • ".join(holds)
    history, fingerprint, snapshot_written = _append_snapshot(
        card, day, production_state, hold_reason, now_utc, now_et
    ) if chain.get("ok") else (_load_history(), "", False)
    st.session_state["wnba_rebounds_prod_guard_fingerprint"] = fingerprint
    st.session_state["wnba_rebounds_prod_guard_state"] = production_state
    st.session_state["wnba_rebounds_prod_guard_ready"] = production_ready
    st.session_state["wnba_rebounds_prod_guard_card"] = card.to_dict("records") if not card.empty else []

    previous = _previous_snapshot(history, day, fingerprint) if fingerprint else pd.DataFrame()
    movement = _movement_audit(previous, card)

    st.markdown("## 🛡️ Production Readiness Guard")
    st.caption(
        "Steps 1–20 remain unchanged. This post-model guard checks slate date, game eligibility, exact quote freshness, "
        "duplicates and card movement before calling a model-qualified selection production-ready."
    )

    a, b, c, d = st.columns(4)
    a.metric("Model chain", "20/20" if chain.get("ok") else "CHECK")
    b.metric("Slate date", day)
    if card.empty:
        c.metric("Live quote audit", "NO CARD")
    else:
        c.metric("Live quote audit", f"{len(card)-pick_holds}/{len(card)}")
    d.metric("Production", production_state)

    st.caption(
        f"Analysis timestamp: {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')} • "
        f"UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} • "
        f"Slate relation: {'HISTORICAL' if historical else 'FUTURE' if future else 'TODAY'}"
    )

    if production_ready and not card.empty:
        msg = f"✅ PRODUCTION READY • {len(card)} qualified selection(s) passed live-game and quote-freshness guards."
        if watch:
            msg += f" {watch} quote(s) are in the 5–10 minute WATCH window; recheck before placement."
        st.success(msg)
    elif production_ready:
        st.success("✅ PRODUCTION READY • full 1–20 chain verified; there is currently NO QUALIFIED PLAY.")
    else:
        st.error(
            "⛔ PRODUCTION HOLD • " + (hold_reason or "production guard is incomplete") + ". "
            "The underlying model output is preserved, but it is not labeled live-ready."
        )

    if stale or unknown_quotes:
        st.warning(
            f"Market freshness: {stale} stale quote(s), {unknown_quotes} unknown timestamp(s). "
            "Use the market recheck below; a full app reboot is not needed for ordinary quote refreshes."
        )

    st.markdown("### 🚦 Production Final Card")
    if card.empty:
        st.info("NO QUALIFIED PLAY — the model will not force a card.")
    else:
        show = card.copy()
        for c in ["Model decision probability", "No-vig edge", "Expected ROI", "Sensitivity worst edge"]:
            if c in show.columns:
                show[c] = (100.0 * pd.to_numeric(show[c], errors="coerce")).round(2)
        if "Quote age sec" in show.columns:
            show["Quote age"] = pd.to_numeric(show["Quote age sec"], errors="coerce").map(
                lambda x: "—" if pd.isna(x) else f"{int(round(x))}s"
            )
        cols = [c for c in [
            "Rank", "Player", "Team", "Opponent", "Book", "Line", "Side", "Posted odds",
            "Model decision probability", "No-vig edge", "Expected ROI", "Sensitivity worst edge",
            "Confidence grade", "Quote freshness", "Quote age", "Game status", "Tip ET",
            "Production pick state", "Production hold reason",
        ] if c in show.columns]
        st.dataframe(show[cols], hide_index=True, use_container_width=True)

    if st.button(
        "🔄 RECHECK MARKET FRESHNESS + FINAL CARD",
        use_container_width=True,
        key="wnba_rebounds_prod_market_recheck_v30",
    ):
        try:
            sgo_tier._fetch_sgo_events_tier_safe.clear()
        except Exception:
            pass
        try:
            sgo_base._fetch_sgo_events.clear()
        except Exception:
            pass
        st.rerun()

    with st.expander("📡 Line / price movement since previous snapshot"):
        if previous.empty:
            st.info("No earlier snapshot for this slate date yet.")
        elif movement.empty:
            st.success("No final-card line/price movement detected versus the previous distinct snapshot.")
        else:
            st.dataframe(movement, hide_index=True, use_container_width=True)

    with st.expander("🗂️ Final-card snapshot history"):
        day_hist = history[history["slate_day"].astype(str).eq(day)].copy() if not history.empty else pd.DataFrame()
        if day_hist.empty:
            st.info("No runtime card snapshots saved for this slate date yet.")
        else:
            ids = day_hist[["snapshot_id", "created_at_et", "fingerprint", "production_state"]].drop_duplicates().copy()
            ids = ids.sort_values("created_at_et", ascending=False).head(12)
            st.dataframe(ids, hide_index=True, use_container_width=True)
            csv_bytes = day_hist.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export this slate's rebound-card history CSV",
                data=csv_bytes,
                file_name=f"wnba_rebounds_card_history_{day}.csv",
                mime="text/csv",
                use_container_width=True,
                key="wnba_rebounds_prod_history_download_v30",
            )
        if snapshot_written:
            st.caption("New distinct card state saved to runtime history on this render.")

    with st.expander("🛡️ Production-guard diagnostics"):
        st.write({
            "model_version": MODEL_VERSION,
            "chain_ok": chain.get("ok"),
            "step1_state": chain.get("step1"),
            "step20_ready": chain.get("step20"),
            "explicit_failed_ready_steps": chain.get("failed"),
            "selected_slate_day": day,
            "today_et": today_et,
            "historical_slate_hold": historical,
            "future_slate": future,
            "quote_fresh_seconds": QUOTE_FRESH_SECONDS,
            "quote_stale_seconds": QUOTE_STALE_SECONDS,
            "watch_quotes": watch,
            "stale_quotes": stale,
            "unknown_quote_timestamps": unknown_quotes,
            "duplicate_player": duplicate_player,
            "duplicate_exact_market": duplicate_market,
            "production_state": production_state,
            "hold_reason": hold_reason or None,
            "snapshot_path": str(HISTORY_PATH),
            "snapshot_persistence": "best-effort Streamlit runtime filesystem; export CSV for durable copy",
            "projection_math_changed": False,
            "ranking_math_changed": False,
            "new_projection_inputs": 0,
        })

    st.caption(
        "⚡ V3.0 production hardening • Steps 1–20 math unchanged • stale quote + started-game protection • "
        "analysis timestamps • duplicate guard • runtime snapshot/movement ledger • market recheck without reboot."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step20_ready"):
        _render_production_guard()
    else:
        st.info("Production Readiness Guard remains locked until the complete Steps 1–20 chain is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
