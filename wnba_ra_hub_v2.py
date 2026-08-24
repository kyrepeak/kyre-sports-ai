"""WNBA Rebounds + Assists V2 — Step 2 exact sportsbook market verification.

Keeps the Step-1 verified slate/player identity experience and adds only the
exact combined Rebounds + Assists sportsbook market from SportsGameOdds.

Step 2 rules:
- use only the true `rebounds+assists` full-game O/U market;
- never synthesize a line by adding separate rebound and assist props;
- reconcile provider player identity to the verified current-slate roster;
- no-vig probability requires exact same-book + same-line Over/Under pairing;
- display quote timestamp/freshness and fail closed when pairing/identity fails;
- no R+A projection, Monte Carlo, edge, EV, qualification or ranking yet.
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
import wnba_ra_market_v1 as market

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V2 • STEP 2 EXACT SPORTSBOOK MARKET"
ET = ZoneInfo("America/New_York")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _fmt(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100*x:.{digits}f}%"


def _odds(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _age(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    if x < 60:
        return f"{int(x)}s"
    if x < 3600:
        return f"{int(x//60)}m"
    return f"{x/3600:.1f}h"


def _logo(team_id) -> str:
    try:
        return str(schedule25.logo_url(int(float(team_id))) or "")
    except Exception:
        return ""


def _espn_headshot(player_id) -> str:
    pid = _safe_int(player_id)
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png" if pid else ""


def _photo_html(player_id, team_id, player_name) -> str:
    headshot = escape(_espn_headshot(player_id), quote=True)
    fallback = escape(_logo(team_id), quote=True)
    alt = escape(str(player_name or "WNBA player"), quote=True)
    if headshot:
        onerror = f"this.onerror=null;this.src='{fallback}';" if fallback else "this.style.display='none';"
        return f'<img class="kra2-photo" src="{headshot}" alt="{alt}" onerror="{onerror}">'
    if fallback:
        return f'<img class="kra2-photo fallback" src="{fallback}" alt="{alt}">'
    return '<div class="kra2-placeholder">🏀</div>'


def _team_meta(schedule: pd.DataFrame) -> dict[int, dict]:
    out = {}
    if schedule is None or schedule.empty:
        return out
    for _, game in schedule.iterrows():
        for side in ("away", "home"):
            tid = _safe_int(game.get(f"{side}_team_id"))
            if tid:
                out[tid] = {
                    "name": str(game.get(f"{side}_team") or "Team"),
                    "abbr": str(game.get(f"{side}_tricode") or ""),
                }
    return out


def _opponent_map(schedule: pd.DataFrame) -> dict[int, dict]:
    out = {}
    if schedule is None or schedule.empty:
        return out
    for _, game in schedule.iterrows():
        away_id, home_id = _safe_int(game.get("away_team_id")), _safe_int(game.get("home_team_id"))
        if not away_id or not home_id:
            continue
        game_id = str(game.get("game_id") or "")
        out[away_id] = {
            "opponent_team_id": home_id,
            "opponent": str(game.get("home_team") or "Opponent"),
            "opponent_abbr": str(game.get("home_tricode") or ""),
            "game_id": game_id,
            "HOME_AWAY": "AWAY",
        }
        out[home_id] = {
            "opponent_team_id": away_id,
            "opponent": str(game.get("away_team") or "Opponent"),
            "opponent_abbr": str(game.get("away_tricode") or ""),
            "game_id": game_id,
            "HOME_AWAY": "HOME",
        }
    return out


@st.cache_data(ttl=600, show_spinner=False, max_entries=16)
def _espn_identity_map(day_str: str):
    schedule = schedule24.schedule_for_date(str(day_str))
    teams = _team_meta(schedule)
    mapping = {}
    connected = 0
    rows = 0
    for tid, meta in teams.items():
        try:
            roster = players._espn_roster(tid, meta.get("name", ""), meta.get("abbr", ""))
        except Exception:
            roster = pd.DataFrame()
        if roster is None or roster.empty:
            continue
        connected += 1
        rows += len(roster)
        for _, p in roster.iterrows():
            pid = _safe_int(p.get("PLAYER_ID"))
            name = _norm(p.get("PLAYER_NAME"))
            if pid and name:
                mapping[(tid, name)] = pid
    return mapping, {"rosters_connected": connected, "roster_rows": rows}


@st.cache_data(ttl=600, show_spinner=False, max_entries=16)
def _player_pool(day_str: str):
    schedule = schedule24.schedule_for_date(str(day_str))
    if schedule is None or schedule.empty:
        return pd.DataFrame(), {"state": "NO_GAMES", "games": 0, "teams": 0, "players": 0, "photo_matches": 0}
    try:
        pool, source_diag = players._build_selected_player_pool(str(day_str))
    except Exception as exc:
        return pd.DataFrame(), {
            "state": "PLAYER_SOURCE_CHECK", "games": len(schedule), "teams": len(_team_meta(schedule)),
            "players": 0, "photo_matches": 0, "error": str(exc)[:180],
        }
    if pool is None or pool.empty:
        return pd.DataFrame(), {"state": "PLAYER_SOURCE_CHECK", "games": len(schedule), "teams": len(_team_meta(schedule)), "players": 0, "photo_matches": 0}

    work = pool.copy()
    for col in ("REB", "AST", "L10_REB", "L10_AST", "L5_REB", "L5_AST", "MIN", "GP"):
        work[col] = pd.to_numeric(work.get(col), errors="coerce")
    work["RA"] = work["REB"] + work["AST"]
    work["L10_RA"] = work["L10_REB"] + work["L10_AST"]
    work["L5_RA"] = work["L5_REB"] + work["L5_AST"]

    opp = _opponent_map(schedule)
    for col in ("opponent_team_id", "opponent", "opponent_abbr", "game_id", "HOME_AWAY"):
        work[col] = work["TEAM_ID"].apply(lambda x, c=col: (opp.get(_safe_int(x)) or {}).get(c, "" if c != "opponent_team_id" else 0))

    identities, id_diag = _espn_identity_map(str(day_str))
    work["ESPN_PLAYER_ID"] = work.apply(lambda r: identities.get((_safe_int(r.get("TEAM_ID")), _norm(r.get("PLAYER_NAME"))), 0), axis=1)
    work["PHOTO_URL"] = work["ESPN_PLAYER_ID"].map(_espn_headshot)
    slate_ids = set(_team_meta(schedule))
    work = work.loc[work["TEAM_ID"].apply(_safe_int).isin(slate_ids) & work["PLAYER_NAME"].astype(str).str.strip().ne("")].copy()
    work["_sort"] = pd.to_numeric(work["MIN"], errors="coerce").fillna(-1)
    work = work.sort_values(["TEAM_NAME", "_sort", "PLAYER_NAME"], ascending=[True, False, True], kind="stable").drop(columns=["_sort"]).reset_index(drop=True)

    return work, {
        "state": "VERIFIED", "games": len(schedule), "teams": len(slate_ids), "players": len(work),
        "photo_matches": int((pd.to_numeric(work["ESPN_PLAYER_ID"], errors="coerce").fillna(0) > 0).sum()),
        "player_source": str((source_diag or {}).get("source") or "WNBA player pool"),
        "roster_source": str((source_diag or {}).get("roster_source") or "ESPN WNBA current roster"),
        **id_diag,
    }


def _schedule_cards(schedule: pd.DataFrame):
    st.markdown("### 🏀 Verified WNBA Slate")
    st.caption("Exact selected-date schedule identity. No R+A projection or ranking yet.")
    cards = []
    for _, game in schedule.iterrows():
        away, home = escape(str(game.get("away_team") or "Away")), escape(str(game.get("home_team") or "Home"))
        al, hl = escape(_logo(game.get("away_team_id")), quote=True), escape(_logo(game.get("home_team_id")), quote=True)
        ai = f'<img src="{al}" alt="{away} logo">' if al else "🏀"
        hi = f'<img src="{hl}" alt="{home} logo">' if hl else "🏀"
        tip, venue = escape(str(game.get("first_tip_et") or "Tip TBD")), escape(str(game.get("venue") or ""))
        cards.append(f'<div class="kra2-game"><div class="kra2-game-team"><span>{ai}</span><b>{away}</b></div><div class="kra2-at">@</div><div class="kra2-game-team"><span>{hi}</span><b>{home}</b></div><div class="kra2-tip">{tip}{(" • "+venue) if venue else ""}</div></div>')
    st.markdown(f'<div class="kra2-games">{"".join(cards)}</div>', unsafe_allow_html=True)


def _selected_row(pool: pd.DataFrame):
    options, lookup = [], {}
    for idx, row in pool.iterrows():
        label = f"{row.get('PLAYER_NAME','Player')} • {row.get('TEAM_ABBREVIATION') or row.get('TEAM_NAME','Team')}"
        display = label if label not in lookup else f"{label} • {idx}"
        options.append(display); lookup[display] = idx
    selected = st.selectbox("Player identity + market preview", options, key="wnba_ra_v2_player_preview")
    return pool.loc[lookup[selected]]


def _market_rows_for_player(markets: pd.DataFrame, row) -> pd.DataFrame:
    if markets is None or markets.empty:
        return pd.DataFrame()
    pid = str(row.get("PLAYER_ID") or "").strip()
    name = str(row.get("PLAYER_NAME") or "").strip().lower()
    game_id = str(row.get("game_id") or "")
    out = markets.copy()
    if "game_id" in out.columns:
        out = out.loc[out["game_id"].astype(str).eq(game_id)]
    if pid and "PLAYER_ID" in out.columns:
        exact = out.loc[out["PLAYER_ID"].astype(str).str.replace(".0", "", regex=False).eq(pid.replace(".0", ""))]
        if not exact.empty:
            out = exact
        elif "PLAYER_NAME" in out.columns:
            out = out.loc[out["PLAYER_NAME"].astype(str).str.lower().eq(name)]
    elif "PLAYER_NAME" in out.columns:
        out = out.loc[out["PLAYER_NAME"].astype(str).str.lower().eq(name)]
    if out.empty:
        return out
    out["_verified"] = out.get("market_state", "").astype(str).eq("VERIFIED").astype(int)
    out["_age"] = pd.to_numeric(out.get("age_seconds"), errors="coerce").fillna(10**12)
    return out.sort_values(["_verified", "_age", "book", "line"], ascending=[False, True, True, True], kind="stable")


def _step2_block(player_row, markets: pd.DataFrame, meta: dict) -> str:
    rows = _market_rows_for_player(markets, player_row)
    state = str((meta or {}).get("state") or "CHECK").upper()
    if rows.empty:
        if state == "NO_API_KEY":
            message = "SportsGameOdds API key is not available to this R+A route."
        elif state == "NO_OPEN_RA_MARKETS":
            message = "No true combined Rebounds + Assists market is currently posted for this verified player/slate."
        elif state == "PROVIDER_ERROR":
            message = f"SportsGameOdds market request needs a source check: {escape(str((meta or {}).get('error') or 'provider error'))}."
        else:
            message = "No exact paired R+A market reconciled to this verified player yet."
        return f'<div class="kra2-step2"><div class="kra2-stephead"><span>STEP 2 • EXACT R+A SPORTSBOOK MARKET</span><span class="kra2-chip warn">NO VERIFIED PAIR</span></div><div class="kra2-empty">{message}</div><div class="kra2-note">Fail closed • no separate rebound/assist lines are added together • no projection or ranking is created.</div></div>'

    cards = []
    verified_count = 0
    for _, q in rows.head(8).iterrows():
        verified = str(q.get("market_state") or "") == "VERIFIED"
        verified_count += int(verified)
        cls = "good" if verified else "warn"
        fresh = _num(q.get("age_seconds"), np.nan)
        freshness = "FRESH" if np.isfinite(fresh) and fresh <= 900 else ("STALE CHECK" if np.isfinite(fresh) else "TIME CHECK")
        cards.append(f'''<div class="kra2-market-card">
<div class="kra2-markettop"><b>{escape(str(q.get('book') or 'Sportsbook'))}</b><span class="kra2-chip {cls}">{'VERIFIED PAIR' if verified else 'INCOMPLETE'}</span></div>
<div class="kra2-line">R+A {float(q.get('line')):.1f}</div>
<div class="kra2-mgrid">
<div><small>OVER</small><strong>{_odds(q.get('over_price'))}</strong></div><div><small>UNDER</small><strong>{_odds(q.get('under_price'))}</strong></div>
<div><small>RAW OVER</small><strong>{_pct(q.get('raw_over_prob'))}</strong></div><div><small>RAW UNDER</small><strong>{_pct(q.get('raw_under_prob'))}</strong></div>
<div><small>NO-VIG OVER</small><strong>{_pct(q.get('no_vig_over'))}</strong></div><div><small>NO-VIG UNDER</small><strong>{_pct(q.get('no_vig_under'))}</strong></div>
<div><small>BOOK HOLD</small><strong>{_pct(q.get('hold'))}</strong></div><div><small>QUOTE AGE</small><strong>{_age(q.get('age_seconds'))} • {freshness}</strong></div>
</div><div class="kra2-updated">Paired timestamp basis • {escape(str(q.get('updated_at') or '—'))}</div></div>''')

    return f'''<div class="kra2-step2"><div class="kra2-stephead"><span>STEP 2 • EXACT R+A SPORTSBOOK MARKET</span><span class="kra2-chip {'good' if verified_count else 'warn'}">{verified_count} VERIFIED PAIR(S)</span></div>
<div class="kra2-stepintro">True combined <b>Rebounds + Assists</b> market only • exact same-book + same-line O/U pairing • player identity reconciled to Step 1.</div>
<div class="kra2-marketgrid">{"".join(cards)}</div>
<div class="kra2-note">Market verification only • no-vig is descriptive market context • no R+A projection, Monte Carlo, edge, EV, qualification, reason-why score or Top-5 ranking yet.</div></div>'''


def _player_card(row, markets, market_meta):
    team_id, opp_id = _safe_int(row.get("TEAM_ID")), _safe_int(row.get("opponent_team_id"))
    name_raw = str(row.get("PLAYER_NAME") or "WNBA Player")
    name = escape(name_raw)
    team = escape(str(row.get("TEAM_NAME") or row.get("TEAM_ABBREVIATION") or "Team"))
    opp = escape(str(row.get("opponent") or "Opponent"))
    tl, ol = escape(_logo(team_id), quote=True), escape(_logo(opp_id), quote=True)
    ti = f'<img src="{tl}" alt="team logo">' if tl else "🏀"
    oi = f'<img src="{ol}" alt="opponent logo">' if ol else "🏀"
    photo = _photo_html(row.get("ESPN_PLAYER_ID"), team_id, name_raw)
    source = escape(str(row.get("DATA_SOURCE") or "WNBA player data"))
    status = escape(str(row.get("ROSTER_STATUS") or "CURRENT ROSTER"))
    pos = escape(str(row.get("POSITION") or "—"))

    st.markdown(f'''<div class="kra2-player-card">
<div class="kra2-player-top"><span>STEP 1 • VERIFIED IDENTITY</span><span>NO PICK / NO RANK</span></div>
<div class="kra2-player-id"><div class="kra2-photo-shell">{photo}</div><div><div class="kra2-player-name">{name}</div><div class="kra2-match"><span>{ti}{team}</span><b>vs</b><span>{oi}{opp}</span></div><div class="kra2-sub">{pos} • {status} • ESPN headshot ID</div></div></div>
<div class="kra2-statgrid"><div><small>SEASON REB + AST</small><strong>{_fmt(row.get('RA'))}</strong></div><div><small>L10 REB + AST</small><strong>{_fmt(row.get('L10_RA'))}</strong></div><div><small>L5 REB + AST</small><strong>{_fmt(row.get('L5_RA'))}</strong></div><div><small>SEASON MIN</small><strong>{_fmt(row.get('MIN'))}</strong></div><div><small>SEASON REB</small><strong>{_fmt(row.get('REB'))}</strong></div><div><small>SEASON AST</small><strong>{_fmt(row.get('AST'))}</strong></div><div><small>GAMES</small><strong>{_fmt(row.get('GP'),0)}</strong></div><div><small>PLAYER DATA</small><strong>{source}</strong></div></div>
<div class="kra2-note">Step 1 remains identity/data verification only.</div>{_step2_block(row, markets, market_meta)}</div>''', unsafe_allow_html=True)


def _full_boards(pool: pd.DataFrame, markets: pd.DataFrame):
    with st.expander("📚 Full verified R+A player pool", expanded=False):
        board = pool.copy(); board["Player Photo"] = board["PHOTO_URL"]
        cols = [c for c in ["Player Photo","PLAYER_NAME","TEAM_ABBREVIATION","opponent_abbr","POSITION","GP","MIN","REB","AST","RA","L10_RA","L5_RA","ROSTER_STATUS","DATA_SOURCE"] if c in board.columns]
        st.dataframe(board[cols], use_container_width=True, hide_index=True, column_config={"Player Photo": st.column_config.ImageColumn("Player", width="small"), "RA": st.column_config.NumberColumn("Season R+A", format="%.1f"), "L10_RA": st.column_config.NumberColumn("L10 R+A", format="%.1f"), "L5_RA": st.column_config.NumberColumn("L5 R+A", format="%.1f")})
    with st.expander("🎯 Full exact R+A market board", expanded=False):
        if markets is None or markets.empty:
            st.info("No reconciled exact R+A market rows are currently available.")
        else:
            cols = [c for c in ["PLAYER_NAME","TEAM_ABBREVIATION","opponent_abbr","book","line","over_price","under_price","no_vig_over","no_vig_under","age_seconds","market_state"] if c in markets.columns]
            st.dataframe(markets[cols], use_container_width=True, hide_index=True)


def _css():
    st.markdown('''<style>
.kra2-route{border:1px solid #294d68;background:linear-gradient(145deg,#0b2034,#071521);border-radius:18px;padding:14px;margin:2px 0 12px}.kra2-route h2{margin:0;color:#f7fbff;font-size:1.35rem}.kra2-route p{margin:6px 0 0;color:#8da6b9;font-size:.72rem;line-height:1.45}.kra2-step{display:inline-block;margin-top:8px;border:1px solid #237a59;background:#0b3327;color:#7df2ba;border-radius:999px;padding:5px 8px;font-size:.58rem;font-weight:950;letter-spacing:.04em}
.kra2-games{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 16px}.kra2-game{background:#081522;border:1px solid #284b64;border-radius:14px;padding:11px}.kra2-game-team{display:flex;align-items:center;gap:8px;color:#f6fbff;margin-top:6px;font-size:.77rem}.kra2-game-team span{width:30px;height:30px;display:flex;align-items:center;justify-content:center}.kra2-game-team img{max-width:30px;max-height:30px;object-fit:contain}.kra2-at{color:#6f8799;font-size:.55rem;font-weight:900;margin-left:10px}.kra2-tip{color:#8198aa;font-size:.55rem;margin-top:8px}
.kra2-player-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #315c78;border-radius:22px;padding:17px;margin:9px 0 14px;box-shadow:0 8px 22px rgba(0,0,0,.18)}.kra2-player-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.kra2-player-id{display:flex;align-items:center;gap:13px;margin:12px 0}.kra2-photo-shell{width:82px;height:82px;min-width:82px;border-radius:50%;overflow:hidden;background:#0a1b2a;border:1px solid #326281;display:flex;align-items:center;justify-content:center}.kra2-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}.kra2-photo.fallback{object-fit:contain;padding:10px}.kra2-placeholder{font-size:1.8rem}.kra2-player-name{color:white;font-size:1.25rem;font-weight:950}.kra2-match{display:flex;align-items:center;gap:7px;color:#a7bbca;font-size:.72rem;flex-wrap:wrap;margin-top:5px}.kra2-match span{display:flex;align-items:center;gap:4px}.kra2-match img{width:24px;height:24px;object-fit:contain}.kra2-sub{color:#7f95a7;font-size:.56rem;margin-top:5px}
.kra2-statgrid,.kra2-mgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra2-statgrid div,.kra2-mgrid div{background:#07131f;border:1px solid #24445c;border-radius:10px;padding:9px}.kra2-statgrid small,.kra2-mgrid small{display:block;color:#718ba0;font-size:.45rem;font-weight:950;letter-spacing:.035em}.kra2-statgrid strong,.kra2-mgrid strong{display:block;color:#f6fbff;font-size:.72rem;margin-top:3px;line-height:1.35;overflow-wrap:anywhere}.kra2-note{color:#6f8799;font-size:.51rem;line-height:1.5;margin-top:9px}
.kra2-step2{background:#091827;border:1px solid #315c78;border-radius:16px;padding:12px;margin-top:14px}.kra2-stephead,.kra2-markettop{display:flex;justify-content:space-between;gap:8px;align-items:center;color:#79d8ff;font-size:.58rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.kra2-stepintro,.kra2-empty{color:#c9d7e2;font-size:.65rem;line-height:1.5;margin:8px 0}.kra2-marketgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}.kra2-market-card{background:#07131f;border:1px solid #24445c;border-radius:13px;padding:10px}.kra2-markettop b{color:#f6fbff}.kra2-line{color:#ffe17a;font-size:1.05rem;font-weight:950;margin:9px 0}.kra2-chip{display:inline-block;border-radius:999px;padding:5px 7px;font-size:.48rem;font-weight:950}.kra2-chip.good{border:1px solid #237a59;background:#0b3327;color:#7df2ba}.kra2-chip.warn{border:1px solid #7c5832;background:#352516;color:#ffc984}.kra2-updated{color:#6f8799;font-size:.47rem;margin-top:7px;overflow-wrap:anywhere}
@media(max-width:760px){.kra2-games,.kra2-marketgrid{grid-template-columns:1fr}.kra2-player-top{flex-direction:column}.kra2-photo-shell{width:74px;height:74px;min-width:74px}}
</style>''', unsafe_allow_html=True)


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    st.markdown('''<div class="kra2-route"><h2>🏀 WNBA Rebounds + Assists</h2><p>Built one verified layer at a time to match the finished Points-card experience while keeping existing WNBA markets isolated.</p><span class="kra2-step">STEPS 1–2 • IDENTITY + EXACT MARKET</span></div>''', unsafe_allow_html=True)

    day = st.date_input("📅 R+A slate date", value=pd.Timestamp.now(tz=ET).date(), key="wnba_ra_v2_date")
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule = schedule24.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        st.info(f"No verified WNBA games were found for {day_str}.")
        return

    pool, diag = _player_pool(day_str)
    with st.spinner("🎯 Verifying exact combined R+A sportsbook markets…"):
        reconciled, market_meta = market.reconcile_to_player_pool(day_str, pool)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Games", int(diag.get("games", len(schedule)) or 0)); c2.metric("Verified players", int(diag.get("players",0) or 0)); c3.metric("R+A paired rows", int((market_meta or {}).get("verified_pairs",0) or 0)); c4.metric("Market state", str((market_meta or {}).get("state") or "CHECK").replace("_"," ").title())
    if str(diag.get("state") or "").upper() == "VERIFIED": st.success("✅ Step 1 identity remains verified.")
    else: st.warning("⚠️ Step 1 identity needs a source check; Step 2 stays fail-closed.")

    mstate = str((market_meta or {}).get("state") or "CHECK").upper()
    if mstate == "VERIFIED":
        st.success("✅ Step 2 exact R+A market connected • true combined market + paired O/U + verified player identity.")
    elif mstate == "NO_OPEN_RA_MARKETS":
        st.info("No open true combined Rebounds + Assists markets are posted right now. Nothing is synthesized from separate props.")
    elif mstate == "NO_API_KEY":
        st.warning("SportsGameOdds API key is unavailable to the R+A route; Step 2 remains locked.")
    elif mstate == "PROVIDER_ERROR":
        st.warning(f"SportsGameOdds R+A source check • {(market_meta or {}).get('error') or 'provider error'}")
    else:
        st.warning("R+A market rows were not fully paired/reconciled yet. Step 2 remains fail-closed.")

    st.caption("SportsGameOdds documented combined market • rebounds+assists-PLAYER_ID-game-ou-over / under • exact market only • no synthetic R+A lines.")
    _schedule_cards(schedule)
    if pool is None or pool.empty:
        st.info("Verified player pool is unavailable for this slate.")
        return
    row = _selected_row(pool)
    _player_card(row, reconciled, market_meta)
    _full_boards(pool, reconciled)
    if st.button("🔄 Refresh exact R+A markets", use_container_width=True, key=f"wnba_ra_v2_refresh_{day_str}"):
        market.clear_cache(); st.rerun()
    st.info("🔒 STEP 2 BOUNDARY • Exact market verification only. No R+A projection, last-five game ledger, Monte Carlo, fair odds, model edge, EV, qualification, reason-why engine or Top-5 ranking has been added yet.")


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
