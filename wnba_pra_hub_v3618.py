"""WNBA PRA V3.6.18 — bounded refresh-to-ready convergence successor.

Handoff-only successor over V3.6.17. Model math, provider routing, snapshot
assembly, and Page 1 presentation are preserved.
"""
from __future__ import annotations

import time

import wnba_pra_hub_v3617 as previous
from wnba_pra_page_snapshot_client_v1 import WNBAPRASnapshotClientError
from wnba_pra_page_snapshot_publish_v1 import WNBAPRASnapshotPublishError

MODEL_VERSION = "PRA V3.6.18 • REFRESH HANDOFF CONVERGENCE • MODEL PRESERVED"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH
STEP5_FROZEN_BASELINE = previous.STEP5_FROZEN_BASELINE
PRECISION_STEP1_CONTRACT = previous.PRECISION_STEP1_CONTRACT
PAGE_CLEANUP_CONTRACT = previous.PAGE_CLEANUP_CONTRACT
PLAYOFF_PRODUCT_CONTRACT = previous.PLAYOFF_PRODUCT_CONTRACT
FANDUEL_PRODUCT_CONTRACT = previous.FANDUEL_PRODUCT_CONTRACT
MULTISOURCE_PRODUCT_CONTRACT = previous.MULTISOURCE_PRODUCT_CONTRACT

resolve_active_slate_date = previous.resolve_active_slate_date
fetch_page_snapshot = previous.fetch_page_snapshot
_refresh = previous._refresh
_render_degraded = previous._render_degraded
render_page_snapshot = previous.render_page_snapshot

_CONVERGENCE_DELAYS_SECONDS = (0.0, 0.25, 0.75)
_TRANSIENT_STATES = {"MODEL_UNAVAILABLE", "MODEL_REFRESH_REQUIRED"}
_convergence_sleep = time.sleep


def _fetch_until_converged(day: str) -> dict:
    """Bounded read-after-refresh convergence; never issues another refresh."""
    last: dict | None = None
    for delay in _CONVERGENCE_DELAYS_SECONDS:
        if delay:
            _convergence_sleep(delay)
        last = fetch_page_snapshot(day, season=2026)
        state = str(last.get("snapshot_state") or "MODEL_UNAVAILABLE")
        cache = str(last.get("cache_state") or "MODEL_UNAVAILABLE")
        if state == "READY" and cache in {"FRESH", "STALE_SAFE"}:
            return last
        if state not in _TRANSIENT_STATES and cache != "MODEL_UNAVAILABLE":
            return last
    return last or {
        "snapshot_state": "MODEL_UNAVAILABLE",
        "cache_state": "MODEL_UNAVAILABLE",
        "date": day,
        "season": 2026,
    }


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    day = resolve_active_slate_date()
    try:
        payload = fetch_page_snapshot(day, season=2026)
    except WNBAPRASnapshotClientError:
        return _render_degraded(day, section_header, status_info, team_logo, h)

    state = str(payload.get("snapshot_state") or "MODEL_UNAVAILABLE")
    cache = str(payload.get("cache_state") or "MODEL_UNAVAILABLE")

    if state == "MODEL_UNAVAILABLE":
        try:
            import streamlit as st
            st.warning("WNBA PRA model artifact is rebuilding through the certified Kyre data path.")
        except Exception:
            pass
        try:
            if _refresh(day, background=False):
                payload = _fetch_until_converged(day)
        except (WNBAPRASnapshotPublishError, WNBAPRASnapshotClientError):
            return _render_degraded(day, section_header, status_info, team_logo, h)
        render_page_snapshot(payload, section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)
        return payload

    render_page_snapshot(payload, section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)
    if payload.get("refresh_required") is True or cache == "STALE_SAFE" or state == "MODEL_REFRESH_REQUIRED":
        try:
            _refresh(day, background=True)
        except WNBAPRASnapshotPublishError:
            pass
    return payload


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "STEP5_FROZEN_BASELINE",
    "PRECISION_STEP1_CONTRACT", "PAGE_CLEANUP_CONTRACT", "PLAYOFF_PRODUCT_CONTRACT",
    "FANDUEL_PRODUCT_CONTRACT", "MULTISOURCE_PRODUCT_CONTRACT", "resolve_active_slate_date",
    "render_wnba_pra_hub",
]
