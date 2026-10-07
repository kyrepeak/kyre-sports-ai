"""WNBA Data Completeness Repair V1 Step 2 — current-roster production gate.

This helper reconciles verified WNBA Stats production with current ESPN roster
identity without assuming the two providers share one player-ID namespace.
It is intentionally limited to WNBA player-pool filtering and never changes
stat values, projections, markets, probabilities, rankings, or sportsbook data.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import pandas as pd


def _norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def _integer(value):
    try:
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return None if pd.isna(number) else int(number)
    except Exception:
        return None


def gate_primary_production(
    primary: pd.DataFrame,
    roster: pd.DataFrame,
    slate_team_ids: Iterable[int],
) -> pd.DataFrame:
    """Keep current/slate WNBA production without cross-provider ID loss.

    Rules:
    - league/source guarding remains the caller's responsibility;
    - never introduce a team outside ``slate_team_ids``;
    - for a team with a connected current-roster feed, keep production when the
      player matches that roster by exact provider ID OR normalized name;
    - for a slate team whose roster feed is unavailable, preserve its already
      league-guarded production instead of deleting the team;
    - never rewrite PLAYER_ID or any basketball stat value.
    """
    if primary is None or primary.empty:
        return pd.DataFrame(columns=(primary.columns if isinstance(primary, pd.DataFrame) else []))

    team_ids = {int(tid) for tid in slate_team_ids if _integer(tid) is not None}
    out = primary.copy()
    if "TEAM_ID" not in out.columns:
        return out.iloc[0:0].copy()

    numeric_team = pd.to_numeric(out["TEAM_ID"], errors="coerce")
    out = out[numeric_team.isin(team_ids)].copy()
    if out.empty or roster is None or roster.empty:
        return out.reset_index(drop=True)

    roster_teams: set[int] = set()
    allowed_ids: set[tuple[int, int]] = set()
    allowed_names: set[tuple[int, str]] = set()

    for _, row in roster.iterrows():
        tid = _integer(row.get("TEAM_ID"))
        if tid is None or tid not in team_ids:
            continue
        roster_teams.add(tid)

        pid = _integer(row.get("PLAYER_ID"))
        if pid is not None:
            allowed_ids.add((tid, pid))

        name = _norm_name(row.get("PLAYER_NAME"))
        if name:
            allowed_names.add((tid, name))

    keep: list[bool] = []
    for _, row in out.iterrows():
        tid = _integer(row.get("TEAM_ID"))
        if tid is None or tid not in team_ids:
            keep.append(False)
            continue
        if tid not in roster_teams:
            keep.append(True)
            continue

        pid = _integer(row.get("PLAYER_ID"))
        name = _norm_name(row.get("PLAYER_NAME"))
        keep.append(
            (pid is not None and (tid, pid) in allowed_ids)
            or (bool(name) and (tid, name) in allowed_names)
        )

    return out.loc[keep].copy().reset_index(drop=True)


__all__ = ["gate_primary_production"]
