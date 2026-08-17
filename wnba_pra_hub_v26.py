"""Compatibility route for the WNBA PRA command center.

The main app historically imports wnba_pra_hub_v26. Keep that stable import path
while forwarding the live WNBA PRA page to V2.7 Step 4 availability + explicit
starter verification.
"""
from wnba_pra_hub_v27 import MODEL_VERSION, render_wnba_pra_hub

__all__ = ["MODEL_VERSION", "render_wnba_pra_hub"]
