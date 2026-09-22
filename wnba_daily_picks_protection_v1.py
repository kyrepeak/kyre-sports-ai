"""WNBA Daily Picks Step 7 — duplicate/correlation protection.

Consumes only the Step-6 read-only safety audit. It does not rank, choose a best
quote, launch simulations, refresh markets/injuries, or write to any production
model. The goal is to identify which rows represent the same underlying wager
and which candidate families share player/game exposure before Step 8 ranking.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MODEL_VERSION = "WNBA DAILY PICKS PROTECTION V1 • STEP 7 READ ONLY"

PROTECTION_COLUMNS = [
    "Protection state", "Protection flags", "Candidate key", "Quote group size",
    "Player-market key", "Alternate lines", "Player exposure key",
    "Player candidate groups", "Player markets", "Game key", "Game candidate groups",
    "Team exposure key", "Team candidate groups",
]


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A"} else s


def _num(value: Any) -> float:
    try:
        x = float(value)
        return float(x) if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _line_token(value: Any) -> str:
    x = _num(value)
    return f"{x:.3f}" if np.isfinite(x) else "?"


def _game_key(team: Any, opponent: Any) -> str:
    t, o = _text(team), _text(opponent)
    if not t or not o:
        return ""
    return " vs ".join(sorted((t, o), key=lambda x: x.lower()))


def annotate(audit: pd.DataFrame) -> pd.DataFrame:
    """Return copied Step-6 rows with read-only duplicate/correlation annotations."""
    if audit is None or audit.empty:
        cols = list(audit.columns) if isinstance(audit, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + [c for c in PROTECTION_COLUMNS if c not in cols])

    d = audit.copy().reset_index(drop=True)
    for col in ("Slate day", "Market", "Player", "Team", "Opponent", "Side", "Book", "Safety state"):
        if col not in d.columns:
            d[col] = ""
    if "Line" not in d.columns:
        d["Line"] = np.nan

    day = d["Slate day"].map(_text)
    market = d["Market"].map(lambda x: _text(x).upper())
    player = d["Player"].map(_text)
    team = d["Team"].map(_text)
    opponent = d["Opponent"].map(_text)
    side = d["Side"].map(lambda x: _text(x).upper())
    safety = d["Safety state"].map(lambda x: _text(x).upper())
    line = d["Line"].map(_line_token)

    # One candidate key = one exact underlying bet. Multiple books are quote
    # alternatives for the same candidate, not multiple independent picks.
    d["Candidate key"] = day + "|" + market + "|" + player + "|" + side + "|" + line
    d["Player-market key"] = day + "|" + market + "|" + player + "|" + side
    d["Player exposure key"] = day + "|" + player
    d["Game key"] = [f"{dy}|{_game_key(t, o)}" if _game_key(t, o) else "" for dy, t, o in zip(day, team, opponent)]
    d["Team exposure key"] = day + "|" + team

    safe_mask = safety.eq("SAFE")
    safe = d.loc[safe_mask].copy()

    quote_sizes = safe.groupby("Candidate key", dropna=False).size().to_dict() if not safe.empty else {}
    d["Quote group size"] = d["Candidate key"].map(quote_sizes).fillna(0).astype(int)

    if safe.empty:
        d["Alternate lines"] = 0
        d["Player candidate groups"] = 0
        d["Player markets"] = 0
        d["Game candidate groups"] = 0
        d["Team candidate groups"] = 0
    else:
        alt = safe.groupby("Player-market key", dropna=False)["Line"].nunique(dropna=True).to_dict()
        player_groups = safe.groupby("Player exposure key", dropna=False)["Candidate key"].nunique().to_dict()
        player_markets = safe.groupby("Player exposure key", dropna=False)["Market"].nunique().to_dict()
        game_groups = safe[safe["Game key"].astype(str).str.len().gt(0)].groupby("Game key")["Candidate key"].nunique().to_dict()
        team_groups = safe.groupby("Team exposure key", dropna=False)["Candidate key"].nunique().to_dict()
        d["Alternate lines"] = d["Player-market key"].map(alt).fillna(0).astype(int)
        d["Player candidate groups"] = d["Player exposure key"].map(player_groups).fillna(0).astype(int)
        d["Player markets"] = d["Player exposure key"].map(player_markets).fillna(0).astype(int)
        d["Game candidate groups"] = d["Game key"].map(game_groups).fillna(0).astype(int)
        d["Team candidate groups"] = d["Team exposure key"].map(team_groups).fillna(0).astype(int)

    states: list[str] = []
    flags_out: list[str] = []
    for _, row in d.iterrows():
        if _text(row.get("Safety state")).upper() != "SAFE":
            states.append("BLOCKED BY STEP 6")
            flags_out.append("not SAFE")
            continue

        flags: list[str] = []
        if int(row.get("Quote group size", 0) or 0) > 1:
            flags.append("same wager / multiple books")
        if int(row.get("Alternate lines", 0) or 0) > 1:
            flags.append("same player-market / alternate lines")
        if int(row.get("Player markets", 0) or 0) > 1:
            flags.append("same player / cross-market correlation")
        if int(row.get("Game candidate groups", 0) or 0) > 1:
            flags.append("same-game exposure")
        if int(row.get("Team candidate groups", 0) or 0) > 1:
            flags.append("same-team exposure")

        flags_out.append(" • ".join(flags) if flags else "none")
        if int(row.get("Quote group size", 0) or 0) > 1:
            states.append("QUOTE GROUP")
        elif int(row.get("Alternate lines", 0) or 0) > 1 or int(row.get("Player markets", 0) or 0) > 1:
            states.append("CORRELATED")
        elif int(row.get("Game candidate groups", 0) or 0) > 1 or int(row.get("Team candidate groups", 0) or 0) > 1:
            states.append("EXPOSURE TAGGED")
        else:
            states.append("CLEAR")

    d["Protection state"] = states
    d["Protection flags"] = flags_out
    return d


def diagnostics(protected: pd.DataFrame) -> dict[str, Any]:
    if protected is None or protected.empty:
        return {
            "rows": 0, "safe_rows": 0, "candidate_groups": 0, "duplicate_quote_groups": 0,
            "extra_quote_rows": 0, "alternate_line_groups": 0, "player_correlation_groups": 0,
            "game_exposure_groups": 0, "team_exposure_groups": 0, "blocked_rows": 0,
            "ranking_enabled": False,
        }

    d = protected.copy()
    safe = d[d["Safety state"].astype(str).str.upper().eq("SAFE")].copy()
    if safe.empty:
        return {
            "rows": int(len(d)), "safe_rows": 0, "candidate_groups": 0, "duplicate_quote_groups": 0,
            "extra_quote_rows": 0, "alternate_line_groups": 0, "player_correlation_groups": 0,
            "game_exposure_groups": 0, "team_exposure_groups": 0,
            "blocked_rows": int(len(d)), "ranking_enabled": False,
        }

    quote_sizes = safe.groupby("Candidate key").size()
    alt_counts = safe.groupby("Player-market key")["Line"].nunique(dropna=True)
    player_group_counts = safe.groupby("Player exposure key")["Candidate key"].nunique()
    player_market_counts = safe.groupby("Player exposure key")["Market"].nunique()
    valid_games = safe[safe["Game key"].astype(str).str.len().gt(0)]
    game_counts = valid_games.groupby("Game key")["Candidate key"].nunique() if not valid_games.empty else pd.Series(dtype=int)
    team_counts = safe.groupby("Team exposure key")["Candidate key"].nunique()

    return {
        "rows": int(len(d)),
        "safe_rows": int(len(safe)),
        "candidate_groups": int(safe["Candidate key"].nunique()),
        "duplicate_quote_groups": int((quote_sizes > 1).sum()),
        "extra_quote_rows": int((quote_sizes - 1).clip(lower=0).sum()),
        "alternate_line_groups": int((alt_counts > 1).sum()),
        "player_correlation_groups": int(((player_group_counts > 1) | (player_market_counts.reindex(player_group_counts.index, fill_value=0) > 1)).sum()),
        "game_exposure_groups": int((game_counts > 1).sum()) if len(game_counts) else 0,
        "team_exposure_groups": int((team_counts > 1).sum()),
        "blocked_rows": int((~d["Safety state"].astype(str).str.upper().eq("SAFE")).sum()),
        "ranking_enabled": False,
    }


__all__ = ["MODEL_VERSION", "PROTECTION_COLUMNS", "annotate", "diagnostics"]
