"""WNBA Spread V1.6.3 — Top-5 Card Step 2 team-vs-team history.

Presentation/context-only wrapper over the verified V1.6.1 Spread production
route. V1.6.3 preserves the V1.6.2 Top-5 Card Step 1 identity/model snapshot,
then adds Step 2: verified current-season Team-vs-Team history for the exact
same one-candidate-per-game final Spread payload.

The V1.6.1 exact-day availability repair, independent margin projection,
SportsGameOdds spread market, analytical probability, exact 5,000,000-draw
Monte Carlo, convergence contract, candidate side, grading and production
ordering remain unchanged. H2H is descriptive only and never feeds probability,
projection, qualification or ranking math.
"""
from __future__ import annotations

from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v161 as prior
import wnba_schedule_v25 as schedule25
import wnba_players_v25 as players

base = prior.base  # genuine verified V1.6 production renderer

MODEL_VERSION = "WNBA SPREAD V1.6.3 • TOP-5 CARD STEP 2 TEAM VS TEAM HISTORY"

# Capture the genuine V1.6 Step-7 renderer before installing the presentation seam.
_ORIGINAL_STEP7 = base._render_step7


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _line(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.1f}".replace("+0.0", "PK").replace("-0.0", "PK")


def _odds(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x) or x == 0:
        return "—"
    return f"{x:+.0f}"


def _ev(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:+.1f}%"


def _fair(value) -> str:
    return _odds(value)


def _logo(team_id) -> str:
    try:
        return str(schedule25.logo_url(int(float(team_id))) or "")
    except Exception:
        return ""


def _is_home(row) -> bool:
    best = _norm(row.get("best_side"))
    home = _norm(row.get("home_team"))
    away = _norm(row.get("away_team"))
    if best and best == home:
        return True
    if best and best == away:
        return False
    return True


def _strength(row) -> tuple[str, str]:
    """Presentation label only; never feeds qualification or ranking math."""
    grade = str(row.get("grade") or "MONITOR").upper().strip()
    state = str(row.get("mc_state") or "MONITOR").upper().strip()
    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    ev = _num(row.get("best_ev"), np.nan)

    if state == "BLOCKED" or grade == "BLOCKED":
        return "BLOCKED", "blocked"
    if state != "READY" or grade == "MONITOR":
        return "MONITOR", "monitor"
    if grade != "QUALIFIED":
        return "NO PLAY", "nop"

    positive_ev = (not np.isfinite(ev)) or ev > 0
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.62 and edge >= 6.0 and positive_ev:
        return "ELITE", "elite"
    if np.isfinite(cover) and np.isfinite(edge) and cover >= 0.59 and edge >= 4.0 and positive_ev:
        return "STRONG", "strong"
    return "MEDIUM", "medium"


def _presentation_order(final: pd.DataFrame) -> pd.DataFrame:
    """Order only already-final one-per-game rows for visual Top-5 display."""
    if not isinstance(final, pd.DataFrame) or final.empty:
        return pd.DataFrame()
    work = final.copy()
    grade_rank = {"QUALIFIED": 4, "MONITOR": 3, "NO PLAY": 2, "BLOCKED": 0}
    grade_series = (
        work["grade"].astype(str).str.upper()
        if "grade" in work.columns
        else pd.Series("MONITOR", index=work.index)
    )
    state_series = (
        work["mc_state"].astype(str).str.upper()
        if "mc_state" in work.columns
        else pd.Series("MONITOR", index=work.index)
    )
    work["_grade_rank"] = grade_series.map(grade_rank).fillna(1)
    work["_ready_rank"] = state_series.eq("READY").astype(int)
    work["_cover_rank"] = pd.to_numeric(
        work["best_cover_no_push"] if "best_cover_no_push" in work.columns else np.nan,
        errors="coerce",
    ).fillna(-1.0)
    work["_edge_rank"] = pd.to_numeric(
        work["best_edge_pp"] if "best_edge_pp" in work.columns else np.nan,
        errors="coerce",
    ).fillna(-999.0)
    work["_ev_rank"] = pd.to_numeric(
        work["best_ev"] if "best_ev" in work.columns else np.nan,
        errors="coerce",
    ).fillna(-999.0)
    return (
        work.sort_values(
            ["_grade_rank", "_ready_rank", "_cover_rank", "_edge_rank", "_ev_rank"],
            ascending=False,
            kind="stable",
        )
        .head(5)
        .reset_index(drop=True)
    )


def _card(row, rank: int) -> str:
    away = str(row.get("away_team") or "Away")
    home = str(row.get("home_team") or "Home")
    best = str(row.get("best_side") or "Team")
    is_home = _is_home(row)

    selected_id = row.get("home_team_id") if is_home else row.get("away_team_id")
    opp_id = row.get("away_team_id") if is_home else row.get("home_team_id")
    opponent = away if is_home else home
    selected_logo = escape(_logo(selected_id), quote=True)
    opp_logo = escape(_logo(opp_id), quote=True)
    selected_img = f'<img src="{selected_logo}" alt="{escape(best)} logo">' if selected_logo else "🏀"
    opp_img = f'<img src="{opp_logo}" alt="{escape(opponent)} logo">' if opp_logo else "🏀"

    cover = _num(row.get("best_cover_no_push"), np.nan)
    edge = _num(row.get("best_edge_pp"), np.nan)
    market = _num(row.get("home_market_novig") if is_home else row.get("away_market_novig"), np.nan)
    fair = row.get("mc_home_fair_odds") if is_home else row.get("mc_away_fair_odds")
    push = _num(row.get("mc_push"), np.nan)
    mean_home = _num(row.get("projected_home_margin"), np.nan)
    side_margin = mean_home if is_home else (-mean_home if np.isfinite(mean_home) else np.nan)
    spread = _num(row.get("best_spread"), np.nan)
    cushion = side_margin + spread if np.isfinite(side_margin) and np.isfinite(spread) else np.nan

    strength, strength_class = _strength(row)
    grade = str(row.get("grade") or "MONITOR").upper()
    converged = bool(row.get("converged"))
    book = str(row.get("book") or "—")
    sims = int(_num(row.get("simulation_count"), 0) or 0)
    venue = str(row.get("venue") or "")
    tip = str(row.get("first_tip_et") or "")
    meta = " • ".join(x for x in [tip, venue] if x)

    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
    edge_text = "—" if not np.isfinite(edge) else f"{edge:+.1f} pp"
    cushion_text = "—" if not np.isfinite(cushion) else f"{cushion:+.1f} pts"
    mean_text = "—" if not np.isfinite(mean_home) else f"{mean_home:+.1f} pts"
    sims_text = f"{sims:,}" if sims else "—"

    return f"""
<div class="ks-spread163-card {('rank1' if rank == 1 else '')}">
  <div class="ks-spread163-rank">{medal} RANK {rank} • <span>{escape(grade)}</span> <b>DISPLAY ORDER ONLY</b></div>
  <div class="ks-spread163-matchup">
    <div class="ks-spread163-side">
      <div class="ks-spread163-logo">{selected_img}</div>
      <div><div class="ks-spread163-team">{escape(best)}</div><div class="ks-spread163-pick">{escape(best)} {_line(spread)}</div></div>
    </div>
    <div class="ks-spread163-vs">vs</div>
    <div class="ks-spread163-side opp">
      <div class="ks-spread163-logo">{opp_img}</div>
      <div><div class="ks-spread163-team">{escape(opponent)}</div><div class="ks-spread163-sub">{escape(away)} @ {escape(home)}</div></div>
    </div>
  </div>
  {f'<div class="ks-spread163-meta">{escape(meta)}</div>' if meta else ''}
  <div class="ks-spread163-prob">{_pct(cover)}</div>
  <div class="ks-spread163-probsub">5M MC NO-PUSH COVER PROBABILITY • FAIR {_fair(fair)}</div>
  <div class="ks-spread163-badges">
    <span class="strength {strength_class}">PICK STRENGTH • {escape(strength)}</span>
    <span>PRODUCTION GRADE • {escape(grade)}</span>
    <span class="{('pass' if converged else 'warn')}">CONVERGENCE • {('PASS' if converged else 'CHECK')}</span>
  </div>
  <div class="ks-spread163-grid">
    <div><small>EXACT MARKET</small><strong>{_line(spread)} ({_odds(row.get('best_price'))})</strong></div>
    <div><small>BOOK</small><strong>{escape(book)}</strong></div>
    <div><small>MC COVER</small><strong>{_pct(cover)}</strong></div>
    <div><small>MARKET NO-VIG</small><strong>{_pct(market)}</strong></div>
    <div><small>NO-VIG EDGE</small><strong>{edge_text}</strong></div>
    <div><small>EV</small><strong>{_ev(row.get('best_ev'))}</strong></div>
    <div><small>PROJECTED HOME MARGIN</small><strong>{mean_text}</strong></div>
    <div><small>PROJECTED COVER CUSHION</small><strong>{cushion_text}</strong></div>
    <div><small>PUSH PROBABILITY</small><strong>{_pct(push)}</strong></div>
    <div><small>SIMULATIONS</small><strong>{sims_text}</strong></div>
  </div>
  <div class="ks-spread163-note">CARD STEP 1 • PICK IDENTITY + VERIFIED MODEL SNAPSHOT • existing V1.6.1 side, line, probability, edge, EV, convergence and qualification only. No new spread projection or reranking is fed back into production.</div>
</div>
"""


@st.cache_data(ttl=1800, show_spinner=False, max_entries=128)
def _team_h2h_games(day_str: str, selected_team_id: int, opponent_team_id: int) -> pd.DataFrame:
    """Verified completed current-season H2H games before the selected slate date."""
    try:
        day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
        selected_team_id = int(selected_team_id)
        opponent_team_id = int(opponent_team_id)
    except Exception:
        return pd.DataFrame()

    if not selected_team_id or not opponent_team_id or selected_team_id == opponent_team_id:
        return pd.DataFrame()

    try:
        season = players._espn_season_schedule(pd.to_datetime(day_str).year)
    except Exception:
        season = pd.DataFrame()
    if not isinstance(season, pd.DataFrame) or season.empty:
        return pd.DataFrame()

    away = pd.to_numeric(season.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(season.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    dates = pd.to_datetime(season.get("game_date"), errors="coerce")
    status = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper()

    pair = (
        (away.eq(selected_team_id) & home.eq(opponent_team_id))
        | (away.eq(opponent_team_id) & home.eq(selected_team_id))
    )
    history = season.loc[pair & dates.lt(pd.to_datetime(day_str)) & status.eq("FINAL")].copy()
    if history.empty:
        return pd.DataFrame()

    history["_d"] = pd.to_datetime(history.get("game_date"), errors="coerce")
    history = history.sort_values("_d", ascending=False).drop_duplicates("game_id").head(10)

    rows = []
    for _, game in history.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if not isinstance(box, pd.DataFrame) or box.empty or "TEAM_ID" not in box.columns or "PTS" not in box.columns:
            continue

        team_ids = pd.to_numeric(box["TEAM_ID"], errors="coerce")
        pts = pd.to_numeric(box["PTS"], errors="coerce")
        selected_points = pts.loc[team_ids.eq(selected_team_id)].sum(min_count=1)
        opponent_points = pts.loc[team_ids.eq(opponent_team_id)].sum(min_count=1)
        if pd.isna(selected_points) or pd.isna(opponent_points):
            continue

        selected_home = int(_num(game.get("home_team_id"), 0) or 0) == selected_team_id
        rows.append({
            "game_id": gid,
            "game_date": gdate,
            "_DATE": pd.to_datetime(gdate, errors="coerce"),
            "selected_home": bool(selected_home),
            "selected_points": float(selected_points),
            "opponent_points": float(opponent_points),
            "margin": float(selected_points - opponent_points),
        })

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values("_DATE", ascending=False)
        .drop_duplicates("game_id", keep="first")
        .head(10)
        .reset_index(drop=True)
    )


def _h2h_summary(games: pd.DataFrame, today_spread: float) -> dict:
    if not isinstance(games, pd.DataFrame) or games.empty:
        return {
            "games": 0, "wins": 0, "losses": 0, "avg_margin": np.nan,
            "l3_margin": np.nan, "cover_hits": 0, "cover_losses": 0, "pushes": 0,
            "cover_rate": np.nan, "avg_cover_cushion": np.nan,
            "avg_for": np.nan, "avg_against": np.nan, "home_margin": np.nan,
            "away_margin": np.nan, "last_date": "—", "last_for": np.nan,
            "last_against": np.nan, "last_site": "—", "last3_margins": "—",
            "sample": "NO PRIOR MEETINGS",
        }

    margins = pd.to_numeric(games.get("margin"), errors="coerce").dropna()
    gp = int(len(margins))
    if gp == 0:
        return _h2h_summary(pd.DataFrame(), today_spread)

    spread = _num(today_spread, np.nan)
    if np.isfinite(spread):
        cover_cushion = margins + spread
        cover_hits = int((cover_cushion > 0).sum())
        cover_losses = int((cover_cushion < 0).sum())
        pushes = int((cover_cushion == 0).sum())
        denom = cover_hits + cover_losses
        cover_rate = cover_hits / denom if denom else np.nan
        avg_cover = float(cover_cushion.mean())
    else:
        cover_hits = cover_losses = pushes = 0
        cover_rate = avg_cover = np.nan

    home_mask = games.get("selected_home", pd.Series(False, index=games.index)).astype(bool)
    home_margins = pd.to_numeric(games.loc[home_mask, "margin"], errors="coerce").dropna()
    away_margins = pd.to_numeric(games.loc[~home_mask, "margin"], errors="coerce").dropna()
    last = games.iloc[0]
    last_date = last.get("_DATE")

    return {
        "games": gp,
        "wins": int((margins > 0).sum()),
        "losses": int((margins < 0).sum()),
        "avg_margin": float(margins.mean()),
        "l3_margin": float(pd.to_numeric(games.head(3)["margin"], errors="coerce").mean()) if gp >= 3 else np.nan,
        "cover_hits": cover_hits,
        "cover_losses": cover_losses,
        "pushes": pushes,
        "cover_rate": cover_rate,
        "avg_cover_cushion": avg_cover,
        "avg_for": float(pd.to_numeric(games["selected_points"], errors="coerce").mean()),
        "avg_against": float(pd.to_numeric(games["opponent_points"], errors="coerce").mean()),
        "home_margin": float(home_margins.mean()) if len(home_margins) else np.nan,
        "away_margin": float(away_margins.mean()) if len(away_margins) else np.nan,
        "last_date": last_date.strftime("%b %d") if pd.notna(last_date) else "—",
        "last_for": _num(last.get("selected_points"), np.nan),
        "last_against": _num(last.get("opponent_points"), np.nan),
        "last_site": "HOME" if bool(last.get("selected_home")) else "AWAY",
        "last3_margins": " • ".join(
            f"{float(x):+.0f}"
            for x in pd.to_numeric(games.head(3)["margin"], errors="coerce").dropna()
        ) or "—",
        "sample": "USEFUL CONTEXT" if gp >= 3 else "SMALL SAMPLE",
    }


def _h2h_context(summary: dict, today_spread: float) -> tuple[str, str]:
    gp = int(summary.get("games") or 0)
    rate = _num(summary.get("cover_rate"), np.nan)
    cushion = _num(summary.get("avg_cover_cushion"), np.nan)
    spread = _num(today_spread, np.nan)

    if gp == 0:
        return "NO PRIOR MEETINGS", "neutral"
    if gp < 3:
        return "SMALL SAMPLE • NO ADJUSTMENT", "warn"
    if not np.isfinite(spread):
        return "DATA LIMITED • NO ADJUSTMENT", "warn"
    if np.isfinite(rate) and np.isfinite(cushion):
        if rate >= 0.60 and cushion >= 2.0:
            return "HISTORY SUPPORTS PICK • DESCRIPTIVE", "good"
        if rate <= 0.40 and cushion <= -2.0:
            return "HISTORY CONCERN • DESCRIPTIVE", "bad"
    return "MIXED / NEUTRAL HISTORY", "neutral"


def _fmt_num(value, digits=1, plus=False) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    if plus:
        return f"{x:+.{digits}f}"
    return f"{x:.{digits}f}"


def _h2h_card(day_str: str, row, rank: int) -> tuple[str, pd.DataFrame]:
    is_home = _is_home(row)
    selected_id = int(_num(row.get("home_team_id") if is_home else row.get("away_team_id"), 0) or 0)
    opponent_id = int(_num(row.get("away_team_id") if is_home else row.get("home_team_id"), 0) or 0)
    selected = str(row.get("best_side") or ("Home" if is_home else "Away"))
    opponent = str((row.get("away_team") if is_home else row.get("home_team")) or "Opponent")
    spread = _num(row.get("best_spread"), np.nan)

    games = _team_h2h_games(str(day_str), selected_id, opponent_id)
    summary = _h2h_summary(games, spread)
    label, label_class = _h2h_context(summary, spread)

    gp = int(summary.get("games") or 0)
    covers = int(summary.get("cover_hits") or 0)
    losses = int(summary.get("cover_losses") or 0)
    pushes = int(summary.get("pushes") or 0)
    rate = _num(summary.get("cover_rate"), np.nan)
    rate_text = "—" if not np.isfinite(rate) else f"{covers}/{max(1, covers + losses)} • {100.0*rate:.0f}%"
    if pushes:
        rate_text += f" • {pushes} push"

    last_text = "—"
    if gp:
        last_text = (
            f"{_fmt_num(summary.get('last_for'),0)}–{_fmt_num(summary.get('last_against'),0)} "
            f"• {summary.get('last_site','—')} • {summary.get('last_date','—')}"
        )

    selected_logo = escape(_logo(selected_id), quote=True)
    opponent_logo = escape(_logo(opponent_id), quote=True)
    selected_img = f'<img src="{selected_logo}" alt="{escape(selected)} logo">' if selected_logo else "🏀"
    opponent_img = f'<img src="{opponent_logo}" alt="{escape(opponent)} logo">' if opponent_logo else "🏀"

    html = f"""
<div class="ks-spread163-h2h-card">
  <div class="ks-spread163-h2h-top"><span>🆚 STEP 2 • H2H #{rank}</span><span>{escape(selected)} {_line(spread)}</span></div>
  <div class="ks-spread163-h2h-id">
    <span>{selected_img}<b>{escape(selected)}</b></span>
    <em>vs</em>
    <span>{opponent_img}<b>{escape(opponent)}</b></span>
  </div>
  <div class="ks-spread163-h2h-read {label_class}">{escape(label)}</div>
  <div class="ks-spread163-h2h-grid">
    <div><small>H2H GP</small><strong>{gp}</strong></div>
    <div><small>STRAIGHT-UP RECORD</small><strong>{int(summary.get('wins') or 0)}–{int(summary.get('losses') or 0)}</strong></div>
    <div><small>AVG MARGIN</small><strong>{_fmt_num(summary.get('avg_margin'),1,True)}</strong></div>
    <div><small>L3 AVG MARGIN</small><strong>{_fmt_num(summary.get('l3_margin'),1,True)}</strong></div>
    <div><small>COVER TODAY LINE</small><strong>{rate_text}</strong></div>
    <div><small>AVG COVER CUSHION</small><strong>{_fmt_num(summary.get('avg_cover_cushion'),1,True)}</strong></div>
    <div><small>AVG SCORE</small><strong>{_fmt_num(summary.get('avg_for'))}–{_fmt_num(summary.get('avg_against'))}</strong></div>
    <div><small>HOME / AWAY MARGIN</small><strong>H {_fmt_num(summary.get('home_margin'),1,True)} • A {_fmt_num(summary.get('away_margin'),1,True)}</strong></div>
    <div><small>LAST 3 MARGINS</small><strong>{escape(str(summary.get('last3_margins') or '—'))}</strong></div>
    <div><small>LAST MEETING</small><strong>{escape(last_text)}</strong></div>
  </div>
  <div class="ks-spread163-h2h-sample {('good' if gp >= 3 else 'warn')}">{escape(str(summary.get('sample') or 'SMALL SAMPLE'))} • current-season prior completed meetings • descriptive only</div>
</div>
"""

    ledger = pd.DataFrame()
    if isinstance(games, pd.DataFrame) and not games.empty:
        ledger = games.copy()
        ledger["Date"] = pd.to_datetime(ledger["_DATE"], errors="coerce").dt.strftime("%b %d, %Y")
        ledger["Site"] = np.where(ledger["selected_home"].astype(bool), "HOME", "AWAY")
        ledger["Selected"] = selected
        ledger["Opponent"] = opponent
        ledger["Score"] = (
            pd.to_numeric(ledger["selected_points"], errors="coerce").round(0).astype("Int64").astype(str)
            + "–"
            + pd.to_numeric(ledger["opponent_points"], errors="coerce").round(0).astype("Int64").astype(str)
        )
        ledger["Margin"] = pd.to_numeric(ledger["margin"], errors="coerce")
        if np.isfinite(spread):
            ledger["Today spread"] = float(spread)
            ledger["Cover cushion"] = ledger["Margin"] + float(spread)
            ledger["Vs today line"] = np.select(
                [ledger["Cover cushion"] > 0, ledger["Cover cushion"] < 0],
                ["COVER", "MISS"],
                default="PUSH",
            )
        else:
            ledger["Today spread"] = np.nan
            ledger["Cover cushion"] = np.nan
            ledger["Vs today line"] = "—"
        ledger["Rank"] = rank
        ledger = ledger[
            ["Rank", "Date", "Site", "Selected", "Opponent", "Score", "Margin", "Today spread", "Cover cushion", "Vs today line"]
        ]
    return html, ledger


def _render_top5_step1(day_str: str, final: pd.DataFrame, meta: dict) -> None:
    st.markdown("### 🏆 Strongest WNBA Spread Picks — Top-5 Cards")
    st.caption(
        "CARD STEP 1 • Pick identity + model snapshot. Uses the existing V1.6 one-candidate-per-game final output after the actual 5M pass. "
        "Up to five are displayed; no fifth play is forced when the slate/model produces fewer candidates."
    )

    if not isinstance(final, pd.DataFrame) or final.empty:
        st.info("Top-5 Spread cards are waiting on the current Step-7 5,000,000-draw result. Run the verified Spread Monte Carlo above first.")
        return

    ranked = _presentation_order(final)
    if ranked.empty:
        st.info("No current final Spread candidates are available for Top-5 presentation.")
        return

    st.markdown(
        """
<style>
.ks-spread163-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 18px}
.ks-spread163-card{background:linear-gradient(145deg,#0b2034,#071521);border:1px solid #315c78;border-radius:22px;padding:17px;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.ks-spread163-card.rank1{border-color:#d5aa18;box-shadow:inset 5px 0 0 #d5aa18,0 8px 24px rgba(0,0,0,.20)}
.ks-spread163-rank{color:#66ddff;font-size:.62rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:12px}.ks-spread163-rank span{color:#9ef3d0}.ks-spread163-rank b{float:right;color:#6f8293;font-size:.48rem}
.ks-spread163-matchup{display:grid;grid-template-columns:1fr 26px 1fr;align-items:center;gap:7px}.ks-spread163-side{display:flex;align-items:center;gap:9px}.ks-spread163-side.opp{justify-content:flex-end;text-align:right}.ks-spread163-logo{width:54px;height:54px;display:flex;align-items:center;justify-content:center}.ks-spread163-logo img{max-width:54px;max-height:54px;object-fit:contain}.ks-spread163-team{color:#fff;font-size:.92rem;font-weight:950;line-height:1.15}.ks-spread163-pick{color:#ffe17a;font-size:.75rem;font-weight:900;margin-top:4px}.ks-spread163-sub{color:#7f95a7;font-size:.58rem;margin-top:4px}.ks-spread163-vs{text-align:center;color:#6e8394;font-size:.68rem;font-weight:900}.ks-spread163-meta{color:#7f95a7;font-size:.60rem;margin:9px 0 3px}
.ks-spread163-prob{font-size:2.75rem;font-weight:1000;color:#fff;line-height:1;margin-top:16px}.ks-spread163-probsub{font-size:.55rem;color:#7890a5;font-weight:900;letter-spacing:.035em;margin-top:5px}
.ks-spread163-badges{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.ks-spread163-badges span{border:1px solid #355873;background:#0b1824;color:#bed4e3;border-radius:999px;padding:6px 8px;font-size:.49rem;font-weight:950;letter-spacing:.035em}.ks-spread163-badges .elite,.ks-spread163-badges .strong,.ks-spread163-badges .pass{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread163-badges .medium{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread163-badges .monitor,.ks-spread163-badges .nop,.ks-spread163-badges .warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread163-badges .blocked{border-color:#7a3941;background:#35171b;color:#ff9aa5}
.ks-spread163-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.ks-spread163-grid div{background:#081522;border:1px solid #284b64;border-radius:11px;padding:9px}.ks-spread163-grid small{display:block;color:#718ba0;font-size:.47rem;font-weight:950;letter-spacing:.04em}.ks-spread163-grid strong{display:block;color:#f6fbff;font-size:.78rem;margin-top:3px}.ks-spread163-note{color:#6f8799;font-size:.54rem;line-height:1.45;margin-top:10px}
.ks-spread163-h2h-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 16px}.ks-spread163-h2h-card{background:linear-gradient(145deg,#10182b,#081521);border:1px solid #4f5f8a;border-radius:20px;padding:15px}.ks-spread163-h2h-top{display:flex;justify-content:space-between;gap:8px;color:#79d8ff;font-size:.60rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.ks-spread163-h2h-id{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:11px 0}.ks-spread163-h2h-id span{display:flex;align-items:center;gap:7px;color:#fff;font-size:.83rem}.ks-spread163-h2h-id img{width:34px;height:34px;object-fit:contain}.ks-spread163-h2h-id em{font-style:normal;color:#718ba0;font-size:.65rem;font-weight:900}.ks-spread163-h2h-read{border-radius:10px;padding:8px 9px;font-size:.60rem;font-weight:950;margin-bottom:9px}.ks-spread163-h2h-read.good{background:#0a3025;border:1px solid #1d7554;color:#75efb4}.ks-spread163-h2h-read.bad{background:#35171b;border:1px solid #7a3941;color:#ff9aa5}.ks-spread163-h2h-read.warn{background:#352516;border:1px solid #7c5832;color:#ffc984}.ks-spread163-h2h-read.neutral{background:#0b1824;border:1px solid #355873;color:#bed4e3}.ks-spread163-h2h-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.ks-spread163-h2h-grid div{background:#091827;border:1px solid #294b64;border-radius:10px;padding:8px}.ks-spread163-h2h-grid small{display:block;color:#718ba0;font-size:.46rem;font-weight:950;letter-spacing:.04em}.ks-spread163-h2h-grid strong{display:block;color:#f6fbff;font-size:.73rem;margin-top:3px}.ks-spread163-h2h-sample{margin-top:9px;font-size:.52rem;font-weight:850;color:#8ea8bd}.ks-spread163-h2h-sample.good{color:#75efb4}.ks-spread163-h2h-sample.warn{color:#ffc984}
@media(max-width:760px){.ks-spread163-wrap,.ks-spread163-h2h-wrap{grid-template-columns:1fr}.ks-spread163-rank b{float:none;display:block;margin-top:3px}.ks-spread163-logo{width:48px;height:48px}.ks-spread163-logo img{max-width:48px;max-height:48px}.ks-spread163-prob{font-size:2.45rem}}
</style>
        """,
        unsafe_allow_html=True,
    )

    cards = "".join(_card(row, i + 1) for i, (_, row) in enumerate(ranked.iterrows()))
    st.markdown(f'<div class="ks-spread163-wrap">{cards}</div>', unsafe_allow_html=True)

    qualified = int(
        ranked["grade"].astype(str).str.upper().eq("QUALIFIED").sum()
        if "grade" in ranked.columns else 0
    )
    st.caption(
        f"Current card set • {len(ranked)} one-per-game candidate(s) • {qualified} QUALIFIED • "
        "visual ordering uses existing production grade → MC cover → no-vig edge → EV only. Production payload and per-game selection are unchanged."
    )

    st.markdown("### 🆚 Step 2 — Team vs Team History")
    st.caption(
        "Verified current-season completed meetings before the selected slate date. Historical final margins are tested against TODAY'S exact selected spread for descriptive context only. "
        "Small samples are explicitly blocked from directional adjustment; H2H never changes the V1.6.1 projection, 5M Monte Carlo, qualification or Top-5 order."
    )

    h2h_cards = []
    ledgers = []
    for i, (_, row) in enumerate(ranked.iterrows(), start=1):
        html, ledger = _h2h_card(day_str, row, i)
        h2h_cards.append(html)
        if isinstance(ledger, pd.DataFrame) and not ledger.empty:
            ledgers.append(ledger)

    st.markdown(f'<div class="ks-spread163-h2h-wrap">{"".join(h2h_cards)}</div>', unsafe_allow_html=True)

    with st.expander("📋 Step 2 H2H game ledger — audit today's spread against prior meetings", expanded=False):
        if ledgers:
            audit = pd.concat(ledgers, ignore_index=True)
            st.dataframe(audit, use_container_width=True, hide_index=True)
        else:
            st.info("No verified current-season prior meetings were available for this Top-5 card set.")
        st.caption("Source • ESPN WNBA completed-game schedule + game summaries • prior games only • current-season descriptive evidence.")


def _render_step7_with_top5(day_str: str, pregame: pd.DataFrame, board: pd.DataFrame, probability_ready: bool):
    detail, final, meta = _ORIGINAL_STEP7(day_str, pregame, board, probability_ready)
    _render_top5_step1(day_str, final, meta if isinstance(meta, dict) else {})
    return detail, final, meta


def _install() -> None:
    # Replace only the V1.6 presentation seam. Returned detail/final/meta stay exact.
    base._render_step7 = _render_step7_with_top5


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎨 Spread V1.6.3 • Top-5 Card Steps 1–2 ACTIVE • verified model snapshot + current-season team-vs-team history • production model/ranking unchanged"
    )
    return prior.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION",
    "render_wnba_spread_hub",
    "_team_h2h_games",
    "_h2h_summary",
]
