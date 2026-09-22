"""WNBA PRA V3.6.11 — Step-5 presentation fail-safe firewall.

Presentation-only wrapper over V3.6.10. Keeps the exact V3.6.10/V2.8 Step-5
candidate payload, eligibility gate, ranking, compact layout and performance
repair. This layer adds final exception isolation around OPTIONAL presentation
enrichment only: headshots, logos, opponent defense, H2H and projection-path
HTML.

If any optional display helper fails unexpectedly, the already-computed Step-5
Top-5 still renders with safe placeholders. A whole-card fallback preserves the
core rank/player/matchup/status/minutes/P/R/A/USG/PRA fields even if an enrichment
renderer throws. Model/projection exceptions are NOT swallowed by this module.

No projection, availability, minutes/usage math, sportsbook, qualification,
Monte Carlo, final-ready, ranking, selection, provider, cache or TTL logic is
changed.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import wnba_pra_step5_perf_v3610 as prior

v28 = prior.v28
cards = prior.cards
defense_layer = prior.defense_layer
history_layer = prior.history_layer
layout = prior.prior

MODEL_VERSION = "PRA V3.6.11 • STEP-5 FAIL-SAFE FIREWALL • MODEL PRESERVED"


def _get(obj, key, default=None):
    try:
        return obj.get(key, default)
    except Exception:
        return default


def _float(value, default=0.0):
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _display_num(value, digits=1, fallback="N/A"):
    try:
        x = float(value)
        if not math.isfinite(x):
            return fallback
        return f"{x:.{digits}f}"
    except Exception:
        return fallback


def _norm(value: str) -> str:
    try:
        return defense_layer._norm(value)
    except Exception:
        return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _player_key(name: str) -> str:
    try:
        return cards._player_key(name)
    except Exception:
        return "".join(ch.lower() for ch in str(name or "") if ch.isalnum())


def _safe_defense_map(day):
    try:
        value = defense_layer._opponent_context_map(day)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _safe_history_map(day, picks, defenses):
    try:
        value = history_layer._board_history_map(day, picks, defenses)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _fallback_headshot(name: str) -> str:
    return (
        '<div style="width:62px;height:62px;min-width:62px;border-radius:50%;'
        'background:#102a3d;border:1px solid #2c7598;display:flex;align-items:center;'
        'justify-content:center;overflow:hidden" '
        f'aria-label="{escape(name, quote=True)} headshot unavailable">'
        '<span style="font-size:28px;opacity:.72">👤</span></div>'
    )


def _safe_headshot(p: dict, name: str) -> str:
    try:
        pid = prior._headshot_id(p)
        return cards._headshot_html(pid, name)
    except Exception:
        return _fallback_headshot(name)


def _fallback_logo(label: str) -> str:
    abbr = str(label or "TEAM")[:4].upper()
    return (
        '<span style="width:30px;height:30px;border:1px solid #31516e;border-radius:50%;'
        'display:inline-flex;align-items:center;justify-content:center;color:#8ea6bb;'
        f'font-size:8px;font-weight:900;flex:0 0 30px">{escape(abbr)}</span>'
    )


def _safe_logo(team_id, label: str, tricode: str, title: str) -> str:
    try:
        meta = prior._logo_meta(team_id, label, tricode)
        return cards._logo_html(meta, label, title)
    except Exception:
        return _fallback_logo(label)


def _fallback_box(title: str, message: str, border: str, background: str) -> str:
    return (
        f'<div class="w369-box" style="border:1px solid {border};background:{background}">'
        '<div class="w369-boxhead">'
        f'<b style="color:#dceaf4">{escape(title)}</b>'
        '<span style="color:#91a2af">N/A</span>'
        '</div>'
        f'<div class="w369-subline"><span>{escape(message)}</span></div>'
        '</div>'
    )


def _safe_defense_box(obj: dict, opponent: str) -> str:
    try:
        return layout._compact_defense_box(obj if isinstance(obj, dict) else {}, opponent)
    except Exception:
        return _fallback_box(
            f"🛡️ {opponent} DEFENSE",
            "Defensive context unavailable • projection unaffected",
            "#31536a",
            "#071927",
        )


def _safe_history_box(obj: dict, opponent: str) -> str:
    try:
        return layout._compact_history_box(obj if isinstance(obj, dict) else {}, opponent)
    except Exception:
        return _fallback_box(
            f"📚 VS {opponent} • HISTORY",
            "No matchup history available • projection unaffected",
            "#5a476f",
            "#141126",
        )


def _safe_path_box(p: dict) -> str:
    try:
        return layout._compact_path_box(p)
    except Exception:
        return _fallback_box(
            "🧭 PROJECTION PATH",
            "Stored path fields unavailable • final PRA above remains model output",
            "#315d72",
            "#0a1b27",
        )


def _status_text(p: dict) -> str:
    try:
        if bool(_get(p, "starter", False)):
            return "STARTER"
        raw = str(_get(p, "status", "NO DESIGNATION") or "NO DESIGNATION")
        return raw if raw != "NO DESIGNATION" else "ACTIVE"
    except Exception:
        return "ACTIVE"


def _core_card(p: dict, rank: int, note: str = "") -> str:
    """Last-resort card containing only already-computed Step-5 core output."""
    name = str(_get(p, "name", "Player") or "Player")
    team = str(_get(p, "team", "") or "")
    opponent = str(_get(p, "opponent", "—") or "—")
    status = _status_text(p)
    mins = _display_num(_get(p, "min"), 1)
    pra = _display_num(_get(p, "pra"), 1)
    pts = _display_num(_get(p, "p"), 1)
    reb = _display_num(_get(p, "r"), 1)
    ast = _display_num(_get(p, "a"), 1)
    usg = _display_num(_get(p, "usg"), 1)
    first = " first" if rank == 1 else ""

    return (
        f'<div class="w369-card{first}">'
        f'<div class="w369-eyebrow"><span>#{int(rank)} STEP-5 PRA</span>'
        '<span style="color:#ffe083;font-size:.34rem">DISPLAY FALLBACK</span></div>'
        '<div class="w369-hero">'
        f'{_fallback_headshot(name)}'
        '<div class="w369-hero-main">'
        f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
        f'<div class="w369-meta">{escape(team)} vs {escape(opponent)} • {escape(status)} • {escape(mins)} MIN</div>'
        '</div></div>'
        f'<div class="w369-pra" style="margin-top:6px">{escape(pra)}<span>Projected PRA</span></div>'
        '<div class="w369-split">'
        f'<div><span>PTS</span><b>{escape(pts)}</b></div>'
        f'<div><span>REB</span><b>{escape(reb)}</b></div>'
        f'<div><span>AST</span><b>{escape(ast)}</b></div>'
        f'<div><span>USG</span><b>{escape(usg)}</b></div>'
        '</div>'
        '<div class="w369-boardnote" style="margin-top:7px">'
        f'Optional presentation enrichment unavailable. Core Step-5 model output preserved. {escape(note)}'
        '</div></div>'
    )


def _render_card(p: dict, rank: int, defenses: dict, histories: dict) -> str:
    first = " first" if rank == 1 else ""
    status = _status_text(p)
    name = str(_get(p, "name", "Player") or "Player")
    team = str(_get(p, "team", "") or "")
    opponent = str(_get(p, "opponent", "—") or "—")

    defense = defenses.get(_norm(opponent), {}) if isinstance(defenses, dict) else {}
    history = histories.get(_player_key(name), {}) if isinstance(histories, dict) else {}

    headshot = _safe_headshot(p, name)
    team_logo = _safe_logo(
        _get(p, "team_id"), team, str(_get(p, "team_tricode", team) or team), f"{team} logo"
    )
    opp_logo = _safe_logo(
        _get(p, "opponent_id"), opponent,
        str(_get(p, "opponent_tricode", opponent) or opponent), f"{opponent} logo"
    )

    pra = _display_num(_get(p, "pra"), 1)
    pts = _display_num(_get(p, "p"), 1)
    reb = _display_num(_get(p, "r"), 1)
    ast = _display_num(_get(p, "a"), 1)
    usg = _display_num(_get(p, "usg"), 1)
    mins = _display_num(_get(p, "min"), 1)

    return (
        f'<div class="w369-card{first}">'
        '<div class="w369-eyebrow">'
        f'<span>#{int(rank)} STEP-5 PRA</span>'
        '<div class="w369-layerchips">'
        '<span class="w369-chip">ID</span><span class="w369-chip">DEF</span>'
        '<span class="w369-chip">H2H</span><span class="w369-chip">PATH</span>'
        '</div></div>'
        '<div class="w369-hero">'
        f'{headshot}'
        '<div class="w369-hero-main">'
        f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
        '<div class="w369-match">'
        f'{team_logo}<span style="color:#8da3b8;font-size:.45rem;font-weight:800">vs</span>{opp_logo}'
        '</div>'
        f'<div class="w369-meta">{escape(team)} vs {escape(opponent)} • {escape(status)} • {escape(mins)} MIN</div>'
        '</div></div>'
        '<div class="w369-scoreline">'
        f'<div class="w369-pra">{escape(pra)}<span>Projected PRA</span></div>'
        '</div>'
        '<div class="w369-split">'
        f'<div><span>PTS</span><b>{escape(pts)}</b></div>'
        f'<div><span>REB</span><b>{escape(reb)}</b></div>'
        f'<div><span>AST</span><b>{escape(ast)}</b></div>'
        f'<div><span>USG</span><b>{escape(usg)}</b></div>'
        '</div>'
        f'{_safe_defense_box(defense, opponent)}'
        f'{_safe_history_box(history, opponent)}'
        f'{_safe_path_box(p)}'
        '</div>'
    )


def _render_top5_v3611(picks):
    """V3.6.10 board with final isolation for optional display enrichment."""
    if not picks:
        st.markdown(
            '<div class="w2-empty">No eligible Step 5 projections are available.</div>',
            unsafe_allow_html=True,
        )
        return

    day = st.session_state.get("wnba_pra_v2_date")
    defenses = _safe_defense_map(day)
    histories = _safe_history_map(day, picks, defenses)
    rendered = []

    for i, p in enumerate(picks, 1):
        try:
            rendered.append(_render_card(p, i, defenses, histories))
        except Exception as exc:
            # Presentation-only exception isolation. Never recompute or alter the
            # already-ranked Step-5 payload to recover from a display failure.
            rendered.append(_core_card(p, i, note=f"Display error isolated: {type(exc).__name__}."))

    st.markdown(
        layout._LAYOUT_CSS
        + '<div class="w23-summary w369-board">'
        '<div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">Same Step-5 ranking/projections and compact layout. Optional identity, defense, H2H and projection-path layers now fail independently instead of being able to break the Top-5 board.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div>'
        '<div class="w369-boardnote">'
        '<b>🛡️ Fail-safe guardrail:</b> missing headshot → silhouette • missing logo → team abbreviation • '
        'missing defense → N/A context • missing H2H → no-history state • missing path field → N/A/fallback. '
        'An unexpected enrichment-render error falls back to the core Step-5 card. '
        '<b>Model guardrail:</b> projection, eligibility, ranking, sportsbook and Monte Carlo logic are unchanged.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _install_overrides():
    # Keep V3.6.10 candidate generation/performance behavior exactly as-is.
    v28._render_top5 = _render_top5_v3611
    cards._render_top5 = _render_top5_v3611
    cards.v28._render_top5 = _render_top5_v3611
    defense_layer.cards._render_top5 = _render_top5_v3611
    defense_layer.cards.v28._render_top5 = _render_top5_v3611


def install():
    prior.install()
    _install_overrides()


def begin_render():
    prior.begin_render()
    _install_overrides()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
