"""WNBA Rebounds + Assists V1.0 — Step 1 verified slate + player identity.

New isolated WNBA Rebounds + Assists (RA) page. Step 1 only:
- verified selected-date WNBA schedule;
- current-slate player pool from the existing WNBA player-data layer;
- ESPN player identity/headshot resolution with team-logo fallback;
- team/opponent identity and logos;
- descriptive season/L10/L5 REB+AST baselines for identity verification.

This module does NOT fetch a Rebounds+Assists sportsbook market, create an RA
projection, run Monte Carlo, calculate fair odds/EV, qualify picks, rank players
or publish a Top 5. Existing Points, Rebounds, Assists, PRA, Spread, Moneyline,
Game Total, Daily Picks, MLB and NFL routes are untouched.
"""
from __future__ import annotations

from html import escape
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule24
import wnba_schedule_v25 as schedule25

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V1.0 • STEP 1 VERIFIED SLATE + PLAYER IDENTITY"
ET = ZoneInfo("America/New_York")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _logo(team_id) -> str:
    try:
        return str(schedule25.logo_url(int(float(team_id))) or "")
    except Exception:
        return ""


def _espn_headshot(espn_player_id) -> str:
    pid = _safe_int(espn_player_id)
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png" if pid else ""


def _photo_html(espn_player_id, team_id, player_name, css_class="kra-photo") -> str:
    headshot = escape(_espn_headshot(espn_player_id), quote=True)
    fallback = escape(_logo(team_id), quote=True)
    alt = escape(str(player_name or "WNBA player"), quote=True)
    if headshot:
        onerror = f"this.onerror=null;this.src='{fallback}';" if fallback else "this.style.display='none';"
        return f'<img class="{css_class}" src="{headshot}" alt="{alt}" onerror="{onerror}">'
    if fallback:
        return f'<img class="{css_class} fallback" src="{fallback}" alt="{alt}">'
    return '<div class="kra-placeholder">🏀</div>'


def _team_meta(schedule: pd.DataFrame) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if schedule is None or schedule.empty:
        return out
    for _, row in schedule.iterrows():
        for side in ("away", "home"):
            tid = _safe_int(row.get(f"{side}_team_id"))
            if not tid:
                continue
            out[tid] = {
                "team_id": tid,
                "name": str(row.get(f"{side}_team") or "Team"),
                "abbr": str(row.get(f"{side}_tricode") or ""),
            }
    return out


def _opponent_map(schedule: pd.DataFrame) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if schedule is None or schedule.empty:
        return out
    for _, row in schedule.iterrows():
        away_id = _safe_int(row.get("away_team_id"))
        home_id = _safe_int(row.get("home_team_id"))
        away_name = str(row.get("away_team") or "Away")
        home_name = str(row.get("home_team") or "Home")
        away_abbr = str(row.get("away_tricode") or "")
        home_abbr = str(row.get("home_tricode") or "")
        game_id = str(row.get("game_id") or "")
        if away_id and home_id:
            out[away_id] = {
                "opponent_team_id": home_id,
                "opponent": home_name,
                "opponent_abbr": home_abbr,
                "game_id": game_id,
                "home_away": "AWAY",
            }
            out[home_id] = {
                "opponent_team_id": away_id,
                "opponent": away_name,
                "opponent_abbr": away_abbr,
                "game_id": game_id,
                "home_away": "HOME",
            }
    return out


@st.cache_data(ttl=600, show_spinner=False, max_entries=16)
def _espn_identity_map(day_str: str) -> tuple[dict[tuple[int, str], int], dict]:
    schedule = schedule24.schedule_for_date(str(day_str))
    meta = _team_meta(schedule)
    mapping: dict[tuple[int, str], int] = {}
    roster_rows = 0
    connected = 0

    for tid, team in meta.items():
        try:
            roster = players._espn_roster(
                int(tid),
                str(team.get("name") or ""),
                str(team.get("abbr") or ""),
            )
        except Exception:
            roster = pd.DataFrame()
        if roster is None or roster.empty:
            continue
        connected += 1
        roster_rows += int(len(roster))
        for _, row in roster.iterrows():
            name_key = _norm(row.get("PLAYER_NAME"))
            pid = _safe_int(row.get("PLAYER_ID"))
            if name_key and pid:
                mapping[(int(tid), name_key)] = pid

    return mapping, {
        "teams": len(meta),
        "rosters_connected": connected,
        "roster_rows": roster_rows,
        "identity_rows": len(mapping),
    }


@st.cache_data(ttl=600, show_spinner=False, max_entries=16)
def _step1_pool(day_str: str) -> tuple[pd.DataFrame, dict]:
    schedule = schedule24.schedule_for_date(str(day_str))
    if schedule is None or schedule.empty:
        return pd.DataFrame(), {
            "state": "NO_GAMES",
            "selected_date": str(day_str),
            "games": 0,
            "teams": 0,
            "players": 0,
            "photo_matches": 0,
        }

    try:
        pool, diag = players._build_selected_player_pool(str(day_str))
    except Exception as exc:
        return pd.DataFrame(), {
            "state": "PLAYER_SOURCE_CHECK",
            "selected_date": str(day_str),
            "games": int(len(schedule)),
            "teams": len(_team_meta(schedule)),
            "players": 0,
            "photo_matches": 0,
            "error": str(exc)[:180],
        }

    if pool is None or pool.empty:
        return pd.DataFrame(), {
            "state": "PLAYER_SOURCE_CHECK",
            "selected_date": str(day_str),
            "games": int(len(schedule)),
            "teams": len(_team_meta(schedule)),
            "players": 0,
            "photo_matches": 0,
            "source": str((diag or {}).get("source") or "none"),
        }

    work = pool.copy()
    for col in ("REB", "AST", "L10_REB", "L10_AST", "L5_REB", "L5_AST", "MIN", "GP"):
        work[col] = pd.to_numeric(work.get(col), errors="coerce")

    work["RA"] = work["REB"] + work["AST"]
    work["L10_RA"] = work["L10_REB"] + work["L10_AST"]
    work["L5_RA"] = work["L5_REB"] + work["L5_AST"]

    opp = _opponent_map(schedule)
    work["opponent_team_id"] = work["TEAM_ID"].apply(
        lambda x: (opp.get(_safe_int(x)) or {}).get("opponent_team_id", 0)
    )
    work["opponent"] = work["TEAM_ID"].apply(
        lambda x: (opp.get(_safe_int(x)) or {}).get("opponent", "Opponent")
    )
    work["opponent_abbr"] = work["TEAM_ID"].apply(
        lambda x: (opp.get(_safe_int(x)) or {}).get("opponent_abbr", "")
    )
    work["game_id"] = work["TEAM_ID"].apply(
        lambda x: (opp.get(_safe_int(x)) or {}).get("game_id", "")
    )
    work["HOME_AWAY"] = work["TEAM_ID"].apply(
        lambda x: (opp.get(_safe_int(x)) or {}).get("home_away", "")
    )

    identity, identity_diag = _espn_identity_map(str(day_str))
    work["ESPN_PLAYER_ID"] = work.apply(
        lambda row: identity.get(
            (_safe_int(row.get("TEAM_ID")), _norm(row.get("PLAYER_NAME"))),
            0,
        ),
        axis=1,
    )
    work["PHOTO_URL"] = work["ESPN_PLAYER_ID"].map(_espn_headshot)

    # Keep only current-slate teams and stable player identities. Existing player
    # source already performs current-roster gating; this is only a final display guard.
    slate_team_ids = set(_team_meta(schedule))
    work = work.loc[
        work["TEAM_ID"].apply(_safe_int).isin(slate_team_ids)
        & work["PLAYER_NAME"].astype(str).str.strip().ne("")
    ].copy()

    work["_MIN_SORT"] = pd.to_numeric(work["MIN"], errors="coerce").fillna(-1.0)
    work = (
        work.sort_values(
            ["TEAM_NAME", "_MIN_SORT", "PLAYER_NAME"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop(columns=["_MIN_SORT"], errors="ignore")
        .reset_index(drop=True)
    )

    return work, {
        "state": "VERIFIED",
        "selected_date": str(day_str),
        "games": int(len(schedule)),
        "teams": len(slate_team_ids),
        "players": int(len(work)),
        "photo_matches": int((pd.to_numeric(work["ESPN_PLAYER_ID"], errors="coerce").fillna(0) > 0).sum()),
        "player_source": str((diag or {}).get("source") or "WNBA player pool"),
        "roster_source": str((diag or {}).get("roster_source") or "ESPN WNBA current roster"),
        **{f"identity_{k}": v for k, v in identity_diag.items()},
    }


def _fmt(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _schedule_cards(schedule: pd.DataFrame) -> None:
    st.markdown("### 🏀 Verified WNBA Slate")
    st.caption("Exact selected-date schedule identity only. No RA picks or projections yet.")
    cards = []
    for _, row in schedule.iterrows():
        away_id = _safe_int(row.get("away_team_id"))
        home_id = _safe_int(row.get("home_team_id"))
        away = escape(str(row.get("away_team") or "Away"))
        home = escape(str(row.get("home_team") or "Home"))
        away_logo = escape(_logo(away_id), quote=True)
        home_logo = escape(_logo(home_id), quote=True)
        away_img = f'<img src="{away_logo}" alt="{away} logo">' if away_logo else "🏀"
        home_img = f'<img src="{home_logo}" alt="{home} logo">' if home_logo else "🏀"
        tip = escape(str(row.get("first_tip_et") or "Tip TBD"))
        venue = escape(str(row.get("venue") or ""))
        status = escape(str(row.get("status") or "SCHEDULED"))
        cards.append(f"""
<div class="kra-game">
  <div class="kra-game-status">{status}</div>
  <div class="kra-game-team"><span>{away_img}</span><b>{away}</b></div>
  <div class="kra-at">@</div>
  <div class="kra-game-team"><span>{home_img}</span><b>{home}</b></div>
  <div class="kra-tip">{tip}{(" • " + venue) if venue else ""}</div>
</div>
""")
    st.markdown(f'<div class="kra-games">{"".join(cards)}</div>', unsafe_allow_html=True)


def _identity_preview(pool: pd.DataFrame) -> None:
    st.markdown("### 👤 Step 1 — Verified Player Identity Preview")
    st.caption(
        "Pick any current-slate player to verify the ESPN photo, current team, opponent and "
        "existing REB/AST baselines. This is NOT a ranked pick board."
    )
    if pool is None or pool.empty:
        st.info("Verified player pool is unavailable for this slate.")
        return

    options = []
    lookup = {}
    for idx, row in pool.iterrows():
        label = f"{row.get('PLAYER_NAME','Player')} • {row.get('TEAM_ABBREVIATION') or row.get('TEAM_NAME','Team')}"
        # Defensive duplicate suffix only if the same display label exists.
        display = label if label not in lookup else f"{label} • {idx}"
        options.append(display)
        lookup[display] = idx

    selected = st.selectbox(
        "Player identity preview",
        options,
        key="wnba_ra_v1_player_preview",
    )
    row = pool.loc[lookup[selected]]

    team_id = _safe_int(row.get("TEAM_ID"))
    opp_id = _safe_int(row.get("opponent_team_id"))
    player_name_raw = str(row.get("PLAYER_NAME") or "WNBA Player")
    player_name = escape(player_name_raw)
    team_name = escape(str(row.get("TEAM_NAME") or row.get("TEAM_ABBREVIATION") or "Team"))
    opponent = escape(str(row.get("opponent") or "Opponent"))
    team_logo = escape(_logo(team_id), quote=True)
    opp_logo = escape(_logo(opp_id), quote=True)
    team_img = f'<img src="{team_logo}" alt="{team_name} logo">' if team_logo else "🏀"
    opp_img = f'<img src="{opp_logo}" alt="{opponent} logo">' if opp_logo else "🏀"
    photo = _photo_html(row.get("ESPN_PLAYER_ID"), team_id, player_name_raw)

    source = escape(str(row.get("DATA_SOURCE") or "WNBA player data"))
    roster_status = escape(str(row.get("ROSTER_STATUS") or "CURRENT ROSTER"))
    id_source = "ESPN headshot ID" if _safe_int(row.get("ESPN_PLAYER_ID")) else "team-logo photo fallback"
    position = escape(str(row.get("POSITION") or "—"))

    st.markdown(f"""
<div class="kra-player-card">
  <div class="kra-player-top"><span>STEP 1 • VERIFIED IDENTITY</span><span>NO PICK / NO RANK</span></div>
  <div class="kra-player-id">
    <div class="kra-photo-shell">{photo}</div>
    <div>
      <div class="kra-player-name">{player_name}</div>
      <div class="kra-match"><span>{team_img}{team_name}</span><b>vs</b><span>{opp_img}{opponent}</span></div>
      <div class="kra-sub">{position} • {roster_status} • {escape(id_source)}</div>
    </div>
  </div>
  <div class="kra-statgrid">
    <div><small>SEASON REB + AST</small><strong>{_fmt(row.get("RA"))}</strong></div>
    <div><small>L10 REB + AST</small><strong>{_fmt(row.get("L10_RA"))}</strong></div>
    <div><small>L5 REB + AST</small><strong>{_fmt(row.get("L5_RA"))}</strong></div>
    <div><small>SEASON MIN</small><strong>{_fmt(row.get("MIN"))}</strong></div>
    <div><small>SEASON REB</small><strong>{_fmt(row.get("REB"))}</strong></div>
    <div><small>SEASON AST</small><strong>{_fmt(row.get("AST"))}</strong></div>
    <div><small>GAMES</small><strong>{_fmt(row.get("GP"),0)}</strong></div>
    <div><small>PLAYER DATA</small><strong>{source}</strong></div>
  </div>
  <div class="kra-note">Step 1 is identity/data verification only. REB+AST values above are existing descriptive averages; no sportsbook line, projection, probability, Monte Carlo, edge, EV, qualification or ranking exists on this new page yet.</div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📚 Full verified RA player pool", expanded=False):
        board = pool.copy()
        board["Player Photo"] = board["PHOTO_URL"]
        cols = [
            "Player Photo", "PLAYER_NAME", "TEAM_ABBREVIATION", "opponent_abbr",
            "POSITION", "GP", "MIN", "REB", "AST", "RA", "L10_RA", "L5_RA",
            "ROSTER_STATUS", "PLAYER_ID_SOURCE", "DATA_SOURCE",
        ]
        cols = [c for c in cols if c in board.columns]
        st.dataframe(
            board[cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Player Photo": st.column_config.ImageColumn("Player", width="small"),
                "PLAYER_NAME": "Name",
                "TEAM_ABBREVIATION": "Team",
                "opponent_abbr": "Opp",
                "RA": st.column_config.NumberColumn("Season R+A", format="%.1f"),
                "L10_RA": st.column_config.NumberColumn("L10 R+A", format="%.1f"),
                "L5_RA": st.column_config.NumberColumn("L5 R+A", format="%.1f"),
            },
        )


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(
        """
<style>
.kra-route{border:1px solid #294d68;background:linear-gradient(145deg,#0b2034,#071521);border-radius:18px;padding:14px;margin:2px 0 12px}
.kra-route h2{margin:0;color:#f7fbff;font-size:1.35rem}.kra-route p{margin:6px 0 0;color:#8da6b9;font-size:.72rem;line-height:1.45}
.kra-step{display:inline-block;margin-top:8px;border:1px solid #237a59;background:#0b3327;color:#7df2ba;border-radius:999px;padding:5px 8px;font-size:.58rem;font-weight:950;letter-spacing:.04em}
.kra-games{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 16px}.kra-game{background:#081522;border:1px solid #284b64;border-radius:14px;padding:11px}.kra-game-status{color:#7df2ba;font-size:.48rem;font-weight:950;letter-spacing:.05em}.kra-game-team{display:flex;align-items:center;gap:8px;color:#f6fbff;margin-top:7px;font-size:.77rem}.kra-game-team span{width:30px;height:30px;display:flex;align-items:center;justify-content:center}.kra-game-team img{max-width:30px;max-height:30px;object-fit:contain}.kra-at{color:#6f8799;font-size:.55rem;font-weight:900;margin-left:10px}.kra-tip{color:#8198aa;font-size:.55rem;margin-top:8px}
.kra-player-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #315c78;border-radius:22px;padding:17px;margin:9px 0 14px;box-shadow:0 8px 22px rgba(0,0,0,.18)}.kra-player-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.kra-player-id{display:flex;align-items:center;gap:13px;margin:12px 0}.kra-photo-shell{width:82px;height:82px;min-width:82px;border-radius:50%;overflow:hidden;background:#0a1b2a;border:1px solid #326281;display:flex;align-items:center;justify-content:center}.kra-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}.kra-photo.fallback{object-fit:contain;padding:10px}.kra-placeholder{font-size:1.8rem}.kra-player-name{color:white;font-size:1.25rem;font-weight:950}.kra-match{display:flex;align-items:center;gap:7px;color:#a7bbca;font-size:.72rem;flex-wrap:wrap;margin-top:5px}.kra-match span{display:flex;align-items:center;gap:4px}.kra-match img{width:24px;height:24px;object-fit:contain}.kra-sub{color:#7f95a7;font-size:.56rem;margin-top:5px}
.kra-statgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra-statgrid div{background:#07131f;border:1px solid #24445c;border-radius:10px;padding:9px}.kra-statgrid small{display:block;color:#718ba0;font-size:.45rem;font-weight:950;letter-spacing:.035em}.kra-statgrid strong{display:block;color:#f6fbff;font-size:.72rem;margin-top:3px;line-height:1.35;overflow-wrap:anywhere}.kra-note{color:#6f8799;font-size:.51rem;line-height:1.5;margin-top:9px}
@media(max-width:760px){.kra-games{grid-template-columns:1fr}.kra-player-top{flex-direction:column}.kra-photo-shell{width:74px;height:74px;min-width:74px}}
</style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="kra-route">
  <h2>🏀 WNBA Rebounds + Assists</h2>
  <p>New isolated R+A page built in small verified steps to match the finished Points-card experience without changing the existing Rebounds, Assists, PRA or Points systems.</p>
  <span class="kra-step">STEP 1 • VERIFIED SLATE + PLAYER IDENTITY</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    day = st.date_input(
        "📅 R+A slate date",
        value=pd.Timestamp.now(tz=ET).date(),
        key="wnba_ra_v1_date",
    )
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    schedule = schedule24.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        st.info(f"No verified WNBA games were found for {day_str}.")
        return

    pool, diag = _step1_pool(day_str)
    state = str((diag or {}).get("state") or "CHECK").upper()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", int((diag or {}).get("games", len(schedule)) or 0))
    c2.metric("Slate teams", int((diag or {}).get("teams", 0) or 0))
    c3.metric("Verified players", int((diag or {}).get("players", 0) or 0))
    c4.metric("ESPN photo IDs", int((diag or {}).get("photo_matches", 0) or 0))

    if state != "VERIFIED":
        st.warning(
            "⚠️ Step 1 player identity is not fully verified yet. The new R+A page stays "
            "read-only and no later modeling step will be enabled from this state."
        )
        if (diag or {}).get("error"):
            st.caption(f"Diagnostic • {(diag or {}).get('error')}")
    else:
        st.success(
            "✅ Step 1 identity foundation verified • current slate + current roster player pool "
            "+ ESPN photo identity are connected."
        )

    st.caption(
        f"Player source • {(diag or {}).get('player_source','—')} • "
        f"Roster/photo identity • {(diag or {}).get('roster_source','ESPN WNBA current roster')} • "
        "R+A = rebounds + assists descriptive baseline only."
    )

    _schedule_cards(schedule)
    _identity_preview(pool)

    st.info(
        "🔒 STEP 1 BOUNDARY • No SportsGameOdds R+A line, projection, last-five game ledger, "
        "Monte Carlo, fair odds, EV, qualification, reason-why logic or Top-5 ranking has been "
        "added yet. Those come one verified step at a time."
    )


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
