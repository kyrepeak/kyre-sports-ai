"""Kyre Sports AI Streamlit entrypoint.

Memory-safe production router: load only the selected sport/market stack instead
of replaying the historical nested app-wrapper chain on every Streamlit rerun.
All model/projection behavior remains delegated to the existing frozen/current
market modules.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v1 import render_app


render_app()
