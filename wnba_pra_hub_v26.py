"""Compatibility route for the WNBA PRA command center.

The main app historically imported wnba_pra_hub_v26. Keep that stable import path
while forwarding the live WNBA PRA page to V2.8 Step 5 projected minutes + role.
"""
from wnba_pra_hub_v28 import MODEL_VERSION, render_wnba_pra_hub

__all__ = ["MODEL_VERSION", "render_wnba_pra_hub"]
