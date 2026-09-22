"""WNBA Points V1.9.6 — visual Step 2.2: enhanced candidate cards + Why this pick.

Presentation-only wrapper over V1.9.5. Uses fields already produced by the validated
Points V1.9 projection/Monte Carlo stack to make Top Points candidates easier to
scan: season/L10/L5 scoring form, projected minutes/usage, pace, opponent recent
defense, position matchup, exact line, calibrated probability/edge and descriptive
H2H. Adds an expandable Why this pick? explanation for each ranked candidate.

No projection, SportsGameOdds, calibration, Monte Carlo, persistence, H2H math,
decision thresholds, frozen WNBA PRA V3.2.1 or frozen MLB V2.1.7 math is changed.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v195 as prior

MODEL_VERSION = "WNBA POINTS V1.9.6 • ENHANCED CANDIDATE CARDS"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
base = prior.base
hierarchy = prior.hierarchy
points = prior.points
core = prior.core


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix=""):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _projection_meta(day: str) -> pd.DataFrame:
    try:
        projections, _, _, _, _ = points._prepare(day)
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()

    work = projections.copy()
    wanted = [
        "game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name",
        "opponent_team_id", "opponent", "PROJ_MIN", "PROJ_USG", "USG_PCT",
        "PTS", "L10_PTS", "L5_PTS", "MIN", "L10_MIN", "L5_MIN",
        "RECENT_TEAM_L3_MIN", "RECENT_TEAM_L5_MIN", "expected_pace", "pace_factor",
        "defense_factor", "opp_drtg_l10", "opp_pa_l10", "defense_source",
        "position_factor", "position_bucket", "position_games", "position_source",
        "team_pts_factor", "pts_factor", "POSITION", "DESIGNATION", "ROLE_LABEL",
    ]
    text_cols = {
        "game_id", "player_key", "PLAYER_NAME", "team_name", "opponent",
        "defense_source", "position_bucket", "position_source", "POSITION",
        "DESIGNATION", "ROLE_LABEL",
    }
    for col in wanted:
        if col not in work.columns:
            work[col] = "" if col in text_cols else np.nan
    return work[wanted].drop_duplicates(["game_id", "player_key"], keep="first")


def _h2h_profile(day, row):
    try:
        return base._player_h2h_profile(
            day,
            row.get("PLAYER_ID"),
            row.get("player") or row.get("PLAYER_NAME"),
            int(_num(row.get("TEAM_ID"), 0)),
            int(_num(row.get("opponent_team_id"), 0)),
            row.get("line"),
        )
    except Exception:
        return {"games": 0, "sample": "UNAVAILABLE"}


def _reason_lines(row, h2h):
    reasons = []
    projection = _num(row.get("projection"), np.nan)
    line = _num(row.get("line"), np.nan)
    floor = _num(row.get("_floor"), np.nan)
    raw = _num(row.get("_raw"), np.nan)
    cedge = _num(row.get("_cedge"), np.nan)
    mins = _num(row.get("PROJ_MIN"), np.nan)
    usage = _num(row.get("PROJ_USG"), _num(row.get("USG_PCT"), np.nan))
    l5 = _num(row.get("L5_PTS"), np.nan)
    l10 = _num(row.get("L10_PTS"), np.nan)
    pace_factor = _num(row.get("pace_factor"), 1.0)
    defense_factor = _num(row.get("defense_factor"), 1.0)
    pos_factor = _num(row.get("position_factor"), 1.0)
    bucket = str(row.get("position_bucket") or "position").title()

    if pd.notna(projection) and pd.notna(line):
        delta = projection - line
        if delta >= 1.0:
            reasons.append(("plus", f"Projection is {delta:+.2f} points above the posted {line:.1f} line."))
        elif delta > 0:
            reasons.append(("neutral", f"Projection is slightly above the posted line ({delta:+.2f})."))
        else:
            reasons.append(("minus", f"Projection is {delta:+.2f} points versus the posted line."))

    if pd.notna(floor) and pd.notna(cedge):
        cls = "plus" if cedge >= 0.05 else ("neutral" if cedge > 0 else "minus")
        reasons.append((cls, f"Calibrated over floor {floor*100:.1f}% with {cedge*100:+.1f} pp edge after the uncertainty guard."))
    elif pd.notna(raw):
        reasons.append(("neutral", f"Raw Monte Carlo over probability is {raw*100:.1f}%."))

    if pd.notna(mins):
        if mins >= 30:
            reasons.append(("plus", f"Projected for {mins:.1f} minutes, a strong opportunity base."))
        elif mins >= 24:
            reasons.append(("neutral", f"Projected minutes are {mins:.1f}; usable but not an elite workload."))
        else:
            reasons.append(("minus", f"Projected minutes are only {mins:.1f}, increasing scoring volatility."))

    if pd.notna(usage):
        cls = "plus" if usage >= 25 else ("neutral" if usage >= 20 else "minus")
        reasons.append((cls, f"Projected/active scoring usage is {usage:.1f}%."))

    form_bits = []
    if pd.notna(l5):
        form_bits.append(f"L5 {l5:.1f}")
    if pd.notna(l10):
        form_bits.append(f"L10 {l10:.1f}")
    if form_bits:
        recent_anchor = l5 if pd.notna(l5) else l10
        cls = "plus" if pd.notna(line) and recent_anchor > line else "neutral"
        reasons.append((cls, "Recent scoring form: " + " • ".join(form_bits) + "."))

    if pace_factor >= 1.01:
        reasons.append(("plus", f"Pace environment is favorable ({pace_factor:.3f}×)."))
    elif pace_factor <= 0.99:
        reasons.append(("minus", f"Pace environment is slower than baseline ({pace_factor:.3f}×)."))
    else:
        reasons.append(("neutral", f"Pace is close to neutral ({pace_factor:.3f}×)."))

    if defense_factor >= 1.01:
        reasons.append(("plus", f"Opponent recent team defense gives a positive scoring adjustment ({defense_factor:.3f}×)."))
    elif defense_factor <= 0.99:
        reasons.append(("minus", f"Opponent recent team defense grades tougher than baseline ({defense_factor:.3f}×)."))
    else:
        reasons.append(("neutral", f"Opponent recent team-defense adjustment is near neutral ({defense_factor:.3f}×)."))

    if pos_factor >= 1.005:
        reasons.append(("plus", f"{bucket} matchup is favorable by opponent L10 positional scoring share ({pos_factor:.3f}×)."))
    elif pos_factor <= 0.995:
        reasons.append(("minus", f"{bucket} matchup is tougher by opponent L10 positional scoring share ({pos_factor:.3f}×)."))
    else:
        reasons.append(("neutral", f"{bucket} positional matchup is essentially neutral ({pos_factor:.3f}×)."))

    gp = int(h2h.get("games") or 0)
    h2h_avg = _num(h2h.get("avg_pts"), np.nan)
    if gp >= 3 and pd.notna(h2h_avg):
        cls = "plus" if pd.notna(line) and h2h_avg > line else "neutral"
        reasons.append((cls, f"Descriptive H2H: {h2h_avg:.1f} PPG in {gp} current-season meetings vs this opponent."))
    elif gp > 0:
        reasons.append(("neutral", f"H2H sample is only {gp} game(s), so it remains descriptive and is not weighted into the projection."))

    if not bool(row.get("lineup_ready")):
        reasons.append(("minus", "Starting five is still pending; qualified status remains MONITOR until explicit lineup confirmation."))
    else:
        reasons.append(("plus", "Starting lineup is explicitly confirmed."))
    return reasons


def _render_final_points_board_enhanced(day):
    rows = points.combined_rows(day)
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return
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
    work = work.sort_values(["_tier", "_floor", "_cedge", "data_quality"], ascending=[True, False, False, False])
    best = work.drop_duplicates(["player_key", "line"], keep="first").copy()
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

    meta = _projection_meta(day)
    if not meta.empty:
        qualified = qualified.merge(meta, on=["game_id", "player_key"], how="left")

    # V1.9.6 cards are rendered one-by-one so each card can own its Why-this-pick expander.
    for rank, (_, row) in enumerate(qualified.iterrows(), start=1):
        player_raw = str(row.get("player") or row.get("PLAYER_NAME") or "WNBA Player")
        player = escape(player_raw)
        team_id = row.get("TEAM_ID")
        opp_id = row.get("opponent_team_id")
        team = escape(str(row.get("team_name") or "Team"))
        opp = escape(str(row.get("opponent") or "Opponent"))
        photo = prior._photo_html(row.get("PLAYER_ID"), team_id, player_raw, "kyre-v196-photo")
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
        usage = _num(row.get("PROJ_USG"), _num(row.get("USG_PCT"), np.nan))
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
        h2h = _h2h_profile(day, row)
        h2h_gp = int(h2h.get("games") or 0)
        h2h_avg = _num(h2h.get("avg_pts"), np.nan)
        h2h_hit = _num(h2h.get("hit_rate"), np.nan)

        line_text = _fmt(line, 1)
        proj_text = _fmt(projection, 2)
        mean_text = _fmt(sim_mean, 2)
        floor_text = "—" if pd.isna(floor) else f"{floor*100:.1f}%"
        raw_text = "—" if pd.isna(raw) else f"{raw*100:.1f}%"
        nv_text = "—" if pd.isna(no_vig) else f"{no_vig*100:.1f}%"
        edge_text = "—" if pd.isna(cedge) else f"{cedge*100:+.1f} pp"
        h2h_text = "—" if not h2h_gp or pd.isna(h2h_avg) else f"{h2h_avg:.1f} ({h2h_gp} GP)"
        hit_text = "—" if pd.isna(h2h_hit) else f"{h2h_hit*100:.0f}%"

        st.markdown(
            f"""
<style>
.kyre-v196-card{{background:linear-gradient(145deg,#0b2034,#071421);border:1px solid #2b5877;border-radius:22px;padding:18px;margin:10px 0 0;box-shadow:0 8px 24px rgba(0,0,0,.18)}}
.kyre-v196-top{{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.68rem;font-weight:900;letter-spacing:.055em}}
.kyre-v196-id{{display:flex;align-items:center;gap:14px;margin:12px 0}}.kyre-v196-photo-shell{{width:88px;height:88px;min-width:88px;border-radius:50%;overflow:hidden;background:#091827;border:1px solid #376a8a;display:flex;align-items:center;justify-content:center}}.kyre-v196-photo{{width:100%;height:100%;object-fit:cover;object-position:center 18%}}.kyre-v196-photo.fallback{{object-fit:contain;padding:11px}}
.kyre-v196-name{{font-size:1.28rem;font-weight:950;color:#fff}}.kyre-v196-match{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#a2b8c8;font-size:.74rem;margin-top:5px}}.kyre-v196-match span{{display:flex;align-items:center;gap:5px}}.kyre-v196-match img{{width:24px;height:24px;object-fit:contain}}.kyre-v196-sub{{color:#819aae;font-size:.70rem;margin-top:5px}}
.kyre-v196-score{{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;margin:10px 0 12px}}.kyre-v196-prob{{font-size:2.25rem;font-weight:1000;color:#72e6ff}}.kyre-v196-prob small{{font-size:.55rem;color:#7893a8;letter-spacing:.04em}}.kyre-v196-proj{{font-size:.78rem;color:#b9cad6;padding-bottom:7px}}
.kyre-v196-stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}.kyre-v196-stats div{{background:#091827;border:1px solid #244760;border-radius:11px;padding:9px}}.kyre-v196-stats small{{display:block;color:#6f889d;font-size:.50rem;font-weight:850;letter-spacing:.045em}}.kyre-v196-stats strong{{display:block;color:#f5fbff;font-size:.80rem;margin-top:3px}}
.kyre-v196-strip{{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}}.kyre-v196-chip{{border:1px solid #2b536d;background:#0a1a29;color:#9fc2d7;border-radius:999px;padding:5px 8px;font-size:.58rem;font-weight:800}}
@media(max-width:760px){{.kyre-v196-stats{{grid-template-columns:repeat(2,minmax(0,1fr))}}.kyre-v196-photo-shell{{width:78px;height:78px;min-width:78px}}}}
</style>
<div class="kyre-v196-card">
  <div class="kyre-v196-top"><span>🏅 RANK {rank}</span><span>{decision}</span></div>
  <div class="kyre-v196-id">
    <div class="kyre-v196-photo-shell">{photo}</div>
    <div>
      <div class="kyre-v196-name">{player}</div>
      <div class="kyre-v196-match"><span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opp}</span></div>
      <div class="kyre-v196-sub">O {line_text} • {book} • {pass_source} • {lineup}</div>
    </div>
  </div>
  <div class="kyre-v196-score"><div class="kyre-v196-prob">{floor_text} <small>CALIBRATED FLOOR</small></div><div class="kyre-v196-proj">Proj {proj_text} PTS • MC mean {mean_text}</div></div>
  <div class="kyre-v196-stats">
    <div><small>RAW P(OVER)</small><strong>{raw_text}</strong></div>
    <div><small>NO-VIG O</small><strong>{nv_text}</strong></div>
    <div><small>CAL EDGE</small><strong>{edge_text}</strong></div>
    <div><small>PROJ MIN</small><strong>{_fmt(mins,1)}</strong></div>
    <div><small>USAGE</small><strong>{_fmt(usage,1,'%')}</strong></div>
    <div><small>SEASON / L10 / L5 PTS</small><strong>{_fmt(season_pts,1)} / {_fmt(l10_pts,1)} / {_fmt(l5_pts,1)}</strong></div>
    <div><small>PACE</small><strong>{_fmt(expected_pace,1)} • {pace_factor:.3f}×</strong></div>
    <div><small>OPP L10 DRTG</small><strong>{_fmt(opp_drtg,1)} • {defense_factor:.3f}×</strong></div>
    <div><small>POSITION MATCHUP</small><strong>{pos_bucket} • {pos_factor:.3f}×</strong></div>
    <div><small>H2H AVG</small><strong>{h2h_text}</strong></div>
    <div><small>H2H OVER TODAY LINE</small><strong>{hit_text}</strong></div>
    <div><small>POSTED LINE</small><strong>O {line_text}</strong></div>
  </div>
  <div class="kyre-v196-strip"><span class="kyre-v196-chip">📊 exact market</span><span class="kyre-v196-chip">🎲 Monte Carlo</span><span class="kyre-v196-chip">🎯 position matchup</span><span class="kyre-v196-chip">🆚 H2H descriptive</span></div>
</div>
            """,
            unsafe_allow_html=True,
        )

        reasons = _reason_lines(row, h2h)
        with st.expander(f"🧠 Why this pick? — {player_raw}", expanded=False):
            st.caption("Explanation of existing Points model inputs. This section does not change the projection or ranking.")
            for kind, text in reasons:
                icon = "✅" if kind == "plus" else ("⚠️" if kind == "minus" else "•")
                st.markdown(f"{icon} {text}")
            if h2h_gp < 3:
                st.caption("🆚 H2H small-sample note: prior opponent meetings are shown for context only and carry no model weight.")

    if (qualified["Decision"] == "⚠️ MONITOR").any():
        st.warning("⚠️ Starting fives are still pending for one or more qualified players. MONITOR candidates are not Final Ready until explicit lineup confirmation publishes.")
    st.caption("V1.9.6 visual layer only • all statistics above come from the existing validated Points inputs/results • no projection or Monte Carlo math changed.")


# Keep V1.9.5 headshot/H2H visuals and replace only the final candidate renderer.
hierarchy._render_final_points_board = _render_final_points_board_enhanced


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Reinstall on every Streamlit rerun because inherited wrappers can restore their renderer.
    hierarchy._render_final_points_board = _render_final_points_board_enhanced
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
