"""WNBA Spread V1.6.4 — Step 3 HTML rendering repair.

Presentation-only compatibility layer over V1.6.3. The Step-3 data/profile
logic is unchanged; this wrapper only removes Markdown-significant indentation
from the generated Step-3 HTML fragment before Streamlit renders it. This
prevents nested team-form <div> blocks from being interpreted as indented code.
The protected V1.6.1 production model and Steps 1-2 remain untouched.
"""
from __future__ import annotations

import wnba_spread_hub_v163 as presentation

base = presentation.base
MODEL_VERSION = "WNBA SPREAD V1.6.4 • STEP 3 HTML RENDER REPAIR"
_ORIGINAL_FORM_BLOCK = presentation._form_block


def _compact_html(fragment: str) -> str:
    """Collapse generated HTML so Markdown cannot reinterpret nested tags as code."""
    return "".join(line.strip() for line in str(fragment or "").splitlines())


def _clean_form_block(day_str: str, row) -> str:
    return _compact_html(_ORIGINAL_FORM_BLOCK(day_str, row))


def _install_render_repair() -> None:
    # V1.6.3's _history_plus_form resolves _form_block from its module globals at
    # call time, so replacing only this presentation seam leaves all data/model
    # calculations unchanged while fixing HTML rendering deterministically.
    presentation._form_block = _clean_form_block


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_render_repair()
    return presentation.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(presentation, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
