"""WNBA PRA V3.6.8 — Step-5 projection path presentation layer.

Presentation-only wrapper over V3.6.7. Preserves the exact V2.8 Step-5
eligibility and PRA sorting while carrying already-existing V2.8 row fields into
the five-card display so the user can see the projection path.

No new projection intermediate is manufactured. The path shows only values that
already exist in the V2.8 role engine: season PRA input, BASE_MIN, PROJ_MIN,
MIN_DELTA, BASE_USG, PROJ_USG, ROLE_DELTA_PCT and final PROJ_PRA. V2.8 does not
store a minutes-only PRA intermediate, does not apply opponent matchup math and
does not calculate sportsbook Over/Under probability at Step 5, so those are
explicitly labeled unavailable/off instead of being inferred.

No PRA projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

import wnba_pra_step5_history_v367 as history_layer
import wnba_pra_step5_identity_v363 as cards

v28 = cards.v28
role = v28.role
defense_layer = history_layer.prior

MODEL_VERSION = "PRA V3.6.8 • STEP-5 PROJECTION PATH • MODEL PRESERVED"


def _num(value, default=float("nan")):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1, suffix=""):
    x = _num(value)
    if not math.isfinite(x):
        return "N/A"
    return f"{x:.{digits}f}{suffix}"


def _signed(value, digits=1, suffix=""):
    x = _num(value)
    if not math.isfinite(x):
        return "N/A"
    return f"{x:+.{digits}f}{suffix}"


def _adjusted_top5_v368(schedule, stats):
    """Exact V2.8 Top-5 selection/order with display-only existing fields added."""
    rows = []
    if schedule is None or schedule.empty:
        return rows

    # Keep the V2.8 traversal, eligibility gate and sort key byte-for-byte in
    # behavior. Extra keys below are already-existing fields from the same row
    # and are used only by the renderer.
    for _, game in schedule.iterrows():
        result = role.role_projection_for_game(game, stats)
        for tid, frame in result.get("teams", {}).items():
            if frame is None or frame.empty:
                continue
            for _, p in frame.iterrows():
                status = str(p.get("DESIGNATION") or "NO DESIGNATION").upper()
                if status in role.OUT_STATUSES or float(p.get("PROJ_MIN") or 0) < 15:
                    continue
                opponent = (
                    game.get("home_team")
                    if int(tid) == int(game.get("away_team_id") or 0)
                    else game.get("away_team")
                )
                rows.append(
                    {
                        "name": str(p.get("PLAYER_NAME") or "Player"),
                        "team": str(p.get("TEAM_ABBREVIATION") or p.get("TEAM_NAME") or ""),
                        "opponent": str(opponent or "—"),
                        "min": float(p.get("PROJ_MIN") or 0),
                        "usg": p.get("PROJ_USG"),
                        "p": float(p.get("PROJ_PTS") or 0),
                        "r": float(p.get("PROJ_REB") or 0),
                        "a": float(p.get("PROJ_AST") or 0),
                        "pra": float(p.get("PROJ_PRA") or 0),
                        "status": status,
                        "starter": bool(p.get("STARTER_CONFIRMED")),
                        # Existing V2.8 fields carried into the DISPLAY payload.
                        "source_pra": p.get("PRA"),
                        "base_min": p.get("BASE_MIN"),
                        "proj_min": p.get("PROJ_MIN"),
                        "min_delta": p.get("MIN_DELTA"),
                        "base_usg": p.get("BASE_USG"),
                        "proj_usg": p.get("PROJ_USG"),
                        "role_delta": p.get("ROLE_DELTA_PCT"),
                    }
                )

    # Exact V2.8 ranking key and Top-5 truncation.
    return sorted(rows, key=lambda x: x["pra"], reverse=True)[:5]


def _path_metric(label, value, note="", accent=False):
    value_color = "#7ff2c2" if accent else "#f4f8ff"
    return (
        '<div style="border:1px solid #23485c;background:#081823;border-radius:8px;'
        'padding:6px 7px;min-width:0">'
        f'<span style="display:block;color:#6e91a5;font-size:.34rem;font-weight:950;'
        f'letter-spacing:.045em">{escape(label)}</span>'
        f'<b style="display:block;color:{value_color};font-size:.58rem;margin-top:2px;'
        f'white-space:nowrap">{escape(value)}</b>'
        + (
            f'<small style="display:block;color:#658094;font-size:.31rem;margin-top:2px;'
            f'line-height:1.25">{escape(note)}</small>'
            if note
            else ""
        )
        + "</div>"
    )


def _projection_path_box(p: dict) -> str:
    source_pra = _fmt(p.get("source_pra"), 1)
    base_min = _fmt(p.get("base_min"), 1)
    proj_min = _fmt(p.get("proj_min"), 1)
    min_delta = _signed(p.get("min_delta"), 1)

    base_usg = _fmt(p.get("base_usg"), 1)
    proj_usg = _fmt(p.get("proj_usg"), 1)
    role_delta = _signed(p.get("role_delta"), 1)
    final_pra = _fmt(p.get("pra"), 1)

    minutes_value = (
        f"{base_min} → {proj_min}" if base_min != "N/A" and proj_min != "N/A" else "N/A"
    )
    usage_value = (
        f"{base_usg} → {proj_usg}" if base_usg != "N/A" and proj_usg != "N/A" else "N/A"
    )

    return (
        '<div style="border:1px solid #315d72;background:#0a1b27;border-radius:10px;'
        'padding:8px;margin-top:8px">'
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px">'
        '<b style="color:#9ee9ff;font-size:.5rem">🧭 PROJECTION PATH</b>'
        '<span style="color:#65a7bb;font-size:.37rem;font-weight:900">EXISTING V2.8 FIELDS</span>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));'
        'gap:4px;margin-top:6px">'
        f'{_path_metric("SEASON PRA INPUT", source_pra, "source average • not a new projection")}'
        f'{_path_metric("MINUTES", minutes_value, f"Δ {min_delta} MIN")}'
        f'{_path_metric("ROLE / USG", usage_value, f"Δ {role_delta} USG pts")}'
        f'{_path_metric("FINAL V2.8 PRA", final_pra, "minutes + role projection", True)}'
        '</div>'
        '<div style="font-size:.34rem;color:#68889a;margin-top:5px;line-height:1.35">'
        'Minutes-only PRA intermediate: not stored • Matchup adjustment: OFF at V2.8 • '
        'O/U probability: not calculated at Step 5 • display only'
        '</div></div>'
    )


def _render_top5_v368(picks):
    """Identity + defense + history + honest existing-field projection path."""
    if not picks:
        st.markdown(
            '<div class="w2-empty">No eligible Step 5 projections are available.</div>',
            unsafe_allow_html=True,
        )
        return

    day = st.session_state.get("wnba_pra_v2_date")
    player_ids, teams = cards._identity_maps(day)
    defenses = defense_layer._opponent_context_map(day)
    histories = history_layer._board_history_map(day, picks, defenses)
    rendered = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = (
            "STARTER"
            if p["starter"]
            else p["status"]
            if p["status"] != "NO DESIGNATION"
            else "ACTIVE"
        )
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        pid = player_ids.get(cards._player_key(name))
        tm = cards._team_meta(teams, team)
        om = cards._team_meta(teams, opponent)
        defense = defenses.get(defense_layer._norm(opponent), {})
        history = histories.get(cards._player_key(name), {})

        headshot = cards._headshot_html(pid, name)
        team_logo = cards._logo_html(tm, team, f"{team} logo")
        opp_logo = cards._logo_html(om, opponent, f"{opponent} logo")
        defense_html = defense_layer._defense_box(defense, opponent)
        history_html = history_layer._history_box(history, opponent)
        path_html = _projection_path_box(p)

        rendered.append(
            f'<div class="w28-pick{first}">'
            f'<div class="w28-rank">#{i} STEP-5 PRA • 🖼️ IDENTITY • 🛡️ DEFENSE • 📚 HISTORY • 🧭 PATH</div>'
            '<div style="display:flex;align-items:center;gap:10px;margin-top:7px;min-width:0">'
            f"{headshot}"
            '<div style="min-width:0;flex:1">'
            f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
            '<div style="display:flex;align-items:center;gap:6px;margin-top:6px;min-width:0">'
            f'{team_logo}<span style="color:#8da3b8;font-size:.5rem;font-weight:800">vs</span>{opp_logo}'
            "</div></div></div>"
            f'<div class="w28-meta" style="margin-top:7px">{escape(team)} vs {escape(opponent)} • {escape(status)} • {p["min"]:.1f} MIN</div>'
            f'<div class="w28-pra">{p["pra"]:.1f} <span>Projected PRA</span></div>'
            '<div class="w28-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div>'
            f'<div><span>REB</span><b>{p["r"]:.1f}</b></div>'
            f'<div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'<div><span>USG</span><b>{v28._fmt(p["usg"],1)}</b></div>'
            "</div>"
            f"{defense_html}{history_html}{path_html}"
            '<div style="font-size:.4rem;color:#577892;margin-top:7px;letter-spacing:.04em">'
            "IDENTITY • DEFENSE • HISTORY • PROJECTION PATH ARE DISPLAY LAYERS"
            "</div></div>"
        )

    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">First adjusted ranking: current availability, projected team minutes and role/USG changes are active. Identity, opponent defense, matchup history and the projection-path explanation are presentation-only. No new intermediate PRA or probability is manufactured.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div></div>',
        unsafe_allow_html=True,
    )


def install():
    """Install only the Step-5 display boundary for this render."""
    # Reinstall the full V3.6.7 presentation stack first, then replace only the
    # Step-5 candidate payload/display functions with the V3.6.8 enriched view.
    history_layer.install()

    v28._adjusted_top5 = _adjusted_top5_v368
    v28._render_top5 = _render_top5_v368

    cards._render_top5 = _render_top5_v368
    cards.v28._render_top5 = _render_top5_v368

    defense_layer.cards._render_top5 = _render_top5_v368
    defense_layer.cards.v28._render_top5 = _render_top5_v368


def begin_render():
    history_layer.begin_render()
    install()


__all__ = [
    "MODEL_VERSION",
    "begin_render",
    "install",
]
