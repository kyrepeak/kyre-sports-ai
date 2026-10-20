"""CFB Player Props Runtime V2 — isolated Page-1/Page-2 terminal wrapper."""
from __future__ import annotations

import importlib
from typing import Any, Mapping

import streamlit as st

page1 = importlib.import_module("cfb_player_props_page1_v1")


class _LazyPage2:
    def render_cfb_player_props_page2(self) -> Any:
        module = importlib.import_module("cfb_player_props_page2_v1")
        return module.render_cfb_player_props_page2()


page2 = _LazyPage2()
MODEL_VERSION = "CFB_PLAYER_PROPS_RUNTIME_V2"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _game_id(session: Mapping[str, Any], query: Mapping[str, Any]) -> str:
    try:
        query_id = _text(query.get("game_id"))
    except Exception:
        query_id = ""
    try:
        session_id = _text(session.get("game_id"))
    except Exception:
        session_id = ""
    return query_id or session_id


def render_cfb_player_props_runtime() -> None:
    if _game_id(st.session_state, st.query_params):
        page2.render_cfb_player_props_page2()
        return
    page1.render_cfb_player_props_page1()


__all__ = ["MODEL_VERSION", "page1", "page2", "render_cfb_player_props_runtime"]
