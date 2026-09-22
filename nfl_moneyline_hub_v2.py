"""Kyre Sports AI — NFL Moneyline V2 Step 2 verification layer.

Preserves the verified Moneyline Step-1 slate/clock foundation and adds only:
- current ESPN NFL QB depth-chart verification;
- roster fallback when a depth chart is unavailable (explicitly unverified as depth);
- current ESPN league injury-report verification;
- preseason rotation/rest guard that remains LOCKED unless an explicit game-plan
  source is later added.

No sportsbook price, win probability, fair odds, edge, EV, Monte Carlo,
qualification, ranking or recommendation is produced. MLB/WNBA are not imported.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as prior

ET = foundation.ET
MODEL_VERSION = "NFL MONEYLINE V2 • STEP 2 QB/DEPTH + INJURY VERIFICATION"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}

# ESPN team IDs are stable league identifiers. Keeping this local avoids an
# unnecessary team-directory request on every new slate.
TEAM_IDS = {
    "ARI": "22", "ATL": "1", "BAL": "33", "BUF": "2", "CAR": "29", "CHI": "3",
    "CIN": "4", "CLE": "5", "DAL": "6", "DEN": "7", "DET": "8", "GB": "9",
    "HOU": "34", "IND": "11", "JAX": "30", "KC": "12", "LV": "13", "LAC": "24",
    "LAR": "14", "MIA": "15", "MIN": "16", "NE": "17", "NO": "18", "NYG": "19",
    "NYJ": "20", "PHI": "21", "PIT": "23", "SF": "25", "SEA": "26", "TB": "27",
    "TEN": "10", "WSH": "28",
}


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _json_get(url: str, timeout: int = 8):
    diag = {"url": url, "http": None, "ok": False, "error": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
        diag["ok"] = True
        return payload, diag
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return {}, diag


@st.cache_data(ttl=300, show_spinner=False)
def _depth_payload(team_id: str):
    return _json_get(f"{ESPN_BASE}/teams/{team_id}/depthcharts")


@st.cache_data(ttl=300, show_spinner=False)
def _roster_payload(team_id: str):
    return _json_get(f"{ESPN_BASE}/teams/{team_id}/roster")


@st.cache_data(ttl=120, show_spinner=False)
def _league_injuries_payload():
    return _json_get(f"{ESPN_BASE}/injuries")


def _parse_qb_depth(payload: dict):
    rows = []
    for chart in (payload or {}).get("depthCharts", []) or []:
        positions = chart.get("positions") or {}
        if isinstance(positions, list):
            candidates = positions
        elif isinstance(positions, dict):
            candidates = list(positions.values())
        else:
            candidates = []
        for block in candidates:
            if not isinstance(block, dict):
                continue
            position = block.get("position") or {}
            abbr = _safe(position.get("abbreviation")).upper()
            name = _safe(position.get("name")).lower()
            if abbr != "QB" and "quarterback" not in name:
                continue
            for item in block.get("athletes", []) or []:
                athlete = item.get("athlete") or {}
                rows.append({
                    "rank": int(pd.to_numeric(item.get("rank"), errors="coerce") or (len(rows) + 1)),
                    "athlete_id": _safe(athlete.get("id")),
                    "name": _safe(athlete.get("displayName") or athlete.get("fullName"), "Unknown QB"),
                    "source": "ESPN DEPTH CHART",
                })
    rows = sorted(rows, key=lambda x: (x.get("rank", 99), x.get("name", "")))
    seen = set()
    out = []
    for row in rows:
        key = row.get("athlete_id") or row.get("name")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _parse_qb_roster(payload: dict):
    rows = []
    for group in (payload or {}).get("athletes", []) or []:
        group_name = _safe(group.get("position")).lower()
        for item in group.get("items", []) or []:
            pos = item.get("position") or {}
            abbr = _safe(pos.get("abbreviation")).upper()
            pos_name = _safe(pos.get("name")).lower()
            if abbr != "QB" and "quarterback" not in pos_name and "quarterback" not in group_name:
                continue
            rows.append({
                "rank": len(rows) + 1,
                "athlete_id": _safe(item.get("id")),
                "name": _safe(item.get("displayName") or item.get("fullName"), "Unknown QB"),
                "source": "ESPN ROSTER FALLBACK",
            })
    return rows


def _status_text(value) -> str:
    if isinstance(value, dict):
        return _safe(
            value.get("name")
            or value.get("description")
            or value.get("displayName")
            or value.get("abbreviation"),
            "Unspecified",
        )
    return _safe(value, "Unspecified")


def _parse_injuries(payload: dict):
    """Normalize the league-wide site API injury payload by team abbreviation."""
    by_team = {}
    blocks = (payload or {}).get("injuries", []) or []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        team = block.get("team") or {}
        abbr = _safe(team.get("abbreviation")).upper()
        team_id = _safe(team.get("id"))
        if not abbr and team_id:
            for k, v in TEAM_IDS.items():
                if str(v) == team_id:
                    abbr = k
                    break
        if not abbr:
            continue
        team_rows = by_team.setdefault(abbr, [])
        nested = block.get("injuries") or block.get("items") or []
        for item in nested:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or item.get("player") or {}
            position = athlete.get("position") or item.get("position") or {}
            status = _status_text(item.get("status") or item.get("type") or item.get("designation"))
            detail = _safe(
                item.get("shortComment")
                or item.get("longComment")
                or item.get("details")
                or item.get("description")
            )
            team_rows.append({
                "athlete_id": _safe(athlete.get("id")),
                "name": _safe(athlete.get("displayName") or athlete.get("fullName") or item.get("name"), "Unknown player"),
                "position": _safe(position.get("abbreviation") or position.get("name"), "—"),
                "status": status,
                "detail": detail,
            })
    return by_team


def _injury_priority(status: str) -> int:
    s = _safe(status).upper()
    if "OUT" in s or "INJURED RESERVE" in s or s == "IR":
        return 0
    if "DOUBTFUL" in s:
        return 1
    if "QUESTIONABLE" in s:
        return 2
    if "PROBABLE" in s:
        return 3
    return 4


def _team_context(abbr: str, team_name: str, injury_map: dict, injury_feed_ok: bool):
    abbr = _safe(abbr).upper()
    team_id = TEAM_IDS.get(abbr, "")
    result = {
        "abbr": abbr,
        "team": team_name,
        "team_id": team_id,
        "qbs": [],
        "depth_state": "CHECK",
        "depth_http": None,
        "injury_state": "VERIFIED" if injury_feed_ok else "CHECK",
        "injuries": list(injury_map.get(abbr, [])),
        "rotation_state": "UNVERIFIED",
    }
    if not team_id:
        return result

    depth_payload, ddiag = _depth_payload(team_id)
    result["depth_http"] = ddiag.get("http")
    qbs = _parse_qb_depth(depth_payload) if ddiag.get("ok") else []
    if qbs:
        result["qbs"] = qbs
        result["depth_state"] = "VERIFIED"
    else:
        roster_payload, rdiag = _roster_payload(team_id)
        fallback = _parse_qb_roster(roster_payload) if rdiag.get("ok") else []
        if fallback:
            result["qbs"] = fallback
            result["depth_state"] = "ROSTER FALLBACK"
            result["depth_http"] = ddiag.get("http") or rdiag.get("http")

    injuries = sorted(result["injuries"], key=lambda x: (_injury_priority(x.get("status")), x.get("name", "")))
    result["injuries"] = injuries

    by_id = {x.get("athlete_id"): x for x in injuries if x.get("athlete_id")}
    by_name = {x.get("name", "").lower(): x for x in injuries if x.get("name")}
    for qb in result["qbs"]:
        hit = by_id.get(qb.get("athlete_id")) or by_name.get(qb.get("name", "").lower())
        qb["injury_status"] = _safe((hit or {}).get("status"), "No listed injury")
        qb["injury_detail"] = _safe((hit or {}).get("detail"))
    return result


def _qb_table(ctx: dict):
    rows = []
    for qb in ctx.get("qbs", [])[:4]:
        rows.append({
            "Depth": f"QB{int(qb.get('rank', len(rows)+1))}",
            "Quarterback": qb.get("name", "Unknown"),
            "Injury listing": qb.get("injury_status", "No listed injury"),
            "Source": qb.get("source", "—"),
        })
    return pd.DataFrame(rows)


def _injury_table(ctx: dict):
    rows = []
    for item in ctx.get("injuries", [])[:10]:
        rows.append({
            "Player": item.get("name", "Unknown"),
            "Pos": item.get("position", "—"),
            "Status": item.get("status", "Unspecified"),
            "Detail": item.get("detail", ""),
        })
    return pd.DataFrame(rows)


def _render_team_step2(ctx: dict, preseason: bool):
    st.markdown(f"#### {escape(_safe(ctx.get('team'), ctx.get('abbr')))}")
    qbs = ctx.get("qbs", [])
    c1, c2, c3 = st.columns(3)
    c1.metric("QB depth", ctx.get("depth_state", "CHECK"))
    c2.metric("Listed injuries", len(ctx.get("injuries", [])))
    c3.metric("Rotation plan", "UNVERIFIED" if preseason else "N/A")

    qbt = _qb_table(ctx)
    if qbt.empty:
        st.warning("⚠️ No verified QB depth order was returned. Downstream Moneyline modeling remains locked.")
    else:
        st.dataframe(qbt, use_container_width=True, hide_index=True)
        if ctx.get("depth_state") == "ROSTER FALLBACK":
            st.warning("⚠️ QB names came from the current roster because the depth-chart feed was unavailable. Roster order is NOT treated as a verified depth rank.")

    if preseason:
        st.warning(
            "⚠️ PRESEASON ROTATION UNVERIFIED • ESPN depth order does not establish how many drives/quarters each QB will play. "
            "No win-probability model may use QB1 as a full-game starter assumption until an explicit coach/game-plan source is added."
        )

    with st.expander(f"🩺 {ctx.get('team', ctx.get('abbr'))} current injury report", expanded=False):
        it = _injury_table(ctx)
        if ctx.get("injury_state") != "VERIFIED":
            st.warning("Current ESPN injury feed could not be verified. Availability remains fail-closed.")
        elif it.empty:
            st.success("✅ ESPN injury feed verified; no listed injuries were returned for this team.")
        else:
            st.dataframe(it, use_container_width=True, hide_index=True)
    st.divider()


def render_nfl_moneyline_hub():
    # Reuse Step-1 visual primitives but render a V2-aware lock table so the page
    # never contradicts itself by showing Step 2 as both active and 'NEXT'.
    st.markdown(prior._CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="knfl-ml-shell">'
        '<div class="knfl-ml-title">💰 NFL Moneyline <span>Command Center</span></div>'
        '<div class="knfl-ml-sub">Step 1 verified pregame foundation + Step 2 current QB depth and injury verification. Preseason rotation/rest intent remains fail-closed until an explicit game-plan source exists. No sportsbook or model math is active.</div>'
        '<div class="knfl-ml-chips">'
        '<span class="knfl-ml-chip">STEP 2</span><span class="knfl-ml-chip">QB DEPTH</span>'
        '<span class="knfl-ml-chip">INJURY FEED</span><span class="knfl-ml-chip">ROTATION FAIL-CLOSED</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(ET).date()

    selected = st.date_input(
        "📅 Moneyline slate date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_moneyline_v2_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("💰 Verifying NFL Moneyline Step 1 foundation…"):
        schedule, diag = foundation.load_nfl_slate(day_str)
        pregame, excluded = prior._pregame_partition(schedule, day_str, now_et=now_et)

    phases = sorted({prior._safe(x) for x in schedule.get("season_type", pd.Series(dtype=str)).tolist() if prior._safe(x)}) if not schedule.empty else []
    preseason = bool(phases and all(x == "Preseason" for x in phases))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "DATA ONLY")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if not diag.get("request_ok"):
        st.error("NFL schedule verification failed. Moneyline production remains locked and no games are fabricated.")
        return
    if schedule.empty:
        st.info("No verified NFL games were returned for this ET date. Moneyline remains locked.")
        return

    st.success(f"✅ STEP 1A PASSED • verified NFL slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ STEP 1B PASSED • {len(pregame)} game(s) remain provider-safe and before scheduled kickoff.")
    else:
        st.info("ℹ️ No games remain pregame-eligible. Step 2 will not fetch team context for locked games.")

    if preseason:
        st.warning("⚠️ PRESEASON SLATE • depth chart and injury status can be verified, but game rotation/rest intent is a separate required input.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame Moneyline", expanded=False):
            cols = [c for c in ["away_team", "home_team", "tip_et", "state", "status", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    st.markdown("### 🧩 Pregame Moneyline Foundation")
    if pregame.empty:
        st.markdown('<div class="knfl-ml-empty">No pregame-eligible NFL game is available for this date.</div>', unsafe_allow_html=True)
    else:
        cards = "".join(prior._game_foundation_card(row) for _, row in pregame.iterrows())
        st.markdown(f'<div class="knfl-ml-grid">{cards}</div>', unsafe_allow_html=True)

    # Step 2 only requests context for teams in games that passed Step 1.
    injury_payload, idiag = _league_injuries_payload() if len(pregame) else ({}, {"ok": False, "http": None, "error": "no eligible games"})
    injury_map = _parse_injuries(injury_payload) if idiag.get("ok") else {}

    team_contexts = {}
    for _, game in pregame.iterrows():
        for side in ("away", "home"):
            abbr = _safe(game.get(f"{side}_abbr")).upper()
            if abbr and abbr not in team_contexts:
                team_contexts[abbr] = _team_context(
                    abbr,
                    _safe(game.get(f"{side}_team"), abbr),
                    injury_map,
                    bool(idiag.get("ok")),
                )

    expected_teams = 2 * len(pregame)
    unique_expected = len({str(x) for x in list(pregame.get("away_abbr", [])) + list(pregame.get("home_abbr", [])) if str(x)}) if len(pregame) else 0
    depth_verified = sum(1 for x in team_contexts.values() if x.get("depth_state") == "VERIFIED")
    injury_verified = sum(1 for x in team_contexts.values() if x.get("injury_state") == "VERIFIED")
    rotation_verified = 0 if preseason else unique_expected

    st.markdown("### 🧠 Step 2 — QB Depth + Current Availability")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Teams checked", f"{len(team_contexts)}/{unique_expected}")
    s2.metric("Depth verified", f"{depth_verified}/{unique_expected}")
    s3.metric("Injury feeds", f"{injury_verified}/{unique_expected}")
    s4.metric("Rotation plans", f"{rotation_verified}/{unique_expected}" if preseason else "N/A")

    if unique_expected and depth_verified == unique_expected:
        st.success("✅ STEP 2A PASSED • current ESPN QB depth order verified for every pregame team.")
    else:
        st.warning("⚠️ STEP 2A CHECK • at least one team lacks a verified QB depth chart. Roster fallback is display-only and cannot unlock the model.")

    if unique_expected and injury_verified == unique_expected:
        st.success("✅ STEP 2B PASSED • current ESPN injury feed verified for every pregame team.")
    else:
        st.warning("⚠️ STEP 2B CHECK • current injury verification is incomplete. Availability remains fail-closed.")

    if preseason:
        st.warning(
            "🔒 STEP 2C LOCKED • preseason QB rotation / starter-rest intent is not inferable from a depth chart. "
            "A later game-plan/coach-news verification layer must clear this before any Moneyline win probability is enabled."
        )

    for _, game in pregame.iterrows():
        st.markdown(f"### {escape(_safe(game.get('away_team'), 'Away'))} @ {escape(_safe(game.get('home_team'), 'Home'))}")
        left, right = st.columns(2)
        with left:
            _render_team_step2(team_contexts.get(_safe(game.get("away_abbr")).upper(), {}), preseason)
        with right:
            _render_team_step2(team_contexts.get(_safe(game.get("home_abbr")).upper(), {}), preseason)

    depth_ready = bool(unique_expected and depth_verified == unique_expected)
    injuries_ready = bool(unique_expected and injury_verified == unique_expected)
    rotation_ready = bool((not preseason) and unique_expected)  # preseason intentionally locked

    st.markdown("### 🔒 Moneyline production locks")
    locks = pd.DataFrame([
        {"Layer": "Verified NFL slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Season-phase guard", "State": "READY" if phases else "CHECK"},
        {"Layer": "QB / depth-chart verification", "State": "READY" if depth_ready else "CHECK"},
        {"Layer": "Current injuries / availability", "State": "READY" if injuries_ready else "CHECK"},
        {"Layer": "Preseason rotation / starter-rest intent", "State": "LOCKED — GAME-PLAN SOURCE REQUIRED" if preseason else "N/A"},
        {"Layer": "Sportsbook Moneyline prices", "State": "LOCKED"},
        {"Layer": "Team-strength win model", "State": "LOCKED"},
        {"Layer": "Monte Carlo", "State": "LOCKED"},
        {"Layer": "No-vig edge / EV / final grading", "State": "LOCKED"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)

    st.session_state["nfl_moneyline_v2_day"] = day_str
    st.session_state["nfl_moneyline_v2_schedule"] = schedule.to_dict("records")
    st.session_state["nfl_moneyline_v2_pregame"] = pregame.to_dict("records") if not pregame.empty else []
    st.session_state["nfl_moneyline_v2_team_context"] = team_contexts
    st.session_state["nfl_moneyline_v2_depth_ready"] = depth_ready
    st.session_state["nfl_moneyline_v2_injuries_ready"] = injuries_ready
    st.session_state["nfl_moneyline_v2_rotation_ready"] = rotation_ready
    st.session_state["nfl_moneyline_v2_model_ready"] = bool(depth_ready and injuries_ready and rotation_ready)

    st.caption(
        "Step 2 performs zero sportsbook requests, zero projection math and zero simulations. "
        "Depth order and injury status are descriptive verification inputs only."
    )


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
