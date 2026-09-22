"""Receiving Yards future-card HTML normalization.

Display-only helper for the frozen V2 receiver identity card HTML. Streamlit's
Markdown renderer can treat later indented <article> blocks as code when
multiple cards are concatenated. This helper removes only common indentation
and outer blank lines; it does not alter player data or card semantics.
"""
from __future__ import annotations

from textwrap import dedent
from typing import Any


def normalize_receiver_identity_card_html(body: Any) -> str:
    text = str(body if body is not None else "")
    return dedent(text).strip()


__all__ = ["normalize_receiver_identity_card_html"]
