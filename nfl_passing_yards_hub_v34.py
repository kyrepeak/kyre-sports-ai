"""NFL Passing Yards V34 — combined player-first 10-step cards.

Additive presentation/composition wrapper over certified V33. The certified
Passing Yards stack already renders every Step 1-10 value correctly; V34 changes
only where those rendered cards live. Instead of presenting two quarterbacks in
separate horizontal grids at each step, V34 captures the already-rendered card
HTML and composes one complete analysis stack per quarterback, matching the
player-first pattern used by certified Receiving Yards and Rushing Yards.

No projection, context, distribution, probability, fair-odds, no-vig, edge, EV,
grade, market, identity, transport, or settlement calculation is recomputed.
V33 and V28 analytical behavior remain frozen. Sportsbook projection influence
remains exactly 0.0% and stake sizing remains OFF.
"""
from __future__ import annotations

import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v5 as pressure_ui
import nfl_passing_yards_hub_v7 as environment_ui
import nfl_passing_yards_hub_v8 as projection_ui
import nfl_passing_yards_hub_v9 as context_ui
import nfl_passing_yards_hub_v10 as distribution_ui
import nfl_passing_yards_hub_v11 as market_ui
import nfl_passing_yards_hub_v17 as provenance_ui
import nfl_passing_yards_hub_v21 as market_visual_ui
import nfl_passing_yards_hub_v28 as personnel_visual_ui
import nfl_passing_yards_hub_v29 as identity_visual_ui
import nfl_passing_yards_hub_v30 as profile_visual_ui
import nfl_passing_yards_hub_v33 as prior

MODEL_VERSION = "NFL PASSING YARDS V34 • COMBINED PLAYER-FIRST 10-STEP CARDS"
FROZEN_PRIOR = "nfl_passing_yards_hub_v33"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
DISPLAY_ONLY = True
PLAYER_CARD_COMPOSITION_ONLY = True
PLAYER_CARD_STEP_COUNT = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ORIGINAL_FINAL_BANNER_V33 = prior._visual_build_banner_v33

_PLAYER_CARD_CSS = r'''
<style>
.kpass34-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;align-items:start;margin:9px 0 13px}
.kpass34-player{position:relative;overflow:hidden;min-width:0;border:1px solid #315940;border-radius:19px;background:linear-gradient(150deg,#09150f 0%,#08110d 58%,#0b1811 100%);padding:10px;box-shadow:inset 0 0 0 1px rgba(139,226,172,.025)}
.kpass34-player:after{content:"";position:absolute;right:-78px;top:-96px;width:250px;height:250px;border:1px solid rgba(139,226,172,.035);border-radius:50%;box-shadow:0 0 0 30px rgba(139,226,172,.012);pointer-events:none}
.kpass34-cardbar{position:relative;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:7px;margin:0 1px 8px;padding:1px 2px}.kpass34-cardbar strong{color:#a6e8b8;font-size:.53rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}.kpass34-cardchips{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}.kpass34-chip{border:1px solid #3c6a4d;background:#0f2418;color:#8be2ac;border-radius:999px;padding:3px 6px;font-size:.37rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.kpass34-chip.blue{border-color:#435e76;background:#111e29;color:#a9c5df}
.kpass34-step{position:relative;z-index:1;margin-top:7px;padding-top:7px;border-top:1px solid #183024}.kpass34-stephead{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 2px 5px}.kpass34-stepname{color:#dcebe1;font-size:.46rem;font-weight:950;letter-spacing:.045em;text-transform:uppercase}.kpass34-stepnum{color:#6f8577;font-size:.36rem;font-weight:950;border:1px solid #243f31;border-radius:999px;background:#0b1911;padding:2px 5px;white-space:nowrap}.kpass34-missing{border:1px dashed #3d5146;border-radius:10px;background:#0a130f;padding:8px;color:#7f9186;font-size:.45rem;line-height:1.45}
.kpass34-player .kpass29-card,.kpass34-player .kpass30-profile,.kpass34-player .kpy-defense,.kpass34-player .kpy-pressure,.kpass34-player .kpy-personnel,.kpass34-player .kpy-env,.kpass34-player .kpy-proj,.kpass34-player .kpy8-card,.kpass34-player .kpy9-card,.kpass34-player .kpy10-card{margin:0!important;width:auto!important;box-sizing:border-box!important}
.kpass34-player .kpass29-card{border-radius:15px!important}.kpass34-player .kpass30-profile,.kpass34-player section.kpy-defense,.kpass34-player section.kpy-pressure,.kpass34-player section.kpy-personnel,.kpass34-player section.kpy-env,.kpass34-player section.kpy-proj,.kpass34-player section.kpy8-card,.kpass34-player section.kpy9-card,.kpass34-player section.kpy10-card{border-radius:13px!important}
.kpass34-player .kpy-envteams{grid-template-columns:1fr!important}.kpass34-player .kpy9-q{grid-template-columns:repeat(3,minmax(0,1fr))!important}.kpass34-player .kpy9-q>div:nth-child(4),.kpass34-player .kpy9-q>div:nth-child(5){grid-column:auto!important}
.kpass34-market-controls{border:1px solid #2a4a38;border-radius:14px;background:linear-gradient(145deg,#0b1712,#09140f);padding:10px 11px;margin:12px 0 8px}.kpass34-market-controls b{color:#a6e8b8;font-size:.72rem}.kpass34-market-controls span{display:block;color:#718579;font-size:.46rem;line-height:1.45;margin-top:3px}
@media(max-width:980px){.kpass34-grid{grid-template-columns:1fr}.kpass34-player{padding:9px}}
</style>
'''

_TAG_RE = re.compile(r"<\s*(/)?\s*([a-zA-Z0-9]+)(?:\s[^<>]*?)?\s*(/?)>")
_VOID_TAGS = {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

_GRID_MARKERS = {
    '<div class="kpy-qbgrid">': "identity",
    '<div class="kpy-pgrid">': "profile",
    '<div class="kpy-dgrid">': "defense",
    '<div class="kpy-xgrid">': "pressure",
    '<div class="kpy-igrid">': "personnel",
    '<div class="kpy-projgrid">': "projection",
    '<div class="kpy8-grid">': "context",
    '<div class="kpy9-grid">': "distribution",
    '<div class="kpy10-grid">': "market",
}

_ROOT_CARD_CLASSES = {
    "defense": ("section", "kpy-defense"),
    "pressure": ("section", "kpy-pressure"),
    "personnel": ("section", "kpy-personnel"),
    "projection": ("section", "kpy-proj"),
    "context": ("section", "kpy8-card"),
    "distribution": ("section", "kpy9-card"),
    "market": ("section", "kpy10-card"),
}

_STEP_LABELS = (
    (2, "Quarterback Passing Profile", "profile"),
    (3, "Opponent Pass Defense", "defense"),
    (4, "Protection vs Defensive Pressure", "pressure"),
    (5, "Weapons + Injuries", "personnel"),
    (6, "Game Environment", "environment"),
    (7, "Baseline Projection", "projection"),
    (8, "Context + Uncertainty", "context"),
    (9, "Distribution + Probability", "distribution"),
    (10, "Market Evaluation", "market"),
)


class _CompositionStreamlitProxy:
    """Route only presentational messages through V34; delegate real widgets."""

    def __init__(self, wrapped: Any, markdown_handler: Any, success_handler: Any, warning_handler: Any, info_handler: Any) -> None:
        self._wrapped = wrapped
        self._markdown_handler = markdown_handler
        self._success_handler = success_handler
        self._warning_handler = warning_handler
        self._info_handler = info_handler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def markdown(self, body: Any, *args: Any, **kwargs: Any):
        return self._markdown_handler(body, *args, **kwargs)

    def success(self, body: Any, *args: Any, **kwargs: Any):
        return self._success_handler(body, *args, **kwargs)

    def warning(self, body: Any, *args: Any, **kwargs: Any):
        return self._warning_handler(body, *args, **kwargs)

    def info(self, body: Any, *args: Any, **kwargs: Any):
        return self._info_handler(body, *args, **kwargs)


def _visual_build_banner_v34() -> str:
    return (
        '<section class="kpass29-build">'
        '<div class="kpass29-buildtop"><div>'
        '<div class="kpass29-buildtitle">🧩 Passing Yards • Combined Player Cards</div>'
        '<div class="kpass29-buildsub">All certified Step 1–10 Passing analysis is now grouped quarterback-first like Receiving Yards + Rushing Yards • analytical values remain frozen.</div>'
        '</div><div class="kpass29-buildchips">'
        '<span class="kpass29-buildchip final">ALL 10 STEPS • PLAYER CARDS</span>'
        '<span class="kpass29-buildchip blue">V33 + V28 FROZEN</span>'
        '<span class="kpass29-buildchip gold">SPORTSBOOK 0%</span>'
        '</div></div><div class="kpass29-track"><div class="kpass29-fill" style="width:100%"></div></div>'
        '<div class="kpass33-finalnote"><strong>Composition-only upgrade.</strong> Existing certified player, matchup, projection, uncertainty, probability, and market cards are moved under the quarterback they belong to • no analytical recomputation • stake sizing OFF.</div>'
        '</section>'
    )


def _inner_fragment(grid_html: str) -> str:
    text = str(grid_html or "").strip()
    first = text.find(">")
    last = text.rfind("</div>")
    if first < 0 or last <= first:
        return ""
    return text[first + 1:last]


def _split_top_level_children(grid_html: str) -> list[str]:
    """Split a generated two-card grid without parsing/recomputing card values."""
    inner = _inner_fragment(grid_html)
    if not inner:
        return []
    children: list[str] = []
    stack: list[str] = []
    child_start: int | None = None
    for match in _TAG_RE.finditer(inner):
        closing = bool(match.group(1))
        tag = str(match.group(2) or "").lower()
        self_closing = bool(match.group(3)) or tag in _VOID_TAGS
        if not closing:
            if not stack and child_start is None:
                child_start = match.start()
            if not self_closing:
                stack.append(tag)
            elif not stack and child_start is not None:
                children.append(inner[child_start:match.end()].strip())
                child_start = None
            continue
        if not stack:
            continue
        if stack[-1] == tag:
            stack.pop()
        else:
            while stack and stack[-1] != tag:
                stack.pop()
            if stack and stack[-1] == tag:
                stack.pop()
        if not stack and child_start is not None:
            children.append(inner[child_start:match.end()].strip())
            child_start = None
    return [child for child in children if child]


def _extract_elements_by_class(body: str, tag: str, class_name: str) -> list[str]:
    """Extract balanced certified root cards by their exact rendered class."""
    text = str(body or "")
    opener = re.compile(
        rf'<{re.escape(tag)}\b[^>]*class="{re.escape(class_name)}"[^>]*>',
        re.IGNORECASE,
    )
    cards: list[str] = []
    cursor = 0
    while True:
        start = opener.search(text, cursor)
        if start is None:
            break
        depth = 0
        end_pos: int | None = None
        for token in _TAG_RE.finditer(text, start.start()):
            closing = bool(token.group(1))
            token_tag = str(token.group(2) or "").lower()
            self_closing = bool(token.group(3)) or token_tag in _VOID_TAGS
            if token_tag != tag.lower():
                continue
            if not closing and not self_closing:
                depth += 1
            elif closing:
                depth -= 1
                if depth == 0:
                    end_pos = token.end()
                    break
        if end_pos is None:
            break
        cards.append(text[start.start():end_pos].strip())
        cursor = end_pos
    return cards


def _capture_grid(captured: dict[str, list[str]], key: str, body: str) -> None:
    # Direct final-factory capture is authoritative. Grid parsing is fallback only.
    if captured.get(key):
        return
    if key == "identity":
        children = _split_top_level_children(body)
    else:
        root = _ROOT_CARD_CLASSES.get(key)
        children = _extract_elements_by_class(body, *root) if root else []
        if not children:
            children = _split_top_level_children(body)
    if children:
        captured[key] = children[:2]


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""


def _step_block(step: int, label: str, content: str) -> str:
    body = content or (
        f'<div class="kpass34-missing">Step {step} certified card was not available for this quarterback on the selected matchup.</div>'
    )
    return (
        f'<section class="kpass34-step" data-passing-step="{step}">'
        '<div class="kpass34-stephead">'
        f'<span class="kpass34-stepname">{label}</span>'
        f'<span class="kpass34-stepnum">STEP {step} / 10</span>'
        '</div>'
        f'{body}</section>'
    )


def _player_card(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index)
    if not identity:
        identity = '<div class="kpass34-missing">Verified quarterback identity card unavailable.</div>'
    stack = [
        '<article class="kpass34-player" data-player-card-index="%d" data-combined-step-count="10">' % index,
        '<div class="kpass34-cardbar"><strong>Quarterback Analysis Card</strong><div class="kpass34-cardchips"><span class="kpass34-chip">10/10 COMBINED</span><span class="kpass34-chip blue">EXACT-ID STACK</span></div></div>',
        identity,
    ]
    for step, label, key in _STEP_LABELS:
        stack.append(_step_block(step, label, _piece(captured, key, index)))
    stack.append('</article>')
    return "".join(stack)


def _combined_player_cards_html(captured: dict[str, list[str]]) -> str:
    return '<div class="kpass34-grid">' + _player_card(captured, 0) + _player_card(captured, 1) + '</div>'


def _is_step_status(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith(("✅ STEP ", "⚠️ STEP ", "ℹ️ STEP 10", "🏆 NFL PASSING YARDS BUILD"))


def render_nfl_passing_yards_hub() -> None:
    """Compose certified V33 outputs into two player-first cards."""
    st.markdown(_PLAYER_CARD_CSS, unsafe_allow_html=True)

    captured: dict[str, list[str]] = {}
    placeholder = None

    original_markdown = st.markdown
    original_success = st.success
    original_warning = st.warning
    original_info = st.info
    original_banner = prior._visual_build_banner_v33
    original_identity_factory = identity_visual_ui._qb_hero_card
    original_profile_factory = profile_visual_ui._profile_card_v30
    original_provenance = provenance_ui._with_provenance
    original_pressure_factory = pressure_ui._pressure_card
    original_personnel_factory = personnel_visual_ui._personnel_card
    original_environment_factory = environment_ui._environment_card
    original_projection_factory = projection_ui._projection_card
    original_context_factory = context_ui._context_card
    original_distribution_factory = distribution_ui._distribution_card
    original_market_logo_injector = market_visual_ui._inject_team_logo
    original_projection_st = projection_ui.st
    original_context_st = context_ui.st
    original_distribution_st = distribution_ui.st
    original_market_st = market_ui.st

    def refresh_composed_placeholder() -> None:
        if placeholder is None:
            return
        if len(captured.get("identity") or []) < 2:
            return
        placeholder.markdown(_combined_player_cards_html(captured), unsafe_allow_html=True)

    def capture_pair(key: str, html: str) -> str:
        rows = captured.setdefault(key, [])
        if len(rows) < 2:
            rows.append(html)
        refresh_composed_placeholder()
        return html

    def capture_identity_card(ctx: dict[str, Any], preseason: bool, matchup: dict[str, str] | None = None) -> str:
        return capture_pair("identity", original_identity_factory(ctx, preseason, matchup))

    def capture_profile_card(team_ctx: dict[str, Any], qb_profile: dict[str, Any]) -> str:
        return capture_pair("profile", original_profile_factory(team_ctx, qb_profile))

    def capture_provenance(html: str, row: dict, label: str) -> str:
        final_html = original_provenance(html, row, label)
        if label == "Step 2 source":
            profile_rows = captured.setdefault("profile", [])
            if profile_rows:
                profile_rows[-1] = final_html
            elif len(profile_rows) < 2:
                profile_rows.append(final_html)
        elif label == "Step 3 source":
            capture_pair("defense", final_html)
        refresh_composed_placeholder()
        return final_html

    def capture_pressure_card(qb_ctx: dict, offense_ctx: dict, defense_ctx: dict, pressure_row: dict) -> str:
        return capture_pair("pressure", original_pressure_factory(qb_ctx, offense_ctx, defense_ctx, pressure_row))

    def capture_personnel_card(personnel_row: dict) -> str:
        return capture_pair("personnel", original_personnel_factory(personnel_row))

    def capture_environment_card(environment_row: dict) -> str:
        html = original_environment_factory(environment_row)
        captured["environment"] = [html]
        refresh_composed_placeholder()
        return html

    def capture_projection_card(projection_row: dict) -> str:
        return capture_pair("projection", original_projection_factory(projection_row))

    def capture_context_card(context_row: dict) -> str:
        return capture_pair("context", original_context_factory(context_row))

    def capture_distribution_card(distribution_row: dict) -> str:
        return capture_pair("distribution", original_distribution_factory(distribution_row))

    def capture_final_market_card(card_html: str, visual: dict) -> str:
        final_html = original_market_logo_injector(card_html, visual)
        return capture_pair("market", final_html)

    def composed_markdown(body: Any, *args: Any, **kwargs: Any):
        nonlocal placeholder
        text = body if isinstance(body, str) else ""

        if '<div class="kpy-step">' in text:
            if "Step 1 — Verified Matchup + Quarterback Identity" in text and placeholder is None:
                placeholder = st.empty()
            if "Step 10 — Market Edge + Final Grade" in text:
                return original_markdown(
                    '<div class="kpass34-market-controls"><b>🎯 Live Market Inputs</b><span>Enter the verified sportsbook line and two-way prices below. The resulting Step 10 evaluation is displayed inside each quarterback card above; sportsbook projection influence remains 0.0%.</span></div>',
                    unsafe_allow_html=True,
                )
            return None

        for marker, key in _GRID_MARKERS.items():
            if marker in text:
                _capture_grid(captured, key, text)
                refresh_composed_placeholder()
                return None

        if '<section class="kpy-env"' in text:
            if not captured.get("environment"):
                captured["environment"] = [text]
            refresh_composed_placeholder()
            return None

        if any(marker in text for marker in ('<div class="kpy8-active"', '<div class="kpy9-active"', '<div class="kpy10-active"')):
            return None

        return original_markdown(body, *args, **kwargs)

    def filtered_success(body: Any, *args: Any, **kwargs: Any):
        if _is_step_status(body):
            return None
        return original_success(body, *args, **kwargs)

    def filtered_warning(body: Any, *args: Any, **kwargs: Any):
        if _is_step_status(body):
            return None
        return original_warning(body, *args, **kwargs)

    def filtered_info(body: Any, *args: Any, **kwargs: Any):
        if _is_step_status(body):
            return None
        return original_info(body, *args, **kwargs)

    projection_proxy = _CompositionStreamlitProxy(original_projection_st, composed_markdown, filtered_success, filtered_warning, filtered_info)
    context_proxy = _CompositionStreamlitProxy(original_context_st, composed_markdown, filtered_success, filtered_warning, filtered_info)
    distribution_proxy = _CompositionStreamlitProxy(original_distribution_st, composed_markdown, filtered_success, filtered_warning, filtered_info)
    market_proxy = _CompositionStreamlitProxy(original_market_st, composed_markdown, filtered_success, filtered_warning, filtered_info)

    prior._visual_build_banner_v33 = _visual_build_banner_v34
    identity_visual_ui._qb_hero_card = capture_identity_card
    profile_visual_ui._profile_card_v30 = capture_profile_card
    provenance_ui._with_provenance = capture_provenance
    pressure_ui._pressure_card = capture_pressure_card
    personnel_visual_ui._personnel_card = capture_personnel_card
    environment_ui._environment_card = capture_environment_card
    projection_ui._projection_card = capture_projection_card
    context_ui._context_card = capture_context_card
    distribution_ui._distribution_card = capture_distribution_card
    market_visual_ui._inject_team_logo = capture_final_market_card
    projection_ui.st = projection_proxy
    context_ui.st = context_proxy
    distribution_ui.st = distribution_proxy
    market_ui.st = market_proxy
    st.markdown = composed_markdown
    st.success = filtered_success
    st.warning = filtered_warning
    st.info = filtered_info
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        st.markdown = original_markdown
        st.success = original_success
        st.warning = original_warning
        st.info = original_info
        projection_ui.st = original_projection_st
        context_ui.st = original_context_st
        distribution_ui.st = original_distribution_st
        market_ui.st = original_market_st
        identity_visual_ui._qb_hero_card = original_identity_factory
        profile_visual_ui._profile_card_v30 = original_profile_factory
        provenance_ui._with_provenance = original_provenance
        pressure_ui._pressure_card = original_pressure_factory
        personnel_visual_ui._personnel_card = original_personnel_factory
        environment_ui._environment_card = original_environment_factory
        projection_ui._projection_card = original_projection_factory
        context_ui._context_card = original_context_factory
        distribution_ui._distribution_card = original_distribution_factory
        market_visual_ui._inject_team_logo = original_market_logo_injector
        prior._visual_build_banner_v33 = original_banner

    if placeholder is not None:
        placeholder.markdown(_combined_player_cards_html(captured), unsafe_allow_html=True)


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V34 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PLAYER_CARD_COMPOSITION_ONLY",
    "PLAYER_CARD_STEP_COUNT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_PLAYER_CARD_CSS",
    "_combined_player_cards_html",
    "_extract_elements_by_class",
    "_split_top_level_children",
    "_visual_build_banner_v34",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
