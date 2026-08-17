"""WNBA PRA V2.8.3 isolated Step-5 compatibility hotfix.

WNBA-only patch. MLB routing/schedule/model files are intentionally untouched.
"""
import streamlit as st
import wnba_pra_hub_v28 as v28
import wnba_role_v282 as role282

MODEL_VERSION = "PRA V2.8.3"

_original_role = v28.role
for _helper in ("_num", "_day_str"):
    if not hasattr(role282, _helper) and hasattr(_original_role, _helper):
        setattr(role282, _helper, getattr(_original_role, _helper))

if not hasattr(role282, "availability"):
    role282.availability = _original_role.availability
if not hasattr(role282.availability, "_norm_name") and hasattr(_original_role.availability, "_norm_name"):
    role282.availability._norm_name = _original_role.availability._norm_name

v28.role = role282
v28.MODEL_VERSION = MODEL_VERSION


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🧠 PRA V2.8.3 • WNBA-isolated hotfix • usage/minutes compatibility restored • MLB untouched")
    return v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "render_wnba_pra_hub"]
