"""MLB Matchup Explorer V1.3 — full active rosters + small-sample calibration.

This layer does NOT rewrite frozen production engines. It adds:
- full two-team active-roster browsing
- confirmed/projected batting-order players first, bench/active roster after
- small-sample probability shrinkage for embedded cards only
- explicit reliability/sample labels so tiny MLB samples cannot masquerade as stable

Bench players remain researchable but are not assigned fabricated batting spots or PA.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_hub_v12 as base
import mlb_hit_hub_v133 as hit133

VERSION = "MLB Matchup Hub V1.3"

_ORIG_HITTERS = ui._hitters_for_game
_ORIG_HIT_RENDER = base._render_hit_card
_ORIG_HR_RENDER = base._render_hr_card
_ORIG_HRR_RENDER = base._render_hrr_card
_ORIG_COMPONENT_RENDER = base._render_component_card


def _safe_int(v):
    try: return int(v)
    except Exception: return None


def _all_hitters_for_game(row):
    """Lineup first, then every other active non-pitcher on both clubs."""
    pk = _safe_int(row.get("game_pk"))
    if pk is None:
        return _ORIG_HITTERS(row)
    day = ui._date_str(row)
    try:
        pool, _ = hit133._candidate_pool(row.to_frame().T, include_live=True)
    except Exception:
        pool = []

    out = []
    seen = set()
    for side, tid, tname in (
        ("away", row.get("away_team_id"), row.get("away_team")),
        ("home", row.get("home_team_id"), row.get("home_team")),
    ):
        lineup = [c for c in pool if str(c.get("team_side")) == side]
        lineup.sort(key=lambda c: int(c.get("position") or 99))
        for c in lineup:
            pid = _safe_int(c.get("player_id"))
            if pid is None or pid in seen: continue
            seen.add(pid)
            confirmed = bool(c.get("lineup_confirmed"))
            out.append({
                "id": pid,
                "name": str(c.get("player_name") or f"Player {pid}"),
                "position": str((ui._person(pid).get("primaryPosition") or {}).get("abbreviation") or ""),
                "slot": int(c.get("position") or 99),
                "team": tname,
                "team_id": tid,
                "side": side,
                "source": "✅ CONFIRMED LINEUP" if confirmed else "🕒 PROJECTED LINEUP",
                "lineup_role": True,
            })

        roster = ui._active_roster(tid, day)
        for p in roster:
            pid = _safe_int(p.get("id"))
            if pid is None or pid in seen: continue
            pos = str(p.get("position") or "").upper()
            if pos in ("P", "SP", "RP"): continue
            seen.add(pid)
            out.append({
                **p,
                "team": tname,
                "team_id": tid,
                "side": side,
                "source": "🪑 BENCH / ACTIVE ROSTER",
                "lineup_role": False,
                "slot": 99,
            })
    return out


def _sample_info_from_result(r):
    # Prefer explicit PA/AB if an engine exposes it; fall back to season game count.
    for key in ("season_pa", "pa", "plate_appearances", "sample_pa"):
        try:
            x = float(r.get(key))
            if math.isfinite(x) and x > 0: return x, "PA"
        except Exception: pass
    try:
        pid = int(r.get("player_id"))
        year = st.session_state.get("mh13_season")
        if year:
            s = ui._season_hitting(pid, int(year))
            pa = float(s.get("plateAppearances") or 0)
            if pa > 0: return pa, "PA"
            g = float(s.get("gamesPlayed") or 0)
            if g > 0: return g, "G"
    except Exception: pass
    return 0.0, "G"


def _reliability(sample, unit="PA"):
    # PA gets a 180-PA stabilization anchor; games gets a 45-game anchor.
    anchor = 180.0 if unit == "PA" else 45.0
    return max(0.0, min(1.0, float(sample) / (float(sample) + anchor)))


def _shrink(p, sample, prior, unit="PA"):
    try:
        p = float(p)
        if not math.isfinite(p): return prior
    except Exception:
        return prior
    w = _reliability(sample, unit)
    return max(0.001, min(0.999, w*p + (1.0-w)*prior))


def _sample_badge(sample, unit):
    rel = _reliability(sample, unit)
    label = "VERY SMALL" if rel < .15 else "SMALL" if rel < .30 else "BUILDING" if rel < .50 else "STABLE"
    return label, rel


def _render_cal_note(sample, unit):
    label, rel = _sample_badge(sample, unit)
    if rel < .50:
        st.warning(f"🧪 Sample protection active • {sample:.0f} {unit} • {label} sample • reliability {rel*100:.0f}%. Explorer probabilities are shrunk toward MLB priors; frozen standalone engines are unchanged.")
    else:
        st.caption(f"🧪 Sample reliability {rel*100:.0f}% • {sample:.0f} {unit} • {label}")


def _render_hit_cal(r, started=False):
    if r.get("error"): return _ORIG_HIT_RENDER(r, started)
    s = dict(r.get("sim") or {})
    sample, unit = _sample_info_from_result(r)
    raw = float(s.get("p_one_plus") or 0)
    s["p_one_plus_raw"] = raw
    s["p_one_plus"] = _shrink(raw, sample, .655, unit)
    p2raw = float(s.get("p_two_plus") or 0)
    s["p_two_plus"] = _shrink(p2raw, sample, .225, unit)
    rr = dict(r); rr["sim"] = s
    _render_cal_note(sample, unit)
    _ORIG_HIT_RENDER(rr, started)


def _render_hr_cal(r, started=False):
    if r.get("error"): return _ORIG_HR_RENDER(r, started)
    sample, unit = _sample_info_from_result(r)
    rr = dict(r)
    rr["p_hr_raw"] = rr.get("p_hr")
    rr["p_hr"] = _shrink(rr.get("p_hr") or 0, sample, .095, unit)
    rr["p_2hr"] = _shrink(rr.get("p_2hr") or 0, sample, .010, unit)
    _render_cal_note(sample, unit)
    _ORIG_HR_RENDER(rr, started)


def _render_hrr_cal(r, started=False):
    if r.get("error"): return _ORIG_HRR_RENDER(r, started)
    sample, unit = _sample_info_from_result(r)
    rr = dict(r); s = dict(rr.get("sim") or {})
    s["p2_raw"] = s.get("p2")
    s["p2"] = _shrink(s.get("p2") or 0, sample, .555, unit)
    s["p3"] = _shrink(s.get("p3") or 0, sample, .350, unit)
    s["p4"] = _shrink(s.get("p4") or 0, sample, .205, unit)
    rr["sim"] = s
    _render_cal_note(sample, unit)
    _ORIG_HRR_RENDER(rr, started)


def _render_component_cal(r, started=False):
    if r.get("error"): return _ORIG_COMPONENT_RENDER(r, started)
    profile = r.get("profile") or {}
    sample, unit = _sample_info_from_result(profile)
    rr = dict(r)
    metric = str(rr.get("metric") or "")
    priors = {
        "Total Bases": (.690, .390, .235, .145),
        "Runs": (.355, .095, .022, None),
        "RBIs": (.340, .090, .024, None),
    }.get(metric, (.50,.20,.08,None))
    rr["p1"] = _shrink(rr.get("p1") or 0, sample, priors[0], unit)
    rr["p2"] = _shrink(rr.get("p2") or 0, sample, priors[1], unit)
    rr["p3"] = _shrink(rr.get("p3") or 0, sample, priors[2], unit)
    if priors[3] is not None and "p4" in rr:
        rr["p4"] = _shrink(rr.get("p4") or 0, sample, priors[3], unit)
    _render_cal_note(sample, unit)
    _ORIG_COMPONENT_RENDER(rr, started)


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is not None and not games_df.empty:
        try: st.session_state["mh13_season"] = int(str(games_df.iloc[0].get("game_date"))[:4])
        except Exception: pass

    # Patch dependencies only during this render call. V1.2 itself remains untouched.
    old_hitters = ui._hitters_for_game
    old_h = base._render_hit_card
    old_hr = base._render_hr_card
    old_hrr = base._render_hrr_card
    old_comp = base._render_component_card
    ui._hitters_for_game = _all_hitters_for_game
    base._render_hit_card = _render_hit_cal
    base._render_hr_card = _render_hr_cal
    base._render_hrr_card = _render_hrr_cal
    base._render_component_card = _render_component_cal
    try:
        base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
        st.caption(f"{VERSION} • full active rosters • sample-size calibration layer • frozen production engines remain read-only")
    finally:
        ui._hitters_for_game = old_hitters
        base._render_hit_card = old_h
        base._render_hr_card = old_hr
        base._render_hrr_card = old_hrr
        base._render_component_card = old_comp
