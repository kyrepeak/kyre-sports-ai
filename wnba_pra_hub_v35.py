"""WNBA PRA V3.5 — lineup-aware finalization + targeted Monte Carlo refresh.

V3.5 keeps the verified V3.4.1 Eastern-date slate and multi-source availability
repairs, then hardens the handoff from a 5M MONITOR result to a true final card:

- explicit RECHECK STARTERS + INJURIES control;
- basketball-state changes are tracked per game so unaffected 5M/10M rows can be
  retained while only changed games are marked dirty;
- targeted 5M rebuild for dirty games rather than intentionally discarding the
  unaffected game;
- targeted 10M finalist/close-call simulation after explicit starting fives are
  verified;
- the Step-9 card stays MONITOR until the row has both confirmed lineups and a
  completed 10M finalist pass.

Projection formulas, matchup weights, SportsGameOdds grading, 5M/10M counts and
market-independence rules are unchanged.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_pra_hub_v34 as v34
import wnba_pra_hub_v33 as v33
import wnba_pra_integrity_v33 as integrity
import wnba_pra_persist_v33 as persist
import wnba_pra_final_v32 as final32
import wnba_pra_monte_carlo_v311 as monte
import wnba_availability_v33 as availability
import wnba_rotowire_status_v34 as rotowire

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "PRA V3.5 • LINEUP-AWARE FINALIZATION"
MLB_FROZEN_BASELINE = v34.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = v34.MLB_FROZEN_BRANCH


def _day(day) -> str:
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _num(value, default=None):
    try:
        x = float(value)
        return x if pd.notna(x) else default
    except Exception:
        return default


def _roundish(value):
    x = _num(value, None)
    return None if x is None else round(float(x), 4)


def _active_schedule(day):
    try:
        schedule = availability.schedule_for_date(day)
    except Exception:
        schedule = pd.DataFrame()
    if not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return pd.DataFrame()
    out = schedule.copy()
    status = out.get("status", out.get("status_text", pd.Series("", index=out.index))).astype(str).str.upper()
    return out.loc[~status.str.contains("FINAL", na=False)].copy().reset_index(drop=True)


def _lineup_snapshot(day):
    """Return explicit starter counts for every active game. Never infer starters."""
    schedule = _active_schedule(day)
    try:
        stats = availability.player_form_table()
    except Exception:
        stats = pd.DataFrame()
    rows = []
    for _, game in schedule.iterrows():
        gid = str(game.get("game_id") or "")
        away_id = int(game.get("away_team_id") or 0)
        home_id = int(game.get("home_team_id") or 0)
        try:
            av = availability.availability_for_game(game, stats)
            counts = av.get("starter_counts") or {}
            away_count = int(counts.get(away_id, 0))
            home_count = int(counts.get(home_id, 0))
            connected = bool(av.get("summary_connected"))
        except Exception:
            away_count = home_count = 0
            connected = False
        rows.append({
            "game_id": gid,
            "away": str(game.get("away_team") or "Away"),
            "home": str(game.get("home_team") or "Home"),
            "away_starters": away_count,
            "home_starters": home_count,
            "ready": bool(away_count >= 5 and home_count >= 5),
            "provider_connected": connected,
        })
    return pd.DataFrame(rows)


def _game_fingerprints(day):
    """Stable per-game basketball fingerprints used for selective invalidation."""
    integrity.install_runtime_guards()
    try:
        projections, meta, _lookup = integrity._projection_map(day)
    except Exception:
        projections, meta = pd.DataFrame(), {}
    schedule = meta.get("schedule") if isinstance(meta, dict) else pd.DataFrame()
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame()

    lineup = _lineup_snapshot(day)
    lineup_map = {
        str(r.get("game_id") or ""): bool(r.get("ready"))
        for _, r in lineup.iterrows()
    } if not lineup.empty else {}

    game_ids = set()
    if not schedule.empty and "game_id" in schedule.columns:
        game_ids.update(schedule["game_id"].astype(str).tolist())
    if isinstance(projections, pd.DataFrame) and not projections.empty and "game_id" in projections.columns:
        game_ids.update(projections["game_id"].astype(str).tolist())

    out = {}
    for gid in sorted(g for g in game_ids if g):
        game_obj = {}
        if not schedule.empty and "game_id" in schedule.columns:
            g = schedule.loc[schedule["game_id"].astype(str).eq(gid)]
            if not g.empty:
                r = g.iloc[0]
                game_obj = {
                    "status": str(r.get("status") or r.get("status_text") or ""),
                    "away": int(_num(r.get("away_team_id"), 0) or 0),
                    "home": int(_num(r.get("home_team_id"), 0) or 0),
                }
        players = []
        if isinstance(projections, pd.DataFrame) and not projections.empty and "game_id" in projections.columns:
            p = projections.loc[projections["game_id"].astype(str).eq(gid)].copy()
            sort_cols = [c for c in ["TEAM_ID", "PLAYER_ID", "PLAYER_NAME"] if c in p.columns]
            if sort_cols:
                p = p.sort_values(sort_cols, kind="mergesort")
            for _, row in p.iterrows():
                players.append({
                    "pid": str(row.get("PLAYER_ID") or ""),
                    "player": str(row.get("PLAYER_NAME") or ""),
                    "team": int(_num(row.get("TEAM_ID"), 0) or 0),
                    "designation": str(row.get("DESIGNATION") or "STATUS UNVERIFIED").upper(),
                    "verified": bool(row.get("AVAILABILITY_VERIFIED", False)),
                    "starter": bool(row.get("STARTER_CONFIRMED", False)),
                    "min": _roundish(row.get("PROJ_MIN")),
                    "usg": _roundish(row.get("PROJ_USG")),
                    "pts": _roundish(row.get("PROJ_PTS")),
                    "reb": _roundish(row.get("PROJ_REB")),
                    "ast": _roundish(row.get("PROJ_AST")),
                    "pra": _roundish(row.get("PROJ_PRA")),
                    "pace": _roundish(row.get("pace_factor")),
                    "def": _roundish(row.get("defense_factor")),
                    "ctx": _roundish(row.get("context_quality")),
                })
        canonical = {
            "schema": "PRA-V3.5-GAME-STATE",
            "day": _day(day),
            "game": gid,
            "schedule": game_obj,
            "lineup_ready": bool(lineup_map.get(gid, False)),
            "players": players,
        }
        raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        out[gid] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return out


def _stamp_game_fingerprints(day, state=None):
    state = state or integrity.current_basketball_state(day)
    fps = _game_fingerprints(day)
    for key in (persist.std_key(day), persist.final_key(day)):
        obj = st.session_state.get(key)
        if not isinstance(obj, dict):
            continue
        rows = obj.get("rows")
        if not isinstance(rows, pd.DataFrame) or rows.empty:
            continue
        represented = set(rows.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
        meta = dict(obj.get("meta") or {})
        meta["basketball_fingerprint"] = str(state.get("fingerprint") or "")
        meta["game_fingerprints"] = {gid: fps.get(gid, "") for gid in represented if gid in fps}
        meta["pra_v35_selective"] = True
        obj = dict(obj)
        obj["meta"] = meta
        st.session_state[key] = obj


def _install_selective_invalidation():
    if getattr(integrity, "_v35_selective_invalidation_installed", False):
        return
    original = integrity.invalidate_stale_session

    def selective(day, state):
        std_key = persist.std_key(day)
        final_key = persist.final_key(day)
        stored = st.session_state.get(std_key) or {}
        rows = stored.get("rows")
        if not isinstance(rows, pd.DataFrame) or rows.empty:
            return False
        meta = dict(stored.get("meta") or {})
        saved_fp = str(meta.get("basketball_fingerprint") or "")
        current_fp = str((state or {}).get("fingerprint") or "")
        if bool((state or {}).get("safe")) and saved_fp and saved_fp == current_fp:
            return False

        saved_games = dict(meta.get("game_fingerprints") or {})
        if not bool((state or {}).get("safe")) or not saved_games:
            return original(day, state)
        current_games = _game_fingerprints(day)
        if not current_games:
            return original(day, state)

        union = set(saved_games) | set(current_games)
        changed = {gid for gid in union if str(saved_games.get(gid) or "") != str(current_games.get(gid) or "")}
        represented = set(rows.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
        unchanged_represented = represented - changed
        if not changed or not unchanged_represented:
            return original(day, state)

        kept = rows.loc[~rows["game_id"].astype(str).isin(changed)].copy().reset_index(drop=True)
        obj = dict(stored)
        obj["rows"] = kept
        new_meta = dict(meta)
        new_meta["basketball_fingerprint"] = current_fp
        new_meta["game_fingerprints"] = {
            gid: current_games.get(gid, "") for gid in unchanged_represented if gid in current_games
        }
        new_meta["pra_v35_partial_invalidation"] = sorted(changed)
        obj["meta"] = new_meta
        st.session_state[std_key] = obj

        fin = st.session_state.get(final_key)
        if isinstance(fin, dict):
            frows = fin.get("rows")
            if isinstance(frows, pd.DataFrame) and not frows.empty and "game_id" in frows.columns:
                fobj = dict(fin)
                fobj["rows"] = frows.loc[~frows["game_id"].astype(str).isin(changed)].copy().reset_index(drop=True)
                fmeta = dict(fobj.get("meta") or {})
                fmeta["basketball_fingerprint"] = current_fp
                represented_final = set(fobj["rows"].get("game_id", pd.Series(dtype=object)).astype(str).tolist())
                fmeta["game_fingerprints"] = {
                    gid: current_games.get(gid, "") for gid in represented_final if gid in current_games
                }
                fobj["meta"] = fmeta
                st.session_state[final_key] = fobj
            else:
                st.session_state.pop(final_key, None)

        existing_dirty = set(st.session_state.get(f"wnba_pra_v35_dirty_games::{_day(day)}") or [])
        st.session_state[f"wnba_pra_v35_dirty_games::{_day(day)}"] = sorted(existing_dirty | changed)
        st.session_state[f"wnba_pra_v33_invalidated::{_day(day)}"] = (
            "lineup/injury/minutes state changed for selected game(s); unaffected simulations retained"
        )
        # False intentionally prevents V3.3 from immediately deleting the retained
        # unaffected rows. The V3.5 panel exposes a targeted rebuild for changed games.
        return False

    integrity.invalidate_stale_session = selective
    integrity._v35_selective_invalidation_installed = True


def _install_10m_final_card_gate():
    """A confirmed lineup is necessary but not sufficient: Step 9 needs a 10M pass."""
    integrity.install_runtime_guards()
    if getattr(final32, "_v35_10m_gate_installed", False):
        return
    original = final32._monitor_reasons

    def monitor_reasons_v35(row):
        reasons = list(original(row))
        qualified = bool(row.get("model_qualified"))
        lineup_ready = bool(row.get("lineup_ready"))
        pass_source = str(row.get("pass_source") or "5M").upper()
        if qualified and lineup_ready and pass_source != "10M":
            reasons.append("10M finalist confirmation is pending")
        return list(dict.fromkeys(reasons))

    final32._monitor_reasons = monitor_reasons_v35
    final32._v35_10m_gate_installed = True


def _filtered_market_call(day, *, game_ids=None, finalist_keys=None, final=False, standard_rows=None, progress=None):
    """Run the proven engine while temporarily narrowing exact PRA market units."""
    monte._install()
    module = monte.base.step6
    original_pairs = module._paired_pra_markets
    game_ids = {str(x) for x in (game_ids or [])}
    finalist_keys = {
        (str(g), str(p), round(float(line), 6)) for g, p, line in (finalist_keys or [])
    }

    def filtered(day_arg):
        pairs, snap = original_pairs(day_arg)
        if not isinstance(pairs, pd.DataFrame) or pairs.empty:
            return pairs, snap
        f = pairs.copy()
        if game_ids:
            f = f.loc[f["game_id"].astype(str).isin(game_ids)]
        if finalist_keys and not f.empty:
            mask = [
                (str(r.get("game_id") or ""), str(r.get("player_key") or ""), round(float(r.get("line")), 6)) in finalist_keys
                for _, r in f.iterrows()
            ]
            f = f.loc[mask]
        return f.reset_index(drop=True), snap

    module._paired_pra_markets = filtered
    try:
        if final:
            return monte.run_final(day, standard_rows, progress=progress)
        return monte.run_standard(day, progress=progress)
    finally:
        module._paired_pra_markets = original_pairs


def _merge_targeted_standard(day, target_games, fresh_rows, fresh_meta):
    key = persist.std_key(day)
    existing = st.session_state.get(key) or {}
    old_rows = existing.get("rows")
    if not isinstance(old_rows, pd.DataFrame):
        old_rows = pd.DataFrame()
    if not old_rows.empty and "game_id" in old_rows.columns:
        old_rows = old_rows.loc[~old_rows["game_id"].astype(str).isin(set(target_games))].copy()
    merged = pd.concat([old_rows, fresh_rows], ignore_index=True) if isinstance(fresh_rows, pd.DataFrame) else old_rows
    meta = dict(existing.get("meta") or {})
    meta.update(dict(fresh_meta or {}))
    st.session_state[key] = {"rows": merged, "meta": meta, "ran_at": pd.Timestamp.now()}

    fkey = persist.final_key(day)
    fin = st.session_state.get(fkey)
    if isinstance(fin, dict):
        frows = fin.get("rows")
        if isinstance(frows, pd.DataFrame) and not frows.empty and "game_id" in frows.columns:
            fobj = dict(fin)
            fobj["rows"] = frows.loc[~frows["game_id"].astype(str).isin(set(target_games))].copy().reset_index(drop=True)
            st.session_state[fkey] = fobj
        else:
            st.session_state.pop(fkey, None)


def _render_finalization_controls(day):
    state = integrity.current_basketball_state(day)
    lineup = _lineup_snapshot(day)
    active_games = int(len(lineup))
    ready_games = int(lineup.get("ready", pd.Series(dtype=bool)).fillna(False).sum()) if not lineup.empty else 0

    std = st.session_state.get(persist.std_key(day)) or {}
    std_rows = std.get("rows")
    if not isinstance(std_rows, pd.DataFrame):
        std_rows = pd.DataFrame()
    fin = st.session_state.get(persist.final_key(day)) or {}
    fin_rows = fin.get("rows")
    if not isinstance(fin_rows, pd.DataFrame):
        fin_rows = pd.DataFrame()

    dirty_key = f"wnba_pra_v35_dirty_games::{_day(day)}"
    dirty = {str(x) for x in (st.session_state.get(dirty_key) or [])}
    represented = set(std_rows.get("game_id", pd.Series(dtype=object)).astype(str).tolist()) if not std_rows.empty else set()
    active_ids = set(lineup.get("game_id", pd.Series(dtype=object)).astype(str).tolist()) if not lineup.empty else set()
    # If a partial retained snapshot lacks an active game, expose it as dirty even
    # if the state change happened before V3.5 installed.
    if std_rows is not None and not std_rows.empty:
        dirty |= (active_ids - represented)
        if dirty:
            st.session_state[dirty_key] = sorted(dirty)

    st.markdown("### 🧭 PRA Lineup-Aware Finalization")
    st.caption(
        "Recheck live starters/injuries → selectively rebuild changed 5M game(s) → run 10M finalists. "
        "A Step-9 pick remains MONITOR until its explicit lineup is confirmed and its 10M finalist pass completes."
    )
    cols = st.columns(4)
    cols[0].metric("Confirmed lineups", f"{ready_games}/{active_games}" if active_games else "0/0")
    cols[1].metric("Availability", "VERIFIED" if state.get("safe") else "CHECK")
    cols[2].metric("5M market rows", int(len(std_rows)))
    cols[3].metric("10M market rows", int(len(fin_rows)))

    if not lineup.empty:
        d = lineup.copy()
        d["Matchup"] = d["away"] + " @ " + d["home"]
        d["Starters"] = d["away_starters"].astype(str) + "/5 • " + d["home_starters"].astype(str) + "/5"
        d["State"] = d["ready"].map(lambda x: "✅ CONFIRMED" if bool(x) else "⏳ PENDING")
        st.dataframe(d[["Matchup", "Starters", "State"]], use_container_width=True, hide_index=True)

    if st.button("🔄 RECHECK PRA STARTERS + INJURIES", key=f"pra_v35_recheck::{_day(day)}", use_container_width=True):
        try:
            availability.clear_availability_cache()
        except Exception:
            pass
        try:
            rotowire.rotowire_today_snapshot.clear()
        except Exception:
            pass
        # Lineup/injury state feeds Step 5, Step 7 and Step 8 through several
        # cache_data layers. Clear data caches, not session/widget state.
        try:
            st.cache_data.clear()
        except Exception:
            pass
        st.session_state[f"wnba_pra_v35_rechecked::{_day(day)}"] = datetime.now(ET).isoformat()
        st.rerun()

    if dirty:
        st.warning(
            "🔁 Basketball state changed for " + str(len(dirty)) + " game(s). Unaffected simulations were retained; "
            "rebuild only the changed game(s) before using the Final Card."
        )
        if st.button(
            f"🚀 REBUILD CHANGED GAME 5M ({len(dirty)} game{'s' if len(dirty) != 1 else ''})",
            key=f"pra_v35_rebuild::{_day(day)}",
            use_container_width=True,
        ):
            bar = st.progress(0.0, text="Rebuilding changed PRA game(s) at 5M…")
            try:
                rows, meta = _filtered_market_call(day, game_ids=dirty, final=False, progress=bar)
                _merge_targeted_standard(day, dirty, rows, meta)
                st.session_state.pop(dirty_key, None)
                new_state = integrity.current_basketball_state(day)
                integrity.attach_fingerprint(day, new_state)
                _stamp_game_fingerprints(day, new_state)
            finally:
                bar.empty()
            st.rerun()
        return

    if std_rows.empty:
        st.info("Run the standard 5,000,000 simulation in Step 8 first. Finalization controls will take over after that pass exists.")
        return

    pending = set(lineup.loc[~lineup["ready"].fillna(False), "game_id"].astype(str).tolist()) if not lineup.empty else set()
    if pending:
        st.info(
            f"⏳ {len(pending)} active game(s) still have explicit starting fives pending. Current qualified rows stay MONITOR. "
            "Use RECHECK STARTERS + INJURIES when lineups publish; do not rerun 5M just because time passed."
        )
        return

    # All active games have explicit 5+5 starters. Send only true finalists or
    # close calls through the proven 10M engine.
    s = std_rows.copy()
    qualified = s.get("model_qualified", pd.Series(False, index=s.index)).fillna(False).astype(bool)
    p = pd.to_numeric(s.get("model_over"), errors="coerce")
    e = pd.to_numeric(s.get("edge"), errors="coerce")
    line_ready = s.get("lineup_ready", pd.Series(False, index=s.index)).fillna(False).astype(bool)
    close = s.loc[line_ready & (qualified | ((p >= 0.53) & (e >= 0.015)))].copy()
    if close.empty:
        st.success("✅ Lineups are confirmed, but no 5M PRA row qualifies as a finalist/close call. No 10M run is necessary.")
        return

    wanted = set(
        (str(r.get("game_id") or ""), str(r.get("player_key") or ""), round(float(r.get("line")), 6))
        for _, r in close.drop_duplicates(subset=["game_id", "player_key", "line"]).iterrows()
    )
    have = set()
    if not fin_rows.empty:
        have = set(
            (str(r.get("game_id") or ""), str(r.get("player_key") or ""), round(float(r.get("line")), 6))
            for _, r in fin_rows.drop_duplicates(subset=["game_id", "player_key", "line"]).iterrows()
        )
    missing = wanted - have
    if not missing:
        st.success(f"🏁 10M FINALIST PASS CURRENT • {len(wanted)} unique finalist/close-call distribution(s) verified.")
        return

    st.success(
        f"✅ Explicit lineups confirmed for all {active_games} active game(s). "
        f"{len(missing)} finalist/close-call distribution(s) are ready for the 10M confirmation pass."
    )
    if st.button(
        f"🏁 RUN TARGETED 10,000,000 FINALIST SIMS ({len(missing)})",
        key=f"pra_v35_10m::{_day(day)}",
        use_container_width=True,
    ):
        subset = close.loc[
            [
                (str(r.get("game_id") or ""), str(r.get("player_key") or ""), round(float(r.get("line")), 6)) in missing
                for _, r in close.iterrows()
            ]
        ].copy()
        bar = st.progress(0.0, text="Running targeted 10M finalist simulation…")
        try:
            frows, fmeta = _filtered_market_call(
                day,
                finalist_keys=missing,
                final=True,
                standard_rows=subset,
                progress=bar,
            )
            old = st.session_state.get(persist.final_key(day)) or {}
            old_rows = old.get("rows")
            if not isinstance(old_rows, pd.DataFrame):
                old_rows = pd.DataFrame()
            if not old_rows.empty:
                old_keys = [
                    (str(r.get("game_id") or ""), str(r.get("player_key") or ""), round(float(r.get("line")), 6))
                    for _, r in old_rows.iterrows()
                ]
                old_rows = old_rows.loc[[k not in missing for k in old_keys]].copy()
            merged = pd.concat([old_rows, frows], ignore_index=True) if isinstance(frows, pd.DataFrame) else old_rows
            meta = dict(old.get("meta") or {})
            meta.update(dict(fmeta or {}))
            st.session_state[persist.final_key(day)] = {"rows": merged, "meta": meta, "ran_at": pd.Timestamp.now()}
            new_state = integrity.current_basketball_state(day)
            integrity.attach_fingerprint(day, new_state)
            _stamp_game_fingerprints(day, new_state)
        finally:
            bar.empty()
        st.rerun()


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    rotowire.install()
    integrity.install_runtime_guards()
    _install_selective_invalidation()
    _install_10m_final_card_gate()

    st.caption(
        "🏁 PRA V3.5 • LINEUP-AWARE FINALIZATION ACTIVE • explicit 5+5 starters → targeted changed-game 5M → targeted 10M finalists • "
        "V3.4.1 ET slate + injury integrity retained"
    )

    result = v34.render_wnba_pra_hub(section_header, status_info, team_logo, h)
    day = st.session_state.get("wnba_pra_v2_date")
    if day:
        try:
            state = integrity.current_basketball_state(day)
            _stamp_game_fingerprints(day, state)
        except Exception:
            pass
        _render_finalization_controls(day)
        st.caption(
            "⚡ V3.5 finalization guard • no inferred starters • unaffected game simulations retained when possible • "
            "5M/10M counts unchanged • sportsbook prices still grade completed simulations only."
        )
    return result


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
