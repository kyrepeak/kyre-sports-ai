"""WNBA Daily Picks — Game Total Step-9 seven-market integration V1.

Extends the frozen six-market Daily Picks pipeline with a read-only Game Total
feed. No source model is imported or run, no sportsbook/network refresh occurs,
no simulation is launched, and no source-model state is written.

Flow: Game Total Step-8 source -> common schema -> safety -> cross-market
protection -> ranking -> Top-5 selection -> final production guard.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import re

import numpy as np
import pandas as pd

import wnba_daily_picks_moneyline_integration_v1 as six
import wnba_daily_picks_ranking_v3 as five_rank
import wnba_daily_picks_standardizer_v3 as std3
import wnba_daily_picks_safety_v1 as safety_base
import wnba_daily_picks_game_total_connector_v1 as total_feed
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking
import wnba_daily_picks_selection_v1 as selection
import wnba_daily_picks_guard_v3 as five_guard

MODEL_VERSION = "WNBA DAILY PICKS GAME TOTAL INTEGRATION V1 • SEVEN MARKET READ ONLY"
STANDARD_SIMS = 5_000_000
MAX_QUOTE_AGE_MIN = 15.0
MAX_OUTPUT_AGE_MIN = 15.0
_ET = six._ET


def _text(v: Any) -> str:
    return six._text(v)


def _num(v: Any) -> float:
    return six._num(v)


def _day(v: Any) -> str:
    return six._day(v)


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(v).lower())


def normalize_game_total(day: Any) -> pd.DataFrame:
    target = _day(day)
    cols = list(std3.COMMON_COLUMNS)
    if not target or not total_feed.status(target).get("connected"):
        return pd.DataFrame(columns=cols)
    rows = total_feed.preview_rows(target, limit=50)
    if rows is None or rows.empty:
        return pd.DataFrame(columns=cols)
    out = rows.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out = out[cols].copy()
    valid = (
        out["Slate day"].map(_day).eq(target)
        & out["Market"].astype(str).str.upper().eq("GAME TOTAL")
        & out["Side"].astype(str).str.upper().isin(["OVER", "UNDER"])
        & pd.to_numeric(out["Line"], errors="coerce").notna()
        & pd.to_numeric(out["Simulation count"], errors="coerce").fillna(0).ge(STANDARD_SIMS)
        & out["Converged"].fillna(False).astype(bool)
        & out["Qualification state"].astype(str).str.upper().eq("PRODUCTION READY")
    )
    out = out.loc[valid].copy()
    return out.drop_duplicates(["Market", "Player", "Side", "Line", "Book"], keep="first").reset_index(drop=True)


def _proof_map(day_str: str):
    proof = total_feed.final_guard_proof(day_str)
    out = {}
    if proof is None or proof.empty:
        return out
    for _, r in proof.iterrows():
        line = _num(r.get("Line"))
        key = (
            _norm(r.get("Player")), _text(r.get("Side")).upper(),
            round(line, 4) if np.isfinite(line) else None, _norm(r.get("Book")),
        )
        out[key] = r
    return out


def _proof_for(row: pd.Series, proofs: dict):
    line = _num(row.get("Line"))
    key = (
        _norm(row.get("Player")), _text(row.get("Side")).upper(),
        round(line, 4) if np.isfinite(line) else None, _norm(row.get("Book")),
    )
    return proofs.get(key)


def evaluate_game_total(frame: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target = _day(slate_day)
    safecols = list(safety_base.SAFETY_COLUMNS)
    if frame is None or frame.empty:
        cols = list(frame.columns) if isinstance(frame, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in safecols if c not in cols])

    feed = total_feed.status(target)
    proofs = _proof_map(target)
    now = now_et or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)

    records = []
    for _, row in frame.copy().iterrows():
        failures, holds, gates = [], [], {}
        if _day(row.get("Slate day")) != target:
            failures.append("wrong/missing slate date"); gates["Slate gate"] = "REJECT"
        else:
            gates["Slate gate"] = "PASS"

        team, opp = _text(row.get("Team")), _text(row.get("Opponent"))
        if not team or not opp or _norm(team) == _norm(opp):
            failures.append("game identity incomplete"); gates["Identity gate"] = "REJECT"
        else:
            gates["Identity gate"] = "PASS"

        side = _text(row.get("Side")).upper()
        line = _num(row.get("Line"))
        market_ok = bool(
            _text(row.get("Market")).upper() == "GAME TOTAL"
            and side in {"OVER", "UNDER"}
            and np.isfinite(line)
            and _text(row.get("Book"))
            and np.isfinite(_num(row.get("Posted odds")))
            and 0.0 <= _num(row.get("Model probability")) <= 1.0
            and 0.0 <= _num(row.get("No-vig probability")) <= 1.0
        )
        if market_ok:
            gates["Market gate"] = "PASS"
        else:
            failures.append("exact Game Total side/line/book/probability incomplete"); gates["Market gate"] = "REJECT"

        sims = _num(row.get("Simulation count"))
        if feed.get("connected") and np.isfinite(sims) and sims >= STANDARD_SIMS:
            gates["Simulation gate"] = "PASS"
        else:
            failures.append("5M Game Total source proof missing"); gates["Simulation gate"] = "REJECT"

        if bool(row.get("Converged")):
            gates["Convergence gate"] = "PASS"
        else:
            failures.append("Game Total Monte Carlo convergence missing"); gates["Convergence gate"] = "REJECT"

        proof = _proof_for(row, proofs)
        if proof is None:
            failures.append("exact Step-8 final Game Total proof missing")
        elif _text(proof.get("Grade proof")).upper() != "QUALIFIED":
            failures.append("source Game Total is not QUALIFIED")

        gates["Availability gate"] = "PASS" if feed.get("connected") else "REJECT"
        tip = six._tip(target, proof.get("Tip ET proof") if proof is not None else None)
        if tip is None:
            holds.append("tip-time proof unavailable"); gates["Game-state gate"] = "HOLD"
        elif tip <= now:
            failures.append("game has reached/passed scheduled tip"); gates["Game-state gate"] = "REJECT"
        else:
            gates["Game-state gate"] = "PASS"

        age = six._fresh_minutes(row.get("Freshness"))
        if age is None:
            holds.append("quote freshness proof unavailable"); gates["Freshness gate"] = "HOLD"
        elif age > MAX_QUOTE_AGE_MIN:
            failures.append(f"Game Total quote stale ({age:.0f}m)"); gates["Freshness gate"] = "REJECT"
        else:
            gates["Freshness gate"] = "PASS"

        state = "REJECT" if failures else ("HOLD" if holds else "SAFE")
        rec = row.to_dict()
        rec.update({
            "Safety state": state,
            "Hard failures": " • ".join(dict.fromkeys(failures)) if failures else "none",
            "Holds": " • ".join(dict.fromkeys(holds)) if holds else "none",
            **{c: gates.get(c, "—") for c in safecols if c not in {"Safety state", "Hard failures", "Holds"}},
        })
        records.append(rec)
    return pd.DataFrame(records)


def _score_game_total(row: pd.Series) -> dict:
    # Game Total uses the same probability/edge/EV/freshness score scale as the
    # Moneyline game-market ranker; only the source market identity differs.
    return six._score_moneyline(row)


def _rank_game_total(protected: pd.DataFrame) -> pd.DataFrame:
    if protected is None or protected.empty:
        return pd.DataFrame()
    d = protected.loc[protected.get("Market", pd.Series("", index=protected.index)).astype(str).str.upper().eq("GAME TOTAL")].copy()
    if d.empty:
        return d
    picked = []
    safe = d.loc[d["Safety state"].astype(str).str.upper().eq("SAFE")].copy()
    for _, group in safe.groupby("Candidate key", dropna=False, sort=False):
        scored = [(row.copy(), _score_game_total(row)) for _, row in group.iterrows()]
        if not scored:
            continue
        def key(item):
            row, score = item
            ev = ranking._num(score.get("EV / $100 ranked"))
            odds = ranking._num(row.get("Posted odds"))
            return (ev if np.isfinite(ev) else -1e9, odds if np.isfinite(odds) else -1e9)
        row, score = max(scored, key=key)
        for k, v in score.items():
            row[k] = v
        row["Quote selection"] = f"BEST OF {len(group)}" if len(group) > 1 else "ONLY QUOTE"
        picked.append(row)
    return pd.DataFrame(picked)


def build_seven_market_selection(day: Any) -> dict:
    target = _day(day)
    base_bundle = six.build_six_market_selection(target)
    base_audit = base_bundle.get("audit") if isinstance(base_bundle, dict) else pd.DataFrame()
    if not isinstance(base_audit, pd.DataFrame):
        base_audit = pd.DataFrame()

    total_common = normalize_game_total(target)
    total_audit = evaluate_game_total(total_common, target)
    audits = [f for f in (base_audit, total_audit) if isinstance(f, pd.DataFrame) and not f.empty]
    audit = pd.concat(audits, ignore_index=True, sort=False) if audits else pd.DataFrame()
    protected = protection.annotate(audit)

    market = protected.get("Market", pd.Series("", index=protected.index)).astype(str).str.upper() if not protected.empty else pd.Series(dtype=str)
    base_ranked = ranking.rank_candidates(protected.loc[~market.isin(["SPREAD", "MONEYLINE", "GAME TOTAL"])].copy()) if not protected.empty else pd.DataFrame()
    spread_ranked = five_rank._rank_spread(protected)
    money_ranked = six._rank_moneyline(protected)
    total_ranked = _rank_game_total(protected)
    pieces = [f for f in (base_ranked, spread_ranked, money_ranked, total_ranked) if isinstance(f, pd.DataFrame) and not f.empty]
    ranked = pd.concat(pieces, ignore_index=True, sort=False) if pieces else pd.DataFrame()

    if not ranked.empty:
        mask = ranked["Rank state"].astype(str).str.upper().eq("RANKED")
        good = ranked.loc[mask].copy().sort_values(
            ["Ranking score", "Model probability", "Edge ranked", "EV / $100 ranked"],
            ascending=[False, False, False, False], na_position="last", kind="mergesort",
        )
        good["Rank"] = np.arange(1, len(good) + 1)
        holds = ranked.loc[~mask].copy(); holds["Rank"] = np.nan
        ranked = pd.concat([good, holds], ignore_index=True, sort=False)

    selected, skipped = selection.select_top5(ranked)
    feeds = dict(base_bundle.get("feeds", {}) if isinstance(base_bundle, dict) else {})
    feeds["GAME TOTAL"] = total_feed.status(target)
    base_common = base_bundle.get("common") if isinstance(base_bundle, dict) else pd.DataFrame()
    if not isinstance(base_common, pd.DataFrame):
        base_common = pd.DataFrame()
    common_parts = [f for f in (base_common, total_common) if isinstance(f, pd.DataFrame) and not f.empty]
    common = pd.concat(common_parts, ignore_index=True, sort=False) if common_parts else pd.DataFrame(columns=std3.COMMON_COLUMNS)

    return {
        "day": target, "feeds": feeds, "common": common, "audit": audit,
        "protected": protected, "ranked": ranked, "selected": selected, "skipped": skipped,
    }


def _game_total_guard(rows: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target = _day(slate_day)
    guardcols = list(five_guard.GUARD_COLUMNS)
    if rows is None or rows.empty:
        cols = list(rows.columns) if isinstance(rows, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in guardcols if c not in cols])

    feed = total_feed.status(target)
    proofs = _proof_map(target)
    now = now_et or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)
    records = []

    for _, row in rows.copy().iterrows():
        blocked, monitor, gates = [], [], {}
        if _text(row.get("Selection state")).upper() != "SELECTED" or _text(row.get("Rank state")).upper() != "RANKED":
            blocked.append("row is not a selected ranked candidate")
        if _text(row.get("Safety state")).upper() != "SAFE":
            blocked.append("Game Total safety is not SAFE")
        if _day(row.get("Slate day")) != target:
            blocked.append("slate date mismatch"); gates["Slate recheck"] = "BLOCKED"
        else:
            gates["Slate recheck"] = "PASS"
        if feed.get("connected"):
            gates["Connector gate"] = "PASS"
        else:
            blocked.append("Game Total source connector is not connected"); gates["Connector gate"] = "BLOCKED"

        proof = _proof_for(row, proofs)
        exact_ok = bool(proof is not None and _text(proof.get("Grade proof")).upper() == "QUALIFIED")
        if exact_ok:
            gates["Exact quote gate"] = "PASS"
        else:
            blocked.append("exact QUALIFIED Game Total Step-8 proof missing"); gates["Exact quote gate"] = "BLOCKED"

        sims = _num(row.get("Simulation count")); proof_sims = _num(proof.get("Simulation count proof")) if proof is not None else np.nan
        if np.isfinite(sims) and sims >= STANDARD_SIMS and np.isfinite(proof_sims) and proof_sims >= STANDARD_SIMS:
            gates["Simulation recheck"] = "PASS"
        else:
            blocked.append("5M Game Total simulation proof missing"); gates["Simulation recheck"] = "BLOCKED"

        conv = bool(row.get("Converged")) and (bool(proof.get("Converged proof")) if proof is not None else False)
        if conv:
            gates["Convergence recheck"] = "PASS"
        else:
            blocked.append("Game Total convergence proof missing"); gates["Convergence recheck"] = "BLOCKED"

        run_ts = six._timestamp(proof.get("Run timestamp proof")) if proof is not None else six._timestamp(feed.get("ran_at"))
        if run_ts is None:
            monitor.append("Game Total availability snapshot time unavailable"); gates["Availability recheck"] = "MONITOR"
        else:
            age = max(0.0, (now - run_ts).total_seconds() / 60.0)
            if age > MAX_OUTPUT_AGE_MIN:
                monitor.append(f"Game Total source snapshot is {age:.0f}m old"); gates["Availability recheck"] = "MONITOR"
            else:
                gates["Availability recheck"] = "PASS"

        tip = six._tip(target, proof.get("Tip ET proof")) if proof is not None else None
        if tip is None:
            monitor.append("tip-time proof unavailable"); gates["Game-state recheck"] = "MONITOR"
        elif tip <= now:
            blocked.append("game has reached/passed scheduled tip"); gates["Game-state recheck"] = "BLOCKED"
        else:
            gates["Game-state recheck"] = "PASS"

        quote_ts = six._timestamp(proof.get("Quote timestamp proof")) if proof is not None else None
        if quote_ts is None:
            monitor.append("exact Game Total quote timestamp unavailable"); gates["Freshness recheck"] = "MONITOR"
        else:
            qage = max(0.0, (now - quote_ts).total_seconds() / 60.0)
            if qage > MAX_QUOTE_AGE_MIN:
                blocked.append(f"Game Total quote stale at guard time ({qage:.0f}m)"); gates["Freshness recheck"] = "BLOCKED"
            else:
                gates["Freshness recheck"] = "PASS"

        if exact_ok and _text(row.get("Qualification state")).upper() == "PRODUCTION READY":
            gates["Finalization gate"] = "PASS"
        else:
            blocked.append("Game Total source is not production-ready"); gates["Finalization gate"] = "BLOCKED"

        state = "BLOCKED" if blocked else ("MONITOR" if monitor else "READY")
        reasons = blocked if blocked else monitor
        rec = row.to_dict()
        rec.update({
            "Guard state": state,
            "Guard reasons": " • ".join(dict.fromkeys(reasons)) if reasons else "ALL FINAL GUARDS PASSED",
            "Guard checked at ET": now.strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "Guard fingerprint": five_guard.four_guard.v1._row_fingerprint(row),
            **{c: gates.get(c, "—") for c in guardcols if c not in {"Guard state", "Guard reasons", "Guard checked at ET", "Guard fingerprint"}},
        })
        records.append(rec)
    return pd.DataFrame(records)


def evaluate_seven_market(selected: pd.DataFrame, slate_day: Any, *, feeds=None, now_et=None) -> pd.DataFrame:
    if selected is None or selected.empty:
        cols = list(selected.columns) if isinstance(selected, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in five_guard.GUARD_COLUMNS if c not in cols])
    work = selected.copy().reset_index(drop=True); work["__order"] = range(len(work))
    market = work.get("Market", pd.Series("", index=work.index)).astype(str).str.upper()
    outputs = []
    base_rows = work.loc[~market.eq("GAME TOTAL")].copy()
    if not base_rows.empty:
        g = six.evaluate_six_market(base_rows, slate_day, feeds=feeds or {}, now_et=now_et)
        if isinstance(g, pd.DataFrame) and not g.empty:
            outputs.append(g)
    total_rows = work.loc[market.eq("GAME TOTAL")].copy()
    if not total_rows.empty:
        g = _game_total_guard(total_rows, slate_day, now_et=now_et)
        if not g.empty:
            outputs.append(g)
    if not outputs:
        return pd.DataFrame()
    out = pd.concat(outputs, ignore_index=True, sort=False)
    if "__order" in out.columns:
        out = out.sort_values("__order", kind="mergesort").drop(columns="__order", errors="ignore")
    return out.reset_index(drop=True)


def ready_rows(guarded: pd.DataFrame) -> pd.DataFrame:
    return five_guard.ready_rows(guarded)


def diagnostics(bundle: dict, guarded: pd.DataFrame | None = None) -> dict:
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    audit = bundle.get("audit") if isinstance(bundle, dict) else pd.DataFrame()
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    def count(frame, market, state_col=None, state=None):
        if not isinstance(frame, pd.DataFrame) or frame.empty or "Market" not in frame.columns:
            return 0
        d = frame.loc[frame["Market"].astype(str).str.upper().eq(market)].copy()
        if state_col and state_col in d.columns:
            d = d.loc[d[state_col].astype(str).str.upper().eq(state)]
        return int(len(d))
    g = guarded if isinstance(guarded, pd.DataFrame) else pd.DataFrame()
    return {
        "game_total_connected": bool((feeds.get("GAME TOTAL", {}) or {}).get("connected")),
        "game_total_common": count(common, "GAME TOTAL"),
        "game_total_safe": count(audit, "GAME TOTAL", "Safety state", "SAFE"),
        "game_total_ranked": count(ranked, "GAME TOTAL", "Rank state", "RANKED"),
        "game_total_selected": count(selected, "GAME TOTAL"),
        "game_total_ready": count(g, "GAME TOTAL", "Guard state", "READY"),
        "selected": int(len(selected)) if isinstance(selected, pd.DataFrame) else 0,
        "guarded": int(len(g)),
        "coverage_pass": bool(len(g) == len(selected)) if isinstance(selected, pd.DataFrame) else False,
        "ready": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("READY").sum()) if not g.empty else 0,
        "monitor": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("MONITOR").sum()) if not g.empty else 0,
        "blocked": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("BLOCKED").sum()) if not g.empty else 0,
        "simulations": 0, "network_requests": 0, "source_model_writes": 0, "backfills": 0,
    }


__all__ = [
    "MODEL_VERSION", "normalize_game_total", "evaluate_game_total", "build_seven_market_selection",
    "evaluate_seven_market", "ready_rows", "diagnostics",
]
