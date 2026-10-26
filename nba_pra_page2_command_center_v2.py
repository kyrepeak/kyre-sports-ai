'''NBA PRA Page 2 final S-tier presentation polish V2.

Presentation-only successor over the frozen V1 command center. No I/O, no
provider access, no projection math, and no sportsbook-shaped projection logic.
'''
from __future__ import annotations

from html import escape
from statistics import mean
from typing import Any, Mapping

import nba_pra_page2_command_center_v1 as _v1
from nba_pra_page2_insights_v1 import build_nba_pra_insights


VERSION = "API2_NBA_PRA_PAGE2_S_TIER_POLISH_V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    return _v1._num(value)


def _fmt(value: Any, digits: int = 1, missing: str = "—") -> str:
    return _v1._fmt(value, digits, missing)


def _side_probability(result: Mapping[str, Any]) -> float | None:
    return _v1._side_probability(result)


def _probability_text(result: Mapping[str, Any]) -> str:
    return _v1._probability_text(result)


def _verified_games(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _v1._verified_games(profile)


def _display_form(model: Mapping[str, Any]) -> Mapping[str, Any]:
    return _v1._display_form(model)


def _hero_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    active_line: float | None,
) -> str:
    html = _v1._hero_html(context, model, result, matchup, active_line)
    availability = _text(context.get("availability")) or "UNVERIFIED"
    if availability.upper() in _v1._UNVERIFIED:
        old = f'<span class="p2cc-pill">{escape(availability)}</span>'
        new = '<span class="p2cc-pill p2cc-status-limited">LIMITED VERIFIED CONTEXT</span>'
        html = html.replace(old, new, 1)
    return html


def _hit_summary(games: list[dict[str, Any]], active_line: float | None, lean: str) -> tuple[int, int]:
    line = _num(active_line)
    side = lean.upper()
    if line is None or side not in {"OVER", "UNDER"}:
        return 0, 0
    decided = [row for row in games if _num(row.get("pra")) is not None and float(row["pra"]) != line]
    if side == "OVER":
        hits = sum(1 for row in decided if float(row["pra"]) > line)
    else:
        hits = sum(1 for row in decided if float(row["pra"]) < line)
    return hits, len(decided)


def _primary_caution(context: Mapping[str, Any], model: Mapping[str, Any]) -> str:
    form = _display_form(model)
    sample = int(form.get("sample") or 0)
    if 0 < sample < 5:
        return f"SMALL SAMPLE: {sample} GAMES"
    status = _text(context.get("availability")).upper()
    if status in _v1._UNVERIFIED:
        return "INJURY / AVAILABILITY IMPACT NOT VERIFIED"
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    if _num(profile.get("usage_pct")) is None:
        return "USAGE / ROLE IMPACT NOT VERIFIED"
    return "NO VERIFIED ELEVATED RISK FLAG"


def _decision_factors_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    active_line: float | None,
    games: list[dict[str, Any]],
) -> str:
    lean = _text(result.get("lean")).upper() or "PASS"
    edge = _num(result.get("edge"))
    supports: list[str] = []
    if edge is not None and ((lean == "OVER" and edge > 0) or (lean == "UNDER" and edge < 0)):
        supports.append(f"{edge:+.1f} PRA EDGE")
    hits, total = _hit_summary(games, active_line, lean)
    if total:
        supports.append(f"{hits}/{total} {lean}")
    grade = _text(matchup.get("matchup_grade")).upper()
    if grade:
        supports.append(f"{grade} PRA MATCHUP")
    probability = _side_probability(result)
    if probability is not None and lean in {"OVER", "UNDER"}:
        supports.append(f"{probability * 100:.0f}% {lean} MODEL SIDE")
    if not supports:
        supports.append("NO VERIFIED SUPPORT SIGNAL BEYOND THE FROZEN MODEL")

    cautions = [_primary_caution(context, model)]
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    if _num(profile.get("usage_pct")) is None:
        cautions.append("USAGE / TEAM ROLE NOT VERIFIED")
    status = _text(context.get("availability")).upper()
    if status in _v1._UNVERIFIED:
        cautions.append("INJURY / TEAMMATE IMPACT NOT VERIFIED")

    support_html = ''.join(f'<span>{escape(item)}</span>' for item in supports)
    caution_html = ''.join(f'<span>{escape(item)}</span>' for item in dict.fromkeys(cautions))
    return f'''
<section class="p2cc-decision-factors" data-ks-section="decision-factors">
  <div class="p2cc-factor p2cc-factor-positive"><small>WHY THIS PICK WORKS</small><div>{support_html}</div></div>
  <div class="p2cc-factor p2cc-factor-caution"><small>WHAT COULD BREAK IT</small><div>{caution_html}</div></div>
</section>'''


def _quick_read_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    games: list[dict[str, Any]],
) -> str:
    chips: list[str] = []
    recent = games[:5]
    if recent:
        avg = mean(float(row["pra"]) for row in recent)
        chips.append(f"{avg:.1f} PRA AVG")
    lean = _text(result.get("lean")).upper()
    probability = _side_probability(result)
    if probability is not None and lean in {"OVER", "UNDER"}:
        chips.append(f"{probability * 100:.0f}% {lean}")
    edge = _num(result.get("edge"))
    if edge is not None:
        chips.append(f"{edge:+.1f} EDGE")
    pra_rank = matchup.get("pra_rank")
    grade = _text(matchup.get("matchup_grade")).upper()
    if pra_rank is not None:
        chips.append(f"#{pra_rank} PRA MATCHUP" + (f" • {grade}" if grade else ""))
    if not chips:
        return ""
    return '<div class="p2cc-quick-read"><b>QUICK READ</b>' + ''.join(f'<span>{escape(item)}</span>' for item in chips) + '</div>'


def _insights_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    active_line: float | None,
    games: list[dict[str, Any]],
) -> str:
    report = build_nba_pra_insights(context, model, result, matchup, active_line=active_line)
    cards: list[str] = []
    for row in list(report.get("sections") or []):
        if not isinstance(row, Mapping):
            continue
        title = _text(row.get("title"))
        body = _text(row.get("body"))
        if title and body:
            cards.append(f'<article class="p2cc-insight"><h3>{escape(title)}</h3><p>{escape(body)}</p></article>')
    evidence = int(report.get("evidence_count") or len(cards))
    final_title = _text(report.get("final_title")) or "KYRE FINAL INSIGHT"
    final_body = _text(report.get("final_body")) or "Verified evidence is currently limited."
    lean = _text(result.get("lean")).upper() or "PASS"
    edge = _num(result.get("edge"))
    probability = _side_probability(result)
    primary_edge = "Frozen model edge not currently quantified"
    if edge is not None:
        primary_edge = f"{edge:+.1f} PRA EDGE"
        if probability is not None and lean in {"OVER", "UNDER"}:
            primary_edge += f" • {probability * 100:.0f}% {lean}"
    caution = _primary_caution(context, model)
    return f'''
<section class="p2cc-panel" data-ks-section="insights">
  <div class="p2cc-panel-head"><div><div class="p2cc-section-kicker">KYRE INSIGHTS</div><p>Verified evidence explaining the frozen projection — not a second projection.</p></div><span class="p2cc-badge">{evidence} VERIFIED EVIDENCE SECTIONS</span></div>
  {_quick_read_html(context, model, result, matchup, games)}
  <div class="p2cc-insight-grid">{"".join(cards) if cards else '<div class="p2cc-empty">No additional verified insight sections are currently available.</div>'}</div>
  <article class="p2cc-final-insight">
    <small class="p2cc-analyst-label">ANALYST SUMMARY</small><h2>{escape(final_title)}</h2>
    <div class="p2cc-final-meta"><div><small>PRIMARY EDGE</small><b>{escape(primary_edge)}</b></div><div><small>PRIMARY CAUTION</small><b>{escape(caution)}</b></div></div>
    <p>{escape(final_body)}</p>
  </article>
</section>'''


def _recent_performance_html(
    games: list[dict[str, Any]],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    active_line: float | None,
) -> str:
    base = _v1._recent_performance_html(games, active_line)
    form = _display_form(model)
    lean = _text(result.get("lean")).upper() or "OVER"
    hits, total = _hit_summary(games, active_line, lean)
    sample = int(form.get("sample") or len(games))
    metrics = f'''
<div class="p2cc-recent-summary">
  <div><small>L5 PRA</small><b>{_fmt(form.get("l5"))}</b></div>
  <div><small>HIT RATE</small><b>{hits}/{total if total else 0} {escape(lean)}</b></div>
  <div><small>RECENT MIN</small><b>{_fmt(form.get("minutes"))}</b></div>
  <div><small>SAMPLE</small><b>{sample} GAME{"S" if sample != 1 else ""}</b></div>
</div>'''
    return base.replace('</section>', metrics + '</section>', 1)


def _market_summary(context: Mapping[str, Any]) -> str:
    quotes = [dict(row) for row in list(context.get("quotes") or []) if isinstance(row, Mapping)]
    if not quotes and _v1._quote(context):
        quotes = [dict(_v1._quote(context))]
    if not quotes:
        return ""
    count = len(quotes)
    cells = [f'<span><small>MARKET COVERAGE</small><b>{count} VERIFIED BOOK{"S" if count != 1 else ""}</b></span>']
    lines = [_num(row.get("line")) for row in quotes]
    same_line = all(value is not None and abs(float(value) - float(lines[0])) < 1e-9 for value in lines) if lines and lines[0] is not None else False
    if count > 1 and same_line:
        over_rows = [(row, _num(row.get("over_price"))) for row in quotes]
        over_rows = [(row, price) for row, price in over_rows if price is not None]
        under_rows = [(row, _num(row.get("under_price"))) for row in quotes]
        under_rows = [(row, price) for row, price in under_rows if price is not None]
        if over_rows:
            row, price = max(over_rows, key=lambda pair: float(pair[1]))
            cells.append(f'<span><small>BEST OVER PRICE</small><b>{escape(_text(row.get("sportsbook")))} {_v1._price(price)}</b></span>')
        if under_rows:
            row, price = max(under_rows, key=lambda pair: float(pair[1]))
            cells.append(f'<span><small>BEST UNDER PRICE</small><b>{escape(_text(row.get("sportsbook")))} {_v1._price(price)}</b></span>')
    elif count > 1:
        cells.append('<span><small>LINE STATE</small><b>INDEPENDENT VERIFIED LINES</b></span>')
    return '<div class="p2cc-market-summary">' + ''.join(cells) + '</div>'


def _market_html(context: Mapping[str, Any]) -> str:
    base = _v1._market_html(context)
    summary = _market_summary(context)
    marker = '<div class="p2cc-section-kicker">MARKET INTELLIGENCE</div>'
    if marker in base and summary:
        return base.replace(marker, marker + summary, 1)
    return base


def build_page2_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    games = _verified_games(profile)
    opponent = _text(context.get("opponent")) or "Opponent not verified"
    return "\n".join(
        (
            '<div id="ks-nba-pra-page2-top"></div>',
            _hero_html(context, model, line_result, matchup, active_line),
            _v1._distribution_html(context, model, active_line),
            _decision_factors_html(context, model, line_result, matchup, active_line, games),
            _insights_html(context, model, line_result, matchup, active_line, games),
            _recent_performance_html(games, model, line_result, active_line),
            _v1._composition_html(games),
            _v1._matchup_html(matchup, opponent),
            _market_html(context),
            _v1._role_availability_html(context, games),
            _v1._risk_html(context, model, matchup),
            _v1._game_log_html(games, active_line),
        )
    )


def _css() -> str:
    base = _v1._css()
    extra = r'''
/* p2cc-line-lab-polish: Page 2-only Streamlit threshold-control integration */
[data-testid="stMainBlockContainer"]{padding-top:1.15rem!important}
div[data-testid="stSlider"]{padding:12px 14px 15px!important;border:1px solid rgba(105,221,255,.18);border-radius:16px;background:linear-gradient(145deg,rgba(7,23,40,.76),rgba(5,14,25,.72));box-shadow:0 12px 28px rgba(0,0,0,.12);margin-bottom:4px}
.p2cc-status-limited{color:#9eb7c8;background:#0b1d2c;border-color:rgba(151,183,205,.24)}
.p2cc-decision-factors{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}.p2cc-factor{padding:13px 15px;border-radius:16px;border:1px solid rgba(109,215,255,.16);background:#071522}.p2cc-factor small{display:block;font-size:10px;font-weight:900;letter-spacing:.11em;margin-bottom:8px}.p2cc-factor div{display:flex;gap:7px;flex-wrap:wrap}.p2cc-factor span{padding:6px 9px;border-radius:999px;font-size:10px;font-weight:900}.p2cc-factor-positive small{color:#63e9b1}.p2cc-factor-positive span{background:#082b23;color:#68eeb8;border:1px solid rgba(84,228,169,.20)}.p2cc-factor-caution small{color:#ffd174}.p2cc-factor-caution span{background:#2b210c;color:#ffd174;border:1px solid rgba(255,194,85,.20)}
.p2cc-quick-read{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:9px 11px;margin:-2px 0 11px;border-radius:12px;background:#071724;border:1px solid rgba(109,215,255,.12)}.p2cc-quick-read>b{font-size:9px;letter-spacing:.11em;color:#8ba6b9;margin-right:2px}.p2cc-quick-read>span{padding:5px 8px;border-radius:999px;background:#0b2538;color:#b9efff;font-size:10px;font-weight:900}.p2cc-analyst-label{display:block;color:#70e4ff;font-size:9px;font-weight:900;letter-spacing:.14em;margin-bottom:5px}.p2cc-final-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0 12px}.p2cc-final-meta>div{padding:10px 11px;border-radius:11px;background:rgba(5,20,34,.52);border:1px solid rgba(112,226,255,.13)}.p2cc-final-meta small{display:block;color:#839daf;font-size:9px;font-weight:900}.p2cc-final-meta b{display:block;margin-top:4px;color:#e4f5ff;font-size:11px}
.p2cc-recent-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.p2cc-recent-summary>div{padding:10px 11px;border-radius:11px;background:#081b2b;border:1px solid rgba(109,215,255,.13)}.p2cc-recent-summary small,.p2cc-market-summary small{display:block;color:#819bad;font-size:9px;font-weight:900}.p2cc-recent-summary b,.p2cc-market-summary b{display:block;margin-top:3px;color:#e2f3fc;font-size:14px}.p2cc-market-summary{display:flex;gap:8px;flex-wrap:wrap;margin:-2px 0 12px}.p2cc-market-summary>span{min-width:150px;padding:9px 11px;border-radius:11px;background:#071a2a;border:1px solid rgba(109,215,255,.13)}
@media(max-width:760px){[data-testid="stMainBlockContainer"]{padding-top:.65rem!important}div[data-testid="stSlider"]{padding:10px 10px 12px!important}.p2cc-decision-factors,.p2cc-final-meta{grid-template-columns:1fr}.p2cc-recent-summary{grid-template-columns:repeat(2,1fr)}.p2cc-market-summary{display:grid;grid-template-columns:1fr}.p2cc-market-summary>span{min-width:0}}
'''
    return base.replace('</style>', extra + '</style>')


__all__ = ["VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "build_page2_html", "_css"]
