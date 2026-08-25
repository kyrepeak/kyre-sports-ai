"""WNBA Points V1.9.8.4.33 — display current Points lines while exact-book pairs are pending.

Presentation/transport-only wrapper over V1.9.8.4.32.

Why this exists
---------------
V1.9.8.4.32 correctly restored the complete Top-5 Step 2-12 card stack when the
configured sportsbook-specific O/U pair is unavailable. Those preview cards
intentionally showed `Today O —` because no line was allowed to be invented.

SportsGameOdds v2 can still return a top-level current consensus O/U line
(`bookOverUnder`, with `fairOverUnder` as a secondary reference) even when the
account/response does not expose a usable configured-book `byBookmaker` pair.
V1.9.8.4.33 uses that provider-returned line for DISPLAY ONLY on the existing
PRE-MARKET cards.

Safety contract
---------------
- Exact configured-book same-player + same-book + same-line O/U pairs remain the
  ONLY lines allowed into the protected production Monte Carlo/readiness path.
- A consensus reference line can NEVER unlock 5M, create sportsbook odds, create
  no-vig probability, create EV, qualify a pick, or alter production ranking.
- When exact market pairs are present, the original production market path wins
  unchanged and this fallback is not used.
- No projection, minutes, matchup, H2H, Monte Carlo, calibration or ranking math
  is modified. PRA/Rebounds/Assists/Spread/MLB/NFL are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198432 as prior
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points
h2h = prior.h2h

MODEL_VERSION = "WNBA POINTS V1.9.8.4.33 • CURRENT LINE DISPLAY FALLBACK"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_HISTORY_OPTIONAL = getattr(
    prior,
    "_kyre_v198433_base_history_optional",
    prior._history_context_market_optional,
)
setattr(prior, "_kyre_v198433_base_history_optional", _BASE_HISTORY_OPTIONAL)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _consensus_line(odd: dict):
    """Prefer SportsGameOdds book consensus, then fair consensus."""
    for field, label in (
        ("bookOverUnder", "SGO BOOK CONSENSUS"),
        ("fairOverUnder", "SGO FAIR CONSENSUS"),
        ("overUnder", "SGO CONSENSUS"),
    ):
        value = _num((odd or {}).get(field), np.nan)
        if pd.notna(value):
            return float(value), label
    return np.nan, ""


@st.cache_data(ttl=90, show_spinner=False, max_entries=16)
def _display_points_lines(day: str) -> pd.DataFrame:
    """Provider-returned player Points reference lines; never production pairs."""
    key = sgo1.get_api_key()
    if not key:
        return pd.DataFrame()

    try:
        schedule = schedule25.schedule_for_date(day)
    except Exception:
        return pd.DataFrame()
    if schedule is None or schedule.empty:
        return pd.DataFrame()

    starts_after, starts_before = sgo1._slate_window(day)
    try:
        events = prior._fetch_points_events_verified(key, starts_after, starts_before)
    except Exception:
        return pd.DataFrame()
    if not events:
        return pd.DataFrame()

    rows = []
    for _, sched in schedule.iterrows():
        try:
            event = sgo1._match_event(events, sched)
        except Exception:
            event = None
        if event is None:
            continue

        game_id = str(sched.get("game_id") or "")
        for odd in prior._iter_odds(event):
            if not isinstance(odd, dict):
                continue
            if str(odd.get("statID") or "").lower().strip() != "points":
                continue
            if str(odd.get("periodID") or "").lower().strip() != "game":
                continue
            if str(odd.get("betTypeID") or "").lower().strip() != "ou":
                continue
            side = str(odd.get("sideID") or "").lower().strip()
            if side not in {"over", "under"}:
                continue

            player_id = str(odd.get("playerID") or odd.get("statEntityID") or "").strip()
            if not player_id or player_id.lower() in {"all", "home", "away"}:
                continue
            line, source = _consensus_line(odd)
            if pd.isna(line):
                continue

            try:
                player_name = sgo1._player_name_from_event(event, player_id, odd.get("marketName"))
            except Exception:
                player_name = str(odd.get("marketName") or player_id)
            player_key = sgo1._norm(player_name)
            if not player_key:
                continue

            rows.append({
                "game_id": game_id,
                "player_key_ref": player_key,
                "player_name_ref": player_name,
                "display_line": float(line),
                "display_line_source": source,
                "display_side": side,
            })

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    # Over and Under should carry the same number. If the provider transiently
    # disagrees between sides, use the modal line; ties resolve to the median.
    grouped = []
    for (gid, pkey), grp in frame.groupby(["game_id", "player_key_ref"], dropna=False):
        vals = pd.to_numeric(grp["display_line"], errors="coerce").dropna()
        if vals.empty:
            continue
        counts = vals.value_counts()
        top_count = int(counts.max())
        candidates = sorted(float(v) for v in counts[counts.eq(top_count)].index)
        median = float(vals.median())
        line = min(candidates, key=lambda x: abs(x - median))
        chosen = grp.loc[pd.to_numeric(grp["display_line"], errors="coerce").eq(line)].iloc[0]
        grouped.append({
            "game_id": str(gid),
            "player_key_ref": str(pkey),
            "display_line": float(line),
            "display_line_source": str(chosen.get("display_line_source") or "SGO CONSENSUS"),
        })
    return pd.DataFrame(grouped)


def _history_context_with_current_line(day: str) -> pd.DataFrame:
    context = _BASE_HISTORY_OPTIONAL(day)
    if not isinstance(context, pd.DataFrame) or context.empty:
        return pd.DataFrame()

    # Real exact market rows always win unchanged.
    is_preview = False
    if "_premarket_preview" in context.columns:
        is_preview = bool(context["_premarket_preview"].fillna(False).astype(bool).all())
    if not is_preview:
        return context

    refs = _display_points_lines(str(day))
    if refs.empty:
        out = context.copy()
        out["books"] = out.get("books", "")
        return out

    out = context.copy()
    out["game_id"] = out.get("game_id", "").astype(str)
    # Normalize from the displayed player name rather than trusting cross-source
    # IDs. This is the same conservative name-normalization family already used
    # by the SportsGameOdds bridge.
    names = out.get("Player", out.get("PLAYER_NAME", "")).astype(str)
    out["player_key_ref"] = names.map(sgo1._norm)
    out = out.merge(refs, on=["game_id", "player_key_ref"], how="left")

    ref_line = pd.to_numeric(out.get("display_line"), errors="coerce")
    current_line = pd.to_numeric(out.get("line"), errors="coerce")
    use_ref = current_line.isna() & ref_line.notna()
    out.loc[use_ref, "line"] = ref_line.loc[use_ref]

    proj = pd.to_numeric(out.get("Proj PTS"), errors="coerce")
    line_now = pd.to_numeric(out.get("line"), errors="coerce")
    out["Delta"] = proj - line_now

    if "books" not in out.columns:
        out["books"] = ""
    source = out.get("display_line_source", pd.Series("", index=out.index)).fillna("").astype(str)
    out.loc[use_ref, "books"] = source.loc[use_ref] + " • DISPLAY ONLY"
    out["_display_only_line"] = use_ref
    return out.drop(columns=["player_key_ref"], errors="ignore")


def _install() -> None:
    # Let V1.9.8.4.32 continue owning the protected exact-market + preview split,
    # then replace only the preview card context it installs at render time.
    prior._history_context_market_optional = _history_context_with_current_line


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎯 Points V1.9.8.4.33 • current SportsGameOdds Points line shown on PRE-MARKET cards when available • "
        "consensus fallback is DISPLAY ONLY • exact configured-book O/U pair still required for 5M, odds, no-vig, EV and qualification"
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
