"""WNBA Points V1.9.8.4.20 — Step 8 cross-provider usage identity repair.

Presentation/context-only wrapper over V1.9.8.4.19. The protected Points
projection, sportsbook transport, Monte Carlo, calibration, readiness gates,
sanity quarantine and Top-5 ordering are unchanged.

Root cause repaired here: the selected WNBA player pool frequently carries ESPN
PLAYER_ID values while the preferred WNBA/NBA Stats usage table can carry a
different provider PLAYER_ID namespace. V1.9.8.4.19 tried only the numeric id
first, so a real player could be present in the usage table under the same name
but still render as PLAYER NOT FOUND.

V1.9.8.4.20 uses a fail-closed identity chain for Step 8 only:
1) existing usage already present on the protected Points row;
2) exact TEAM_ID + PLAYER_ID match in the hardened role/usage table;
3) normalized player-name match, with TEAM_ID used as a tie-breaker when the
   provider team ids are compatible;
4) if the preferred table is non-empty but still omits this player, use the
   existing day-aware ESPN WNBA box-score usage fallback for this player.

Every non-row fallback is labeled as audit/display-only and is never written
back into the protected Points projection or simulation.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198419 as prior
import wnba_role_v282 as role

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.20 • STEP 8 CROSS-PROVIDER USAGE IDENTITY REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_KEYS = ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT")


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _id_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _valid_usage(value) -> bool:
    x = _num(value, np.nan)
    return bool(pd.notna(x) and x > 0)


def _norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    # Provider punctuation/spacing should never prevent an identity match.
    return re.sub(r"[^a-z0-9]+", "", text)


def _player_name(data: dict) -> str:
    for key in ("PLAYER_NAME", "Player", "player", "player_name", "NAME", "name"):
        value = data.get(key)
        if value is not None and str(value).strip() not in ("", "nan", "None"):
            return str(value).strip()
    return ""


def _match_usage_row(table: pd.DataFrame, data: dict):
    """Return (row, identity_method) without assuming provider id namespaces."""
    if table is None or table.empty:
        return None, ""

    pid = _id_int(data.get("PLAYER_ID"))
    tid = _id_int(data.get("TEAM_ID"))
    name_key = _norm_name(_player_name(data))

    # 1) Strongest identity: exact team + player id.
    if pid and "PLAYER_ID" in table.columns:
        ids = pd.to_numeric(table["PLAYER_ID"], errors="coerce").fillna(-1).astype(int)
        exact = table.loc[ids.eq(pid)].copy()
        if tid and not exact.empty and "TEAM_ID" in exact.columns:
            tids = pd.to_numeric(exact["TEAM_ID"], errors="coerce").fillna(-1).astype(int)
            same_team = exact.loc[tids.eq(tid)]
            if not same_team.empty:
                return same_team.iloc[0], "TEAM+PLAYER ID"
        if len(exact) == 1:
            return exact.iloc[0], "PLAYER ID"

    # 2) Cross-provider identity: normalized full player name. WNBA Stats and
    # ESPN player IDs are not guaranteed to share a namespace.
    if name_key and "PLAYER_NAME" in table.columns:
        names = table["PLAYER_NAME"].map(_norm_name)
        by_name = table.loc[names.eq(name_key)].copy()
        if not by_name.empty:
            if tid and "TEAM_ID" in by_name.columns:
                tids = pd.to_numeric(by_name["TEAM_ID"], errors="coerce").fillna(-1).astype(int)
                same_team = by_name.loc[tids.eq(tid)]
                if not same_team.empty:
                    return same_team.iloc[0], "TEAM+NAME • CROSS-PROVIDER ID"
            if len(by_name) == 1:
                return by_name.iloc[0], "NAME • CROSS-PROVIDER ID"

    return None, ""


def _fill_from_row(out: dict, row) -> int:
    if row is None:
        return 0
    filled = 0
    for key in _KEYS:
        if not _valid_usage(out.get(key)) and key in row.index and _valid_usage(row.get(key)):
            out[key] = row.get(key)
            filled += 1
    return filled


def _missing_keys(out: dict) -> list[str]:
    return [key for key in _KEYS if not _valid_usage(out.get(key))]


def _usage_handoff_identity(day: str, data: dict) -> tuple[dict, str]:
    """Hydrate Step-8 usage with provider-safe identity matching.

    This function changes presentation data only. It never writes fallback usage
    into the protected projection frame or Monte Carlo runtime.
    """
    out = dict(data or {})
    if not _missing_keys(out):
        return out, "PROTECTED POINTS PROJECTION ROW"

    try:
        day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
        season = int(pd.to_datetime(day).year)
    except Exception:
        return out, "USAGE AUDIT UNAVAILABLE • INVALID SLATE DATE"

    source_notes = []

    # Preferred hardened role/usage table. A non-empty table is not enough: the
    # player must actually be identity-matched.
    try:
        preferred, preferred_source = role.advanced_usage_table(season)
    except Exception:
        preferred, preferred_source = pd.DataFrame(), ""

    row, method = _match_usage_row(preferred, out)
    filled = _fill_from_row(out, row)
    if filled:
        label = prior._usage_source_label(preferred_source)
        source_notes.append(f"{label} • {method}")

    # Important: role.advanced_usage_table() returns the first healthy league
    # table. If that table omits a player, its global non-empty state used to
    # prevent the existing ESPN fallback from ever being consulted for that one
    # player. Query the same verified fallback per player only when fields remain.
    if _missing_keys(out):
        try:
            espn = role.prior._espn_usage_fallback(season, day_str)
        except Exception:
            espn = pd.DataFrame()
        erow, emethod = _match_usage_row(espn, out)
        efilled = _fill_from_row(out, erow)
        if efilled:
            source_notes.append(
                f"ESPN WNBA BOX-SCORE ESTIMATED USG% • {emethod} • AUDIT FALLBACK ONLY"
            )

    missing = _missing_keys(out)
    if not missing:
        return out, " + ".join(source_notes) if source_notes else "USAGE IDENTITY VERIFIED"

    if source_notes:
        labels = ", ".join(missing).replace("_PCT", "")
        return out, " + ".join(source_notes) + f" • {labels} NOT PUBLISHED"

    name = _player_name(out) or "PLAYER"
    return out, (
        f"NO VERIFIED USAGE ROW FOR {name.upper()} AFTER ID + NORMALIZED-NAME MATCH "
        "AND DAY-AWARE ESPN FALLBACK"
    )


def _install() -> None:
    # Keep all V1.9.8.4.19 repairs active first (explicit FALSE lineup source,
    # Step-8 provenance display), then replace only its usage handoff helper.
    prior._install()
    prior._usage_handoff = _usage_handoff_identity


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🩺 Points V1.9.8.4.20 • Step 8 cross-provider usage identity repair ACTIVE • "
        "ID → normalized name → day-aware ESPN fallback • audit only • model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
