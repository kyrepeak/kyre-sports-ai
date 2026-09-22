"""WNBA Points V1.9.8.4.15 — embedded Step 7 shot volume + scoring efficiency.

Presentation/context-only wrapper over V1.9.8.4.14. The validated V1.9.8.4.5
Points projection, sportsbook transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and sanity quarantine remain
unchanged.

Step 7 is restricted to the same Top-5 candidates already rendered by Steps
2-6. It exposes verified WNBA Base-stat shooting volume/efficiency for season,
L10 and L5 windows when that feed is available. It does not apply another shot
volume or efficiency adjustment and cannot rerank the Top 5.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198414 as prior
import wnba_data_v232 as data_transport

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.15 • STEP 7 SHOT VOLUME + EFFICIENCY"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP6_BLOCK = prior._step6_block


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    if abs(x) <= 1.5:
        x *= 100.0
    return f"{x:.{digits}f}%"


@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def _shooting_tables(season: int) -> dict:
    """Fetch league-wide verified Base shooting tables once per window."""
    out = {}
    for label, last_n in (("season", 0), ("l10", 10), ("l5", 5)):
        try:
            df = data_transport._fetch_player_stats(int(season), int(last_n))
        except Exception:
            df = pd.DataFrame()
        if df is None:
            df = pd.DataFrame()
        out[label] = df
    return out


def _player_row(frame: pd.DataFrame, player_id: int) -> dict:
    if frame is None or frame.empty or "PLAYER_ID" not in frame.columns:
        return {}
    ids = pd.to_numeric(frame["PLAYER_ID"], errors="coerce")
    part = frame.loc[ids.eq(int(player_id))]
    if part.empty:
        return {}
    return part.iloc[0].to_dict()


def _profile(row: dict) -> dict:
    if not row:
        return {}
    p = {key: _num(row.get(key), np.nan) for key in (
        "GP", "MIN", "PTS", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A",
        "FG3_PCT", "FTM", "FTA", "FT_PCT"
    )}
    fga, fta = p.get("FGA"), p.get("FTA")
    fgm, fg3m = p.get("FGM"), p.get("FG3M")
    pts = p.get("PTS")
    if pd.notna(fga) and fga > 0 and pd.notna(fgm):
        p["EFG_PCT"] = (fgm + 0.5 * (fg3m if pd.notna(fg3m) else 0.0)) / fga
        p["FG3_SHARE"] = (p.get("FG3A") / fga) if pd.notna(p.get("FG3A")) else np.nan
        p["FTA_RATE"] = (fta / fga) if pd.notna(fta) else np.nan
    else:
        p["EFG_PCT"] = p["FG3_SHARE"] = p["FTA_RATE"] = np.nan
    denom = 2.0 * (fga + 0.44 * fta) if pd.notna(fga) and pd.notna(fta) else np.nan
    p["TS_PCT"] = pts / denom if pd.notna(pts) and pd.notna(denom) and denom > 0 else np.nan
    p["SHOT_OPP"] = fga + 0.44 * fta if pd.notna(fga) and pd.notna(fta) else np.nan
    p["SOURCE"] = str(row.get("DATA_SOURCE") or "WNBA Stats Base")
    return p


def _trend_text(l10: dict, l5: dict) -> tuple[str, str, float, float]:
    fga_delta = _num(l5.get("FGA"), np.nan) - _num(l10.get("FGA"), np.nan)
    ts_delta = _num(l5.get("TS_PCT"), np.nan) - _num(l10.get("TS_PCT"), np.nan)

    if pd.isna(fga_delta):
        volume = "DATA LIMITED"
    elif fga_delta >= 1.5:
        volume = f"RISING VOLUME • L5 {fga_delta:+.1f} FGA vs L10"
    elif fga_delta <= -1.5:
        volume = f"FALLING VOLUME • L5 {fga_delta:+.1f} FGA vs L10"
    else:
        volume = f"STABLE VOLUME • L5 {fga_delta:+.1f} FGA vs L10"

    if pd.isna(ts_delta):
        efficiency = "DATA LIMITED"
    elif ts_delta >= 0.04:
        efficiency = f"HOTTER EFFICIENCY • L5 TS {ts_delta*100:+.1f} pp vs L10"
    elif ts_delta <= -0.04:
        efficiency = f"COOLER EFFICIENCY • L5 TS {ts_delta*100:+.1f} pp vs L10"
    else:
        efficiency = f"STABLE EFFICIENCY • L5 TS {ts_delta*100:+.1f} pp vs L10"
    return volume, efficiency, fga_delta, ts_delta


def _grade(season: dict, l10: dict, l5: dict):
    volume, efficiency, fga_delta, ts_delta = _trend_text(l10, l5)
    score = 0
    evidence = 0

    if pd.notna(fga_delta):
        evidence += 1
        score += 2 if fga_delta >= 2.0 else 1 if fga_delta >= 0.8 else -2 if fga_delta <= -2.0 else -1 if fga_delta <= -0.8 else 0
    if pd.notna(ts_delta):
        evidence += 1
        score += 2 if ts_delta >= 0.05 else 1 if ts_delta >= 0.02 else -2 if ts_delta <= -0.05 else -1 if ts_delta <= -0.02 else 0

    fta_delta = _num(l5.get("FTA"), np.nan) - _num(l10.get("FTA"), np.nan)
    if pd.notna(fta_delta):
        evidence += 1
        score += 1 if fta_delta >= 1.0 else -1 if fta_delta <= -1.0 else 0

    fg3_delta = _num(l5.get("FG3A"), np.nan) - _num(l10.get("FG3A"), np.nan)
    if pd.notna(fg3_delta):
        evidence += 1
        score += 1 if fg3_delta >= 1.0 else -1 if fg3_delta <= -1.0 else 0

    if evidence < 2:
        return "DATA LIMITED", "limited", "NEUTRAL", score, evidence, volume, efficiency
    if score >= 4:
        return "ELITE SCORING PROFILE", "elite", "SUPPORTS SCORER", score, evidence, volume, efficiency
    if score >= 2:
        return "STRONG PROFILE", "strong", "SUPPORTS SCORER", score, evidence, volume, efficiency
    if score <= -4:
        return "HARD SCORING PROFILE", "hard", "HURTS SCORER", score, evidence, volume, efficiency
    if score <= -2:
        return "TOUGH PROFILE", "tough", "HURTS SCORER", score, evidence, volume, efficiency
    return "NEUTRAL", "neutral", "NEUTRAL", score, evidence, volume, efficiency


def _step7_block(day: str, data: dict) -> str:
    try:
        season = int(pd.to_datetime(day).year)
        player_id = int(float(data.get("PLAYER_ID")))
    except Exception:
        season, player_id = 0, 0

    tables = _shooting_tables(season) if season and player_id else {}
    season_p = _profile(_player_row(tables.get("season", pd.DataFrame()), player_id)) if tables else {}
    l10_p = _profile(_player_row(tables.get("l10", pd.DataFrame()), player_id)) if tables else {}
    l5_p = _profile(_player_row(tables.get("l5", pd.DataFrame()), player_id)) if tables else {}

    grade, grade_class, verdict, score, evidence_n, volume_trend, eff_trend = _grade(season_p, l10_p, l5_p)
    source = escape(str(l5_p.get("SOURCE") or l10_p.get("SOURCE") or season_p.get("SOURCE") or "VERIFIED SHOOTING FEED UNAVAILABLE"))

    html = f"""
<style>
.kyre-v198415-step7{{background:#171a25;border:1px solid #6b6f98;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198415-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#b8bfff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198415-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198415-grade.elite,.kyre-v198415-grade.strong{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198415-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
.kyre-v198415-grade.tough{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
.kyre-v198415-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198415-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198415-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198415-grid div{{border:1px solid #4e5275;border-radius:10px;padding:8px;background:#0d1019}}
.kyre-v198415-grid small{{display:block;color:#8d93bb;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198415-grid strong{{display:block;color:#f5f6ff;font-size:.84rem;margin-top:3px}}
.kyre-v198415-detail{{background:#0d1019;border:1px solid #4e5275;border-radius:10px;padding:8px 9px;color:#dcdef2;font-size:.68rem;line-height:1.55;margin-top:8px}}
.kyre-v198415-detail b{{color:#b8bfff}}
.kyre-v198415-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#171b2d;border:1px solid #6b6f98;color:#f1f2ff;font-size:.68rem;font-weight:850}}
.kyre-v198415-note{{color:#8185a0;font-size:.57rem;line-height:1.4;margin-top:7px}}
@media(max-width:760px){{.kyre-v198415-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198415-step7">
<div class="kyre-v198415-head"><span>STEP 7 • SHOT VOLUME + SCORING EFFICIENCY</span><span class="kyre-v198415-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198415-grid">
<div><small>SEASON FGA</small><strong>{_fmt(season_p.get('FGA'))}</strong></div><div><small>L10 FGA</small><strong>{_fmt(l10_p.get('FGA'))}</strong></div>
<div><small>L5 FGA</small><strong>{_fmt(l5_p.get('FGA'))}</strong></div><div><small>L5 SHOT OPPORTUNITY</small><strong>{_fmt(l5_p.get('SHOT_OPP'))}</strong></div>
<div><small>SEASON 3PA</small><strong>{_fmt(season_p.get('FG3A'))}</strong></div><div><small>L10 3PA</small><strong>{_fmt(l10_p.get('FG3A'))}</strong></div>
<div><small>L5 3PA</small><strong>{_fmt(l5_p.get('FG3A'))}</strong></div><div><small>L5 3PA SHARE</small><strong>{_pct(l5_p.get('FG3_SHARE'))}</strong></div>
<div><small>SEASON FTA</small><strong>{_fmt(season_p.get('FTA'))}</strong></div><div><small>L10 FTA</small><strong>{_fmt(l10_p.get('FTA'))}</strong></div>
<div><small>L5 FTA</small><strong>{_fmt(l5_p.get('FTA'))}</strong></div><div><small>L5 FTA RATE</small><strong>{_pct(l5_p.get('FTA_RATE'))}</strong></div>
<div><small>SEASON FG%</small><strong>{_pct(season_p.get('FG_PCT'))}</strong></div><div><small>L10 FG%</small><strong>{_pct(l10_p.get('FG_PCT'))}</strong></div>
<div><small>L5 FG%</small><strong>{_pct(l5_p.get('FG_PCT'))}</strong></div><div><small>L5 3P%</small><strong>{_pct(l5_p.get('FG3_PCT'))}</strong></div>
<div><small>L5 eFG%</small><strong>{_pct(l5_p.get('EFG_PCT'))}</strong></div><div><small>L5 TS%</small><strong>{_pct(l5_p.get('TS_PCT'))}</strong></div>
</div>
<div class="kyre-v198415-detail"><b>Volume trend</b> • {escape(volume_trend)}<br><b>Efficiency trend</b> • {escape(eff_trend)}<br><b>Scoring-profile audit</b> • {evidence_n}/4 available trend signals • score {score:+d}<br><b>Source</b> • {source}<br><b>Shot-location split</b> • rim/midrange location data is not inferred when the verified Base feed does not expose it</div>
<div class="kyre-v198415-verdict">Scoring profile • {escape(verdict)}</div>
<div class="kyre-v198415-note">Audit/context only • Step 7 displays verified shooting volume and efficiency. It does not add or re-apply shot-volume/efficiency weight to the protected Points projection, Monte Carlo probability or Top-5 ordering.</div>
</div>
"""
    return prior._compact_html(html)


def _step6_plus_step7(day: str, data: dict) -> str:
    return _ORIGINAL_STEP6_BLOCK(day, data) + _step7_block(day, data)


def _install() -> None:
    prior._step6_block = _step6_plus_step7


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎯 Points V1.9.8.4.15 • Step 7 Shot Volume + Scoring Efficiency ACTIVE • "
        "same Top-5 cards • verified Base shooting stats • audit only"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
