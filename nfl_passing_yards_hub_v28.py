"""NFL Passing Yards V28 — Step 5 exact-ID weapons + injury upgrade.

Presentation/data-routing wrapper over certified V27. V28 advances only Step 5:
- injects Personnel V3 into the active V8 Step 5 call site;
- supplies the exact selected slate date from existing V8 Streamlit state;
- adds recent verified target-share context for current depth-chart weapons;
- recovers current depth from season-specific ESPN Core when the site endpoint's
  changed ``depthchart`` shape leaves frozen V1 with no parsed rows;
- keeps current injury/depth evidence and fail-closed semantics visible.

V27 Step 4, V24-V20 market/visual contracts, projection/distribution/market math,
0.0% sportsbook projection influence, and stake sizing OFF remain frozen.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_passing_yards_hub_v7 as step5_ui
import nfl_passing_yards_hub_v8 as step7_owner
import nfl_passing_yards_hub_v27 as prior
import nfl_passing_yards_personnel_v3 as personnel_v3

MODEL_VERSION = "NFL PASSING YARDS V28 • STEP 5 EXACT-ID WEAPONS + INJURIES MONSTER"
FROZEN_PRIOR = "nfl_passing_yards_hub_v27"

_STEP5_MONSTER_CSS = r"""
<style>
.kpy28-weapons{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;color:#8299ad;font-size:.50rem;line-height:1.6}
.kpy28-weapons b{color:#e9f5ff}.kpy28-weapon-pill{display:inline-block;margin:3px 4px 0 0;padding:3px 6px;border:1px solid #29485f;border-radius:999px;background:#081a28;color:#b9d8ee;font-weight:800}
.kpy28-source{color:#70a1c5;font-size:.46rem;margin-top:5px}
</style>
"""


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _selected_cutoff() -> str:
    for key in ("nfl_passing_yards_v8_date_input", "nfl_passing_yards_v8_date"):
        if key not in st.session_state:
            continue
        try:
            return pd.to_datetime(st.session_state[key]).strftime("%Y-%m-%d")
        except Exception:
            continue
    return ""


class _PersonnelV3Proxy:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "build_personnel_matchup":
            def build(offense_ctx, defense_ctx, year, season_type, team_pass_attempts):
                return personnel_v3.build_personnel_matchup(
                    offense_ctx,
                    defense_ctx,
                    year,
                    season_type,
                    team_pass_attempts,
                    cutoff_date=_selected_cutoff(),
                )
            return build
        return getattr(self._wrapped, name)


def _weapon_pills(p: dict) -> str:
    pills = []
    for row in (p.get("top_weapons") or [])[:4]:
        name = escape(_safe(row.get("name"), "Unknown"))
        pos = escape(_safe(row.get("position"), "—"))
        share = _fmt(row.get("target_share"), 1, "%")
        share_text = escape(share if share != "—" else "usage —")
        pills.append(f'<span class="kpy28-weapon-pill">{name} • {pos} • {share_text}</span>')
    return "".join(pills) or '<span class="kpy28-weapon-pill">No exact-ID weapon usage available</span>'


def _personnel_card(p: dict) -> str:
    label = _safe(p.get("personnel_label"), "CHECK").upper()
    css = label.lower() if label.lower() in {"help", "hurt", "mixed", "watch", "neutral"} else "check"
    depth_state = _safe(p.get("depth_recovery_state"), "EXACT ESPN DEPTH")
    return (
        '<section class="kpy-personnel">'
        '<div class="kpy-ihead">'
        f'<div><div class="kpy-iname">{escape(_safe(p.get("qb_name"),"Unresolved QB1"))} • Weapons + Availability</div>'
        f'<div class="kpy-isub">{escape(_safe(p.get("offense_team_name"),"Offense"))} offense vs {escape(_safe(p.get("defense_team_name"),"Defense"))} secondary • {escape(_safe(p.get("personnel_basis"),"evidence incomplete"))}</div></div>'
        f'<div class="kpy-ilabel {css}">{escape(label)}</div></div>'
        '<div class="kpy-imetrics">'
        f'<div class="kpy-imetric"><b>{escape(_safe(p.get("qb_status"),"—"))}</b><span>QB Status</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("skill_hard_count") or 0)}</b><span>Skill Hard</span></div>'
        f'<div class="kpy-imetric"><b>{_fmt(p.get("hard_target_share"),1,"%")}</b><span>Hard Target Share</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("ol_hard_count") or 0)}</b><span>OL Hard</span></div>'
        f'<div class="kpy-imetric"><b>{int(p.get("secondary_hard_count") or 0)}</b><span>Opp Secondary Hard</span></div>'
        '</div>'
        '<div class="kpy28-weapons"><b>Core passing weapons • recent verified target share</b><br>'
        f'{_weapon_pills(p)}'
        f'<div class="kpy28-source">{escape(_safe(p.get("weapon_usage_state"), p.get("target_share_state") or "UNAVAILABLE"))}<br>{escape(depth_state)}</div></div>'
        '<div class="kpy-inote">'
        f'Watch-list skill players: <b>{int(p.get("skill_watch_count") or 0)}</b> • '
        f'watch target share: <b>{_fmt(p.get("watch_target_share"),1,"%")}</b><br>'
        f'Availability source: current ESPN injury snapshot • weapon identity: exact ESPN athlete IDs'
        '</div></section>'
    )


def _personnel_table(p: dict) -> pd.DataFrame:
    rows = []
    skill_injuries = {_safe(r.get("athlete_id")): r for r in (p.get("skill_injuries") or []) if _safe(r.get("athlete_id"))}
    for item in p.get("top_weapons") or []:
        hit = skill_injuries.get(_safe(item.get("athlete_id"))) or {}
        rows.append({
            "Group": "Core weapon",
            "Player": _safe(item.get("name"), "Unknown"),
            "Pos": _safe(item.get("position"), "—"),
            "Status": _safe(hit.get("status"), "No listed injury"),
            "Depth": f"#{item.get('rank')}" if isinstance(item.get("rank"), int) and item.get("rank") < 99 else "—",
            "Targets": int(round(float(item.get("targets")))) if _finite(item.get("targets")) else "—",
            "Target Share": _fmt(item.get("target_share"), 1, "%"),
            "Detail": f"recent {int(item.get('usage_games') or 0)} verified game(s) • {item.get('source','ESPN depth')}",
        })

    for group, items in (
        ("Pass catcher injury", p.get("skill_injuries") or []),
        ("Offensive line injury", p.get("ol_injuries") or []),
        ("Opponent secondary injury", p.get("secondary_injuries") or []),
    ):
        for item in items:
            rank = item.get("depth_rank")
            rows.append({
                "Group": group,
                "Player": _safe(item.get("name"), "Unknown"),
                "Pos": _safe(item.get("position"), "—"),
                "Status": _safe(item.get("status"), "Unspecified"),
                "Depth": f"#{rank}" if isinstance(rank, int) and rank < 99 else "—",
                "Targets": int(round(float(item.get("targets")))) if _finite(item.get("targets")) else "—",
                "Target Share": _fmt(item.get("target_share"), 1, "%"),
                "Detail": _safe(item.get("detail")),
            })
    return pd.DataFrame(rows)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_STEP5_MONSTER_CSS, unsafe_allow_html=True)
    original_personnel = step7_owner.personnel
    original_card = step5_ui._personnel_card
    original_table = step5_ui._personnel_table
    step7_owner.personnel = _PersonnelV3Proxy(original_personnel)
    step5_ui._personnel_card = _personnel_card
    step5_ui._personnel_table = _personnel_table
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        step7_owner.personnel = original_personnel
        step5_ui._personnel_card = original_card
        step5_ui._personnel_table = original_table


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_PersonnelV3Proxy",
    "_personnel_card",
    "_personnel_table",
    "render_nfl_passing_yards_hub",
]
