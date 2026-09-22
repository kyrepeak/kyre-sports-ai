"""MLB Daily Game Picks V2.1.3 — persistent completed-card snapshots.

Persistence/orchestration layer only. Production model math, simulation depths,
market verification, normalization, Step 5/6 scoring, live-risk logic, and all
V2.1.2.5 sportsbook retry behavior remain unchanged.

When a real native 7/7 card completes, this layer saves a compact scored-candidate
snapshot to browser localStorage plus a compressed process-disk fallback. A later
Streamlit restart/redeploy can restore the Final Card without rerunning models.
Selective refresh still works: refreshed native markets replace only their saved
market, while untouched markets remain snapshot-backed.
"""
from __future__ import annotations

import base64
from datetime import datetime
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import zlib

import streamlit as st

try:
    from streamlit_local_storage import LocalStorage
except Exception:
    LocalStorage = None

import mlb_daily_game_picks_v2125 as previous
import mlb_daily_game_picks_v2124 as resume_ui
import mlb_daily_game_picks_v212 as live
import mlb_daily_game_picks_v211 as decision
import mlb_daily_game_picks_v209 as ui
import mlb_daily_game_picks_v206 as master

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.3 • PERSISTENT COMPLETED-CARD SNAPSHOT"
SNAPSHOT_SCHEMA = 1
MAX_BROWSER_BYTES = 4_500_000
CACHE_DIR = Path(".kyre_runtime_cache")

_BASE_COLLECT_CANDIDATES = master._collect_candidates
_BASE_RESUME_RENDERER = resume_ui._render_full_builder_v2124
_BASE_COMPACT_FINAL = ui._render_compact_final

STAGE_TO_MARKET = {
    "runline": "Run Line",
    "total": "Total",
    "moneyline": "Moneyline",
    "pitcherk": "Pitcher Strikeouts",
    "hrrbi": "H+R+RBI",
    "homerun": "Home Run",
    "onehit": "1+ Hit",
}

_LOCAL = LocalStorage() if LocalStorage is not None else None


def _day(games_df):
    return controller._day(games_df)


def _snapshot_session_key(day):
    return f"dgp_persistent_snapshot_v213::{day}"


def _snapshot_source_key(day):
    return f"dgp_persistent_snapshot_source_v213::{day}"


def _snapshot_saved_key(day):
    return f"dgp_persistent_snapshot_saved_v213::{day}"


def _browser_key(day):
    return f"kyre_sports_ai_mlb_daily_card_v213::{day}"


def _browser_component_key(day):
    return f"dgp_localstorage_get_v213::{day}"


def _safe_int(v):
    try:
        return int(float(v))
    except Exception:
        return None


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _parse_dt(v):
    if isinstance(v, datetime):
        return v
    text = str(v or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _slate_signature(games_df):
    rows = []
    if games_df is not None and not getattr(games_df, "empty", True):
        for _, row in games_df.iterrows():
            rows.append({
                "game_pk": str(_safe_int(row.get("game_pk")) or row.get("game_pk") or ""),
                "away": str(row.get("away_team") or "").strip(),
                "home": str(row.get("home_team") or "").strip(),
            })
    rows.sort(key=lambda x: (x["game_pk"], x["away"], x["home"]))
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _jsonable(v, depth=0):
    if depth > 7:
        return None
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            return _jsonable(v.item(), depth + 1)
        except Exception:
            pass
    if isinstance(v, dict):
        out = {}
        for k, value in v.items():
            item = _jsonable(value, depth + 1)
            if item is not None:
                out[str(k)] = item
        return out
    if isinstance(v, (list, tuple, set)):
        seq = list(v)
        if len(seq) > 250:
            return None
        return [_jsonable(x, depth + 1) for x in seq]
    try:
        return str(v)
    except Exception:
        return None


def _encode_snapshot(snapshot):
    raw = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return "z1:" + base64.urlsafe_b64encode(compressed).decode("ascii")


def _decode_snapshot(raw):
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.startswith("z1:"):
            payload = base64.urlsafe_b64decode(text[3:].encode("ascii"))
            return json.loads(zlib.decompress(payload).decode("utf-8"))
        return json.loads(text)
    except Exception:
        return None


def _disk_path(day):
    safe_day = "".join(ch for ch in str(day or "") if ch.isdigit() or ch == "-")
    return CACHE_DIR / f"mlb_daily_card_{safe_day}.json.gz"


def _write_disk(snapshot):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _disk_path(snapshot.get("day"))
        tmp = path.with_suffix(path.suffix + ".tmp")
        raw = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp.write_bytes(gzip.compress(raw, compresslevel=9))
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _read_disk(day):
    try:
        path = _disk_path(day)
        if not path.exists():
            return None
        return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except Exception:
        return None


def _valid_snapshot(snapshot, games_df):
    if not isinstance(snapshot, dict):
        return False
    day = _day(games_df)
    if str(snapshot.get("day") or "") != str(day):
        return False
    if int(snapshot.get("schema", 0) or 0) != SNAPSHOT_SCHEMA:
        return False
    if int(snapshot.get("source_complete", 0) or 0) != len(controller.STAGES):
        return False
    if snapshot.get("slate_signature") != _slate_signature(games_df):
        return False
    candidates = snapshot.get("candidates")
    return isinstance(candidates, list) and len(candidates) > 0


def _is_stub(pack):
    return bool(isinstance(pack, dict) and pack.get("snapshot_stub"))


def _real_stage_complete(games_df, stage):
    pack = controller._pack(games_df, stage)
    return bool(controller._complete(pack) and not _is_stub(pack))


def _all_real_complete(games_df):
    return all(_real_stage_complete(games_df, stage) for stage, _, _ in controller.STAGES)


def _current_snapshot(games_df):
    return st.session_state.get(_snapshot_session_key(_day(games_df)))


def _hydrate_timestamp_and_baseline(games_df, snapshot):
    day = _day(games_df)
    ts = _parse_dt(snapshot.get("build_ts"))
    run_id = int(snapshot.get("run_id", 0) or 0)
    if ts is not None:
        st.session_state[ui._timestamp_key(day)] = {"ts": ts, "run_id": run_id}

    baseline = snapshot.get("starter_baseline")
    if isinstance(baseline, dict):
        try:
            st.session_state[live._baseline_key(day)] = baseline
        except Exception:
            pass

    state_key = controller._state_key(day)
    state = st.session_state.get(state_key)
    if not isinstance(state, dict):
        state = controller._initial_state(day)
    if not state.get("active"):
        state["day"] = day
        state["runs"] = run_id
        st.session_state[state_key] = state


def _install_snapshot(games_df, snapshot, source):
    if not _valid_snapshot(snapshot, games_df):
        return False
    day = _day(games_df)
    st.session_state[_snapshot_session_key(day)] = snapshot
    st.session_state[_snapshot_source_key(day)] = str(source or "saved snapshot")
    _hydrate_timestamp_and_baseline(games_df, snapshot)

    state = st.session_state.get(controller._state_key(day)) or {}
    if not bool(state.get("active")):
        for stage, label, _ in controller.STAGES:
            key = controller._pack_key(games_df, stage)
            if not key:
                continue
            current = st.session_state.get(key)
            if current is None or _is_stub(current):
                st.session_state[key] = {
                    "complete": True,
                    "snapshot_stub": True,
                    "stage": stage,
                    "label": label,
                    "source_build_ts": snapshot.get("build_ts"),
                    "source_candidate_count": int(snapshot.get("candidate_count", 0) or 0),
                    "rows": [],
                    "errors": [],
                }
    return True


def _try_restore_snapshot(games_df):
    day = _day(games_df)
    if not day:
        return None

    current = _current_snapshot(games_df)
    if _valid_snapshot(current, games_df):
        return current

    disk = _read_disk(day)
    if _valid_snapshot(disk, games_df):
        _install_snapshot(games_df, disk, "server disk fallback")
        return disk

    if _LOCAL is not None:
        raw = None
        try:
            raw = _LOCAL.getItem(_browser_key(day), key=_browser_component_key(day))
        except Exception:
            raw = st.session_state.get(_browser_component_key(day))
        if raw in (None, ""):
            raw = st.session_state.get(_browser_component_key(day))
        snap = _decode_snapshot(raw)
        if _valid_snapshot(snap, games_df):
            _install_snapshot(games_df, snap, "browser persistent storage")
            return snap
    return None


def _parse_price(price_text):
    text = str(price_text or "").strip().replace("+", "")
    try:
        return float(text)
    except Exception:
        return None


def _snapshot_candidates(games_df):
    candidates = _BASE_COLLECT_CANDIDATES(games_df) or []
    out = []
    for c in candidates:
        item = _jsonable(dict(c))
        if not isinstance(item, dict):
            continue
        if not item.get("posted_book") or item.get("posted_price") is None:
            try:
                book, price_text, note = decision._cached_sportsbook_context(c, games_df)
            except Exception:
                book, price_text, note = None, None, None
            price = _parse_price(price_text)
            if book and price is not None:
                item["posted_book"] = str(book)
                item["posted_price"] = price
                item["posted_quote_note"] = str(note or "")
        out.append(item)
    return out


def _build_snapshot(games_df):
    if not _all_real_complete(games_df):
        return None
    candidates = _snapshot_candidates(games_df)
    if not candidates:
        return None

    day = _day(games_df)
    state = st.session_state.get(controller._state_key(day)) or {}
    run_id = int(state.get("runs", 0) or 0)
    ts = decision._build_timestamp(games_df) or ui._now_et()
    try:
        baseline = live._starter_baseline(games_df)
    except Exception:
        baseline = {}

    return {
        "schema": SNAPSHOT_SCHEMA,
        "day": day,
        "slate_signature": _slate_signature(games_df),
        "source_complete": len(controller.STAGES),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "build_ts": ts.isoformat() if isinstance(ts, datetime) else str(ts or ""),
        "saved_at": ui._now_et().isoformat(),
        "run_id": run_id,
        "starter_baseline": _jsonable(baseline),
        "source_version": VERSION,
    }


def _persist_if_ready(games_df):
    if not _all_real_complete(games_df):
        return None
    snapshot = _build_snapshot(games_df)
    if not snapshot:
        return None

    day = _day(games_df)
    signature = f"{snapshot.get('build_ts')}::{snapshot.get('candidate_count')}::{snapshot.get('run_id')}"
    saved_key = _snapshot_saved_key(day)
    if st.session_state.get(saved_key) == signature:
        st.session_state[_snapshot_session_key(day)] = snapshot
        return snapshot

    st.session_state[_snapshot_session_key(day)] = snapshot
    st.session_state[_snapshot_source_key(day)] = "current native 7/7 build"
    st.session_state[saved_key] = signature
    _write_disk(snapshot)

    if _LOCAL is not None:
        try:
            encoded = _encode_snapshot(snapshot)
            if len(encoded.encode("utf-8")) <= MAX_BROWSER_BYTES:
                _LOCAL.setItem(_browser_key(day), encoded)
            else:
                st.session_state[f"dgp_persist_warning_v213::{day}"] = (
                    "The completed card was too large for the browser snapshot limit; server-disk fallback was still saved."
                )
        except Exception as exc:
            st.session_state[f"dgp_persist_warning_v213::{day}"] = (
                f"Browser snapshot write was unavailable ({type(exc).__name__}); server-disk fallback was still saved."
            )
    return snapshot


def _dedupe_sort(candidates):
    uniq = {}
    for c in candidates:
        if not isinstance(c, dict):
            continue
        key = (
            c.get("game_pk"), c.get("market"), c.get("name"), c.get("side"),
            str(c.get("line")), round(_finite(c.get("probability"), 0.0) or 0.0, 8),
        )
        uniq[key] = c
    return sorted(
        uniq.values(),
        key=lambda c: (
            _finite(c.get("score"), 0.0) or 0.0,
            _finite(c.get("reliability"), 0.0) or 0.0,
            _finite(c.get("data_quality"), 0.0) or 0.0,
            _finite(c.get("probability"), 0.0) or 0.0,
        ),
        reverse=True,
    )


def _persistent_collect_candidates(games_df):
    native = _BASE_COLLECT_CANDIDATES(games_df) or []
    snapshot = _current_snapshot(games_df)
    if not _valid_snapshot(snapshot, games_df):
        return native

    snap_candidates = [dict(x) for x in (snapshot.get("candidates") or []) if isinstance(x, dict)]
    real_markets = {
        STAGE_TO_MARKET[stage]
        for stage, _, _ in controller.STAGES
        if _real_stage_complete(games_df, stage)
    }
    if not real_markets:
        return _dedupe_sort(snap_candidates)

    merged = [c for c in snap_candidates if str(c.get("market") or "") not in real_markets]
    merged.extend(c for c in native if str(c.get("market") or "") in real_markets)
    return _dedupe_sort(merged)


def _snapshot_backed_stages(games_df):
    out = []
    for stage, label, _ in controller.STAGES:
        if _is_stub(controller._pack(games_df, stage)):
            out.append((stage, label))
    return out


def _render_persistence_notice(games_df):
    day = _day(games_df)
    snapshot = _current_snapshot(games_df)
    if not _valid_snapshot(snapshot, games_df):
        warning = st.session_state.pop(f"dgp_persist_warning_v213::{day}", None)
        if warning:
            st.warning(warning)
        return

    stubs = _snapshot_backed_stages(games_df)
    source = st.session_state.get(_snapshot_source_key(day), "saved snapshot")
    ts = _parse_dt(snapshot.get("build_ts"))
    ts_text = ui._fmt_ts(ts) if ts is not None else str(snapshot.get("build_ts") or "saved build")

    if stubs:
        st.success(
            f"♻️ RESTORED COMPLETED CARD • source build {ts_text} • "
            f"{len(stubs)}/7 connector stage(s) are snapshot-backed • no model rerun required."
        )
        with st.expander("♻️ Restored-card storage", expanded=False):
            st.caption(
                "The Final Card and market leaders are restored from the last real 7/7 scored-candidate snapshot. "
                "Live MLB lineup/starter/weather checks still refresh normally. Snapshot-backed stages are skipped by the one-tap controller."
            )
            st.caption("Snapshot source: " + str(source))
            st.caption("Snapshot-backed: " + " • ".join(label for _, label in stubs))
            if st.button(
                "🔄 SYNC SNAPSHOT-BACKED CONNECTORS",
                use_container_width=True,
                key=f"dgp_sync_snapshot_stubs_v213::{day}",
                help="Rebuilds only stages currently backed by the saved snapshot. Already-real native stages stay cached.",
            ):
                for stage, _label in stubs:
                    key = controller._pack_key(games_df, stage)
                    if key:
                        st.session_state.pop(key, None)
                state_key = controller._state_key(day)
                old = st.session_state.get(state_key) or {}
                fresh = controller._initial_state(day)
                fresh["active"] = True
                fresh["runs"] = int(old.get("runs", 0) or 0) + 1
                st.session_state[state_key] = fresh
                st.rerun()
    else:
        st.caption(
            f"💾 V2.1.3 persistence armed • current real 7/7 card saved for restart/redeploy recovery ({ts_text})."
        )

    warning = st.session_state.pop(f"dgp_persist_warning_v213::{day}", None)
    if warning:
        st.warning(warning)


def _render_compact_final_v213(games_df):
    snapshot = _current_snapshot(games_df)
    if _valid_snapshot(snapshot, games_df):
        return ui._render_master_polished(games_df)
    return _BASE_COMPACT_FINAL(games_df)


def _render_full_builder_v213(games_df):
    day = _day(games_df)
    state = st.session_state.get(controller._state_key(day)) or {}
    if state.get("active") or not _snapshot_backed_stages(games_df):
        return _BASE_RESUME_RENDERER(games_df)

    st.markdown("### 🚀 One-Tap Full MLB Card")
    st.caption(
        "Saved 7/7 production outputs are available. Snapshot-backed stages remain skipped until a selective data refresh or explicit sync is requested."
    )
    st.progress(1.0, text="Full MLB Card • 7/7 source connectors represented")
    st.caption(controller._summary(games_df))
    st.success("♻️ FULL MLB CARD RESTORED • Final Card is ready now • no production rerun required.")


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    _try_restore_snapshot(games_df)
    _persist_if_ready(games_df)

    master._collect_candidates = _persistent_collect_candidates
    ui.master._collect_candidates = _persistent_collect_candidates
    ui._render_compact_final = _render_compact_final_v213

    # V2.1.2.4 assigns controller._render_full_builder from this module-global on
    # every rerun, so replace that global rather than only patching controller.
    resume_ui._render_full_builder_v2124 = _render_full_builder_v213
    controller._render_full_builder = _render_full_builder_v213

    st.caption(
        "💾 V2.1.3 persistent card storage: completed 7/7 scored outputs are saved to browser storage + a server-disk fallback; redeploys can restore the Final Card without rerunning models."
    )
    _render_persistence_notice(games_df)

    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
