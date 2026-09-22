"""WNBA Spread V1.6.6 — Top-5 Card Step 5: injury + availability context.

Presentation-only wrapper over the verified V1.6.5 Step-4 card layer. Step 5
adds the current ESPN WNBA injury snapshot plus each team's last verified
starting five from its most recent completed game before the selected slate.
This is descriptive availability context only. It never feeds the protected
V1.6.1 spread model, sportsbook market, analytical probability, 5,000,000
Monte Carlo, convergence, qualification, selected side, edge/EV, Pick Strength
or card ranking.

Important temporal rule: ESPN's injury endpoint is a current snapshot and has no
historical-date filter. When a non-current slate is selected, the card labels
that limitation explicitly instead of pretending the injury report is an
historical reconstruction. Last-game starter context is date-safe and only uses
completed games strictly before the selected slate.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_context_v26 as context
import wnba_players_v25 as players
import wnba_schedule_v24 as schedule24
import wnba_spread_hub_v163 as step3
import wnba_spread_hub_v165 as previous

base = step3.base
MODEL_VERSION = "WNBA SPREAD V1.6.6 • TOP-5 CARD STEP 5 INJURY + AVAILABILITY"
ESPN_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries"
ESPN_SUMMARY = players.ESPN_SUMMARY


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _compact_html(fragment: str) -> str:
    return "".join(line.strip() for line in str(fragment or "").splitlines())


def _text(value) -> str:
    if isinstance(value, dict):
        for key in ("displayName", "name", "description", "shortName", "type"):
            if value.get(key) not in (None, ""):
                return str(value.get(key))
        return ""
    return "" if value is None else str(value)


def _date_text(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert("America/New_York").strftime("%b %d")
    except Exception:
        try:
            return pd.to_datetime(value).strftime("%b %d")
        except Exception:
            return str(value)[:20]


def _truth(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "starter"}


def _status_bucket(value: str) -> tuple[str, str, int]:
    s = str(value or "UNKNOWN").strip().upper().replace("_", " ")
    if any(x in s for x in ("OUT", "INACTIVE", "SUSPENDED", "INJURED RESERVE")):
        return "OUT", "bad", 5
    if "DOUBT" in s:
        return "DOUBTFUL", "bad", 4
    if any(x in s for x in ("QUESTION", "GAME TIME", "GAME-TIME")):
        return "QUESTIONABLE", "warn", 3
    if any(x in s for x in ("DAY TO DAY", "DAY-TO-DAY", "PROBABLE", "LIMITED")):
        return s or "WATCH", "mid", 2
    if any(x in s for x in ("AVAILABLE", "ACTIVE", "CLEARED")):
        return s, "good", 0
    return s if s else "UNKNOWN", "warn", 1


def _flatten_injury_entries(payload: dict) -> list[dict]:
    """Support both flat WNBA rows and grouped team->injuries variants."""
    out = []
    for item in (payload or {}).get("injuries", []) or []:
        if not isinstance(item, dict):
            continue
        nested = item.get("injuries")
        if isinstance(nested, list):
            team = item.get("team") or {}
            for child in nested:
                if not isinstance(child, dict):
                    continue
                merged = dict(child)
                if not merged.get("team"):
                    merged["team"] = team
                out.append(merged)
        else:
            out.append(item)
    return out


@st.cache_data(ttl=300, show_spinner=False, max_entries=4)
def _league_injury_snapshot() -> tuple[pd.DataFrame, dict]:
    try:
        payload, meta = schedule24._request_json(
            "ESPN WNBA injury snapshot",
            ESPN_INJURIES,
            timeout=7,
            attempts=2,
        )
    except Exception as exc:
        return pd.DataFrame(), {"state": "UNAVAILABLE", "error": str(exc)[:180]}

    if not isinstance(payload, dict):
        return pd.DataFrame(), {
            "state": "UNAVAILABLE",
            "error": str((meta or {}).get("error") or "ESPN injury endpoint returned no JSON")[:180],
        }

    rows = []
    for entry in _flatten_injury_entries(payload):
        team = entry.get("team") or {}
        athlete = entry.get("athlete") or {}
        injury = entry.get("injury") or {}
        try:
            official_team_id = int(players._team_id(team) or 0)
        except Exception:
            official_team_id = 0
        if not official_team_id:
            continue

        pos = athlete.get("position") or {}
        status_raw = _text(entry.get("status"))
        status, status_class, severity = _status_bucket(status_raw)
        rows.append({
            "team_id": official_team_id,
            "team_name": str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""),
            "team_abbr": str(team.get("abbreviation") or ""),
            "athlete_id": str(athlete.get("id") or ""),
            "athlete_name": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
            "position": str(pos.get("abbreviation") or pos.get("name") or ""),
            "status": status,
            "status_class": status_class,
            "severity": severity,
            "reported_date": str(entry.get("date") or ""),
            "injury_type": _text(injury.get("type")),
            "injury_side": _text(injury.get("location")),
            "return_date": str(entry.get("returnDate") or ""),
            "short_comment": str(entry.get("shortComment") or ""),
            "long_comment": str(entry.get("longComment") or ""),
        })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["severity", "athlete_name"], ascending=[False, True]).reset_index(drop=True)
    now_et = pd.Timestamp.now(tz="America/New_York")
    return frame, {
        "state": "READY",
        "source": "ESPN WNBA current injury feed",
        "fetched_et": now_et.strftime("%Y-%m-%d %I:%M %p ET"),
        "rows": int(len(frame)),
    }


def _starter_rows_from_summary(payload: dict, team_id: int) -> list[dict]:
    rows = []
    for block in (payload or {}).get("boxscore", {}).get("players", []) or []:
        team = block.get("team") or {}
        try:
            tid = int(players._team_id(team) or 0)
        except Exception:
            tid = 0
        if tid != int(team_id):
            continue
        seen = set()
        for group in block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                athlete = item.get("athlete") or {}
                if not athlete or bool(item.get("didNotPlay")):
                    continue
                if not (_truth(item.get("starter")) or _truth(item.get("isStarter")) or _truth(athlete.get("starter"))):
                    continue
                aid = str(athlete.get("id") or "")
                name = str(athlete.get("displayName") or athlete.get("fullName") or "Player")
                key = aid or _norm(name)
                if key in seen:
                    continue
                seen.add(key)
                pos = athlete.get("position") or {}
                rows.append({
                    "athlete_id": aid,
                    "athlete_name": name,
                    "position": str(pos.get("abbreviation") or pos.get("name") or ""),
                })
            if athletes:
                break
        break
    return rows


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _last_verified_starters(day_str: str, team_id: int) -> dict:
    day = pd.to_datetime(day_str).normalize()
    season = int(day.year)
    try:
        games = context._season_team_games(season)
    except Exception as exc:
        return {"state": "UNAVAILABLE", "error": str(exc)[:160], "starters": []}
    if games is None or games.empty:
        return {"state": "UNAVAILABLE", "error": "no completed team games available", "starters": []}

    dates = pd.to_datetime(games.get("GAME_DATE"), errors="coerce")
    ids = pd.to_numeric(games.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
    part = games.loc[(dates < day) & ids.eq(int(team_id))].copy()
    if part.empty:
        return {"state": "NO_PRIOR_GAME", "starters": []}
    part["GAME_DATE"] = pd.to_datetime(part["GAME_DATE"], errors="coerce")
    game = part.sort_values("GAME_DATE", ascending=False).iloc[0]
    gid = str(game.get("GAME_ID") or "")
    if not gid:
        return {"state": "UNAVAILABLE", "error": "latest completed game ID missing", "starters": []}

    try:
        payload, meta = schedule24._request_json(
            "ESPN WNBA last-start lineup",
            ESPN_SUMMARY,
            params={"event": gid},
            timeout=7,
            attempts=2,
        )
    except Exception as exc:
        return {"state": "UNAVAILABLE", "error": str(exc)[:160], "starters": []}
    if not isinstance(payload, dict):
        return {"state": "UNAVAILABLE", "error": str((meta or {}).get("error") or "summary unavailable")[:160], "starters": []}

    starters = _starter_rows_from_summary(payload, int(team_id))
    opponent = str(game.get("OPP_NAME") or "Opponent")
    dt = game.get("GAME_DATE")
    date_text = dt.strftime("%b %d") if pd.notna(dt) else "—"
    return {
        "state": "READY" if starters else "NO_STARTER_FLAGS",
        "game_id": gid,
        "game_date": date_text,
        "opponent": opponent,
        "starters": starters,
        "source": "ESPN WNBA most recent completed-game box score",
    }


def _injuries_for_team(frame: pd.DataFrame, team_id: int) -> pd.DataFrame:
    if frame is None or frame.empty or "team_id" not in frame.columns:
        return pd.DataFrame(columns=list(frame.columns) if isinstance(frame, pd.DataFrame) else [])
    ids = pd.to_numeric(frame["team_id"], errors="coerce").fillna(0).astype(int)
    return frame.loc[ids.eq(int(team_id))].copy().reset_index(drop=True)


def _starter_keys(starters: dict) -> tuple[set[str], set[str]]:
    ids, names = set(), set()
    for row in starters.get("starters", []) or []:
        aid = str(row.get("athlete_id") or "")
        name = _norm(row.get("athlete_name"))
        if aid:
            ids.add(aid)
        if name:
            names.add(name)
    return ids, names


def _is_last_starter(injury, starter_info: dict) -> bool:
    ids, names = _starter_keys(starter_info)
    aid = str(injury.get("athlete_id") or "")
    name = _norm(injury.get("athlete_name"))
    return bool((aid and aid in ids) or (name and name in names))


def _team_availability(team_name: str, team_id: int, role: str, injuries: pd.DataFrame, starters: dict) -> str:
    team = escape(str(team_name or "Team"))
    role_text = escape(str(role or "TEAM"))
    logo = escape(step3.prior._logo(int(team_id)), quote=True)
    img = f'<img src="{logo}" alt="{team} logo">' if logo else "🏀"

    injury_rows = []
    out_n = questionable_n = watch_n = starter_flag_n = 0
    if injuries is not None and not injuries.empty:
        records = injuries.to_dict("records")
        records.sort(key=lambda x: (int(_is_last_starter(x, starters)), int(x.get("severity") or 0)), reverse=True)
        for item in records:
            status = str(item.get("status") or "UNKNOWN")
            status_class = str(item.get("status_class") or "warn")
            severity = int(item.get("severity") or 0)
            if severity >= 4:
                out_n += 1
            elif severity == 3:
                questionable_n += 1
            elif severity == 2:
                watch_n += 1
            starter_flag = _is_last_starter(item, starters)
            starter_flag_n += int(starter_flag)

            name = escape(str(item.get("athlete_name") or "Player"))
            pos = escape(str(item.get("position") or ""))
            injury_type = str(item.get("injury_type") or "").strip()
            injury_side = str(item.get("injury_side") or "").strip()
            issue = " • ".join(x for x in [injury_side, injury_type] if x) or "Injury detail not specified"
            ret = _date_text(item.get("return_date"))
            reported = _date_text(item.get("reported_date"))
            comment = str(item.get("short_comment") or item.get("long_comment") or "").strip()
            if len(comment) > 180:
                comment = comment[:177].rstrip() + "…"
            meta = f"{escape(issue)} • reported {escape(reported)}"
            if ret != "—":
                meta += f" • est. return {escape(ret)}"
            starter_chip = '<span class="ks-spread166-mini starter">LAST STARTER</span>' if starter_flag else ""
            comment_html = f'<div class="ks-spread166-comment">{escape(comment)}</div>' if comment else ""
            injury_rows.append(f"""
              <div class="ks-spread166-injury">
                <div class="ks-spread166-injurytop"><span><b>{name}</b>{f'<small>{pos}</small>' if pos else ''}</span><span class="ks-spread166-mini {status_class}">{escape(status)}</span>{starter_chip}</div>
                <div class="ks-spread166-injurymeta">{meta}</div>{comment_html}
              </div>
            """)

    total = int(len(injuries)) if injuries is not None else 0
    if starter_flag_n and out_n:
        team_state, team_class = "STARTER FLAG", "bad"
    elif out_n:
        team_state, team_class = "ABSENCE FLAGS", "bad"
    elif questionable_n:
        team_state, team_class = "QUESTIONABLE", "warn"
    elif watch_n:
        team_state, team_class = "WATCH", "mid"
    elif total:
        team_state, team_class = "REPORTED", "mid"
    else:
        team_state, team_class = "NO ESPN-REPORTED INJURIES", "good"

    starter_list = starters.get("starters", []) or []
    if starter_list:
        starter_text = " • ".join(
            f"{str(x.get('athlete_name') or 'Player')}{(' (' + str(x.get('position')) + ')') if x.get('position') else ''}"
            for x in starter_list
        )
        starter_scope = f"{starters.get('game_date','—')} vs {starters.get('opponent','Opponent')}"
        starter_html = f"""
          <div class="ks-spread166-starters"><small>LAST VERIFIED STARTERS • {escape(starter_scope)}</small><strong>{escape(starter_text)}</strong></div>
        """
    else:
        state = str(starters.get("state") or "UNAVAILABLE").upper()
        starter_html = f"""
          <div class="ks-spread166-starters"><small>LAST VERIFIED STARTERS</small><strong>Starter flags unavailable ({escape(state.replace('_',' ').title())})</strong></div>
        """

    injury_html = "".join(injury_rows) if injury_rows else '<div class="ks-spread166-clear">No players from this team are listed on ESPN\'s current WNBA injury feed.</div>'

    return f"""
      <div class="ks-spread166-team">
        <div class="ks-spread166-teamhead">
          <span class="ks-spread166-logo">{img}</span>
          <span><b>{team}</b><small>{role_text}</small></span>
          <span class="ks-spread166-chip {team_class}">{escape(team_state)}</span>
        </div>
        <div class="ks-spread166-summary">
          <div><small>ACTIVE REPORT</small><strong>{total}</strong></div>
          <div><small>OUT / DOUBTFUL</small><strong>{out_n}</strong></div>
          <div><small>QUESTIONABLE</small><strong>{questionable_n}</strong></div>
          <div><small>LAST-STARTER FLAGS</small><strong>{starter_flag_n}</strong></div>
        </div>
        {starter_html}
        <div class="ks-spread166-list">{injury_html}</div>
      </div>
    """


def _availability_block(day_str: str, row) -> str:
    try:
        selected_is_home = step3.prior._is_home(row)
        away_id, home_id, identity_source = step3.prior._resolved_team_ids(str(day_str), row)
        if not away_id or not home_id:
            raise ValueError("team IDs could not be resolved from the verified daily schedule")

        away_name = str(row.get("away_team") or "Away")
        home_name = str(row.get("home_team") or "Home")
        selected_id = home_id if selected_is_home else away_id
        opponent_id = away_id if selected_is_home else home_id
        selected_name = str(row.get("best_side") or (home_name if selected_is_home else away_name))
        opponent_name = away_name if selected_is_home else home_name

        injuries, provider = _league_injury_snapshot()
        if str((provider or {}).get("state") or "").upper() != "READY":
            raise RuntimeError(str((provider or {}).get("error") or "ESPN WNBA injury source unavailable"))

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_sel = pool.submit(_last_verified_starters, str(day_str), int(selected_id))
            f_opp = pool.submit(_last_verified_starters, str(day_str), int(opponent_id))
            selected_starters = f_sel.result()
            opponent_starters = f_opp.result()

        selected_injuries = _injuries_for_team(injuries, int(selected_id))
        opponent_injuries = _injuries_for_team(injuries, int(opponent_id))
        fetched = str((provider or {}).get("fetched_et") or "—")
        source = str((provider or {}).get("source") or "ESPN WNBA current injury feed")

        slate_day = pd.to_datetime(day_str).date()
        today_et = pd.Timestamp.now(tz="America/New_York").date()
        current_slate = slate_day == today_et
        scope_badge = "CURRENT SLATE SNAPSHOT" if current_slate else "CURRENT SNAPSHOT • NON-HISTORICAL"
        scope_class = "good" if current_slate else "warn"
    except Exception as exc:
        return _compact_html(f"""
        <div class="ks-spread166-wrap">
          <div class="ks-spread166-head"><span>STEP 5 • INJURY + AVAILABILITY CONTEXT</span><span class="ks-spread166-chip warn">SOURCE CHECK</span></div>
          <div class="ks-spread166-empty">Current availability context is temporarily unavailable. Steps 1–4 and the verified Spread model remain unchanged.</div>
          <div class="ks-spread166-note">Diagnostic • {escape(str(exc)[:180])}</div>
        </div>
        """)

    historical_note = "" if current_slate else (
        '<div class="ks-spread166-warning">ESPN\'s injury endpoint has no historical-date filter. The injury list below is the current snapshot, not a reconstruction of the selected historical/future slate. Last verified starters remain date-safe.</div>'
    )

    return _compact_html(f"""
    <div class="ks-spread166-wrap">
      <div class="ks-spread166-head"><span>STEP 5 • INJURY + AVAILABILITY CONTEXT</span><span class="ks-spread166-chip {scope_class}">{scope_badge}</span></div>
      <div class="ks-spread166-scope">Injury snapshot fetched {escape(fetched)} • last-start lineups use completed games strictly before this slate</div>
      {historical_note}
      <div class="ks-spread166-teams">
        {_team_availability(selected_name, selected_id, 'SELECTED SPREAD SIDE', selected_injuries, selected_starters)}
        {_team_availability(opponent_name, opponent_id, 'OPPONENT', opponent_injuries, opponent_starters)}
      </div>
      <div class="ks-spread166-note">Source • {escape(source)} + ESPN WNBA most recent completed-game box scores • identity • {escape(str(identity_source))} • “Last verified starters” means the most recent confirmed starting five before this slate, NOT a projected lineup. Injury/availability context is descriptive only • NOT FED INTO projected margin, 5M Monte Carlo, market probability, edge, EV, qualification, selected side, Pick Strength or card ranking.</div>
    </div>
    """)


def _form_plus_step5(day_str: str, row) -> str:
    return previous._form_plus_step4(day_str, row) + _availability_block(day_str, row)


def _install_step5() -> None:
    previous._install_step4()
    step3._form_block = _form_plus_step5


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_step5()
    st.markdown(
        """
<style>
.ks-spread166-wrap{background:#0a1723;border:1px solid #36546d;border-radius:15px;padding:12px;margin-top:14px}
.ks-spread166-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#9ed9ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.ks-spread166-scope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}.ks-spread166-teams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.ks-spread166-team{background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}.ks-spread166-teamhead{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:7px;margin-bottom:9px}
.ks-spread166-teamhead b{display:block;color:#f5fbff;font-size:.73rem;line-height:1.15}.ks-spread166-teamhead small{display:block;color:#7890a5;font-size:.44rem;font-weight:900;margin-top:3px;letter-spacing:.03em}
.ks-spread166-logo{width:32px;height:32px;display:flex;align-items:center;justify-content:center}.ks-spread166-logo img{max-width:32px;max-height:32px;object-fit:contain}
.ks-spread166-chip,.ks-spread166-mini{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.43rem;font-weight:950;white-space:nowrap}.ks-spread166-chip.good,.ks-spread166-mini.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread166-chip.mid,.ks-spread166-mini.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread166-chip.warn,.ks-spread166-mini.warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread166-chip.bad,.ks-spread166-mini.bad{border-color:#7a3941;background:#35171b;color:#ffadb5}.ks-spread166-mini.starter{border-color:#486884;background:#10253a;color:#a9dcff}
.ks-spread166-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread166-summary div{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px}.ks-spread166-summary small,.ks-spread166-starters small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread166-summary strong{display:block;color:#f6fbff;font-size:.69rem;margin-top:3px}
.ks-spread166-starters{margin-top:7px;background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px}.ks-spread166-starters strong{display:block;color:#d9e8f3;font-size:.60rem;line-height:1.45;margin-top:4px}
.ks-spread166-list{margin-top:7px}.ks-spread166-injury{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px;margin-top:6px}.ks-spread166-injurytop{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.ks-spread166-injurytop b{color:#f5fbff;font-size:.66rem}.ks-spread166-injurytop small{color:#7f95a7;font-size:.47rem;margin-left:5px}.ks-spread166-injurymeta{color:#9cb0bf;font-size:.50rem;line-height:1.4;margin-top:5px}.ks-spread166-comment{color:#c2d1dc;font-size:.52rem;line-height:1.45;margin-top:4px}.ks-spread166-clear{color:#9eddbf;font-size:.58rem;line-height:1.45;background:#09231d;border:1px solid #245d49;border-radius:9px;padding:8px}
.ks-spread166-warning{color:#ffd79b;font-size:.54rem;line-height:1.45;background:#2b2114;border:1px solid #77572c;border-radius:9px;padding:8px;margin-bottom:9px}.ks-spread166-note{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread166-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread166-head{align-items:flex-start}.ks-spread166-teams{grid-template-columns:1fr}.ks-spread166-chip{font-size:.41rem}.ks-spread166-teamhead{grid-template-columns:34px 1fr}.ks-spread166-teamhead>.ks-spread166-chip{grid-column:2;justify-self:start}}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "🎨 Spread V1.6.6 • Top-5 Card Steps 1–5 ACTIVE • verified model snapshot + official WNBA H2H + "
        "team form + recent matchup analytics + current injury/last-start availability context • presentation-only"
    )
    return step3.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(previous, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
