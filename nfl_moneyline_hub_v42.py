"""Kyre Sports AI — NFL Moneyline V4.2 Step-4B matchup + home-field feature layer.

Builds on the verified V4.1 Step-4A historical baseline. Step 4B adds raw,
transparent matchup features without exposing a calibrated win probability:
- offense vs opponent defense scoring interaction;
- baseline strength-index gap;
- recent-L6 form gap;
- ESPN-verified neutral/home-site status;
- a fixed 2.0-point home-field structural adjustment when the game is verified
  non-neutral.

The features are intentionally NOT combined into a final P(win). Step 4C will
calibrate historical feature/outcome relationships before any probability is
exposed. Sportsbook prices, Monte Carlo, EV, ranking and recommendations remain
OFF. Preseason Step 3 remains a final-output safety gate.
"""
from __future__ import annotations

from datetime import date
from html import escape

import numpy as np
import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v4 as v4
import nfl_moneyline_hub_v41 as v41

MODEL_VERSION = "NFL MONEYLINE V4.2 • STEP 4B MATCHUP + HOME FIELD FEATURES"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
HEADERS = v4.HEADERS
HOME_FIELD_POINTS = 2.0


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _num(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def _finite(*values) -> bool:
    return all(np.isfinite(_num(x)) for x in values)


@st.cache_data(ttl=300, show_spinner=False)
def _site_context(day_str: str):
    """Verify neutral-site flags from the same ESPN scoreboard family."""
    day = pd.to_datetime(day_str).strftime("%Y%m%d")
    diag = {"ok": False, "http": None, "error": "", "provider": "ESPN NFL scoreboard site context"}
    try:
        r = requests.get(
            ESPN_SCOREBOARD,
            params={"dates": day, "limit": 100},
            headers=HEADERS,
            timeout=8,
        )
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return {}, diag

    out = {}
    for event in payload.get("events", []) or []:
        game_id = _safe(event.get("id"))
        comps = event.get("competitions") or []
        if not game_id or not comps:
            continue
        comp = comps[0] or {}
        if "neutralSite" in comp:
            neutral = bool(comp.get("neutralSite"))
            verified = True
        else:
            neutral = None
            verified = False
        venue = comp.get("venue") or {}
        out[game_id] = {
            "verified": verified,
            "neutral": neutral,
            "venue": _safe(venue.get("fullName")),
        }
    diag["ok"] = True
    return out, diag


def _matchup_features(game: dict, away_profile: dict, home_profile: dict, site: dict) -> dict:
    if not away_profile.get("ready") or not home_profile.get("ready"):
        return {"ready": False, "reason": "Step 4A profile unavailable"}

    ab = away_profile.get("blended") or {}
    hb = home_profile.get("blended") or {}
    needed = [
        away_profile.get("strength_index"), home_profile.get("strength_index"),
        ab.get("ppg"), ab.get("papg"), ab.get("recent6_diff_pg"),
        hb.get("ppg"), hb.get("papg"), hb.get("recent6_diff_pg"),
    ]
    if not _finite(*needed):
        return {"ready": False, "reason": "required Step 4A metrics incomplete"}

    # Transparent offense/defense interaction: average a team's scoring rate with
    # the opponent's points-allowed rate. This is a feature, not a projected score.
    away_off_vs_def = 0.5 * (float(ab["ppg"]) + float(hb["papg"]))
    home_off_vs_def = 0.5 * (float(hb["ppg"]) + float(ab["papg"]))
    raw_scoring_margin = away_off_vs_def - home_off_vs_def

    strength_gap = float(away_profile["strength_index"] - home_profile["strength_index"])
    recent_gap = float(ab["recent6_diff_pg"] - hb["recent6_diff_pg"])

    site_verified = bool(site.get("verified"))
    neutral = site.get("neutral") if site_verified else None
    hfa = 0.0 if neutral is True else (HOME_FIELD_POINTS if neutral is False else 0.0)
    site_adjusted_scoring_margin = raw_scoring_margin - hfa

    return {
        "ready": bool(site_verified),
        "feature_ready": True,
        "site_verified": site_verified,
        "neutral": neutral,
        "venue": _safe(site.get("venue"), _safe(game.get("venue"), "—")),
        "away_off_vs_def": float(away_off_vs_def),
        "home_off_vs_def": float(home_off_vs_def),
        "raw_scoring_margin": float(raw_scoring_margin),
        "strength_gap": strength_gap,
        "recent_gap": recent_gap,
        "home_field_points": float(hfa),
        "site_adjusted_scoring_margin": float(site_adjusted_scoring_margin),
        "reason": "" if site_verified else "neutral/home-site flag not verified",
    }


def _fmt(value, digits=1, suffix="") -> str:
    return "—" if not np.isfinite(_num(value)) else f"{float(value):.{digits}f}{suffix}"


def _render_matchup(game: dict, features: dict):
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    st.markdown(f"#### Matchup features — {escape(away)} @ {escape(home)}")

    if not features.get("feature_ready"):
        st.warning(f"Step 4B features unavailable • {features.get('reason') or 'missing Step 4A inputs'}")
        return

    a, b, c, d = st.columns(4)
    a.metric("Strength gap A-H", _fmt(features.get("strength_gap"), 1))
    b.metric("Off/Def margin A-H", _fmt(features.get("raw_scoring_margin"), 1))
    c.metric("Recent L6 gap A-H", _fmt(features.get("recent_gap"), 1))
    d.metric("Home-field pts", _fmt(features.get("home_field_points"), 1))

    x, y, z = st.columns(3)
    x.metric(f"{away} O vs D", _fmt(features.get("away_off_vs_def"), 1))
    y.metric(f"{home} O vs D", _fmt(features.get("home_off_vs_def"), 1))
    z.metric("Site-adj scoring signal", _fmt(features.get("site_adjusted_scoring_margin"), 1))

    if features.get("site_verified"):
        site_text = "NEUTRAL — no HFA" if features.get("neutral") else f"HOME FIELD VERIFIED — {home} +{HOME_FIELD_POINTS:.1f} structural pts"
        st.success(f"✅ Site context verified • {site_text} • {features.get('venue') or 'venue verified'}")
    else:
        st.warning("⚠️ Site context not verified • home-field value is held at 0.0 rather than assumed.")

    st.info(
        "Step 4B exposes raw matchup features only. The site-adjusted scoring signal is the offense/defense interaction minus verified home-field structure; "
        "it does NOT yet combine strength gap or recent form and is NOT a Moneyline probability or pick."
    )


def _render_step4b() -> bool:
    selected = st.session_state.get("nfl_v1_date", date.today())
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    schedule, diag = foundation.load_nfl_slate(day_str)
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))
    profiles = st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}
    sites, sdiag = _site_context(day_str)

    st.markdown("### 🧭 Step 4B — Opponent + Home-Field Context")
    st.caption(
        "Raw calibration features ACTIVE • offense vs opponent defense • historical strength gap • recent-L6 gap • verified neutral/home-site status • "
        "2.0-point structural home-field input when non-neutral • final P(win) remains locked."
    )

    if not diag.get("request_ok") or pregame.empty:
        st.warning("Step 4B cannot build matchup features because no verified pregame game is available.")
        return False
    if not profiles:
        st.warning("Step 4B cannot run because the Step 4A strength profiles are unavailable.")
        return False

    feature_map = {}
    ready_games = 0
    for _, row in pregame.iterrows():
        game = row.to_dict()
        away_abbr = _safe(game.get("away_abbr")).upper()
        home_abbr = _safe(game.get("home_abbr")).upper()
        game_id = _safe(game.get("game_id"))
        feat = _matchup_features(
            game,
            profiles.get(away_abbr, {}),
            profiles.get(home_abbr, {}),
            sites.get(game_id, {}),
        )
        feature_map[game_id or f"{away_abbr}@{home_abbr}"] = feat
        if feat.get("ready"):
            ready_games += 1

    m1, m2, m3 = st.columns(3)
    m1.metric("Games featured", f"{ready_games}/{len(pregame)}")
    m2.metric("Site verification", "READY" if sdiag.get("ok") and ready_games == len(pregame) else "CHECK")
    m3.metric("Calibrated P(win)", "LOCKED")

    all_ready = bool(len(pregame) and ready_games == len(pregame))
    if all_ready:
        st.success("✅ STEP 4B PASSED • opponent interaction and verified home/neutral-site features built for every pregame matchup.")
    else:
        st.warning("⚠️ STEP 4B CHECK • at least one matchup lacks a verified site/context input. Missing values are not assumed.")

    for _, row in pregame.iterrows():
        game = row.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        _render_matchup(game, feature_map.get(gid, {}))

    st.session_state["nfl_moneyline_v42_matchup_features"] = feature_map
    st.session_state["nfl_moneyline_v42_matchup_ready"] = all_ready
    return all_ready


def render_nfl_moneyline_hub():
    """Render V4.1 unchanged and inject Step 4B immediately after Step 4A."""
    real_markdown = st.markdown
    real_dataframe = st.dataframe
    real_caption = st.caption
    state = {"step4b_injected": False, "step4b_ready": False}

    def _markdown(body, *args, **kwargs):
        if isinstance(body, str):
            # V4's inner wrapper rewrites STEP 3 -> STEP 4A before reaching us.
            if '<span class="knfl-ml-chip">STEP 4A</span>' in body:
                body = body.replace(
                    '<span class="knfl-ml-chip">STEP 4A</span>',
                    '<span class="knfl-ml-chip">STEP 4B</span>',
                )
                body = body.replace(
                    "Team-strength baseline is active; final win probability, sportsbook math and Monte Carlo remain off.",
                    "Step 4A baseline + Step 4B matchup features are active; calibrated win probability, sportsbook math and Monte Carlo remain off.",
                )
            if body.strip() == "### 🔒 Moneyline production locks" and not state["step4b_injected"]:
                state["step4b_injected"] = True
                state["step4b_ready"] = _render_step4b()
        return real_markdown(body, *args, **kwargs)

    def _dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and "Layer" in data.columns and "State" in data.columns:
            layers = data["Layer"].astype(str).tolist()
            if "Team-strength win model" in layers:
                data = data.copy()
                mask = data["Layer"].astype(str) == "Team-strength win model"
                data.loc[mask, "State"] = "STEP 4A BASELINE READY" if st.session_state.get("nfl_moneyline_v4_strength_ready") else "STEP 4A CHECK"
                if "Opponent + home-field features" not in set(data["Layer"].astype(str)):
                    insert_at = int(np.where(mask.to_numpy())[0][0]) + 1
                    extra = pd.DataFrame([
                        {
                            "Layer": "Opponent + home-field features",
                            "State": "STEP 4B READY" if state.get("step4b_ready") else "STEP 4B CHECK",
                        },
                        {
                            "Layer": "Calibrated win probability",
                            "State": "LOCKED — STEP 4C NEXT",
                        },
                    ])
                    data = pd.concat([data.iloc[:insert_at], extra, data.iloc[insert_at:]], ignore_index=True)
        return real_dataframe(data, *args, **kwargs)

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and body.startswith("Step 4A calculates a descriptive historical team-strength baseline only"):
            body = (
                "Step 4B adds opponent interaction, recent-form separation and verified home/neutral-site features on top of the Step 4A historical baseline. "
                "Calibrated win probability, sportsbook prices, Monte Carlo, edge/EV and final grading remain OFF. Step 3 remains a preseason final-output safety gate."
            )
        return real_caption(body, *args, **kwargs)

    st.markdown = _markdown
    st.dataframe = _dataframe
    st.caption = _caption
    try:
        return v41.render_nfl_moneyline_hub()
    finally:
        st.markdown = real_markdown
        st.dataframe = real_dataframe
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
