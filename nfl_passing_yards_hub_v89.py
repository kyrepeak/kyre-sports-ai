"""NFL Passing Yards V89 — synchronized two-quarterback comparison dashboard.

Presentation-only successor for Universal Runtime V5. Reuses the frozen V43/V34
certified capture pipeline and changes only the final composition. No football
model, probability, market, identity, provider, sportsbook, or stake behavior is
recomputed or modified.
"""
from __future__ import annotations

from html import escape
import importlib
from typing import Any

MODEL_VERSION = "NFL PASSING YARDS V89 • SYNCHRONIZED QB COMPARISON"
CERTIFIED_CAPTURE_OWNER = "nfl_passing_yards_hub_v43"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_DASH_CSS = r"""<style data-passing-yards-comparison-css="v89">
.ks-py89,.ks-py89 *{box-sizing:border-box}.ks-py89{max-width:1180px;margin:.35rem auto 1.2rem;color:#eef7ff}
.ks-py89-hero{border:1px solid rgba(78,190,255,.32);border-radius:22px;padding:18px;background:radial-gradient(circle at 88% 0%,rgba(69,196,255,.13),transparent 34%),linear-gradient(145deg,#091a29,#07131e);box-shadow:0 18px 48px rgba(0,0,0,.22)}
.ks-py89-kicker{font-size:.6rem;font-weight:950;letter-spacing:.14em;color:#77d8ff;text-transform:uppercase}.ks-py89-title{margin:4px 0 0;font-size:clamp(1.55rem,3.2vw,2.25rem);font-weight:950;letter-spacing:-.035em}.ks-py89-sub{margin:7px 0 0;color:#91a8ba;font-size:.72rem;line-height:1.5;max-width:820px}
.ks-py89-nav{position:sticky;top:52px;z-index:50;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;margin:9px 0 12px;padding:7px;border:1px solid rgba(71,151,203,.22);border-radius:14px;background:rgba(6,16,25,.96);backdrop-filter:blur(12px)}.ks-py89-nav::-webkit-scrollbar{display:none}.ks-py89-nav a{flex:0 0 auto;text-decoration:none!important;color:#98b4c8!important;border:1px solid #24445b;border-radius:999px;padding:6px 9px;font-size:.5rem;font-weight:900}.ks-py89-nav a:first-child{color:#eaf8ff!important;border-color:#3d8fbe;background:#0e3149}
.ks-py89-overview-title{margin:11px 2px 7px;color:#dff4ff;font-size:.7rem;font-weight:950}.ks-py89-overview,.ks-py89-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:start}.ks-py89-qb{min-width:0;border:1px solid #29475c;border-radius:17px;background:linear-gradient(145deg,#091824,#07121c);padding:10px;overflow:hidden}.ks-py89-qbtop{font-size:.53rem;color:#79d8ff;font-weight:950;letter-spacing:.08em;text-transform:uppercase;margin-bottom:7px}.ks-py89-snapshot{display:grid;grid-template-columns:1fr;gap:7px;margin-top:7px}
.ks-py89-section{scroll-margin-top:108px;margin-top:10px;border:1px solid #254156;border-radius:18px;background:#07141e;overflow:hidden}.ks-py89-section>summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;color:#dff4ff;font-size:.67rem;font-weight:950}.ks-py89-section>summary::-webkit-details-marker{display:none}.ks-py89-section>summary:after{content:'+';color:#72cfff;font-size:1rem}.ks-py89-section[open]>summary:after{content:'−'}.ks-py89-sectionbody{padding:0 10px 10px}.ks-py89-cell{min-width:0;border:1px solid #1d3445;border-radius:14px;background:#081722;padding:8px;overflow:hidden}.ks-py89-label{display:block;margin:0 0 6px;color:#7896aa;font-size:.46rem;font-weight:950;text-transform:uppercase;letter-spacing:.07em}
.ks-py89-env{scroll-margin-top:108px;margin-top:10px;border:1px solid #254156;border-radius:18px;background:#07141e;padding:10px}.ks-py89-env h3{margin:0 0 8px;font-size:.69rem;color:#dff4ff}.ks-py89-missing{padding:12px;color:#70899a;font-size:.58rem;border:1px dashed #294355;border-radius:10px}.ks-py89 .kpass29-build{display:none!important}
@media(max-width:760px){.ks-py89-overview,.ks-py89-pair{grid-template-columns:1fr}.ks-py89-nav{top:46px}.ks-py89-hero{padding:14px;border-radius:17px}.ks-py89-section{scroll-margin-top:102px}}
</style>"""

_NAV = (
    ("py-overview", "Overview"), ("py-profile", "Profile"), ("py-defense", "Defense"),
    ("py-pressure", "Pressure"), ("py-weapons", "Weapons"), ("py-environment", "Environment"),
    ("py-projection", "Projection"), ("py-probability", "Probability"), ("py-market", "Market"),
)


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _fallback(label: str) -> str:
    return f'<div class="ks-py89-missing">{escape(label)} unavailable for this quarterback.</div>'


def _cell(label: str, content: str) -> str:
    return f'<div class="ks-py89-cell"><span class="ks-py89-label">{escape(label)}</span>{content or _fallback(label)}</div>'


def _pair_section(section_id: str, title: str, captured: dict[str, list[str]], key: str, *, open_default: bool = False) -> str:
    opened = " open" if open_default else ""
    return (
        f'<details class="ks-py89-section" id="{escape(section_id)}"{opened}>'
        f'<summary>{escape(title)}<span>QB vs QB</span></summary><div class="ks-py89-sectionbody"><div class="ks-py89-pair">'
        + _cell("Away quarterback", _piece(captured, key, 0))
        + _cell("Home quarterback", _piece(captured, key, 1))
        + '</div></div></details>'
    )


def _overview_qb(captured: dict[str, list[str]], index: int) -> str:
    return (
        f'<article class="ks-py89-qb" data-comparison-qb="{index + 1}"><div class="ks-py89-qbtop">Quarterback {index + 1}</div>'
        + (_piece(captured, "identity", index) or _fallback("Quarterback identity"))
        + '<div class="ks-py89-snapshot">'
        + _cell("Baseline projection", _piece(captured, "projection", index))
        + _cell("Current market + final lean", _piece(captured, "market", index))
        + '</div></article>'
    )


def _comparison_dashboard_html(captured: dict[str, list[str]]) -> str:
    nav = ('<a href="#py-overview">Overview</a><a href="#py-profile">Profile</a><a href="#py-defense">Defense</a>'
           '<a href="#py-pressure">Pressure</a><a href="#py-weapons">Weapons</a><a href="#py-environment">Environment</a>'
           '<a href="#py-projection">Projection</a><a href="#py-probability">Probability</a><a href="#py-market">Market</a>')
    env = _piece(captured, "environment", 0) or _fallback("Game environment")
    return ''.join([
        _DASH_CSS,
        '<section class="ks-py89" data-passing-yards-comparison="v89">',
        '<header class="ks-py89-hero"><div class="ks-py89-kicker">KYRE SPORTS AI • NFL</div>',
        '<h1 class="ks-py89-title">🏈 Passing Yards • QB Comparison</h1>',
        '<p class="ks-py89-sub">Compare both quarterbacks in the same lane. Certified model values are unchanged; this view only reorganizes the evidence so the matchup is faster to read.</p></header>',
        f'<nav class="ks-py89-nav" aria-label="Passing Yards sections">{nav}</nav>',
        '<div class="ks-py89-overview-title">Final Projection + Market</div>',
        '<section id="py-overview" class="ks-py89-overview">', _overview_qb(captured, 0), _overview_qb(captured, 1), '</section>',
        _pair_section("py-profile", "Why This Projection • Passing Profile", captured, "profile", open_default=True),
        _pair_section("py-defense", "Opponent Pass Defense", captured, "defense"),
        _pair_section("py-pressure", "Protection vs Defensive Pressure", captured, "pressure"),
        _pair_section("py-weapons", "Weapons + Availability", captured, "personnel"),
        f'<section id="py-environment" class="ks-py89-env"><h3>Game Environment • Shared Matchup Context</h3>{env}</section>',
        _pair_section("py-projection", "Context Projection + Uncertainty", captured, "context", open_default=True),
        _pair_section("py-probability", "Distribution + Probability", captured, "distribution"),
        _pair_section("py-market", "Market Evaluation", captured, "market"),
        '</section>',
    ])


def render_nfl_passing_yards_hub() -> None:
    st = importlib.import_module("streamlit")
    certified = importlib.import_module(CERTIFIED_CAPTURE_OWNER)
    legacy_visual = importlib.import_module("nfl_passing_yards_hub_v16")
    composition = importlib.import_module("nfl_passing_yards_hub_v34")
    pre_compact = importlib.import_module("nfl_passing_yards_hub_v35")
    compact = importlib.import_module("nfl_passing_yards_hub_v36")
    prior = importlib.import_module("nfl_passing_yards_hub_v42")

    original_cards = composition._combined_player_cards_html
    original_banner = composition._visual_build_banner_v34
    original_markdown = st.markdown
    original_caption = st.caption
    original_matchup_html = legacy_visual._matchup_html
    original_why_html = legacy_visual._why_html
    original_compact_render = compact.render_nfl_passing_yards_hub

    def filtered_caption(body: Any, *args: Any, **kwargs: Any):
        text = str(body if body is not None else "")
        if "10/10 COMPLETE" in text or "10 / 10 COMPLETE" in text:
            return None
        return original_caption(body, *args, **kwargs)

    def capture_only_markdown(body: Any, *args: Any, **kwargs: Any):
        for style in certified._style_blocks_only(body):
            original_markdown(style, unsafe_allow_html=True)
        return None

    legacy_visual._matchup_html = lambda *args, **kwargs: ""
    legacy_visual._why_html = lambda *args, **kwargs: ""
    composition._combined_player_cards_html = _comparison_dashboard_html
    composition._visual_build_banner_v34 = lambda: ""
    compact.render_nfl_passing_yards_hub = pre_compact.render_nfl_passing_yards_hub
    st.markdown = capture_only_markdown
    st.caption = filtered_caption
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.markdown = original_markdown
        st.caption = original_caption
        legacy_visual._matchup_html = original_matchup_html
        legacy_visual._why_html = original_why_html
        compact.render_nfl_passing_yards_hub = original_compact_render
        composition._combined_player_cards_html = original_cards
        composition._visual_build_banner_v34 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V89 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = ["CERTIFIED_CAPTURE_OWNER","DISPLAY_ONLY","MODEL_VERSION","PRESENTATION_ONLY","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED","_comparison_dashboard_html","render_nfl_hub","render_nfl_passing_yards_hub"]
