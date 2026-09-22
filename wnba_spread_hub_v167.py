"""WNBA Spread V1.6.7 — Step 4 stylesheet repair under Step 5.

V1.6.6 correctly appends Step 5 but calls the V1.6.3 renderer directly so that
Step 5's presentation seam is not overwritten. That also bypasses V1.6.5's
render-time stylesheet injection, leaving the Step-4 HTML structurally correct
but visually unstyled (large team logos / concatenated text on mobile).

This wrapper restores only the missing V1.6.5 CSS before delegating to V1.6.6.
No Step-4 calculations, Step-5 data, protected V1.6.1 model outputs, market
transport, analytical probability, 5,000,000 Monte Carlo, convergence,
qualification, selected side, edge/EV, Pick Strength or ranking are changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_spread_hub_v166 as presentation

base = presentation.base
MODEL_VERSION = "WNBA SPREAD V1.6.7 • STEP 4 STYLE REPAIR + STEP 5"

_STEP4_CSS = r"""
<style>
.ks-spread165-wrap{background:#0a1723;border:1px solid #36546d;border-radius:15px;padding:12px;margin-top:14px}
.ks-spread165-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#9ed9ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.ks-spread165-scope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}.ks-spread165-teams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.ks-spread165-team{background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}.ks-spread165-teamhead{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:7px;margin-bottom:9px}
.ks-spread165-teamhead b{display:block;color:#f5fbff;font-size:.73rem;line-height:1.15}.ks-spread165-teamhead small{display:block;color:#7890a5;font-size:.44rem;font-weight:900;margin-top:3px;letter-spacing:.03em}
.ks-spread165-logo{width:32px;height:32px;display:flex;align-items:center;justify-content:center}.ks-spread165-logo img{max-width:32px;max-height:32px;object-fit:contain}
.ks-spread165-chip{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.45rem;font-weight:950;white-space:nowrap}.ks-spread165-chip.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread165-chip.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread165-chip.warn,.ks-spread165-chip.bad{border-color:#7c5832;background:#352516;color:#ffc984}
.ks-spread165-grid,.ks-spread165-compgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread165-grid div,.ks-spread165-compgrid div{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px}.ks-spread165-compgrid .wide{grid-column:1/-1}
.ks-spread165-grid small,.ks-spread165-compgrid small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread165-grid strong,.ks-spread165-compgrid strong{display:block;color:#f6fbff;font-size:.69rem;margin-top:3px;line-height:1.3}
.ks-spread165-compgrid strong.good{color:#7df2ba}.ks-spread165-compgrid strong.bad{color:#ffb0b7}.ks-spread165-compgrid strong.mid{color:#ffe17a}.ks-spread165-compgrid strong.warn{color:#ffc984}
.ks-spread165-compare{margin-top:9px;background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}.ks-spread165-comparehead{color:#a8cce2;font-size:.49rem;font-weight:950;letter-spacing:.045em;margin-bottom:7px}
.ks-spread165-note{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread165-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread165-head{align-items:flex-start}.ks-spread165-teams{grid-template-columns:1fr}.ks-spread165-chip{font-size:.43rem}}
</style>
"""


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Restore only V1.6.5's CSS that V1.6.6 bypasses by design. V1.6.6 still
    # owns all Step-5 installation/data/rendering and delegates the production
    # work to the same verified lower layers.
    st.markdown(_STEP4_CSS, unsafe_allow_html=True)
    return presentation.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(presentation, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
