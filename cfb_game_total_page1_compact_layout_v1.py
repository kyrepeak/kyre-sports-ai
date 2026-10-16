"""CFB Game Total Page 1 — compact mobile presentation V1.

Presentation-only successor to V45. The frozen Page-1 data/model chain remains
unchanged; this layer only changes how already-rendered analysis HTML is
presented. Deep analysis sections become one exclusive collapsed accordion and
verified two-team comparison surfaces stay side-by-side on narrow screens.

Page 2 intentionally does not import this module and remains on frozen V45.
"""
from __future__ import annotations

from contextlib import contextmanager
import re
from threading import RLock
from typing import Any, Callable

import streamlit as st

import cfb_game_total_clean_page_v45 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 COMPACT LAYOUT V1"
MARKET = prior.MARKET
FROZEN_PRODUCT_OWNER = "cfb_game_total_clean_page_v45"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_COMPACT_LAYOUT_V1_ACTIVE"
ACCORDION_NAME = "gt-page1-analysis"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
NEW_PROVIDER_PATHS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_LOCK = RLock()
_DETAILS_TAG = re.compile(
    r'<details\b(?=[^>]*\bclass="[^"]*\bgt159-step\b[^"]*")[^>]*>',
    flags=re.IGNORECASE,
)
_OPEN_ATTR = re.compile(r"\s+open(?=\s|>)", flags=re.IGNORECASE)
_NAME_ATTR = re.compile(r"\s+name\s*=", flags=re.IGNORECASE)


PAGE1_COMPACT_LAYOUT_CSS = r"""
<style id="gt-page1-compact-layout-v1">
/* Keep collapsed analysis rows compact; underlying content remains untouched. */
.gt159-step{margin:8px 0!important;border-radius:18px!important}
.gt159-step:not([open]){min-height:0!important}
.gt159-step:not([open])>summary{min-height:58px!important;padding-top:10px!important;padding-bottom:10px!important}
.gt159-step[open]>summary{margin-bottom:4px!important}

/* Phone layout: compare teams across the screen instead of one giant card per row. */
@media(max-width:560px){
  .gt165-team-pair,
  .gt167-team-pair,
  .gt227-grid{
    grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr)!important;
    gap:5px!important;
    align-items:stretch!important;
  }

  .gt165-vs,
  .gt167-vs,
  .gt227-vs{
    display:grid!important;
    place-items:center!important;
    width:24px!important;
    min-width:24px!important;
    height:24px!important;
    align-self:center!important;
    justify-self:center!important;
    font-size:8px!important;
  }

  .gt165-vs:before,.gt165-vs:after,
  .gt167-vs:before,.gt167-vs:after{
    display:none!important;
  }

  .gt165-idcard,
  .gt167-profile,
  .gt227-card{
    min-width:0!important;
    padding:9px 7px!important;
    border-radius:15px!important;
  }

  .gt165-idlogo,.gt165-idlogo-fallback{
    width:34px!important;
    height:34px!important;
    flex-basis:34px!important;
  }

  .gt227-logo,.gt227-logo-fallback{
    width:36px!important;
    height:36px!important;
  }

  .gt165-name,.gt167-teamname,.gt227-name{
    font-size:12px!important;
    line-height:1.1!important;
    overflow-wrap:anywhere!important;
  }

  .gt165-fields,
  .gt227-stats{
    gap:5px!important;
  }

  .gt165-field,
  .gt227-stat{
    min-width:0!important;
    padding:6px 5px!important;
  }

  .gt165-field b,.gt227-stat b{
    font-size:11px!important;
  }

  .gt165-field span,.gt227-stat span,
  .gt167-metric span{
    font-size:6px!important;
    letter-spacing:.03em!important;
  }

  .gt167-metrics{
    gap:5px!important;
  }

  .gt167-metric{
    min-width:0!important;
    padding:7px 4px!important;
  }

  .gt167-metric b{
    font-size:11px!important;
  }
}
</style>
"""


def compact_step_html(html: str) -> str:
    """Make already-rendered Page-1 analysis details collapsed and exclusive."""
    text = str(html)
    if "gt159-step" not in text or "<details" not in text:
        return text

    def _compact(match: re.Match[str]) -> str:
        tag = _OPEN_ATTR.sub("", match.group(0))
        if not _NAME_ATTR.search(tag):
            tag = tag[:-1] + f' name="{ACCORDION_NAME}">'
        return tag

    return _DETAILS_TAG.sub(_compact, text)


@contextmanager
def install_compact_page1_presentation():
    """Intercept only unsafe HTML emitted during the V45 Page-1 render."""
    with _LOCK:
        original_markdown: Callable[..., Any] = st.markdown

        def _markdown(body: Any, *args: Any, **kwargs: Any):
            unsafe = bool(kwargs.get("unsafe_allow_html", args[0] if args else False))
            if unsafe and isinstance(body, str):
                body = compact_step_html(body)
            return original_markdown(body, *args, **kwargs)

        st.markdown = _markdown  # type: ignore[assignment]
        try:
            yield
        finally:
            st.markdown = original_markdown  # type: ignore[assignment]


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render frozen V45 data/product truth through the compact Page-1 shell."""
    st.markdown(PAGE1_COMPACT_LAYOUT_CSS, unsafe_allow_html=True)
    with install_compact_page1_presentation():
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Compact Page 1 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACCORDION_NAME",
    "ACTIVE_MARKER",
    "FROZEN_PRODUCT_OWNER",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "NEW_PROVIDER_PATHS_ADDED",
    "PAGE1_COMPACT_LAYOUT_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "compact_step_html",
    "install_compact_page1_presentation",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
