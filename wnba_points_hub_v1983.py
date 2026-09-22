"""WNBA Points V1.9.8.3 — frozen live model + out-of-sample calibration lab.

This wrapper does NOT change the V1.9.8.2 Points projection, SportsGameOdds grading,
Monte Carlo distributions, uncertainty floor, candidate hierarchy, H2H, PRA, or MLB.
It freezes the validated live presentation/model handoff and starts a separate
observational calibration ledger.

The ledger captures the latest UPCOMING pregame snapshot for each player/line,
resolves final points from verified ESPN WNBA game summaries when games become
FINAL, and reports Brier score / log loss / ECE / projection MAE. No historical
calibrator is allowed to touch live probabilities until minimum sample and slate
requirements are met and a chronological holdout test improves calibration.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v1982 as frozen

MODEL_VERSION = "WNBA POINTS V1.9.8.3 • FROZEN LIVE MODEL + CALIBRATION LAB"
PRA_FROZEN_BRANCH = frozen.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = frozen.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = frozen.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = "wnba-points-v1982-frozen-20260818"
POINTS_FROZEN_COMMIT = "a16c37962f4aecaa1941786718544b0432623734"

MIN_RESOLVED = 200
MIN_SLATES = 12
HOLDOUT_FRACTION = 0.20
LEDGER_SCHEMA = 1


def _day(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if not np.isfinite(x) else x
    except Exception:
        return default


def _norm(value) -> str:
    mod = getattr(frozen.points, "sgo1", None)
    fn = getattr(mod, "_norm", None) if mod is not None else None
    if callable(fn):
        try:
            return str(fn(value) or "")
        except Exception:
            pass
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _ledger_path() -> Path:
    root = Path(getattr(frozen.points, "CACHE_DIR", Path("/tmp")))
    path = root / "wnba_points_precision"
    path.mkdir(parents=True, exist_ok=True)
    return path / "calibration_ledger_v1.json"


def _empty_ledger() -> dict:
    return {"schema": LEDGER_SCHEMA, "snapshots": {}, "results": {}}


def _load_ledger() -> dict:
    path = _ledger_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("schema", LEDGER_SCHEMA)
            payload.setdefault("snapshots", {})
            payload.setdefault("results", {})
            return payload
    except Exception:
        pass
    return _empty_ledger()


def _save_ledger(payload: dict) -> None:
    path = _ledger_path()
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _schedule_for(day: str):
    try:
        _, _, _, pmeta, _ = frozen.points._prepare(day)
        schedule = (pmeta or {}).get("schedule") if isinstance(pmeta, dict) else None
        return schedule if isinstance(schedule, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _game_status_map(schedule: pd.DataFrame) -> dict:
    out = {}
    if schedule is None or schedule.empty:
        return out
    for _, g in schedule.iterrows():
        gid = str(g.get("game_id") or "")
        if not gid:
            continue
        text = str(g.get("status") or g.get("status_text") or "").upper()
        out[gid] = text
    return out


def _snapshot_key(day: str, row) -> str:
    return "|".join([
        day,
        str(row.get("game_id") or ""),
        str(row.get("player_key") or _norm(row.get("player") or row.get("PLAYER_NAME"))),
        f"{_num(row.get('line'), np.nan):.3f}",
    ])


def _capture_pregame(day: str, ledger: dict) -> int:
    """Store only latest UPCOMING snapshot; LIVE/FINAL states are never captured."""
    try:
        rows = frozen._display_df(day)
    except Exception:
        rows = pd.DataFrame()
    if rows is None or rows.empty:
        return 0
    status_map = _game_status_map(_schedule_for(day))
    now = datetime.now(timezone.utc).isoformat()
    captured = 0
    for _, row in rows.iterrows():
        gid = str(row.get("game_id") or "")
        status = status_map.get(gid, "")
        if "FINAL" in status or "LIVE" in status or "IN PROGRESS" in status:
            continue
        # Require an explicit pregame/upcoming state when provider supplies one.
        if status and not any(token in status for token in ("UPCOMING", "SCHEDULED", "PRE", "STATUS_SCHEDULED")):
            continue
        p = _num(row.get("_floor"), np.nan)
        raw = _num(row.get("_raw"), np.nan)
        line = _num(row.get("line"), np.nan)
        if pd.isna(p) or pd.isna(line):
            continue
        key = _snapshot_key(day, row)
        ledger["snapshots"][key] = {
            "day": day,
            "captured_at_utc": now,
            "model_version": MODEL_VERSION,
            "frozen_commit": POINTS_FROZEN_COMMIT,
            "game_id": gid,
            "player_key": str(row.get("player_key") or _norm(row.get("player") or row.get("PLAYER_NAME"))),
            "player": str(row.get("player") or row.get("PLAYER_NAME") or ""),
            "team": str(row.get("team_name") or ""),
            "opponent": str(row.get("opponent") or ""),
            "line": float(line),
            "book": str(row.get("book") or ""),
            "projection": _num(row.get("projection"), np.nan),
            "sim_mean": _num(row.get("sim_mean"), np.nan),
            "raw_p_over": raw,
            "calibrated_floor": p,
            "no_vig_over": _num(row.get("no_vig_over"), np.nan),
            "calibrated_edge": _num(row.get("_cedge"), np.nan),
            "lineup_ready": bool(row.get("lineup_ready")),
            "freshness": str(row.get("freshness") or ""),
            "pass_source": str(row.get("pass_source") or ""),
        }
        captured += 1
    return captured


def _box_for_game(game_id: str, day: str) -> pd.DataFrame:
    players_mod = getattr(frozen.points, "players", None)
    fn = getattr(players_mod, "_espn_game_summary", None) if players_mod is not None else None
    if not callable(fn):
        # wnba_points_v19 imports the player module through its prior chain.
        prior = getattr(frozen.points, "prior", None)
        players_mod = getattr(prior, "players", None) if prior is not None else None
        fn = getattr(players_mod, "_espn_game_summary", None) if players_mod is not None else None
    if not callable(fn):
        return pd.DataFrame()
    try:
        box = fn(str(game_id), day)
        return box if isinstance(box, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _actual_points_map(box: pd.DataFrame) -> dict:
    out = {}
    if box is None or box.empty:
        return out
    for _, row in box.iterrows():
        name = str(row.get("PLAYER_NAME") or row.get("player") or row.get("athlete_name") or "")
        pts = _num(row.get("PTS"), np.nan)
        key = _norm(name)
        if key and pd.notna(pts):
            out[key] = float(pts)
    return out


def _resolve_finals(day: str, ledger: dict) -> int:
    schedule = _schedule_for(day)
    status_map = _game_status_map(schedule)
    final_ids = {gid for gid, status in status_map.items() if "FINAL" in status}
    if not final_ids:
        return 0
    resolved = 0
    box_cache = {}
    for key, snap in list(ledger.get("snapshots", {}).items()):
        if key in ledger.get("results", {}):
            continue
        gid = str(snap.get("game_id") or "")
        if gid not in final_ids:
            continue
        if gid not in box_cache:
            box_cache[gid] = _actual_points_map(_box_for_game(gid, day))
        actual = box_cache[gid].get(str(snap.get("player_key") or ""))
        if actual is None:
            # Safe name-normalized fallback.
            actual = box_cache[gid].get(_norm(snap.get("player")))
        if actual is None:
            continue
        line = _num(snap.get("line"), np.nan)
        if pd.isna(line):
            continue
        outcome = 1.0 if actual > line else (0.0 if actual < line else np.nan)
        ledger["results"][key] = {
            **snap,
            "actual_pts": float(actual),
            "over_result": outcome,
            "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        resolved += 1
    return resolved


def _resolved_frame(ledger: dict) -> pd.DataFrame:
    rows = list((ledger or {}).get("results", {}).values())
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ("calibrated_floor", "raw_p_over", "projection", "line", "actual_pts", "over_result"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _metrics(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"n": 0, "slates": 0}
    use = df.dropna(subset=["calibrated_floor", "over_result"]).copy()
    if use.empty:
        return {"n": 0, "slates": int(df.get("day", pd.Series(dtype=str)).nunique())}
    p = use["calibrated_floor"].clip(1e-6, 1 - 1e-6).to_numpy(float)
    y = use["over_result"].to_numpy(float)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    bins = pd.cut(p, bins=np.linspace(0, 1, 11), include_lowest=True)
    tmp = pd.DataFrame({"p": p, "y": y, "bin": bins})
    ece = 0.0
    for _, group in tmp.groupby("bin", observed=False):
        if len(group):
            ece += (len(group) / len(tmp)) * abs(float(group["p"].mean()) - float(group["y"].mean()))
    proj = pd.to_numeric(use.get("projection"), errors="coerce")
    actual = pd.to_numeric(use.get("actual_pts"), errors="coerce")
    mae = float((proj - actual).abs().dropna().mean()) if proj.notna().any() and actual.notna().any() else np.nan
    return {
        "n": int(len(use)),
        "slates": int(use["day"].nunique()) if "day" in use.columns else 0,
        "brier": brier,
        "logloss": logloss,
        "ece": float(ece),
        "mae": mae,
    }


def _render_calibration_lab(day: str, ledger: dict) -> None:
    df = _resolved_frame(ledger)
    m = _metrics(df)
    ready = m.get("n", 0) >= MIN_RESOLVED and m.get("slates", 0) >= MIN_SLATES
    with st.expander("🧪 Precision Calibration Lab — out-of-sample tracker", expanded=False):
        st.caption(
            "Frozen V1.9.8.2 live probabilities are being observed against actual final results. "
            "This lab cannot alter tonight's projection or Monte Carlo."
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Resolved outcomes", f"{m.get('n',0)}/{MIN_RESOLVED}")
        c2.metric("Resolved slates", f"{m.get('slates',0)}/{MIN_SLATES}")
        c3.metric("Brier score", "—" if not m.get("n") else f"{m.get('brier', np.nan):.4f}")
        c4.metric("Calibration error", "—" if not m.get("n") else f"{m.get('ece', np.nan)*100:.1f} pp")
        if not ready:
            st.info(
                "🔒 HISTORICAL CALIBRATOR LOCKED • We are collecting real pregame predictions + final outcomes first. "
                "No probability curve will be fitted or promoted from a tiny sample."
            )
        else:
            st.success(
                "✅ SAMPLE GATE REACHED • enough resolved observations exist to build a chronological train/holdout calibrator. "
                "Promotion still requires holdout Brier/log-loss improvement before live use."
            )
        if m.get("n"):
            st.caption(
                f"Projection MAE: {m.get('mae', np.nan):.2f} PTS • Log loss: {m.get('logloss', np.nan):.4f} • "
                "pushes are excluded from binary probability scoring."
            )
        export = json.dumps(ledger, indent=2, ensure_ascii=False)
        st.download_button(
            "⬇️ Export calibration ledger",
            export,
            file_name=f"wnba_points_calibration_{day}.json",
            mime="application/json",
            key=f"wnba_points_calibration_export_{day}",
        )
        st.caption(
            "Precision rule: archive UPCOMING snapshots only; resolve from final box scores; keep H2H descriptive; "
            "never tune against the current night's result; validate chronologically before promotion."
        )


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = frozen._current_day()
    ledger = _load_ledger()
    before = json.dumps(ledger, sort_keys=True, default=str)
    _capture_pregame(day, ledger)
    _resolve_finals(day, ledger)
    after = json.dumps(ledger, sort_keys=True, default=str)
    if after != before:
        _save_ledger(ledger)

    result = frozen.render_wnba_points_hub(section_header, status_info, team_logo, h)
    st.divider()
    _render_calibration_lab(day, ledger)
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
