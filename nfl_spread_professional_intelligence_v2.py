"""NFL Spread Professional Intelligence V2 — readable projection + display-only H2H.

Additive presentation layer over frozen V1. The model, probabilities, fair line,
and sportsbook firewall remain owned by frozen V1/V3. V2 only replaces the
technical projection-range presentation and adds descriptive matchup history.
"""
from __future__ import annotations

from html import escape
import math
import re
from typing import Any

import nfl_spread_professional_intelligence_v1 as frozen

CSS = frozen.CSS
PRESENTATION_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
FROZEN_PRIOR = "nfl_spread_professional_intelligence_v1"


def _num(value: Any) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else math.nan
    except (TypeError, ValueError, OverflowError):
        return math.nan


def _pct(value: Any) -> str:
    number = _num(value)
    return f"{number * 100:.1f}%" if math.isfinite(number) else "—"


def _margin(value: Any) -> str:
    number = _num(value)
    return f"{number:+.1f}" if math.isfinite(number) else "—"


def _nickname(team: Any) -> str:
    bits = str(team or "Team").strip().split()
    return bits[-1] if bits else "Team"


def _side(analytics: dict[str, Any], market: dict[str, Any], book: dict[str, Any]) -> str:
    away_margin = _num(analytics.get("projected_away_margin"))
    market_ready = bool(market.get("ready")) and bool(book)
    if market_ready and math.isfinite(away_margin):
        fair_away, fair_home = -away_margin, away_margin
        market_away = _num(book.get("away_spread"))
        market_home = _num(book.get("home_spread"))
        if all(math.isfinite(x) for x in (market_away, market_home, fair_away, fair_home)):
            return "away" if (market_away - fair_away) >= (market_home - fair_home) else "home"
    away_win = _num(analytics.get("away_win_probability"))
    home_win = _num(analytics.get("home_win_probability"))
    return "away" if away_win >= home_win else "home"


def _side_range(analytics: dict[str, Any], side: str, low_key: str, high_key: str) -> tuple[float, float]:
    q = analytics.get("margin_quantiles") or {}
    lo, hi = _num(q.get(low_key)), _num(q.get(high_key))
    if side == "away":
        return lo, hi
    return (-hi if math.isfinite(hi) else math.nan, -lo if math.isfinite(lo) else math.nan)


def _plain_range(team: str, opponent: str, lo: float, hi: float) -> str:
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "—"
    if lo > hi:
        lo, hi = hi, lo
    if lo >= 0:
        return f"{_nickname(team)} by {abs(lo):.0f}–{abs(hi):.0f}"
    if hi <= 0:
        return f"{_nickname(opponent)} by {abs(hi):.0f}–{abs(lo):.0f}"
    return f"{_nickname(opponent)} by {abs(lo):.0f} → {_nickname(team)} by {abs(hi):.0f}"


def _expected_result(game: dict[str, Any], analytics: dict[str, Any]) -> str:
    margin = _num(analytics.get("projected_away_margin"))
    if not math.isfinite(margin):
        return "—"
    winner = game.get("away_team") if margin >= 0 else game.get("home_team")
    return f"{_nickname(winner)} by {abs(margin):.1f}"


def _projection_html(game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any], book: dict[str, Any]) -> str:
    side = _side(analytics, market, book)
    team = str(game.get("away_team") if side == "away" else game.get("home_team") or "Team")
    opponent = str(game.get("home_team") if side == "away" else game.get("away_team") or "Opponent")
    lo25, hi75 = _side_range(analytics, side, "p25", "p75")
    lo05, hi95 = _side_range(analytics, side, "p05", "p95")
    win = _num(analytics.get("away_win_probability" if side == "away" else "home_win_probability"))
    non_win = 1.0 - win if math.isfinite(win) else math.nan
    push = _num(analytics.get("push_probability"))
    push_text = _pct(push) if bool(market.get("ready")) and bool(book) else "—"
    return (
        '<section class="ksp7-section"><h3>WHAT THE MODEL EXPECTS</h3><div class="ksp7-row3">'
        f'<div class="ksp7-metric"><span>Expected result</span><b>{escape(_expected_result(game, analytics))}</b></div>'
        f'<div class="ksp7-metric"><span>Most likely range</span><b>{escape(_plain_range(team, opponent, lo25, hi75))}</b></div>'
        f'<div class="ksp7-metric"><span>Wider possible range</span><b>{escape(_plain_range(team, opponent, lo05, hi95))}</b></div>'
        f'<div class="ksp7-metric"><span>Chance team does not win</span><b>{escape(_pct(non_win))}</b></div>'
        f'<div class="ksp7-metric"><span>Push chance</span><b>{escape(push_text)}</b></div>'
        '</div></section>'
    )


def _history_html(history: dict[str, Any]) -> str:
    if not history.get("ready"):
        return (
            '<details class="ksp7-detail ksp7-detail-wide"><summary>MATCHUP HISTORY '
            '<span class="ksp7-detail-note">DISPLAY ONLY</span></summary><div class="ksp7-detail-body">'
            '<div class="ksp7-method"><strong>DISPLAY ONLY • 0.0% MODEL INFLUENCE</strong><br>'
            'No verified matchup history is available right now.</div></div></details>'
        )
    games = int(_num(history.get("games"))) if math.isfinite(_num(history.get("games"))) else 0
    average = _num(history.get("average_margin"))
    average_text = f"{average:.1f} pts" if math.isfinite(average) else "—"
    rows: list[str] = []
    for meeting in history.get("meetings") or []:
        if not isinstance(meeting, dict):
            continue
        date_text = str(meeting.get("date") or "Date unavailable")
        score = str(meeting.get("score") or "Score unavailable")
        winner = str(meeting.get("winner_abbr") or "—")
        margin = _num(meeting.get("margin"))
        result = "Tie" if winner == "TIE" else (f"{winner} by {margin:.0f}" if math.isfinite(margin) else winner)
        ats = str(meeting.get("ats_winner") or "").strip()
        ats_text = f" • ATS {ats}" if ats else ""
        rows.append(f'<div class="ksp7-item"><strong>{escape(date_text)}</strong> • {escape(score)} • {escape(result + ats_text)}</div>')
    series = str(history.get("series_summary") or "—")
    ats_summary = str(history.get("ats_summary") or "—")
    source = str(history.get("source") or "verified source").upper()
    return (
        '<details class="ksp7-detail ksp7-detail-wide"><summary>MATCHUP HISTORY '
        f'<span class="ksp7-detail-note">LAST {games} • DISPLAY ONLY</span></summary><div class="ksp7-detail-body">'
        '<div class="ksp7-method"><strong>DISPLAY ONLY • 0.0% MODEL INFLUENCE</strong></div>'
        '<div class="ksp7-row3" style="margin-top:10px">'
        f'<div class="ksp7-metric"><span>Series snapshot</span><b>{escape(series)}</b></div>'
        f'<div class="ksp7-metric"><span>Average margin</span><b>{escape(average_text)}</b></div>'
        f'<div class="ksp7-metric"><span>Verified ATS</span><b>{escape(ats_summary)}</b></div></div>'
        f'<div class="ksp7-list" style="margin-top:10px"><h4>Last {games} meetings</h4>{"".join(rows)}</div>'
        f'<div class="ksp7-method" style="margin-top:9px">Source: {escape(source)} • descriptive context only.</div>'
        '</div></details>'
    )


def _advanced_html(analytics: dict[str, Any]) -> str:
    q = analytics.get("margin_quantiles") or {}
    p25, p75 = _num(q.get("p25")), _num(q.get("p75"))
    p05, p95 = _num(q.get("p05")), _num(q.get("p95"))
    middle = f"{_margin(p25)} to {_margin(p75)}" if math.isfinite(p25) and math.isfinite(p75) else "—"
    wide = f"{_margin(p05)} to {_margin(p95)}" if math.isfinite(p05) and math.isfinite(p95) else "—"
    mc = _num(analytics.get("away_cover_mc_se"))
    mc_text = f"±{mc * 100:.3f} pp" if math.isfinite(mc) else "—"
    return (
        '<details class="ksp7-detail ksp7-detail-wide"><summary>ADVANCED MODEL DETAILS '
        '<span class="ksp7-detail-note">TECHNICAL</span></summary><div class="ksp7-detail-body"><div class="ksp7-row3">'
        f'<div class="ksp7-metric"><span>Predictive SD</span><b>{escape(_margin(analytics.get("predictive_sd")))}</b></div>'
        f'<div class="ksp7-metric"><span>Parameter SE</span><b>{escape(_margin(analytics.get("parameter_se")))}</b></div>'
        f'<div class="ksp7-metric"><span>Residual SD</span><b>{escape(_margin(analytics.get("residual_sd")))}</b></div>'
        f'<div class="ksp7-metric"><span>Cover MC SE</span><b>{escape(mc_text)}</b></div>'
        f'<div class="ksp7-metric"><span>Raw middle 50%</span><b>{escape(middle)}</b></div>'
        f'<div class="ksp7-metric"><span>Raw 90% range</span><b>{escape(wide)}</b></div>'
        '</div></div></details>'
    )


def _replace_section(html: str, heading: str, replacement: str) -> str:
    marker = f'<section class="ksp7-section"><h3>{heading}</h3>'
    start = html.find(marker)
    if start < 0:
        return html
    end = html.find('</section>', start)
    if end < 0:
        return html
    return html[:start] + replacement + html[end + len('</section>'):]


def render_matchup_card(
    game: dict[str, Any],
    market: dict[str, Any],
    analytics: dict[str, Any],
    *,
    book: dict[str, Any] | None = None,
    history: dict[str, Any] | None = None,
) -> str:
    book = dict(book or {})
    html = frozen.render_matchup_card(game, market, analytics, book=book)
    html = _replace_section(html, "PROJECTION RANGE", _projection_html(game, market, analytics, book))
    html = re.sub(r'Parameter uncertainty:.*?<br>', '', html, count=1)
    verification = '<details class="ksp7-detail ksp7-detail-wide"><summary>MODEL VERIFICATION'
    history_block = _history_html(dict(history or {}))
    at = html.find(verification)
    if at >= 0:
        html = html[:at] + history_block + html[at:]
    else:
        html = html.replace('</article>', history_block + '</article>', 1)
    html = html.replace('</article>', _advanced_html(analytics) + '</article>', 1)
    return html


__all__ = [
    "CSS", "FROZEN_PRIOR", "PRESENTATION_ONLY", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "render_matchup_card",
]
