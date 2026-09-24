"""NFL Passing Yards V78 — selected-QB fast first paint.

Speed Phase Step 2. This wrapper does not change any certified model, data,
probability, market, personnel, environment, sportsbook, widget, or navigation
calculation. It decouples *initial visual usability* from the expensive frozen
V77 full-detail render:

1) the QB selection screen appends bounded display-only preview hints to the
   selected-QB URL;
2) the selected-QB route immediately renders a tiny first-paint card from those
   hints (or a generic loading shell on a cold/direct link);
3) the unchanged V77 pipeline continues underneath;
4) the temporary first-paint card is removed only after the full certified page
   finishes successfully.

The URL hints are never consumed by model/data code. They are display-only and
the final frozen analysis remains authoritative.
"""
from __future__ import annotations

from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import streamlit as st

import nfl_passing_yards_hub_v58 as selection
import nfl_passing_yards_hub_v69 as detail_helpers
import nfl_passing_yards_hub_v77 as prior

MODEL_VERSION = "NFL PASSING YARDS V78 • SPEED STEP 2 FAST FIRST PAINT"
FROZEN_PRIOR = "nfl_passing_yards_hub_v77"
SPEED_PHASE_STEP = 2
FIRST_PAINT_VERSION = "v78"
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

_HINT_PREFIX = "ks_py_hint_"
_HINT_NAMES = (
    "name",
    "meta",
    "projection",
    "attempts",
    "ypa",
    "line",
    "lean",
)
_ORIGINAL_SELECTION_SCREEN = selection._selection_screen

_FAST_CSS = r"""
<style data-passing-yards-speed-first-paint-css="v78">
.ks-py78-fast,.ks-py78-fast *{box-sizing:border-box}
.ks-py78-fast{
  width:100%;max-width:1120px;margin:.35rem auto .75rem;padding:14px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-card);
  background:
    radial-gradient(circle at 100% 0%,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card)
}
.ks-py78-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.ks-py78-kicker{
  color:var(--kyre-sem-text-accent-soft);font-size:.58rem;font-weight:950;
  letter-spacing:.1em;text-transform:uppercase
}
.ks-py78-name{
  margin-top:4px;color:var(--kyre-sem-text-primary);font-size:1.25rem;
  font-weight:950;line-height:1.12
}
.ks-py78-meta{margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.7rem;line-height:1.4}
.ks-py78-state{
  flex:0 0 auto;padding:6px 9px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:999px;background:var(--kyre-sem-accent-wash-soft);
  color:var(--kyre-sem-text-accent-soft);font-size:.56rem;font-weight:950
}
.ks-py78-grid{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px
}
.ks-py78-metric{
  min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:10px;background:rgba(255,255,255,.018)
}
.ks-py78-metric b{
  display:block;color:var(--kyre-sem-text-primary);font-size:.88rem;
  font-weight:950;line-height:1.15;overflow-wrap:anywhere
}
.ks-py78-metric span{
  display:block;margin-top:4px;color:var(--kyre-sem-text-muted);
  font-size:.5rem;font-weight:900;line-height:1.25;text-transform:uppercase
}
.ks-py78-note{
  margin-top:10px;padding-top:9px;border-top:1px solid var(--kyre-sem-border-soft);
  color:var(--kyre-sem-text-muted);font-size:.64rem;line-height:1.45
}
.ks-py78-note strong{color:var(--kyre-sem-text-accent-soft)}
@media(max-width:760px){.ks-py78-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:430px){
  .ks-py78-fast{padding:11px}
  .ks-py78-top{flex-direction:column}
  .ks-py78-state{align-self:flex-start}
  .ks-py78-grid{grid-template-columns:1fr 1fr}
  .ks-py78-metric:first-child{grid-column:1/-1}
}
</style>
"""


def _bounded(value: object, fallback: str = "Loading…", limit: int = 96) -> str:
    text = str(value if value is not None else "").strip()
    if not text or text == "—":
        return fallback
    text = " ".join(text.split())
    return text[:limit]


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _summary_from_captured(captured: dict[str, list[str]], index: int) -> dict[str, str]:
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    market = _piece(captured, "market", index)
    return {
        "name": _bounded(
            detail_helpers._extract_div_text(identity, "kpass29-name", f"Quarterback {index + 1}"),
            f"Quarterback {index + 1}",
        ),
        "meta": _bounded(
            detail_helpers._extract_div_text(identity, "kpass29-meta", "Verified quarterback"),
            "Verified quarterback",
        ),
        "projection": _bounded(detail_helpers._extract_b_span(projection, "Baseline Pass Yards")),
        "attempts": _bounded(detail_helpers._extract_b_span(projection, "Expected Attempts")),
        "ypa": _bounded(detail_helpers._extract_b_span(projection, "Expected YPA")),
        "line": _bounded(detail_helpers._extract_b_span(market, "Market Line")),
        "lean": _bounded(detail_helpers._extract_b_span(market, "Final Lean")),
    }


def _url_with_hints(url: str, summary: dict[str, str]) -> str:
    split = urlsplit(str(url or ""))
    pairs = parse_qsl(split.query, keep_blank_values=True)
    keep = [(key, value) for key, value in pairs if not key.startswith(_HINT_PREFIX)]
    for name in _HINT_NAMES:
        value = _bounded(summary.get(name), fallback="", limit=96)
        if value:
            keep.append((_HINT_PREFIX + name, value))
    query = urlencode(keep)
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))


def _selection_screen_with_hints(captured: dict[str, list[str]]) -> str:
    body = _ORIGINAL_SELECTION_SCREEN(captured)
    for slot in (1, 2):
        summary = _summary_from_captured(captured, slot - 1)
        old_url = selection._current_nav_url(slot)
        new_url = _url_with_hints(old_url, summary)
        old_href = 'href="' + escape(old_url, quote=True) + '"'
        new_href = 'href="' + escape(new_url, quote=True) + '"'
        body = body.replace(old_href, new_href, 1)
    return body


def _query_hints(slot: int) -> dict[str, str]:
    values: dict[str, str] = {}
    for name in _HINT_NAMES:
        values[name] = _bounded(
            selection._param(_HINT_PREFIX + name),
            fallback="",
            limit=96,
        )
    if not values.get("name"):
        values["name"] = f"Quarterback {slot}"
    if not values.get("meta"):
        values["meta"] = "Verified Passing Yards analysis"
    return values


def build_fast_first_paint(slot: int, hints: dict[str, str]) -> str:
    name = _bounded(hints.get("name"), f"Quarterback {slot}")
    meta = _bounded(hints.get("meta"), "Verified Passing Yards analysis")
    projection = _bounded(hints.get("projection"))
    attempts = _bounded(hints.get("attempts"))
    ypa = _bounded(hints.get("ypa"))
    line = _bounded(hints.get("line"))
    lean = _bounded(hints.get("lean"))
    return (
        _FAST_CSS
        + f'<section class="ks-py78-fast" data-passing-yards-speed-first-paint="v78" '
          f'data-fast-first-paint-slot="{int(slot)}">'
        + '<div class="ks-py78-top"><div>'
        + '<div class="ks-py78-kicker">Selected quarterback • instant preview</div>'
        + f'<div class="ks-py78-name">{escape(name)}</div>'
        + f'<div class="ks-py78-meta">{escape(meta)}</div>'
        + '</div><div class="ks-py78-state">ANALYSIS LOADING</div></div>'
        + '<div class="ks-py78-grid">'
        + f'<div class="ks-py78-metric"><b>{escape(projection)}</b><span>Baseline Pass Yards</span></div>'
        + f'<div class="ks-py78-metric"><b>{escape(attempts)}</b><span>Expected Attempts</span></div>'
        + f'<div class="ks-py78-metric"><b>{escape(ypa)}</b><span>Expected YPA</span></div>'
        + f'<div class="ks-py78-metric"><b>{escape(line)}</b><span>Market Line</span></div>'
        + f'<div class="ks-py78-metric"><b>{escape(lean)}</b><span>Current Lean</span></div>'
        + '</div>'
        + '<div class="ks-py78-note"><strong>Fast first paint:</strong> this lightweight preview appears before '
          'the full certified analysis finishes. Preview hints never feed the model; the full frozen analysis below '
          'remains authoritative.</div></section>'
    )


def render_nfl_passing_yards_hub() -> None:
    raw_slot = selection._param("ks_qb_slot")
    slot = int(raw_slot) if raw_slot in {"1", "2"} else None
    placeholder = None
    if slot is not None:
        placeholder = st.empty()
        placeholder.markdown(
            build_fast_first_paint(slot, _query_hints(slot)),
            unsafe_allow_html=True,
        )

    original_selection = selection._selection_screen
    selection._selection_screen = _selection_screen_with_hints
    succeeded = False
    try:
        result = prior.render_nfl_passing_yards_hub()
        succeeded = True
        return result
    finally:
        selection._selection_screen = original_selection
        if succeeded and placeholder is not None:
            placeholder.empty()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V78 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FIRST_PAINT_VERSION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_ENVIRONMENT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PERSONNEL_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPEED_PHASE_STEP",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_query_hints",
    "_selection_screen_with_hints",
    "_summary_from_captured",
    "_url_with_hints",
    "build_fast_first_paint",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
