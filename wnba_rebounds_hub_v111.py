"""WNBA Rebounds V1.1.1 — Step-2 identity/status reconciliation hotfix.

Keeps the V1.1 schedule, roster and availability gate intact, but makes the
injury overlay auditable and robust when ESPN's injury and roster feeds expose
different athlete identifiers for the same current player.

Matching order is deliberately conservative:
1) exact ESPN player id + verified slate team;
2) exact normalized player name + verified slate team, only when unique.

No fuzzy/cross-team matching is allowed. No rebound projection, sportsbook
market, Monte Carlo or frozen Points/PRA/MLB math is changed.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v11 as base

MODEL_VERSION = "WNBA REBOUNDS V1.1.1 • STEP 2 IDENTITY RECONCILIATION"


def _status_token(value) -> str:
    if isinstance(value, dict):
        value = " ".join(
            str(value.get(k) or "")
            for k in ("name", "type", "description", "abbreviation", "displayName")
        )
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _pick_designation(text: str):
    t = f" {str(text or '').lower()} "
    if any(x in t for x in (" ruled out ", " will miss ", " won't play ", " wont play ", " out indefinitely ")):
        return "OUT"
    if " inactive " in t:
        return "INACTIVE"
    if " doubtful " in t:
        return "DOUBTFUL"
    if " questionable " in t or any(x in t for x in (" day-to-day ", " day to day ", " game-time decision ", " gtd ")):
        return "QUESTIONABLE"
    if " probable " in t:
        return "PROBABLE"
    # Only accept a bare OUT token after more specific designations are checked.
    if " out " in t:
        return "OUT"
    return None


def _injury_status(item: dict) -> str:
    """Prefer ESPN's structured designation, then fall back to narrative text."""
    item = item or {}
    details = item.get("details") or {}
    fantasy = details.get("fantasyStatus") or {}

    # Structured fields get first say. This prevents a stale/contradictory
    # sentence fragment from overriding the provider's explicit designation.
    for raw in (item.get("status"), fantasy):
        label = _pick_designation(_status_token(raw))
        if label:
            return label

    narrative = " ".join(
        str(x or "")
        for x in (
            item.get("shortComment"),
            item.get("longComment"),
            item.get("type"),
            details.get("type"),
            fantasy.get("description") if isinstance(fantasy, dict) else "",
            fantasy.get("abbreviation") if isinstance(fantasy, dict) else "",
        )
    )
    return _pick_designation(_status_token(narrative)) or "REPORTED"


def _overlay_availability(roster, injuries, slate, feed_ok):
    if roster is None or roster.empty:
        return pd.DataFrame(), pd.DataFrame()

    out = roster.copy()
    out["PLAYER_ID"] = out["PLAYER_ID"].astype(str)
    out["AVAILABILITY"] = "NOT LISTED" if feed_ok else "UNKNOWN"
    out["INJURY"] = ""
    out["INJURY_NOTE"] = ""
    out["INJURY_UPDATED"] = ""
    out["INJURY_SOURCE"] = "ESPN WNBA injuries" if feed_ok else "unavailable"
    out["INJURY_MATCH_MODE"] = ""
    if injuries is None or injuries.empty:
        return out, pd.DataFrame()

    slate_names, slate_abbrs = {}, {}
    for tid, meta in base._team_meta(slate).items():
        slate_names[base._norm(meta.get("name"))] = tid
        slate_abbrs[base._norm(meta.get("abbr"))] = tid

    inj = injuries.copy()
    inj["_slate_team_id"] = inj.apply(
        lambda r: slate_names.get(base._norm(r.get("TEAM_NAME")))
        or slate_abbrs.get(base._norm(r.get("TEAM_ABBR")))
        or 0,
        axis=1,
    )
    inj = inj[inj["_slate_team_id"].astype(int).ne(0)].copy()

    by_pid = {}
    by_name_team = {}
    for idx, row in out.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = base._int(row.get("TEAM_ID"))
        pname = base._norm(row.get("PLAYER_NAME"))
        if pid:
            by_pid.setdefault(pid, []).append(idx)
        if tid and pname:
            by_name_team.setdefault((tid, pname), []).append(idx)

    unmatched = []
    for _, row in inj.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = base._int(row.get("_slate_team_id"))
        pname = base._norm(row.get("PLAYER_NAME"))
        matched_idx = None
        match_mode = ""

        # Primary: exact athlete id on the verified slate team.
        id_matches = [idx for idx in by_pid.get(pid, []) if base._int(out.at[idx, "TEAM_ID"]) == tid]
        if len(id_matches) == 1:
            matched_idx = id_matches[0]
            match_mode = "ESPN_ID_EXACT"

        # Safe fallback: exact normalized player name + same verified team.
        if matched_idx is None:
            name_matches = by_name_team.get((tid, pname), []) if tid and pname else []
            if len(name_matches) == 1:
                matched_idx = name_matches[0]
                match_mode = "NAME_TEAM_EXACT"

        if matched_idx is None:
            miss = row.to_dict()
            miss["MATCH_REASON"] = "NO_UNIQUE_ID_OR_EXACT_NAME_TEAM_MATCH"
            unmatched.append(miss)
            continue

        out.at[matched_idx, "AVAILABILITY"] = str(row.get("AVAILABILITY") or "REPORTED")
        out.at[matched_idx, "INJURY"] = str(row.get("INJURY") or "")
        out.at[matched_idx, "INJURY_NOTE"] = str(row.get("SHORT_NOTE") or "")
        out.at[matched_idx, "INJURY_UPDATED"] = str(row.get("UPDATED") or "")
        out.at[matched_idx, "INJURY_MATCH_MODE"] = match_mode

    return out, pd.DataFrame(unmatched)


def render_wnba_rebounds_hub(section_header=None, status_info=None, _unused=None, h=None):
    # Patch only the two Step-2 reconciliation functions. The V1.1 renderer,
    # schedule logic, roster source, freshness rules and hard gate stay intact.
    base._injury_status = _injury_status
    base._overlay_availability = _overlay_availability

    # Force one fresh read on first load of this hotfix so cached V1.1 rows that
    # were parsed before the new designation/reconciliation logic cannot linger.
    key = "wnba_rebounds_v111_cache_refresh_done"
    if not st.session_state.get(key):
        try:
            base._injury_feed.clear()
        except Exception:
            pass
        try:
            base._current_rosters.clear()
        except Exception:
            pass
        st.session_state[key] = True

    st.caption("🧩 WNBA Rebounds V1.1.1 • conservative injury identity reconciliation active • no model math yet")
    base.render_wnba_rebounds_hub(section_header, status_info, _unused, h)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
