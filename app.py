"""Kyre Sports AI Streamlit entrypoint — clean presentation router.

The V2 presentation shell wraps the frozen streamlit_memory_lazy_router_v1
bootstrap; it does not replay the historical app-wrapper chain.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v2 import render_app


render_app()
