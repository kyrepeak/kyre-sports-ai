"""NFL Passing Yards V79 — selected-QB lazy detail gate.

Speed Phase Step 3. The selected quarterback page becomes usable without waiting
for the frozen full analysis pipeline. The lightweight V78 preview is the initial
page. Heavy Why/Matchup/Market/Game Day/Reliability detail is loaded only when
the user explicitly opens full analysis via ks_py_full=1.

No model, provider, projection, probability, market, sportsbook, widget-key, or
navigation calculation is changed. V78/V77 remain the full-analysis authority.
"""
from __future__ import annotations

from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import streamlit as st

import nfl_passing_yards_hub_v58 as selection
import nfl_passing_yards_hub_v78 as prior
from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V79 • SPEED STEP 3 LAZY DETAIL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v78"
SPEED_PHASE_STEP = 3
LAZY_DETAIL_VERSION = "v79"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PERSONNEL_MATH = False
MAY_MODIFY_ENVIRONMENT_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_FULL_PARAM = "ks_py_full"

_LAZY_CSS = r"""
<style data-passing-yards-lazy-detail-css="v79">
.ks-py79,.ks-py79 *{box-sizing:border-box}
.ks-py79{width:100%;max-width:1120px;margin:.45rem auto 1rem;color:var(--kyre-sem-text-primary)}
.ks-py79-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.ks-py79-back,.ks-py79-load{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 14px;border-radius:12px;text-decoration:none!important;font-size:.68rem;font-weight:950}
.ks-py79-back{border:1px solid var(--kyre-sem-border-medium);background:rgba(255,255,255,.018);color:var(--kyre-sem-text-accent-soft)!important}
.ks-py79-load{border:1px solid var(--kyre-sem-border-strong);background:var(--kyre-sem-accent-wash-soft);color:var(--kyre-sem-text-primary)!important}
.ks-py79-head{margin:0 0 10px;padding:14px;border:1px solid var(--kyre-sem-border-medium);border-radius:var(--kyre-sem-radius-card);background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))}
.ks-py79-kicker{color:var(--kyre-sem-text-accent-soft);font-size:.58rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase}
.ks-py79-title{margin:4px 0 0;font-size:1.25rem;font-weight:950;line-height:1.12}
.ks-py79-sub{margin:5px 0 0;color:var(--kyre-sem-text-muted);font-size:.7rem;line-height:1.5}
.ks-py79-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:10px}
.ks-py79-card{min-width:0;padding:10px;border:1px solid var(--kyre-sem-border-soft);border-radius:11px;background:rgba(255,255,255,.015)}
.ks-py79-card b{display:block;color:var(--kyre-sem-text-primary);font-size:.67rem;line-height:1.2}
.ks-py79-card span{display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.54rem;line-height:1.35}
.ks-py79-note{margin-top:10px;padding:10px;border:1px solid var(--kyre-sem-border-soft);border-radius:11px;color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.5}
.ks-py79-note strong{color:var(--kyre-sem-text-accent-soft)}
@media(max-width:760px){.ks-py79-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ks-py79-card:first-child{grid-column:1/-1}}
@media(max-width:430px){.ks-py79-toolbar{align-items:stretch}.ks-py79-back,.ks-py79-load{width:100%}.ks-py79-grid{grid-template-columns:1fr}.ks-py79-card:first-child{grid-column:auto}}
</style>
"""


def _full_requested() -> bool:
    return selection._param(_FULL_PARAM) == "1"


def _with_full(url: str, enabled: bool) -> str:
    split = urlsplit(str(url or ""))
    pairs = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k != _FULL_PARAM]
    if enabled:
        pairs.append((_FULL_PARAM, "1"))
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(pairs), split.fragment))


def _full_url(slot: int, hints: dict[str, str]) -> str:
    base = selection._current_nav_url(slot)
    hinted = prior._url_with_hints(base, hints)
    return _with_full(hinted, True)


def build_lazy_detail_shell(slot: int, hints: dict[str, str]) -> str:
    back = escape(selection._current_nav_url(None), quote=True)
    full = escape(_full_url(slot, hints), quote=True)
    fast = prior.build_fast_first_paint(slot, hints)
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _LAZY_CSS
        + '<section class="ks-py79" data-passing-yards-lazy-detail="v79" '
          f'data-lazy-detail-slot="{int(slot)}">'
        + '<div class="ks-py79-toolbar">'
        + f'<a class="ks-py79-back" href="{back}">← Back to Quarterbacks</a>'
        + f'<a class="ks-py79-load" data-passing-yards-load-full="v79" href="{full}">Load Full Analysis →</a>'
        + '</div>'
        + fast
        + '<section class="ks-py79-head">'
        + '<div class="ks-py79-kicker">Heavy analysis deferred</div>'
        + '<div class="ks-py79-title">Choose when to load the deep breakdown</div>'
        + '<div class="ks-py79-sub">The fast preview is usable now. The expensive detail pipeline is not running until you open the full analysis.</div>'
        + '<div class="ks-py79-grid">'
        + '<div class="ks-py79-card"><b>Why</b><span>Projection drivers and evidence.</span></div>'
        + '<div class="ks-py79-card"><b>Matchup</b><span>Opponent and pressure detail.</span></div>'
        + '<div class="ks-py79-card"><b>Market</b><span>Verified live line context.</span></div>'
        + '<div class="ks-py79-card"><b>Game Day</b><span>Availability and environment.</span></div>'
        + '<div class="ks-py79-card"><b>Reliability</b><span>Failure-proofing and source status.</span></div>'
        + '</div>'
        + '<div class="ks-py79-note"><strong>Speed mode:</strong> none of these deferred sections can influence the model by being hidden or shown. Full analysis uses the unchanged frozen pipeline.</div>'
        + '</section></section>'
    )


def render_nfl_passing_yards_hub() -> None:
    selection._restore_context_from_query()
    raw_slot = selection._param("ks_qb_slot")
    slot = int(raw_slot) if raw_slot in {"1", "2"} else None
    if slot is not None and not _full_requested():
        st.markdown(build_lazy_detail_shell(slot, prior._query_hints(slot)), unsafe_allow_html=True)
        return None
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V79 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY","FROZEN_PRIOR","LAZY_DETAIL_VERSION","MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR","MAY_MODIFY_ENVIRONMENT_MATH","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE","MAY_MODIFY_PERSONNEL_MATH","MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION","PRESENTATION_ONLY",
    "SPEED_PHASE_STEP","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED",
    "_full_requested","_full_url","_with_full","build_lazy_detail_shell","render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
