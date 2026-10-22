"""Sticky KYRE SPORTS renderer for Universal Sports Navigation V1."""
from __future__ import annotations

from base64 import b64decode, b64encode
from io import BytesIO
from pathlib import Path
import tarfile

import streamlit as st

from universal_sports_nav_controller_v1 import RouteIntent, RouteState
from universal_sports_nav_registry_v1 import get_sport, visible_sports


NAV_CONTAINER_KEY = "ks_universal_nav_shell"
SPORT_CONTROL_KEY = "ks_universal_sport_pills"
MARKET_CONTROL_KEY = "ks_universal_market_pills"
HEADER_TITLE = "KYRE SPORTS AI"
HEADER_SUBTITLE = "Professional Sports Analytics"

# Presentation-only league marks. They never participate in sports data routing.
# The optimized SVG bundle is vendored with the app in connector-safe fragments,
# reconstructed locally at import time, then embedded into CSS as data URIs.
_SPORT_IDS_WITH_LOGOS = ("nfl", "cfb", "nba", "mlb", "wnba")
_SPORT_LOGO_BUNDLE_PARTS = tuple(
    f"assets/league_logos/league_marks_v1.b64part{index}" for index in range(7)
)


def _load_sport_logo_data_uris() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    encoded = "".join(
        (root / relative_path).read_text(encoding="ascii").strip()
        for relative_path in _SPORT_LOGO_BUNDLE_PARTS
    )
    archive_bytes = b64decode(encoded)
    logos: dict[str, str] = {}
    with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as bundle:
        for sport_id in _SPORT_IDS_WITH_LOGOS:
            member = bundle.extractfile(f"{sport_id}.svg")
            if member is None:
                raise RuntimeError(f"Missing local league mark for {sport_id}")
            svg_bytes = member.read()
            logos[sport_id] = "data:image/svg+xml;base64," + b64encode(svg_bytes).decode("ascii")
    return logos


_SPORT_LOGO_DATA_URIS = _load_sport_logo_data_uris()

_NAV_CSS_TEMPLATE = r"""
<style>
.st-key-ks_universal_nav_shell{
    position: sticky;
    top: .2rem;
    z-index: 950;
    margin: 0 0 .82rem 0;
    padding: .72rem .76rem .68rem;
    border: 1px solid rgba(125,211,252,.19);
    border-radius: 18px;
    background:
        radial-gradient(circle at 9% 0%,rgba(56,189,248,.10),transparent 29%),
        linear-gradient(145deg,rgba(7,13,23,.985),rgba(8,16,28,.975));
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow: 0 14px 38px rgba(2,6,23,.34), inset 0 1px 0 rgba(255,255,255,.025);
}
.st-key-ks_universal_nav_shell .ks-universal-brand{
    margin: 0 0 .52rem .14rem;
    font-size: 0;
    line-height: 1;
    display: flex;
    flex-direction: column;
    gap: .18rem;
}
.st-key-ks_universal_nav_shell .ks-universal-brand::before,
.st-key-ks_universal_nav_shell .ks-universal-brand-title{
    content: "KYRE SPORTS AI";
    color: #f8fafc;
    font-size: .83rem;
    font-weight: 950;
    letter-spacing: .12em;
    line-height: 1.05;
}
.st-key-ks_universal_nav_shell .ks-universal-brand::after,
.st-key-ks_universal_nav_shell .ks-universal-brand-subtitle{
    content: "Professional Sports Analytics";
    color: #7dd3fc;
    font-size: .62rem;
    font-weight: 800;
    letter-spacing: .055em;
    line-height: 1.05;
    opacity: .78;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"]{
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"]::-webkit-scrollbar{display:none}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] [role="radiogroup"]{
    display: flex;
    flex-wrap: nowrap !important;
    width: max-content;
    min-width: 100%;
    gap: .38rem;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button{
    flex: 0 0 auto;
    min-height: 37px;
    border-radius: 999px !important;
    white-space: nowrap;
    font-weight: 850;
    letter-spacing: .01em;
    transition: border-color .14s ease,background .14s ease,transform .14s ease,box-shadow .14s ease;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button[aria-checked="true"]{
    border-color: rgba(125,211,252,.86) !important;
    background: linear-gradient(180deg,rgba(56,189,248,.18),rgba(14,165,233,.10)) !important;
    color: #eefaff !important;
    box-shadow: inset 0 0 0 1px rgba(125,211,252,.08),0 0 18px rgba(14,165,233,.10);
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button:focus-visible{
    outline: 2px solid #7dd3fc !important;
    outline-offset: 2px;
}
[class*="st-key-ks_universal_sport_pills__"] button{
    min-height: 42px !important;
    padding-inline: .76rem .86rem !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: .48rem !important;
}
[class*="st-key-ks_universal_sport_pills__"] button::before{
    content: "";
    display: inline-block;
    width: 24px;
    height: 24px;
    flex: 0 0 24px;
    background-position: center;
    background-repeat: no-repeat;
    background-size: contain;
    filter: drop-shadow(0 2px 5px rgba(0,0,0,.28));
}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(1)::before{background-image:url("__NFL_LOGO__")}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(2)::before{background-image:url("__CFB_LOGO__")}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(3)::before{background-image:url("__NBA_LOGO__")}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(4)::before{background-image:url("__MLB_LOGO__")}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(5)::before{background-image:url("__WNBA_LOGO__")}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(3)::before,
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(5)::before{width:17px;flex-basis:17px}
[class*="st-key-ks_universal_sport_pills__"] button:nth-of-type(4)::before{width:29px;flex-basis:29px}
@media(max-width:640px){
    .st-key-ks_universal_nav_shell{top:.12rem;padding:.62rem .56rem .6rem;border-radius:15px;margin-bottom:.7rem}
    .st-key-ks_universal_nav_shell .ks-universal-brand{margin-bottom:.46rem}
    [class*="st-key-ks_universal_sport_pills__"] button{min-height:42px !important;padding-inline:.68rem .76rem !important}
    [class*="st-key-ks_universal_sport_pills__"] button::before{width:22px;height:22px;flex-basis:22px}
    .st-key-ks_universal_nav_shell div[data-testid="stPills"] button{min-height:38px}
}
</style>
"""

_NAV_CSS = (
    _NAV_CSS_TEMPLATE
    .replace("__NFL_LOGO__", _SPORT_LOGO_DATA_URIS["nfl"])
    .replace("__CFB_LOGO__", _SPORT_LOGO_DATA_URIS["cfb"])
    .replace("__NBA_LOGO__", _SPORT_LOGO_DATA_URIS["nba"])
    .replace("__MLB_LOGO__", _SPORT_LOGO_DATA_URIS["mlb"])
    .replace("__WNBA_LOGO__", _SPORT_LOGO_DATA_URIS["wnba"])
)

# Registry metadata is immutable for the lifetime of this module. Build the
# option/label maps once instead of reconstructing them on every Streamlit rerun.
_NAV_SPORTS = visible_sports()
_SPORT_IDS = tuple(sport.id for sport in _NAV_SPORTS)
_SPORT_LABELS = {sport.id: sport.label for sport in _NAV_SPORTS}
_MARKET_IDS_BY_SPORT = {
    sport.id: tuple(market.id for market in sport.markets if market.live)
    for sport in _NAV_SPORTS
}
_MARKET_LABELS_BY_SPORT = {
    sport.id: {market.id: market.label for market in sport.markets if market.live}
    for sport in _NAV_SPORTS
}


def _brand_markup() -> str:
    return (
        '<div class="ks-universal-brand">'
        f'<span class="ks-universal-brand-title">{HEADER_TITLE}</span>'
        f'<span class="ks-universal-brand-subtitle">{HEADER_SUBTITLE}</span>'
        '</div>'
    )


def _sport_label(sport_id: str) -> str:
    sport = get_sport(sport_id)
    return sport.label if sport else sport_id.upper()


def _market_label(sport_id: str, market_id: str) -> str:
    sport = get_sport(sport_id)
    if sport is None:
        return market_id
    market = next((item for item in sport.markets if item.id == market_id), None)
    return market.label if market else market_id


def render_universal_nav(state: RouteState) -> RouteIntent | None:
    sports = _NAV_SPORTS
    sport_ids = _SPORT_IDS
    active_sport = get_sport(state.sport_id)
    if active_sport is None:
        active_sport = sports[0]

    sport_widget_key = f"{SPORT_CONTROL_KEY}__{state.epoch}"
    market_widget_key = f"{MARKET_CONTROL_KEY}__{state.epoch}"

    with st.container(key=NAV_CONTAINER_KEY):
        st.markdown(_NAV_CSS, unsafe_allow_html=True)
        st.markdown(_brand_markup(), unsafe_allow_html=True)
        selected_sport = st.pills(
            "Sport",
            sport_ids,
            default=state.sport_id if state.sport_id in sport_ids else active_sport.id,
            key=sport_widget_key,
            format_func=_SPORT_LABELS.get,
            selection_mode="single",
            label_visibility="collapsed",
        )

        market_ids = _MARKET_IDS_BY_SPORT[active_sport.id]
        selected_market = st.pills(
            "Market",
            market_ids,
            default=state.market_id if state.market_id in market_ids else active_sport.default_market_id,
            key=market_widget_key,
            format_func=_MARKET_LABELS_BY_SPORT[active_sport.id].get,
            selection_mode="single",
            label_visibility="collapsed",
        )

    if selected_sport and selected_sport != state.sport_id:
        return RouteIntent(sport_id=str(selected_sport), source="tap")
    if selected_market and selected_market != state.market_id:
        return RouteIntent(sport_id=state.sport_id, market_id=str(selected_market), source="tap")
    return None


__all__ = [
    "HEADER_SUBTITLE", "HEADER_TITLE", "MARKET_CONTROL_KEY", "NAV_CONTAINER_KEY",
    "SPORT_CONTROL_KEY", "render_universal_nav",
]
