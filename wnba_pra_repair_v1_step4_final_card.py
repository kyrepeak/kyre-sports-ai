"""WNBA PRA Repair V1 Step 4 — truthful universal final PRA card.

Presentation-only helper. It never creates a market line, side, probability, or
projection. It formats values already present in the frozen selected-player
snapshot and exact certified PRA card. Missing market context remains N/A.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping


MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 4 UNIVERSAL FINAL CARD"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _direction(value: Any) -> str:
    text = _text(value).upper()
    if text == "OVER" or text.startswith("OVER "):
        return "OVER"
    if text == "UNDER" or text.startswith("UNDER "):
        return "UNDER"
    return "N/A"


def _fmt_number(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return "N/A" if number is None else f"{number:.{digits}f}"


def _fmt_probability(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "N/A"
    if abs(number) <= 1.000001:
        number *= 100.0
    return f"{number:.1f}%"


def build_final_card(
    player: Mapping[str, Any] | None,
    exact_card: Mapping[str, Any] | None,
    card_state: str,
) -> dict[str, Any]:
    """Return a display-only summary without inventing unavailable market data."""
    player_map = dict(player) if isinstance(player, Mapping) else {}
    card_map = dict(exact_card) if isinstance(exact_card, Mapping) else {}
    prop = card_map.get("prop") if isinstance(card_map.get("prop"), Mapping) else {}
    model = card_map.get("model") if isinstance(card_map.get("model"), Mapping) else {}

    expected_pra = _num(player_map.get("projected_pra"))
    line = _num(prop.get("line"))
    direction = _direction(prop.get("pick") or prop.get("side"))
    probability = _num(model.get("resolved_fair_probability"))

    market_ready = (
        line is not None
        and direction in {"OVER", "UNDER"}
        and probability is not None
        and _text(card_state) == "qualified_exact_pra_card"
    )

    return {
        "player_id": player_map.get("player_id"),
        "player_name": _text(player_map.get("player_name")) or "Selected Player",
        "expected_pra": expected_pra,
        "line": line if market_ready else None,
        "direction": direction if market_ready else "N/A",
        "probability": probability if market_ready else None,
        "market_ready": bool(market_ready),
        "card_state": _text(card_state) or "unavailable",
    }


def render_final_card(summary: Mapping[str, Any]) -> None:
    """Render the same final PRA summary surface for every eligible player."""
    import streamlit as st

    ready = bool(summary.get("market_ready"))
    status = "CERTIFIED MARKET" if ready else "NO CERTIFIED MARKET"
    direction = _text(summary.get("direction")) or "N/A"
    st.markdown(
        """
<style>
.ks-s4-final{border:1px solid rgba(56,189,248,.28);border-radius:20px;padding:1rem 1.05rem;margin:.75rem 0 1rem;background:linear-gradient(145deg,rgba(2,132,199,.13),rgba(15,23,42,.94))}
.ks-s4-kicker{font-size:.62rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase;color:#7dd3fc}.ks-s4-title{font-size:1.12rem;font-weight:950;color:#f8fafc;margin:.16rem 0 .55rem}.ks-s4-grid{display:grid;grid-template-columns:repeat(4,minmax(90px,1fr));gap:.45rem}.ks-s4-cell{border:1px solid rgba(148,163,184,.15);border-radius:14px;padding:.62rem .5rem;text-align:center;background:rgba(15,23,42,.75)}.ks-s4-cell b{display:block;color:#f8fafc;font-size:1rem}.ks-s4-cell span{display:block;color:#64748b;font-size:.58rem;font-weight:900;letter-spacing:.07em;margin-top:.12rem}@media(max-width:620px){.ks-s4-grid{grid-template-columns:repeat(2,1fr)}}
.wn4-decision{display:none!important}
</style>
""",
        unsafe_allow_html=True,
    )
    html = (
        '<div class="ks-s4-final" data-wnba-pra-repair-v1-step4="universal-final-card" '
        f'data-market-ready="{str(ready).lower()}">'
        '<div class="ks-s4-kicker">Final PRA Card</div>'
        f'<div class="ks-s4-title">{escape(status)}</div>'
        '<div class="ks-s4-grid">'
        f'<div class="ks-s4-cell"><b>{escape(_fmt_number(summary.get("expected_pra")))}</b><span>Expected PRA</span></div>'
        f'<div class="ks-s4-cell"><b>{escape(_fmt_number(summary.get("line")))}</b><span>Line</span></div>'
        f'<div class="ks-s4-cell"><b>{escape(direction)}</b><span>Direction</span></div>'
        f'<div class="ks-s4-cell"><b>{escape(_fmt_probability(summary.get("probability")))}</b><span>Probability</span></div>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "build_final_card", "render_final_card"]
