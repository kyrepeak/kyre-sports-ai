"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V4 preserves the frozen `streamlit_memory_lazy_router_v3` Hits route, the
`streamlit_memory_lazy_router_v2` shell, and the `streamlit_memory_lazy_router_v1`
bootstrap. Only MLB Moneyline advances to additive UI V16.6; Matchup Explorer and
Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v4 import render_app


render_app()
