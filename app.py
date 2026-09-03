"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V3 preserves the frozen V2/V1 routing contract and changes only the MLB
1+ Hit presentation route to UI V13.16. Matchup Explorer remains frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v3 import render_app


render_app()
