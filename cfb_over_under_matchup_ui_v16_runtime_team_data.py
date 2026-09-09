"""CFB O/U UI V16 — central runtime team-data handoff.

Additive hotfix above permanently frozen V15.

The base Over/Under hub itself now receives reconciled team profiles from the
first team-data load, so every downstream frozen card sees the same corrected
record, split, form, rank, coach and scoring evidence.

V16 also swaps the frozen V13 deep slate's data source to the same runtime
adapter and clears stale Streamlit caches once per session.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_hub_v3 as frozen_team_ui
import cfb_over_under_hub_v1 as base_hub
import cfb_over_under_matchup_ui_v14_deep_data as frozen_v14
import cfb_over_under_matchup_ui_v15_visible_data_path as frozen_v15
import cfb_over_under_runtime_deep_adapter_v1 as runtime_deep
import cfb_over_under_runtime_team_data_v1 as runtime_team_data
import cfb_over_under_slate_v13_deep_data as deep_slate
import cfb_schedule_v5_runtime_snapshot as schedule_v5

MODEL_VERSION = "CFB O/U UI V16 • CENTRAL RUNTIME TEAM-DATA HANDOFF"
FROZEN_PARENT_UI = "cfb_over_under_matchup_ui_v15_visible_data_path"
MARKET = "Over/Under"

_CSS16 = r"""
<style>
.cfbou16-status{margin:8px 0 2px;border:1px solid rgba(80,220,145,.28);border-radius:12px;
background:#071b13;padding:8px 10px;color:#a6efc9;font-size:.40rem;font-weight:900}
.cfbou16-status.partial{border-color:#705a20;background:#2a240d;color:#e2cb78}
.cfbou16-detail{display:block;color:#719985;font-size:.32rem;font-weight:700;margin-top:4px}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _hero_v16(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    # Profiles are already reconciled by base_hub.team_data. Do not re-fetch.
    return (
        frozen_v14._FROZEN_V13_HERO(game, away, home)
        + frozen_v14._current_data_panel(game, away, home)
    )


def _team_data_diagnostics_v16(diag: Mapping[str, Any]) -> str:
    status = _clean(diag.get("runtime_status")) or "PARTIAL"
    issues = diag.get("runtime_issues") or []
    snap = bool(diag.get("runtime_snapshot_used"))
    deep_ok = bool(diag.get("deep_reconciliation_ok"))
    err = _clean(diag.get("deep_reconciliation_error"))

    if status == "GREEN":
        cls = ""
        headline = "🟢 CURRENT TEAM DATA PATH GREEN"
    else:
        cls = " partial"
        headline = "🟡 CURRENT TEAM DATA PATH PARTIAL"

    source = (
        "verified local runtime snapshot"
        if snap
        else "live deep reconciliation"
        if deep_ok
        else "field-level fallback"
    )
    detail = " • ".join(str(x) for x in issues[:3]) if issues else "no record/venue/broadcast contradictions detected"
    if err:
        detail += f" • live error exposed: {err}"

    return f'''
<div class="cfbou16-status{cls}">
  {escape(headline)}
  <span class="cfbou16-detail">source: {escape(source)} • {escape(detail)}</span>
</div>'''


def _reset_runtime_caches_once() -> None:
    marker = "cfb_ou_v16_runtime_cache_reset"
    if st.session_state.get(marker):
        return

    try:
        schedule_v5.clear_schedule_cache()
    except Exception:
        pass
    try:
        runtime_team_data.clear_team_data_cache()
    except Exception:
        pass
    try:
        deep_slate.analyze_game.clear()
    except Exception:
        pass

    # Old scan result state can preserve rows from a prior data path.
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith("cfb_step9_top5_") or text.startswith("cfb_step9_scan_diag_"):
            try:
                del st.session_state[key]
            except Exception:
                pass

    st.session_state[marker] = True


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
):
    st.caption("🟢 CFB O/U • CENTRAL RUNTIME TEAM DATA V1 ACTIVE")
    st.markdown(_CSS16, unsafe_allow_html=True)
    _reset_runtime_caches_once()

    original_team_data = base_hub.team_data
    original_hero = frozen_v15._hero_v15
    original_deep_data = deep_slate.deep_data
    original_diag = frozen_v14._team_data_diagnostics_v14
    original_v15_schedule = frozen_v15.schedule_v4

    base_hub.team_data = runtime_team_data
    frozen_v15._hero_v15 = _hero_v16
    deep_slate.deep_data = runtime_deep
    frozen_v14._team_data_diagnostics_v14 = _team_data_diagnostics_v16
    frozen_v15.schedule_v4 = schedule_v5
    try:
        return frozen_v15.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        base_hub.team_data = original_team_data
        frozen_v15._hero_v15 = original_hero
        deep_slate.deep_data = original_deep_data
        frozen_v14._team_data_diagnostics_v14 = original_diag
        frozen_v15.schedule_v4 = original_v15_schedule


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
):
    if market != MARKET:
        raise ValueError(
            f"Runtime team-data O/U UI received unsupported market: {market}"
        )
    return render_over_under_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "FROZEN_PARENT_UI",
    "MARKET",
    "MODEL_VERSION",
    "_hero_v16",
    "_reset_runtime_caches_once",
    "_team_data_diagnostics_v16",
    "render_cfb_hub",
    "render_over_under_hub",
]
