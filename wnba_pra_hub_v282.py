"""WNBA PRA V2.8.2 presentation bridge."""
import streamlit as st
import wnba_pra_hub_v28 as v28
import wnba_role_v282 as role282

MODEL_VERSION = "PRA V2.8.2"

v28.role = role282
v28.MODEL_VERSION = MODEL_VERSION


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🧠 PRA V2.8.2 • hardened usage fallback • workload-aware minutes • provider errors contained")
    return v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)

__all__ = ["MODEL_VERSION", "render_wnba_pra_hub"]
