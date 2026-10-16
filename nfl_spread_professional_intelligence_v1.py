"""NFL Spread Professional Intelligence V1 — presentation-only matchup renderer."""
from __future__ import annotations

from html import escape
import math
from typing import Any

PRESENTATION_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
MODEL_FEATURE_FAMILY = (
    "Strength gap",
    "Scoring interaction gap",
    "Recent L6 margin gap",
    "Site context",
)

CSS = r"""
<style>
.ksp7-card{border:1px solid rgba(86,194,255,.28);border-radius:22px;padding:20px;margin:16px 0;background:linear-gradient(180deg,#071827 0%,#07131f 100%);box-shadow:0 14px 36px rgba(0,0,0,.18);color:#eaf5ff}
.ksp7-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;border-bottom:1px solid rgba(109,200,255,.16);padding-bottom:15px}.ksp7-phase{font-size:12px;font-weight:900;letter-spacing:.08em;color:#63efbd;text-transform:uppercase}.ksp7-title{font-size:24px;font-weight:850;line-height:1.18;margin-top:7px}.ksp7-meta{font-size:13px;color:#8fa8bc;margin-top:8px;line-height:1.55}.ksp7-badges{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.ksp7-badge{font-size:11px;font-weight:800;padding:7px 10px;border:1px solid rgba(86,194,255,.3);border-radius:999px;color:#a9ddff}.ksp7-badge.good{border-color:rgba(61,232,173,.48);color:#78efc2}.ksp7-badge.warn{border-color:rgba(247,198,89,.48);color:#f7cf72}
.ksp7-verdict{margin-top:16px;border:1px solid rgba(61,232,173,.46);border-radius:18px;padding:17px;background:linear-gradient(135deg,rgba(10,55,56,.5),rgba(8,29,43,.9))}.ksp7-kicker{font-size:11px;font-weight:900;letter-spacing:.08em;color:#7fa0b8;text-transform:uppercase}.ksp7-lean{font-size:27px;font-weight:900;margin-top:5px;color:#7af0c4}.ksp7-explain{font-size:14px;color:#c6d6e2;margin-top:6px;line-height:1.5}.ksp7-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:13px}.ksp7-tile{padding:12px;border-radius:13px;border:1px solid rgba(86,194,255,.18);background:#071521}.ksp7-tile span{display:block;font-size:10px;font-weight:850;letter-spacing:.06em;color:#7994a8;text-transform:uppercase}.ksp7-tile b{display:block;font-size:18px;margin-top:6px}.ksp7-tile.hero b{color:#78efc2}
.ksp7-section{margin-top:15px;border:1px solid rgba(86,194,255,.18);border-radius:17px;padding:15px;background:rgba(5,17,27,.72)}.ksp7-section h3{font-size:12px;letter-spacing:.075em;text-transform:uppercase;margin:0 0 12px;color:#9ab6ca}.ksp7-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ksp7-team{border:1px solid rgba(86,194,255,.16);border-radius:14px;padding:13px}.ksp7-team-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.ksp7-team-name{font-weight:850}.ksp7-team-rec{font-size:11px;color:#748da1}.ksp7-mini{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.ksp7-mini div{padding:9px;border-radius:10px;background:#081927}.ksp7-mini span{display:block;font-size:9px;color:#718ca0;text-transform:uppercase;font-weight:800}.ksp7-mini b{display:block;margin-top:4px;font-size:14px}.ksp7-row3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.ksp7-metric{padding:11px;border-radius:12px;background:#081927;border:1px solid rgba(86,194,255,.12)}.ksp7-metric span{display:block;font-size:9px;color:#7894a8;font-weight:850;text-transform:uppercase}.ksp7-metric b{display:block;font-size:16px;margin-top:5px}.ksp7-cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ksp7-list{border-radius:12px;background:#071722;padding:12px}.ksp7-list h4{font-size:11px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.06em}.ksp7-item{font-size:12px;color:#c7d6e0;padding:8px 0;border-top:1px solid rgba(255,255,255,.07);line-height:1.45}.ksp7-item:first-of-type{border-top:0}.ksp7-method{font-size:12px;color:#8da6b8;line-height:1.55}.ksp7-method strong{color:#c8dce9}.ksp7-gated{padding:14px;border-radius:12px;background:rgba(94,24,30,.2);color:#f0b8bc}.ksp7-edge{color:#78efc2!important}
@media(max-width:720px){.ksp7-card{padding:14px;border-radius:18px}.ksp7-title{font-size:21px}.ksp7-grid{grid-template-columns:1fr 1fr}.ksp7-compare,.ksp7-cols{grid-template-columns:1fr}.ksp7-row3{grid-template-columns:1fr 1fr}.ksp7-lean{font-size:23px}}
</style>
"""


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except (TypeError, ValueError, OverflowError):
        return math.nan


def _pct(value: Any, digits: int = 1) -> str:
    n = _num(value)
    return f"{n * 100:.{digits}f}%" if math.isfinite(n) else "—"


def _line(value: Any) -> str:
    n = _num(value)
    if not math.isfinite(n):
        return "—"
    if abs(n) < 0.05:
        return "PK"
    return f"{n:+.1f}"


def _price(value: Any) -> str:
    n = _num(value)
    if not math.isfinite(n):
        return "—"
    return f"{int(round(n)):+d}"


def _margin(value: Any) -> str:
    n = _num(value)
    return f"{n:+.1f}" if math.isfinite(n) else "—"


def _nickname(team: str) -> str:
    bits = _safe(team, "Team").split()
    return bits[-1] if bits else "Team"


def _fair_lines(analytics: dict[str, Any]) -> tuple[float, float]:
    away_margin = _num(analytics.get("projected_away_margin"))
    if not math.isfinite(away_margin):
        return math.nan, math.nan
    return -away_margin, away_margin


def _side_values(analytics: dict[str, Any], side: str) -> tuple[float, float, float]:
    away_win = _num(analytics.get("away_win_probability"))
    away_cover = _num(analytics.get("away_cover_probability"))
    home_cover = _num(analytics.get("home_cover_probability"))
    away_med = _num(analytics.get("simulated_away_margin_median"))
    if side == "away":
        return away_win, away_cover, away_med
    home_win = _num(analytics.get("home_win_probability"))
    if not math.isfinite(home_win) and math.isfinite(away_win):
        home_win = 1.0 - away_win - max(_num(analytics.get("tie_probability")), 0.0)
    return home_win, home_cover, -away_med if math.isfinite(away_med) else math.nan


def _confidence(cover: float, edge: float, quality: str) -> str:
    if not (math.isfinite(cover) and math.isfinite(edge)):
        return "CHECK"
    if quality == "HIGH" and cover >= 0.575 and edge >= 2.5:
        return "STRONG"
    if cover >= 0.535 and edge >= 1.0:
        return "MODERATE"
    return "THIN"


def _range_for_side(analytics: dict[str, Any], side: str, lo_key: str, hi_key: str) -> tuple[float, float]:
    q = analytics.get("margin_quantiles") or {}
    lo = _num(q.get(lo_key))
    hi = _num(q.get(hi_key))
    if side == "away":
        return lo, hi
    return (-hi if math.isfinite(hi) else math.nan, -lo if math.isfinite(lo) else math.nan)


def _team_block(team: str, abbr: str, record: str, market_line: Any, fair_line: Any, cover: Any, win: Any, price: Any) -> str:
    return f'''<div class="ksp7-team"><div class="ksp7-team-head"><div><div class="ksp7-team-name">{escape(team)}</div><div class="ksp7-team-rec">{escape(abbr)} • {escape(record)}</div></div><b>{escape(_line(market_line))}</b></div><div class="ksp7-mini"><div><span>Market</span><b>{escape(_line(market_line))} <small>{escape(_price(price))}</small></b></div><div><span>Fair line</span><b>{escape(_line(fair_line))}</b></div><div><span>Cover</span><b>{escape(_pct(cover))}</b></div><div><span>Win</span><b>{escape(_pct(win))}</b></div></div></div>'''


def render_matchup_card(
    game: dict[str, Any],
    market: dict[str, Any],
    analytics: dict[str, Any],
    *,
    book: dict[str, Any] | None = None,
) -> str:
    """Render a compact decision-first card from already-certified inputs only."""
    book = dict(book or {})
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    away_abbr = _safe(game.get("away_abbr"), "AWAY").upper()
    home_abbr = _safe(game.get("home_abbr"), "HOME").upper()
    away_record = _safe(game.get("away_record"), "—")
    home_record = _safe(game.get("home_record"), "—")
    phase = _safe(game.get("season_type"), "NFL")
    tip = _safe(game.get("tip_et"), "TBD")
    venue = _safe(game.get("venue"), "Venue TBD")
    broadcast = _safe(game.get("broadcast"), "—")
    event_id = _safe(game.get("game_id"))

    ready = bool(analytics.get("ready"))
    market_ready = bool(market.get("ready")) and bool(book)
    quality = _safe(analytics.get("model_quality"), "CHECK").upper() if ready else "GATED"
    sims = int(_num(analytics.get("simulations"))) if math.isfinite(_num(analytics.get("simulations"))) else 0
    certified = bool(analytics.get("certified_run"))
    converged = bool(analytics.get("converged"))

    fair_away, fair_home = _fair_lines(analytics)
    market_away = _num(book.get("away_spread")) if market_ready else math.nan
    market_home = _num(book.get("home_spread")) if market_ready else math.nan
    away_edge = market_away - fair_away if math.isfinite(market_away) and math.isfinite(fair_away) else math.nan
    home_edge = market_home - fair_home if math.isfinite(market_home) and math.isfinite(fair_home) else math.nan

    if market_ready and math.isfinite(away_edge) and math.isfinite(home_edge):
        side = "away" if away_edge >= home_edge else "home"
        edge = away_edge if side == "away" else home_edge
    else:
        away_win = _num(analytics.get("away_win_probability"))
        home_win = _num(analytics.get("home_win_probability"))
        side = "away" if away_win >= home_win else "home"
        edge = math.nan

    lean_team = away if side == "away" else home
    lean_nick = _nickname(lean_team)
    lean_market = market_away if side == "away" else market_home
    lean_fair = fair_away if side == "away" else fair_home
    win, cover, med = _side_values(analytics, side)
    confidence = _confidence(cover, edge, quality)
    p25, p75 = _range_for_side(analytics, side, "p25", "p75")
    p05, p95 = _range_for_side(analytics, side, "p05", "p95")
    predictive_sd = _num(analytics.get("predictive_sd"))
    parameter_se = _num(analytics.get("parameter_se"))
    residual_sd = _num(analytics.get("residual_sd"))
    push = _num(analytics.get("push_probability"))
    non_win = 1.0 - win if math.isfinite(win) else math.nan
    range_width = p75 - p25 if math.isfinite(p25) and math.isfinite(p75) else math.nan
    sportsbook = _safe(book.get("sportsbook"), "FanDuel") if market_ready else "Market"

    if not ready:
        reason = _safe(analytics.get("error"), "Independent analytics unavailable.")
        verdict = f'<div class="ksp7-verdict"><div class="ksp7-kicker">MODEL VERDICT</div><div class="ksp7-lean">GATED</div><div class="ksp7-gated">{escape(reason)}</div></div>'
    else:
        lean_label = f"{lean_nick} {_line(lean_market)}" if market_ready else f"{lean_nick} • MODEL FAVORITE"
        explain = (
            f"Fair line {lean_nick} {_line(lean_fair)} vs {sportsbook} {_line(lean_market)} → model edge {_line(edge)} pts."
            if market_ready and math.isfinite(edge)
            else "Market unavailable — showing the football-only model favorite without fabricating a betting edge."
        )
        verdict = f'''<div class="ksp7-verdict"><div class="ksp7-kicker">MODEL VERDICT</div><div class="ksp7-lean">{escape(lean_label)}</div><div class="ksp7-explain">{escape(explain)}</div><div class="ksp7-grid"><div class="ksp7-tile hero"><span>Cover probability</span><b>{escape(_pct(cover))}</b></div><div class="ksp7-tile"><span>Win probability</span><b>{escape(_pct(win))}</b></div><div class="ksp7-tile"><span>Median margin</span><b>{escape(lean_nick)} {escape(_margin(med))}</b></div><div class="ksp7-tile"><span>Signal confidence</span><b>{escape(confidence)}</b></div></div></div>'''

    away_win, away_cover, _ = _side_values(analytics, "away")
    home_win, home_cover, _ = _side_values(analytics, "home")
    compare = _team_block(away, away_abbr, away_record, market_away, fair_away, away_cover, away_win, book.get("away_price")) + _team_block(home, home_abbr, home_record, market_home, fair_home, home_cover, home_win, book.get("home_price"))

    edge_text = f"{edge:+.1f} pts" if math.isfinite(edge) else "—"
    market_text = f"{lean_nick} {_line(lean_market)}" if market_ready else "MARKET UNAVAILABLE"
    fair_text = f"{lean_nick} {_line(lean_fair)}" if math.isfinite(lean_fair) else "—"
    p25p75 = f"{_margin(p25)} to {_margin(p75)}" if math.isfinite(p25) and math.isfinite(p75) else "—"
    p05p95 = f"{_margin(p05)} to {_margin(p95)}" if math.isfinite(p05) and math.isfinite(p95) else "—"

    supports = [
        f"Fair-line gap: the football-only fair line is {abs(edge):.1f} points stronger on {lean_nick}." if math.isfinite(edge) else "Market comparison is unavailable, so no edge is asserted.",
        f"Cover signal: {_pct(cover)} of certified simulations finish on the {lean_nick} side of the current spread." if market_ready else "Cover probability is gated until a certified market line is attached.",
        f"Win signal: {_pct(win)} outright win probability with a median simulated margin of {_margin(med)}.",
        f"Model quality is {quality}; sportsbook projection influence remains 0.0%.",
    ]
    risks = [
        f"Game-to-game residual uncertainty is {residual_sd:.2f} points SD." if math.isfinite(residual_sd) else "Residual uncertainty is unavailable.",
        f"Middle 50% outcome range spans {range_width:.1f} points ({p25p75})." if math.isfinite(range_width) else "Middle-50% outcome range is unavailable.",
        f"Non-win risk remains {_pct(non_win)}; this is a probabilistic projection, not a guarantee.",
        f"Push probability at the current line is {_pct(push)}." if market_ready else "Push probability is unavailable without a certified spread.",
    ]
    support_html = "".join(f'<div class="ksp7-item">{escape(x)}</div>' for x in supports)
    risk_html = "".join(f'<div class="ksp7-item">{escape(x)}</div>' for x in risks)
    features = " • ".join(MODEL_FEATURE_FAMILY)
    sim_status = "5M CERTIFIED" if certified else ("CONVERGED" if converged else "CHECK")
    mc_se = _num(analytics.get("away_cover_mc_se"))
    mc_se_text = f"±{mc_se * 100:.3f} pp" if math.isfinite(mc_se) else "—"

    html = f'''
    <article class="ksp7-card" data-spread-v7="true" data-event-id="{escape(event_id, quote=True)}">
      <div class="ksp7-top"><div><div class="ksp7-phase">{escape(phase)}</div><div class="ksp7-title">{escape(away)} <span style="color:#6f8799">@</span> {escape(home)}</div><div class="ksp7-meta">🕒 {escape(tip)} &nbsp;•&nbsp; 🏟️ {escape(venue)} &nbsp;•&nbsp; 📺 {escape(broadcast)}</div><div class="ksp7-badges"><span class="ksp7-badge {'good' if market_ready else 'warn'}">{'MARKET READY' if market_ready else 'MARKET UNAVAILABLE'}</span><span class="ksp7-badge good">MODEL {escape(quality)}</span><span class="ksp7-badge good">{escape(sim_status)}</span><span class="ksp7-badge">EXACT ID</span></div></div></div>
      {verdict}
      <section class="ksp7-section"><h3>TEAM COMPARISON</h3><div class="ksp7-compare">{compare}</div></section>
      <section class="ksp7-section"><h3>MARKET VS MODEL</h3><div class="ksp7-row3"><div class="ksp7-metric"><span>Current market</span><b>{escape(market_text)}</b></div><div class="ksp7-metric"><span>Model fair line</span><b>{escape(fair_text)}</b></div><div class="ksp7-metric"><span>MODEL EDGE</span><b class="ksp7-edge">{escape(edge_text)}</b></div></div></section>
      <section class="ksp7-section"><h3>PROJECTION RANGE</h3><div class="ksp7-row3"><div class="ksp7-metric"><span>Middle 50%</span><b>{escape(p25p75)}</b></div><div class="ksp7-metric"><span>90% range</span><b>{escape(p05p95)}</b></div><div class="ksp7-metric"><span>Predictive SD</span><b>{escape(_margin(predictive_sd))}</b></div><div class="ksp7-metric"><span>Parameter SE</span><b>{escape(_margin(parameter_se))}</b></div><div class="ksp7-metric"><span>Non-win risk</span><b>{escape(_pct(non_win))}</b></div><div class="ksp7-metric"><span>Push</span><b>{escape(_pct(push) if market_ready else '—')}</b></div></div></section>
      <section class="ksp7-section"><div class="ksp7-cols"><div class="ksp7-list"><h4>WHY THE MODEL LEANS</h4>{support_html}</div><div class="ksp7-list"><h4>RISK / COUNTERWEIGHTS</h4>{risk_html}</div></div></section>
      <section class="ksp7-section"><h3>MODEL VERIFICATION</h3><div class="ksp7-method"><strong>{sims:,} simulations • {escape(sim_status)}</strong><br>Football-only feature family: {escape(features)}.<br>Parameter uncertainty: {_margin(parameter_se)} pts • residual uncertainty: {_margin(residual_sd)} pts • cover MC SE: {escape(mc_se_text)}.<br>Sportsbook line is comparison/settlement context only. <strong>Sportsbook influence on projection math: 0.0%</strong></div></section>
    </article>
    '''
    return "".join(line.strip() for line in html.splitlines())


__all__ = [
    "CSS",
    "MODEL_FEATURE_FAMILY",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "render_matchup_card",
]
