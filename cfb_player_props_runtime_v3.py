"""CFB Player Props Runtime V3 — exclusive Page-1/Page-2/Page-3 selector."""
from __future__ import annotations

import importlib
from typing import Any, Mapping

import streamlit as st

page1 = importlib.import_module("cfb_player_props_page1_v1")


class _LazyPage2:
    def render_cfb_player_props_page2(self) -> Any:
        return importlib.import_module("cfb_player_props_page2_v1").render_cfb_player_props_page2()


class _LazyPage3:
    def render_cfb_player_props_page3(self) -> Any:
        return importlib.import_module("cfb_player_props_page3_v1").render_cfb_player_props_page3()


page2 = _LazyPage2()
page3 = _LazyPage3()
MODEL_VERSION = "CFB_PLAYER_PROPS_RUNTIME_V3"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _pick(session: Mapping[str, Any], query: Mapping[str, Any], key: str) -> str:
    try:
        query_value = _text(query.get(key))
    except Exception:
        query_value = ""
    try:
        session_value = _text(session.get(key))
    except Exception:
        session_value = ""
    return query_value or session_value


def render_cfb_player_props_runtime() -> None:
    game_id = _pick(st.session_state, st.query_params, "game_id")
    if not game_id:
        page1.render_cfb_player_props_page1()
        return
    player_id = _pick(st.session_state, st.query_params, "player_id")
    prop = _pick(st.session_state, st.query_params, "prop")
    if player_id and prop:
        page3.render_cfb_player_props_page3()
        return
    page2.render_cfb_player_props_page2()


__all__ = ["MODEL_VERSION", "page1", "page2", "page3", "render_cfb_player_props_runtime"]
