'''NBA PRA Page 2 S-tier command-center presentation V1.

Pure presentation only. This module performs no I/O and no provider access.
It consumes the already-verified Page 2 context/model/result/matchup mappings
and renders visual analytics without changing projection ownership.
'''
from __future__ import annotations

from html import escape
from math import exp, pi, sqrt
from statistics import mean
from typing import Any, Mapping

from nba_pra_page2_insights_v1 import build_nba_pra_insights


VERSION = "API2_NBA_PRA_PAGE2_S_TIER_COMMAND_CENTER_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_UNVERIFIED = {"", "UNVERIFIED", "UNKNOWN", "NOT CURRENTLY VERIFIED", "NO VERIFIED INJURY FLAG"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _fmt(value: Any, digits: int = 1, missing: str = "—") -> str:
    number = _num(value)
    return missing if number is None else f"{number:.{digits}f}"


def _signed(value: Any) -> str:
    number = _num(value)
    return "—" if number is None else f"{number:+.1f}"


def _price(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _side_probability(result: Mapping[str, Any]) -> float | None:
    lean = _text(result.get("lean")).upper()
    direct = _num(result.get("under_probability" if lean == "UNDER" else "over_probability"))
    if direct is not None:
        return direct
    other = _num(result.get("over_probability" if lean == "UNDER" else "under_probability"))
    return None if other is None else 1.0 - other


def _probability_text(result: Mapping[str, Any]) -> str:
    value = _side_probability(result)
    return "—" if value is None else f"{value * 100:.0f}%"


def _display_form(model: Mapping[str, Any]) -> Mapping[str, Any]:
    current = model.get("current") if isinstance(model.get("current"), Mapping) else {}
    if int(current.get("sample") or 0) > 0:
        return current
    prior = model.get("prior") if isinstance(model.get("prior"), Mapping) else {}
    return prior if int(prior.get("sample") or 0) > 0 else current


def _verified_games(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    current = list(profile.get("current_games") or [])
    source = current if current else list(profile.get("prior_games") or [])
    rows: list[dict[str, Any]] = []
    for raw in source:
        if not isinstance(raw, Mapping):
            continue
        pts = _num(raw.get("points"))
        reb = _num(raw.get("rebounds"))
        ast = _num(raw.get("assists"))
        if pts is None or reb is None or ast is None:
            continue
        rows.append({**dict(raw), "points": pts, "rebounds": reb, "assists": ast, "pra": pts + reb + ast})
    return rows


def _exact_opponent_games(profile: Mapping[str, Any], opponent: str) -> list[dict[str, Any]]:
    target = _text(opponent).casefold()
    if not target:
        return []
    out: list[dict[str, Any]] = []
    for raw in list(profile.get("current_games") or []) + list(profile.get("prior_games") or []):
        if not isinstance(raw, Mapping) or _text(raw.get("opponent")).casefold() != target:
            continue
        pts, reb, ast = (_num(raw.get(key)) for key in ("points", "rebounds", "assists"))
        if pts is None or reb is None or ast is None:
            continue
        out.append({**dict(raw), "points": pts, "rebounds": reb, "assists": ast, "pra": pts + reb + ast})
    return out


def _quote(context: Mapping[str, Any]) -> Mapping[str, Any]:
    current = context.get("current_quote")
    if isinstance(current, Mapping):
        return current
    selected = context.get("selected_quote")
    return selected if isinstance(selected, Mapping) else {}


def _evidence_coverage(context: Mapping[str, Any], model: Mapping[str, Any], matchup: Mapping[str, Any]) -> tuple[int, int]:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    status = _text(context.get("availability")).upper()
    checks = (
        bool(_verified_games(profile)),
        _num(model.get("projection")) is not None and _num(model.get("sigma")) is not None,
        bool(list(context.get("quotes") or [])) or bool(_quote(context)),
        any(
            (isinstance(matchup.get(key), Mapping) and matchup.get(key, {}).get("rank") is not None)
            for key in ("points", "rebounds", "assists")
        ) or matchup.get("pra_rank") is not None,
        _num(profile.get("usage_pct")) is not None,
        status not in _UNVERIFIED,
    )
    return sum(1 for item in checks if item), len(checks)


def _hero_html(context: Mapping[str, Any], model: Mapping[str, Any], result: Mapping[str, Any], active_line: float | None) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    name = _text(context.get("player_name") or profile.get("player_name")) or "NBA Player"
    team = _text(context.get("team")) or "NBA"
    opponent = _text(context.get("opponent")) or "Opponent not verified"
    position = _text(profile.get("position")) or "Position not verified"
    headshot = _text(profile.get("headshot"))
    team_logo = _text(context.get("team_logo"))
    opponent_logo = _text(context.get("opponent_logo"))
    availability = _text(context.get("availability")) or "UNVERIFIED"
    quote = _quote(context)
    book = _text(quote.get("sportsbook")) or "Verified book unavailable"
    lean = _text(result.get("lean")).upper() or "PASS"
    tier = _text(result.get("tier")) or _text(result.get("confidence")) or ""
    score = _fmt(result.get("score"), 1)
    evidence, total = _evidence_coverage(context, model, {})
    face = f'<img class="p2cc-face" src="{escape(headshot)}" alt="{escape(name)}">' if headshot else '<div class="p2cc-face p2cc-face-empty">NBA</div>'
    team_img = f'<img class="p2cc-mini-logo" src="{escape(team_logo)}" alt="{escape(team)} logo">' if team_logo else ""
    opp_img = f'<img class="p2cc-mini-logo" src="{escape(opponent_logo)}" alt="{escape(opponent)} logo">' if opponent_logo else ""
    return f'''
<section class="p2cc-hero" data-ks-section="hero">
  <div class="p2cc-section-kicker">PLAYER COMMAND CENTER</div>
  <div class="p2cc-hero-grid">
    <div class="p2cc-player">{face}<div>{team_img}<h1>{escape(name)}</h1><p>{escape(team)} • {escape(position)} &nbsp;vs&nbsp; {escape(opponent)} {opp_img}</p><div class="p2cc-pill-row"><span class="p2cc-pill">{escape(availability)}</span><span class="p2cc-pill p2cc-pill-soft">{evidence}/{total} VERIFIED DATA AREAS</span></div></div></div>
    <div class="p2cc-decision">
      <div class="p2cc-decision-top"><span>KYRE DECISION</span><em>{escape(tier)}</em></div>
      <strong>{escape(lean)} {_fmt(active_line)} PRA</strong>
      <div class="p2cc-metrics">
        <div><small>PROJECTION</small><b>{_fmt(model.get("projection"))}</b></div>
        <div><small>PROBABILITY</small><b>{_probability_text(result)}</b></div>
        <div><small>EDGE</small><b>{_signed(result.get("edge"))}</b></div>
        <div><small>KYRE SCORE</small><b>{score}</b></div>
      </div>
      <div class="p2cc-bookline"><span>{escape(book)}</span><b>{_fmt(quote.get("line"))}</b><small>O {_price(quote.get("over_price"))} • U {_price(quote.get("under_price"))}</small></div>
    </div>
  </div>
</section>'''


def _distribution_html(context: Mapping[str, Any], model: Mapping[str, Any], active_line: float | None) -> str:
    projection = _num(model.get("projection"))
    sigma = _num(model.get("sigma"))
    quote = _quote(context)
    book_line = _num(quote.get("line"))
    marker_line = book_line if book_line is not None else _num(active_line)
    if projection is None or sigma is None or sigma <= 0:
        return '''<section class="p2cc-panel" data-ks-section="distribution"><div class="p2cc-section-kicker">PROJECTION DISTRIBUTION</div><div class="p2cc-empty">Projection distribution unavailable — verified model sigma is not available.</div></section>'''
    x_min = max(0.0, min(projection, marker_line if marker_line is not None else projection) - 3.0 * sigma)
    x_max = max(projection, marker_line if marker_line is not None else projection) + 3.0 * sigma
    if x_max <= x_min:
        x_max = x_min + 1.0
    width, height = 760.0, 210.0
    left, right, top, bottom = 34.0, 18.0, 18.0, 38.0
    plot_w, plot_h = width - left - right, height - top - bottom

    def sx(value: float) -> float:
        return left + ((value - x_min) / (x_max - x_min)) * plot_w

    def pdf(value: float) -> float:
        z = (value - projection) / sigma
        return exp(-0.5 * z * z) / (sigma * sqrt(2.0 * pi))

    samples = [x_min + (x_max - x_min) * i / 60.0 for i in range(61)]
    ymax = max(pdf(value) for value in samples) or 1.0
    points = [(sx(value), top + (1.0 - pdf(value) / ymax) * plot_h) for value in samples]
    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area_points = f"{left:.1f},{top + plot_h:.1f} " + line_points + f" {left + plot_w:.1f},{top + plot_h:.1f}"
    projection_x = sx(projection)
    marker = ""
    if marker_line is not None:
        marker_x = sx(marker_line)
        marker = f'<line class="p2cc-book-marker" x1="{marker_x:.1f}" y1="{top:.1f}" x2="{marker_x:.1f}" y2="{top + plot_h:.1f}"/><text class="p2cc-svg-label p2cc-svg-book" x="{marker_x:.1f}" y="{height - 8:.1f}" text-anchor="middle">BOOK LINE {marker_line:.1f}</text>'
    lo = projection - sigma
    hi = projection + sigma
    return f'''
<section class="p2cc-panel" data-ks-section="distribution">
  <div class="p2cc-panel-head"><div><div class="p2cc-section-kicker">PROJECTION DISTRIBUTION</div><p>Visualized from the frozen PRA projection and verified model dispersion.</p></div><span class="p2cc-badge">MODEL SIGMA {sigma:.1f}</span></div>
  <svg class="p2cc-distribution-svg" viewBox="0 0 760 210" role="img" aria-label="PRA projection distribution">
    <polygon class="p2cc-dist-area" points="{area_points}"/><polyline class="p2cc-dist-line" points="{line_points}"/>
    {marker}
    <line class="p2cc-projection-marker" x1="{projection_x:.1f}" y1="{top:.1f}" x2="{projection_x:.1f}" y2="{top + plot_h:.1f}"/>
    <text class="p2cc-svg-label p2cc-svg-projection" x="{projection_x:.1f}" y="18" text-anchor="middle">KYRE {projection:.1f}</text>
  </svg>
  <div class="p2cc-chart-meta"><span>MODEL SPREAD (±1σ) {_fmt(lo)}–{_fmt(hi)}</span><span>ACTIVE THRESHOLD {_fmt(active_line)}</span></div>
</section>'''


def _insights_html(context: Mapping[str, Any], model: Mapping[str, Any], result: Mapping[str, Any], matchup: Mapping[str, Any], active_line: float | None) -> str:
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
    return f'''
<section class="p2cc-panel" data-ks-section="insights">
  <div class="p2cc-panel-head"><div><div class="p2cc-section-kicker">KYRE INSIGHTS</div><p>Verified evidence explaining the frozen projection — not a second projection.</p></div><span class="p2cc-badge">{evidence} VERIFIED EVIDENCE SECTIONS</span></div>
  <div class="p2cc-insight-grid">{"".join(cards) if cards else '<div class="p2cc-empty">No additional verified insight sections are currently available.</div>'}</div>
  <article class="p2cc-final-insight"><h2>{escape(final_title)}</h2><p>{escape(final_body)}</p></article>
</section>'''


def _recent_performance_html(games: list[dict[str, Any]], active_line: float | None) -> str:
    if not games:
        chart = '<div class="p2cc-empty">Recent performance chart unavailable — no verified game sample.</div>'
    else:
        rows = games[:10]
        values = [float(row["pra"]) for row in rows]
        max_value = max(values + ([_num(active_line)] if _num(active_line) is not None else []))
        ymax = max(10.0, float(max_value or 10.0) * 1.2)
        width, height = 760.0, 220.0
        left, right, top, bottom = 36.0, 18.0, 20.0, 48.0
        plot_w, plot_h = width - left - right, height - top - bottom
        gap = 10.0
        bar_w = max(26.0, min(76.0, (plot_w - gap * (len(rows) - 1)) / max(1, len(rows))))
        total_w = len(rows) * bar_w + max(0, len(rows) - 1) * gap
        start_x = left + max(0.0, (plot_w - total_w) / 2.0)
        elements: list[str] = []
        for index, row in enumerate(rows):
            value = float(row["pra"])
            bar_h = (value / ymax) * plot_h
            x = start_x + index * (bar_w + gap)
            y = top + plot_h - bar_h
            date = escape(_text(row.get("game_date")) or "Verified game")
            elements.append(f'<rect class="p2cc-recent-bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="6"/><text class="p2cc-svg-value" x="{x + bar_w / 2:.1f}" y="{max(14.0, y - 7):.1f}" text-anchor="middle">{value:.1f}</text><text class="p2cc-svg-date" x="{x + bar_w / 2:.1f}" y="{height - 13:.1f}" text-anchor="middle">{date}</text>')
        line_markup = ""
        line_value = _num(active_line)
        if line_value is not None:
            line_y = top + plot_h - (line_value / ymax) * plot_h
            line_markup = f'<line class="p2cc-active-line" x1="{left}" y1="{line_y:.1f}" x2="{left + plot_w}" y2="{line_y:.1f}"/><text class="p2cc-svg-line-label" x="{left + plot_w - 4:.1f}" y="{max(13.0, line_y - 6):.1f}" text-anchor="end">ACTIVE LINE {line_value:.1f}</text>'
        chart = f'<svg class="p2cc-recent-svg" viewBox="0 0 760 220" role="img" aria-label="Recent verified PRA performance">{line_markup}{"".join(elements)}</svg>'
    return f'<section class="p2cc-panel" data-ks-section="recent"><div class="p2cc-section-kicker">RECENT PERFORMANCE</div>{chart}</section>'


def _composition_html(games: list[dict[str, Any]]) -> str:
    if not games:
        body = '<div class="p2cc-empty">Verified PRA composition unavailable — no verified game sample.</div>'
    else:
        sample = games[:10]
        pts = mean(float(row["points"]) for row in sample)
        reb = mean(float(row["rebounds"]) for row in sample)
        ast = mean(float(row["assists"]) for row in sample)
        total = pts + reb + ast
        items = []
        for label, value in (("PTS", pts), ("REB", reb), ("AST", ast)):
            share = 0.0 if total <= 0 else value / total * 100.0
            items.append(f'<div class="p2cc-component"><small>{label}</small><b>{value:.1f} {label}</b><div class="p2cc-component-track"><span style="width:{share:.1f}%"></span></div><em>{share:.0f}% of verified recent PRA</em></div>')
        body = f'<div class="p2cc-component-grid">{"".join(items)}</div><p class="p2cc-note">Verified recent-history composition across {len(sample)} game{"s" if len(sample) != 1 else ""}. This is not a component projection.</p>'
    return f'<section class="p2cc-panel" data-ks-section="composition"><div class="p2cc-section-kicker">VERIFIED PRA COMPOSITION</div>{body}</section>'


def _rank_grade_class(grade: str) -> str:
    upper = grade.upper()
    return "good" if upper == "FAVORABLE" else "bad" if upper == "TOUGH" else "mid"


def _matchup_html(matchup: Mapping[str, Any], opponent: str) -> str:
    rows: list[tuple[str, Any, str]] = []
    for key, label in (("points", "POINTS ALLOWED"), ("rebounds", "REBOUNDS ALLOWED"), ("assists", "ASSISTS ALLOWED")):
        raw = matchup.get(key) if isinstance(matchup.get(key), Mapping) else {}
        rows.append((label, raw.get("rank"), _text(raw.get("grade")) or "NOT VERIFIED"))
    rows.append(("PRA ALLOWED", matchup.get("pra_rank"), _text(matchup.get("matchup_grade")) or "NOT VERIFIED"))
    bars: list[str] = []
    for label, raw_rank, grade in rows:
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            continue
        width = max(3.0, min(100.0, rank / 30.0 * 100.0))
        bars.append(f'<div class="p2cc-rank-bar"><span>{escape(label)}</span><b>#{rank}</b><div class="p2cc-rank-track"><i style="width:{width:.1f}%"></i></div><em class="p2cc-grade-{_rank_grade_class(grade)}">{escape(grade)}</em></div>')
    semantics = escape(_text(matchup.get("rank_semantics")) or "1 = toughest/stingiest, 30 = most permissive")
    period = escape(_text(matchup.get("evidence_period")) or "Evidence period not currently verified")
    body = "".join(bars) if bars else '<div class="p2cc-empty">Verified opponent ranking detail is not currently available.</div>'
    return f'<section class="p2cc-panel" data-ks-section="matchup"><div class="p2cc-section-kicker">MATCHUP INTELLIGENCE • {escape(opponent)}</div>{body}<p class="p2cc-note">{semantics} • {period}</p></section>'


def _market_html(context: Mapping[str, Any]) -> str:
    quotes = [dict(row) for row in list(context.get("quotes") or []) if isinstance(row, Mapping)]
    if not quotes and _quote(context):
        quotes = [dict(_quote(context))]
    cards: list[str] = []
    for row in quotes:
        book = _text(row.get("sportsbook")) or "Verified book"
        cards.append(f'<article class="p2cc-market-card"><h3>{escape(book)}</h3><b>{_fmt(row.get("line"))} PRA</b><span>O {_price(row.get("over_price"))} • U {_price(row.get("under_price"))}</span><small>{escape(_text(row.get("observed_at_utc")) or "Timestamp not currently verified")}</small></article>')
    selected = context.get("selected_quote") if isinstance(context.get("selected_quote"), Mapping) else {}
    current = context.get("current_quote") if isinstance(context.get("current_quote"), Mapping) else {}
    selected_line, current_line = _num(selected.get("line")), _num(current.get("line"))
    same_book = _text(selected.get("sportsbook")).casefold() == _text(current.get("sportsbook")).casefold() and bool(_text(current.get("sportsbook")))
    if same_book and selected_line is not None and current_line is not None and abs(selected_line - current_line) > 1e-9:
        movement = f'<div class="p2cc-movement"><small>VERIFIED SAME-BOOK MOVEMENT</small><b>{selected_line:.1f} → {current_line:.1f}</b><span>{escape(_text(current.get("sportsbook")))}</span></div>'
    else:
        movement = '<div class="p2cc-movement"><small>LINE MOVEMENT</small><b>—</b><span>No verified same-book movement since selection.</span></div>'
    body = "".join(cards) if cards else '<div class="p2cc-empty">No verified sportsbook quote is currently available.</div>'
    return f'<section class="p2cc-panel" data-ks-section="market"><div class="p2cc-section-kicker">MARKET INTELLIGENCE</div><div class="p2cc-market-grid">{body}{movement}</div><p class="p2cc-note">Verified books remain independent. Conflicting lines are never averaged.</p></section>'


def _role_availability_html(context: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    team = _text(context.get("team"))
    opponent = _text(context.get("opponent"))
    cards: list[str] = []
    gaps: list[str] = []
    usage = _num(profile.get("usage_pct"))
    if usage is not None:
        rank = profile.get("usage_rank")
        rank_text = f"#{rank} ON {team}" if rank is not None and team else "TEAM RANK NOT VERIFIED"
        cards.append(f'<article class="p2cc-context-card"><small>ROLE & USAGE</small><b>{usage:.1f}%</b><span>{escape(rank_text)}</span><em>{escape(_text(profile.get("usage_period")) or "Verified usage period")}</em></article>')
    else:
        gaps.append("Usage / team role not currently verified")
    status = _text(context.get("availability")).upper()
    if status not in _UNVERIFIED:
        cards.append(f'<article class="p2cc-context-card"><small>AVAILABILITY</small><b>{escape(status)}</b><span>Verified availability state</span></article>')
    else:
        gaps.append("Player / teammate injury impact not currently verified")
    history = _exact_opponent_games(profile, opponent)
    if history:
        avg = mean(float(row["pra"]) for row in history)
        cards.append(f'<article class="p2cc-context-card"><small>PLAYER VS {escape(opponent)}</small><b>{avg:.1f} PRA</b><span>{len(history)} verified meeting{"s" if len(history) != 1 else ""}</span></article>')
    else:
        gaps.append("No verified prior matchup sample")
    if not games:
        gaps.append("Recent verified game history unavailable")
    gap_html = ''.join(f'<span>{escape(item)}</span>' for item in gaps)
    return f'<section class="p2cc-panel" data-ks-section="role"><div class="p2cc-section-kicker">ROLE & AVAILABILITY</div><div class="p2cc-context-grid">{"".join(cards)}</div>{f"<div class=\"p2cc-data-gaps\"><b>DATA GAPS</b>{gap_html}</div>" if gaps else ""}</section>'


def _risk_html(context: Mapping[str, Any], model: Mapping[str, Any], matchup: Mapping[str, Any]) -> str:
    form = _display_form(model)
    sample = int(form.get("sample") or 0)
    sigma = _num(model.get("sigma"))
    evidence, total = _evidence_coverage(context, model, matchup)
    risks: list[str] = []
    if 0 < sample < 5:
        risks.append(f"Small recent sample: {sample} games")
    if sigma is not None and sigma >= 9.0:
        risks.append(f"Wide PRA dispersion: σ {sigma:.1f}")
    if context.get("line_moved"):
        risks.append("Sportsbook line moved since selection")
    status = _text(context.get("availability")).upper()
    if status not in _UNVERIFIED and status != "AVAILABLE":
        risks.append(f"Availability: {status}")
    if not risks:
        risks.append("No verified elevated risk flag")
    pills = ''.join(f'<span class="p2cc-risk-pill">{escape(item)}</span>' for item in risks)
    coverage = 0.0 if total <= 0 else evidence / total * 100.0
    return f'<section class="p2cc-panel" data-ks-section="risk"><div class="p2cc-section-kicker">RISK & EVIDENCE QUALITY</div><div class="p2cc-risk-grid"><div><small>EVIDENCE COVERAGE</small><b>{evidence}/{total}</b><div class="p2cc-coverage"><span style="width:{coverage:.1f}%"></span></div><em>Completeness only — not model confidence.</em></div><div class="p2cc-risk-list">{pills}</div></div></section>'


def _game_log_html(games: list[dict[str, Any]], active_line: float | None) -> str:
    if not games:
        body = '<div class="p2cc-empty">Verified game log is not currently available.</div>'
    else:
        rows: list[str] = []
        line = _num(active_line)
        for row in games:
            pra = float(row["pra"])
            result = "—" if line is None else "OVER" if pra > line else "UNDER" if pra < line else "PUSH"
            rows.append(f'<tr><td>{escape(_text(row.get("game_date")) or "Not verified")}</td><td>{escape(_text(row.get("opponent")) or "Not verified")}</td><td>{_fmt(row.get("minutes"))}</td><td>{_fmt(row.get("points"), 0)}</td><td>{_fmt(row.get("rebounds"), 0)}</td><td>{_fmt(row.get("assists"), 0)}</td><td><b>{pra:.1f}</b></td><td><span class="p2cc-result p2cc-result-{result.casefold()}">{escape(result)}</span></td></tr>')
        body = '<div class="p2cc-table-wrap"><table class="p2cc-log"><thead><tr><th>DATE</th><th>OPP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>PRA</th><th>RESULT</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
    return f'<section class="p2cc-panel" data-ks-section="log"><div class="p2cc-section-kicker">FULL GAME LOG</div><p class="p2cc-note">Results recalculate against the active threshold of <b>{_fmt(active_line)}</b>. Raw verified evidence remains unchanged.</p>{body}</section>'


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
            _hero_html(context, model, line_result, active_line),
            _distribution_html(context, model, active_line),
            _insights_html(context, model, line_result, matchup, active_line),
            _recent_performance_html(games, active_line),
            _composition_html(games),
            _matchup_html(matchup, opponent),
            _market_html(context),
            _role_availability_html(context, games),
            _risk_html(context, model, matchup),
            _game_log_html(games, active_line),
        )
    )


def _css() -> str:
    return '''<style>
.p2-wrap{max-width:1450px;margin:auto;color:#f5fbff}.p2cc-hero,.p2cc-panel{margin:12px 0;padding:18px;border-radius:20px;border:1px solid rgba(105,221,255,.22);background:radial-gradient(circle at 92% 0%,rgba(47,174,255,.09),transparent 28%),linear-gradient(145deg,#071728,#050e19);box-shadow:0 18px 44px rgba(0,0,0,.22);overflow:hidden}.p2cc-section-kicker{font-size:11px;letter-spacing:.17em;font-weight:900;color:#6ee4ff;margin-bottom:12px}.p2cc-panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:12px}.p2cc-panel-head p,.p2cc-note{margin:3px 0;color:#91a9bc;font-size:12px;line-height:1.55}.p2cc-badge,.p2cc-pill{display:inline-flex;align-items:center;border-radius:999px;border:1px solid rgba(111,225,255,.24);background:#0a2235;padding:6px 9px;font-size:10px;font-weight:900;color:#a8edff}.p2cc-pill-soft{color:#8faabe}.p2cc-hero{background:radial-gradient(circle at 86% 15%,rgba(40,173,255,.14),transparent 32%),linear-gradient(140deg,#071b2e,#050d18)}.p2cc-hero-grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(340px,.9fr);gap:22px;align-items:center}.p2cc-player{display:flex;align-items:center;gap:18px}.p2cc-face{width:116px;height:116px;border-radius:22px;object-fit:cover;background:#0a1e31;border:1px solid rgba(114,224,255,.25)}.p2cc-face-empty{display:grid;place-items:center;font-weight:900}.p2cc-mini-logo{width:30px;height:30px;object-fit:contain;vertical-align:middle;margin-right:8px}.p2cc-player h1{margin:4px 0 2px;font-size:34px;line-height:1.05}.p2cc-player p{margin:7px 0;color:#a6bbcb}.p2cc-pill-row{display:flex;gap:7px;flex-wrap:wrap}.p2cc-decision{padding:16px;border-radius:17px;background:linear-gradient(145deg,rgba(10,35,55,.96),rgba(6,22,37,.98));border:1px solid rgba(111,225,255,.22)}.p2cc-decision-top{display:flex;justify-content:space-between;gap:12px;color:#87a4b9;font-size:10px;font-weight:900;letter-spacing:.08em}.p2cc-decision-top em{color:#70e6ff;font-style:normal}.p2cc-decision>strong{display:block;font-size:27px;margin:7px 0 13px}.p2cc-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.p2cc-metrics div{padding:9px;border-radius:11px;background:#081a2b;border:1px solid rgba(110,216,255,.13)}.p2cc-metrics small,.p2cc-context-card small,.p2cc-movement small,.p2cc-risk-grid small{display:block;color:#819bae;font-size:9px;font-weight:900}.p2cc-metrics b{display:block;font-size:20px;margin-top:3px}.p2cc-bookline{margin-top:10px;padding-top:10px;border-top:1px solid rgba(110,216,255,.13);display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center}.p2cc-bookline b{font-size:23px;color:#73e5ff}.p2cc-bookline small{color:#aebfcb}.p2cc-distribution-svg,.p2cc-recent-svg{width:100%;display:block;min-height:180px}.p2cc-dist-area{fill:rgba(42,147,255,.20)}.p2cc-dist-line{fill:none;stroke:#34a8ff;stroke-width:3}.p2cc-book-marker{stroke:#ff5b64;stroke-width:2;stroke-dasharray:7 6}.p2cc-projection-marker{stroke:#70e8ff;stroke-width:2}.p2cc-svg-label,.p2cc-svg-value,.p2cc-svg-date,.p2cc-svg-line-label{font-family:Arial,sans-serif;fill:#bcd1df;font-size:11px;font-weight:700}.p2cc-svg-book{fill:#ff737a}.p2cc-svg-projection{fill:#83ecff}.p2cc-chart-meta{display:flex;justify-content:space-between;gap:14px;color:#8ea6b7;font-size:11px}.p2cc-insight-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.p2cc-insight{background:#081c2e;border:1px solid rgba(109,215,255,.15);border-radius:14px;padding:13px}.p2cc-insight h3{margin:0 0 7px;color:#70e1ff;font-size:11px;letter-spacing:.07em}.p2cc-insight p{margin:0;color:#d2e1eb;font-size:12px;line-height:1.62}.p2cc-final-insight{margin-top:11px;padding:16px;border-radius:16px;background:linear-gradient(135deg,rgba(16,55,82,.93),rgba(7,28,46,.97));border:1px solid rgba(112,226,255,.28)}.p2cc-final-insight h2{margin:0 0 8px;font-size:17px}.p2cc-final-insight p{margin:0;color:#dcebf4;font-size:13px;line-height:1.72}.p2cc-recent-bar{fill:#278fe8;opacity:.9}.p2cc-active-line{stroke:#ff5b64;stroke-width:2;stroke-dasharray:7 6}.p2cc-svg-value{fill:#e5f6ff}.p2cc-svg-date{fill:#829bad;font-size:9px}.p2cc-svg-line-label{fill:#ff747c}.p2cc-component-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.p2cc-component{padding:14px;border-radius:14px;background:#081c2e;border:1px solid rgba(109,215,255,.15)}.p2cc-component small{display:block;color:#829bad;font-weight:900}.p2cc-component b{display:block;font-size:22px;margin:5px 0}.p2cc-component-track,.p2cc-coverage,.p2cc-rank-track{height:8px;border-radius:999px;background:#102a40;overflow:hidden}.p2cc-component-track span,.p2cc-coverage span{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#39b9ff,#78e9ff)}.p2cc-component em{display:block;margin-top:6px;color:#829bad;font-size:10px;font-style:normal}.p2cc-rank-bar{display:grid;grid-template-columns:145px 46px minmax(120px,1fr) 110px;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(109,215,255,.10)}.p2cc-rank-bar>span{color:#c7d9e5;font-size:12px}.p2cc-rank-bar>b{font-size:18px}.p2cc-rank-track i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#32d7a2,#6ee7ff)}.p2cc-rank-bar em{font-size:10px;font-weight:900;font-style:normal}.p2cc-grade-good{color:#51e3a8}.p2cc-grade-mid{color:#65d8ff}.p2cc-grade-bad{color:#ff8e96}.p2cc-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.p2cc-market-card,.p2cc-movement,.p2cc-context-card{padding:14px;border-radius:14px;background:#081c2e;border:1px solid rgba(109,215,255,.15)}.p2cc-market-card h3{margin:0 0 9px;font-size:15px}.p2cc-market-card b,.p2cc-movement b,.p2cc-context-card b{display:block;font-size:22px}.p2cc-market-card span,.p2cc-market-card small,.p2cc-movement span,.p2cc-context-card span,.p2cc-context-card em{display:block;margin-top:5px;color:#8fa7b8;font-size:11px;font-style:normal}.p2cc-context-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.p2cc-data-gaps{margin-top:10px;padding:11px 13px;border-radius:12px;background:#0a1723;border:1px dashed rgba(142,172,194,.20)}.p2cc-data-gaps b{display:block;color:#9eb4c4;font-size:10px;letter-spacing:.10em;margin-bottom:7px}.p2cc-data-gaps span{display:inline-block;margin:3px 6px 3px 0;padding:5px 8px;border-radius:999px;background:#101f2d;color:#91a6b5;font-size:10px}.p2cc-risk-grid{display:grid;grid-template-columns:minmax(230px,.45fr) 1fr;gap:14px}.p2cc-risk-grid>div{padding:13px;border-radius:14px;background:#081c2e;border:1px solid rgba(109,215,255,.15)}.p2cc-risk-grid b{display:block;font-size:25px;margin:4px 0 8px}.p2cc-risk-grid em{display:block;color:#829bad;font-size:10px;font-style:normal;margin-top:6px}.p2cc-risk-list{display:flex;align-content:flex-start;gap:7px;flex-wrap:wrap}.p2cc-risk-pill{height:max-content;padding:6px 9px;border-radius:999px;border:1px solid rgba(255,190,87,.25);background:#2d210a;color:#ffd174;font-size:10px;font-weight:900}.p2cc-table-wrap{overflow:auto;border-radius:13px;border:1px solid rgba(109,215,255,.15)}.p2cc-log{width:100%;border-collapse:collapse;min-width:760px}.p2cc-log th{position:sticky;top:0;background:#0c2539;color:#a9bfd0;text-align:left;padding:10px;font-size:10px;letter-spacing:.04em}.p2cc-log td{padding:10px;border-top:1px solid rgba(109,215,255,.10);color:#d8e7f0;font-size:11px}.p2cc-result{padding:4px 7px;border-radius:999px;font-size:9px;font-weight:900}.p2cc-result-over{background:#073326;color:#5ee6ad}.p2cc-result-under{background:#381b21;color:#ff939a}.p2cc-result-push{background:#2b2c19;color:#e7db78}.p2cc-empty{padding:14px;border-radius:13px;background:#081723;border:1px dashed rgba(139,173,194,.18);color:#8ea4b5;font-size:12px}.ks-p2-top{position:fixed;right:18px;bottom:18px;z-index:50;border:1px solid rgba(111,225,255,.35);background:#071827;color:#89e9ff!important;border-radius:999px;padding:10px 13px;text-decoration:none!important;font-size:11px;font-weight:900}.stButton>button{border-radius:11px!important}.p2cc-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:980px){.p2cc-hero-grid{grid-template-columns:1fr}.p2cc-insight-grid{grid-template-columns:repeat(2,1fr)}.p2cc-market-grid{grid-template-columns:repeat(2,1fr)}.p2cc-context-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.p2cc-hero,.p2cc-panel{padding:13px;border-radius:16px}.p2cc-hero-grid,.p2cc-two,.p2cc-insight-grid,.p2cc-market-grid,.p2cc-context-grid,.p2cc-risk-grid,.p2cc-component-grid{grid-template-columns:1fr}.p2cc-player{align-items:flex-start}.p2cc-face{width:86px;height:86px;border-radius:17px}.p2cc-player h1{font-size:27px}.p2cc-metrics{grid-template-columns:repeat(2,1fr)}.p2cc-bookline{grid-template-columns:1fr auto}.p2cc-bookline small{grid-column:1/-1}.p2cc-panel-head{display:block}.p2cc-badge{margin-top:8px}.p2cc-rank-bar{grid-template-columns:105px 38px 1fr}.p2cc-rank-bar em{grid-column:1/-1}.p2cc-chart-meta{display:block}.p2cc-chart-meta span{display:block;margin-top:4px}}
</style>'''


__all__ = ["VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "build_page2_html", "_css"]
