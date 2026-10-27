'''MONSTER NBA PRA Page 2 S-tier V4 — compact decision terminal.

Presentation only. Consumes verified normalized Page 2 mappings, performs no
provider access, and never changes projection/model math.
'''
from __future__ import annotations

from html import escape
from statistics import mean, median
from typing import Any, Mapping

import nba_pra_page2_command_center_v1 as _v1
from nba_pra_page2_data_completeness_v1 import combined_verified_games
from nba_pra_page2_insights_v1 import build_nba_pra_insights


VERSION = "MONSTER_NBA_PRA_PAGE2_S_TIER_V4"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_UNVERIFIED = {"", "UNVERIFIED", "UNKNOWN", "NOT CURRENTLY VERIFIED", "NO VERIFIED INJURY FLAG"}


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _fmt(value: Any, digits: int = 1, missing: str = "—") -> str:
    number = _num(value)
    return f"{number:.{digits}f}" if number is not None else missing


def _price(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _side_probability(result: Mapping[str, Any]) -> float | None:
    lean = _text(result.get("lean")).upper()
    key = "over_probability" if lean == "OVER" else "under_probability" if lean == "UNDER" else ""
    value = _num(result.get(key)) if key else None
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _games(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    return combined_verified_games(profile)


def _verified_quotes(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in list(context.get("quotes") or []) if isinstance(row, Mapping)]
    if rows:
        return rows
    for key in ("current_quote", "selected_quote"):
        row = context.get(key)
        if isinstance(row, Mapping) and row:
            return [dict(row)]
    return []


def _availability_label(context: Mapping[str, Any]) -> tuple[str, bool]:
    status = _text(context.get("availability")).upper()
    verification = _text(context.get("availability_verification")).upper()
    if verification != "VERIFIED" or status in _UNVERIFIED:
        return "STATUS NOT VERIFIED", False
    if "NO OFFICIAL INJURY DESIGNATION" in status or status == "AVAILABLE":
        return "ACTIVE", True
    return status, True


def _recent_minutes(games: list[dict[str, Any]], limit: int = 5) -> list[float]:
    values = [_num(row.get("minutes")) for row in games[:limit]]
    return [float(value) for value in values if value is not None]


def _evidence_coverage(context: Mapping[str, Any], matchup: Mapping[str, Any], games: list[dict[str, Any]]) -> tuple[int, int]:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    status, availability_verified = _availability_label(context)
    del status
    opponent = _text(context.get("opponent")).upper()
    exact = any(_text(row.get("opponent")).upper() == opponent for row in games if opponent)
    areas = (
        bool(games),
        bool(_verified_quotes(context)),
        matchup.get("pra_rank") is not None,
        _num(profile.get("usage_pct")) is not None,
        availability_verified,
        exact,
    )
    return sum(1 for item in areas if item), len(areas)


def _role_descriptor(profile: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    usage = _num(profile.get("usage_pct"))
    minutes = _recent_minutes(games)
    avg_minutes = mean(minutes) if minutes else None
    if usage is not None and usage >= 24:
        return "HIGH-USAGE CREATOR"
    if usage is not None and usage >= 18:
        return "CORE ROTATION • SECONDARY CREATOR"
    if avg_minutes is not None and avg_minutes >= 28:
        return "CORE ROTATION ROLE"
    if avg_minutes is not None:
        return "ROTATION ROLE"
    return "ROLE NOT VERIFIED"


def _hero_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    active_line: float | None,
    games: list[dict[str, Any]],
) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    name = _text(context.get("player_name") or profile.get("player_name")) or "Selected player"
    team = _text(context.get("team") or profile.get("team")).upper() or "TEAM"
    opponent = _text(context.get("opponent")).upper() or "OPP"
    position = _text(profile.get("position")).upper() or "PLAYER"
    headshot = _text(profile.get("headshot"))
    team_logo = _text(context.get("team_logo"))
    opponent_logo = _text(context.get("opponent_logo"))
    status, status_verified = _availability_label(context)
    coverage, coverage_total = _evidence_coverage(context, matchup, games)
    coverage_pct = 100.0 * coverage / coverage_total if coverage_total else 0.0
    minutes = _recent_minutes(games)
    avg_minutes = mean(minutes) if minutes else None
    pra_rank = matchup.get("pra_rank")
    role = _role_descriptor(profile, games)
    lean = _text(result.get("lean")).upper() or "PASS"
    projection = _num(model.get("projection"))
    probability = _side_probability(result)
    edge = _num(result.get("edge"))
    score = _num(result.get("score"))
    tier = _text(result.get("tier")).upper() or _text(result.get("confidence")).upper() or "MODEL"

    photo = f'<img class="p2v4-player-photo" src="{escape(headshot)}" alt="{escape(name)}">' if headshot else '<div class="p2v4-player-photo p2v4-photo-empty">PLAYER</div>'
    team_img = f'<img class="p2v4-team-logo" src="{escape(team_logo)}" alt="{escape(team)} logo">' if team_logo else ""
    opp_img = f'<img class="p2v4-opp-logo" src="{escape(opponent_logo)}" alt="{escape(opponent)} logo">' if opponent_logo else ""
    watermark = f'style="--p2v4-team-watermark:url(\'{escape(team_logo)}\')"' if team_logo else ""
    matchup_badge = f"#{pra_rank} PRA MATCHUP" if pra_rank is not None else "PRA MATCHUP NOT VERIFIED"
    status_class = "p2v4-good" if status_verified and status == "ACTIVE" else "p2v4-warn" if not status_verified else "p2v4-neutral"
    decision = f"{lean} {_fmt(active_line)} PRA" if active_line is not None and lean in {"OVER", "UNDER"} else "PASS / LINE NOT VERIFIED"

    return f'''
<section class="p2v4-hero" data-ks-section="hero" {watermark}>
  <div class="p2v4-kicker">PLAYER COMMAND CENTER</div>
  <div class="p2v4-identity">
    <div class="p2v4-photo-shell">{photo}</div>
    <div class="p2v4-player-copy">
      <div class="p2v4-team-line">{team_img}<span>{escape(team)} • {escape(position)}</span><span class="p2v4-vs">vs</span>{opp_img}<span>{escape(opponent)}</span></div>
      <h1>{escape(name)}</h1>
      <p>{escape(role)}</p>
    </div>
  </div>
  <div class="p2v4-status-row">
    <span class="{status_class}">{escape(status)}</span>
    <span>{coverage}/{coverage_total} VERIFIED</span>
    <span>{_fmt(avg_minutes)} MIN</span>
    <span>{escape(matchup_badge)}</span>
  </div>
  <div class="p2v4-evidence-meter" aria-label="verified evidence coverage"><i style="width:{coverage_pct:.0f}%"></i></div>
  <section class="p2v4-decision-terminal" data-ks-section="decision-terminal">
    <div class="p2v4-decision-head"><small>KYRE DECISION</small><b>{escape(tier)}</b></div>
    <div class="p2v4-decision-main">{escape(decision)}</div>
    <div class="p2v4-metric-grid">
      <div><small>PROJECTION</small><b>{_fmt(projection)}</b></div>
      <div><small>PROBABILITY</small><b>{f'{probability * 100:.0f}%' if probability is not None else '—'}</b></div>
      <div><small>EDGE</small><b>{f'{edge:+.1f}' if edge is not None else '—'}</b></div>
      <div><small>KYRE SCORE</small><b>{_fmt(score)}</b></div>
    </div>
  </section>
</section>'''


def _trend_html(games: list[dict[str, Any]], active_line: float | None) -> str:
    rows = list(reversed(games[:10]))
    line = _num(active_line)
    values = [_num(row.get("pra")) for row in rows]
    values = [float(value) for value in values if value is not None]
    if not values:
        return '<section class="p2v4-panel"><div class="p2v4-kicker">L10 PRA TREND</div><div class="p2v4-empty">Verified game history unavailable.</div></section>'
    scale_values = values + ([float(line)] if line is not None else [])
    lo = min(scale_values)
    hi = max(scale_values)
    pad = max(2.0, (hi - lo) * 0.18)
    lo -= pad
    hi += pad
    span = max(1.0, hi - lo)
    coords: list[tuple[float, float, float]] = []
    for index, row in enumerate(rows):
        pra = _num(row.get("pra"))
        if pra is None:
            continue
        x = 7.0 + (86.0 * index / max(1, len(rows) - 1))
        y = 90.0 - ((float(pra) - lo) / span) * 76.0
        coords.append((x, y, float(pra)))
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
    threshold_y = 90.0 - ((float(line) - lo) / span) * 76.0 if line is not None else None
    threshold = f'<line class="p2v4-threshold" x1="5" y1="{threshold_y:.1f}" x2="95" y2="{threshold_y:.1f}" />' if threshold_y is not None else ""
    circles = "".join(
        f'<circle class="{"p2v4-dot-over" if line is not None and pra > line else "p2v4-dot-under" if line is not None and pra < line else "p2v4-dot-push"}" cx="{x:.1f}" cy="{y:.1f}" r="2.2"><title>{pra:.1f} PRA</title></circle>'
        for x, y, pra in coords
    )
    decided = [pra for _, _, pra in coords if line is not None and pra != line]
    hits = sum(1 for pra in decided if line is not None and pra > line)
    hit_text = f"{hits}/{len(decided)} OVER" if decided else "THRESHOLD RESULTS NOT VERIFIED"
    return f'''
<section class="p2v4-panel" data-ks-section="trend">
  <div class="p2v4-panel-head"><div><div class="p2v4-kicker">L10 PRA TREND</div><p>Verified game-by-game PRA against the active threshold.</p></div><span>ACTIVE LINE {_fmt(line)}</span></div>
  <svg class="p2v4-trend-svg" viewBox="0 0 100 100" role="img" aria-label="PRA trend chart">{threshold}<polyline points="{points}" />{circles}</svg>
  <div class="p2v4-trend-foot"><span>OLDEST</span><b>{escape(hit_text)}</b><span>MOST RECENT</span></div>
</section>'''


def _distribution_html(model: Mapping[str, Any], result: Mapping[str, Any], active_line: float | None) -> str:
    projection = _num(model.get("projection"))
    sigma = _num(model.get("sigma"))
    line = _num(active_line)
    probability = _side_probability(result)
    if projection is None or sigma is None or sigma <= 0:
        return '<section class="p2v4-panel"><div class="p2v4-kicker">PROJECTION DISTRIBUTION</div><div class="p2v4-empty">Verified model dispersion unavailable.</div></section>'
    low = projection - sigma
    high = projection + sigma
    spread = max(1e-6, high - low)
    marker = 50.0 if line is None else max(0.0, min(100.0, ((line - low) / spread) * 100.0))
    return f'''
<section class="p2v4-panel" data-ks-section="projection-range">
  <div class="p2v4-panel-head"><div><div class="p2v4-kicker">PROJECTION DISTRIBUTION</div><p>Frozen projection with verified model dispersion.</p></div><span>MODEL SIGMA {_fmt(sigma)}</span></div>
  <div class="projection-range">
    <div class="p2v4-range-labels"><b>{low:.1f}</b><strong>{projection:.1f}</strong><b>{high:.1f}</b></div>
    <div class="p2v4-range-track"><i></i>{f'<em style="left:{marker:.1f}%"></em>' if line is not None else ''}</div>
    <div class="p2v4-range-meta"><span>−1σ</span><b>{f'ACTIVE LINE {line:.1f}' if line is not None else 'ACTIVE LINE —'}</b><span>+1σ</span></div>
  </div>
  <div class="p2v4-prob-callout">{f'{probability * 100:.0f}% MODEL SIDE' if probability is not None else 'MODEL-SIDE PROBABILITY NOT VERIFIED'}</div>
</section>'''


def _market_html(context: Mapping[str, Any], model: Mapping[str, Any], active_line: float | None) -> str:
    quotes = _verified_quotes(context)
    if not quotes:
        return '<section class="p2v4-panel"><div class="p2v4-kicker">MARKET INTELLIGENCE</div><div class="p2v4-empty">No verified sportsbook quote is currently available.</div></section>'
    lines = [float(value) for value in (_num(row.get("line")) for row in quotes) if value is not None]
    count = len(quotes)
    top_cells = [f'<div><small>MARKET COVERAGE</small><b>{count} VERIFIED BOOK{"S" if count != 1 else ""}</b></div>']
    if count > 1 and lines:
        top_cells.append(f'<div><small>CONSENSUS</small><b>{median(lines):.1f} PRA</b></div>')
    projection = _num(model.get("projection"))
    if projection is not None and active_line is not None:
        top_cells.append(f'<div><small>EDGE VS ACTIVE</small><b>{projection - float(active_line):+.1f}</b></div>')
    over_rows = [(row, _num(row.get("over_price"))) for row in quotes]
    over_rows = [(row, price) for row, price in over_rows if price is not None]
    under_rows = [(row, _num(row.get("under_price"))) for row in quotes]
    under_rows = [(row, price) for row, price in under_rows if price is not None]
    if over_rows:
        row, price = max(over_rows, key=lambda pair: float(pair[1]))
        top_cells.append(f'<div><small>BEST OVER</small><b>{escape(_text(row.get("sportsbook")))} {_price(price)}</b></div>')
    if under_rows:
        row, price = max(under_rows, key=lambda pair: float(pair[1]))
        top_cells.append(f'<div><small>BEST UNDER</small><b>{escape(_text(row.get("sportsbook")))} {_price(price)}</b></div>')
    quote_cards = []
    for row in quotes:
        book = _text(row.get("sportsbook")) or "Verified book"
        quote_cards.append(
            '<article class="p2v4-book">'
            f'<b>{escape(book)}</b><strong>{_fmt(row.get("line"))} PRA</strong>'
            f'<span>O {_price(row.get("over_price"))} • U {_price(row.get("under_price"))}</span>'
            '</article>'
        )
    selected = context.get("selected_quote") if isinstance(context.get("selected_quote"), Mapping) else {}
    current = context.get("current_quote") if isinstance(context.get("current_quote"), Mapping) else {}
    movement = "No verified same-book movement since selection."
    if selected and current and _text(selected.get("sportsbook")) == _text(current.get("sportsbook")):
        old_line = _num(selected.get("line"))
        new_line = _num(current.get("line"))
        if old_line is not None and new_line is not None and abs(old_line - new_line) > 1e-9:
            movement = f'{_text(current.get("sportsbook"))}: {old_line:.1f} → {new_line:.1f} PRA'
    return f'''
<section class="p2v4-panel" data-ks-section="market">
  <div class="p2v4-kicker">MARKET INTELLIGENCE</div>
  <div class="p2v4-market-summary">{"".join(top_cells)}</div>
  <div class="p2v4-book-grid">{"".join(quote_cards)}</div>
  <div class="p2v4-movement"><small>LINE MOVEMENT</small><b>{escape(movement)}</b></div>
  <p class="p2v4-fine">Verified books remain independent. Market lines are never used as the projection.</p>
</section>'''


def _role_html(context: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    usage = _num(profile.get("usage_pct"))
    usage_rank = profile.get("usage_rank")
    team = _text(context.get("team")).upper()
    minutes = _recent_minutes(games)
    avg_minutes = mean(minutes) if minutes else None
    minutes_trend = " → ".join(f"{value:.0f}" for value in reversed(minutes)) if minutes else "NOT VERIFIED"
    status, status_verified = _availability_label(context)
    availability_source = _text(context.get("availability_source")) or ("Verified source" if status_verified else "Source not verified")
    opponent = _text(context.get("opponent")).upper()
    exact = [row for row in games if opponent and _text(row.get("opponent")).upper() == opponent]
    usage_value = f"{usage:.1f}%" if usage is not None else "USAGE NOT VERIFIED"
    usage_meta = f"#{int(usage_rank)} ON {team}" if isinstance(usage_rank, (int, float)) and team else _role_descriptor(profile, games)
    prior = f'{len(exact)} VERIFIED GAME{"S" if len(exact) != 1 else ""}' if exact else "NO VERIFIED PRIOR MATCHUP"
    teammates = context.get("teammate_injuries") if isinstance(context.get("teammate_injuries"), list) else []
    teammate_text = f"{len(teammates)} FLAGGED" if teammates else "NO VERIFIED FLAGS" if _text(context.get("availability_verification")).upper() == "VERIFIED" else "NOT VERIFIED"
    return f'''
<section class="p2v4-panel" data-ks-section="role">
  <div class="p2v4-kicker">ROLE & AVAILABILITY</div>
  <div class="p2v4-role-grid">
    <article><small>ROLE / USAGE</small><b>{escape(usage_value)}</b><span>{escape(usage_meta)}</span><em>{escape(_text(profile.get("usage_period")) or "Usage period not verified")}</em></article>
    <article><small>RECENT OPPORTUNITY</small><b>{_fmt(avg_minutes)} MIN</b><span>{escape(minutes_trend)}</span><em>Verified recent minutes</em></article>
    <article><small>PLAYER AVAILABILITY</small><b>{escape(status)}</b><span>{escape(_text(context.get("availability_reason")) or ("No listed designation." if status == "ACTIVE" else "Verified status" if status_verified else "Awaiting verified report"))}</span><em>{escape(availability_source)}</em></article>
    <article><small>TEAMMATE AVAILABILITY</small><b>{escape(teammate_text)}</b><span>{escape(prior)}</span><em>{"Exact opponent history available" if exact else "Exact opponent history only"}</em></article>
  </div>
</section>'''


def _driver_row(label: str, value: str, tone: str, detail: str) -> str:
    return f'<div class="p2v4-driver"><span>{escape(label)}</span><b class="p2v4-driver-{tone}">{escape(value)}</b><em>{escape(detail)}</em></div>'


def _drivers_html(context: Mapping[str, Any], result: Mapping[str, Any], matchup: Mapping[str, Any], active_line: float | None, games: list[dict[str, Any]]) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    lean = _text(result.get("lean")).upper()
    line = _num(active_line)
    recent = [float(row["pra"]) for row in games[:5] if _num(row.get("pra")) is not None]
    recent_avg = mean(recent) if recent else None
    if recent_avg is None or line is None or lean not in {"OVER", "UNDER"}:
        form_value, form_tone, form_detail = "NOT VERIFIED", "neutral", "Need verified recent PRA + active line"
    else:
        supports = recent_avg > line if lean == "OVER" else recent_avg < line
        form_value, form_tone = ("SUPPORTS", "good") if supports else ("PRESSURES", "warn")
        form_detail = f"{recent_avg:.1f} recent PRA avg vs {line:.1f}"
    minutes = _recent_minutes(games)
    if minutes:
        avg_minutes = mean(minutes)
        minute_value = "STRONG" if avg_minutes >= 30 else "STABLE" if avg_minutes >= 24 else "LIMITED"
        minute_tone = "good" if avg_minutes >= 24 else "warn"
        minute_detail = f"{avg_minutes:.1f} verified recent minutes"
    else:
        minute_value, minute_tone, minute_detail = "NOT VERIFIED", "neutral", "Recent minutes unavailable"
    grade = _text(matchup.get("matchup_grade")).upper()
    matchup_value = grade or "NOT VERIFIED"
    matchup_tone = "warn" if grade in {"TOUGH", "VERY TOUGH"} and lean == "OVER" else "good" if grade in {"FAVORABLE", "SOFT"} and lean == "OVER" else "neutral"
    matchup_detail = f'#{matchup.get("pra_rank")} PRA opponent rank' if matchup.get("pra_rank") is not None else "PRA rank unavailable"
    usage = _num(profile.get("usage_pct"))
    role_value = f"{usage:.1f}%" if usage is not None else "NOT VERIFIED"
    role_tone = "good" if usage is not None and usage >= 18 else "neutral"
    role_detail = _role_descriptor(profile, games)
    status, verified = _availability_label(context)
    availability_value = status
    availability_tone = "good" if status == "ACTIVE" else "neutral" if verified else "warn"
    availability_detail = "Official report verified" if verified else "Verified report not available"
    return f'''
<section class="p2v4-panel" data-ks-section="drivers">
  <div class="p2v4-kicker">MODEL DRIVERS</div>
  <div class="p2v4-driver-list">
    {_driver_row("RECENT FORM", form_value, form_tone, form_detail)}
    {_driver_row("MINUTES", minute_value, minute_tone, minute_detail)}
    {_driver_row("MATCHUP", matchup_value, matchup_tone, matchup_detail)}
    {_driver_row("ROLE / USAGE", role_value, role_tone, role_detail)}
    {_driver_row("AVAILABILITY", availability_value, availability_tone, availability_detail)}
  </div>
</section>'''


def _hit_summary(games: list[dict[str, Any]], active_line: float | None, lean: str) -> tuple[int, int]:
    line = _num(active_line)
    if line is None or lean not in {"OVER", "UNDER"}:
        return 0, 0
    values = [float(row["pra"]) for row in games[:10] if _num(row.get("pra")) is not None and float(row["pra"]) != line]
    hits = sum(1 for value in values if (value > line if lean == "OVER" else value < line))
    return hits, len(values)


def _caution(context: Mapping[str, Any], model: Mapping[str, Any]) -> str:
    current = model.get("current") if isinstance(model.get("current"), Mapping) else {}
    sample = int(_num(current.get("sample")) or 0)
    if 0 < sample < 5:
        return f"SMALL SAMPLE: {sample} GAMES"
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    if _num(profile.get("usage_pct")) is None:
        return "USAGE / ROLE NOT VERIFIED"
    status, verified = _availability_label(context)
    if not verified:
        return "AVAILABILITY NOT VERIFIED"
    if status != "ACTIVE":
        return status
    return "NO VERIFIED ELEVATED RISK FLAG"


def _decision_factors_html(context: Mapping[str, Any], model: Mapping[str, Any], result: Mapping[str, Any], matchup: Mapping[str, Any], active_line: float | None, games: list[dict[str, Any]]) -> str:
    lean = _text(result.get("lean")).upper() or "PASS"
    edge = _num(result.get("edge"))
    probability = _side_probability(result)
    hits, total = _hit_summary(games, active_line, lean)
    grade = _text(matchup.get("matchup_grade")).upper()
    supports = []
    if edge is not None:
        supports.append(f"{edge:+.1f} PRA EDGE")
    if total:
        supports.append(f"{hits}/{total} {lean}")
    if probability is not None:
        supports.append(f"{probability * 100:.0f}% {lean} MODEL SIDE")
    if grade:
        supports.append(f"{grade} PRA MATCHUP")
    support_html = "".join(f"<span>{escape(item)}</span>" for item in supports) or "<span>VERIFIED SUPPORT LIMITED</span>"
    caution = _caution(context, model)
    return f'''
<section class="p2v4-factors" data-ks-section="decision-factors">
  <div class="p2v4-factor-good"><small>WHY THIS PICK WORKS</small><div>{support_html}</div></div>
  <div class="p2v4-factor-warn"><small>WHAT COULD BREAK IT</small><div><span>{escape(caution)}</span></div></div>
</section>'''


def _kyre_read_html(context: Mapping[str, Any], model: Mapping[str, Any], result: Mapping[str, Any], matchup: Mapping[str, Any], active_line: float | None, games: list[dict[str, Any]]) -> str:
    projection = _num(model.get("projection"))
    edge = _num(result.get("edge"))
    probability = _side_probability(result)
    lean = _text(result.get("lean")).upper() or "PASS"
    recent = [float(row["pra"]) for row in games[:5] if _num(row.get("pra")) is not None]
    recent_avg = mean(recent) if recent else None
    edge_text = f"{edge:+.1f} PRA EDGE" if edge is not None else "EDGE NOT VERIFIED"
    if probability is not None and lean in {"OVER", "UNDER"}:
        edge_text += f" • {probability * 100:.0f}% {lean}"
    caution = _caution(context, model)
    bits: list[str] = []
    if projection is not None and active_line is not None:
        bits.append(f"Kyre projects {projection:.1f} PRA against {float(active_line):.1f}.")
    if recent_avg is not None:
        bits.append(f"Recent verified PRA averages {recent_avg:.1f}.")
    if matchup.get("pra_rank") is not None:
        bits.append(f"Opponent PRA rank is #{matchup.get('pra_rank')} with a {_text(matchup.get('matchup_grade')).upper() or 'verified'} grade.")
    status, verified = _availability_label(context)
    if verified:
        bits.append(f"Availability: {status}.")
    bottom = " ".join(bits) or "Verified evidence is currently limited; no missing evidence was invented."
    return f'''
<section class="p2v4-panel p2v4-read" data-ks-section="kyre-read">
  <div class="p2v4-kicker">KYRE READ</div>
  <div class="p2v4-read-meta"><div><small>PRIMARY EDGE</small><b>{escape(edge_text)}</b></div><div><small>PRIMARY CAUTION</small><b>{escape(caution)}</b></div></div>
  <p>{escape(bottom)}</p>
</section>'''


def _deep_evidence_html(context: Mapping[str, Any], model: Mapping[str, Any], result: Mapping[str, Any], matchup: Mapping[str, Any], active_line: float | None, games: list[dict[str, Any]]) -> str:
    opponent = _text(context.get("opponent")) or "Opponent not verified"
    report = build_nba_pra_insights(context, model, result, matchup, active_line=active_line)
    insight_cards = []
    for row in list(report.get("sections") or []):
        if not isinstance(row, Mapping):
            continue
        title = _text(row.get("title"))
        body = _text(row.get("body"))
        if title and body:
            insight_cards.append(f'<article class="p2v4-evidence-card"><h3>{escape(title)}</h3><p>{escape(body)}</p></article>')
    return f'''
<details class="p2v4-details">
  <summary>DEEP VERIFIED EVIDENCE <span>Tap to expand</span></summary>
  <div class="p2v4-details-body">
    <div class="p2v4-evidence-grid">{"".join(insight_cards) if insight_cards else '<div class="p2v4-empty">No additional verified narrative evidence.</div>'}</div>
    {_v1._composition_html(games)}
    {_v1._matchup_html(matchup, opponent)}
    {_v1._risk_html(context, model, matchup)}
  </div>
</details>'''


def _game_result(pra: float, line: float | None) -> str:
    if line is None:
        return "—"
    if pra > line:
        return "OVER"
    if pra < line:
        return "UNDER"
    return "PUSH"


def _game_log_html(games: list[dict[str, Any]], active_line: float | None) -> str:
    line = _num(active_line)
    if not games:
        return '<section class="p2v4-panel"><div class="p2v4-kicker">FULL GAME LOG</div><div class="p2v4-empty">Verified game history unavailable.</div></section>'
    table_rows = []
    cards = []
    for row in games:
        date = _text(row.get("game_date")) or "—"
        opp = _text(row.get("opponent")).upper() or "—"
        minutes = _num(row.get("minutes"))
        pts = _num(row.get("points"))
        reb = _num(row.get("rebounds"))
        ast = _num(row.get("assists"))
        pra = _num(row.get("pra"))
        if pra is None:
            continue
        result = _game_result(float(pra), line)
        result_class = result.lower()
        table_rows.append(
            f'<tr><td>{escape(date)}</td><td>{escape(opp)}</td><td>{_fmt(minutes)}</td><td>{_fmt(pts,0)}</td><td>{_fmt(reb,0)}</td><td>{_fmt(ast,0)}</td><td><b>{pra:.1f}</b></td><td><span class="p2v4-result-{result_class}">{result}</span></td></tr>'
        )
        cards.append(
            f'<article class="p2v4-game-card"><div><b>{escape(date)} • vs {escape(opp)}</b><span class="p2v4-result-{result_class}">{result}{f" {line:.1f}" if line is not None else ""}</span></div><strong>{pra:.1f} PRA</strong><p>{_fmt(minutes)} MIN • {_fmt(pts,0)} PTS • {_fmt(reb,0)} REB • {_fmt(ast,0)} AST</p></article>'
        )
    return f'''
<section class="p2v4-panel" data-ks-section="game-log">
  <div class="p2v4-panel-head"><div><div class="p2v4-kicker">FULL GAME LOG</div><p>Verified results recalculated against the active threshold of <b>{_fmt(line)}</b>.</p></div></div>
  <div class="p2v4-game-table"><table><thead><tr><th>DATE</th><th>OPP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>PRA</th><th>RESULT</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>
  <div class="p2v4-game-cards">{"".join(cards)}</div>
</section>'''


def build_page2_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> str:
    games = _games(context)
    return "\n".join(
        (
            '<div id="ks-nba-pra-page2-top"></div>',
            _hero_html(context, model, line_result, matchup, active_line, games),
            _trend_html(games, active_line),
            _distribution_html(model, line_result, active_line),
            _market_html(context, model, active_line),
            _role_html(context, games),
            _drivers_html(context, line_result, matchup, active_line, games),
            _decision_factors_html(context, model, line_result, matchup, active_line, games),
            _kyre_read_html(context, model, line_result, matchup, active_line, games),
            _deep_evidence_html(context, model, line_result, matchup, active_line, games),
            _game_log_html(games, active_line),
        )
    )


def _css() -> str:
    base = _v1._css().rstrip()
    if not base.endswith("</style>"):
        raise ValueError("NBA PRA Page 2 base stylesheet is missing its closing style tag")
    base = base[:-len("</style>")]
    return base + r'''
/* MONSTER NBA PRA Page 2 V4 — compact decision terminal */
.p2-wrap{max-width:1180px;margin:0 auto;padding-bottom:40px}
.p2v4-hero,.p2v4-panel,.p2v4-details{position:relative;margin:14px 0;padding:20px;border:1px solid rgba(92,211,255,.22);border-radius:24px;background:linear-gradient(145deg,rgba(7,29,48,.96),rgba(4,18,31,.96));box-shadow:0 16px 44px rgba(0,0,0,.18);overflow:hidden}
.p2v4-hero:before{content:"";position:absolute;inset:0;background-image:linear-gradient(90deg,rgba(5,20,34,.97),rgba(5,20,34,.78)),var(--p2v4-team-watermark);background-position:center,right -20px center;background-size:auto,230px;background-repeat:no-repeat;opacity:.52;pointer-events:none}.p2v4-hero>*{position:relative;z-index:1}
.p2v4-kicker{font-size:13px;letter-spacing:.2em;font-weight:900;color:#69ddff;margin-bottom:14px}.p2v4-identity{display:flex;align-items:center;gap:18px}.p2v4-photo-shell{width:126px;height:126px;border-radius:24px;border:1px solid rgba(105,221,255,.3);background:#081d2f;overflow:hidden;flex:0 0 126px}.p2v4-player-photo{width:100%;height:100%;object-fit:cover;display:block}.p2v4-photo-empty{display:flex;align-items:center;justify-content:center;color:#7f9aae;font-size:11px;font-weight:900}.p2v4-player-copy h1{font-size:clamp(28px,5vw,48px);line-height:1.02;margin:7px 0;color:#f7fbff}.p2v4-player-copy p{margin:0;color:#8faec2;font-weight:800;letter-spacing:.04em}.p2v4-team-line{display:flex;align-items:center;gap:8px;color:#b5c9d7;font-size:14px;font-weight:800}.p2v4-team-logo,.p2v4-opp-logo{width:27px;height:27px;object-fit:contain}.p2v4-vs{opacity:.55;margin:0 3px}.p2v4-status-row{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 9px}.p2v4-status-row span{padding:7px 10px;border-radius:999px;background:#0a2237;border:1px solid rgba(105,221,255,.16);font-size:11px;font-weight:900;color:#c5d8e5}.p2v4-status-row .p2v4-good{color:#72efc0;border-color:rgba(65,231,173,.32);background:rgba(11,66,52,.48)}.p2v4-status-row .p2v4-warn{color:#ffc866;border-color:rgba(255,181,62,.3);background:rgba(77,48,5,.48)}.p2v4-evidence-meter{height:5px;border-radius:999px;background:#0c2a43;overflow:hidden;margin-bottom:16px}.p2v4-evidence-meter i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#38bdf8,#69ddff)}
.p2v4-decision-terminal{border:1px solid rgba(105,221,255,.22);border-radius:20px;padding:16px;background:rgba(3,18,30,.72)}.p2v4-decision-head{display:flex;justify-content:space-between;align-items:center;color:#87a7bb;font-size:11px;font-weight:900;letter-spacing:.11em}.p2v4-decision-head b{color:#69ddff}.p2v4-decision-main{font-size:clamp(28px,5vw,42px);font-weight:950;color:#fff;margin:10px 0 14px}.p2v4-metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.p2v4-metric-grid div,.p2v4-market-summary div,.p2v4-read-meta div{padding:12px;border-radius:14px;background:#071b2c;border:1px solid rgba(105,221,255,.12)}.p2v4-metric-grid small,.p2v4-market-summary small,.p2v4-read-meta small{display:block;color:#7897aa;font-size:10px;font-weight:900;margin-bottom:6px}.p2v4-metric-grid b,.p2v4-market-summary b,.p2v4-read-meta b{font-size:20px;color:#f7fbff}
.p2v4-panel-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.p2v4-panel-head p,.p2v4-fine{color:#8da7b9;margin:2px 0 10px}.p2v4-panel-head>span{white-space:nowrap;padding:7px 10px;border-radius:999px;border:1px solid rgba(105,221,255,.2);color:#a9c7d8;font-size:11px;font-weight:900}.p2v4-trend-svg{width:100%;height:210px;background:#061a2b;border:1px solid rgba(105,221,255,.12);border-radius:18px;padding:8px;box-sizing:border-box}.p2v4-trend-svg polyline{fill:none;stroke:#69ddff;stroke-width:1.4;vector-effect:non-scaling-stroke}.p2v4-threshold{stroke:#f8c15c;stroke-width:1.2;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}.p2v4-dot-over{fill:#59e1b3}.p2v4-dot-under{fill:#ff7789}.p2v4-dot-push{fill:#f8c15c}.p2v4-trend-foot{display:flex;justify-content:space-between;align-items:center;margin-top:8px;color:#7593a7;font-size:10px;font-weight:800}.p2v4-trend-foot b{color:#cfe3ee}.projection-range{padding:15px;border-radius:18px;background:#061a2b;border:1px solid rgba(105,221,255,.12)}.p2v4-range-labels,.p2v4-range-meta{display:flex;justify-content:space-between;align-items:center;color:#8eabba;font-size:11px}.p2v4-range-labels strong{font-size:22px;color:#f8fbff}.p2v4-range-track{height:10px;margin:14px 0;position:relative;border-radius:999px;background:#102e47}.p2v4-range-track i{position:absolute;left:0;right:0;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,#2fbaf2,#78e7f6)}.p2v4-range-track em{position:absolute;top:-5px;width:3px;height:20px;background:#f8c15c;border-radius:2px;transform:translateX(-50%)}.p2v4-prob-callout{margin-top:10px;font-size:12px;font-weight:900;color:#7ce9c2}
.p2v4-market-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin-bottom:10px}.p2v4-book-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:9px}.p2v4-book{padding:14px;border-radius:16px;background:#071b2c;border:1px solid rgba(105,221,255,.13);display:grid;gap:7px}.p2v4-book b{color:#fff}.p2v4-book strong{font-size:24px;color:#69ddff}.p2v4-book span{color:#8da6b8}.p2v4-movement{margin-top:10px;padding:12px;border-radius:14px;background:#071b2c}.p2v4-movement small{display:block;color:#7897aa;font-weight:900;margin-bottom:5px}.p2v4-movement b{color:#d7e7f0}
.p2v4-role-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.p2v4-role-grid article{padding:14px;border-radius:16px;background:#071b2c;border:1px solid rgba(105,221,255,.13);display:grid;gap:6px}.p2v4-role-grid small{color:#7897aa;font-weight:900}.p2v4-role-grid b{font-size:23px;color:#fff}.p2v4-role-grid span{color:#b6cbd8}.p2v4-role-grid em{font-style:normal;color:#708da1;font-size:12px}.p2v4-driver-list{display:grid;gap:7px}.p2v4-driver{display:grid;grid-template-columns:140px 120px 1fr;gap:12px;align-items:center;padding:11px 12px;border-radius:14px;background:#071b2c}.p2v4-driver span{color:#9cb7c8;font-weight:900}.p2v4-driver b{font-size:12px}.p2v4-driver em{font-style:normal;color:#708da1}.p2v4-driver-good{color:#63e6b7}.p2v4-driver-warn{color:#ffc866}.p2v4-driver-neutral{color:#8fb0c3}
.p2v4-factors{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.p2v4-factor-good,.p2v4-factor-warn{padding:16px;border-radius:18px;border:1px solid rgba(105,221,255,.15);background:#071b2c}.p2v4-factor-good small{color:#63e6b7}.p2v4-factor-warn small{color:#ffc866}.p2v4-factors small{font-weight:950;letter-spacing:.1em}.p2v4-factors div div{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.p2v4-factors span{padding:7px 9px;border-radius:999px;background:#0a2438;color:#d4e4ed;font-size:11px;font-weight:900}.p2v4-read-meta{display:grid;grid-template-columns:1fr 1fr;gap:9px}.p2v4-read p{font-size:16px;line-height:1.65;color:#c8d9e3}.p2v4-details summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;color:#69ddff;font-weight:950;letter-spacing:.08em}.p2v4-details summary span{font-size:11px;color:#7e9caf;letter-spacing:0}.p2v4-details-body{padding-top:16px}.p2v4-evidence-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-bottom:12px}.p2v4-evidence-card{padding:14px;border-radius:16px;background:#071b2c;border:1px solid rgba(105,221,255,.12)}.p2v4-evidence-card h3{margin:0 0 7px;color:#69ddff;font-size:13px;letter-spacing:.08em}.p2v4-evidence-card p{margin:0;color:#b7cad6;line-height:1.55}.p2v4-empty{padding:18px;border-radius:16px;background:#071b2c;color:#809eb1}
.p2v4-game-table{overflow:hidden;border:1px solid rgba(105,221,255,.14);border-radius:18px}.p2v4-game-table table{width:100%;border-collapse:collapse}.p2v4-game-table th,.p2v4-game-table td{padding:12px 10px;text-align:left;border-bottom:1px solid rgba(105,221,255,.1);color:#bcd0dc}.p2v4-game-table th{font-size:10px;color:#809eb1;background:#0a263d}.p2v4-game-table td b{color:#fff}.p2v4-game-cards{display:none}.p2v4-result-over{color:#62e6b6!important}.p2v4-result-under{color:#ff7f91!important}.p2v4-result-push{color:#f8c15c!important}
@media(max-width:700px){.p2-wrap{padding-left:0;padding-right:0}.p2v4-hero,.p2v4-panel,.p2v4-details{padding:16px;border-radius:20px;margin:11px 0}.p2v4-identity{align-items:flex-start}.p2v4-photo-shell{width:98px;height:112px;flex-basis:98px;border-radius:20px}.p2v4-player-copy h1{font-size:31px}.p2v4-team-line{flex-wrap:wrap;font-size:12px}.p2v4-status-row{gap:6px}.p2v4-status-row span{font-size:10px;padding:6px 8px}.p2v4-metric-grid{grid-template-columns:repeat(2,1fr)}.p2v4-panel-head{display:block}.p2v4-panel-head>span{display:inline-block;margin-bottom:10px}.p2v4-trend-svg{height:180px}.p2v4-role-grid,.p2v4-factors,.p2v4-read-meta,.p2v4-evidence-grid{grid-template-columns:1fr}.p2v4-driver{grid-template-columns:100px 90px 1fr;gap:8px}.p2v4-driver em{font-size:11px}.p2v4-game-table{display:none}.p2v4-game-cards{display:grid;gap:8px}.p2v4-game-card{padding:13px;border-radius:16px;background:#071b2c;border:1px solid rgba(105,221,255,.13)}.p2v4-game-card>div{display:flex;justify-content:space-between;gap:8px;align-items:center}.p2v4-game-card b{font-size:12px;color:#b9ceda}.p2v4-game-card strong{display:block;font-size:22px;color:#fff;margin:8px 0 4px}.p2v4-game-card p{margin:0;color:#7897aa;font-size:12px}}
</style>'''
