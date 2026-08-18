"""MLB Daily Game Picks V2.0.4 — Run Line + Total production connectors.

Adds the two remaining MLB game-market families to the Daily Game Picks production
bridge without changing their underlying model math:
- Run Line uses the existing Spread V15.2/V15.5 production engine at Standard
  150K simulations per modeled game and only grades a real posted full-game ±1.5.
- Total uses the existing Totals V17.1/V17.3 production engine at Standard
  150K simulations per modeled game and only grades a verified full-game sportsbook
  total from the existing V20.5 normalized odds feed.

Both connectors are bounded, resumable, preserve completed work, and fail closed
when a compatible sportsbook line is missing. Existing five production connectors,
Step 3 normalization, Step 5 ranking, and matchup identity firewalls are preserved.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import math
import re

import pandas as pd
import streamlit as st

import mlb_daily_game_picks_v203 as previous
import mlb_daily_game_picks_v200 as core
import spread_hub_v152 as spread
import totals_hub_v171 as totals
from live_odds_feed import get_api_key, get_bookmakers
from slate_odds_feed_v205 import slate_snapshots_for_games_v205

VERSION = "MLB Daily Game Picks V2.0.4 • ALL 7 MARKET FAMILIES"
SIMS = 150_000
PASS_TIMEOUT = 120
MAX_WORKERS = 6

_orig_production_candidates = previous._production_candidates


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _day(games):
    try:
        if games is None or games.empty:
            return ""
        return str(games.iloc[0].get("game_date") or "")[:10]
    except Exception:
        return ""


def _gpk(row):
    try:
        return int(float(row.get("game_pk")))
    except Exception:
        return None


def _actionable(row):
    status = str(row.get("status") or "").strip().lower()
    blocked = (
        "final", "game over", "completed", "in progress", "live",
        "postponed", "cancelled", "canceled", "suspended",
    )
    return not any(x in status for x in blocked)


def _clean_key(raw):
    key = str(raw or "").strip()
    if not key:
        return None
    upper = key.upper()
    if any(x in upper for x in (
        "PASTE_YOUR_KEY_HERE", "YOUR_API_KEY", "YOUR_KEY_HERE", "API_KEY_HERE"
    )):
        return None
    return key


def _odds_key(day):
    return f"dgp_prod_market_odds_v204::{day}"


def _get_odds(games_df, force=False):
    day = _day(games_df)
    state_key = _odds_key(day)
    if not force and st.session_state.get(state_key):
        return st.session_state[state_key], ""

    key = _clean_key(get_api_key())
    if not key:
        return {}, (
            "Sportsbook odds are not connected. Run Line and Total require a real "
            "posted full-game line; add ODDS_API_IO_KEY in Streamlit Secrets or connect "
            "the existing odds feed first. No line was fabricated."
        )
    try:
        snaps = slate_snapshots_for_games_v205(
            games_df, key, get_bookmakers()
        ) or {}
    except Exception as exc:
        return {}, f"Sportsbook market sync: {type(exc).__name__}: {exc}"

    if not snaps:
        return {}, "Sportsbook market sync returned no matched MLB games for this slate."
    st.session_state[state_key] = snaps
    return snaps, ""


def _snapshot(snaps, pk):
    if pk is None:
        return None
    return snaps.get(pk) or snaps.get(str(pk))


def _rl_market(snap):
    best = dict((snap or {}).get("best") or {})
    out = {}
    for side, key in (("away", "away_rl"), ("home", "home_rl")):
        item = best.get(key) or {}
        line = _finite(item.get("line"))
        if line is None or abs(abs(line) - 1.5) > 1e-6:
            continue
        out[side] = {
            "line": line,
            "price": item.get("price"),
            "book": item.get("book"),
        }
    return out


def _total_market(snap):
    snap = snap or {}
    status = str(snap.get("total_market_status") or "")
    best = dict(snap.get("best") or {})
    line = _finite(best.get("consensus_total"))
    if line is None or status not in {"consensus", "single_book"}:
        return None
    if not (6.0 <= line <= 13.5):
        return None
    return {"line": line, "status": status, "best": best}


def _runline_key(day):
    return f"dgp_prod_runline_v204::{day}"


def _total_key(day):
    return f"dgp_prod_total_v204::{day}"


def _runline_one(row, market):
    result = spread._scan_game(row, SIMS)
    team = str(result.get("team") or "")
    away = str(row.get("away_team") or "")
    home = str(row.get("home_team") or "")
    side = "away" if team == away else "home" if team == home else ""
    posted = market.get(side) if side else None
    line = _finite(result.get("line"))
    if not posted or line is None or abs(line - float(posted["line"])) > 1e-6:
        return "skip", None, (
            f"{away} @ {home}: model-selected Run Line side did not have the exact "
            "verified ±1.5 full-game market posted."
        )
    out = dict(result)
    out.update({
        "posted_line": float(posted["line"]),
        "posted_price": posted.get("price"),
        "posted_book": posted.get("book"),
        "market_verified": True,
    })
    return "ok", out, ""


def _total_one(row, market):
    result = totals._scan_ou_game(row, float(market["line"]), SIMS)
    lean = str(result.get("lean") or "").upper()
    best = market.get("best") or {}
    price_item = best.get("over" if lean == "OVER" else "under") or {}
    out = dict(result)
    out.update({
        "posted_line": float(market["line"]),
        "posted_price": price_item.get("price"),
        "posted_book": price_item.get("book"),
        "total_market_status": market.get("status"),
        "market_verified": True,
    })
    return "ok", out, ""


def _build_market(games_df, kind, previous_pack=None, force_odds=False):
    rows = [dict(r) for r in games_df.to_dict("records") if _actionable(r)]
    total_games = len(rows)
    snaps, odds_error = _get_odds(games_df, force=force_odds)
    if odds_error:
        return {
            "rows": [], "complete": False, "candidate_count": total_games,
            "market_count": 0, "remaining_count": total_games,
            "skipped_count": 0, "skipped_keys": [], "notes": [],
            "errors": [odds_error], "sim_depth": SIMS,
        }

    kept = {}
    skipped = set()
    notes = []
    errors = []
    if previous_pack and not previous_pack.get("complete"):
        for r in previous_pack.get("rows", []) or []:
            pk = _gpk(r)
            if pk is not None:
                kept[pk] = dict(r)
        for pk in previous_pack.get("skipped_keys", []) or []:
            try:
                skipped.add(int(pk))
            except Exception:
                pass
        for msg in previous_pack.get("notes", []) or []:
            notes.append(str(msg))

    markets = {}
    for row in rows:
        pk = _gpk(row)
        if pk is None or pk in kept or pk in skipped:
            continue
        snap = _snapshot(snaps, pk)
        if kind == "runline":
            market = _rl_market(snap)
            if not market:
                skipped.add(pk)
                notes.append(
                    f"{row.get('away_team')} @ {row.get('home_team')}: no verified standard ±1.5 full-game Run Line was posted."
                )
                continue
        else:
            market = _total_market(snap)
            if not market:
                skipped.add(pk)
                status = str((snap or {}).get("total_market_status") or "not_posted")
                notes.append(
                    f"{row.get('away_team')} @ {row.get('home_team')}: no verified usable full-game total ({status})."
                )
                continue
        markets[pk] = market

    pending = [r for r in rows if _gpk(r) in markets]
    market_count = len(kept) + len(pending)
    timed_out = False

    if pending:
        label = "Run Line" if kind == "runline" else "Total"
        finished0 = len(kept) + len(skipped)
        bar = st.progress(
            finished0 / max(total_games, 1),
            text=f"{label}: production models {finished0}/{total_games}",
        )
        pool = ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(pending)))
        futs = {}
        for row in pending:
            pk = _gpk(row)
            fn = _runline_one if kind == "runline" else _total_one
            futs[pool.submit(fn, row, markets[pk])] = row
        try:
            for fut in as_completed(futs, timeout=PASS_TIMEOUT):
                row = futs[fut]
                pk = _gpk(row)
                try:
                    status, result, msg = fut.result()
                except Exception as exc:
                    status, result, msg = "error", None, f"{type(exc).__name__}: {exc}"
                if status == "ok" and result:
                    kept[pk] = result
                elif status == "skip":
                    skipped.add(pk)
                    if msg:
                        notes.append(msg)
                else:
                    errors.append(
                        f"{row.get('away_team')} @ {row.get('home_team')}: {msg or 'model failed'}"
                    )
                finished = len(kept) + len(skipped)
                bar.progress(
                    min(1.0, finished / max(total_games, 1)),
                    text=f"{label}: production models {finished}/{total_games}",
                )
        except TimeoutError:
            timed_out = True
            errors.append(
                f"{label} pass reached the {PASS_TIMEOUT}-second safety limit. Tap CONTINUE {label.upper()} to finish only remaining games; completed games are preserved."
            )
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            bar.empty()

    accounted = len(kept) + len(skipped)
    remaining = max(0, total_games - accounted)
    complete = remaining == 0
    return {
        "rows": list(kept.values()),
        "complete": complete,
        "candidate_count": total_games,
        "market_count": market_count,
        "remaining_count": remaining,
        "skipped_count": len(skipped),
        "skipped_keys": sorted(skipped),
        "notes": notes,
        "errors": errors,
        "timed_out": timed_out,
        "sim_depth": SIMS,
    }


def _connector_row(games_df, kind):
    day = _day(games_df)
    is_rl = kind == "runline"
    key = _runline_key(day) if is_rl else _total_key(day)
    pack = st.session_state.get(key)
    title = "Run Line" if is_rl else "Total"
    icon = "🏃" if is_rl else "🧾"
    model_text = (
        "Spread V15.5 production math • Standard 150K/game • verified posted ±1.5 only"
        if is_rl else
        "Totals V17.3/V17.1 production math • Standard 150K/game • verified posted full-game total only"
    )

    c1, c2 = st.columns([4, 1])
    with c1:
        if pack and pack.get("complete") and pack.get("rows"):
            st.success(
                f"{icon} {title} production connector ready • {len(pack.get('rows',[]))} verified market(s) modeled • "
                f"{pack.get('skipped_count',0)} unavailable/unscored • 150K sims/game • {day}"
            )
        elif pack and (pack.get("rows") or pack.get("errors")):
            st.warning(
                f"{icon} {title} connector partial/not ready • {len(pack.get('rows',[]))} modeled • "
                f"{pack.get('remaining_count',0)} remaining • completed work preserved"
            )
        else:
            st.info(
                f"{icon} {title} connector is ready. {model_text}. No sportsbook line is fabricated."
            )

    with c2:
        if pack and not pack.get("complete") and pack.get("rows"):
            button = f"▶ CONTINUE {title.upper()}"
        elif pack and pack.get("complete"):
            button = f"↻ REFRESH {title.upper()}"
        else:
            button = f"{icon} CONNECT {title.upper()}"

        if st.button(button, use_container_width=True, key=f"dgp_{kind}_connect_v204::{day}"):
            resume = pack if pack and not pack.get("complete") else None
            force_odds = resume is None
            st.toast(f"{icon} {title} build started" if resume is None else f"{icon} Resuming {title}")
            status = st.status(f"{title} connector is working…", expanded=True)
            status.write(model_text)
            try:
                built = _build_market(games_df, kind, resume, force_odds=force_odds)
                st.session_state[key] = built
                if built.get("complete"):
                    status.update(
                        label=f"{title} pass complete — {len(built.get('rows',[]))} verified markets modeled",
                        state="complete", expanded=False,
                    )
                elif built.get("rows"):
                    status.update(
                        label=f"{title} partial — {built.get('remaining_count',0)} games remaining",
                        state="complete", expanded=True,
                    )
                else:
                    status.update(
                        label=f"{title} could not build a verified market yet",
                        state="error", expanded=True,
                    )
            except Exception as exc:
                st.session_state[key] = {
                    "rows": [], "complete": False, "candidate_count": 0,
                    "market_count": 0, "remaining_count": 0, "skipped_count": 0,
                    "skipped_keys": [], "notes": [],
                    "errors": [f"{type(exc).__name__}: {exc}"], "sim_depth": SIMS,
                }
                status.update(label=f"{title} error: {type(exc).__name__}", state="error", expanded=True)
            st.rerun()

    if pack and pack.get("skipped_count"):
        st.caption(
            f"ℹ️ {pack.get('skipped_count',0)} game(s) had no compatible verified posted {title} market and remain unscored rather than using a placeholder."
        )
    diagnostics = []
    if pack:
        diagnostics.extend(pack.get("errors") or [])
        diagnostics.extend(pack.get("notes") or [])
    if diagnostics:
        with st.expander(f"⚠️ {title} connector diagnostics ({len(diagnostics)})"):
            for msg in diagnostics:
                st.caption(str(msg))

    st.caption(f"🔌 Step 4 {'F' if is_rl else 'G'} V2.0.4: {model_text}.")


def _same_team(a, b):
    def norm(v):
        return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()
    aliases = {"oakland athletics": "athletics", "the athletics": "athletics"}
    aa, bb = aliases.get(norm(a), norm(a)), aliases.get(norm(b), norm(b))
    return bool(aa) and aa == bb


def _runline_candidates(row):
    day = str(row.get("game_date") or "")[:10]
    pack = st.session_state.get(_runline_key(day), {}) or {}
    gpk = core._gamepk(row)
    allowed = (row.get("away_team"), row.get("home_team"))
    out = []
    for r in pack.get("rows", []) or []:
        if not core._same_game(r, gpk):
            continue
        team = r.get("team")
        if not any(_same_team(team, x) for x in allowed):
            continue
        p = _finite(r.get("cover"))
        line = _finite(r.get("line"))
        if p is None or line is None or abs(abs(line) - 1.5) > 1e-6:
            continue
        c = core._scored(
            market="Run Line",
            name=team,
            side=f"{line:+g}",
            line=line,
            probability=p,
            reliability=core._confidence_rel(r.get("confidence")),
            data_quality=core._clamp((_finite(r.get("data_score"), 0.0) or 0.0) / 9.0),
            confirmed=core.step4.base.base.base._confirmed_flag(row),
            source="Spread V15.5 production model • verified posted ±1.5",
            team=team,
            extra={
                "fair_odds": r.get("fair_odds"),
                "projected_margin": r.get("projected_margin"),
                "simulations": r.get("simulations"),
                "mc_se": r.get("mc_se"),
                "converged": r.get("converged"),
                "posted_price": r.get("posted_price"),
                "posted_book": r.get("posted_book"),
            },
        )
        if c:
            out.append(c)
    return out


def _total_candidates(row):
    day = str(row.get("game_date") or "")[:10]
    pack = st.session_state.get(_total_key(day), {}) or {}
    gpk = core._gamepk(row)
    out = []
    for r in pack.get("rows", []) or []:
        if not core._same_game(r, gpk):
            continue
        p = _finite(r.get("lean_prob"))
        line = _finite(r.get("total_line"))
        lean = str(r.get("lean") or "").upper()
        if p is None or line is None or lean not in {"OVER", "UNDER"}:
            continue
        name = f"{row.get('away_team')} @ {row.get('home_team')}"
        c = core._scored(
            market="Total",
            name=name,
            side=f"{lean} {line:g}",
            line=line,
            probability=p,
            reliability=core._confidence_rel(r.get("confidence")),
            data_quality=core._clamp((_finite(r.get("data_score"), 0.0) or 0.0) / 9.0),
            confirmed=core.step4.base.base.base._confirmed_flag(row),
            source="Totals V17.3/V17.1 production model • verified posted full-game total",
            team=None,
            extra={
                "fair_odds": r.get("fair_lean"),
                "projected_total": r.get("projected_total"),
                "model_edge_runs": r.get("model_edge_runs"),
                "simulations": (r.get("simulation") or {}).get("simulations"),
                "push_probability": (r.get("simulation") or {}).get("p_push"),
                "posted_price": r.get("posted_price"),
                "posted_book": r.get("posted_book"),
                "market_status": r.get("total_market_status"),
            },
        )
        if c:
            out.append(c)
    return out


def _production_candidates(row, market):
    if market == "Run Line":
        return _runline_candidates(row)
    if market == "Total":
        return _total_candidates(row)
    return _orig_production_candidates(row, market)


# Patch both the V2.0.3 wrapper global and the V2.0 Step-5 core. V2.0.3's
# defensive render assignment then keeps this function installed on rerenders.
previous._production_candidates = _production_candidates
core._production_candidates = _production_candidates


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    previous._production_candidates = _production_candidates
    core._production_candidates = _production_candidates

    st.markdown("### 🎯 Complete the game-market bridge")
    _connector_row(games_df, "runline")
    _connector_row(games_df, "total")

    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
