"""WNBA Daily Picks V34 — runtime source-contract binding repair.

V34 preserves V33, V32 Step 11, the verified V31.1 Run-All-7 controller, every
source model, every simulation result, native qualification rules, and the
existing Daily Picks safety/ranking/final guard.

The repair is intentionally narrow: Streamlit can keep an already-imported
``wnba_daily_picks_standardizer_v2`` module alive across hot deploys. That older
module object can still point its ``v1`` global at Standardizer V1, where Points
``status=MONITOR LINEUP`` masks ``model_qualified=True``. The Points connector
therefore correctly reports qualified rows while the V33 source-winner board can
incorrectly report NO QUALIFIED PICK.

V34 rebinds the live Standardizer-V2 module object to the verified V1.1
source-contract repair before any seven-market visual bundle is built. It also
adds a read-only Points fallback that reads the same completed V19 standard
payload through V1.1 if a stale common frame still omits a source-qualified
Points row. No values are invented and no source state is written.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v33 as v33
import wnba_daily_picks_standardizer_v11 as repaired_props
import wnba_daily_picks_standardizer_v2 as standardizer_v2

MODEL_VERSION = "WNBA DAILY PICKS V34 • POINTS SOURCE-CONTRACT RUNTIME BINDING REPAIR"

_ORIGINAL_SOURCE_BEST = v33._source_best


def _install_runtime_binding() -> None:
    """Force every already-loaded Daily Picks path to use Standardizer V1.1."""
    # normalize_all() in Standardizer V2 resolves its module-global `v1` at call
    # time, so this assignment repairs both freshly imported and cached V2
    # module objects without reloading or touching source-model state.
    standardizer_v2.v1 = repaired_props

    # Bind the exact module objects reachable from the live V33/V32 chain too.
    # These assignments are deliberately defensive because Streamlit hot reloads
    # can preserve different portions of the import graph between deployments.
    try:
        v33.v32.seven.five_rank.standardizer.v2.v1 = repaired_props
    except Exception:
        pass
    try:
        v33.v32.seven.five_rank.four.standardizer.v1 = repaired_props
    except Exception:
        pass


def _day_from_common(common: pd.DataFrame) -> str:
    if isinstance(common, pd.DataFrame) and not common.empty and "Slate day" in common.columns:
        values = common["Slate day"].dropna().astype(str)
        if not values.empty:
            try:
                return pd.to_datetime(values.iloc[0]).strftime("%Y-%m-%d")
            except Exception:
                pass
    try:
        return v33.v32._today()
    except Exception:
        return ""


def _source_best_repaired(common: pd.DataFrame, market: str) -> pd.DataFrame:
    """Use V33 normally; only repair an impossible Points qualification mismatch."""
    best = _ORIGINAL_SOURCE_BEST(common, market)
    if str(market).upper() != "POINTS" or not best.empty:
        return best

    day = _day_from_common(common)
    if not day:
        return best

    # The passive connector is the source-of-truth proof that same-day Points
    # rows exist and that at least one row is natively model-qualified.
    try:
        feed = v33.v32.points_feed.status(day) or {}
    except Exception:
        feed = {}
    if not feed.get("connected") or int(feed.get("qualified") or 0) <= 0:
        return best

    # Re-read the exact completed V19 standard payload through the repaired
    # source-contract adapter. No simulations, grading, network calls or writes.
    try:
        direct = repaired_props.normalize_points(day)
    except Exception:
        direct = pd.DataFrame()
    if direct is None or direct.empty:
        return best
    return _ORIGINAL_SOURCE_BEST(direct, "POINTS")


# V33 resolves this helper dynamically while rendering both source-market cards
# and the aggregation audit, so the fallback remains presentation/read-only.
v33._source_best = _source_best_repaired


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_runtime_binding()
    st.caption(
        "🛠️ Daily Picks V34 • Points qualification handoff cache repair ACTIVE • "
        "19-vs-NO-QUALIFIED mismatch protected • source math unchanged"
    )
    return v33.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
