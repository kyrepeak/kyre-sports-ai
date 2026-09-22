"""WNBA Rebounds + Assists V3 — Step 3 player form + history.

Presentation/data-context layer over the verified V2 identity + exact combined
SportsGameOdds R+A market page.

Step 3 adds only completed-game descriptive evidence before the selected slate:
- current-team season / L10 / L5 R+A form;
- individual last-five game ledger with MIN, REB, AST and R+A;
- hit/miss/push results against the exact verified current R+A line;
- season / L10 / L5 hit rates;
- home / away R+A splits;
- current-team player-vs-opponent R+A history and sample reliability;
- a simple descriptive recent trend.

No R+A projection, Monte Carlo, probability model, fair odds, model edge, EV,
qualification, reason-why score, ranking or Top-5 publication is created here.
Existing Points, Rebounds, Assists, PRA, Spread and all other routes are untouched.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_ra_hub_v2 as prior

players = prior.players
schedule24 = prior.schedule24
market = prior.market
ET = prior.ET

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V3 • STEP 3 PLAYER FORM + HISTORY"


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


def _line_basis(player_row, markets: pd.DataFrame) -> dict:
    """Choose a descriptive exact-line basis without ranking books or sides."""
    rows = prior._market_rows_for_player(markets, player_row)
    if rows is None or rows.empty:
        return {"line": np.nan, "books": "", "pairs": 0}
    work = rows.copy()
    work["line"] = pd.to_numeric(work.get("line"), errors="coerce")
    work["age_seconds"] = pd.to_numeric(work.get("age_seconds"), errors="coerce")
    work = work.loc[
        work.get("market_state", "").astype(str).str.upper().eq("VERIFIED")
        & work["line"].notna()
    ].copy()
    if work.empty:
        return {"line": np.nan, "books": "", "pairs": 0}

    grouped = (
        work.groupby("line", dropna=False)
        .agg(Pairs=("book", "nunique"), Youngest=("age_seconds", "min"))
        .reset_index()
    )
    grouped["Youngest"] = pd.to_numeric(grouped["Youngest"], errors="coerce").fillna(10**12)
    chosen = grouped.sort_values(["Pairs", "Youngest", "line"], ascending=[False, True, True]).iloc[0]
    line = float(chosen["line"])
    same = work.loc[work["line"].eq(line)].copy()
    books = ", ".join(sorted({str(x) for x in same.get("book", []) if str(x).strip()}))
    return {"line": line, "books": books, "pairs": int(chosen["Pairs"])}


@st.cache_data(ttl=900, show_spinner=False, max_entries=256)
def _player_current_team_log(day_str: str, team_id: int, espn_player_id: int, player_name: str) -> pd.DataFrame:
    """Completed current-team game log strictly before the selected slate date."""
    day = pd.to_datetime(day_str).normalize()
    tid = int(team_id or 0)
    pid = int(espn_player_id or 0)
    name_key = _norm(player_name)
    if not tid or (not pid and not name_key):
        return pd.DataFrame()

    try:
        season = players._espn_season_schedule(int(day.year))
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return pd.DataFrame()

    work = season.copy()
    dates = pd.to_datetime(work.get("game_date"), errors="coerce")
    away_ids = pd.to_numeric(work.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home_ids = pd.to_numeric(work.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    mask = dates.lt(day) & (away_ids.eq(tid) | home_ids.eq(tid))
    games = work.loc[mask].copy()
    if games.empty:
        return pd.DataFrame()
    games["_DATE"] = pd.to_datetime(games.get("game_date"), errors="coerce")
    games = games.sort_values("_DATE", ascending=False).drop_duplicates("game_id", keep="first")

    rows = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty:
            continue

        part = box.loc[pd.to_numeric(box.get("TEAM_ID"), errors="coerce").eq(tid)].copy()
        if part.empty:
            continue
        match = pd.DataFrame()
        if pid and "PLAYER_ID" in part.columns:
            match = part.loc[pd.to_numeric(part["PLAYER_ID"], errors="coerce").fillna(0).astype(int).eq(pid)].copy()
        if match.empty and name_key and "PLAYER_NAME" in part.columns:
            match = part.loc[part["PLAYER_NAME"].map(_norm).eq(name_key)].copy()
        if match.empty:
            continue

        p = match.iloc[0]
        reb = _num(p.get("REB"), np.nan)
        ast = _num(p.get("AST"), np.nan)
        mins = _num(p.get("MIN"), np.nan)
        if not np.isfinite(reb) or not np.isfinite(ast):
            continue

        home_id = _safe_int(game.get("home_team_id"))
        away_id = _safe_int(game.get("away_team_id"))
        is_home = home_id == tid
        if is_home:
            opp_id = away_id
            opp_name = str(game.get("away_team") or game.get("away_tricode") or "Opponent")
            location = "HOME"
        else:
            opp_id = home_id
            opp_name = str(game.get("home_team") or game.get("home_tricode") or "Opponent")
            location = "AWAY"

        game_date = pd.to_datetime(game.get("game_date"), errors="coerce")
        rows.append({
            "game_id": gid,
            "game_date": game_date,
            "opponent_team_id": opp_id,
            "opponent": opp_name,
            "location": location,
            "MIN": mins,
            "REB": reb,
            "AST": ast,
            "RA": float(reb + ast),
        })

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return (
        out.drop_duplicates("game_id", keep="first")
        .sort_values("game_date", ascending=False)
        .reset_index(drop=True)
    )


def _line_result(value: float, line: float) -> tuple[str, str]:
    if not np.isfinite(line) or not np.isfinite(value):
        return "—", "neutral"
    if value > line:
        return "OVER", "good"
    if value < line:
        return "UNDER", "bad"
    return "PUSH", "push"


def _hit_text(frame: pd.DataFrame, line: float) -> str:
    if frame is None or frame.empty or not np.isfinite(line):
        return "—"
    vals = pd.to_numeric(frame.get("RA"), errors="coerce").dropna()
    if vals.empty:
        return "—"
    overs = int((vals > line).sum())
    pushes = int((vals == line).sum())
    return f"{overs}/{len(vals)} • {100*overs/len(vals):.0f}%" + (f" • {pushes} push" if pushes else "")


def _split_text(frame: pd.DataFrame, line: float) -> str:
    if frame is None or frame.empty:
        return "—"
    avg = pd.to_numeric(frame.get("RA"), errors="coerce").mean()
    if not np.isfinite(avg):
        return "—"
    if np.isfinite(line):
        vals = pd.to_numeric(frame.get("RA"), errors="coerce").dropna()
        overs = int((vals > line).sum()) if len(vals) else 0
        return f"{avg:.1f} avg • {overs}/{len(vals)} O"
    return f"{avg:.1f} avg"


def _summary(logs: pd.DataFrame, line: float, opponent_team_id: int) -> dict:
    if logs is None or logs.empty:
        return {"state": "NO_HISTORY"}
    season = logs.copy()
    l10 = season.head(10)
    l5 = season.head(5)
    home = season.loc[season["location"].eq("HOME")]
    away = season.loc[season["location"].eq("AWAY")]
    h2h = season.loc[pd.to_numeric(season["opponent_team_id"], errors="coerce").fillna(0).astype(int).eq(int(opponent_team_id or 0))].copy()

    season_avg = pd.to_numeric(season["RA"], errors="coerce").mean()
    l10_avg = pd.to_numeric(l10["RA"], errors="coerce").mean()
    l5_avg = pd.to_numeric(l5["RA"], errors="coerce").mean()
    delta = l5_avg - season_avg if np.isfinite(l5_avg) and np.isfinite(season_avg) else np.nan
    if np.isfinite(delta) and delta >= 1.0:
        trend, trend_cls = "IMPROVING", "good"
    elif np.isfinite(delta) and delta <= -1.0:
        trend, trend_cls = "DECLINING", "bad"
    else:
        trend, trend_cls = "STEADY", "mid"

    hgp = int(len(h2h))
    if hgp >= 5:
        reliability, rel_cls = "HIGH", "good"
    elif hgp >= 3:
        reliability, rel_cls = "MEDIUM", "mid"
    elif hgp >= 1:
        reliability, rel_cls = "LOW", "warn"
    else:
        reliability, rel_cls = "NO SAMPLE", "warn"

    return {
        "state": "READY",
        "season": season,
        "l10": l10,
        "l5": l5,
        "home": home,
        "away": away,
        "h2h": h2h,
        "season_avg": season_avg,
        "l10_avg": l10_avg,
        "l5_avg": l5_avg,
        "season_hit": _hit_text(season, line),
        "l10_hit": _hit_text(l10, line),
        "l5_hit": _hit_text(l5, line),
        "home_text": _split_text(home, line),
        "away_text": _split_text(away, line),
        "trend": trend,
        "trend_cls": trend_cls,
        "h2h_gp": hgp,
        "h2h_avg": pd.to_numeric(h2h.get("RA"), errors="coerce").mean() if hgp else np.nan,
        "h2h_hit": _hit_text(h2h, line),
        "reliability": reliability,
        "rel_cls": rel_cls,
    }


def _game_rows_html(frame: pd.DataFrame, line: float, max_games: int = 5) -> str:
    if frame is None or frame.empty:
        return '<div class="kra3-empty">No verified completed-game rows available.</div>'
    rows = []
    for _, game in frame.head(max_games).iterrows():
        dt = game.get("game_date")
        date_text = dt.strftime("%b %d") if pd.notna(dt) else "—"
        loc = "vs" if str(game.get("location")) == "HOME" else "@"
        opponent = escape(str(game.get("opponent") or "Opponent"))
        ra = _num(game.get("RA"), np.nan)
        label, cls = _line_result(ra, line)
        rows.append(f'''<div class="kra3-game-row">
<div class="kra3-game-main"><b>{date_text} • {loc} {opponent}</b><small>{_fmt(game.get('MIN'))} MIN</small></div>
<div><small>REB</small><strong>{_fmt(game.get('REB'),0)}</strong></div>
<div><small>AST</small><strong>{_fmt(game.get('AST'),0)}</strong></div>
<div><small>R+A</small><strong>{_fmt(ra,0)}</strong></div>
<div class="kra3-result {cls}">{label}</div>
</div>''')
    return "".join(rows)


def _step3_block(day_str: str, player_row, markets: pd.DataFrame) -> str:
    line_info = _line_basis(player_row, markets)
    line = _num(line_info.get("line"), np.nan)
    books = escape(str(line_info.get("books") or ""))
    pairs = int(line_info.get("pairs") or 0)
    team_id = _safe_int(player_row.get("TEAM_ID"))
    opponent_id = _safe_int(player_row.get("opponent_team_id"))
    espn_id = _safe_int(player_row.get("ESPN_PLAYER_ID"))
    player_name = str(player_row.get("PLAYER_NAME") or "WNBA Player")

    logs = _player_current_team_log(day_str, team_id, espn_id, player_name)
    summary = _summary(logs, line, opponent_id)
    if str(summary.get("state")) != "READY":
        return '''<div class="kra3-step3"><div class="kra3-head"><span>STEP 3 • PLAYER R+A FORM + HISTORY</span><span class="kra3-chip warn">DATA CHECK</span></div><div class="kra3-empty">No verified current-team completed-game history was available for this player before the selected slate.</div><div class="kra3-note">Descriptive only • Step 1 identity and Step 2 exact market remain unchanged.</div></div>'''

    line_text = "—" if not np.isfinite(line) else f"{line:.1f}"
    basis = "No verified exact line available; hit-rate fields remain blank." if not np.isfinite(line) else f"Exact-line basis • R+A {line_text} • {pairs} verified book pair(s){(' • ' + books) if books else ''}."
    h2h = summary.get("h2h")
    last5_html = _game_rows_html(summary.get("l5"), line, 5)
    h2h_html = _game_rows_html(h2h, line, 5) if isinstance(h2h, pd.DataFrame) and not h2h.empty else '<div class="kra3-empty">No prior current-team meetings vs today\'s opponent.</div>'

    return f'''<div class="kra3-step3">
<div class="kra3-head"><span>STEP 3 • PLAYER R+A FORM + HISTORY</span><span class="kra3-chip good">DESCRIPTIVE ONLY</span></div>
<div class="kra3-intro">Current-team completed games strictly before this slate • no future-game leakage.<br>{basis}</div>
<div class="kra3-grid">
<div><small>SEASON R+A</small><strong>{_fmt(summary.get('season_avg'))}</strong></div>
<div><small>L10 R+A</small><strong>{_fmt(summary.get('l10_avg'))}</strong></div>
<div><small>L5 R+A</small><strong>{_fmt(summary.get('l5_avg'))}</strong></div>
<div><small>RECENT TREND</small><strong class="{summary.get('trend_cls')}">{escape(str(summary.get('trend')))}</strong></div>
<div><small>SEASON OVER {line_text}</small><strong>{escape(str(summary.get('season_hit')))}</strong></div>
<div><small>L10 OVER {line_text}</small><strong>{escape(str(summary.get('l10_hit')))}</strong></div>
<div><small>L5 OVER {line_text}</small><strong>{escape(str(summary.get('l5_hit')))}</strong></div>
<div><small>HOME R+A / LINE</small><strong>{escape(str(summary.get('home_text')))}</strong></div>
<div><small>AWAY R+A / LINE</small><strong>{escape(str(summary.get('away_text')))}</strong></div>
<div><small>H2H GP</small><strong>{int(summary.get('h2h_gp') or 0)}</strong></div>
<div><small>H2H AVG R+A</small><strong>{_fmt(summary.get('h2h_avg'))}</strong></div>
<div><small>H2H OVER {line_text}</small><strong>{escape(str(summary.get('h2h_hit')))}</strong></div>
</div>
<div class="kra3-subhead"><span>LAST 5 • GAME-BY-GAME</span></div>
<div class="kra3-ledger">{last5_html}</div>
<div class="kra3-subhead"><span>PLAYER VS TODAY'S OPPONENT</span><span class="kra3-chip {summary.get('rel_cls')}">{escape(str(summary.get('reliability')))} RELIABILITY</span></div>
<div class="kra3-ledger">{h2h_html}</div>
<div class="kra3-note">Source • verified ESPN WNBA completed-game summaries • current team only • exact current R+A line is used only for descriptive hit/miss comparison. NOT FED INTO any projection, Monte Carlo, probability, edge, EV, qualification, reason-why score or ranking.</div>
</div>'''


def _player_card(day_str: str, row, markets, market_meta):
    team_id, opp_id = _safe_int(row.get("TEAM_ID")), _safe_int(row.get("opponent_team_id"))
    name_raw = str(row.get("PLAYER_NAME") or "WNBA Player")
    name = escape(name_raw)
    team = escape(str(row.get("TEAM_NAME") or row.get("TEAM_ABBREVIATION") or "Team"))
    opp = escape(str(row.get("opponent") or "Opponent"))
    tl, ol = escape(prior._logo(team_id), quote=True), escape(prior._logo(opp_id), quote=True)
    ti = f'<img src="{tl}" alt="team logo">' if tl else "🏀"
    oi = f'<img src="{ol}" alt="opponent logo">' if ol else "🏀"
    photo = prior._photo_html(row.get("ESPN_PLAYER_ID"), team_id, name_raw)
    source = escape(str(row.get("DATA_SOURCE") or "WNBA player data"))
    status = escape(str(row.get("ROSTER_STATUS") or "CURRENT ROSTER"))
    pos = escape(str(row.get("POSITION") or "—"))

    st.markdown(f'''<div class="kra2-player-card">
<div class="kra2-player-top"><span>STEP 1 • VERIFIED IDENTITY</span><span>NO PICK / NO RANK</span></div>
<div class="kra2-player-id"><div class="kra2-photo-shell">{photo}</div><div><div class="kra2-player-name">{name}</div><div class="kra2-match"><span>{ti}{team}</span><b>vs</b><span>{oi}{opp}</span></div><div class="kra2-sub">{pos} • {status} • ESPN headshot ID</div></div></div>
<div class="kra2-statgrid"><div><small>SEASON REB + AST</small><strong>{prior._fmt(row.get('RA'))}</strong></div><div><small>L10 REB + AST</small><strong>{prior._fmt(row.get('L10_RA'))}</strong></div><div><small>L5 REB + AST</small><strong>{prior._fmt(row.get('L5_RA'))}</strong></div><div><small>SEASON MIN</small><strong>{prior._fmt(row.get('MIN'))}</strong></div><div><small>SEASON REB</small><strong>{prior._fmt(row.get('REB'))}</strong></div><div><small>SEASON AST</small><strong>{prior._fmt(row.get('AST'))}</strong></div><div><small>GAMES</small><strong>{prior._fmt(row.get('GP'),0)}</strong></div><div><small>PLAYER DATA</small><strong>{source}</strong></div></div>
<div class="kra2-note">Step 1 remains identity/data verification only.</div>
{prior._step2_block(row, markets, market_meta)}
{_step3_block(day_str, row, markets)}
</div>''', unsafe_allow_html=True)


def _css():
    prior._css()
    st.markdown('''<style>
.kra3-step3{background:#0a1928;border:1px solid #3a5d76;border-radius:16px;padding:12px;margin-top:14px}.kra3-head,.kra3-subhead{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#79d8ff;font-size:.58rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.kra3-subhead{margin-top:12px;color:#a7c8dd}.kra3-intro,.kra3-empty{color:#c9d7e2;font-size:.63rem;line-height:1.5;margin:8px 0}.kra3-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kra3-grid div{background:#07131f;border:1px solid #24445c;border-radius:10px;padding:9px}.kra3-grid small{display:block;color:#718ba0;font-size:.45rem;font-weight:950;letter-spacing:.035em}.kra3-grid strong{display:block;color:#f6fbff;font-size:.72rem;margin-top:3px;line-height:1.35}.kra3-grid strong.good{color:#7df2ba}.kra3-grid strong.bad{color:#ff9aa5}.kra3-grid strong.mid{color:#ffe17a}.kra3-chip{display:inline-block;border-radius:999px;padding:5px 7px;font-size:.48rem;font-weight:950;white-space:nowrap}.kra3-chip.good{border:1px solid #237a59;background:#0b3327;color:#7df2ba}.kra3-chip.mid{border:1px solid #826c16;background:#3a3009;color:#ffe17a}.kra3-chip.warn{border:1px solid #7c5832;background:#352516;color:#ffc984}.kra3-ledger{margin-top:7px;border:1px solid #24445c;border-radius:12px;overflow:hidden}.kra3-game-row{display:grid;grid-template-columns:minmax(0,2.2fr) repeat(3,minmax(42px,.55fr)) minmax(58px,.7fr);gap:6px;align-items:center;padding:9px;border-bottom:1px solid #1e394e;background:#07131f}.kra3-game-row:last-child{border-bottom:0}.kra3-game-main b{display:block;color:#eef7fd;font-size:.62rem}.kra3-game-main small,.kra3-game-row>div>small{display:block;color:#718ba0;font-size:.43rem;margin-top:2px}.kra3-game-row>div>strong{color:#f6fbff;font-size:.65rem}.kra3-result{border-radius:999px;padding:5px 6px;text-align:center;font-size:.48rem;font-weight:950}.kra3-result.good{border:1px solid #237a59;background:#0b3327;color:#7df2ba}.kra3-result.bad{border:1px solid #7a3941;background:#35171b;color:#ff9aa5}.kra3-result.push{border:1px solid #826c16;background:#3a3009;color:#ffe17a}.kra3-result.neutral{border:1px solid #355873;color:#bed4e3}.kra3-note{color:#6f8799;font-size:.49rem;line-height:1.5;margin-top:9px}
@media(max-width:760px){.kra3-game-row{grid-template-columns:minmax(0,1.9fr) repeat(3,minmax(36px,.5fr));}.kra3-result{grid-column:1/-1;justify-self:start;padding:4px 8px}.kra3-head,.kra3-subhead{align-items:flex-start;flex-wrap:wrap}}
</style>''', unsafe_allow_html=True)


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    st.markdown('''<div class="kra2-route"><h2>🏀 WNBA Rebounds + Assists</h2><p>Built one verified layer at a time to match the finished Points-card experience while keeping existing WNBA markets isolated.</p><span class="kra2-step">STEPS 1–3 • IDENTITY + EXACT MARKET + FORM / HISTORY</span></div>''', unsafe_allow_html=True)

    day = st.date_input("📅 R+A slate date", value=pd.Timestamp.now(tz=ET).date(), key="wnba_ra_v2_date")
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule = schedule24.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        st.info(f"No verified WNBA games were found for {day_str}.")
        return

    pool, diag = prior._player_pool(day_str)
    with st.spinner("🎯 Verifying exact combined R+A sportsbook markets…"):
        reconciled, market_meta = market.reconcile_to_player_pool(day_str, pool)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", int(diag.get("games", len(schedule)) or 0))
    c2.metric("Verified players", int(diag.get("players", 0) or 0))
    c3.metric("R+A paired rows", int((market_meta or {}).get("verified_pairs", 0) or 0))
    c4.metric("Market state", str((market_meta or {}).get("state") or "CHECK").replace("_", " ").title())

    if str(diag.get("state") or "").upper() == "VERIFIED":
        st.success("✅ Step 1 identity remains verified.")
    else:
        st.warning("⚠️ Step 1 identity needs a source check; later steps stay fail-closed.")

    mstate = str((market_meta or {}).get("state") or "CHECK").upper()
    if mstate == "VERIFIED":
        st.success("✅ Step 2 exact R+A market remains verified • true combined market + paired O/U + player identity.")
    elif mstate == "NO_OPEN_RA_MARKETS":
        st.info("No open true combined Rebounds + Assists markets are posted right now. Nothing is synthesized from separate props.")
    elif mstate == "NO_API_KEY":
        st.warning("SportsGameOdds API key is unavailable to the R+A route; market-dependent comparisons stay locked.")
    elif mstate == "PROVIDER_ERROR":
        st.warning(f"SportsGameOdds R+A source check • {(market_meta or {}).get('error') or 'provider error'}")
    else:
        st.warning("R+A market rows are not fully paired/reconciled; exact-line hit-rate fields stay fail-closed.")

    st.caption("Step 3 history source • verified ESPN WNBA completed-game summaries • games strictly before selected slate • current team only • descriptive context.")
    prior._schedule_cards(schedule)
    if pool is None or pool.empty:
        st.info("Verified player pool is unavailable for this slate.")
        return

    row = prior._selected_row(pool)
    _player_card(day_str, row, reconciled, market_meta)
    prior._full_boards(pool, reconciled)
    if st.button("🔄 Refresh exact R+A markets", use_container_width=True, key=f"wnba_ra_v2_refresh_{day_str}"):
        market.clear_cache()
        st.rerun()

    st.info("🔒 STEP 3 BOUNDARY • Form/history is descriptive only. No R+A projection, Monte Carlo, fair odds, model edge, EV, qualification, reason-why engine or Top-5 ranking has been added yet.")


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]