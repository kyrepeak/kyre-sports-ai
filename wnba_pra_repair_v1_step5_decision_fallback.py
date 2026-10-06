"""WNBA PRA Repair V1 Step 5 — truthful decision/data fallback.

Exact certified market decisions always win. When no exact market card exists,
Step 5 may use a clearly labeled reference threshold with the frozen hosted
Step-5F probability output. If that model result is unavailable, official
recent-game PRA hit rate is the final fallback. Nothing in this module creates
a sportsbook line or changes projection/market/qualification/ranking math.
"""
from __future__ import annotations

from html import escape
import math
from statistics import median
from typing import Any, Mapping

MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 5 DECISION FALLBACK"
MAX_HISTORY_GAMES = 10


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pra(row: Mapping[str, Any]) -> float | None:
    values = [_num(row.get("points")), _num(row.get("rebounds")), _num(row.get("assists"))]
    if any(value is None for value in values):
        return None
    return float(sum(value for value in values if value is not None))


def history_pra_values(history: Mapping[str, Any] | None) -> list[float]:
    games = history.get("games") if isinstance(history, Mapping) else None
    if not isinstance(games, list):
        return []
    rows = [dict(row) for row in games if isinstance(row, Mapping)]
    rows.sort(key=lambda row: _text(row.get("game_date")), reverse=True)
    values: list[float] = []
    for row in rows[:MAX_HISTORY_GAMES]:
        value = _pra(row)
        if value is not None:
            values.append(value)
    return values


def reference_line(history: Mapping[str, Any] | None) -> float | None:
    """Use a half-point threshold centered on the recent official PRA median."""
    values = history_pra_values(history)
    if not values:
        return None
    center = float(median(values))
    return float(math.floor(center) + 0.5)


def _model_side(probability_payload: Mapping[str, Any] | None, expected_pra: float | None, line: float) -> tuple[str, float] | None:
    if not isinstance(probability_payload, Mapping):
        return None
    primary = probability_payload.get("primary_result")
    fair = primary.get("fair_odds") if isinstance(primary, Mapping) else None
    if not isinstance(fair, Mapping):
        return None
    over = fair.get("over") if isinstance(fair.get("over"), Mapping) else {}
    under = fair.get("under") if isinstance(fair.get("under"), Mapping) else {}
    if over.get("available") is not True or under.get("available") is not True:
        return None
    p_over = _num(over.get("fair_probability"))
    p_under = _num(under.get("fair_probability"))
    if p_over is None or p_under is None or not 0.0 <= p_over <= 1.0 or not 0.0 <= p_under <= 1.0:
        return None
    if p_over > p_under:
        return "OVER", p_over
    if p_under > p_over:
        return "UNDER", p_under
    direction = "OVER" if expected_pra is not None and expected_pra >= line else "UNDER"
    return direction, p_over


def _history_side(values: list[float], expected_pra: float | None, line: float) -> tuple[str, float] | None:
    if not values:
        return None
    over_hits = sum(1 for value in values if value > line)
    under_hits = sum(1 for value in values if value < line)
    resolved = over_hits + under_hits
    if resolved <= 0:
        return None
    p_over = over_hits / resolved
    p_under = under_hits / resolved
    if p_over > p_under:
        return "OVER", round(p_over, 10)
    if p_under > p_over:
        return "UNDER", round(p_under, 10)
    direction = "OVER" if expected_pra is not None and expected_pra >= line else "UNDER"
    return direction, 0.5


def build_step5_decision(
    base_summary: Mapping[str, Any],
    history: Mapping[str, Any] | None,
    probability_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(base_summary)
    expected_pra = _num(result.get("expected_pra"))

    if result.get("market_ready") is True:
        result.update({
            "decision_source": "CERTIFIED MARKET",
            "line_source": "SPORTSBOOK",
            "fallback_used": False,
            "reference_line_is_sportsbook": False,
            "history_games_used": 0,
        })
        return result

    values = history_pra_values(history)
    line = reference_line(history)
    if line is None:
        result.update({
            "line": None,
            "direction": "N/A",
            "probability": None,
            "decision_source": "DATA LIMITED",
            "line_source": "NONE",
            "fallback_used": False,
            "reference_line_is_sportsbook": False,
            "history_games_used": 0,
        })
        return result

    model = _model_side(probability_payload, expected_pra, line)
    if model is not None:
        direction, probability = model
        result.update({
            "line": line,
            "direction": direction,
            "probability": probability,
            "decision_source": "MODEL FALLBACK",
            "line_source": "REFERENCE",
            "fallback_used": True,
            "reference_line_is_sportsbook": False,
            "history_games_used": len(values),
        })
        return result

    empirical = _history_side(values, expected_pra, line)
    if empirical is not None:
        direction, probability = empirical
        result.update({
            "line": line,
            "direction": direction,
            "probability": probability,
            "decision_source": "HISTORY FALLBACK",
            "line_source": "REFERENCE",
            "fallback_used": True,
            "reference_line_is_sportsbook": False,
            "history_games_used": len(values),
        })
        return result

    result.update({
        "line": None,
        "direction": "N/A",
        "probability": None,
        "decision_source": "DATA LIMITED",
        "line_source": "NONE",
        "fallback_used": False,
        "reference_line_is_sportsbook": False,
        "history_games_used": len(values),
    })
    return result


def _fmt_number(value: Any) -> str:
    number = _num(value)
    return "N/A" if number is None else f"{number:.1f}"


def _fmt_probability(value: Any) -> str:
    number = _num(value)
    return "N/A" if number is None else f"{number * 100.0:.1f}%"


def render_step5_final_card(summary: Mapping[str, Any]) -> None:
    import streamlit as st

    source = _text(summary.get("decision_source")) or "DATA LIMITED"
    line_source = _text(summary.get("line_source")) or "NONE"
    line_label = "Sportsbook Line" if line_source == "SPORTSBOOK" else "Reference Line" if line_source == "REFERENCE" else "Line"
    note = {
        "CERTIFIED MARKET": "Exact certified market decision.",
        "MODEL FALLBACK": "Reference threshold + frozen Step-5F model probability. This is not a sportsbook line.",
        "HISTORY FALLBACK": "Reference threshold + official recent-game PRA hit rate. This is not a sportsbook line.",
        "DATA LIMITED": "No certified market, model probability, or official-history fallback is available; missing values remain N/A.",
    }.get(source, "Missing values remain N/A.")

    st.markdown(
        """
<style>
.ks-s5-final{border:1px solid rgba(56,189,248,.3);border-radius:20px;padding:1rem 1.05rem;margin:.75rem 0 1rem;background:linear-gradient(145deg,rgba(2,132,199,.14),rgba(15,23,42,.95))}.ks-s5-kicker{font-size:.62rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase;color:#7dd3fc}.ks-s5-title{font-size:1.12rem;font-weight:950;color:#f8fafc;margin:.16rem 0 .25rem}.ks-s5-note{font-size:.68rem;color:#94a3b8;margin-bottom:.62rem}.ks-s5-grid{display:grid;grid-template-columns:repeat(4,minmax(90px,1fr));gap:.45rem}.ks-s5-cell{border:1px solid rgba(148,163,184,.15);border-radius:14px;padding:.62rem .5rem;text-align:center;background:rgba(15,23,42,.75)}.ks-s5-cell b{display:block;color:#f8fafc;font-size:1rem}.ks-s5-cell span{display:block;color:#64748b;font-size:.58rem;font-weight:900;letter-spacing:.07em;margin-top:.12rem}@media(max-width:620px){.ks-s5-grid{grid-template-columns:repeat(2,1fr)}}
.wn4-decision,.ks-s4-final{display:none!important}
</style>
""",
        unsafe_allow_html=True,
    )
    html = (
        f'<div class="ks-s5-final" data-decision-source="{escape(source)}" data-line-source="{escape(line_source)}">'
        '<div class="ks-s5-kicker">Final PRA Card • Step 5</div>'
        f'<div class="ks-s5-title">{escape(source)}</div>'
        f'<div class="ks-s5-note">{escape(note)}</div>'
        '<div class="ks-s5-grid">'
        f'<div class="ks-s5-cell"><b>{escape(_fmt_number(summary.get("expected_pra")))}</b><span>Expected PRA</span></div>'
        f'<div class="ks-s5-cell"><b>{escape(_fmt_number(summary.get("line")))}</b><span>{escape(line_label)}</span></div>'
        f'<div class="ks-s5-cell"><b>{escape(_text(summary.get("direction")) or "N/A")}</b><span>Direction</span></div>'
        f'<div class="ks-s5-cell"><b>{escape(_fmt_probability(summary.get("probability")))}</b><span>Probability</span></div>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


__all__ = [
    "MAX_HISTORY_GAMES",
    "MODEL_VERSION",
    "build_step5_decision",
    "history_pra_values",
    "reference_line",
    "render_step5_final_card",
]
