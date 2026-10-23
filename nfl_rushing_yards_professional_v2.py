"""NFL Rushing Yards Page 2 Command Center V2.

Decision-first professional renderer. All deep data is loaded only through the
Kyre Sports API Page 2 detail gateway; the frontend never calls a provider.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from nfl_rushing_yards_detail_gateway_v2 import load_rushing_yards_detail

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "NFL RUSHING YARDS PAGE 2 COMMAND CENTER V2"

CSS = r"""
<style>
.kry2{max-width:1180px;margin:0 auto;padding:2px 4px 38px;color:#eef7fc}.kry2 *{box-sizing:border-box}.kry2back{display:inline-flex;margin:0 0 9px;color:#82d9ff;text-decoration:none;font-size:.72rem;font-weight:900}.kry2hero,.kry2sec{border:1px solid #244a60;background:linear-gradient(135deg,#091b29,#071620);border-radius:18px}.kry2hero{position:relative;overflow:hidden;padding:16px 17px 14px;margin-bottom:11px}.kry2rail{position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--team-accent,#68cdf7)}.kry2identity{display:flex;align-items:center;gap:11px}.kry2face,.kry2faceph{width:60px;height:60px;border-radius:50%;flex:0 0 60px;border:2px solid var(--team-accent,#68cdf7);background:#06131d}.kry2face{object-fit:cover}.kry2faceph{display:flex;align-items:center;justify-content:center;font-weight:950;color:#b9d9e8}.kry2idcopy{min-width:0;flex:1}.kry2kick,.kry2title,.kry2label{font-weight:950;letter-spacing:.11em}.kry2kick{font-size:.61rem;color:#71d4ff}.kry2name{font-size:1.45rem;line-height:1.05;font-weight:950;margin-top:3px}.kry2sub{font-size:.72rem;color:#a4bac7;margin-top:4px}.kry2logo{width:43px;height:43px;object-fit:contain}.kry2verdict{display:grid;grid-template-columns:1.15fr repeat(5,1fr);margin-top:13px;border:1px solid #31566d;border-radius:13px;overflow:hidden;background:#061520}.kry2cell{padding:9px 10px;min-width:0}.kry2cell+.kry2cell{border-left:1px solid #29485c}.kry2label{font-size:.49rem;color:#8fa8b7}.kry2value{font-size:.98rem;font-weight:950;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kry2note{font-size:.56rem;color:#849ba9;margin-top:2px}.kry2pos{color:#7de2b2}.kry2neg{color:#ff9b95}.kry2pending{color:#f0cd79}.kry2sec{padding:14px 15px;margin-bottom:10px}.kry2title{font-size:.70rem;margin-bottom:9px;color:#dcecf4}.kry2sectionnote{font-size:.66rem;color:#91a9b7;margin:-3px 0 9px}.kry2grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.kry2metric{border:1px solid #294b60;background:#061520;border-radius:11px;padding:9px;min-width:0}.kry2metric .kry2value{font-size:.91rem}.kry2twocol{display:grid;grid-template-columns:1fr 1fr;gap:9px}.kry2tablewrap{overflow-x:auto;border:1px solid #294a5e;border-radius:11px}.kry2table{width:100%;border-collapse:collapse;min-width:620px;font-size:.70rem}.kry2table th,.kry2table td{padding:7px 8px;border-bottom:1px solid #243e50;text-align:left;white-space:nowrap}.kry2table th{font-size:.52rem;letter-spacing:.08em;color:#90a7b5;background:#0b202e}.kry2pill{display:inline-flex;border:1px solid #5e5836;border-radius:999px;padding:5px 8px;color:#efcf7f;background:#1d190d;font-size:.64rem;font-weight:850}.kry2evidence{display:grid;gap:6px}.kry2evidence>div{border:1px solid #315266;border-left:4px solid #67cdf6;border-radius:10px;padding:8px 10px;font-size:.70rem;line-height:1.35}.kry2evidence .risk{border-left-color:#ff9b76}.kry2evidence .pending{border-left-color:#edc96f}.kry2summary{border:1px solid #39705d;background:#0b211b;border-radius:12px;padding:11px 12px;color:#baf0d3;font-size:.78rem;font-weight:800;line-height:1.45;margin-bottom:9px}.kry2lineage{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.kry2chip{border:1px solid #315269;border-radius:999px;padding:4px 7px;color:#bfd4df;font-size:.59rem}.kry2history{display:grid;gap:6px}.kry2historyrow{display:flex;justify-content:space-between;gap:10px;border:1px solid #29495c;border-radius:10px;padding:8px 9px;font-size:.68rem}.kry2split{display:grid;grid-template-columns:1.1fr .9fr;gap:9px}.kry2statusbar{margin-top:8px;font-size:.61rem;color:#9cb2bf}
@media(max-width:900px){.kry2verdict{grid-template-columns:repeat(3,1fr)}.kry2cell:nth-child(4),.kry2cell:nth-child(5),.kry2cell:nth-child(6){border-top:1px solid #29485c}.kry2cell:nth-child(4){border-left:0}.kry2grid{grid-template-columns:repeat(2,1fr)}.kry2split,.kry2twocol{grid-template-columns:1fr}}
@media(max-width:560px){.kry2hero,.kry2sec{padding:12px}.kry2verdict{grid-template-columns:repeat(2,1fr)}.kry2cell:nth-child(3),.kry2cell:nth-child(5){border-left:0}.kry2cell:nth-child(3),.kry2cell:nth-child(4),.kry2cell:nth-child(5),.kry2cell:nth-child(6){border-top:1px solid #29485c}.kry2name{font-size:1.25rem}.kry2face,.kry2faceph{width:52px;height:52px;flex-basis:52px}.kry2logo{width:34px;height:34px}.kry2historyrow{flex-direction:column;gap:3px}}
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


def _pct(value: Any, fallback: str = "Pending verification") -> str:
    number = _num(value)
    return fallback if number is None else f"{round(number * 100):d}%"


def _odds(value: Any) -> str:
    number = _num(value)
    return "Pending verification" if number is None else f"{int(number):+d}"


def _kickoff(value: Any) -> str:
    raw = _text(value, "")
    if not raw:
        return "Kickoff verification pending"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET)
        return dt.astimezone(ET).strftime("%a %-m/%-d · %-I:%M %p ET")
    except Exception:
        return raw


def _semantic(status: Any, display: str = "") -> str:
    key = _text(status, "")
    mapping = {
        "FIRST_CAREER_MATCHUP": "First career matchup",
        "NO_PREVIOUS_MEETINGS": "No previous meetings",
        "NO_COMPARABLE_MATCHUPS": "No comparable matchups",
        "MARKET_NOT_POSTED": "Market not posted yet",
        "LINE_CURRENTLY_OFF_BOARD": "Line currently off board",
        "OPENING_LINE_NOT_CAPTURED": "Opening line not captured by verified feed",
        "MOVEMENT_HISTORY_NOT_CAPTURED": "Movement history not captured by verified feed",
        "PERSONNEL_VERIFICATION_PENDING": "Personnel verification pending",
        "WEATHER_VERIFICATION_PENDING": "Weather verification pending",
        "GAME_SPREAD_NOT_VERIFIED": "Game spread verification pending",
        "GAME_TOTAL_NOT_VERIFIED": "Game total verification pending",
        "ADVANCED_SAMPLE_NOT_VERIFIED": "Advanced sample verification pending",
        "NO_QUALIFYING_GAMES": "No qualifying games",
        "PREGAME": "Pregame",
        "DATA_UNAVAILABLE": "Verification pending",
    }
    return display or mapping.get(key, key.replace("_", " ").title() if key else "Verification pending")


def _metric(label: str, value: str, note: str = "", value_class: str = "") -> str:
    cls = f"kry2value {value_class}".strip()
    return (
        '<div class="kry2metric">'
        f'<div class="kry2label">{escape(label)}</div>'
        f'<div class="{cls}">{escape(value)}</div>'
        + (f'<div class="kry2note">{escape(note)}</div>' if note else "")
        + '</div>'
    )


def _cell(label: str, value: str, note: str = "", value_class: str = "") -> str:
    cls = f"kry2value {value_class}".strip()
    return (
        '<div class="kry2cell">'
        f'<div class="kry2label">{escape(label)}</div>'
        f'<div class="{cls}">{escape(value)}</div>'
        + (f'<div class="kry2note">{escape(note)}</div>' if note else "")
        + '</div>'
    )


def _team_theme(team: Any) -> dict[str, str]:
    try:
        from nfl_rushing_yards_simple_rb_grid_v1 import team_theme
        return team_theme(team)
    except Exception:
        return {"primary": "#0B1B2A", "secondary": "#8AD8FF", "accent": "#68CDF7"}


def _recent_table(detail: Mapping[str, Any]) -> str:
    recent = detail.get("recent_form") if isinstance(detail.get("recent_form"), dict) else {}
    rows = [row for row in (recent.get("games_detail") or []) if isinstance(row, dict)]
    if not rows:
        profile = detail.get("profile") if isinstance(detail.get("profile"), dict) else {}
        rows = [row for row in (profile.get("recent_games") or []) if isinstance(row, dict)]
    if not rows:
        return '<span class="kry2pill">No qualifying games</span>'
    market = detail.get("market") if isinstance(detail.get("market"), dict) else {}
    line = _num(market.get("line")) if _text(market.get("status"), "") == "VERIFIED" else None
    body: list[str] = []
    for row in rows[:10]:
        yards = _num(row.get("rushing_yards"))
        attempts = _num(row.get("attempts"))
        ypc = (yards / attempts) if yards is not None and attempts not in {None, 0} else None
        result = "MARKET PENDING" if line is None or yards is None else "OVER" if yards > line else "UNDER" if yards < line else "PUSH"
        body.append(
            "<tr>"
            f"<td>{escape(_text(row.get('game_date'), 'Date pending'))}</td>"
            f"<td>{escape(_text(row.get('opponent_abbr'), 'Opponent pending'))}</td>"
            f"<td><b>{escape(_fmt(yards,0))}</b></td>"
            f"<td>{escape(_fmt(attempts,0))}</td>"
            f"<td>{escape(_fmt(ypc,2))}</td>"
            f"<td>{escape(result)}</td>"
            "</tr>"
        )
    return '<div class="kry2tablewrap"><table class="kry2table"><thead><tr><th>DATE</th><th>OPP</th><th>RUSH YDS</th><th>ATT</th><th>YPC</th><th>VS LINE</th></tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'


def _history_rows(rows: list[dict[str, Any]], empty_label: str) -> str:
    if not rows:
        return f'<span class="kry2pill">{escape(empty_label)}</span>'
    body: list[str] = []
    for row in rows[:5]:
        body.append(
            '<div class="kry2historyrow">'
            f'<strong>{escape(_text(row.get("game_date"), "Date pending"))} · {escape(_text(row.get("opponent_abbr"), "Opponent pending"))}</strong>'
            f'<span>{escape(_fmt(row.get("rushing_yards"),0))} yds · {escape(_fmt(row.get("attempts"),0))} carries</span>'
            '</div>'
        )
    return '<div class="kry2history">' + "".join(body) + '</div>'


def build_rushing_detail_html(detail: Mapping[str, Any]) -> str:
    profile = detail.get("profile") if isinstance(detail.get("profile"), dict) else {}
    projection = detail.get("projection") if isinstance(detail.get("projection"), dict) else {}
    defense = detail.get("opponent_run_defense") if isinstance(detail.get("opponent_run_defense"), dict) else {}
    history = detail.get("matchup_history") if isinstance(detail.get("matchup_history"), dict) else {}
    decision = detail.get("decision") if isinstance(detail.get("decision"), dict) else {}
    workload = detail.get("workload_intelligence") if isinstance(detail.get("workload_intelligence"), dict) else {}
    recent = detail.get("recent_form") if isinstance(detail.get("recent_form"), dict) else {}
    script = detail.get("game_script") if isinstance(detail.get("game_script"), dict) else {}
    comparable = detail.get("comparable_matchups") if isinstance(detail.get("comparable_matchups"), dict) else {}
    advanced = detail.get("advanced_efficiency") if isinstance(detail.get("advanced_efficiency"), dict) else {}
    market = detail.get("market_intelligence") if isinstance(detail.get("market_intelligence"), dict) else (detail.get("market") if isinstance(detail.get("market"), dict) else {})
    personnel = detail.get("personnel") if isinstance(detail.get("personnel"), dict) else {}
    final_read = detail.get("final_read") if isinstance(detail.get("final_read"), dict) else {}
    lineage = detail.get("source_lineage") if isinstance(detail.get("source_lineage"), dict) else {}

    team = _text(detail.get("team_abbr"), "NFL")
    theme = _team_theme(team)
    side = _text(decision.get("side"), "WAIT").upper()
    side_class = "kry2pos" if side == "OVER" else "kry2neg" if side == "UNDER" else "kry2pending"
    edge = _num(decision.get("edge"))
    edge_class = "kry2pos" if edge is not None and edge > 0 else "kry2neg" if edge is not None and edge < 0 else "kry2pending"
    market_line = decision.get("line") if decision else market.get("current_line")
    projected = decision.get("projection") if decision else projection.get("projection_yards")
    kickoff = detail.get("game_time") or (detail.get("environment") or {}).get("kickoff_et") if isinstance(detail.get("environment"), dict) else detail.get("game_time")

    face = _text(detail.get("headshot_url"), "")
    logo = _text(detail.get("team_logo_url"), "")
    face_html = f'<img class="kry2face" src="{escape(face)}" alt="">' if face else '<div class="kry2faceph">RB</div>'
    logo_html = f'<img class="kry2logo" src="{escape(logo)}" alt="">' if logo else ""

    verdict = "".join([
        _cell("KYRE LEAN", side, _text(decision.get("confidence"), "Market pending"), side_class),
        _cell("MARKET", _fmt(market_line), _text(market.get("sportsbook"), _semantic(market.get("status"))), "" if _num(market_line) is not None else "kry2pending"),
        _cell("PROJECTION", _fmt(projected), "Market-blind rushing yards"),
        _cell("EDGE", f"{edge:+.1f}" if edge is not None else "WAIT", "Projection minus verified line", edge_class),
        _cell("PROBABILITY", _pct(decision.get("probability")), "Model side probability", side_class if _num(decision.get("probability")) is not None else "kry2pending"),
        _cell("EXPECTED LOAD", f"{_fmt(decision.get('expected_carries'))} att", f"{_fmt(decision.get('expected_ypc'),2)} expected YPC"),
    ])

    workload_grid = "".join([
        _metric("SEASON ATT/G", _fmt(workload.get("season_carries_per_game"),1), "Verified rushing workload"),
        _metric("L3 ATT/G", _fmt(workload.get("l3_carries_per_game"),1), _text(workload.get("workload_trend"))),
        _metric("L5 ATT/G", _fmt(workload.get("l5_carries_per_game"),1), "Recent workload"),
        _metric("TEAM RUSH SHARE", _pct(workload.get("team_rush_attempt_share")), "Player share of team RB rush attempts"),
        _metric("RED-ZONE CARRIES", _fmt(workload.get("red_zone_carries"),0), "Verified play-by-play"),
        _metric("GOAL-LINE CARRIES", _fmt(workload.get("goal_line_carries"),0), "Inside opponent 5"),
        _metric("4Q CARRIES", _fmt(workload.get("fourth_quarter_carries"),0), "Fourth-quarter usage"),
        _metric("LEAD / TRAIL", f"{_fmt(workload.get('leading_carries'),0)} / {_fmt(workload.get('trailing_carries'),0)}", "Carries by score state"),
    ])

    recent_grid = "".join([
        _metric("L3 AVG", _fmt(recent.get("l3_average")), "Rushing yards"),
        _metric("L5 AVG", _fmt(recent.get("l5_average")), "Rushing yards"),
        _metric("MEDIAN", _fmt(recent.get("median")), "Season median"),
        _metric("FLOOR / CEILING", f"{_fmt(recent.get('floor'),0)} / {_fmt(recent.get('ceiling'),0)}", "Verified qualifying games"),
        _metric("CURRENT-LINE HIT RATE", _pct(recent.get("current_line_hit_rate")), _semantic(recent.get("hit_rate_status"))),
        _metric("SEASON AVG", _fmt(recent.get("season_average")), "Rushing yards"),
    ])

    defense_grid = "".join([
        _metric("RUSH YDS ALLOWED/G", _fmt(defense.get("rush_yards_allowed_per_game")), _text(defense.get("grade"))),
        _metric("RUSH ATT ALLOWED/G", _fmt(defense.get("rush_attempts_allowed_per_game")), "Opponent volume allowed"),
        _metric("YPC ALLOWED", _fmt(defense.get("yards_per_carry_allowed"),2), f"Rank {_fmt(defense.get('rank'),0)}"),
        _metric("EXPLOSIVE ALLOWED", _pct(defense.get("explosive_run_rate_allowed")), "10+ yard rush rate"),
        _metric("STUFF RATE", _pct(defense.get("stuff_rate")), "Rushes held to 0 or fewer"),
        _metric("SUCCESS ALLOWED", _pct(defense.get("success_rate_allowed")), "Verified play-by-play"),
        _metric("EPA / ATT ALLOWED", _fmt(defense.get("rush_epa_allowed_per_attempt"),3), "Rush EPA allowed"),
        _metric("DEFENSE GRADE", _text(defense.get("grade"), "CHECK"), "Current-season rushing sample"),
    ])

    script_grid = "".join([
        _metric("TEAM RUSH ATT/G", _fmt(script.get("team_rush_attempts_per_game")), "Verified game sample"),
        _metric("LEADING SHARE", _pct(script.get("player_leading_carry_share")), "Player carries while team leads"),
        _metric("TRAILING SHARE", _pct(script.get("player_trailing_carry_share")), "Player carries while team trails"),
        _metric("4Q SHARE", _pct(script.get("player_fourth_quarter_carry_share")), "Player fourth-quarter carry share"),
        _metric("SPREAD", _semantic(script.get("spread_status")), "No fabricated game line"),
        _metric("TOTAL", _semantic(script.get("total_status")), "No fabricated game total"),
        _metric("WEATHER", _semantic(script.get("weather_status")), "Venue/time verification required"),
        _metric("GAME STATE", _semantic((detail.get("environment") or {}).get("status") if isinstance(detail.get("environment"),dict) else "PREGAME"), _kickoff(kickoff)),
    ])

    advanced_grid = "".join([
        _metric("EXPLOSIVE RUN RATE", _pct(advanced.get("explosive_run_rate")), "10+ yard rushes"),
        _metric("STUFF RATE", _pct(advanced.get("stuff_rate")), "Rushes held to 0 or fewer"),
        _metric("SUCCESS RATE", _pct(advanced.get("success_rate")), "Verified play success"),
        _metric("RUSH EPA / ATT", _fmt(advanced.get("rush_epa_per_attempt"),3), "Efficiency per rushing attempt"),
        _metric("RED-ZONE CARRIES", _fmt(advanced.get("red_zone_carries"),0), "Season verified sample"),
        _metric("GOAL-LINE CARRIES", _fmt(advanced.get("goal_line_carries"),0), "Inside opponent 5"),
    ])

    history_rows = [row for row in (history.get("games_detail") or []) if isinstance(row, dict)]
    comp_rows = [row for row in (comparable.get("games_detail") or []) if isinstance(row, dict)]
    history_html = _history_rows(history_rows, _semantic(history.get("status"), _text(history.get("display"), "")))
    comp_html = _history_rows(comp_rows, _semantic(comparable.get("status")))

    market_grid = "".join([
        _metric("CURRENT LINE", _fmt(market.get("current_line") if "current_line" in market else market.get("line")), _text(market.get("sportsbook"), _semantic(market.get("status")))),
        _metric("OVER PRICE", _odds(market.get("over_odds")), "Book-specific price"),
        _metric("UNDER PRICE", _odds(market.get("under_odds")), "Book-specific price"),
        _metric("OPENING LINE", _semantic(market.get("opening_line_status")), "Verified history only"),
        _metric("LINE MOVEMENT", _semantic(market.get("movement_status")), "No inferred movement"),
        _metric("PERSONNEL", _semantic(personnel.get("status"), _text(personnel.get("display"), "")), "OL / defensive-front verification"),
    ])

    factors = [str(x) for x in (final_read.get("supporting_factors") or []) if str(x).strip()]
    risks = [str(x) for x in (final_read.get("risk_factors") or []) if str(x).strip()]
    unresolved = [str(x) for x in (final_read.get("unresolved") or []) if str(x).strip()]
    evidence_html = "".join(f'<div>{escape(x)}</div>' for x in factors)
    evidence_html += "".join(f'<div class="risk">{escape(x)}</div>' for x in risks)
    evidence_html += "".join(f'<div class="pending">{escape(x)}</div>' for x in unresolved)
    if not evidence_html:
        evidence_html = '<div class="pending">Decision evidence verification pending.</div>'
    lineage_html = "".join(f'<span class="kry2chip">{escape(str(k).replace("_"," ").title())}: {escape(_text(v))}</span>' for k,v in lineage.items())

    style = f'--team-primary:{theme.get("primary")};--team-secondary:{theme.get("secondary")};--team-accent:{theme.get("accent")}'
    return (
        CSS + f'<div class="kry2" style="{escape(style)}">'
        '<a class="kry2back" href="?sport=nfl&market=rushing-yards">← Back to RB Market Board</a>'
        '<div class="kry2hero"><div class="kry2rail"></div><div class="kry2identity">' + face_html + '<div class="kry2idcopy">'
        '<div class="kry2kick">KYRE AI · NFL RUSHING YARDS · DECISION COCKPIT</div>'
        f'<div class="kry2name">{escape(_text(detail.get("player_name"), "Running back"))}</div>'
        f'<div class="kry2sub">{escape(_text(detail.get("role"), "RB"))} · {escape(team)} vs {escape(_text(detail.get("opponent_abbr"), "Opponent"))} · {escape(_text(detail.get("home_away"), "Pregame"))} · {escape(_kickoff(kickoff))}</div>'
        '</div>' + logo_html + '</div><div class="kry2verdict">' + verdict + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">WORKLOAD INTELLIGENCE</div><div class="kry2grid">' + workload_grid + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">RECENT FORM</div><div class="kry2grid">' + recent_grid + '</div><div style="height:8px"></div>' + _recent_table(detail) + '</div>'
        '<div class="kry2sec"><div class="kry2title">OPPONENT RUN DEFENSE</div><div class="kry2grid">' + defense_grid + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">GAME SCRIPT</div><div class="kry2grid">' + script_grid + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">MATCHUP + COMPARABLE HISTORY</div><div class="kry2twocol"><div><div class="kry2sectionnote">RB vs current defense</div>' + history_html + '</div><div><div class="kry2sectionnote">Comparable run-defense tier · ' + escape(_text(comparable.get("target_grade"), "Verification pending")) + '</div>' + comp_html + '</div></div></div>'
        '<div class="kry2sec"><div class="kry2title">ADVANCED EFFICIENCY</div><div class="kry2sectionnote">' + escape(_semantic(advanced.get("status"))) + '</div><div class="kry2grid">' + advanced_grid + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">MARKET + PERSONNEL</div><div class="kry2sectionnote">Sportsbook records remain independent. Missing historical market/personnel fields are never fabricated.</div><div class="kry2grid">' + market_grid + '</div></div>'
        '<div class="kry2sec"><div class="kry2title">FINAL KYRE READ</div><div class="kry2summary">' + escape(_text(final_read.get("summary"), "Decision summary verification pending.")) + '</div><div class="kry2evidence">' + evidence_html + '</div><div class="kry2lineage">' + lineage_html + '</div></div>'
        '</div>'
    )


def render_page2(st: Any, card: Mapping[str, Any]) -> None:
    player_id = _text(card.get("player_id"), "")
    game_id = _text(card.get("game_id"), "")
    target_date = _text(card.get("game_date"), "") or None
    payload = load_rushing_yards_detail(player_id=player_id, game_id=game_id, target_date=target_date) if player_id and game_id else {"ready": False}
    detail = payload.get("detail") if payload.get("ready") is True and isinstance(payload.get("detail"), dict) else (card.get("detail") if isinstance(card.get("detail"), dict) else {})
    st.markdown(build_rushing_detail_html(detail), unsafe_allow_html=True)


__all__ = ["CSS", "MODEL_VERSION", "build_rushing_detail_html", "render_page2"]
