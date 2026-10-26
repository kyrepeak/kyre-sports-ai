"""NFL Rushing Yards Page 2 S-tier analyst cockpit V3.

Presentation successor only. All data continues to arrive through the Kyre
Sports API Page 2 detail gateway. This module performs deterministic display
summaries over the verified payload and does not fetch external data.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

from nfl_rushing_yards_detail_gateway_v2 import load_rushing_yards_detail
from nfl_rushing_yards_professional_v2 import (
    _fmt,
    _kickoff,
    _num,
    _odds,
    _pct,
    _semantic,
    _team_theme,
    _text,
)

MODEL_VERSION = "NFL RUSHING YARDS PAGE 2 S-TIER V3"

CSS = r"""
<style>
.kry3{max-width:1180px;margin:0 auto;padding:2px 5px 44px;color:#eef8fd;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.kry3 *{box-sizing:border-box}.kry3 a{color:inherit}.kry3back{display:inline-flex;margin:0 0 9px;color:#8adfff;text-decoration:none;font-size:.72rem;font-weight:900}.kry3hero,.kry3sec{border:1px solid #244d64;background:linear-gradient(145deg,#081b29,#06141f);border-radius:18px;box-shadow:0 10px 28px rgba(0,0,0,.18)}.kry3hero{position:relative;overflow:hidden;padding:16px 17px 14px;margin-bottom:10px}.kry3hero:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 80% 0%,color-mix(in srgb,var(--team-accent,#66d2ff) 18%,transparent),transparent 38%);pointer-events:none}.kry3rail{position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--team-accent,#66d2ff)}.kry3identity{display:flex;align-items:center;gap:12px;position:relative}.kry3face,.kry3faceph{width:64px;height:64px;border-radius:50%;flex:0 0 64px;border:2px solid var(--team-accent,#66d2ff);background:#06131d}.kry3face{object-fit:cover}.kry3faceph{display:flex;align-items:center;justify-content:center;font-weight:950;color:#c4e5f4}.kry3idcopy{min-width:0;flex:1}.kry3kick,.kry3title,.kry3label{font-weight:950;letter-spacing:.12em}.kry3kick{font-size:.60rem;color:#73d7ff}.kry3name{font-size:1.55rem;line-height:1.04;font-weight:950;margin-top:3px;overflow-wrap:anywhere}.kry3sub{font-size:.72rem;color:#a8bfcb;margin-top:5px;line-height:1.4;overflow-wrap:anywhere}.kry3logo{width:46px;height:46px;object-fit:contain}.kry3tabs{position:sticky;top:0;z-index:8;display:flex;gap:6px;overflow-x:auto;margin:0 0 10px;padding:7px 8px;border:1px solid #244a60;border-radius:13px;background:rgba(5,18,27,.94);backdrop-filter:blur(12px)}.kry3tabs a{text-decoration:none;border:1px solid #2d5369;border-radius:999px;padding:6px 10px;font-size:.60rem;font-weight:900;color:#c4d9e5;background:#081b28}.kry3tabs a:first-child{border-color:#62cef8;color:#8de2ff}.kry3sec{padding:14px 15px;margin-bottom:10px;scroll-margin-top:60px}.kry3title{font-size:.72rem;color:#e8f4fa;margin-bottom:9px}.kry3note{font-size:.64rem;color:#8fa9b7;line-height:1.45;margin:-2px 0 9px}.kry3grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.kry3grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.kry3metric{border:1px solid #2b5066;background:#061621;border-radius:12px;padding:10px;min-width:0}.kry3label{font-size:.48rem;color:#8fa9b9}.kry3value{font-size:1.02rem;font-weight:950;margin-top:4px;line-height:1.12;overflow-wrap:anywhere}.kry3small{font-size:.57rem;color:#89a3b1;margin-top:4px;line-height:1.35;overflow-wrap:anywhere}.kry3pos{color:#79e6b0}.kry3neg{color:#ff9a8f}.kry3pending{color:#f2ce77}.kry3cockpit{border-color:#3b7a99;box-shadow:0 0 0 1px rgba(99,211,255,.08),0 14px 34px rgba(0,0,0,.24)}.kry3cockpit .kry3metric:first-child{border-color:#45a2c9;background:linear-gradient(145deg,#082433,#071923)}.kry3insights{display:grid;gap:6px}.kry3insight{display:grid;grid-template-columns:28px 1fr;gap:8px;align-items:start;border:1px solid #2b5167;background:#071824;border-radius:11px;padding:8px 10px;font-size:.68rem;line-height:1.4}.kry3insight b{display:flex;width:24px;height:24px;align-items:center;justify-content:center;border-radius:50%;background:#0e5f85;color:#dff6ff}.kry3marketmeta{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:8px;padding-top:8px;border-top:1px solid #234454;font-size:.59rem;color:#9ab3c0}.kry3chart{display:flex;align-items:flex-end;gap:7px;height:170px;padding:14px 8px 6px;border:1px solid #294d62;border-radius:12px;background:linear-gradient(180deg,#071b28,#06131d);position:relative;overflow:hidden}.kry3line{position:absolute;left:6px;right:6px;border-top:1px dashed #d9e7ee;opacity:.68}.kry3linetag{position:absolute;right:7px;transform:translateY(-50%);font-size:.50rem;font-weight:900;background:#dbe8ef;color:#07131b;padding:2px 5px;border-radius:6px}.kry3baritem{flex:1;min-width:0;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px}.kry3barval{font-size:.53rem;font-weight:900;color:#dcebf3}.kry3bar{width:72%;min-height:4px;border-radius:5px 5px 2px 2px;background:linear-gradient(180deg,#4cd2ff,#1586c3);box-shadow:0 0 16px rgba(53,188,244,.13)}.kry3bar.under{background:linear-gradient(180deg,#7391a3,#35576b)}.kry3barlbl{font-size:.46rem;color:#91aab7;text-align:center;line-height:1.15;overflow-wrap:anywhere}.kry3matrix{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px}.kry3matrix .kry3metric{text-align:center;padding:8px 5px}.kry3matrix .kry3value{font-size:.88rem}.kry3matrix .kry3small{font-size:.50rem}.kry3defense{display:grid;grid-template-columns:150px 1fr;gap:8px}.kry3grade{display:flex;flex-direction:column;align-items:center;justify-content:center;border:1px solid #7b4a43;background:linear-gradient(145deg,#241416,#10171d);border-radius:12px;padding:12px;text-align:center}.kry3grade .big{font-size:1.55rem;font-weight:950}.kry3grade .rank{font-size:.60rem;color:#ef9d8f}.kry3split{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kry3state{border:1px dashed #496578;border-radius:12px;padding:10px 11px;font-size:.66rem;line-height:1.45;color:#b8ced9;background:#071722}.kry3history{display:grid;gap:6px}.kry3historyrow{display:grid;grid-template-columns:1.15fr .85fr;gap:9px;border:1px solid #2a4c60;border-radius:11px;padding:9px 10px;font-size:.66rem;line-height:1.35}.kry3historyrow span{color:#a6bfcb}.kry3tablewrap{overflow-x:auto;border:1px solid #294a5e;border-radius:12px}.kry3table{width:100%;border-collapse:collapse;min-width:620px;font-size:.68rem}.kry3table th,.kry3table td{padding:7px 8px;border-bottom:1px solid #243f50;text-align:left}.kry3table th{font-size:.50rem;letter-spacing:.09em;color:#8fa8b6;background:#0b202d}.kry3final{border-color:#3a7390}.kry3why{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.kry3whybox{border:1px solid #2a5064;border-radius:11px;padding:9px 10px;background:#071722}.kry3whybox b{font-size:.53rem;letter-spacing:.1em}.kry3whybox ul{margin:6px 0 0;padding-left:16px;font-size:.63rem;line-height:1.45;color:#bdd1db}.kry3bottom{margin-top:8px;border:1px solid #2a546b;border-radius:11px;padding:10px 11px;background:#082131;font-size:.68rem;line-height:1.45}.kry3sources{border:1px solid #294b60;border-radius:12px;background:#061520;overflow:hidden}.kry3sources summary{cursor:pointer;padding:10px 12px;font-size:.65rem;font-weight:900;letter-spacing:.09em;color:#d7e8f1}.kry3sourcebody{padding:0 12px 11px;display:flex;flex-wrap:wrap;gap:6px}.kry3chip{border:1px solid #315269;border-radius:999px;padding:5px 8px;color:#bfd4df;font-size:.57rem;overflow-wrap:anywhere}.kry3top{position:fixed;right:14px;bottom:18px;z-index:12;width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;border:1px solid #3d7897;background:#071b28;color:#8bdfff;font-size:.88rem;font-weight:950;box-shadow:0 8px 24px rgba(0,0,0,.35)}
@media(max-width:900px){.kry3grid4{grid-template-columns:repeat(2,minmax(0,1fr))}.kry3matrix{grid-template-columns:repeat(3,minmax(0,1fr))}.kry3defense,.kry3split{grid-template-columns:1fr}.kry3grade{min-height:105px}}
@media(max-width:620px){.kry3{padding-left:4px;padding-right:4px}.kry3hero,.kry3sec{padding:12px}.kry3grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kry3name{font-size:1.32rem}.kry3face,.kry3faceph{width:54px;height:54px;flex-basis:54px}.kry3logo{width:36px;height:36px}.kry3chart{height:155px}.kry3historyrow{grid-template-columns:1fr}.kry3why{grid-template-columns:1fr}.kry3top{right:10px;bottom:14px;width:40px;height:40px}.kry3tabs{top:0}.kry3value{overflow-wrap:anywhere}}
</style>
"""


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    recent = _dict(detail.get("recent_form"))
    rows = [dict(row) for row in (recent.get("games_detail") or []) if isinstance(row, Mapping)]
    if not rows:
        profile = _dict(detail.get("profile"))
        rows = [dict(row) for row in (profile.get("recent_games") or []) if isinstance(row, Mapping)]
    return rows[:10]


def _verified_market(detail: Mapping[str, Any]) -> tuple[dict[str, Any], float | None]:
    market = _dict(detail.get("market_intelligence")) or _dict(detail.get("market"))
    status = _text(market.get("status"), "").upper()
    line = _num(market.get("current_line") if market.get("current_line") is not None else market.get("line"))
    return market, line if status == "VERIFIED" else None


def _projection_value(detail: Mapping[str, Any]) -> float | None:
    decision = _dict(detail.get("decision"))
    projection = _dict(detail.get("projection"))
    return _num(decision.get("projection")) or _num(projection.get("projection_yards")) or _num(projection.get("projection"))


def _expected_carries(detail: Mapping[str, Any]) -> float | None:
    decision = _dict(detail.get("decision"))
    projection = _dict(detail.get("projection"))
    return _num(decision.get("expected_carries")) or _num(projection.get("expected_carries"))


def _expected_ypc(detail: Mapping[str, Any]) -> float | None:
    decision = _dict(detail.get("decision"))
    projection = _dict(detail.get("projection"))
    return _num(decision.get("expected_ypc")) or _num(projection.get("expected_yards_per_carry")) or _num(projection.get("expected_ypc"))


def _metric(label: str, value: str, note: str = "", value_class: str = "") -> str:
    cls = f"kry3value {value_class}".strip()
    return (
        '<div class="kry3metric">'
        f'<div class="kry3label">{escape(label)}</div>'
        f'<div class="{cls}">{escape(value)}</div>'
        + (f'<div class="kry3small">{escape(note)}</div>' if note else "")
        + '</div>'
    )


def _ratio_label(rows: list[dict[str, Any]], line: float | None) -> tuple[str, str]:
    if line is None or not rows:
        return "Pending verification", "Verified line required"
    values = [_num(row.get("rushing_yards")) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return "Pending verification", "No verified sample"
    hits = sum(1 for value in clean if value > line)
    return f"{round(hits / len(clean) * 100):d}%", f"{hits}/{len(clean)}"


def _performance_chart(rows: list[dict[str, Any]], line: float | None) -> str:
    if not rows:
        return '<div class="kry3state">Recent verified rushing history is not available.</div>'
    values = [_num(row.get("rushing_yards")) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return '<div class="kry3state">Recent verified rushing history is not available.</div>'
    max_value = max(max(clean), line or 0.0, 1.0)
    bars: list[str] = []
    for row in rows[:10]:
        yards = _num(row.get("rushing_yards"))
        if yards is None:
            continue
        height = max(4.0, min(100.0, yards / max_value * 100.0))
        cls = "kry3bar" if line is None or yards > line else "kry3bar under"
        date = _text(row.get("game_date"), "")
        short_date = date[5:] if len(date) >= 10 else date
        opp = _text(row.get("opponent_abbr"), "OPP")
        bars.append(
            '<div class="kry3baritem">'
            f'<div class="kry3barval">{escape(_fmt(yards,0))}</div>'
            f'<div class="{cls}" style="height:{height:.1f}%"></div>'
            f'<div class="kry3barlbl">{escape(short_date)}<br>vs {escape(opp)}</div>'
            '</div>'
        )
    line_html = ""
    if line is not None:
        top = max(0.0, min(100.0, 100.0 - line / max_value * 100.0))
        line_html = (
            f'<div class="kry3line" style="top:{top:.1f}%"></div>'
            f'<div class="kry3linetag" style="top:{top:.1f}%">CURRENT LINE {escape(_fmt(line))}</div>'
        )
    return '<div class="kry3chart">' + line_html + "".join(bars) + '</div>'


def _hit_rate_matrix(detail: Mapping[str, Any], rows: list[dict[str, Any]], line: float | None) -> str:
    history = _dict(detail.get("matchup_history"))
    comparable = _dict(detail.get("comparable_matchups"))
    history_rows = [dict(row) for row in (history.get("games_detail") or []) if isinstance(row, Mapping)]
    comp_rows = [dict(row) for row in (comparable.get("games_detail") or []) if isinstance(row, Mapping)]
    groups = (
        ("L5", rows[:5]),
        ("L10", rows[:10]),
        ("SEASON", rows),
        ("AWAY", []),
        ("SIM DEF", comp_rows),
        ("VS OPP", history_rows),
    )
    cards: list[str] = []
    for label, sample in groups:
        value, note = _ratio_label(sample, line)
        cards.append(_metric(label, value, note, "kry3pos" if line is not None and sample else "kry3pending"))
    return '<div class="kry3matrix">' + "".join(cards) + '</div>'


def _history_rows(rows: list[dict[str, Any]], line: float | None, empty: str) -> str:
    if not rows:
        return f'<div class="kry3state">{escape(empty)}</div>'
    body: list[str] = []
    for row in rows[:6]:
        yards = _num(row.get("rushing_yards"))
        attempts = _num(row.get("attempts"))
        result = ""
        if line is not None and yards is not None:
            result = "OVER" if yards > line else "UNDER" if yards < line else "PUSH"
        result_html = f' · <b>{escape(result)}</b>' if result else ""
        body.append(
            '<div class="kry3historyrow">'
            f'<strong>{escape(_text(row.get("game_date"), "Date pending"))} · {escape(_text(row.get("opponent_abbr"), "Opponent pending"))}</strong>'
            f'<span>{escape(_fmt(yards,0))} yds · {escape(_fmt(attempts,0))} carries{result_html}</span>'
            '</div>'
        )
    return '<div class="kry3history">' + "".join(body) + '</div>'


def _full_log(rows: list[dict[str, Any]], line: float | None) -> str:
    if not rows:
        return '<div class="kry3state">No qualifying verified games.</div>'
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
    return '<div class="kry3tablewrap"><table class="kry3table"><thead><tr><th>DATE</th><th>OPP</th><th>RUSH YDS</th><th>ATT</th><th>YPC</th><th>VS LINE</th></tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'


def _insights(detail: Mapping[str, Any], line: float | None) -> list[str]:
    final_read = _dict(detail.get("final_read"))
    factors = [str(item).strip() for item in (final_read.get("supporting_factors") or []) if str(item).strip()]
    workload = _dict(detail.get("workload_intelligence"))
    defense = _dict(detail.get("opponent_run_defense"))
    recent = _dict(detail.get("recent_form"))
    generated: list[str] = []
    trend = _text(workload.get("workload_trend"), "")
    l5 = _num(workload.get("l5_carries_per_game"))
    if trend and l5 is not None:
        generated.append(f"Workload is {trend.lower()} at {l5:.1f} carries per game over the recent five-game sample.")
    grade = _text(defense.get("grade"), "")
    rank = _num(defense.get("rank"))
    if grade:
        rank_text = f" (rank {int(rank)})" if rank is not None else ""
        generated.append(f"Opponent run-defense profile grades {grade.lower()}{rank_text} in the verified current-season sample.")
    l5_yards = _num(recent.get("l5_average"))
    if l5_yards is not None:
        suffix = f" versus a {line:.1f} verified line" if line is not None else " while the sportsbook decision remains unverified"
        generated.append(f"Recent five-game rushing average is {l5_yards:.1f} yards{suffix}.")
    out: list[str] = []
    for item in factors + generated:
        if item not in out:
            out.append(item)
        if len(out) == 3:
            break
    return out or ["Verified decision context is still building for this matchup."]


def _source_details(lineage: Mapping[str, Any]) -> str:
    chips = "".join(
        f'<span class="kry3chip">{escape(str(key).replace("_", " ").title())}: {escape(_text(value))}</span>'
        for key, value in lineage.items()
    )
    return '<details class="kry3sources"><summary>DATA & SOURCES</summary><div class="kry3sourcebody">' + (chips or '<span class="kry3chip">Source lineage verification pending</span>') + '</div></details>'


def build_rushing_detail_html(detail: Mapping[str, Any]) -> str:
    profile = _dict(detail.get("profile"))
    market, line = _verified_market(detail)
    decision = _dict(detail.get("decision"))
    workload = _dict(detail.get("workload_intelligence"))
    recent = _dict(detail.get("recent_form"))
    defense = _dict(detail.get("opponent_run_defense"))
    script = _dict(detail.get("game_script"))
    personnel = _dict(detail.get("personnel"))
    availability = _dict(detail.get("availability"))
    history = _dict(detail.get("matchup_history"))
    comparable = _dict(detail.get("comparable_matchups"))
    advanced = _dict(detail.get("advanced_efficiency"))
    final_read = _dict(detail.get("final_read"))
    lineage = _dict(detail.get("source_lineage"))
    environment = _dict(detail.get("environment"))
    rows = _rows(detail)

    team = _text(detail.get("team_abbr"), "NFL")
    opponent = _text(detail.get("opponent_abbr"), "Opponent")
    theme = _team_theme(team)
    projection = _projection_value(detail)
    expected_carries = _expected_carries(detail)
    expected_ypc = _expected_ypc(detail)
    side = _text(decision.get("side"), "WAIT").upper() if line is not None else "WAIT"
    probability = _num(decision.get("probability")) if line is not None else None
    edge = _num(decision.get("edge")) if line is not None else None
    side_class = "kry3pos" if side == "OVER" else "kry3neg" if side == "UNDER" else "kry3pending"
    edge_class = "kry3pos" if edge is not None and edge > 0 else "kry3neg" if edge is not None and edge < 0 else "kry3pending"

    face = _text(detail.get("headshot_url") or detail.get("player_headshot"), "")
    logo = _text(detail.get("team_logo_url") or detail.get("team_logo"), "")
    face_html = f'<img class="kry3face" src="{escape(face)}" alt="">' if face else '<div class="kry3faceph">RB</div>'
    logo_html = f'<img class="kry3logo" src="{escape(logo)}" alt="">' if logo else ""
    kickoff = detail.get("game_time") or detail.get("kickoff_utc") or environment.get("kickoff_et")

    market_state = _semantic(market.get("status"))
    line_value = _fmt(line) if line is not None else market_state
    probability_value = _pct(probability) if probability is not None else "Pending verification"
    edge_value = f"{edge:+.1f}" if edge is not None else "WAIT"

    cockpit = "".join((
        _metric("KYRE LEAN", side, "Rushing yards decision", side_class),
        _metric("VERIFIED LINE", line_value, _text(market.get("sportsbook"), market_state), "" if line is not None else "kry3pending"),
        _metric("PROJECTION", _fmt(projection), "Market-blind rushing yards"),
        _metric("EDGE", edge_value, "Projection minus verified line", edge_class),
        _metric("PROBABILITY", probability_value, "Model side probability", side_class if probability is not None else "kry3pending"),
        _metric("EXPECTED LOAD", f"{_fmt(expected_carries)} att", f"{_fmt(expected_ypc,2)} expected YPC"),
    ))

    insight_html = "".join(
        f'<div class="kry3insight"><b>{index}</b><span>{escape(text)}</span></div>'
        for index, text in enumerate(_insights(detail, line), start=1)
    )

    market_grid = "".join((
        _metric("CURRENT LINE", line_value, _text(market.get("sportsbook"), market_state), "" if line is not None else "kry3pending"),
        _metric("OVER PRICE", _odds(market.get("over_odds")) if line is not None else "Pending verification", "Book-specific price"),
        _metric("UNDER PRICE", _odds(market.get("under_odds")) if line is not None else "Pending verification", "Book-specific price"),
        _metric("OPENING LINE", _semantic(market.get("opening_line_status")), "Verified history only"),
    ))

    workload_grid = "".join((
        _metric("SEASON ATT/G", _fmt(workload.get("season_carries_per_game")), "Verified rushing workload"),
        _metric("L3 ATT/G", _fmt(workload.get("l3_carries_per_game")), _text(workload.get("workload_trend"))),
        _metric("L5 ATT/G", _fmt(workload.get("l5_carries_per_game")), "Recent workload"),
        _metric("TEAM RUSH SHARE", _pct(workload.get("team_rush_attempt_share")), "Share of team RB rush attempts"),
        _metric("RED-ZONE CARRIES", _fmt(workload.get("red_zone_carries"),0), "Verified play-by-play"),
        _metric("GOAL-LINE CARRIES", _fmt(workload.get("goal_line_carries"),0), "Inside opponent 5"),
        _metric("4Q CARRIES", _fmt(workload.get("fourth_quarter_carries"),0), "Fourth-quarter usage"),
        _metric("LEAD / TRAIL", f"{_fmt(workload.get('leading_carries'),0)} / {_fmt(workload.get('trailing_carries'),0)}", "Carries by score state"),
    ))

    defense_grid = "".join((
        _metric("RUSH YDS ALLOWED/G", _fmt(defense.get("rush_yards_allowed_per_game")), "Verified current-season sample"),
        _metric("RUSH ATT ALLOWED/G", _fmt(defense.get("rush_attempts_allowed_per_game")), "Opponent volume allowed"),
        _metric("YPC ALLOWED", _fmt(defense.get("yards_per_carry_allowed"),2), "Rushing efficiency allowed"),
        _metric("EXPLOSIVE ALLOWED", _pct(defense.get("explosive_run_rate_allowed")), "10+ yard rush rate"),
        _metric("STUFF RATE", _pct(defense.get("stuff_rate")), "Rushes held to 0 or fewer"),
        _metric("SUCCESS ALLOWED", _pct(defense.get("success_rate_allowed")), "Verified play success"),
        _metric("EPA / ATT ALLOWED", _fmt(defense.get("rush_epa_allowed_per_attempt"),3), "Rush EPA allowed"),
        _metric("DEFENSE RANK", _fmt(defense.get("rank"),0), _text(defense.get("grade"), "CHECK")),
    ))

    grade = _text(defense.get("grade"), "CHECK")
    rank = _fmt(defense.get("rank"),0)
    defense_block = (
        '<div class="kry3defense">'
        f'<div class="kry3grade"><div class="kry3label">DEFENSE GRADE</div><div class="big">{escape(grade)}</div><div class="rank">Rank {escape(rank)}</div></div>'
        f'<div class="kry3grid4">{defense_grid}</div></div>'
    )

    personnel_state = _semantic(personnel.get("status"), _text(personnel.get("display"), ""))
    availability_state = _semantic(availability.get("status"), _text(availability.get("display"), "")) if availability else "Availability verification pending"
    trench_html = (
        '<div class="kry3split">'
        f'<div class="kry3state"><b>OFFENSIVE LINE / FRONT CONTEXT</b><br>{escape(personnel_state)}</div>'
        f'<div class="kry3state"><b>RUN-DEFENSE CONTEXT</b><br>{escape(grade)} · Rank {escape(rank)}</div>'
        '</div>'
    )

    game_grid = "".join((
        _metric("SPREAD", _semantic(script.get("spread_status")), "No fabricated game line"),
        _metric("TOTAL", _semantic(script.get("total_status")), "No fabricated game total"),
        _metric("GAME STATE", _semantic(environment.get("status") or script.get("status") or "PREGAME"), _kickoff(kickoff)),
        _metric("WEATHER", _semantic(script.get("weather_status")), "Verified only"),
        _metric("TEAM RUSH ATT/G", _fmt(script.get("team_rush_attempts_per_game")), "Verified game sample"),
        _metric("LEADING SHARE", _pct(script.get("player_leading_carry_share") if script.get("player_leading_carry_share") is not None else script.get("leading_share")), "Carries while team leads"),
        _metric("TRAILING SHARE", _pct(script.get("player_trailing_carry_share") if script.get("player_trailing_carry_share") is not None else script.get("trailing_share")), "Carries while team trails"),
        _metric("4Q SHARE", _pct(script.get("player_fourth_quarter_carry_share") if script.get("player_fourth_quarter_carry_share") is not None else script.get("fourth_quarter_share")), "Fourth-quarter carry share"),
    ))

    history_rows = [dict(row) for row in (history.get("games_detail") or []) if isinstance(row, Mapping)]
    comp_rows = [dict(row) for row in (comparable.get("games_detail") or []) if isinstance(row, Mapping)]

    advanced_grid = "".join((
        _metric("EXPLOSIVE RUN RATE", _pct(advanced.get("explosive_run_rate")), "10+ yard rushes"),
        _metric("STUFF RATE", _pct(advanced.get("stuff_rate")), "Rushes held to 0 or fewer"),
        _metric("SUCCESS RATE", _pct(advanced.get("success_rate")), "Verified play success"),
        _metric("RUSH EPA / ATT", _fmt(advanced.get("rush_epa_per_attempt"),3), "Efficiency per rushing attempt"),
    ))

    supporting = [str(item).strip() for item in (final_read.get("supporting_factors") or []) if str(item).strip()]
    risks = [str(item).strip() for item in (final_read.get("risk_factors") or []) if str(item).strip()]
    unresolved = [str(item).strip() for item in (final_read.get("unresolved") or []) if str(item).strip()]
    why_items = "".join(f"<li>{escape(item)}</li>" for item in supporting[:4]) or "<li>Verified positive evidence is still building.</li>"
    risk_items = "".join(f"<li>{escape(item)}</li>" for item in (risks + unresolved)[:4]) or "<li>No additional verified risk note.</li>"
    confidence = decision.get("confidence")
    confidence_value = _pct(confidence) if _num(confidence) is not None else _text(confidence, "Evidence based")

    style = f'--team-primary:{theme.get("primary")};--team-secondary:{theme.get("secondary")};--team-accent:{theme.get("accent")}'
    return (
        CSS + f'<div id="kry3top" class="kry3" style="{escape(style)}">'
        '<a class="kry3back" href="?sport=nfl&market=rushing-yards">← Back to RB Market Board</a>'
        '<section class="kry3hero"><div class="kry3rail"></div><div class="kry3identity">' + face_html + '<div class="kry3idcopy">'
        '<div class="kry3kick">KYRE AI · NFL RUSHING YARDS</div>'
        f'<div class="kry3name">{escape(_text(detail.get("player_name"), "Running back"))}</div>'
        f'<div class="kry3sub">{escape(_text(detail.get("role"), "RB"))} · {escape(team)} vs {escape(opponent)} · {escape(_text(detail.get("home_away"), "Pregame"))} · {escape(_kickoff(kickoff))}</div>'
        '</div>' + logo_html + '</div></section>'
        '<nav class="kry3tabs">'
        '<a href="#decision">OVERVIEW</a><a href="#performance">PERFORMANCE</a><a href="#matchup">MATCHUP</a><a href="#environment">GAME</a><a href="#final">INSIGHTS</a>'
        '</nav>'
        '<section id="decision" class="kry3sec kry3cockpit"><div class="kry3title">DECISION COCKPIT</div><div class="kry3grid">' + cockpit + '</div></section>'
        '<section class="kry3sec"><div class="kry3title">KYRE INSIGHTS</div><div class="kry3insights">' + insight_html + '</div></section>'
        '<section class="kry3sec"><div class="kry3title">MARKET LAB</div><div class="kry3grid4">' + market_grid + '</div><div class="kry3marketmeta"><span>Sportsbook records remain independent.</span><span>' + escape(_semantic(market.get("movement_status"))) + '</span></div></section>'
        '<section id="performance" class="kry3sec"><div class="kry3title">RECENT PERFORMANCE</div><div class="kry3note">Verified rushing yards against the current market line when a verified line exists.</div>' + _performance_chart(rows, line) + '</section>'
        '<section class="kry3sec"><div class="kry3title">HIT RATE MATRIX</div>' + _hit_rate_matrix(detail, rows, line) + '</section>'
        '<section class="kry3sec"><div class="kry3title">WORKLOAD & ROLE</div><div class="kry3grid4">' + workload_grid + '</div></section>'
        '<section id="matchup" class="kry3sec"><div class="kry3title">OPPONENT RUN DEFENSE</div>' + defense_block + '</section>'
        '<section class="kry3sec"><div class="kry3title">TRENCH & PERSONNEL</div><div class="kry3note">Only verified personnel/trench context is shown; no synthetic grade is created.</div>' + trench_html + '</section>'
        '<section id="environment" class="kry3sec"><div class="kry3title">GAME ENVIRONMENT</div><div class="kry3grid4">' + game_grid + '</div></section>'
        '<section class="kry3sec"><div class="kry3title">AVAILABILITY & PERSONNEL</div><div class="kry3split"><div class="kry3state"><b>PLAYER AVAILABILITY</b><br>' + escape(availability_state) + '</div><div class="kry3state"><b>PERSONNEL</b><br>' + escape(personnel_state) + '</div></div></section>'
        '<section class="kry3sec"><div class="kry3title">MATCHUP + COMPARABLE HISTORY</div><div class="kry3split"><div><div class="kry3note">RB vs current defense</div>' + _history_rows(history_rows, line, _semantic(history.get("status"), _text(history.get("display"), "No verified prior matchup"))) + '</div><div><div class="kry3note">Comparable run-defense tier · ' + escape(_text(comparable.get("target_grade"), "Verification pending")) + '</div>' + _history_rows(comp_rows, line, _semantic(comparable.get("status"))) + '</div></div></section>'
        '<section class="kry3sec"><div class="kry3title">ADVANCED EFFICIENCY</div><div class="kry3note">Player-only efficiency metrics from verified play-by-play.</div><div class="kry3grid4">' + advanced_grid + '</div></section>'
        '<section class="kry3sec"><div class="kry3title">FULL GAME LOG</div>' + _full_log(rows, line) + '</section>'
        '<section id="final" class="kry3sec kry3final"><div class="kry3title">FINAL KYRE READ</div><div class="kry3grid">'
        + _metric("LEAN", side if line is not None else "WAIT", f"Rushing yards · {line_value}", side_class)
        + _metric("CONFIDENCE", confidence_value, "Evidence quality / model confidence")
        + _metric("PROBABILITY", probability_value, "Projected side probability", side_class if probability is not None else "kry3pending")
        + '</div><div class="kry3why"><div class="kry3whybox"><b class="kry3pos">WHY</b><ul>' + why_items + '</ul></div><div class="kry3whybox"><b class="kry3pending">RISKS</b><ul>' + risk_items + '</ul></div></div>'
        + '<div class="kry3bottom"><b>BOTTOM LINE</b><br>' + escape(_text(final_read.get("summary"), "Decision summary verification pending.")) + '</div></section>'
        + _source_details(lineage)
        + '<a class="kry3top" href="#kry3top" aria-label="Back to top">↑</a>'
        + '</div>'
    )


def render_page2(st: Any, card: Mapping[str, Any]) -> None:
    player_id = _text(card.get("player_id"), "")
    game_id = _text(card.get("game_id"), "")
    target_date = _text(card.get("game_date"), "") or None
    payload = load_rushing_yards_detail(player_id=player_id, game_id=game_id, target_date=target_date) if player_id and game_id else {"ready": False}
    detail = payload.get("detail") if payload.get("ready") is True and isinstance(payload.get("detail"), Mapping) else (card.get("detail") if isinstance(card.get("detail"), Mapping) else {})
    st.markdown(build_rushing_detail_html(detail), unsafe_allow_html=True)


__all__ = ["CSS", "MODEL_VERSION", "build_rushing_detail_html", "render_page2"]
