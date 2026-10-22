"""NFL Passing Yards Page 2 — selected-QB analytics command center.

This renderer is application-only. It performs no provider requests and consumes
only the normalized selected-player payload delivered by Kyre Sports API.
Missing or unverified fields stay explicit; sportsbook observations stay
independent and are never blended into a synthetic market line.
"""
from __future__ import annotations

from html import escape
from typing import Any


CSS = r"""
<style>
:root{--k-bg:#080d14;--k-card:#0c1621;--k-card2:#09121b;--k-line:#26394b;--k-text:#f4f7fb;--k-muted:#9aaabc;--k-blue:#6cc9ff;--k-green:#73dfa5;--k-red:#ff6d75;--k-amber:#ffc968}
.kpy2-shell{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--k-text);max-width:1120px;margin:0 auto;padding:8px 0 42px}
.kpy2-back{display:inline-flex;text-decoration:none;color:#89d6ff;border:1px solid #31536c;border-radius:999px;padding:8px 13px;font-weight:800;margin:4px 0 14px}
.kpy2-hero{background:linear-gradient(145deg,#0d1b28,#08111b 70%);border:1px solid #31506a;border-radius:24px;padding:22px;box-shadow:0 18px 50px rgba(0,0,0,.24)}
.kpy2-hero-top{display:grid;grid-template-columns:auto 1fr auto;gap:18px;align-items:center}.kpy2-face{width:92px;height:92px;border-radius:50%;object-fit:cover;border:4px solid #3c789f;background:#101b26}.kpy2-teamlogo{width:64px;height:64px;object-fit:contain}.kpy2-kicker{color:var(--k-blue);font-size:12px;font-weight:900;letter-spacing:.16em}.kpy2-name{font-size:34px;line-height:1.05;font-weight:950;margin:5px 0}.kpy2-sub{color:#b8c5d2;font-size:15px}.kpy2-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:18px}.kpy2-stat,.kpy2-box{background:rgba(6,14,22,.78);border:1px solid var(--k-line);border-radius:18px;padding:15px}.kpy2-stat .l,.kpy2-label{color:var(--k-muted);font-size:11px;letter-spacing:.12em;font-weight:900}.kpy2-stat .v{font-size:25px;font-weight:950;margin-top:6px}.kpy2-stat .s{font-size:12px;color:#aebccb;margin-top:4px}.kpy2-section{margin-top:18px;background:var(--k-card);border:1px solid #203447;border-radius:22px;padding:19px}.kpy2-title{font-size:15px;font-weight:950;letter-spacing:.11em;color:#e9f5ff;margin-bottom:14px}.kpy2-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.kpy2-three{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.kpy2-five{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.kpy2-value{font-size:20px;font-weight:900;margin-top:5px}.kpy2-note{font-size:12px;color:#a7b7c6;margin-top:5px;line-height:1.45}.kpy2-good{color:var(--k-green)}.kpy2-warn{color:var(--k-amber)}.kpy2-bad{color:var(--k-red)}.kpy2-blue{color:var(--k-blue)}
.kpy2-tablewrap{overflow-x:auto;border:1px solid #22394c;border-radius:16px}.kpy2-table{width:100%;border-collapse:collapse;min-width:660px;background:#08121b}.kpy2-table th{font-size:10px;color:#8fa3b6;text-align:left;padding:11px;border-bottom:1px solid #24384a;letter-spacing:.09em}.kpy2-table td{font-size:13px;font-weight:750;padding:11px;border-bottom:1px solid #172a3a;color:#dbe7f1}.kpy2-table tr:last-child td{border-bottom:0}.kpy2-chip{display:inline-flex;border:1px solid #35536a;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:900}.kpy2-over{border-color:#397b58;color:#82e3ac}.kpy2-under{border-color:#86514e;color:#ff9c96}.kpy2-push{border-color:#806c3b;color:#ffd77b}.kpy2-na{display:flex;align-items:flex-start;gap:8px;border:1px dashed #4b5662;border-radius:14px;padding:12px;color:#b8c0c9;background:#0b1118;font-size:12px;line-height:1.45}.kpy2-factor{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #1b3041}.kpy2-factor:last-child{border-bottom:0}.kpy2-dot{width:9px;height:9px;border-radius:50%;margin-top:5px;background:#758698}.kpy2-dot.y{background:#67da99}.kpy2-risk{padding:10px 12px;border-left:3px solid #ffb955;background:#16140d;border-radius:8px;margin:8px 0;color:#f4d59c;font-size:13px}.kpy2-decision{background:linear-gradient(135deg,#0b1e1a,#0b1722);border:1px solid #38745c;border-radius:20px;padding:18px}.kpy2-side{font-size:30px;font-weight:1000;letter-spacing:.02em}.kpy2-footer{color:#7890a4;font-size:11px;text-align:center;padding:18px 4px 0}
@media(max-width:760px){.kpy2-shell{padding-left:2px;padding-right:2px}.kpy2-hero,.kpy2-section{border-radius:18px;padding:15px}.kpy2-hero-top{grid-template-columns:72px 1fr auto;gap:11px}.kpy2-face{width:70px;height:70px}.kpy2-teamlogo{width:44px;height:44px}.kpy2-name{font-size:25px}.kpy2-grid{grid-template-columns:1fr 1fr}.kpy2-two,.kpy2-three,.kpy2-five{grid-template-columns:1fr 1fr}.kpy2-stat .v{font-size:21px}.kpy2-side{font-size:26px}}
</style>
"""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _e(value: Any) -> str:
    return escape(_text(value), quote=True)


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return "NOT AVAILABLE" if number is None else f"{number:.{digits}f}"


def _pct(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "NOT AVAILABLE"
    if -1.0 <= number <= 1.0:
        number *= 100.0
    return f"{number:.0f}%"


def _odds(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "NOT AVAILABLE"
    return f"{int(number):+d}" if float(number).is_integer() else f"{number:+.1f}"


def _metric(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="s">{_e(sub)}</div>' if sub else ""
    return f'<div class="kpy2-stat"><div class="l">{_e(label)}</div><div class="v">{_e(value)}</div>{sub_html}</div>'


def _unavailable(reason: Any) -> str:
    message = _text(reason) or "Verified data is not available for this field."
    return f'<div class="kpy2-na"><b>NOT AVAILABLE</b><span>{_e(message)}</span></div>'


def _market_result(yards: Any, line: Any) -> str:
    y = _num(yards)
    l = _num(line)
    if y is None or l is None:
        return "NOT AVAILABLE"
    if y > l:
        return "OVER"
    if y < l:
        return "UNDER"
    return "PUSH"


def _result_chip(result: str) -> str:
    key = result.lower().replace(" ", "-")
    cls = "kpy2-over" if key == "over" else ("kpy2-under" if key == "under" else ("kpy2-push" if key == "push" else ""))
    return f'<span class="kpy2-chip {cls}">{_e(result)}</span>'


def _game_rows(detail: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    season = [dict(row) for row in (detail.get("season_game_log") or []) if isinstance(row, dict)]
    if season:
        return list(reversed(season[-10:])), True
    recent = [dict(row) for row in ((detail.get("profile") or {}).get("recent_games") or []) if isinstance(row, dict)]
    return recent[:5], False


def _game_table(detail: dict[str, Any], line: Any) -> str:
    rows, full_log = _game_rows(detail)
    if not rows:
        return _unavailable("Verified quarterback game history is not available in this payload.")
    body: list[str] = []
    for row in rows:
        result = _market_result(row.get("passing_yards"), line)
        week = row.get("week")
        week_text = f"W{int(week)}" if _num(week) is not None else "—"
        opponent = _text(row.get("opponent")) or "—"
        location = _text(row.get("home_away")) or "—"
        body.append(
            "<tr>"
            f"<td>{_e(week_text)}</td><td>{_e(location)}</td><td>{_e(opponent)}</td>"
            f"<td>{_fmt(row.get('passing_yards'),0)}</td><td>{_fmt(row.get('attempts'),0)}</td>"
            f"<td>{_fmt(row.get('completions'),0)}</td><td>{_fmt(row.get('pass_tds'),0)}</td>"
            f"<td>{_fmt(row.get('interceptions'),0)}</td><td>{_result_chip(result)}</td></tr>"
        )
    scope_note = "Full verified current-season log" if full_log else "Verified recent-game sample"
    return (
        f'<div class="kpy2-note" style="margin-bottom:8px">{_e(scope_note)} · result is measured against the current displayed line.</div>'
        '<div class="kpy2-tablewrap"><table class="kpy2-table"><thead><tr>'
        '<th>WEEK</th><th>H/A</th><th>OPP</th><th>YDS</th><th>ATT</th><th>CMP</th><th>TD</th><th>INT</th><th>VS LINE</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _hit_counts(rows: list[dict[str, Any]], line: Any) -> tuple[int, int, int, int]:
    l = _num(line)
    if l is None:
        return 0, 0, 0, 0
    over = under = push = sample = 0
    for row in rows:
        y = _num(row.get("passing_yards"))
        if y is None:
            continue
        sample += 1
        if y > l:
            over += 1
        elif y < l:
            under += 1
        else:
            push += 1
    return over, under, push, sample


def _hit_card(label: str, rows: list[dict[str, Any]], line: Any) -> str:
    over, under, push, sample = _hit_counts(rows, line)
    if not sample:
        return f'<div class="kpy2-box"><div class="kpy2-label">{_e(label)}</div><div class="kpy2-value">NOT AVAILABLE</div><div class="kpy2-note">Verified game rows unavailable.</div></div>'
    push_text = f" · {push} push" if push else ""
    return (
        f'<div class="kpy2-box"><div class="kpy2-label">{_e(label)}</div>'
        f'<div class="kpy2-value"><span class="kpy2-good">O {over}/{sample}</span> · <span class="kpy2-bad">U {under}/{sample}</span></div>'
        f'<div class="kpy2-note">Current line {_fmt(line)}{_e(push_text)}</div></div>'
    )


def _hit_rate_lab(detail: dict[str, Any], line: Any) -> str:
    season = [dict(row) for row in (detail.get("season_game_log") or []) if isinstance(row, dict)]
    fallback = [dict(row) for row in ((detail.get("profile") or {}).get("recent_games") or []) if isinstance(row, dict)]
    source = season or list(reversed(fallback))
    last5 = source[-5:]
    last10 = source[-10:] if season else []
    home = [row for row in season if _text(row.get("home_away")).upper() == "HOME"]
    away = [row for row in season if _text(row.get("home_away")).upper() == "AWAY"]
    cards = [
        _hit_card("LAST 5", last5, line),
        _hit_card("LAST 10", last10, line),
        _hit_card("SEASON", season, line),
        _hit_card("HOME", home, line),
        _hit_card("AWAY", away, line),
    ]
    return f'<div class="kpy2-five">{"".join(cards)}</div>'


def _books(detail: dict[str, Any]) -> str:
    market = detail.get("market") or {}
    books = [row for row in (market.get("books") or []) if isinstance(row, dict)]
    if not books:
        return _unavailable("No verified two-way sportsbook observation is available for this player.")
    rows = []
    for book in books:
        rows.append(
            "<tr>"
            f"<td>{_e(book.get('sportsbook') or book.get('provider'))}</td>"
            f"<td>{_fmt(book.get('line'))}</td><td>{_odds(book.get('over_odds'))}</td><td>{_odds(book.get('under_odds'))}</td>"
            f"<td>{_e(book.get('source_timestamp') or 'NOT AVAILABLE')}</td></tr>"
        )
    return (
        '<div class="kpy2-tablewrap"><table class="kpy2-table"><thead><tr>'
        '<th>SPORTSBOOK</th><th>LINE</th><th>OVER</th><th>UNDER</th><th>OBSERVED</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _movement(detail: dict[str, Any]) -> str:
    movement = (detail.get("market") or {}).get("line_movement") or {}
    if not movement.get("ready"):
        return _unavailable("Verified same-book opening-to-current line history is not available yet.")
    delta = _num(movement.get("delta"))
    delta_text = "NOT AVAILABLE" if delta is None else f"{delta:+.1f}"
    return (
        '<div class="kpy2-three">'
        f'{_metric("OPEN " + _fmt(movement.get("open_line")), _e(movement.get("sportsbook") or "SPORTSBOOK"))}'
        f'{_metric("CURRENT " + _fmt(movement.get("current_line")), delta_text, "line move")}'
        f'{_metric("DIRECTION", "UP" if (delta or 0) > 0 else ("DOWN" if (delta or 0) < 0 else "FLAT"), delta_text)}'
        '</div>'
    )


def _defense(detail: dict[str, Any]) -> str:
    d = detail.get("pass_defense") or {}
    if not d:
        return _unavailable("Verified opponent pass-defense profile is not available.")
    return (
        '<div class="kpy2-grid">'
        + _metric("PASS-YDS RANK", _fmt(d.get("rank"),0), _text(d.get("grade")) or "CHECK")
        + _metric("YDS / GAME", _fmt(d.get("pass_yards_allowed_per_game")))
        + _metric("ATT / GAME", _fmt(d.get("passing_attempts_allowed_per_game")))
        + _metric("CMP% ALLOWED", _fmt(d.get("completion_pct_allowed")) + ("%" if _num(d.get("completion_pct_allowed")) is not None else ""))
        + _metric("YPA ALLOWED", _fmt(d.get("yards_per_attempt_allowed"),2))
        + _metric("RECENT 3 YDS", _fmt(d.get("recent3_pass_yards_allowed")))
        + _metric("SACK RATE", _fmt(d.get("sack_rate_generated")) + ("%" if _num(d.get("sack_rate_generated")) is not None else ""))
        + '</div>'
    )


def _history(detail: dict[str, Any]) -> str:
    h = detail.get("qb_vs_team_history") or {}
    if not h.get("available"):
        return _unavailable(h.get("message") or "No verified prior quarterback-versus-defense history.")
    games = [row for row in (h.get("games_detail") or []) if isinstance(row, dict)]
    summary = (
        '<div class="kpy2-grid">'
        + _metric("PRIOR GAMES", _fmt(h.get("games"),0))
        + _metric("YDS / GAME", _fmt(h.get("avg_passing_yards")))
        + _metric("ATT / GAME", _fmt(h.get("avg_attempts")))
        + _metric("CMP%", _fmt(h.get("completion_pct")) + ("%" if _num(h.get("completion_pct")) is not None else ""))
        + '</div>'
    )
    if not games:
        return summary + _unavailable("Verified prior-game detail rows are not available.")
    body = []
    for row in reversed(games):
        body.append(
            "<tr>"
            f"<td>{_e(row.get('opponent') or detail.get('opponent_abbr'))}</td><td>{_fmt(row.get('passing_yards'),0)}</td>"
            f"<td>{_fmt(row.get('attempts'),0)}</td><td>{_fmt(row.get('completions'),0)}</td>"
            f"<td>{_fmt(row.get('pass_tds'),0)}</td><td>{_fmt(row.get('interceptions'),0)}</td></tr>"
        )
    table = '<div class="kpy2-tablewrap" style="margin-top:12px"><table class="kpy2-table"><thead><tr><th>OPP</th><th>YDS</th><th>ATT</th><th>CMP</th><th>TD</th><th>INT</th></tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'
    return summary + table


def _volume(detail: dict[str, Any]) -> str:
    p = detail.get("profile") or {}
    c = detail.get("context_projection") or {}
    dist = detail.get("distribution") or {}
    return (
        '<div class="kpy2-grid">'
        + _metric("SEASON GAMES", _fmt(p.get("games"),0))
        + _metric("PASS YDS / GAME", _fmt(p.get("passing_yards_per_game")))
        + _metric("ATT / GAME", _fmt(p.get("attempts_per_game")))
        + _metric("COMPLETION", _fmt(p.get("completion_pct")) + ("%" if _num(p.get("completion_pct")) is not None else ""))
        + _metric("YARDS / ATT", _fmt(p.get("yards_per_attempt"),2))
        + _metric("PASS TD", _fmt(p.get("pass_tds"),0))
        + _metric("INT", _fmt(p.get("interceptions"),0))
        + _metric("PRESSURE ADJ", (_fmt(c.get("pressure_adjustment_yards")) + " yd") if _num(c.get("pressure_adjustment_yards")) is not None else "NOT AVAILABLE")
        + _metric("MODEL SIGMA", (_fmt(dist.get("sigma_yards")) + " yd") if _num(dist.get("sigma_yards")) is not None else "NOT AVAILABLE", _text(dist.get("confidence")) or "CHECK")
        + '</div>'
    )


def _conditions(detail: dict[str, Any]) -> str:
    g = detail.get("game_environment") or {}
    if not g.get("verified"):
        return _unavailable(g.get("reason") or "Verified game-condition data is not available.")
    temp = _fmt(g.get("temperature_f"),0) + ("°F" if _num(g.get("temperature_f")) is not None else "")
    wind = _fmt(g.get("wind_mph"),0) + (" mph" if _num(g.get("wind_mph")) is not None else "")
    return (
        '<div class="kpy2-grid">'
        + _metric("VENUE", _text(g.get("venue")) or "NOT AVAILABLE")
        + _metric("ROOF", _text(g.get("roof")) or "NOT AVAILABLE")
        + _metric("SURFACE", _text(g.get("surface")) or "NOT AVAILABLE")
        + _metric("TEMPERATURE", temp)
        + _metric("WIND", wind)
        + _metric("REST DAYS", _fmt(g.get("rest_days"),0))
        + '</div>'
        + f'<div class="kpy2-note">Source: {_e(g.get("source") or "Kyre Sports API verified environment routing")}</div>'
    )


def _availability(detail: dict[str, Any]) -> str:
    a = detail.get("availability") or {}
    if not a.get("verified"):
        return _unavailable(a.get("reason") or "Verified player/lineup availability is not available for this request.")
    fields = []
    for label, key in (("STATUS","status"),("QB","quarterback"),("RECEIVERS","receivers"),("OFFENSIVE LINE","offensive_line"),("OPP SECONDARY","opponent_secondary")):
        value = _text(a.get(key))
        if value:
            fields.append(_metric(label, value))
    return '<div class="kpy2-grid">' + "".join(fields) + '</div>' if fields else _unavailable("Availability was marked verified but no displayable fields were supplied.")


def _why(detail: dict[str, Any]) -> str:
    support = detail.get("page1_decision_support") or {}
    thesis = support.get("thesis") or {}
    narrative = _text(thesis.get("narrative"))
    factors = [row for row in (thesis.get("factors") or []) if isinstance(row, dict)]
    if not narrative and not factors:
        return _unavailable("Verified decision-support factors are not available.")
    parts = [f'<div class="kpy2-note" style="font-size:14px;color:#d8e6f1;margin-bottom:10px">{_e(narrative)}</div>'] if narrative else []
    for factor in factors:
        dot = " y" if factor.get("positive") else ""
        parts.append(
            f'<div class="kpy2-factor"><span class="kpy2-dot{dot}"></span><div><b>{_e(factor.get("label") or "Verified factor")}</b><div class="kpy2-note">{_e(factor.get("detail"))}</div></div></div>'
        )
    return "".join(parts)


def _risks(detail: dict[str, Any]) -> str:
    risks = [str(item).strip() for item in ((detail.get("page1_decision_support") or {}).get("risk_flags") or []) if str(item).strip()]
    if not risks:
        return _unavailable("No additional verified risk flags are currently exposed by Kyre Sports API.")
    return "".join(f'<div class="kpy2-risk">{_e(item)}</div>' for item in risks)


def _final_decision(card: dict[str, Any], detail: dict[str, Any]) -> str:
    thesis = (detail.get("page1_decision_support") or {}).get("thesis") or {}
    market = detail.get("market") or {}
    evaluation = detail.get("market_evaluation") or {}
    ready = bool(thesis.get("ready")) and bool(market.get("ready"))
    side = _text(thesis.get("side")).upper() if ready else "NO BET"
    if side not in {"OVER", "UNDER"}:
        side = "NO BET"
    probability = evaluation.get("model_over_probability") if side == "OVER" else (evaluation.get("model_under_probability") if side == "UNDER" else None)
    line = market.get("line")
    side_line = f"{side} {_fmt(line)}" if side in {"OVER", "UNDER"} else "NO BET"
    reason = _text(thesis.get("narrative")) if ready else (_text(market.get("reason")) or "A verified two-way market and evidence-backed side are required before Kyre issues a betting lean.")
    return (
        '<div class="kpy2-decision">'
        f'<div class="kpy2-label">FINAL DECISION</div><div class="kpy2-side">{_e(side_line)}</div>'
        '<div class="kpy2-grid">'
        + _metric("SPORTSBOOK", _text(market.get("sportsbook")) or "NOT AVAILABLE")
        + _metric("PROBABILITY", _pct(probability))
        + _metric("CONFIDENCE", _text(card.get("confidence") or (detail.get("distribution") or {}).get("confidence")) or "CHECK")
        + _metric("STRENGTH", _text(thesis.get("strength")) or "CHECK")
        + _metric("KYRE PROJECTION", _fmt(card.get("projection_yards")))
        + _metric("EDGE", (_fmt(card.get("edge_yards")) + " yd") if _num(card.get("edge_yards")) is not None else "NOT AVAILABLE")
        + '</div>'
        f'<div class="kpy2-note" style="margin-top:12px">{_e(reason)}</div></div>'
    )


def build_page2_html(card: dict[str, Any]) -> str:
    detail = card.get("detail") or {}
    visuals = detail.get("identity_visuals") or {}
    market = detail.get("market") or {}
    evaluation = detail.get("market_evaluation") or {}
    qb = _text(card.get("qb_name") or detail.get("qb_name")) or "Quarterback"
    team = _text(card.get("team_name") or detail.get("team_name") or card.get("team_abbr"))
    opponent = _text(card.get("opponent_abbr") or detail.get("opponent_abbr"))
    face = _text(card.get("headshot_url") or visuals.get("headshot_url"))
    logo = _text(card.get("team_logo_url") or visuals.get("team_logo_url"))
    face_html = f'<img class="kpy2-face" src="{_e(face)}" alt="{_e(qb)}">' if face else '<div class="kpy2-face"></div>'
    logo_html = f'<img class="kpy2-teamlogo" src="{_e(logo)}" alt="{_e(team)} logo">' if logo else ""
    line = market.get("line") if market.get("ready") else (card.get("market") or {}).get("line")
    sportsbook = _text(market.get("sportsbook") or (card.get("market") or {}).get("sportsbook")) or "NOT AVAILABLE"
    timestamp = _text(market.get("source_timestamp") or (card.get("market") or {}).get("timestamp")) or "NOT AVAILABLE"
    projection = card.get("projection_yards")
    edge = card.get("edge_yards")
    over = evaluation.get("model_over_probability") if evaluation.get("ready") else card.get("over_probability")
    under = evaluation.get("model_under_probability") if evaluation.get("ready") else card.get("under_probability")

    hero = (
        '<div class="kpy2-hero"><div class="kpy2-hero-top">'
        f'{face_html}<div><div class="kpy2-kicker">QB ANALYSIS COMMAND CENTER</div><div class="kpy2-name">{_e(qb)}</div>'
        f'<div class="kpy2-sub">{_e(team)} · vs {_e(opponent)} · {_e(card.get("home_away"))} · {_e(card.get("game_date"))} {_e(card.get("game_time"))}</div></div>{logo_html}</div>'
        '<div class="kpy2-grid">'
        + _metric("MARKET LINE", _fmt(line), sportsbook)
        + _metric("KYRE PROJECTION", _fmt(projection), ((_fmt(edge) + " yd edge") if _num(edge) is not None else "edge NOT AVAILABLE"))
        + _metric("OVER", _pct(over), _odds(market.get("over_odds")))
        + _metric("UNDER", _pct(under), _odds(market.get("under_odds")))
        + '</div>'
        f'<div class="kpy2-note">Market observed: {_e(timestamp)} · canonical player: {_e(card.get("player_id") or detail.get("player_id"))}</div></div>'
    )

    market_model = (
        '<div class="kpy2-section"><div class="kpy2-title">MARKET & MODEL</div><div class="kpy2-grid">'
        + _metric("SPORTSBOOK", sportsbook)
        + _metric("LINE", _fmt(line))
        + _metric("OVER PRICE", _odds(market.get("over_odds")))
        + _metric("UNDER PRICE", _odds(market.get("under_odds")))
        + _metric("OVER PROB", _pct(over))
        + _metric("UNDER PROB", _pct(under))
        + _metric("MODEL GRADE", _text(evaluation.get("grade")) or "CHECK")
        + _metric("CONFIDENCE", _text(card.get("confidence") or (detail.get("distribution") or {}).get("confidence")) or "CHECK")
        + '</div></div>'
    )

    return (
        '<div class="kpy2-shell">'
        + hero
        + market_model
        + '<div class="kpy2-section"><div class="kpy2-title">RECENT GAME LOG</div>' + _game_table(detail, line) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">HIT RATE LAB</div>' + _hit_rate_lab(detail, line) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">MATCHUP & PASS DEFENSE</div>' + _defense(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">QB VS DEFENSE HISTORY</div>' + _history(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">LINE MOVEMENT & SPORTSBOOKS</div>' + _movement(detail) + '<div style="height:12px"></div>' + _books(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">VOLUME & EFFICIENCY</div>' + _volume(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">GAME CONDITIONS</div>' + _conditions(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">AVAILABILITY</div>' + _availability(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">WHY KYRE LEANS</div>' + _why(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">WHAT COULD MAKE THIS BET LOSE?</div>' + _risks(detail) + '</div>'
        + '<div class="kpy2-section"><div class="kpy2-title">FINAL DECISION</div>' + _final_decision(card, detail) + '</div>'
        + '<div class="kpy2-footer">Kyre Sports API · canonical identity · sportsbook-specific observations · no missing-to-zero conversion</div></div>'
    )


def render_page2(st: Any, card: dict[str, Any]) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<a class="kpy2-back" href="?">← All Quarterbacks</a>', unsafe_allow_html=True)
    st.markdown(build_page2_html(card), unsafe_allow_html=True)


__all__ = ["CSS", "build_page2_html", "render_page2"]
