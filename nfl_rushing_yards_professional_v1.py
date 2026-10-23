"""Deep Page 2 renderer for the Kyre Sports NFL Rushing Yards successor."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

CSS = r"""
<style>
.kry2{max-width:1180px;margin:0 auto;padding:4px 4px 34px;color:#edf7fc}.kry2hero,.kry2sec{border:1px solid #21465d;background:#091a27;border-radius:18px}.kry2hero{padding:16px;margin-bottom:12px}.kry2sec{padding:15px 17px;margin-bottom:12px}.kry2head{display:flex;align-items:center;gap:12px}.kry2face{width:64px;height:64px;border-radius:50%;object-fit:cover;border:3px solid #5bc0eb;background:#06131d}.kry2logo{width:48px;height:48px;object-fit:contain;margin-left:auto}.kry2kick,.kry2title,.kry2label{font-weight:950;letter-spacing:.12em}.kry2kick{font-size:.66rem;color:#72d4ff}.kry2name{font-size:1.55rem;font-weight:950}.kry2sub{font-size:.78rem;color:#a9bfcc;margin-top:4px}.kry2title{font-size:.78rem;margin-bottom:11px}.kry2grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.kry2metric,.kry2tile{border:1px solid #294d62;background:#071621;border-radius:13px;padding:10px;min-width:0}.kry2label{font-size:.55rem;color:#9db1be}.kry2value{font-size:1.04rem;font-weight:950;margin-top:4px}.kry2note{font-size:.68rem;color:#9eb3c0;margin-top:4px;line-height:1.35}.kry2twocol{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kry2tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.kry2tablewrap{overflow-x:auto;border:1px solid #29495d;border-radius:12px}.kry2table{width:100%;border-collapse:collapse;min-width:680px;font-size:.76rem}.kry2table th,.kry2table td{padding:8px 9px;border-bottom:1px solid #263f50;text-align:left;white-space:nowrap}.kry2table th{font-size:.57rem;letter-spacing:.08em;color:#9db1bf;background:#0d202e}.kry2status{display:inline-flex;border:1px solid #6c6134;border-radius:999px;padding:6px 9px;font-size:.69rem;font-weight:850;color:#f3cf7f;background:#211c0d}.kry2status.good{border-color:#37785f;color:#7de2b2;background:#0d2119}.kry2why{display:grid;gap:7px}.kry2why>div{border:1px solid #315066;border-left:4px solid #65c9f3;border-radius:10px;padding:9px 11px;font-size:.75rem}.kry2lineage{display:flex;gap:7px;flex-wrap:wrap}.kry2chip{border:1px solid #31536a;border-radius:999px;padding:5px 8px;font-size:.65rem;color:#c7dae5}.kry2back{display:inline-flex;margin-bottom:10px;text-decoration:none;color:#8bdcff;font-weight:850;font-size:.78rem}.kry2market{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.kry2sectionnote{font-size:.71rem;color:#a8bcc8;margin:-4px 0 10px}.kry2history{display:grid;gap:7px}.kry2historyrow{display:flex;justify-content:space-between;gap:12px;border:1px solid #29495d;border-radius:11px;padding:9px 11px;font-size:.74rem}.kry2historyrow strong{font-size:.8rem}
@media(max-width:900px){.kry2grid,.kry2market{grid-template-columns:repeat(2,1fr)}.kry2tiles{grid-template-columns:repeat(2,1fr)}}
@media(max-width:650px){.kry2twocol{grid-template-columns:1fr}.kry2sec{padding:12px}.kry2name{font-size:1.3rem}.kry2historyrow{flex-direction:column;gap:3px}}
</style>
"""


def _text(value: Any, fallback: str = "Pending verification") -> str:
    text = str(value if value is not None else "").strip()
    return text or fallback


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, digits: int = 1, fallback: str = "Pending verification") -> str:
    number = _num(value)
    return fallback if number is None else f"{number:.{digits}f}"


def _pct(value: Any) -> str:
    number = _num(value)
    return "Pending verification" if number is None else f"{round(number * 100):d}%"


def _odds(value: Any) -> str:
    number = _num(value)
    return "Pending verification" if number is None else f"{int(number):+d}"


def _metric(label: str, value: str, note: str = "") -> str:
    return f'<div class="kry2metric"><div class="kry2label">{escape(label)}</div><div class="kry2value">{escape(value)}</div>' + (f'<div class="kry2note">{escape(note)}</div>' if note else "") + "</div>"


def _semantic(status: str, display: str = "") -> str:
    mapping = {
        "FIRST_CAREER_MATCHUP": "First career matchup",
        "NO_PREVIOUS_MEETINGS": "No previous meetings",
        "MARKET_NOT_POSTED": "Market not posted yet",
        "LINE_CURRENTLY_OFF_BOARD": "Line currently off board",
        "NO_INJURY_DESIGNATION": "No injury designation",
        "PREGAME": "Pregame",
        "NO_QUALIFYING_GAMES": "No qualifying games",
        "DATA_UNAVAILABLE": "Verification pending",
    }
    return display or mapping.get(status, status.replace("_", " ").title() if status else "Verification pending")


def _recent_table(profile: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    rows = [row for row in (profile.get("recent_games") or []) if isinstance(row, dict)]
    if not rows:
        return '<span class="kry2status">No qualifying games</span>'
    line = _num(market.get("line"))
    body: list[str] = []
    for row in rows:
        yards = _num(row.get("rushing_yards"))
        result = "PREGAME MARKET PENDING" if line is None or yards is None else "OVER" if yards > line else "UNDER" if yards < line else "PUSH"
        body.append(
            "<tr>"
            f"<td>{escape(_text(row.get('game_date'), 'Date pending'))}</td>"
            f"<td>{escape(_text(row.get('opponent_abbr'), 'Opponent pending'))}</td>"
            f"<td><b>{escape(_fmt(yards, 0))}</b></td>"
            f"<td>{escape(_fmt(row.get('attempts'), 0))}</td>"
            f"<td>{escape(_fmt((yards / float(row['attempts'])) if yards is not None and _num(row.get('attempts')) not in {None, 0} else None, 2))}</td>"
            f"<td>{escape(result)}</td>"
            "</tr>"
        )
    return '<div class="kry2tablewrap"><table class="kry2table"><thead><tr><th>DATE</th><th>OPP</th><th>RUSH YDS</th><th>ATT</th><th>YPC</th><th>VS CURRENT LINE</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"


def _history(history: Mapping[str, Any]) -> str:
    status = _text(history.get("status"), "DATA_UNAVAILABLE")
    rows = [row for row in (history.get("games_detail") or []) if isinstance(row, dict)]
    if not rows:
        return f'<span class="kry2status">{escape(_semantic(status, _text(history.get("display"), "")))}</span>'
    body: list[str] = []
    for row in rows:
        body.append(
            '<div class="kry2historyrow">'
            f'<strong>{escape(_text(row.get("game_date"), "Date pending"))} · vs {escape(_text(row.get("opponent_abbr"), "Opponent pending"))}</strong>'
            f'<span>{escape(_fmt(row.get("rushing_yards"),0))} yds · {escape(_fmt(row.get("attempts"),0))} carries · {escape(_fmt(row.get("rushing_touchdowns"),0))} TD</span>'
            '</div>'
        )
    return '<div class="kry2history">' + "".join(body) + "</div>"


def build_rushing_detail_html(detail: Mapping[str, Any]) -> str:
    profile = detail.get("profile") if isinstance(detail.get("profile"), dict) else {}
    defense = detail.get("opponent_run_defense") if isinstance(detail.get("opponent_run_defense"), dict) else {}
    history = detail.get("matchup_history") if isinstance(detail.get("matchup_history"), dict) else {}
    market = detail.get("market") if isinstance(detail.get("market"), dict) else {}
    projection = detail.get("projection") if isinstance(detail.get("projection"), dict) else {}
    availability = detail.get("availability") if isinstance(detail.get("availability"), dict) else {}
    environment = detail.get("environment") if isinstance(detail.get("environment"), dict) else {}
    why = [str(item) for item in (detail.get("why_kyre_leans") or []) if str(item).strip()]
    lineage = detail.get("source_lineage") if isinstance(detail.get("source_lineage"), dict) else {}

    projection_yards = _num(projection.get("projection_yards"))
    line = _num(market.get("line"))
    edge = projection_yards - line if projection_yards is not None and line is not None else None
    role = _text(detail.get("role"), "RB")
    market_status = _text(market.get("status"), "MARKET_NOT_POSTED")
    market_display = _semantic(market_status)
    history_status = _text(history.get("status"), "DATA_UNAVAILABLE")
    availability_status = _text(availability.get("status"), "DATA_UNAVAILABLE")
    environment_status = _text(environment.get("status"), "PREGAME")

    workload = "".join([
        _metric("CARRIES / GAME", _fmt(profile.get("carries_per_game")), "Verified workload"),
        _metric("RUSH YDS / GAME", _fmt(profile.get("rushing_yards_per_game")), "Current-season sample"),
        _metric("YARDS / CARRY", _fmt(profile.get("yards_per_carry"), 2), "Rushing efficiency"),
        _metric("LAST 5 AVG", _fmt(profile.get("last5_average")), "Most recent qualifying games"),
    ])
    defense_tiles = "".join([
        _metric("RUSH YDS ALLOWED / GAME", _fmt(defense.get("rush_yards_allowed_per_game")), "Opponent defense"),
        _metric("YPC ALLOWED", _fmt(defense.get("yards_per_carry_allowed"), 2), "Opponent efficiency allowed"),
        _metric("RUSH ATT ALLOWED / GAME", _fmt(defense.get("rush_attempts_allowed_per_game")), "Opponent volume allowed"),
        _metric("DEFENSE RANK", f"#{int(_num(defense.get('rank')))}" if _num(defense.get("rank")) is not None else "Pending verification", _text(defense.get("grade"))),
    ])
    market_tiles = "".join([
        _metric("CURRENT LINE", _fmt(market.get("line")), _text(market.get("sportsbook"), market_display)),
        _metric("OVER PRICE", _odds(market.get("over_odds")), "Book-specific price"),
        _metric("UNDER PRICE", _odds(market.get("under_odds")), "Book-specific price"),
        _metric("EDGE", f"{edge:+.1f} yds" if edge is not None else market_display, "Projection minus same-book line"),
    ])
    advanced = "".join([
        _metric("EXPECTED CARRIES", _fmt(projection.get("expected_carries")), "Market-blind model input"),
        _metric("EXPECTED YPC", _fmt(projection.get("expected_yards_per_carry"), 2), "Player + opponent efficiency blend"),
        _metric("KYRE PROJECTION", _fmt(projection_yards), "Sportsbook influence: 0.0"),
        _metric("ROLE", role, _text(detail.get("role_source"), "Verified role derivation")),
    ])
    why_html = "".join(f"<div>{escape(item)}</div>" for item in why) or '<div>Decision evidence is still being verified. No unsupported lean is shown.</div>'
    lineage_html = "".join(f'<span class="kry2chip">{escape(str(key).replace("_"," ").title())}: {escape(_text(value))}</span>' for key, value in lineage.items())

    return (
        CSS + '<div class="kry2">'
        '<a class="kry2back" href="?sport=nfl&market=rushing-yards">← Back to Running Back Board</a>'
        '<div class="kry2hero"><div class="kry2head">'
        f'<div><div class="kry2kick">RB RUSHING ANALYSIS COMMAND CENTER</div><div class="kry2name">{escape(_text(detail.get("player_name"), "Running back"))}</div>'
        f'<div class="kry2sub">{escape(role)} · {escape(_text(detail.get("team_abbr"), "NFL"))} vs {escape(_text(detail.get("opponent_abbr"), "Opponent"))} · {escape(_text(detail.get("home_away"), "Pregame"))}</div></div>'
        '</div><div class="kry2grid" style="margin-top:13px">' + advanced + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">WORKLOAD</div><div class="kry2grid">' + workload + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">RECENT FORM</div><div class="kry2sectionnote">Verified rushing production only. Current market result is calculated only when a verified line exists.</div>' + _recent_table(profile, market) + '</div>'
        '<div class="kry2sec"><div class="kry2title">OPPONENT RUN DEFENSE</div><div class="kry2grid">' + defense_tiles + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">MATCHUP HISTORY</div><div class="kry2sectionnote">' + escape(_semantic(history_status, _text(history.get("display"), ""))) + '</div>' + _history(history) + '</div>'
        '<div class="kry2sec"><div class="kry2title">MARKET INTELLIGENCE</div><div class="kry2sectionnote">' + escape(market_display) + ' · sportsbook records remain independent.</div><div class="kry2market">' + market_tiles + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">GAME ENVIRONMENT</div><div class="kry2grid">' +
        _metric("STATE", _semantic(environment_status, _text(environment.get("display"), "")), "Upcoming games only") +
        _metric("KICKOFF", _text(environment.get("kickoff_et"), "Kickoff verification pending"), "Game is removed when kickoff passes") +
        _metric("HOME / AWAY", _text(detail.get("home_away"), "Pregame"), "Verified matchup context") +
        _metric("OPPONENT", _text(detail.get("opponent_abbr"), "Opponent pending"), "Canonical matchup identity") + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">AVAILABILITY</div><span class="kry2status">' + escape(_semantic(availability_status, _text(availability.get("display"), ""))) + '</span></div>'
        '<div class="kry2sec"><div class="kry2title">WHY KYRE LEANS</div><div class="kry2why">' + why_html + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">SOURCE LINEAGE</div><div class="kry2lineage">' + lineage_html + '</div></div>'
        '</div>'
    )


def render_page2(st: Any, card: Mapping[str, Any]) -> None:
    detail = card.get("detail") if isinstance(card.get("detail"), dict) else {}
    st.markdown(build_rushing_detail_html(detail), unsafe_allow_html=True)


__all__ = ["CSS", "build_rushing_detail_html", "render_page2"]
