'''Pure evidence composer for NBA PRA Page 2 Insights V1.

This module performs no I/O. It only turns already-verified Page 2 mappings into
structured analyst copy. Provider routing and projection ownership remain
outside this module.
'''
from __future__ import annotations

from statistics import mean
from typing import Any, Mapping


INSIGHTS_VERSION = "API2_NBA_PRA_PAGE2_INSIGHTS_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if number is None:
        return "—"
    return f"{number:.{digits}f}"


def _signed(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    return f"{number:+.1f}"


def _display_form(model: Mapping[str, Any]) -> Mapping[str, Any]:
    current = model.get("current") if isinstance(model.get("current"), Mapping) else {}
    if int(current.get("sample") or 0) > 0:
        return current
    prior = model.get("prior") if isinstance(model.get("prior"), Mapping) else {}
    if int(prior.get("sample") or 0) > 0:
        return prior
    return current


def _game_pra(row: Mapping[str, Any]) -> float | None:
    values = [_number(row.get(field)) for field in ("points", "rebounds", "assists")]
    if any(value is None for value in values):
        return None
    return float(sum(value for value in values if value is not None))


def _verified_games(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    current = list(profile.get("current_games") or [])
    source = current if current else list(profile.get("prior_games") or [])
    games: list[dict[str, Any]] = []
    for row in source:
        if not isinstance(row, Mapping):
            continue
        pra = _game_pra(row)
        if pra is None:
            continue
        games.append({**dict(row), "pra": pra})
    return games


def _exact_opponent_games(profile: Mapping[str, Any], opponent: str) -> list[dict[str, Any]]:
    target = _text(opponent).casefold()
    if not target:
        return []
    rows: list[dict[str, Any]] = []
    for raw in list(profile.get("current_games") or []) + list(profile.get("prior_games") or []):
        if not isinstance(raw, Mapping) or _text(raw.get("opponent")).casefold() != target:
            continue
        pra = _game_pra(raw)
        if pra is not None:
            rows.append({**dict(raw), "pra": pra})
    return rows


def _side_probability(result: Mapping[str, Any], lean: str) -> float | None:
    if lean == "UNDER":
        direct = _number(result.get("under_probability"))
        if direct is not None:
            return direct
        over = _number(result.get("over_probability"))
        return None if over is None else 1.0 - over
    if lean == "OVER":
        direct = _number(result.get("over_probability"))
        if direct is not None:
            return direct
        under = _number(result.get("under_probability"))
        return None if under is None else 1.0 - under
    return None


def _section(title: str, body: str) -> dict[str, str]:
    return {"title": title, "body": body}


def _recent_form_section(
    player_name: str,
    profile: Mapping[str, Any],
    model: Mapping[str, Any],
    active_line: float | None,
) -> dict[str, str] | None:
    games = _verified_games(profile)
    if not games:
        return None
    recent = games[:5]
    average = mean(row["pra"] for row in recent)
    pieces = [
        f"Across the {len(recent)} most recent verified games, {player_name} averaged {average:.1f} PRA."
    ]
    if active_line is not None:
        hits = sum(1 for row in recent if row["pra"] > active_line)
        pushes = sum(1 for row in recent if row["pra"] == active_line)
        hit_line = f"The active {active_line:.1f} threshold was cleared in {hits} of {len(recent)} games"
        if pushes:
            hit_line += f", with {pushes} push{'es' if pushes != 1 else ''}"
        pieces.append(hit_line + ".")
    form = _display_form(model)
    minutes = _number(form.get("minutes"))
    if minutes is not None:
        pieces.append(f"Recent verified playing time is {minutes:.1f} minutes per game across the active model sample.")
    l5 = _number(form.get("l5"))
    l10 = _number(form.get("l10"))
    if l5 is not None and l10 is not None:
        direction = "above" if l5 > l10 else "below" if l5 < l10 else "even with"
        pieces.append(f"The verified L5 PRA mark is {l5:.1f}, {direction} the L10 mark of {l10:.1f}.")
    return _section("RECENT FORM", " ".join(pieces))


def _role_section(
    profile: Mapping[str, Any],
    team: str,
    model: Mapping[str, Any],
) -> dict[str, str] | None:
    usage = _number(profile.get("usage_pct"))
    if usage is None:
        return None
    rank = profile.get("usage_rank")
    team_size = profile.get("usage_team_size")
    games = profile.get("usage_games")
    period = _text(profile.get("usage_period"))
    source = _text(profile.get("usage_source"))
    body = f"Verified usage is {usage:.1f}%"
    if rank is not None and team:
        body += f", ranking #{rank} on {team}"
    if isinstance(team_size, (int, float)):
        body += f" within a {int(team_size)}-player verified team cohort"
    body += "."
    details: list[str] = []
    if isinstance(games, (int, float)):
        details.append(f"{int(games)} verified games")
    if period:
        details.append(period)
    if source:
        details.append(source)
    if details:
        body += " Usage evidence: " + " • ".join(details) + "."
    minutes = _number(_display_form(model).get("minutes"))
    if minutes is not None:
        body += f" Recent verified minutes are {minutes:.1f} per game."
    return _section("ROLE & USAGE", body)


def _matchup_section(opponent: str, matchup: Mapping[str, Any]) -> dict[str, str] | None:
    pra_rank = matchup.get("pra_rank")
    grade = _text(matchup.get("matchup_grade"))
    component_rows: list[str] = []
    for key, label in (("points", "points"), ("rebounds", "rebounds"), ("assists", "assists")):
        raw = matchup.get(key)
        if isinstance(raw, Mapping) and raw.get("rank") is not None:
            component_rows.append(f"{label} #{raw.get('rank')}")
    if pra_rank is None and not grade and not component_rows:
        return None
    subject = opponent or "The verified opponent"
    pieces: list[str] = []
    if pra_rank is not None:
        pieces.append(f"{subject} carries a verified PRA matchup rank of #{pra_rank}" + (f" with a {grade} grade." if grade else "."))
    elif grade:
        pieces.append(f"{subject} carries a verified {grade} PRA matchup grade.")
    if component_rows:
        pieces.append("Component opponent ranks are " + ", ".join(component_rows) + ".")
    period = _text(matchup.get("evidence_period"))
    semantics = _text(matchup.get("rank_semantics"))
    if period:
        pieces.append(f"Evidence period: {period}.")
    if semantics:
        pieces.append(f"Rank context: {semantics}.")
    return _section("MATCHUP", " ".join(pieces))


def _history_section(
    player_name: str,
    profile: Mapping[str, Any],
    opponent: str,
    active_line: float | None,
) -> dict[str, str] | None:
    rows = _exact_opponent_games(profile, opponent)
    if not rows:
        return None
    average = mean(row["pra"] for row in rows)
    noun = "game" if len(rows) == 1 else "games"
    body = f"{player_name} has {len(rows)} verified {noun} against {opponent}, averaging {average:.1f} PRA in that exact-opponent sample."
    if active_line is not None:
        hits = sum(1 for row in rows if row["pra"] > active_line)
        misses = sum(1 for row in rows if row["pra"] < active_line)
        pushes = len(rows) - hits - misses
        body += f" At {active_line:.1f} PRA, that history is {hits} OVER / {misses} UNDER"
        if pushes:
            body += f" / {pushes} PUSH"
        body += "."
    latest = rows[0]
    date = _text(latest.get("game_date"))
    latest_label = f" on {date}" if date else ""
    body += f" The latest verified meeting{latest_label} produced {latest['pra']:.1f} PRA."
    return _section("PLAYER VS OPPONENT", body)


def _market_section(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    active_line: float | None,
) -> dict[str, str] | None:
    quote = context.get("current_quote") if isinstance(context.get("current_quote"), Mapping) else context.get("selected_quote")
    quote = quote if isinstance(quote, Mapping) else {}
    book = _text(quote.get("sportsbook"))
    projection = _number(model.get("projection"))
    edge = _number(line_result.get("edge"))
    lean = _text(line_result.get("lean")).upper()
    probability = _side_probability(line_result, lean)
    if not book and projection is None and active_line is None and edge is None:
        return None
    pieces: list[str] = []
    book_line = _number(quote.get("line"))
    if book and book_line is not None:
        pieces.append(f"{book} currently lists {book_line:.1f} PRA.")
    elif book:
        pieces.append(f"The active verified sportsbook is {book}.")
    if projection is not None and active_line is not None:
        sentence = f"Kyre's frozen projection is {projection:.1f} PRA versus the active {active_line:.1f} threshold"
        if edge is not None:
            sentence += f", a {_signed(edge)} PRA model edge"
        pieces.append(sentence + ".")
    if lean in {"OVER", "UNDER"} and probability is not None:
        pieces.append(f"The model leans {lean} with {probability * 100:.0f}% probability on that side at the active threshold.")
    elif lean:
        pieces.append(f"The current model decision is {lean}; no unsupported probability is added when verified variance is unavailable.")
    if context.get("line_moved"):
        selected = context.get("selected_quote") if isinstance(context.get("selected_quote"), Mapping) else {}
        selected_line = _number(selected.get("line"))
        current_line = _number(quote.get("line"))
        if selected_line is not None and current_line is not None:
            pieces.append(f"The same-book line moved from {selected_line:.1f} at selection to {current_line:.1f} now.")
        else:
            pieces.append("The verified sportsbook quote changed after the player was selected.")
    return _section("MARKET & MODEL EDGE", " ".join(pieces)) if pieces else None


def _risk_section(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
) -> dict[str, str] | None:
    pieces: list[str] = []
    status = _text(context.get("availability")).upper()
    if status and status not in {"UNVERIFIED", "NO VERIFIED INJURY FLAG", "AVAILABLE"}:
        pieces.append(f"Verified player availability is {status}.")
    elif status == "AVAILABLE":
        pieces.append("The player is verified AVAILABLE on the current availability feed.")
    if context.get("line_moved"):
        pieces.append("The sportsbook line moved after selection, so the current threshold should be judged separately from the original quote.")
    form = _display_form(model)
    sample = int(form.get("sample") or 0)
    if 0 < sample < 5:
        pieces.append(f"The active recent-history model sample is only {sample} games.")
    sigma = _number(model.get("sigma"))
    if sigma is not None and sigma >= 9.0:
        pieces.append(f"Verified PRA dispersion is wide at {sigma:.1f}, increasing outcome volatility around the threshold.")
    if not pieces:
        return None
    return _section("AVAILABILITY & RISK", " ".join(pieces))


def _game_situation_section(context: Mapping[str, Any]) -> dict[str, str] | None:
    game = context.get("game") if isinstance(context.get("game"), Mapping) else {}
    team = _text(context.get("team")).upper()
    opponent = _text(context.get("opponent")).upper()
    away = _text(game.get("away_tricode")).upper()
    home = _text(game.get("home_tricode")).upper()
    if not team or team not in {away, home}:
        return None
    if team == away:
        body = f"{team} is the road team"
        if home:
            body += f" at {home}"
    else:
        body = f"{team} is the home team"
        if away:
            body += f" against {away}"
    body += " in the verified scheduled matchup."
    if opponent and opponent not in {away, home}:
        body += f" Page 2 currently identifies {opponent} as the opponent."
    body += " Venue identity is context only; no home/road production advantage is inferred without a verified split."
    return _section("GAME SITUATION", body)


def _final_insight(
    sections: list[dict[str, str]],
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    active_line: float | None,
) -> tuple[str, str]:
    lean = _text(line_result.get("lean")).upper() or "PASS"
    threshold = f"{active_line:.1f}" if active_line is not None else "—"
    title = f"KYRE FINAL INSIGHT • {lean} {threshold} PRA" if lean in {"OVER", "UNDER"} else f"KYRE FINAL INSIGHT • PASS @ {threshold} PRA"
    projection = _number(model.get("projection"))
    edge = _number(line_result.get("edge"))
    probability = _side_probability(line_result, lean)
    player_name = _text(context.get("player_name")) or _text((context.get("player") or {}).get("player_name")) or "This player"
    sentences: list[str] = []
    if lean in {"OVER", "UNDER"} and projection is not None and active_line is not None:
        sentence = f"Kyre's frozen projection is {projection:.1f} PRA against {active_line:.1f}"
        if edge is not None:
            sentence += f", creating a {_signed(edge)} PRA model edge"
        if probability is not None:
            sentence += f" with {probability * 100:.0f}% probability on the {lean} side"
        sentences.append(sentence + ".")
    elif projection is not None and active_line is not None:
        sentences.append(f"Kyre does not have enough verified separation to force an Over/Under conclusion at {active_line:.1f} PRA; the frozen projection is {projection:.1f}.")
    section_map = {row["title"]: row["body"] for row in sections}
    if "RECENT FORM" in section_map:
        sentences.append(section_map["RECENT FORM"])
    if "ROLE & USAGE" in section_map:
        sentences.append(section_map["ROLE & USAGE"])
    if "MATCHUP" in section_map or "PLAYER VS OPPONENT" in section_map:
        matchup_bits = [section_map[key] for key in ("MATCHUP", "PLAYER VS OPPONENT") if key in section_map]
        sentences.append(" ".join(matchup_bits))
    if "AVAILABILITY & RISK" in section_map:
        sentences.append("The main verified caution is this: " + section_map["AVAILABILITY & RISK"])
    if not sentences:
        sentences.append(f"Verified evidence is currently too limited to build a stronger analyst conclusion for {player_name}.")
    if lean == "PASS" and len(sentences) == 1:
        sentences.append("Unavailable evidence is not inferred, and the current threshold should remain a pass until stronger verified separation exists.")
    return title, " ".join(sentences)


def build_nba_pra_insights(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> dict[str, Any]:
    """Build deterministic, evidence-backed Page 2 analyst copy from loaded data."""
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    player_name = _text(context.get("player_name")) or _text(profile.get("player_name")) or "The player"
    team = _text(context.get("team")).upper()
    opponent = _text(context.get("opponent")).upper()

    candidates = (
        _recent_form_section(player_name, profile, model, active_line),
        _role_section(profile, team, model),
        _matchup_section(opponent, matchup),
        _history_section(player_name, profile, opponent, active_line),
        _market_section(context, model, line_result, active_line),
        _risk_section(context, model),
        _game_situation_section(context),
    )
    sections = [row for row in candidates if row is not None and _text(row.get("body"))]
    final_title, final_body = _final_insight(sections, context, model, line_result, active_line)
    return {
        "version": INSIGHTS_VERSION,
        "sections": sections,
        "final_title": final_title,
        "final_body": final_body,
        "evidence_count": len(sections),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = ["INSIGHTS_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "build_nba_pra_insights"]
