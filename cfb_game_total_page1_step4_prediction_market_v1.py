"""Pure Step-4 prediction + market presentation helpers.

This module is intentionally Streamlit-free and presentation-only. It reads the
existing frozen projection output plus verified market fields already present on
the display game. Missing market values fail closed as "Line not posted".
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
STEP4_MARKER = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_ACTIVE"


def _clean(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _coerce_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sources(display_game: Mapping[str, Any]):
    yield display_game
    for key in ("odds", "market"):
        nested = display_game.get(key)
        if isinstance(nested, Mapping):
            yield nested


def _first_number(display_game: Mapping[str, Any], *keys: str) -> float | None:
    for source in _sources(display_game):
        for key in keys:
            number = _coerce_number(source.get(key))
            if number is not None:
                return number
    return None


def _decimal(value: float) -> str:
    return f"{value:.1f}"


def _signed_decimal(value: float) -> str:
    return f"{value:+.1f}"


def _american(value: float) -> str:
    rounded = int(round(value))
    return f"{rounded:+d}"


def _confidence(value: Any) -> str:
    number = _coerce_number(value)
    if number is None:
        return "—"
    if 0.0 <= number <= 1.0:
        number *= 100.0
    number = max(0.0, min(100.0, number))
    return f"{number:.0f}%"


def _market_total(display_game: Mapping[str, Any]) -> float | None:
    return _first_number(display_game, "total", "market_total", "total_line", "over_under", "ou")


def _paired_line(
    display_game: Mapping[str, Any],
    away_keys: tuple[str, ...],
    home_keys: tuple[str, ...],
    *,
    moneyline: bool = False,
) -> str:
    away = _first_number(display_game, *away_keys)
    home = _first_number(display_game, *home_keys)
    if away is None and home is None:
        return "Line not posted"
    away_name = _clean(display_game.get("away_team")) or "Away"
    home_name = _clean(display_game.get("home_team")) or "Home"
    formatter = _american if moneyline else _signed_decimal
    pieces: list[str] = []
    if away is not None:
        pieces.append(f"{away_name} {formatter(away)}")
    if home is not None:
        pieces.append(f"{home_name} {formatter(home)}")
    return " • ".join(pieces)


def build_prediction_market_html(
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    display_game: Mapping[str, Any],
    statuses: Mapping[int, str],
    ready_count: int,
) -> str:
    del statuses
    projected_value = (
        final.get("projected_combined_total")
        if final.get("ready")
        else raw.get("projected_combined_total")
    )
    projected_number = _coerce_number(projected_value)
    projected_text = "—" if projected_number is None else _decimal(projected_number)
    grade = _clean(final.get("grade")) if final.get("ready") else "—"
    confidence = _confidence(final.get("forecast_strength")) if final.get("ready") else "—"

    market_total = _market_total(display_game)
    market_text = "Line not posted" if market_total is None else _decimal(market_total)
    spread_text = _paired_line(
        display_game,
        ("away_spread", "away_point_spread"),
        ("home_spread", "home_point_spread"),
    )
    moneyline_text = _paired_line(
        display_game,
        ("away_moneyline", "away_ml"),
        ("home_moneyline", "home_ml"),
        moneyline=True,
    )

    if market_total is None or projected_number is None:
        lean = "Market line unavailable"
        comparison = "No verified total • model remains independent"
        direction = "↔"
    else:
        edge = projected_number - market_total
        comparison = f"{_signed_decimal(edge)} pts vs market"
        if edge > 0:
            lean = f"Over +{abs(edge):.1f}"
            direction = "↗"
        elif edge < 0:
            lean = f"Under -{abs(edge):.1f}"
            direction = "↘"
        else:
            lean = "Even 0.0"
            direction = "↔"

    ready = max(0, min(12, int(ready_count)))
    return f"""
<div class="gt237-wrap" data-testid="gt237-prediction-market" data-step4="{STEP4_MARKER}">
  <div class="gt237-head">
    <div><span class="gt237-kicker">GAME TOTAL</span><h3>PREDICTION + MARKET COMPARISON</h3></div>
    <span class="gt237-cert">🛡 5M CERTIFIED</span>
  </div>
  <div class="gt237-primary">
    <div class="gt237-projection"><span>Projected Total</span><strong>{escape(projected_text)}</strong><small>Independent model projection</small></div>
    <div class="gt237-lean"><span>Over / Under Lean</span><strong>{escape(lean)}</strong><small>{escape(comparison)}</small><b>{direction}</b></div>
    <div class="gt237-confidence"><span>Confidence</span><strong>{escape(confidence)}</strong><small>Grade {escape(grade or '—')}</small></div>
  </div>
  <div class="gt237-market">
    <div><span>Market Total</span><strong>{escape(market_text)}</strong></div>
    <div><span>Spread</span><strong>{escape(spread_text)}</strong></div>
    <div><span>Moneyline</span><strong>{escape(moneyline_text)}</strong></div>
  </div>
  <div class="gt237-foot">
    <span>{ready}/12 verified</span>
    <span>0.0% sportsbook projection influence</span>
    <span>Verified lines only • missing markets never fabricated</span>
  </div>
</div>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_MARKER",
    "build_prediction_market_html",
]
