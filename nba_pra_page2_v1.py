'''NBA PRA Page 2 V2 — S-tier selected-player intelligence deep dive.'''
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping

from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
from nba_pra_page1_model_v1 import project_pra
from nba_pra_page2_context_v1 import build_page2_context
from nba_pra_page2_line_lab_v1 import evaluate_line, line_steps
from nba_pra_page2_matchup_api_v1 import load_kyre_sports_api_nba_pra_matchup
from nba_pra_page2_matchup_v1 import build_matchup_summary
from nba_pra_runtime_v2 import (
    SESSION_LINE_LAB,
    SESSION_SELECTED_QUOTE,
    clear_page2_state,
    selected_player_key,
)

MODEL_VERSION = "NBA PRA PAGE 2/3 • PLAYER INTELLIGENCE V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fmt(value: Any, digits: int = 1, missing: str = "—") -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return missing


def _signed(value: Any) -> str:
    try:
        return f"{float(value):+.1f}"
    except (TypeError, ValueError):
        return "—"


def _price(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _display_form(model: Mapping[str, Any]) -> Mapping[str, Any]:
    current = model.get("current") or {}
    if int(current.get("sample") or 0) > 0:
        return current
    prior = model.get("prior") or {}
    if int(prior.get("sample") or 0) > 0:
        return prior
    return current


def _probability(result: Mapping[str, Any]) -> str:
    lean = _text(result.get("lean")).upper()
    probability = result.get("over_probability")
    if probability is None:
        return "—"
    shown = 1.0 - float(probability) if lean == "UNDER" else float(probability)
    return f"{shown * 100:.0f}%"


def game_log_rows(profile: Mapping[str, Any], active_line: float | None) -> list[dict[str, Any]]:
    games = list(profile.get("current_games") or []) or list(profile.get("prior_games") or [])
    out: list[dict[str, Any]] = []
    for game in games:
        try:
            pts = float(game.get("points"))
            reb = float(game.get("rebounds"))
            ast = float(game.get("assists"))
        except (TypeError, ValueError):
            continue
        pra = pts + reb + ast
        if active_line is None:
            result = "—"
        elif pra > float(active_line):
            result = "OVER"
        elif pra < float(active_line):
            result = "UNDER"
        else:
            result = "PUSH"
        out.append(
            {
                "date": game.get("game_date"),
                "opponent": game.get("opponent"),
                "points": pts,
                "rebounds": reb,
                "assists": ast,
                "pra": pra,
                "minutes": game.get("minutes"),
                "result": result,
            }
        )
    return out


def _hit_rate(rows: list[dict[str, Any]]) -> str:
    decided = [row for row in rows if row.get("result") in {"OVER", "UNDER"}]
    if not decided:
        return "—"
    over = sum(1 for row in decided if row["result"] == "OVER")
    return f"{over}/{len(decided)} OVER • {over / len(decided) * 100:.0f}%"


def _quote_cards(quotes: list[Mapping[str, Any]]) -> str:
    if not quotes:
        return '<div class="p2-empty">No verified sportsbook quote is currently available.</div>'
    cards: list[str] = []
    for quote in quotes:
        book = escape(_text(quote.get("sportsbook")) or "Verified book")
        observed = escape(_text(quote.get("observed_at_utc")) or "Timestamp not currently verified")
        cards.append(
            '<div class="p2-book">'
            f'<div class="p2-book-name">{book}</div>'
            f'<strong>{_fmt(quote.get("line"))}</strong>'
            f'<span>O {_price(quote.get("over_price"))} &nbsp;•&nbsp; U {_price(quote.get("under_price"))}</span>'
            f'<small>{observed}</small>'
            '</div>'
        )
    return "".join(cards)


def _rank_card(label: str, row: Mapping[str, Any]) -> str:
    rank = row.get("rank")
    grade = _text(row.get("grade")) or "NOT VERIFIED"
    grade_class = "good" if grade.upper() == "FAVORABLE" else "bad" if grade.upper() == "TOUGH" else "mid"
    return (
        '<div class="p2-rank-card">'
        f'<small>{escape(label)}</small>'
        f'<b>{"#" + str(rank) if rank is not None else "—"}</b>'
        f'<span class="p2-grade-{grade_class}">{escape(grade)}</span>'
        f'<em>{_fmt(row.get("value"))}</em>'
        '</div>'
    )


def _risk_items(context: Mapping[str, Any], model: Mapping[str, Any], matchup: Mapping[str, Any]) -> list[str]:
    risks: list[str] = []
    if context.get("line_moved"):
        risks.append("Sportsbook line moved since selection")
    form = _display_form(model)
    if int(form.get("sample") or 0) < 5:
        risks.append("Small recent history sample")
    try:
        if float(model.get("sigma")) >= 9.0:
            risks.append("Wide PRA variance")
    except (TypeError, ValueError):
        pass
    status = _text(context.get("availability")).upper()
    if status not in {"AVAILABLE", "UNVERIFIED", "NO VERIFIED INJURY FLAG", ""}:
        risks.append(f"Availability: {status}")
    if "PRESEASON" in _text(matchup.get("evidence_period")).upper():
        risks.append("Opponent rank uses preseason baseline")
    if not risks:
        risks.append("No verified elevated risk flag")
    return risks


def _risk_pills(items: list[str]) -> str:
    return "".join(f'<span class="p2-risk-pill">{escape(item)}</span>' for item in items)


def _game_log_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="p2-empty">Verified game log is not currently available.</div>'
    body: list[str] = []
    for row in rows:
        result = _text(row.get("result")).upper() or "—"
        row_class = "p2-row-over" if result == "OVER" else "p2-row-under" if result == "UNDER" else "p2-row-push"
        opponent = _text(row.get("opponent")) or "Not verified"
        body.append(
            f'<tr class="{row_class}">'
            f'<td>{escape(_text(row.get("date")) or "Not verified")}</td>'
            f'<td>{escape(opponent)}</td>'
            f'<td>{_fmt(row.get("points"), 0)}</td>'
            f'<td>{_fmt(row.get("rebounds"), 0)}</td>'
            f'<td>{_fmt(row.get("assists"), 0)}</td>'
            f'<td><b>{_fmt(row.get("pra"), 1)}</b></td>'
            f'<td>{_fmt(row.get("minutes"), 1)}</td>'
            f'<td><span class="p2-result p2-result-{result.casefold()}">{escape(result)}</span></td>'
            '</tr>'
        )
    return (
        '<div class="p2-table-wrap"><table class="p2-log">'
        '<thead><tr><th>DATE</th><th>OPP</th><th>PTS</th><th>REB</th><th>AST</th><th>PRA</th><th>MIN</th><th>RESULT</th></tr></thead>'
        '<tbody>' + "".join(body) + '</tbody></table></div>'
    )


def _prior_matchup_rows(profile: Mapping[str, Any], opponent: str, active_line: float | None) -> list[dict[str, Any]]:
    exact: list[Mapping[str, Any]] = []
    for row in list(profile.get("current_games") or []) + list(profile.get("prior_games") or []):
        if opponent and _text(row.get("opponent")).upper() == _text(opponent).upper():
            exact.append(row)
    if not exact:
        return []
    return game_log_rows({"current_games": exact, "prior_games": []}, active_line)


def _prior_matchup_html(profile: Mapping[str, Any], opponent: str, active_line: float | None) -> str:
    rows = _prior_matchup_rows(profile, opponent, active_line)
    if not rows:
        return '<span class="p2-muted">No verified prior matchup sample.</span>'
    latest = rows[0]
    return (
        f'<b>{len(rows)} verified game{"s" if len(rows) != 1 else ""}</b>'
        f'<span class="p2-muted">Latest: {_fmt(latest.get("pra"))} PRA • {escape(_text(latest.get("result")))}</span>'
    )


def _recent_strip(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<span class="p2-muted">Recent verified PRA sequence unavailable.</span>'
    chips: list[str] = []
    for row in rows[:10]:
        result = _text(row.get("result")).casefold()
        chips.append(f'<span class="p2-form-chip p2-chip-{escape(result)}">{_fmt(row.get("pra"))}</span>')
    return '<div class="p2-form-strip">' + "".join(chips) + '</div>'


def _usage_html(profile: Mapping[str, Any], team: str, minutes: Any) -> str:
    usage = profile.get("usage_pct")
    rank = profile.get("usage_rank")
    period = _text(profile.get("usage_period"))
    source = _text(profile.get("usage_source"))
    games = profile.get("usage_games")
    if usage is None:
        return (
            f'<div class="p2-context-value">{_fmt(minutes)} MIN</div>'
            '<span class="p2-muted">Usage % / team rank: Not currently verified.</span>'
        )
    rank_text = f"#{rank} ON {team}" if rank is not None and team else "TEAM RANK NOT VERIFIED"
    leader = '<span class="p2-leader">TEAM USAGE LEADER</span>' if rank == 1 else ""
    sample = f" • {int(games)} games" if isinstance(games, (int, float)) else ""
    provenance = " • ".join(piece for piece in (period, source) if piece)
    return (
        f'<div class="p2-usage-line"><b>{_fmt(usage)}%</b><strong>{escape(rank_text.upper())}</strong>{leader}</div>'
        f'<span class="p2-muted">{_fmt(minutes)} recent MIN{sample}</span>'
        + (f'<span class="p2-muted">{escape(provenance)}</span>' if provenance else "")
    )


def build_page2_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> str:
    profile = context.get("player") or {}
    form = _display_form(model)
    name = _text(context.get("player_name") or profile.get("player_name")) or "Player"
    team = _text(context.get("team")) or "NBA"
    opponent = _text(context.get("opponent")) or "Opponent not verified"
    position = _text(profile.get("position")) or "Position not verified"
    headshot = _text(profile.get("headshot"))
    team_logo = _text(context.get("team_logo"))
    opp_logo = _text(context.get("opponent_logo"))
    quote = context.get("current_quote") or context.get("selected_quote") or {}
    lean = _text(line_result.get("lean")).upper() or "PASS"
    score = _fmt(line_result.get("score"), 1, "—")
    logs = game_log_rows(profile, active_line)
    risks = _risk_items(context, model, matchup)
    matchup_history = _prior_matchup_html(profile, opponent, active_line)
    current_book_line = quote.get("line")
    book = _text(quote.get("sportsbook")) or "Verified book unavailable"
    availability = _text(context.get("availability")) or "UNVERIFIED"
    hero_image = f'<img class="p2-face" src="{escape(headshot)}" alt="{escape(name)}">' if headshot else '<div class="p2-face p2-face-empty">NBA</div>'
    team_image = f'<img class="p2-logo" src="{escape(team_logo)}" alt="{escape(team)} logo">' if team_logo else ""
    opp_image = f'<img class="p2-logo" src="{escape(opp_logo)}" alt="{escape(opponent)} logo">' if opp_logo else ""
    evidence_period = escape(_text(matchup.get("evidence_period")) or "Opponent evidence period not currently verified")
    rank_semantics = escape(_text(matchup.get("rank_semantics")) or "Opponent ranking semantics not currently verified")
    pra_rank = matchup.get("pra_rank")
    matchup_grade = _text(matchup.get("matchup_grade")) or "NOT VERIFIED"
    line_move = f'<div class="p2-alert">{escape(_text(context.get("line_moved_label")))}</div>' if context.get("line_moved") else ""

    return f'''
<div id="ks-nba-pra-page2-top"></div>
<section class="p2-hero">
  <div class="p2-hero-kicker">PLAYER COMMAND CENTER</div>
  <div class="p2-hero-main">
    <div class="p2-player">{hero_image}<div class="p2-player-copy">{team_image}<h1>{escape(name)}</h1><p>{escape(team)} • {escape(position)} • vs {escape(opponent)} {opp_image}</p><span class="p2-status">{escape(availability)}</span></div></div>
    <div class="p2-command-pick"><small>KYRE DECISION @ SELECTED THRESHOLD</small><strong>{escape(lean)} {_fmt(active_line)} PRA</strong><span>{_probability(line_result)} probability • {_signed(line_result.get("edge"))} edge</span></div>
    <div class="p2-quote"><small>CURRENT BOOK LINE • {escape(book)}</small><b>{_fmt(current_book_line)}</b><span>O {_price(quote.get("over_price"))} • U {_price(quote.get("under_price"))}</span></div>
  </div>
</section>{line_move}

<section class="p2-panel p2-verdict">
  <div class="p2-kicker">KYRE AI VERDICT</div>
  <div class="p2-verdict-grid">
    <div><small>DECISION</small><b>{escape(lean)}</b></div>
    <div><small>SELECTED THRESHOLD</small><b>{_fmt(active_line)}</b></div>
    <div><small>PROJECTION</small><b>{_fmt(model.get("projection"))}</b></div>
    <div><small>EDGE</small><b>{_signed(line_result.get("edge"))}</b></div>
    <div><small>PROBABILITY</small><b>{_probability(line_result)}</b></div>
    <div><small>KYRE SCORE</small><b>{score}</b><span>{escape(_text(line_result.get("tier")))}</span></div>
  </div>
  <p class="p2-note">Frozen Kyre projection is evaluated against the selected threshold. Sportsbook and opponent context remain evidence only and never alter the projection.</p>
</section>

<section class="p2-panel p2-line-lab-card">
  <div class="p2-kicker">FAST LINE LAB</div>
  <div class="p2-line-compare">
    <div><small>CURRENT BOOK LINE</small><b>{_fmt(current_book_line)}</b><span>{escape(book)}</span></div>
    <div class="p2-arrow">→</div>
    <div><small>SELECTED THRESHOLD</small><b>{_fmt(active_line)}</b><span>Instant local re-evaluation</span></div>
  </div>
  <p class="p2-note">LINE LAB changes only the threshold. Projection remains frozen • 0 external fetches per slider move.</p>
</section>

<section class="p2-panel">
  <div class="p2-kicker">SPORTSBOOK MARKET</div>
  <div class="p2-books">{_quote_cards(list(context.get("quotes") or []))}</div>
  <p class="p2-note">Each verified sportsbook quote keeps its own line, price, and timestamp. No conflicting lines are averaged.</p>
</section>

<section class="p2-panel">
  <div class="p2-kicker">RECENT FORM</div>
  <div class="p2-form-grid">
    <div><small>L5 PRA</small><b>{_fmt(form.get("l5"))}</b></div>
    <div><small>L10 PRA</small><b>{_fmt(form.get("l10"))}</b></div>
    <div><small>RECENT MIN</small><b>{_fmt(form.get("minutes"))}</b></div>
    <div><small>HIT RATE @ {_fmt(active_line)}</small><b>{escape(_hit_rate(logs))}</b></div>
  </div>
  {_recent_strip(logs)}
</section>

<section class="p2-panel">
  <div class="p2-kicker">OPPONENT ANALYTICS • OPPONENT RANK • {escape(opponent)}</div>
  <div class="p2-ranks">
    {_rank_card("Points", matchup.get("points") or {})}
    {_rank_card("Rebounds", matchup.get("rebounds") or {})}
    {_rank_card("Assists", matchup.get("assists") or {})}
    <div class="p2-rank-card p2-rank-pra"><small>PRA</small><b>{"#" + str(pra_rank) if pra_rank is not None else "—"}</b><span class="p2-grade-mid">{escape(matchup_grade)}</span><em>combined context</em></div>
  </div>
  <p class="p2-note">{rank_semantics} • {evidence_period} • PRA rank is a transparent mean of verified PTS/REB/AST ranks.</p>
</section>

<section class="p2-panel">
  <div class="p2-kicker">ANALYTICS CONTEXT</div>
  <div class="p2-context-grid">
    <div class="p2-context-card"><small>OPPONENT MATCHUP INTELLIGENCE</small><div class="p2-context-value">{escape(opponent)} • {"#" + str(pra_rank) if pra_rank is not None else "Not verified"}</div><span class="p2-muted">PRA matchup: {escape(matchup_grade)}</span></div>
    <div class="p2-context-card"><small>ROLE & USAGE • ROLE & MINUTES</small>{_usage_html(profile, team, form.get("minutes"))}</div>
    <div class="p2-context-card"><small>PLAYER VS OPPONENT HISTORY</small>{matchup_history}</div>
    <div class="p2-context-card"><small>INJURY / LINEUP IMPACT</small><div class="p2-context-value">{escape(availability)}</div><span class="p2-muted">No teammate impact is inferred without verified role evidence.</span></div>
  </div>
</section>

<section class="p2-panel p2-model">
  <div class="p2-kicker">MODEL SNAPSHOT • PROJECTION BREAKDOWN</div>
  <div class="p2-model-row"><div><small>FROZEN PROJECTION</small><b>{_fmt(model.get("projection"))} PRA</b></div><div><small>MODEL SAMPLE</small><b>{int(form.get("sample") or 0)}</b></div><div><small>RECENT MIN</small><b>{_fmt(form.get("minutes"))}</b></div></div>
  <div class="p2-risk-title">RISK FACTORS</div><div class="p2-risks">{_risk_pills(risks)}</div>
</section>

<section class="p2-panel">
  <div class="p2-kicker">FULL GAME LOG</div>
  <p class="p2-note">OVER / UNDER recalculates instantly against the active Line Lab threshold of <b>{_fmt(active_line)}</b>.</p>
  {_game_log_html(logs)}
</section>
'''


def _css() -> str:
    return '''<style>
.p2-wrap{max-width:1450px;margin:auto;color:#f3f9ff}.p2-hero,.p2-panel{background:linear-gradient(145deg,#071525,#06101d);border:1px solid rgba(108,210,255,.22);border-radius:16px;padding:14px;margin:9px 0;color:#eff9ff;box-shadow:0 12px 32px rgba(0,0,0,.20)}
.p2-hero{position:relative;overflow:hidden;background:radial-gradient(circle at 85% 20%,rgba(61,199,255,.10),transparent 30%),linear-gradient(145deg,#07182a,#050d18)}.p2-hero-kicker,.p2-kicker{font-size:11px;letter-spacing:.16em;font-weight:900;color:#69ddff;margin-bottom:10px}.p2-hero-main{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(230px,.8fr) minmax(170px,.45fr);gap:16px;align-items:center}.p2-player{display:flex;gap:14px;align-items:center}.p2-face{width:92px;height:92px;object-fit:cover;border-radius:18px;background:#0b1d2d;border:1px solid rgba(124,231,255,.22)}.p2-face-empty{display:grid;place-items:center}.p2-logo{width:27px;height:27px;object-fit:contain;vertical-align:middle;margin-right:7px}.p2-player h1{margin:2px 0;font-size:30px;line-height:1.05}.p2-player p{margin:7px 0;color:#a8bbcb}.p2-status{display:inline-block;padding:4px 8px;border-radius:999px;background:#0c2235;border:1px solid rgba(124,231,255,.20);font-size:11px;font-weight:800;color:#cfefff}.p2-command-pick{padding:13px;border-radius:14px;background:rgba(9,28,46,.78);border:1px solid rgba(124,231,255,.18)}.p2-command-pick small,.p2-quote small{display:block;color:#8ca6bb;font-size:10px;font-weight:800;letter-spacing:.06em}.p2-command-pick strong{display:block;font-size:24px;margin:5px 0}.p2-command-pick span{font-size:12px;color:#b5c7d6}.p2-quote{text-align:right}.p2-quote b{display:block;font-size:36px;color:#7ce7ff;line-height:1.05}.p2-quote span{color:#c5d4df}.p2-alert{background:#382405;border:1px solid rgba(255,184,77,.55);color:#ffd17c;padding:9px 12px;border-radius:11px;font-weight:900;margin:7px 0}
.p2-verdict-grid,.p2-form-grid,.p2-ranks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.p2-verdict-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.p2-verdict-grid>div,.p2-form-grid>div,.p2-rank-card,.p2-book,.p2-context-card,.p2-model-row>div{background:#091c2e;border:1px solid rgba(109,215,255,.16);padding:11px;border-radius:12px}.p2-verdict-grid small,.p2-form-grid small,.p2-rank-card small,.p2-context-card small,.p2-model-row small{display:block;color:#879fb2;font-size:10px;font-weight:800;letter-spacing:.04em}.p2-verdict-grid b,.p2-form-grid b,.p2-rank-card b,.p2-model-row b{font-size:21px}.p2-verdict-grid span{display:block;color:#8edfff;font-size:11px}.p2-note,.p2-muted{color:#91a8bb;font-size:12px}.p2-muted{display:block;margin-top:5px}
.p2-line-compare{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center}.p2-line-compare>div:not(.p2-arrow){background:#091c2e;border:1px solid rgba(109,215,255,.16);border-radius:12px;padding:11px}.p2-line-compare small{display:block;color:#879fb2;font-size:10px;font-weight:800}.p2-line-compare b{font-size:25px;display:block}.p2-line-compare span{color:#93aabd;font-size:11px}.p2-arrow{font-size:22px;color:#62d9ff}.p2-books{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:8px}.p2-book-name{font-weight:900;margin-bottom:5px}.p2-book strong{display:block;font-size:24px;color:#f4fbff}.p2-book span,.p2-book small{display:block;color:#9bb1c3}.p2-book small{font-size:9px;margin-top:5px;overflow-wrap:anywhere}
.p2-form-strip{display:flex;gap:6px;overflow-x:auto;padding-top:9px}.p2-form-chip{min-width:42px;text-align:center;border-radius:9px;padding:6px 7px;font-weight:800;font-size:12px;background:#0b2032;border:1px solid rgba(255,255,255,.08)}.p2-chip-over{background:rgba(42,181,112,.13);border-color:rgba(61,214,134,.25);color:#7df0ae}.p2-chip-under{background:rgba(222,73,73,.10);border-color:rgba(242,97,97,.20);color:#ff9e9e}.p2-chip-push{color:#ffd27a}.p2-rank-card span{display:block;font-weight:900;margin-top:2px}.p2-rank-card em{font-size:10px;color:#7d93a5}.p2-grade-good{color:#75edab}.p2-grade-bad{color:#ff9b9b}.p2-grade-mid{color:#78ddff}
.p2-context-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.p2-context-value{font-size:18px;font-weight:850;margin-top:4px}.p2-usage-line{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-top:4px}.p2-usage-line b{font-size:24px}.p2-usage-line strong{font-size:16px;color:#80e7ff}.p2-leader{background:rgba(49,207,124,.14);border:1px solid rgba(73,234,147,.28);color:#82f0b4;padding:3px 6px;border-radius:999px;font-size:9px;font-weight:900}.p2-model-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.p2-risk-title{margin-top:11px;font-size:10px;color:#879fb2;font-weight:900;letter-spacing:.08em}.p2-risks{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.p2-risk-pill{padding:5px 8px;border-radius:999px;background:#2b210b;border:1px solid rgba(235,176,74,.24);color:#ffd17a;font-size:11px;font-weight:700}
.p2-table-wrap{overflow:auto;max-height:720px;border:1px solid rgba(109,215,255,.12);border-radius:12px}.p2-log{width:100%;border-collapse:separate;border-spacing:0;font-size:12px;min-width:680px}.p2-log thead th{position:sticky;top:0;z-index:2;background:#081827;color:#b8ccdc;border-bottom:1px solid rgba(124,231,255,.18)}.p2-log th,.p2-log td{padding:8px 9px;text-align:left;border-bottom:1px solid rgba(255,255,255,.055)}.p2-row-over{background:rgba(32,174,101,.055)}.p2-row-under{background:rgba(210,63,63,.04)}.p2-row-over:hover,.p2-row-under:hover,.p2-row-push:hover{background:rgba(101,215,255,.07)}.p2-result{display:inline-block;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:900}.p2-result-over{background:rgba(43,198,117,.15);color:#7cf0ad}.p2-result-under{background:rgba(224,75,75,.13);color:#ff9d9d}.p2-result-push{background:rgba(236,178,70,.12);color:#ffd27d}.p2-empty{color:#91a8bb;padding:9px 0}.ks-p2-top{position:fixed;right:18px;bottom:24px;z-index:99999;background:#0b2a41;color:#8ee9ff!important;border:1px solid #4ccdf7;border-radius:999px;padding:10px 14px;text-decoration:none;font-weight:900;box-shadow:0 10px 30px rgba(0,0,0,.35)}
@media(max-width:980px){.p2-hero-main{grid-template-columns:1fr 1fr}.p2-player{grid-column:1/-1}.p2-verdict-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.p2-hero-main{grid-template-columns:1fr}.p2-player,.p2-command-pick,.p2-quote{grid-column:1}.p2-quote{text-align:left}.p2-verdict-grid,.p2-form-grid,.p2-ranks{grid-template-columns:repeat(2,minmax(0,1fr))}.p2-context-grid,.p2-model-row{grid-template-columns:1fr}.p2-face{width:76px;height:76px}.p2-player h1{font-size:23px}.p2-quote b{font-size:28px}.ks-p2-top{right:12px;bottom:74px}.p2-panel,.p2-hero{padding:12px}}
</style>'''


def default_line_for_context(context: Mapping[str, Any]) -> float | None:
    quote = context.get("selected_quote") or context.get("current_quote") or {}
    try:
        return float(quote.get("line"))
    except (TypeError, ValueError, AttributeError):
        return None


def _baseline_model(profile: Mapping[str, Any]) -> dict[str, Any]:
    model = project_pra(profile.get("current_games") or [], profile.get("prior_games") or [])
    baseline = profile.get("season_baseline") if isinstance(profile.get("season_baseline"), Mapping) else {}
    if model.get("projection") is None and baseline.get("pra") is not None:
        try:
            value = round(float(baseline.get("pra")), 1)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            model = {**model, "projection": value, "sigma": None, "basis": "VERIFIED SEASON BASELINE"}
    return model


def render_nba_pra_page2_v1(context: Mapping[str, Any] | None = None) -> None:
    import streamlit as st

    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<a class="ks-p2-top" href="#ks-nba-pra-page2-top">↑ TOP</a>', unsafe_allow_html=True)
    if st.button("← Back to PRA Board", key="nba-pra-p2-back", use_container_width=False):
        clear_page2_state(st.session_state)
        st.rerun()

    now = datetime.now(timezone.utc)
    if context is None:
        key = selected_player_key(st.session_state)
        if key is None:
            st.warning("No verified player selection. Return to the PRA board.")
            return
        with st.spinner("Loading selected NBA PRA intelligence…"):
            snapshot = load_page2_snapshot_v1(key, now=now)
        selected = st.session_state.get(SESSION_SELECTED_QUOTE)
        context = build_page2_context(snapshot, key, selected_quote=selected if isinstance(selected, Mapping) else None)

    if context.get("state") not in {"ready", "line_moved"}:
        st.warning("Selected player or PRA market is no longer available. Return to the PRA board.")
        return

    profile = context.get("player") or {}
    model = _baseline_model(profile)
    default_line = default_line_for_context(context)
    if default_line is None:
        st.warning("Verified PRA line unavailable. No test line was invented.")
        return

    # Expensive/provider-backed context is resolved exactly once on the parent run.
    # The fragment below contains only local threshold math and presentation.
    matchup_raw = load_kyre_sports_api_nba_pra_matchup(_text(context.get("opponent")), now_utc=now)
    matchup = build_matchup_summary(matchup_raw)
    options = line_steps(default_line, width=10.0)
    prior = st.session_state.get(SESSION_LINE_LAB)
    default = prior if prior in options else default_line if default_line in options else min(options, key=lambda value: abs(value - default_line))

    @st.fragment
    def _render_fast_line_lab() -> None:
        active_line = st.select_slider(
            "PRA Line Lab",
            options=options,
            value=default,
            key=SESSION_LINE_LAB,
            help="Instantly test alternate PRA thresholds. Projection stays frozen; no provider is called on slider movement.",
        )
        result = evaluate_line(model.get("projection"), model.get("sigma"), float(active_line))
        st.caption("⚡ FAST LINE LAB • 0 external fetches per slider move")
        st.markdown(
            '<div class="p2-wrap">' + build_page2_html(context, model, result, matchup, active_line=float(active_line)) + '</div>',
            unsafe_allow_html=True,
        )

    _render_fast_line_lab()
