"""WNBA Points V1.9.8.4.34 — two-stage SportsGameOdds player-points transport repair.

Transport/presentation-only wrapper over V1.9.8.4.33.

Root cause targeted
-------------------
The app is rendering the restored PRE-MARKET Top-5 cards, but `Today O —` can
remain blank when the one-shot WNBA request does not return player Points odds.
SportsGameOdds documents that player props live on the same Event and that
eventID/eventIDs takes priority while oddID/includeOpposingOdds still shape the
returned odds. This wrapper therefore resolves today's WNBA Events first, then
re-fetches those exact eventIDs for the Points O/U market.

Display behavior
----------------
- Exact configured-book same-player + same-book + same-line O/U pairs still win.
- If production pairing is not available, a provider-returned current Points line
  may be shown on PRE-MARKET cards for display only.
- Display-line extraction now checks both top-level consensus fields and each
  available byBookmaker overUnder value.
- Name matching is allowed as a display-only fallback when game-id namespaces
  differ across the verified projection and sportsbook schedule layers.

Safety contract
---------------
No display-only line can unlock 5M, create odds/no-vig/EV, qualify a pick, or
change production ordering. All existing production/readiness gates remain
fail-closed and unchanged. PRA/Rebounds/Assists/Spread/MLB/NFL are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_points_hub_v198433 as prior
import wnba_points_hub_v198432 as v432
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points
h2h = prior.h2h

MODEL_VERSION = "WNBA POINTS V1.9.8.4.34 • TWO-STAGE CURRENT-LINE TRANSPORT REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_HISTORY_OPTIONAL = getattr(prior, "_kyre_v198434_base_history_optional", prior._BASE_HISTORY_OPTIONAL)
setattr(prior, "_kyre_v198434_base_history_optional", _BASE_HISTORY_OPTIONAL)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _events_from_response(response):
    response.raise_for_status()
    try:
        payload = response.json()
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _has_points(events) -> bool:
    try:
        return bool(v432._contains_player_points(events))
    except Exception:
        pass
    for event in events or []:
        odds = (event or {}).get("odds") or {}
        values = odds.values() if isinstance(odds, dict) else odds if isinstance(odds, list) else []
        for odd in values:
            if not isinstance(odd, dict):
                continue
            stat = str(odd.get("statID") or "").lower().strip()
            period = str(odd.get("periodID") or "").lower().strip()
            bet = str(odd.get("betTypeID") or "").lower().strip()
            entity = str(odd.get("playerID") or odd.get("statEntityID") or "").lower().strip()
            if stat == "points" and period == "game" and bet == "ou" and entity not in {"", "all", "home", "away"}:
                return True
    return False


@st.cache_data(ttl=90, show_spinner=False, max_entries=16)
def _fetch_points_events_two_stage(api_key: str, starts_after: str, starts_before: str):
    headers = {"x-api-key": str(api_key)}
    endpoint = f"{sgo1.SGO_BASE}/events"
    discovery_attempts = (
        {"leagueID": "WNBA", "type": "match", "finalized": "false", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "oddsPresent": "true", "limit": 100},
        {"leagueID": "WNBA", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "oddsAvailable": "true", "limit": 100},
        {"leagueID": "WNBA", "startsAfter": str(starts_after), "startsBefore": str(starts_before), "limit": 100},
    )
    discovered = []
    for params in discovery_attempts:
        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=20)
            if response.status_code != 200:
                if response.status_code in {400, 403, 404, 422, 429, 500, 502, 503, 504}:
                    continue
                response.raise_for_status()
            data = _events_from_response(response)
            if data:
                discovered = data
                break
        except Exception:
            continue
    if _has_points(discovered):
        return discovered
    event_ids = []
    for event in discovered:
        eid = str((event or {}).get("eventID") or (event or {}).get("id") or "").strip()
        if eid and eid not in event_ids:
            event_ids.append(eid)
    if event_ids:
        ids = ",".join(event_ids[:100])
        over = "points-PLAYER_ID-game-ou-over"
        both = "points-PLAYER_ID-game-ou-over,points-PLAYER_ID-game-ou-under"
        detail_attempts = (
            {"eventIDs": ids, "oddID": over, "includeOpposingOdds": "true", "includeAltLines": "false"},
            {"eventIDs": ids, "oddIDs": over, "includeOpposingOdds": "true", "includeAltLines": "false"},
            {"eventIDs": ids, "oddID": both, "includeAltLines": "false"},
            {"eventIDs": ids, "oddIDs": both, "includeAltLines": "false"},
            {"eventIDs": ids, "includeAltLines": "false"},
        )
        last_detail = []
        for params in detail_attempts:
            try:
                response = requests.get(endpoint, params=params, headers=headers, timeout=20)
                if response.status_code != 200:
                    if response.status_code in {400, 403, 404, 422, 429, 500, 502, 503, 504}:
                        continue
                    response.raise_for_status()
                data = _events_from_response(response)
                last_detail = data
                if _has_points(data):
                    return data
            except Exception:
                continue
        if last_detail:
            return last_detail
    try:
        fallback = v432._fetch_points_events_verified(str(api_key), str(starts_after), str(starts_before))
        if fallback:
            return fallback
    except Exception:
        pass
    if discovered:
        return discovered
    return []


def _book_candidates(odd: dict):
    rows = []
    books = (odd or {}).get("byBookmaker") or {}
    if not isinstance(books, dict):
        return rows
    configured = set()
    try:
        configured = {sgo1._book_id(x) for x in str(sgo1.get_bookmakers() or "").split(",") if sgo1._book_id(x)}
    except Exception:
        configured = set()
    for book_id, payload in books.items():
        if not isinstance(payload, dict) or payload.get("available") is False:
            continue
        line = _num(payload.get("overUnder"), np.nan)
        if pd.isna(line):
            continue
        key = sgo1._book_id(book_id)
        label = sgo1._BOOK_ALIASES.get(key, str(book_id))
        try:
            age = sgo1._age_seconds(payload.get("lastUpdatedAt"))
        except Exception:
            age = None
        rows.append({"line": float(line), "book_key": key, "book": str(label), "configured": key in configured if configured else False, "age_seconds": age})
    return rows


def _choose_display_line(odd: dict):
    books = _book_candidates(odd)
    if books:
        books = sorted(books, key=lambda r: (0 if r.get("configured") else 1, float(r.get("age_seconds")) if r.get("age_seconds") is not None else 10**12, str(r.get("book") or "")))
        best = books[0]
        tag = f"{best['book']} CURRENT LINE"
        if not best.get("configured"):
            tag += " • PROVIDER BOOK"
        return float(best["line"]), tag
    for field, label in (("bookOverUnder", "SGO BOOK CONSENSUS"), ("fairOverUnder", "SGO FAIR CONSENSUS"), ("overUnder", "SGO CONSENSUS")):
        value = _num((odd or {}).get(field), np.nan)
        if pd.notna(value):
            return float(value), label
    return np.nan, ""


@st.cache_data(ttl=90, show_spinner=False, max_entries=16)
def _display_points_lines_robust(day: str) -> pd.DataFrame:
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
        events = _fetch_points_events_two_stage(key, starts_after, starts_before)
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
        odds = (event or {}).get("odds") or {}
        values = odds.values() if isinstance(odds, dict) else odds if isinstance(odds, list) else []
        for odd in values:
            if not isinstance(odd, dict):
                continue
            stat = str(odd.get("statID") or "").lower().strip()
            period = str(odd.get("periodID") or "").lower().strip()
            bet = str(odd.get("betTypeID") or "").lower().strip()
            side = str(odd.get("sideID") or "").lower().strip()
            entity = str(odd.get("playerID") or odd.get("statEntityID") or "").strip()
            if stat != "points" or period != "game" or bet != "ou" or side not in {"over", "under"}:
                continue
            if not entity or entity.lower() in {"all", "home", "away"}:
                continue
            line, source = _choose_display_line(odd)
            if pd.isna(line):
                continue
            try:
                player_name = sgo1._player_name_from_event(event, entity, odd.get("marketName"))
            except Exception:
                player_name = str(odd.get("marketName") or entity)
            pkey = sgo1._norm(player_name)
            if not pkey:
                continue
            rows.append({"game_id": game_id, "player_key_ref": pkey, "player_name_ref": player_name, "display_line": float(line), "display_line_source": source, "display_side": side})
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    grouped = []
    for (gid, pkey), grp in frame.groupby(["game_id", "player_key_ref"], dropna=False):
        over = grp.loc[grp["display_side"].astype(str).str.lower().eq("over")]
        chosen_pool = over if not over.empty else grp
        vals = pd.to_numeric(chosen_pool["display_line"], errors="coerce").dropna()
        if vals.empty:
            continue
        counts = vals.value_counts()
        top_count = int(counts.max())
        candidates = sorted(float(v) for v in counts[counts.eq(top_count)].index)
        median = float(vals.median())
        line = min(candidates, key=lambda x: abs(x - median))
        chosen = chosen_pool.loc[pd.to_numeric(chosen_pool["display_line"], errors="coerce").eq(line)].iloc[0]
        grouped.append({"game_id": str(gid), "player_key_ref": str(pkey), "display_line": float(line), "display_line_source": str(chosen.get("display_line_source") or "SGO CURRENT LINE")})
    return pd.DataFrame(grouped)


def _history_context_with_current_line_robust(day: str) -> pd.DataFrame:
    context = _BASE_HISTORY_OPTIONAL(day)
    if not isinstance(context, pd.DataFrame) or context.empty:
        return pd.DataFrame()
    preview = False
    if "_premarket_preview" in context.columns:
        preview = bool(context["_premarket_preview"].fillna(False).astype(bool).all())
    if not preview:
        return context
    refs = _display_points_lines_robust(str(day))
    if refs.empty:
        return context
    out = context.copy()
    if "line" not in out.columns:
        out["line"] = np.nan
    if "books" not in out.columns:
        out["books"] = ""
    names = out.get("Player", out.get("PLAYER_NAME", "")).astype(str)
    out["player_key_ref"] = names.map(sgo1._norm)
    out["game_id"] = out.get("game_id", "").astype(str)
    exact_refs = refs.drop_duplicates(["game_id", "player_key_ref"], keep="first")
    out = out.merge(exact_refs[["game_id", "player_key_ref", "display_line", "display_line_source"]], on=["game_id", "player_key_ref"], how="left")
    missing = pd.to_numeric(out.get("display_line"), errors="coerce").isna()
    if missing.any():
        unique_name_refs = refs.sort_values(["player_key_ref", "game_id"]).drop_duplicates(["player_key_ref", "display_line"], keep="first")
        counts = unique_name_refs.groupby("player_key_ref")["display_line"].nunique()
        safe_keys = set(counts[counts.eq(1)].index.astype(str))
        name_map = unique_name_refs.loc[unique_name_refs["player_key_ref"].astype(str).isin(safe_keys)].drop_duplicates("player_key_ref", keep="first").set_index("player_key_ref")[["display_line", "display_line_source"]]
        for idx in out.index[missing]:
            key = str(out.at[idx, "player_key_ref"] or "")
            if key in name_map.index:
                out.at[idx, "display_line"] = float(name_map.at[key, "display_line"])
                out.at[idx, "display_line_source"] = str(name_map.at[key, "display_line_source"])
    ref_line = pd.to_numeric(out.get("display_line"), errors="coerce")
    current_line = pd.to_numeric(out.get("line"), errors="coerce")
    use_ref = current_line.isna() & ref_line.notna()
    out.loc[use_ref, "line"] = ref_line.loc[use_ref]
    proj = pd.to_numeric(out.get("Proj PTS"), errors="coerce")
    line_now = pd.to_numeric(out.get("line"), errors="coerce")
    out["Delta"] = proj - line_now
    source = out.get("display_line_source", pd.Series("", index=out.index)).fillna("").astype(str)
    out.loc[use_ref, "books"] = source.loc[use_ref] + " • DISPLAY ONLY"
    out["_display_only_line"] = use_ref
    return out.drop(columns=["player_key_ref"], errors="ignore")


def _install() -> None:
    v432._fetch_points_events_verified = _fetch_points_events_two_stage
    prior._display_points_lines = _display_points_lines_robust
    prior._history_context_with_current_line = _history_context_with_current_line_robust


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption("🛰️ Points V1.9.8.4.34 • two-stage WNBA event→eventID Points fetch active • current byBookmaker/consensus line may populate PRE-MARKET cards • display fallback cannot unlock 5M • exact same-book/same-line O/U pair and all production gates remain mandatory")
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points", "render_wnba_points_hub"]
