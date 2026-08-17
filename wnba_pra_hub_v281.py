"""WNBA PRA V2.8.1 presentation bridge.

Uses the V2.8 UI while replacing its role engine with V2.8.1's verified usage
fallback + safer minute redistribution. Keeps all prior schedule/roster/context/
availability rendering intact.
"""
import streamlit as st
import wnba_pra_hub_v28 as v28
import wnba_role_v281 as role281

MODEL_VERSION = "PRA V2.8.1"

# All V2.8 rendering functions read the module-global `role` object at runtime.
v28.role = role281
v28.MODEL_VERSION = MODEL_VERSION


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🧠 PRA V2.8.1 • Advanced USG first • ESPN box-score usage fallback • workload-aware minute caps")
    return v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)

__all__ = ["MODEL_VERSION", "render_wnba_pra_hub"]
