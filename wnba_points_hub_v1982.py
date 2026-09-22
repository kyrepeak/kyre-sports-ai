"""WNBA Points V1.9.8.2 — single rich-card renderer + safe usage/role display.

Presentation-only wrapper over V1.9.8.1. It fixes the remaining split-renderer
handoff that could show both the old compact V1.9.5 candidate cards and the rich
V1.9.6 cards on the same page. All inherited candidate-renderer reset points are
routed to one V1.9.8.2 renderer.

It also normalizes the player usage/role display without touching protected model
outputs. Verified/role-engine usage is preferred. When a player has no finite
usage value in the verified projection frame, a clearly labeled team-relative
production-role proxy is calculated from already-loaded season scoring/assist and
minute data for DISPLAY ONLY. NaN is never printed as a percentage.

No Points projection, SportsGameOdds grading, Monte Carlo, probability
calibration, persistence, H2H, frozen WNBA PRA V3.2.1 or frozen MLB V2.1.7 math
is changed. Existing protected 5M/10M summaries are reused.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v1981 as route

# V1.9.8.1 -> V1.9.8. `prior` is the real V1.9.8 module object loaded before
# app.py installs compatibility aliases in sys.modules.
prior = route.prior
enhanced = prior.enhanced
visual = prior.visual
points = prior.points
hierarchy = prior.hierarchy
core = enhanced.core
legacy_photos = enhanced.prior  # genuine V1.9.5 module object
base = enhanced.base

MODEL_VERSION = "WNBA POINTS V1.9.8.2 • SINGLE CARDS + SAFE USAGE"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH

_RENDER_MARKER = "_wnba_points_v1982_cards_rendered"


def _current_day() -> str:
    for key in ("wnba_points_date", "wnba_points_date_control"):
        value = st.session_state.get(key)
        if value is not None:
            try:
                return pd.to_datetime(value).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if not np.isfinite(x) else x
    except Exception:
        return default


def _usage_number(value):
    """Return a sane 0-100 usage percentage or NaN."""
    x = _num(value, np.nan)
    if pd.isna(x):
        return np.nan
    if 0 < abs(x) <= 1.5:
        x *= 100.0
    return float(x) if 0 < x <= 100 else np.nan


def _team_role_proxy(work: pd.DataFrame) -> pd.Series:
    """Existing V2.8.2-style production-role proxy, display only.

    Uses already-loaded season PTS/AST/MIN and preserves within-team role rank.
    It is never fed back into projection or Monte Carlo math.
    """
    proxy = pd.Series(np.nan, index=work.index, dtype=float)
    if work.empty or "TEAM_ID" not in work.columns:
        return proxy

    for _, team in work.groupby("TEAM_ID", dropna=False):
        if team.empty:
            continue
        mins = pd.to_numeric(team.get("MIN"), errors="coerce")
        if mins is None:
            mins = pd.Series(np.nan, index=team.index)
        for alt in ("L10_MIN", "L5_MIN", "PROJ_MIN"):
            if alt in team.columns:
                mins = mins.fillna(pd.to_numeric(team[alt], errors="coerce"))
        mins = mins.fillna(0).clip(lower=0.1)

        pts = pd.to_numeric(team.get("PTS"), errors="coerce")
        if pts is None:
            pts = pd.Series(np.nan, index=team.index)
        for alt in ("L10_PTS", "L5_PTS", "PROJ_PTS"):
            if alt in team.columns:
                pts = pts.fillna(pd.to_numeric(team[alt], errors="coerce"))
        pts = pts.fillna(0)

        ast = pd.to_numeric(team.get("AST"), errors="coerce")
        if ast is None:
            ast = pd.Series(np.nan, index=team.index)
        for alt in ("L10_AST", "L5_AST", "PROJ_AST"):
            if alt in team.columns:
                ast = ast.fillna(pd.to_numeric(team[alt], errors="coerce"))
        ast = ast.fillna(0)

        load = (pts + 1.35 * ast) / mins
        positive = load[load.gt(0) & np.isfinite(load)]
        if positive.empty:
            continue
        median = float(positive.median())
        load = load.where(load.gt(0) & np.isfinite(load), median).clip(lower=0.05)
        std = float(load.std(ddof=0)) if len(load) > 1 else 0.0
        z = (load - float(load.mean())) / max(std, 0.08)
        values = (20.0 + 4.5 * z).clip(8.0, 35.0)
        proxy.loc[team.index] = values.astype(float)
    return proxy


def _verified_opponent_map(schedule: pd.DataFrame) -> dict:
    out = {}
    if not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return out
    for _, game in schedule.iterrows():
        gid = str(game.get("game_id") or "")
        if not gid:
            continue
        try:
            away_id = int(float(game.get("away_team_id")))
        except Exception:
            away_id = 0
        try:
            home_id = int(float(game.get("home_team_id")))
        except Exception:
            home_id = 0
        away = str(game.get("away_team") or "").strip()
        home = str(game.get("home_team") or "").strip()
        if away_id:
            out[(gid, away_id)] = (home_id, home)
        if home_id:
            out[(gid, home_id)] = (away_id, away)
    return out


def _projection_meta_v1982(day: str) -> pd.DataFrame:
    """Authoritative visual metadata from the current Points projection frame."""
    try:
        projections, _, _, pmeta, _ = points._prepare(day)
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()

    work = projections.copy()
    schedule = (pmeta or {}).get("schedule") if isinstance(pmeta, dict) else None
    opp_map = _verified_opponent_map(schedule)

    # Build one finite display value. Nothing here is fed into Points model math.
    display_usage = pd.Series(np.nan, index=work.index, dtype=float)
    usage_source = pd.Series("N/A", index=work.index, dtype=object)
    usage_estimated = pd.Series(False, index=work.index, dtype=bool)

    priority = (
        ("PROJ_USG", "ROLE ENGINE"),
        ("BASE_USG", "ROLE ENGINE BASE"),
        ("USG_PCT", "VERIFIED USG"),
        ("L10_USG_PCT", "VERIFIED L10 USG"),
        ("L5_USG_PCT", "VERIFIED L5 USG"),
    )
    for idx, row in work.iterrows():
        for col, label in priority:
            value = _usage_number(row.get(col))
            if pd.notna(value):
                display_usage.at[idx] = value
                usage_source.at[idx] = label
                break

    proxy = _team_role_proxy(work)
    missing = display_usage.isna() & proxy.notna()
    display_usage.loc[missing] = proxy.loc[missing]
    usage_source.loc[missing] = "EST. ROLE PROXY • DISPLAY ONLY"
    usage_estimated.loc[missing] = True

    work["PROJ_USG"] = display_usage
    work["USG_DISPLAY_SOURCE"] = usage_source
    work["USG_DISPLAY_ESTIMATED"] = usage_estimated

    # Repair opponent text directly from the verified schedule if a projection
    # row ever arrives blank/generic.
    for idx, row in work.iterrows():
        current = str(row.get("opponent") or "").strip()
        if current and current.upper() not in {"OPPONENT", "N/A", "NONE", "NAN"}:
            continue
        try:
            tid = int(float(row.get("TEAM_ID")))
        except Exception:
            tid = 0
        pair = opp_map.get((str(row.get("game_id") or ""), tid))
        if pair:
            work.at[idx, "opponent_team_id"] = pair[0]
            work.at[idx, "opponent"] = pair[1]

    wanted = [
        "game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name",
        "opponent_team_id", "opponent", "PROJ_MIN", "PROJ_USG", "USG_PCT",
        "USG_DISPLAY_SOURCE", "USG_DISPLAY_ESTIMATED",
        "PTS", "L10_PTS", "L5_PTS", "MIN", "L10_MIN", "L5_MIN",
        "RECENT_TEAM_L3_MIN", "RECENT_TEAM_L5_MIN", "expected_pace", "pace_factor",
        "defense_factor", "opp_drtg_l10", "opp_pa_l10", "defense_source",
        "position_factor", "position_bucket", "position_games", "position_source",
        "team_pts_factor", "pts_factor", "POSITION", "DESIGNATION", "ROLE_LABEL",
    ]
    text_cols = {
        "game_id", "player_key", "PLAYER_NAME", "team_name", "opponent",
        "USG_DISPLAY_SOURCE", "defense_source", "position_bucket", "position_source",
        "POSITION", "DESIGNATION", "ROLE_LABEL",
    }
    for col in wanted:
        if col not in work.columns:
            work[col] = "" if col in text_cols else (False if col == "USG_DISPLAY_ESTIMATED" else np.nan)
    return work[wanted].drop_duplicates(["game_id", "player_key"], keep="first")


def _display_df(day: str) -> pd.DataFrame:
    try:
        rows = prior._ORIGINAL_COMBINED_ROWS(day)
    except Exception:
        rows = points.combined_rows(day)
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return pd.DataFrame()

    work = rows.copy()
    for col in ("model_over", "edge", "data_quality", "market_age"):
        work[col] = pd.to_numeric(work.get(col), errors="coerce")
    work["Decision"] = work.apply(core._calibrated_decision_tier, axis=1)
    work["_tier"] = work["Decision"].map({
        "🔥 BEST BET": 0, "✅ STRONG": 1, "⚠️ MONITOR": 2, "⛔ AVOID": 3,
    }).fillna(9)
    cal = work.apply(core._calibrated_values, axis=1, result_type="expand")
    cal.columns = ["_raw", "_buffer", "_floor", "_cedge"]
    for col in cal.columns:
        work[col] = cal[col].values
    work = work.sort_values(
        ["_tier", "_floor", "_cedge", "data_quality"],
        ascending=[True, False, False, False],
    )
    best = work.drop_duplicates(["player_key", "line"], keep="first").copy()

    meta = _projection_meta_v1982(day)
    if not meta.empty:
        keys = ["game_id", "player_key"]
        # Projection metadata is authoritative for visual identity/context.
        collisions = [c for c in meta.columns if c not in keys and c in best.columns]
        if collisions:
            best = best.drop(columns=collisions)
        best = best.merge(meta, on=keys, how="left")
    return best


def _fmt(value, digits=1, suffix=""):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _pct01(value):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x*100:.1f}%"


def _render_final_points_board_v1982(day):
    day = pd.to_datetime(day).strftime("%Y-%m-%d")
    st.session_state[_RENDER_MARKER] = day
    # Satisfy V1.9.8's fallback guard too, so the old enhanced renderer cannot
    # render a second copy after this one.
    try:
        st.session_state[prior._RENDER_MARKER] = day
    except Exception:
        pass

    best = _display_df(day)
    if best.empty:
        return
    qualified = best[best["Decision"].isin(["🔥 BEST BET", "✅ STRONG", "⚠️ MONITOR"])].head(5)

    st.markdown("### 🏆 Top Points Candidates")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BEST BET", int((best["Decision"] == "🔥 BEST BET").sum()))
    c2.metric("STRONG", int((best["Decision"] == "✅ STRONG").sum()))
    c3.metric("MONITOR", int((best["Decision"] == "⚠️ MONITOR").sum()))
    c4.metric("AVOID", int((best["Decision"] == "⛔ AVOID").sum()))

    if qualified.empty:
        st.info("No qualified Points candidate currently clears the calibrated final hierarchy. Nothing is forced.")
        return

    st.caption("🎯 One authoritative candidate renderer • protected 5M/10M results • verified opponent identity • usage never prints NaN")

    for rank, (_, row) in enumerate(qualified.iterrows(), start=1):
        player_raw = str(row.get("player") or row.get("PLAYER_NAME") or "WNBA Player")
        player = escape(player_raw)
        team_id = row.get("TEAM_ID")
        opp_id = row.get("opponent_team_id")
        team = escape(str(row.get("team_name") or "Team"))
        opp_raw = str(row.get("opponent") or "").strip()
        opp = escape(opp_raw if opp_raw and opp_raw.upper() != "OPPONENT" else "Opponent pending")

        photo = legacy_photos._photo_html(row.get("PLAYER_ID"), team_id, player_raw, "kyre-v1982-photo")
        team_logo = escape(base._logo(team_id), quote=True)
        opp_logo = escape(base._logo(opp_id), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"

        decision = escape(str(row.get("Decision") or "⚠️ MONITOR"))
        line = _num(row.get("line"), np.nan)
        projection = _num(row.get("projection"), np.nan)
        sim_mean = _num(row.get("sim_mean"), np.nan)
        raw = _num(row.get("_raw"), np.nan)
        floor = _num(row.get("_floor"), np.nan)
        cedge = _num(row.get("_cedge"), np.nan)
        no_vig = _num(row.get("no_vig_over"), np.nan)
        mins = _num(row.get("PROJ_MIN"), np.nan)
        usage = _usage_number(row.get("PROJ_USG"))
        usage_est = bool(row.get("USG_DISPLAY_ESTIMATED")) if pd.notna(row.get("USG_DISPLAY_ESTIMATED")) else False
        usage_source = str(row.get("USG_DISPLAY_SOURCE") or "N/A")
        usage_text = "N/A" if pd.isna(usage) else (("~" if usage_est else "") + f"{usage:.1f}%")
        usage_tag = "EST ROLE" if usage_est else ("ROLE ENGINE" if pd.notna(usage) else "NO VERIFIED VALUE")

        season_pts = _num(row.get("PTS"), np.nan)
        l10_pts = _num(row.get("L10_PTS"), np.nan)
        l5_pts = _num(row.get("L5_PTS"), np.nan)
        expected_pace = _num(row.get("expected_pace"), np.nan)
        pace_factor = _num(row.get("pace_factor"), 1.0)
        opp_drtg = _num(row.get("opp_drtg_l10"), np.nan)
        defense_factor = _num(row.get("defense_factor"), 1.0)
        pos_factor = _num(row.get("position_factor"), 1.0)
        pos_bucket = escape(str(row.get("position_bucket") or row.get("POSITION") or "—"))
        book = escape(str(row.get("book") or "Sportsbook"))
        pass_source = escape(str(row.get("pass_source") or "5M"))
        lineup = "CONFIRMED" if bool(row.get("lineup_ready")) else "LINEUP PENDING"

        try:
            h2h = enhanced._h2h_profile(day, row)
        except Exception:
            h2h = {"games": 0, "sample": "UNAVAILABLE"}
        h2h_gp = int(h2h.get("games") or 0)
        h2h_avg = _num(h2h.get("avg_pts"), np.nan)
        h2h_hit = _num(h2h.get("hit_rate"), np.nan)

        line_text = _fmt(line, 1)
        floor_text = _pct01(floor)
        raw_text = _pct01(raw)
        nv_text = _pct01(no_vig)
        edge_text = "—" if pd.isna(cedge) else f"{cedge*100:+.1f} pp"
        h2h_text = "—" if not h2h_gp or pd.isna(h2h_avg) else f"{h2h_avg:.1f} ({h2h_gp} GP)"
        hit_text = "—" if pd.isna(h2h_hit) else f"{h2h_hit*100:.0f}%"

        st.markdown(
            f"""
<style>
.kyre-v1982-card{{background:linear-gradient(145deg,#0b2034,#071421);border:1px solid #2b5877;border-radius:22px;padding:18px;margin:12px 0 0;box-shadow:0 8px 24px rgba(0,0,0,.18)}}
.kyre-v1982-top{{display:flex;justify-content:space-between;gap:10px;color:#65ddff;font-size:.68rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}}
.kyre-v1982-id{{display:flex;align-items:center;gap:15px;margin:13px 0 10px}}.kyre-v1982-photo-shell{{width:88px;height:88px;min-width:88px;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 50% 35%,#183b59,#071522 72%);border:1px solid #376a8a;display:flex;align-items:center;justify-content:center}}.kyre-v1982-photo{{width:100%;height:100%;object-fit:cover;object-position:center 18%}}.kyre-v1982-photo.fallback{{object-fit:contain;padding:11px}}
.kyre-v1982-name{{font-size:1.35rem;font-weight:950;color:white}}.kyre-v1982-match{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:#a4bacb;font-size:.77rem;margin-top:5px}}.kyre-v1982-match span{{display:flex;align-items:center;gap:5px}}.kyre-v1982-match img{{width:24px;height:24px;object-fit:contain}}.kyre-v1982-book{{color:#7f9ab0;font-size:.70rem;margin-top:6px}}
.kyre-v1982-prob{{font-size:2.35rem;font-weight:1000;color:#71e7ff;margin:12px 0}}.kyre-v1982-prob small{{font-size:.56rem;color:#7893a8;letter-spacing:.05em}}
.kyre-v1982-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}.kyre-v1982-grid div{{background:#091827;border:1px solid #244760;border-radius:11px;padding:9px}}.kyre-v1982-grid small{{display:block;color:#6f899e;font-size:.50rem;font-weight:900;letter-spacing:.05em}}.kyre-v1982-grid strong{{display:block;color:#f5fbff;font-size:.82rem;margin-top:4px}}.kyre-v1982-grid em{{display:block;color:#70a9c7;font-style:normal;font-size:.48rem;font-weight:850;margin-top:2px}}
.kyre-v1982-strip{{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}}.kyre-v1982-chip{{border:1px solid #2a5876;border-radius:999px;padding:4px 8px;color:#b8d1df;font-size:.58rem;font-weight:850}}
@media(max-width:760px){{.kyre-v1982-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.kyre-v1982-photo-shell{{width:78px;height:78px;min-width:78px}}}}
</style>
<div class="kyre-v1982-card">
  <div class="kyre-v1982-top"><span>🏅 RANK {rank}</span><span>{decision}</span></div>
  <div class="kyre-v1982-id">
    <div class="kyre-v1982-photo-shell">{photo}</div>
    <div>
      <div class="kyre-v1982-name">{player}</div>
      <div class="kyre-v1982-match"><span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opp}</span></div>
      <div class="kyre-v1982-book">O {line_text} • {book} • {pass_source} • {lineup}</div>
    </div>
  </div>
  <div class="kyre-v1982-prob">{floor_text} <small>CALIBRATED FLOOR</small></div>
  <div class="kyre-v1982-grid">
    <div><small>PROJ PTS</small><strong>{_fmt(projection,2)}</strong></div>
    <div><small>MC MEAN</small><strong>{_fmt(sim_mean,2)}</strong></div>
    <div><small>RAW P(OVER)</small><strong>{raw_text}</strong></div>
    <div><small>NO-VIG O</small><strong>{nv_text}</strong></div>
    <div><small>CAL EDGE</small><strong>{edge_text}</strong></div>
    <div><small>PROJ MIN</small><strong>{_fmt(mins,1)}</strong></div>
    <div><small>USAGE / ROLE</small><strong>{usage_text}</strong><em>{usage_tag}</em></div>
    <div><small>SEASON / L10 / L5 PTS</small><strong>{_fmt(season_pts,1)} / {_fmt(l10_pts,1)} / {_fmt(l5_pts,1)}</strong></div>
    <div><small>PACE</small><strong>{_fmt(expected_pace,1)} • {pace_factor:.3f}×</strong></div>
    <div><small>OPP L10 DRTG</small><strong>{_fmt(opp_drtg,1)} • {defense_factor:.3f}×</strong></div>
    <div><small>POSITION MATCHUP</small><strong>{pos_bucket} • {pos_factor:.3f}×</strong></div>
    <div><small>H2H AVG / OVER LINE</small><strong>{h2h_text} • {hit_text}</strong></div>
  </div>
  <div class="kyre-v1982-strip"><span class="kyre-v1982-chip">📊 exact market</span><span class="kyre-v1982-chip">🎲 protected Monte Carlo</span><span class="kyre-v1982-chip">🎯 position matchup</span><span class="kyre-v1982-chip">🆚 H2H descriptive</span></div>
</div>
            """,
            unsafe_allow_html=True,
        )

        reason_row = row.copy()
        if usage_est:
            # Do not let an estimated display-only role proxy read like verified
            # model usage inside the inherited explanation helper.
            reason_row["PROJ_USG"] = np.nan
            reason_row["USG_PCT"] = np.nan
        try:
            reasons = enhanced._reason_lines(reason_row, h2h)
        except Exception:
            reasons = []
        with st.expander(f"🧠 Why this pick? — {player_raw}", expanded=False):
            st.caption("Explanation of existing Points model inputs. Sportsbook prices do not move the projection.")
            for kind, text in reasons:
                icon = "✅" if kind == "plus" else ("⚠️" if kind == "minus" else "•")
                st.markdown(f"{icon} {text}")
            if usage_est and pd.notna(usage):
                st.markdown(f"• Display-only role estimate: ~{usage:.1f}% from the player's verified season scoring/assist/minute role relative to teammates.")
                st.caption("This estimated role proxy is informational only and did NOT change the protected projection or Monte Carlo result.")
            elif pd.notna(usage):
                st.caption(f"Usage source: {usage_source}.")
            else:
                st.caption("Usage/role value is unavailable; the card intentionally shows N/A rather than a fabricated percentage.")
            if h2h_gp < 3:
                st.caption("🆚 H2H small-sample note: prior opponent meetings are context only and carry no model weight.")

    if (qualified["Decision"] == "⚠️ MONITOR").any():
        st.warning("⚠️ Starting fives are still pending for one or more qualified players. MONITOR candidates are not Final Ready until explicit lineup confirmation publishes.")
    st.caption("V1.9.8.2 display calibration • one candidate renderer • finite usage/role display • protected simulation and probability math unchanged.")


def _visual_header_v1982(day, slate):
    visual._visual_css()
    try:
        rows = prior._ORIGINAL_COMBINED_ROWS(day)
    except Exception:
        rows = pd.DataFrame()
    distributions = 0
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        keys = [c for c in ("game_id", "player_key", "line") if c in rows.columns]
        distributions = int(rows[keys].drop_duplicates().shape[0]) if len(keys) == 3 else int(len(rows))

    st.markdown(
        """
<div class="kyre-wnba-hero">
  <div class="kyre-wnba-kicker">KYRE SPORTS AI • WNBA POINTS • VISUAL COMMAND CENTER</div>
  <div class="kyre-wnba-title">🏀 WNBA Points Command Center — V1.9.8.2</div>
  <div class="kyre-wnba-sub">Display calibration complete • one authoritative Top Points renderer • verified opponent names • safe usage/role sourcing • no NaN percentages • player headshots • team logos • descriptive H2H • expandable Why this pick? • protected 5M/10M simulation reuse. Production model math is unchanged.</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(slate.get("total") or 0))
    c2.metric("Upcoming", int(slate.get("upcoming") or 0))
    pairs = slate.get("pairs")
    market_players = 0 if not isinstance(pairs, pd.DataFrame) or pairs.empty else int(pairs["player_key"].nunique())
    c3.metric("Points market players", market_players)
    c4.metric("Protected distributions", distributions)

    diag = slate.get("diag") or {}
    state = str(diag.get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE", "VERIFIED_OFF_DAY"}:
        st.success(f"✅ VERIFIED WNBA POINTS SLATE • {day} • {int(slate.get('total') or 0)} game(s) • Eastern Time")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")
    st.info("🧹 V1.9.8.2 • duplicate candidate renderer removed • opponent identity schedule-verified • missing usage is safely labeled/estimated for display only • no simulation rerun.")
    visual._render_matchup_cards(day)
    st.markdown(
        '<div class="kyre-engine-note">⚙️ <b>Production engine room below:</b> roster, minutes, history, matchup, Monte Carlo and calibration checks stay visible for auditability. The visual layer does not alter any projection.</div>',
        unsafe_allow_html=True,
    )


def _install_v1982_hooks():
    # V1.9.8 reads this global when it installs the visual header.
    prior._visual_header_v198 = _visual_header_v1982

    # Critical duplicate-render fix: V1.9.5 resets the hierarchy to this exact
    # global on every inherited rerun. Replacing the global itself means that
    # reset now points to our single rich renderer rather than the compact one.
    legacy_photos._render_final_points_board_with_photos = _render_final_points_board_v1982

    # Cover every higher-level route too.
    enhanced._render_final_points_board_enhanced = _render_final_points_board_v1982
    hierarchy._render_final_points_board = _render_final_points_board_v1982
    try:
        visual.core.clean.v19._render_final_points_board = _render_final_points_board_v1982
    except Exception:
        pass
    try:
        visual.core.v19._render_final_points_board = _render_final_points_board_v1982
    except Exception:
        pass


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = _current_day()
    st.session_state[_RENDER_MARKER] = ""
    _install_v1982_hooks()
    result = route.render_wnba_points_hub(section_header, status_info, team_logo, h)
    # The normal inherited path should render once. If a future wrapper bypasses
    # every hook, render exactly one recovery copy from the protected rows.
    if st.session_state.get(_RENDER_MARKER) != day:
        st.divider()
        st.caption("🧹 V1.9.8.2 protected-result recovery renderer • no new simulation is run.")
        _render_final_points_board_v1982(day)
    return result


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
