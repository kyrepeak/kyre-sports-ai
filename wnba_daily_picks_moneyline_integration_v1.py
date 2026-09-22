"""WNBA Daily Picks — Moneyline Step-9 six-market integration V1.

Extends the frozen five-market Daily Picks pipeline with a read-only Moneyline
feed. No source model is imported or run, no sportsbook/network refresh occurs,
no simulation is launched, and no source-model state is written.

Flow: Moneyline Step-8 source -> common schema -> safety -> cross-market
protection -> ranking -> Top-5 selection -> final production guard.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import re

import numpy as np
import pandas as pd

import wnba_daily_picks_ranking_v3 as five_rank
import wnba_daily_picks_standardizer_v3 as std3
import wnba_daily_picks_safety_v1 as safety_base
import wnba_daily_picks_moneyline_connector_v1 as money_feed
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking
import wnba_daily_picks_selection_v1 as selection
import wnba_daily_picks_guard_v3 as five_guard

MODEL_VERSION = "WNBA DAILY PICKS MONEYLINE INTEGRATION V1 • SIX MARKET READ ONLY"
STANDARD_SIMS = 5_000_000
MAX_QUOTE_AGE_MIN = 15.0
MAX_OUTPUT_AGE_MIN = 15.0
_ET = ZoneInfo("America/New_York")


def _text(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _num(v: Any) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _day(v: Any) -> str:
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(v).lower())


def _timestamp(v: Any):
    s = _text(v)
    if not s:
        return None
    clean = re.sub(r"\sET$", "", s, flags=re.IGNORECASE).strip()
    try:
        ts = pd.to_datetime(clean, errors="raise", utc=False)
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return ts.to_pydatetime()
    except Exception:
        return None


def _tip(day_str: str, v: Any):
    s = _text(v).replace(" ET", "").strip()
    if not s:
        return None
    try:
        return pd.Timestamp(f"{day_str} {s}").tz_localize(_ET).to_pydatetime()
    except Exception:
        return None


def _fresh_minutes(v: Any):
    s = _text(v).upper()
    if not s:
        return None
    if "STALE" in s:
        return float("inf")
    m = re.search(r"(\d+(?:\.\d+)?)\s*M", s)
    return float(m.group(1)) if m else (0.0 if "FRESH" in s else None)


def normalize_moneyline(day: Any) -> pd.DataFrame:
    target = _day(day)
    cols = list(std3.COMMON_COLUMNS)
    if not target or not money_feed.status(target).get("connected"):
        return pd.DataFrame(columns=cols)
    rows = money_feed.preview_rows(target, limit=50)
    if rows is None or rows.empty:
        return pd.DataFrame(columns=cols)
    out = rows.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out = out[cols].copy()
    valid = (
        out["Slate day"].map(_day).eq(target)
        & out["Market"].astype(str).str.upper().eq("MONEYLINE")
        & out["Side"].astype(str).str.upper().eq("MONEYLINE")
        & pd.to_numeric(out["Line"], errors="coerce").fillna(np.nan).eq(0.0)
        & pd.to_numeric(out["Simulation count"], errors="coerce").fillna(0).ge(STANDARD_SIMS)
        & out["Converged"].fillna(False).astype(bool)
        & out["Qualification state"].astype(str).str.upper().eq("PRODUCTION READY")
    )
    out = out.loc[valid].copy()
    return out.drop_duplicates(["Market", "Team", "Opponent", "Book"], keep="first").reset_index(drop=True)


def _proof_map(day_str: str):
    proof = money_feed.final_guard_proof(day_str)
    out = {}
    if proof is None or proof.empty:
        return out
    for _, r in proof.iterrows():
        key = (_norm(r.get("Team")), _norm(r.get("Opponent")), _norm(r.get("Book")))
        out[key] = r
    return out


def evaluate_moneyline(frame: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target = _day(slate_day)
    safecols = list(safety_base.SAFETY_COLUMNS)
    if frame is None or frame.empty:
        cols = list(frame.columns) if isinstance(frame, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in safecols if c not in cols])

    feed = money_feed.status(target)
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
            failures.append("team/opponent identity incomplete"); gates["Identity gate"] = "REJECT"
        else:
            gates["Identity gate"] = "PASS"

        market_ok = bool(
            _text(row.get("Market")).upper() == "MONEYLINE"
            and _text(row.get("Side")).upper() == "MONEYLINE"
            and abs(_num(row.get("Line"))) < 1e-9
            and _text(row.get("Book"))
            and np.isfinite(_num(row.get("Posted odds")))
            and 0.0 <= _num(row.get("Model probability")) <= 1.0
            and 0.0 <= _num(row.get("No-vig probability")) <= 1.0
        )
        if market_ok:
            gates["Market gate"] = "PASS"
        else:
            failures.append("exact Moneyline/book/odds/probability incomplete"); gates["Market gate"] = "REJECT"

        sims = _num(row.get("Simulation count"))
        if feed.get("connected") and np.isfinite(sims) and sims >= STANDARD_SIMS:
            gates["Simulation gate"] = "PASS"
        else:
            failures.append("5M Moneyline source proof missing"); gates["Simulation gate"] = "REJECT"

        if bool(row.get("Converged")):
            gates["Convergence gate"] = "PASS"
        else:
            failures.append("Moneyline Monte Carlo convergence missing"); gates["Convergence gate"] = "REJECT"

        proof = proofs.get((_norm(team), _norm(opp), _norm(row.get("Book"))))
        if proof is None:
            failures.append("exact Step-8 final Moneyline proof missing")
        elif _text(proof.get("Grade proof")).upper() != "QUALIFIED":
            failures.append("source Moneyline is not QUALIFIED")

        gates["Availability gate"] = "PASS" if feed.get("connected") else "REJECT"
        tip = _tip(target, proof.get("Tip ET proof") if proof is not None else None)
        if tip is None:
            holds.append("tip-time proof unavailable"); gates["Game-state gate"] = "HOLD"
        elif tip <= now:
            failures.append("game has reached/passed scheduled tip"); gates["Game-state gate"] = "REJECT"
        else:
            gates["Game-state gate"] = "PASS"

        age = _fresh_minutes(row.get("Freshness"))
        if age is None:
            holds.append("quote freshness proof unavailable"); gates["Freshness gate"] = "HOLD"
        elif age > MAX_QUOTE_AGE_MIN:
            failures.append(f"Moneyline quote stale ({age:.0f}m)"); gates["Freshness gate"] = "REJECT"
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


def _score_moneyline(row: pd.Series) -> dict:
    p = ranking._prob(row.get("Model probability"))
    nv = ranking._prob(row.get("No-vig probability"))
    edge = ranking._edge(row.get("Edge"))
    if not np.isfinite(edge) and np.isfinite(p) and np.isfinite(nv):
        edge = p - nv
    ev100 = ranking._num(row.get("EV / $100"))
    ev_source = "SOURCE"
    if not np.isfinite(ev100) and np.isfinite(p):
        ev100 = ranking._american_ev100(p, row.get("Posted odds")); ev_source = "DERIVED: model p + posted odds"

    rankable = bool(
        ranking._text(row.get("Safety state")).upper() == "SAFE"
        and np.isfinite(p) and np.isfinite(nv) and np.isfinite(edge) and np.isfinite(ev100)
    )
    if not rankable:
        return {
            "Rank state": "SCORE HOLD", "Ranking score": np.nan, "Raw score": np.nan,
            "Exposure penalty": np.nan, "Probability score": np.nan, "Edge score": np.nan,
            "EV score": np.nan, "Projection score": np.nan, "Freshness score": np.nan,
            "Quality score": np.nan, "EV / $100 ranked": ev100, "No-vig ranked": nv,
            "Edge ranked": edge, "Projection edge": np.nan, "EV source": ev_source,
        }

    probability_score = float(np.clip((p - 0.50) / 0.25, 0, 1) * 40)
    edge_score = float(np.clip(edge / 0.15, 0, 1) * 25)
    ev_score = float(np.clip(ev100 / 25.0, 0, 1) * 15)
    certainty_score = float(np.clip((p - 0.50) / 0.15, 0, 1) * 10)
    fresh = ranking._fresh_minutes(row.get("Freshness"))
    freshness_score = 2.0 if fresh is None else (5.0 if fresh <= 5 else (3.5 if fresh <= 10 else (1.5 if fresh <= 15 else 0.0)))
    quality_score = ranking._quality_points(row.get("Confidence"), row.get("Qualification state"))
    raw = probability_score + edge_score + ev_score + certainty_score + freshness_score + quality_score

    game_groups = max(int(ranking._num(row.get("Game candidate groups")) if np.isfinite(ranking._num(row.get("Game candidate groups"))) else 0) - 1, 0)
    team_groups = max(int(ranking._num(row.get("Team candidate groups")) if np.isfinite(ranking._num(row.get("Team candidate groups"))) else 0) - 1, 0)
    penalty = float(min(8.0, 0.75 * game_groups + 0.35 * team_groups))
    return {
        "Rank state": "RANKED", "Ranking score": max(raw - penalty, 0.0), "Raw score": raw,
        "Exposure penalty": penalty, "Probability score": probability_score, "Edge score": edge_score,
        "EV score": ev_score, "Projection score": certainty_score, "Freshness score": freshness_score,
        "Quality score": quality_score, "EV / $100 ranked": ev100, "No-vig ranked": nv,
        "Edge ranked": edge, "Projection edge": p - 0.50, "EV source": ev_source,
    }


def _rank_moneyline(protected: pd.DataFrame) -> pd.DataFrame:
    if protected is None or protected.empty:
        return pd.DataFrame()
    d = protected.loc[protected.get("Market", pd.Series("", index=protected.index)).astype(str).str.upper().eq("MONEYLINE")].copy()
    if d.empty:
        return d
    picked = []
    safe = d.loc[d["Safety state"].astype(str).str.upper().eq("SAFE")].copy()
    for _, group in safe.groupby("Candidate key", dropna=False, sort=False):
        scored = []
        for _, row in group.iterrows():
            scored.append((row.copy(), _score_moneyline(row)))
        if not scored:
            continue
        def key(item):
            row, s = item
            ev = ranking._num(s.get("EV / $100 ranked"))
            odds = ranking._num(row.get("Posted odds"))
            return (ev if np.isfinite(ev) else -1e9, odds if np.isfinite(odds) else -1e9)
        row, score = max(scored, key=key)
        for k, v in score.items():
            row[k] = v
        row["Quote selection"] = f"BEST OF {len(group)}" if len(group) > 1 else "ONLY QUOTE"
        picked.append(row)
    return pd.DataFrame(picked)


def build_six_market_selection(day: Any) -> dict:
    target = _day(day)
    base_bundle = five_rank.build_five_market_ranking(target)
    base_audit = base_bundle.get("audit") if isinstance(base_bundle, dict) else pd.DataFrame()
    if not isinstance(base_audit, pd.DataFrame):
        base_audit = pd.DataFrame()

    ml_common = normalize_moneyline(target)
    ml_audit = evaluate_moneyline(ml_common, target)
    audits = [f for f in (base_audit, ml_audit) if isinstance(f, pd.DataFrame) and not f.empty]
    audit = pd.concat(audits, ignore_index=True, sort=False) if audits else pd.DataFrame()
    protected = protection.annotate(audit)

    market = protected.get("Market", pd.Series("", index=protected.index)).astype(str).str.upper() if not protected.empty else pd.Series(dtype=str)
    base_ranked = ranking.rank_candidates(protected.loc[~market.isin(["SPREAD", "MONEYLINE"])].copy()) if not protected.empty else pd.DataFrame()
    spread_ranked = five_rank._rank_spread(protected)
    ml_ranked = _rank_moneyline(protected)
    pieces = [f for f in (base_ranked, spread_ranked, ml_ranked) if isinstance(f, pd.DataFrame) and not f.empty]
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
    feeds["MONEYLINE"] = money_feed.status(target)
    base_common = base_bundle.get("common") if isinstance(base_bundle, dict) else pd.DataFrame()
    if not isinstance(base_common, pd.DataFrame):
        base_common = pd.DataFrame()
    common_parts = [f for f in (base_common, ml_common) if isinstance(f, pd.DataFrame) and not f.empty]
    common = pd.concat(common_parts, ignore_index=True, sort=False) if common_parts else pd.DataFrame(columns=std3.COMMON_COLUMNS)

    return {
        "day": target, "feeds": feeds, "common": common, "audit": audit,
        "protected": protected, "ranked": ranked, "selected": selected, "skipped": skipped,
    }


def _moneyline_guard(rows: pd.DataFrame, slate_day: Any, now_et=None) -> pd.DataFrame:
    target = _day(slate_day)
    guardcols = list(five_guard.GUARD_COLUMNS)
    if rows is None or rows.empty:
        cols = list(rows.columns) if isinstance(rows, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in guardcols if c not in cols])

    feed = money_feed.status(target)
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
            blocked.append("Moneyline safety is not SAFE")
        if _day(row.get("Slate day")) != target:
            blocked.append("slate date mismatch"); gates["Slate recheck"] = "BLOCKED"
        else:
            gates["Slate recheck"] = "PASS"
        if feed.get("connected"):
            gates["Connector gate"] = "PASS"
        else:
            blocked.append("Moneyline source connector is not connected"); gates["Connector gate"] = "BLOCKED"

        proof = proofs.get((_norm(row.get("Team")), _norm(row.get("Opponent")), _norm(row.get("Book"))))
        exact_ok = bool(proof is not None and _text(proof.get("Grade proof")).upper() == "QUALIFIED")
        if exact_ok:
            gates["Exact quote gate"] = "PASS"
        else:
            blocked.append("exact QUALIFIED Moneyline Step-8 proof missing"); gates["Exact quote gate"] = "BLOCKED"

        sims = _num(row.get("Simulation count")); proof_sims = _num(proof.get("Simulation count proof")) if proof is not None else np.nan
        if np.isfinite(sims) and sims >= STANDARD_SIMS and np.isfinite(proof_sims) and proof_sims >= STANDARD_SIMS:
            gates["Simulation recheck"] = "PASS"
        else:
            blocked.append("5M Moneyline simulation proof missing"); gates["Simulation recheck"] = "BLOCKED"

        conv = bool(row.get("Converged")) and bool(proof.get("Converged proof")) if proof is not None else False
        if conv:
            gates["Convergence recheck"] = "PASS"
        else:
            blocked.append("Moneyline convergence proof missing"); gates["Convergence recheck"] = "BLOCKED"

        run_ts = _timestamp(proof.get("Run timestamp proof")) if proof is not None else _timestamp(feed.get("ran_at"))
        if run_ts is None:
            monitor.append("Moneyline availability snapshot time unavailable"); gates["Availability recheck"] = "MONITOR"
        else:
            age = max(0.0, (now - run_ts).total_seconds() / 60.0)
            if age > MAX_OUTPUT_AGE_MIN:
                monitor.append(f"Moneyline source snapshot is {age:.0f}m old"); gates["Availability recheck"] = "MONITOR"
            else:
                gates["Availability recheck"] = "PASS"

        tip = _tip(target, proof.get("Tip ET proof")) if proof is not None else None
        if tip is None:
            monitor.append("tip-time proof unavailable"); gates["Game-state recheck"] = "MONITOR"
        elif tip <= now:
            blocked.append("game has reached/passed scheduled tip"); gates["Game-state recheck"] = "BLOCKED"
        else:
            gates["Game-state recheck"] = "PASS"

        quote_ts = _timestamp(proof.get("Quote timestamp proof")) if proof is not None else None
        if quote_ts is None:
            monitor.append("exact Moneyline quote timestamp unavailable"); gates["Freshness recheck"] = "MONITOR"
        else:
            qage = max(0.0, (now - quote_ts).total_seconds() / 60.0)
            if qage > MAX_QUOTE_AGE_MIN:
                blocked.append(f"Moneyline quote stale at guard time ({qage:.0f}m)"); gates["Freshness recheck"] = "BLOCKED"
            else:
                gates["Freshness recheck"] = "PASS"

        if exact_ok and _text(row.get("Qualification state")).upper() == "PRODUCTION READY":
            gates["Finalization gate"] = "PASS"
        else:
            blocked.append("Moneyline source is not production-ready"); gates["Finalization gate"] = "BLOCKED"

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


def evaluate_six_market(selected: pd.DataFrame, slate_day: Any, *, feeds=None, now_et=None) -> pd.DataFrame:
    if selected is None or selected.empty:
        cols = list(selected.columns) if isinstance(selected, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in five_guard.GUARD_COLUMNS if c not in cols])
    work = selected.copy().reset_index(drop=True); work["__order"] = range(len(work))
    market = work.get("Market", pd.Series("", index=work.index)).astype(str).str.upper()
    outputs = []
    base_rows = work.loc[~market.eq("MONEYLINE")].copy()
    if not base_rows.empty:
        g = five_guard.evaluate_five_market(base_rows, slate_day, feeds=feeds or {}, now_et=now_et)
        if isinstance(g, pd.DataFrame) and not g.empty:
            outputs.append(g)
    ml_rows = work.loc[market.eq("MONEYLINE")].copy()
    if not ml_rows.empty:
        g = _moneyline_guard(ml_rows, slate_day, now_et=now_et)
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
        "moneyline_connected": bool((feeds.get("MONEYLINE", {}) or {}).get("connected")),
        "moneyline_common": count(common, "MONEYLINE"),
        "moneyline_safe": count(audit, "MONEYLINE", "Safety state", "SAFE"),
        "moneyline_ranked": count(ranked, "MONEYLINE", "Rank state", "RANKED"),
        "moneyline_selected": count(selected, "MONEYLINE"),
        "moneyline_ready": count(g, "MONEYLINE", "Guard state", "READY"),
        "selected": int(len(selected)) if isinstance(selected, pd.DataFrame) else 0,
        "guarded": int(len(g)),
        "coverage_pass": bool(len(g) == len(selected)) if isinstance(selected, pd.DataFrame) else False,
        "ready": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("READY").sum()) if not g.empty else 0,
        "monitor": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("MONITOR").sum()) if not g.empty else 0,
        "blocked": int(g.get("Guard state", pd.Series(dtype=str)).astype(str).str.upper().eq("BLOCKED").sum()) if not g.empty else 0,
        "simulations": 0, "network_requests": 0, "source_model_writes": 0, "backfills": 0,
    }


__all__ = [
    "MODEL_VERSION", "normalize_moneyline", "evaluate_moneyline", "build_six_market_selection",
    "evaluate_six_market", "ready_rows", "diagnostics",
]
