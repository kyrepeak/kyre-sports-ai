"""WNBA Daily Picks Step 9 — read-only Top-5 selection layer.

Consumes only the Step-8 ranked preview. It does not rescore candidates, import
production models, launch/restore simulations, refresh injuries/markets, request
sportsbook data, or write model/session state.

Selection preserves Step-8 order and adds only bounded card-diversity rules:
- one published card per player;
- at most three published cards from the same game;
- at most three published cards from the same player's team;
- maximum five cards; never force five.

Step 10 owns the final production-ready recheck/guard.
"""
from __future__ import annotations

from typing import Any
import re
import unicodedata

import numpy as np
import pandas as pd

MODEL_VERSION = "WNBA DAILY PICKS SELECTION V1 • STEP 9 READ ONLY"
MAX_CARDS = 5
MAX_PER_GAME = 3
MAX_PER_TEAM = 3


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _num(value: Any) -> float:
    try:
        x = float(value)
        return float(x) if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _game_key(row: pd.Series) -> str:
    team = _norm(row.get("Team"))
    opp = _norm(row.get("Opponent"))
    if not team or not opp:
        return ""
    return "::".join(sorted((team, opp)))


def _ordered_ranked(ranked: pd.DataFrame) -> pd.DataFrame:
    if ranked is None or ranked.empty or "Rank state" not in ranked.columns:
        return pd.DataFrame()
    d = ranked[ranked["Rank state"].astype(str).str.upper().eq("RANKED")].copy()
    if d.empty:
        return d
    rank = pd.to_numeric(d.get("Rank"), errors="coerce")
    score = pd.to_numeric(d.get("Ranking score"), errors="coerce")
    d["_selection_rank"] = rank
    d["_selection_score"] = score
    d = d.sort_values(
        ["_selection_rank", "_selection_score"],
        ascending=[True, False],
        na_position="last",
        kind="mergesort",
    )
    return d.reset_index(drop=True)


def select_top5(ranked: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return selected cards plus a display-only skip audit, preserving Step-8 order."""
    ordered = _ordered_ranked(ranked)
    if ordered.empty:
        cols = list(ranked.columns) if isinstance(ranked, pd.DataFrame) else []
        return pd.DataFrame(columns=cols + ["Daily rank", "Selection state"]), pd.DataFrame(
            columns=["Player", "Market", "Reason", "Step-8 rank"]
        )

    selected: list[pd.Series] = []
    skipped: list[dict[str, Any]] = []
    players: set[str] = set()
    game_counts: dict[str, int] = {}
    team_counts: dict[str, int] = {}

    for _, row in ordered.iterrows():
        if len(selected) >= MAX_CARDS:
            break

        player = _norm(row.get("Player"))
        team = _norm(row.get("Team"))
        game = _game_key(row)
        reason = ""

        if not player:
            reason = "MISSING PLAYER IDENTITY"
        elif player in players:
            reason = "SAME PLAYER ALREADY SELECTED"
        elif game and game_counts.get(game, 0) >= MAX_PER_GAME:
            reason = f"GAME EXPOSURE CAP ({MAX_PER_GAME})"
        elif team and team_counts.get(team, 0) >= MAX_PER_TEAM:
            reason = f"TEAM EXPOSURE CAP ({MAX_PER_TEAM})"

        if reason:
            skipped.append({
                "Player": _text(row.get("Player")) or "—",
                "Market": _text(row.get("Market")) or "—",
                "Reason": reason,
                "Step-8 rank": _num(row.get("Rank")),
            })
            continue

        out = row.copy()
        out["Daily rank"] = len(selected) + 1
        out["Selection state"] = "SELECTED"
        selected.append(out)
        players.add(player)
        if game:
            game_counts[game] = game_counts.get(game, 0) + 1
        if team:
            team_counts[team] = team_counts.get(team, 0) + 1

    selected_df = pd.DataFrame(selected)
    if not selected_df.empty:
        selected_df = selected_df.drop(columns=["_selection_rank", "_selection_score"], errors="ignore")
    skipped_df = pd.DataFrame(skipped, columns=["Player", "Market", "Reason", "Step-8 rank"])
    return selected_df, skipped_df


def diagnostics(ranked: pd.DataFrame, selected: pd.DataFrame, skipped: pd.DataFrame) -> dict[str, Any]:
    eligible = _ordered_ranked(ranked)
    markets = selected.get("Market", pd.Series(dtype=str)).astype(str).str.upper() if isinstance(selected, pd.DataFrame) else pd.Series(dtype=str)
    reasons = skipped.get("Reason", pd.Series(dtype=str)).astype(str) if isinstance(skipped, pd.DataFrame) else pd.Series(dtype=str)
    return {
        "eligible": int(len(eligible)),
        "published": int(len(selected)) if isinstance(selected, pd.DataFrame) else 0,
        "markets": int(markets[markets.str.len().gt(0)].nunique()) if not markets.empty else 0,
        "skipped": int(len(skipped)) if isinstance(skipped, pd.DataFrame) else 0,
        "same_player_skips": int(reasons.str.contains("SAME PLAYER", case=False, na=False).sum()) if not reasons.empty else 0,
        "game_cap_skips": int(reasons.str.contains("GAME EXPOSURE", case=False, na=False).sum()) if not reasons.empty else 0,
        "team_cap_skips": int(reasons.str.contains("TEAM EXPOSURE", case=False, na=False).sum()) if not reasons.empty else 0,
        "max_cards": MAX_CARDS,
        "simulations": 0,
        "writes": 0,
        "network_requests": 0,
        "production_guard": "PENDING STEP 10",
    }


__all__ = [
    "MODEL_VERSION", "MAX_CARDS", "MAX_PER_GAME", "MAX_PER_TEAM",
    "select_top5", "diagnostics",
]
