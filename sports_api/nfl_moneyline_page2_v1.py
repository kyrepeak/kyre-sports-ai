"""Lightweight facade for the NFL Moneyline Page 2 Kyre Sports API owner.

Loads the dedicated API module directly so unrelated API package initializers do
not become a dependency of the NFL Moneyline Streamlit route.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_OWNER_PATH = Path(__file__).resolve().parent / "api" / "nfl_moneyline_page2_v1.py"
_SPEC = importlib.util.spec_from_file_location("_kyre_nfl_moneyline_page2_api_v1", _OWNER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL_MONEYLINE_PAGE2_API_OWNER_LOAD_FAILED")
_OWNER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_OWNER)
for _name in _OWNER.__all__:
    globals()[_name] = getattr(_OWNER, _name)
__all__ = list(_OWNER.__all__)
