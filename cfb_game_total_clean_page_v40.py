"""CFB Game Total clean page V40 — native Page-1 website shell Step 3.

Additive successor to frozen native-routing V39. This layer adds only the
Game Total Page-1 presentation shell that sits inside the existing KYRE SPORTS
AI site chrome. It deliberately does not own date selection, game loading,
matchup-card interaction, or selected-event Page 2 behavior; those remain in
their existing owners for later rebuild steps.

No model, projection, probability, market-ownership, sportsbook-influence,
network-provider, event-identity, schedule, or Page-2 behavior is changed.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v39 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V40 • NATIVE PAGE1 SHELL STEP 3"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v39"
ACTIVE_MARKER = "CFB GAME TOTAL • NATIVE PAGE1 SHELL STEP 3 ACTIVE"
PAGE1_SHELL_MARKER = "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
NETWORK_CALLS_ADDED = 0

PAGE1_SHELL_CSS = r"""
<style>
.gt240-shell{position:relative;overflow:hidden;margin:2px auto 18px;padding:24px 26px 22px;border:1px solid rgba(87,197,255,.33);border-radius:24px;background:radial-gradient(circle at 84% -12%,rgba(32,174,255,.20),transparent 38%),radial-gradient(circle at 10% 118%,rgba(26,225,210,.10),transparent 42%),linear-gradient(145deg,#071827 0%,#06121e 52%,#050c14 100%);box-shadow:0 20px 50px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.025);color:#f7fbff}
.gt240-shell:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,transparent 0 49.8%,rgba(89,195,240,.06) 50%,transparent 50.2%);opacity:.65}
.gt240-top{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:19px}.gt240-brand,.gt240-route{display:inline-flex;align-items:center;gap:8px;min-height:29px;padding:0 11px;border:1px solid rgba(88,194,238,.24);border-radius:999px;background:rgba(5,24,37,.72);font-size:9px;font-weight:950;letter-spacing:.105em;text-transform:uppercase}.gt240-brand{color:#74dbff}.gt240-route{color:#8ea8ba}.gt240-dot{width:6px;height:6px;border-radius:50%;background:#45f0ad;box-shadow:0 0 12px rgba(69,240,173,.65)}
.gt240-copy{position:relative;z-index:1;max-width:790px}.gt240-eyebrow{margin-bottom:7px;color:#6edcff;font-size:11px;font-weight:1000;letter-spacing:.18em;text-transform:uppercase}.gt240-copy h1{margin:0;color:#fff;font-size:clamp(34px,5vw,60px);line-height:.98;font-weight:1000;letter-spacing:-.045em}.gt240-copy h1 span{color:#62d8ff}.gt240-copy p{max-width:680px;margin:12px 0 0;color:#91a9ba;font-size:13px;line-height:1.58;font-weight:650}
.gt240-grid{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:22px}.gt240-tile{min-width:0;padding:12px 13px;border:1px solid rgba(78,166,207,.20);border-radius:14px;background:linear-gradient(180deg,rgba(9,34,51,.86),rgba(6,23,35,.86))}.gt240-tile small{display:block;color:#638198;font-size:8px;font-weight:1000;letter-spacing:.12em;text-transform:uppercase}.gt240-tile b{display:block;margin-top:5px;color:#edf8ff;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt240-tile em{display:block;margin-top:4px;color:#6f8b9f;font-size:8px;font-style:normal;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gt240-tile.market b{color:#45f0ad}
@media(max-width:760px){.gt240-shell{padding:18px 16px 16px;border-radius:19px}.gt240-top{margin-bottom:15px}.gt240-route{display:none}.gt240-copy h1{font-size:36px}.gt240-copy p{font-size:11px}.gt240-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:17px}.gt240-tile{padding:10px 11px}.gt240-tile b{font-size:10px}}
@media(max-width:390px){.gt240-copy h1{font-size:31px}.gt240-grid{grid-template-columns:1fr 1fr}.gt240-brand{font-size:8px}}
</style>
"""


def _page1_shell_html() -> str:
    return f"""
<section class="gt240-shell" data-testid="gt240-native-page1-shell"
         data-step3-marker="{PAGE1_SHELL_MARKER}">
  <div class="gt240-top">
    <div class="gt240-brand"><span class="gt240-dot"></span>KYRE SPORTS AI</div>
    <div class="gt240-route">CFB&nbsp;&nbsp;/&nbsp;&nbsp;GAME TOTAL</div>
  </div>
  <div class="gt240-copy">
    <div class="gt240-eyebrow">College Football</div>
    <h1>Game <span>Total</span></h1>
    <p>One clean home for the slate, matchup context, model intelligence, and market context — inside the native CFB website experience.</p>
  </div>
  <div class="gt240-grid" aria-label="Game Total page capabilities">
    <div class="gt240-tile"><small>Model</small><b>Projection Engine</b><em>Frozen certified math</em></div>
    <div class="gt240-tile"><small>Matchup</small><b>Team Context</b><em>Identity-safe evidence</em></div>
    <div class="gt240-tile market"><small>Market</small><b>Context Only</b><em>0% projection weight</em></div>
    <div class="gt240-tile"><small>Coverage</small><b>Full CFB Slate</b><em>Existing schedule owners</em></div>
  </div>
</section>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(PAGE1_SHELL_CSS, unsafe_allow_html=True)
    st.markdown(_page1_shell_html(), unsafe_allow_html=True)
    return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V40 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE1_SHELL_CSS",
    "PAGE1_SHELL_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_page1_shell_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
