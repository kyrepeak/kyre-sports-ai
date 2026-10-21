'''NBA PRA Page 2 V1 — selected-player intelligence deep dive.'''
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from statistics import mean
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

MODEL_VERSION = "NBA PRA PAGE 2/3 • PLAYER INTELLIGENCE V1"
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
    p = result.get("over_probability")
    if p is None:
        return "—"
    shown = 1.0 - float(p) if lean == "UNDER" else float(p)
    return f"{shown * 100:.0f}%"


def game_log_rows(profile: Mapping[str, Any], active_line: float | None) -> list[dict[str, Any]]:
    games = list(profile.get("current_games") or []) or list(profile.get("prior_games") or [])
    out: list[dict[str, Any]] = []
    for game in games:
        try:
            pts = float(game.get("points")); reb = float(game.get("rebounds")); ast = float(game.get("assists"))
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
        out.append({
            "date": game.get("game_date"),
            "opponent": game.get("opponent"),
            "points": pts,
            "rebounds": reb,
            "assists": ast,
            "pra": pra,
            "minutes": game.get("minutes"),
            "result": result,
        })
    return out


def _hit_rate(rows: list[dict[str, Any]]) -> str:
    decided = [row for row in rows if row.get("result") in {"OVER", "UNDER"}]
    if not decided:
        return "—"
    over = sum(1 for row in decided if row["result"] == "OVER")
    return f"{over}/{len(decided)} OVER • {over / len(decided) * 100:.0f}%"


def _quote_cards(quotes: list[Mapping[str, Any]]) -> str:
    if not quotes:
        return '<div class="p2-empty">No verified sportsbook quotes.</div>'
    cards=[]
    for q in quotes:
        cards.append(
            '<div class="p2-book">'
            f'<b>{escape(_text(q.get("sportsbook")) or "Book")}</b>'
            f'<strong>{_fmt(q.get("line"))}</strong>'
            f'<span>O {_price(q.get("over_price"))} • U {_price(q.get("under_price"))}</span>'
            f'<small>{escape(_text(q.get("observed_at_utc")) or "Timestamp unavailable")}</small>'
            '</div>'
        )
    return ''.join(cards)


def _rank_card(label: str, row: Mapping[str, Any]) -> str:
    rank = row.get("rank")
    grade = _text(row.get("grade")) or "UNAVAILABLE"
    return (
        '<div class="p2-rank-card">'
        f'<small>{escape(label)}</small><b>{"#" + str(rank) if rank is not None else "—"}</b>'
        f'<span>{escape(grade)}</span><em>{_fmt(row.get("value"))}</em>'
        '</div>'
    )


def _risk_items(context: Mapping[str, Any], model: Mapping[str, Any], matchup: Mapping[str, Any]) -> list[str]:
    risks=[]
    if context.get("line_moved"):
        risks.append("Sportsbook line moved since selection")
    form=_display_form(model)
    if int(form.get("sample") or 0) < 5:
        risks.append("Small recent history sample")
    try:
        if float(model.get("sigma")) >= 9.0:
            risks.append("Wide PRA variance")
    except (TypeError,ValueError):
        pass
    status=_text(context.get("availability")).upper()
    if status not in {"AVAILABLE","UNVERIFIED","NO VERIFIED INJURY FLAG",""}:
        risks.append(f"Availability: {status}")
    if "PRESEASON" in _text(matchup.get("evidence_period")).upper():
        risks.append("Opponent rank uses preseason baseline")
    if not risks:
        risks.append("No verified elevated risk flag")
    return risks


def _game_log_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="p2-empty">Verified game log unavailable.</div>'
    body=[]
    for row in rows:
        body.append(
            '<tr>'
            f'<td>{escape(_text(row.get("date")) or "—")}</td>'
            f'<td>{escape(_text(row.get("opponent")) or "—")}</td>'
            f'<td>{_fmt(row.get("points"),0)}</td><td>{_fmt(row.get("rebounds"),0)}</td><td>{_fmt(row.get("assists"),0)}</td>'
            f'<td><b>{_fmt(row.get("pra"),1)}</b></td><td>{_fmt(row.get("minutes"),1)}</td>'
            f'<td><span class="p2-result">{escape(_text(row.get("result")))}</span></td></tr>'
        )
    return '<table class="p2-log"><thead><tr><th>DATE</th><th>OPP</th><th>PTS</th><th>REB</th><th>AST</th><th>PRA</th><th>MIN</th><th>RESULT</th></tr></thead><tbody>'+''.join(body)+'</tbody></table>'


def _prior_matchup_html(profile: Mapping[str, Any], opponent: str, active_line: float | None) -> str:
    exact=[]
    for row in list(profile.get("current_games") or []) + list(profile.get("prior_games") or []):
        if _text(row.get("opponent")).upper() == _text(opponent).upper() and opponent:
            exact.append(row)
    if not exact:
        return '<div class="p2-empty">No verified prior matchup sample.</div>'
    temp={"current_games":exact,"prior_games":[]}
    return _game_log_html(game_log_rows(temp,active_line))


def build_page2_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> str:
    profile=context.get("player") or {}
    form=_display_form(model)
    name=_text(context.get("player_name") or profile.get("player_name")) or "Player"
    team=_text(context.get("team")) or "NBA"
    opponent=_text(context.get("opponent")) or "—"
    position=_text(profile.get("position"))
    headshot=_text(profile.get("headshot"))
    team_logo=_text(context.get("team_logo")); opp_logo=_text(context.get("opponent_logo"))
    quote=context.get("current_quote") or context.get("selected_quote") or {}
    lean=_text(line_result.get("lean")).upper() or "PASS"
    score=_fmt(line_result.get("score"),1,"—")
    line_move=(f'<div class="p2-alert">{escape(_text(context.get("line_moved_label")))}</div>' if context.get("line_moved") else '')
    logs=game_log_rows(profile,active_line)
    risks=''.join(f'<li>{escape(item)}</li>' for item in _risk_items(context,model,matchup))
    hero_image=f'<img class="p2-face" src="{escape(headshot)}" alt="{escape(name)}">' if headshot else '<div class="p2-face p2-face-empty">NBA</div>'
    team_image=f'<img class="p2-logo" src="{escape(team_logo)}" alt="{escape(team)} logo">' if team_logo else ''
    opp_image=f'<img class="p2-logo" src="{escape(opp_logo)}" alt="{escape(opponent)} logo">' if opp_logo else ''
    evidence_period=escape(_text(matchup.get("evidence_period")) or "Opponent ranking unavailable")
    rank_semantics=escape(_text(matchup.get("rank_semantics")) or "Opponent ranking unavailable")
    return f'''
<div id="ks-nba-pra-page2-top"></div>
<section class="p2-hero">
  <div class="p2-player">{hero_image}<div>{team_image}<h1>{escape(name)}</h1><p>{escape(team)} • {escape(position or "Position unavailable")} • vs {escape(opponent)} {opp_image}</p><small>{escape(_text(context.get("availability")) or "UNVERIFIED")}</small></div></div>
  <div class="p2-quote"><small>CURRENT PRA • {escape(_text(quote.get("sportsbook")) or "—")}</small><b>{_fmt(quote.get("line"))}</b><span>O {_price(quote.get("over_price"))} • U {_price(quote.get("under_price"))}</span></div>
</section>{line_move}
<section class="p2-panel p2-verdict"><div class="p2-kicker">KYRE AI VERDICT</div><div class="p2-verdict-grid">
  <div><small>DECISION</small><b>{escape(lean)}</b></div><div><small>LINE</small><b>{_fmt(active_line)}</b></div>
  <div><small>PROJECTION</small><b>{_fmt(model.get("projection"))}</b></div><div><small>EDGE</small><b>{_signed(line_result.get("edge"))}</b></div>
  <div><small>PROBABILITY</small><b>{_probability(line_result)}</b></div><div><small>KYRE SCORE</small><b>{score}</b><span>{escape(_text(line_result.get("tier")))}</span></div>
</div><p>Projection is evaluated against the selected threshold using verified player history. Opponent ranking is contextual evidence only and does not alter the frozen Kyre projection.</p></section>
<section class="p2-panel"><div class="p2-kicker">LINE LAB</div><p>Use the touch slider to test alternate PRA thresholds. The slider changes only the threshold — never the projection.</p></section>
<section class="p2-panel"><div class="p2-kicker">SPORTSBOOK BOARD</div><div class="p2-books">{_quote_cards(list(context.get("quotes") or []))}</div><p class="p2-note">Verified opening movement unavailable unless same-book opening history is explicitly present. Current quotes stay separate; no line averaging.</p></section>
<section class="p2-panel"><div class="p2-kicker">RECENT FORM</div><div class="p2-form-grid"><div><small>L5</small><b>{_fmt(form.get("l5"))}</b></div><div><small>L10</small><b>{_fmt(form.get("l10"))}</b></div><div><small>MIN</small><b>{_fmt(form.get("minutes"))}</b></div><div><small>HIT RATE @ {_fmt(active_line)}</small><b>{escape(_hit_rate(logs))}</b></div></div></section>
<section class="p2-panel"><div class="p2-kicker">OPPONENT RANK • {escape(opponent)}</div><div class="p2-ranks">
{_rank_card("Points",matchup.get("points") or {})}{_rank_card("Rebounds",matchup.get("rebounds") or {})}{_rank_card("Assists",matchup.get("assists") or {})}
<div class="p2-rank-card p2-rank-pra"><small>PRA</small><b>{"#"+str(matchup.get("pra_rank")) if matchup.get("pra_rank") is not None else "—"}</b><span>{escape(_text(matchup.get("matchup_grade")) or "UNAVAILABLE")}</span><em>combined context</em></div></div>
<p class="p2-note">{rank_semantics} • {evidence_period} • PRA rank = transparent mean of verified PTS/REB/AST ranks.</p></section>
<section class="p2-panel"><div class="p2-kicker">OPPONENT MATCHUP INTELLIGENCE</div><p>Stat-specific opponent rankings above are verified context. Pace/position/paint or advanced fields remain unavailable unless supplied by an approved Kyre Sports API owner.</p></section>
<section class="p2-panel"><div class="p2-kicker">PLAYER VS OPPONENT HISTORY</div>{_prior_matchup_html(profile,opponent,active_line)}</section>
<section class="p2-panel"><div class="p2-kicker">ROLE & MINUTES</div><p>Recent verified minutes: <b>{_fmt(form.get("minutes"))}</b>. Starter/bench, touches, usage, and projected minutes remain unavailable unless a verified owner supplies them.</p></section>
<section class="p2-panel"><div class="p2-kicker">INJURY / LINEUP IMPACT</div><p>Player availability: <b>{escape(_text(context.get("availability")) or "UNVERIFIED")}</b>. Teammate impact is not inferred from injury labels without explicit role evidence.</p></section>
<section class="p2-panel"><div class="p2-kicker">PROJECTION BREAKDOWN</div><p>Final frozen Kyre projection: <b>{_fmt(model.get("projection"))} PRA</b> • model sample: {int(form.get("sample") or 0)} • recent minutes: {_fmt(form.get("minutes"))}. Opponent and sportsbook context remain presentation-only.</p></section>
<section class="p2-panel"><div class="p2-kicker">RISK FACTORS</div><ul>{risks}</ul></section>
<section class="p2-panel"><div class="p2-kicker">FULL GAME LOG</div>{_game_log_html(logs)}</section>
'''


def _css() -> str:
    return '''<style>
.p2-wrap{max-width:1500px;margin:auto}.p2-hero,.p2-panel{background:linear-gradient(145deg,#071525,#06101d);border:1px solid rgba(108,210,255,.22);border-radius:18px;padding:18px;margin:12px 0;color:#eff9ff;box-shadow:0 16px 40px rgba(0,0,0,.23)}
.p2-hero{display:flex;justify-content:space-between;gap:18px;align-items:center}.p2-player{display:flex;gap:15px;align-items:center}.p2-face{width:94px;height:94px;object-fit:cover;border-radius:18px;background:#0b1d2d}.p2-face-empty{display:grid;place-items:center}.p2-logo{width:28px;height:28px;object-fit:contain;vertical-align:middle;margin-right:7px}.p2-player h1{margin:3px 0;font-size:29px}.p2-player p,.p2-note{color:#9db2c6}.p2-quote{text-align:right;min-width:150px}.p2-quote b{display:block;font-size:36px;color:#7ce7ff}.p2-kicker{font-size:12px;letter-spacing:.14em;font-weight:800;color:#64d7ff;margin-bottom:13px}.p2-verdict-grid,.p2-form-grid,.p2-ranks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.p2-verdict-grid>div,.p2-form-grid>div,.p2-rank-card,.p2-book{background:#091c2e;border:1px solid rgba(109,215,255,.17);padding:13px;border-radius:13px}.p2-verdict-grid small,.p2-form-grid small,.p2-rank-card small{display:block;color:#8da6ba}.p2-verdict-grid b,.p2-form-grid b,.p2-rank-card b{font-size:22px}.p2-rank-card span{display:block;font-weight:800;color:#7ce7ff}.p2-rank-card em{font-size:11px;color:#8096a8}.p2-books{display:flex;gap:9px;overflow-x:auto;padding-bottom:4px}.p2-book{min-width:145px}.p2-book strong{display:block;font-size:22px}.p2-book span,.p2-book small{display:block;color:#9bb1c3}.p2-alert{background:#44280a;border:1px solid #d58b28;color:#ffc766;padding:10px 14px;border-radius:12px;font-weight:800;margin:8px 0}.p2-log{width:100%;border-collapse:collapse;font-size:13px}.p2-log th,.p2-log td{padding:8px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left}.p2-empty{color:#8da6ba;padding:12px 0}.ks-p2-top{position:fixed;right:18px;bottom:24px;z-index:99999;background:#0b2a41;color:#8ee9ff!important;border:1px solid #4ccdf7;border-radius:999px;padding:10px 14px;text-decoration:none;font-weight:900;box-shadow:0 10px 30px rgba(0,0,0,.35)}
@media(max-width:800px){.p2-hero{align-items:flex-start}.p2-verdict-grid,.p2-form-grid,.p2-ranks{grid-template-columns:repeat(2,minmax(0,1fr))}.p2-face{width:76px;height:76px}.p2-player h1{font-size:23px}.p2-quote b{font-size:28px}.ks-p2-top{right:12px;bottom:74px}}
</style>'''


def default_line_for_context(context: Mapping[str, Any]) -> float | None:
    quote = context.get("selected_quote") or context.get("current_quote") or {}
    try:
        return float(quote.get("line"))
    except (TypeError, ValueError, AttributeError):
        return None


def _baseline_model(profile: Mapping[str, Any]) -> dict[str, Any]:
    model=project_pra(profile.get("current_games") or [], profile.get("prior_games") or [])
    baseline=profile.get("season_baseline") if isinstance(profile.get("season_baseline"),Mapping) else {}
    if model.get("projection") is None and baseline.get("pra") is not None:
        try: value=round(float(baseline.get("pra")),1)
        except (TypeError,ValueError): value=None
        if value is not None:
            model={**model,"projection":value,"sigma":None,"basis":"VERIFIED SEASON BASELINE"}
    return model


def render_nba_pra_page2_v1(context: Mapping[str, Any] | None = None) -> None:
    import streamlit as st

    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<a class="ks-p2-top" href="#ks-nba-pra-page2-top">↑ TOP</a>',unsafe_allow_html=True)
    if st.button("← Back to PRA Board", key="nba-pra-p2-back", use_container_width=False):
        clear_page2_state(st.session_state)
        st.rerun()

    now=datetime.now(timezone.utc)
    if context is None:
        key=selected_player_key(st.session_state)
        if key is None:
            st.warning("No verified player selection. Return to the PRA board.")
            return
        with st.spinner("Loading selected NBA PRA intelligence…"):
            snapshot=load_page2_snapshot_v1(key,now=now)
        selected=st.session_state.get(SESSION_SELECTED_QUOTE)
        context=build_page2_context(snapshot,key,selected_quote=selected if isinstance(selected,Mapping) else None)

    if context.get("state") not in {"ready","line_moved"}:
        st.warning("Selected player or PRA market is no longer available. Return to the PRA board.")
        return

    profile=context.get("player") or {}
    model=_baseline_model(profile)
    current_quote=context.get("current_quote") or context.get("selected_quote") or {}
    default_line=default_line_for_context(context)
    if default_line is None:
        st.warning("Verified PRA line unavailable. No test line was invented.")
        return

    options=line_steps(default_line,width=10.0)
    prior=st.session_state.get(SESSION_LINE_LAB)
    default=prior if prior in options else default_line if default_line in options else min(options,key=lambda x:abs(x-default_line))
    active_line=st.select_slider(
        "PRA Line Lab",
        options=options,
        value=default,
        key=SESSION_LINE_LAB,
        help="Test alternate PRA thresholds. This does not change the Kyre projection.",
    )
    result=evaluate_line(model.get("projection"),model.get("sigma"),float(active_line))
    matchup_raw=load_kyre_sports_api_nba_pra_matchup(_text(context.get("opponent")),now_utc=now)
    matchup=build_matchup_summary(matchup_raw)
    st.markdown('<div class="p2-wrap">'+build_page2_html(context,model,result,matchup,active_line=float(active_line))+'</div>',unsafe_allow_html=True)
