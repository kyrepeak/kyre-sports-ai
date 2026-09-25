"""NFL Passing Yards V85 — same-tab direct full-analysis transport.

Speed Phase Step 7 public transport repair. V84 proved the Streamlit widget
rerun path still adds large public roundtrip overhead. V85 uses st.html in the
main app DOM with a same-tab direct navigation to the already-certified
ks_py_full=1 route. The full route continues through frozen V84 -> V83 -> V82.

No football value, data provider, projection, context, probability, market,
sportsbook, widget-selection key, or stake behavior changes.
"""
from __future__ import annotations

import json

import streamlit as st

import nfl_passing_yards_hub_v79 as lazy_v79
import nfl_passing_yards_hub_v83 as same_session_v83
import nfl_passing_yards_hub_v84 as prior

MODEL_VERSION = "NFL PASSING YARDS V85 • SPEED STEP 7 SAME-TAB DIRECT FULL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v84"
SPEED_PHASE_STEP = 7
TRANSITION_VERSION = "v85"
SAME_TAB_DIRECT_TRANSPORT = True
PRESENTATION_ONLY = False
TRANSPORT_NAVIGATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
_LINK_ID = "ks-py85-load-full"


def _lazy_slot() -> int | None:
    lazy_v79.selection._restore_context_from_query()
    raw_slot = lazy_v79.selection._param("ks_qb_slot")
    return int(raw_slot) if raw_slot in {"1", "2"} else None


def _direct_full_url(slot: int) -> str:
    hints = lazy_v79.prior._query_hints(slot)
    return lazy_v79._full_url(slot, hints)


def _same_tab_control_html(full_url: str) -> str:
    href = str(full_url or "")
    href_json = json.dumps(href)
    return f"""
    <div data-passing-yards-same-tab-owner="v85"
         data-passing-yards-speed-step="7"
         data-step7-transport="same-tab-direct-full">
      <a id="{_LINK_ID}" href="{href}" target="_self"
         style="display:flex;align-items:center;justify-content:center;width:100%;
                min-height:44px;border-radius:999px;text-decoration:none;
                font-weight:900;letter-spacing:.02em;border:1px solid currentColor;"
         aria-label="Load Full Analysis">Load Full Analysis →</a>
    </div>
    <script>
    (() => {{
      const link = document.getElementById("{_LINK_ID}");
      if (!link || link.dataset.ksPy85Bound === "1") return;
      link.dataset.ksPy85Bound = "1";
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        window.location.assign({href_json});
      }});
    }})();
    </script>
    """


def _render_same_tab_lazy(slot: int) -> None:
    hints = lazy_v79.prior._query_hints(slot)
    shell = same_session_v83._strip_legacy_load_link(
        lazy_v79.build_lazy_detail_shell(slot, hints)
    )
    st.html(
        _same_tab_control_html(lazy_v79._full_url(slot, hints)),
        width="stretch",
        unsafe_allow_javascript=True,
    )
    st.markdown(shell, unsafe_allow_html=True)


def render_nfl_passing_yards_hub() -> None:
    slot = _lazy_slot()
    if slot is not None and not lazy_v79._full_requested():
        return _render_same_tab_lazy(slot)

    st.markdown(
        '<span data-passing-yards-same-tab-owner="v85" '
        'data-passing-yards-speed-step="7" '
        'data-step7-transport="same-tab-direct-full" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V85 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR","MAY_MODIFY_CONTEXT_MATH","MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_MARKET_MATH","MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION",
    "PRESENTATION_ONLY","SAME_TAB_DIRECT_TRANSPORT","SPEED_PHASE_STEP",
    "SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED","TRANSITION_VERSION",
    "TRANSPORT_NAVIGATION_ONLY","_direct_full_url","_lazy_slot",
    "_render_same_tab_lazy","_same_tab_control_html","render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
