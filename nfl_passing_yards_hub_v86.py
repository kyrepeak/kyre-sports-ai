"""NFL Passing Yards V86 — Page 2 compact UX repair.

Presentation-only wrapper over frozen V85. V86 keeps the certified selected-QB
analysis payload intact while improving the default reading path: it adds a
compact Quick Read, adds a visual frozen-distribution range strip, hides the
redundant V69 clean-detail copies from the default flow, tightens spacing, and
places the already-deduplicated Deep Evidence block behind an advanced-evidence
expander.

No football value, projection, context, probability, market math, sportsbook,
provider, widget, navigation, cache, or transport behavior changes.
"""
from __future__ import annotations

from html import escape, unescape
import importlib
import re
from threading import RLock
from typing import Any, Callable

MODEL_VERSION = "NFL PASSING YARDS V86 • PAGE 2 COMPACT UX REPAIR"
FROZEN_PRIOR = "nfl_passing_yards_hub_v85"
PAGE2_COMPACT_UX_VERSION = "v86"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_PAGE2_RLOCK = RLock()

_COMPACT_CSS = r"""
<style data-passing-yards-page2-compact-ux-css="v86">
[data-passing-yards-page2-compact-ux="v86"],
[data-passing-yards-page2-compact-ux="v86"] *{box-sizing:border-box}

[data-passing-yards-page2-compact-ux="v86"]{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
}

/* V69 clean-detail panels duplicate richer certified sections already visible. */
[data-passing-yards-page2-compact-ux="v86"] .ks-py69-clean-detail{
  display:none!important;
}

/* Compact the selected-QB hero without changing its content. */
[data-passing-yards-page2-compact-ux="v86"] .ks-py59-player{
  padding:10px!important;
  margin-bottom:8px!important;
}
[data-passing-yards-page2-compact-ux="v86"] .ks-py59-player img{
  max-height:300px!important;
  object-fit:contain!important;
}

/* Keep the existing guide, but make it lighter and faster to scan. */
[data-passing-yards-page2-compact-ux="v86"] .ks-py76-guide{
  margin:6px 0 8px!important;
  padding:6px!important;
  border-radius:10px!important;
}
[data-passing-yards-page2-compact-ux="v86"] .ks-py76-link{
  min-height:36px!important;
  padding:6px 10px!important;
}

/* Reduce giant vertical gaps while preserving every certified section. */
[data-passing-yards-page2-compact-ux="v86"] .ks-py71-explain,
[data-passing-yards-page2-compact-ux="v86"] .ks-py72-matchup,
[data-passing-yards-page2-compact-ux="v86"] .ks-py73-market,
[data-passing-yards-page2-compact-ux="v86"] .ks-py74,
[data-passing-yards-page2-compact-ux="v86"] .ks-py75,
[data-passing-yards-page2-compact-ux="v86"] .ks-py59-section{
  margin:8px 0!important;
  padding:10px!important;
  border-radius:12px!important;
}

[data-passing-yards-page2-compact-ux="v86"] .ks-py71-hero,
[data-passing-yards-page2-compact-ux="v86"] .ks-py72-grid,
[data-passing-yards-page2-compact-ux="v86"] .ks-py73-grid,
[data-passing-yards-page2-compact-ux="v86"] .ks-py74-grid{
  gap:7px!important;
}

.ks-py86-quick,
.ks-py86-range-card{
  width:100%;min-width:0;
  margin:8px 0;
  padding:11px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:14px;
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  overflow:hidden;
}
.ks-py86-head{
  display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:9px;
}
.ks-py86-kicker{
  color:var(--kyre-sem-text-accent-soft);font-size:.53rem;font-weight:950;
  letter-spacing:.1em;text-transform:uppercase;
}
.ks-py86-title{
  margin-top:2px;color:var(--kyre-sem-text-primary);font-size:1rem;font-weight:950;line-height:1.18;
}
.ks-py86-badge{
  flex:0 0 auto;padding:5px 8px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:999px;font-size:.5rem;font-weight:950;color:var(--kyre-sem-text-accent-soft);
}
.ks-py86-metrics{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;
}
.ks-py86-metric{
  min-width:0;padding:9px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:10px;background:rgba(255,255,255,.018);
}
.ks-py86-metric b{
  display:block;color:var(--kyre-sem-text-primary);font-size:.88rem;line-height:1.1;overflow-wrap:anywhere;
}
.ks-py86-metric span{
  display:block;margin-top:4px;color:var(--kyre-sem-text-muted);font-size:.46rem;
  font-weight:900;letter-spacing:.05em;text-transform:uppercase;
}
.ks-py86-copy{
  margin-top:9px;color:var(--kyre-sem-text-secondary);font-size:.65rem;line-height:1.45;
}

.ks-py86-range{
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;align-items:center;
  position:relative;margin-top:4px;
}
.ks-py86-range:before{
  content:"";position:absolute;left:7%;right:7%;top:19px;height:2px;
  background:var(--kyre-sem-border-medium);z-index:0;
}
.ks-py86-range-node{
  position:relative;z-index:1;text-align:center;min-width:0;
}
.ks-py86-range-dot{
  width:12px;height:12px;margin:0 auto 6px;border-radius:50%;
  border:2px solid var(--kyre-sem-text-accent-soft);background:var(--kyre-sem-surface-panel);
}
.ks-py86-range-node.ks-py86-median .ks-py86-range-dot{
  width:16px;height:16px;margin-bottom:4px;background:var(--kyre-sem-text-accent-soft);
}
.ks-py86-range-node b{display:block;font-size:.75rem;color:var(--kyre-sem-text-primary)}
.ks-py86-range-node span{display:block;margin-top:2px;font-size:.44rem;font-weight:900;color:var(--kyre-sem-text-muted)}
.ks-py86-range-foot{margin-top:9px;font-size:.58rem;line-height:1.4;color:var(--kyre-sem-text-muted)}

.ks-py86-advanced{
  margin:8px 0;border:1px solid var(--kyre-sem-border-soft);border-radius:12px;
  background:rgba(255,255,255,.01);overflow:hidden;
}
.ks-py86-advanced>summary{
  min-height:44px;display:flex;align-items:center;padding:9px 11px;cursor:pointer;
  color:var(--kyre-sem-text-accent-soft);font-size:.63rem;font-weight:950;
}
.ks-py86-advanced>.ks-py67-deep{margin:0!important;border:0!important;border-radius:0!important}

@media(max-width:900px){
  .ks-py86-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:620px){
  .ks-py86-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  [data-passing-yards-page2-compact-ux="v86"] .ks-py59-player img{max-height:230px!important}
  .ks-py86-range-node b{font-size:.66rem}
}
@media(max-width:460px){
  .ks-py86-head{flex-direction:column;align-items:flex-start}
  .ks-py86-metrics{grid-template-columns:1fr 1fr}
  .ks-py86-copy{font-size:.62rem}
}
</style>
"""


def _plain(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""), flags=re.S)
    return " ".join(unescape(text).split()).strip()


def _section_slice(text: str, kind: str) -> str:
    marker = f'data-passing-yards-clean-detail="{kind}"'
    pos = text.find(marker)
    if pos < 0:
        return ""
    start = text.rfind("<section", 0, pos)
    end = text.find("</section>", pos)
    if start < 0 or end < 0:
        return ""
    return text[start : end + len("</section>")]


def _clean_field(panel: str, key: str, fallback: str = "—") -> str:
    pattern = re.compile(
        rf'data-clean-field="{re.escape(key)}"[^>]*>\s*<b>(.*?)</b>',
        flags=re.I | re.S,
    )
    match = pattern.search(str(panel or ""))
    value = _plain(match.group(1)) if match else ""
    return value if value and len(value) <= 120 else fallback


def _metric(label: str, value: str) -> str:
    return (
        '<div class="ks-py86-metric">'
        f'<b>{escape(str(value or "—"))}</b><span>{escape(label)}</span></div>'
    )


def _quick_read(text: str) -> str:
    market = _section_slice(text, "market")
    projection = _section_slice(text, "projection")
    lean = _clean_field(market, "lean")
    line = _clean_field(market, "line")
    confidence = _clean_field(market, "confidence")
    probability = _clean_field(market, "model-probability")
    edge = _clean_field(market, "edge")
    projected = _clean_field(projection, "baseline-yards")

    if lean.upper() == "PASS":
        copy = (
            "The certified final read is PASS: the existing model does not clear "
            "the conservative Step 10 value threshold. No model or market value is "
            "changed by this summary."
        )
    else:
        copy = (
            f"Certified final lean: {lean}. This is a compact display of the existing "
            "Step 10 result; no projection, probability, edge, EV, or market value is recalculated."
        )

    return (
        '<section class="ks-py86-quick" data-passing-yards-page2-quick-read="v86">'
        '<div class="ks-py86-head"><div><div class="ks-py86-kicker">⚡ Start here</div>'
        '<div class="ks-py86-title">Quick Read</div></div>'
        f'<div class="ks-py86-badge">{escape(lean)}</div></div>'
        '<div class="ks-py86-metrics">'
        + _metric("Projection", projected)
        + _metric("Market Line", line)
        + _metric("Model O/U", probability)
        + _metric("Model Edge", edge)
        + _metric("Confidence", confidence)
        + '</div>'
        f'<div class="ks-py86-copy">{escape(copy)}</div></section>'
    )


def _range_card(text: str) -> str:
    distribution = _section_slice(text, "distribution")
    values = (
        ("P10", _clean_field(distribution, "p10"), False),
        ("P25", _clean_field(distribution, "p25"), False),
        ("MEDIAN", _clean_field(distribution, "p50"), True),
        ("P75", _clean_field(distribution, "p75"), False),
        ("P90", _clean_field(distribution, "p90"), False),
    )
    nodes = "".join(
        '<div class="ks-py86-range-node%s"><div class="ks-py86-range-dot"></div><b>%s</b><span>%s</span></div>'
        % (" ks-py86-median" if median else "", escape(value), escape(label))
        for label, value, median in values
    )
    return (
        '<section class="ks-py86-range-card" data-passing-yards-page2-range="v86">'
        '<div class="ks-py86-head"><div><div class="ks-py86-kicker">🎯 Frozen outcome distribution</div>'
        '<div class="ks-py86-title">Expected Range</div></div>'
        '<div class="ks-py86-badge">P10 → P90</div></div>'
        f'<div class="ks-py86-range">{nodes}</div>'
        '<div class="ks-py86-range-foot">These are the existing certified distribution quantiles. '
        'V86 changes presentation only and does not recalculate the distribution.</div></section>'
    )


def _wrap_advanced_evidence(text: str) -> str:
    marker = '<section class="ks-py67-deep"'
    start = text.find(marker)
    if start < 0 or "ks-py86-advanced" in text:
        return text
    end = text.find("</section>", start)
    if end < 0:
        return text
    end += len("</section>")
    section = text[start:end]
    wrapped = (
        '<details class="ks-py86-advanced" data-passing-yards-page2-advanced-evidence="v86">'
        '<summary>🔎 Show Advanced Evidence</summary>' + section + '</details>'
    )
    return text[:start] + wrapped + text[end:]


def _compact_selected_analysis(body: str) -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-detail-cleanup="v69"' not in text
        or 'data-passing-yards-page2-compact-ux="v86"' in text
    ):
        return text

    root = '<section class="ks-py59" data-passing-yards-qb-detail="v59"'
    if root not in text:
        return text
    text = text.replace(
        root,
        root + ' data-passing-yards-page2-compact-ux="v86"',
        1,
    )

    player_start = text.find('<article class="ks-py59-player"')
    if player_start >= 0:
        player_end = text.find("</article>", player_start)
        if player_end >= 0:
            player_end += len("</article>")
            summary = _quick_read(text) + _range_card(text)
            text = text[:player_end] + summary + text[player_end:]

    text = _wrap_advanced_evidence(text)
    return _COMPACT_CSS + text


def _make_markdown_bridge(delegate: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(delegate, "_passing_yards_page2_compact_v86", False):
        return delegate

    def _bridge(body: Any, *args: Any, **kwargs: Any):
        value = body
        if isinstance(body, str) and 'data-passing-yards-qb-detail="v59"' in body:
            value = _compact_selected_analysis(body)
        return delegate(value, *args, **kwargs)

    _bridge._passing_yards_page2_compact_v86 = True  # type: ignore[attr-defined]
    _bridge._passing_yards_page2_compact_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def render_nfl_passing_yards_hub() -> None:
    st = importlib.import_module("streamlit")
    prior = importlib.import_module(FROZEN_PRIOR)
    with _PAGE2_RLOCK:
        original_markdown = st.markdown
        st.markdown = _make_markdown_bridge(original_markdown)
        try:
            original_markdown(
                '<span data-passing-yards-page2-compact-owner="v86" '
                'style="display:none" aria-hidden="true"></span>',
                unsafe_allow_html=True,
            )
            return prior.render_nfl_passing_yards_hub()
        finally:
            st.markdown = original_markdown


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V86 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PAGE2_COMPACT_UX_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_compact_selected_analysis",
    "_make_markdown_bridge",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
