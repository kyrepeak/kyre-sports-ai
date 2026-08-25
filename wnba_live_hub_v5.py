"""WNBA Live Games V5 — Step 5 H2H + roster + availability context.

Appends a descriptive-only Step 5 to the verified/frozen Steps 1-4 stack.
No Step-5 field is fed back into live market math, probability, simulation,
qualification, ranking or recommendations.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_context_v1 as ctx
import wnba_live_hub_v2 as v2
import wnba_live_hub_v43 as v43

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V5 • STEP 5 H2H + ROSTER + AVAILABILITY"


def _signed(value, digits=1):
    try:
        return f"{float(value):+.{digits}f}"
    except Exception:
        return "—"


def _num(value, digits=1):
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _date(value):
    try:
        return pd.to_datetime(value).strftime("%b %-d, %Y")
    except Exception:
        return str(value or "—")


def _logo(url: str, name: str) -> str:
    if not url:
        return '<span class="kwl5-ball">🏀</span>'
    return f'<img src="{escape(str(url), quote=True)}" alt="{escape(str(name), quote=True)}">'


def _status_class(status: str) -> str:
    s = str(status or "").upper()
    if s in {"OUT", "INACTIVE", "DOUBTFUL"}:
        return "bad"
    if s in {"QUESTIONABLE", "DAY-TO-DAY", "PROBABLE"}:
        return "warn"
    return "good"


def _injury_rows(av: dict, team_id: int) -> list[dict]:
    rows = []
    for item in av.get("injuries") or []:
        try:
            if int(item.get("TEAM_ID") or 0) != int(team_id):
                continue
        except Exception:
            continue
        rows.append(item)
    return rows


def _availability_html(game: dict, context: dict, side: str) -> str:
    team_id = int(game.get(f"{side}_team_id") or 0)
    name = str(game.get(f"{side}_team") or side.title())
    logo = str(game.get(f"{side}_logo") or "")
    role = "AWAY" if side == "away" else "HOME"
    av = context.get("availability") or {}
    coverage = {int(k): bool(v) for k, v in (av.get("team_status_coverage") or {}).items()}
    covered = bool(coverage.get(team_id, False))
    injuries = _injury_rows(av, team_id)
    rotation = (context.get("rotation") or {}).get(team_id) or []
    current_starters = (context.get("current_starters") or {}).get(team_id) or []
    prior = (context.get("last_starters") or {}).get(team_id) or {}

    if covered:
        source_badge = '<span class="good">AVAILABILITY FEED CONNECTED</span>'
    else:
        source_badge = '<span class="bad">AVAILABILITY UNVERIFIED</span>'

    if injuries:
        items = []
        for row in injuries:
            status = str(row.get("DESIGNATION") or "NO DESIGNATION")
            detail = str(row.get("DETAIL") or "").strip()
            source = str(row.get("SOURCE") or row.get("STATUS_SOURCE") or "ESPN WNBA")
            items.append(
                f'<div class="kwl5-status"><div><b>{escape(str(row.get("PLAYER_NAME") or "Player"))}</b><small>{escape(detail or source)}</small></div><span class="{_status_class(status)}">{escape(status)}</span></div>'
            )
        injury_html = "".join(items)
    elif covered:
        injury_html = '<div class="kwl5-ok">No ESPN-reported active injury designation for this team in the connected Step-5 feeds.</div>'
    else:
        injury_html = '<div class="kwl5-alert">Injury/status coverage is unavailable. A blank report is NOT being treated as proof that everyone is healthy.</div>'

    starters_html = " • ".join(escape(x) for x in current_starters) if current_starters else "Explicit current starter flags not available yet."
    entered_names = [str(x.get("name") or "") for x in rotation if x.get("name")]
    rotation_html = " • ".join(escape(x) for x in entered_names) if entered_names else "Current entered-player rotation not available from the live summary yet."

    prior_starters = prior.get("starters") or []
    if prior_starters:
        prior_title = f"LAST VERIFIED STARTERS • {_date(prior.get('date'))} vs {prior.get('opponent') or 'Opponent'}"
        prior_html = " • ".join(escape(str(x)) for x in prior_starters)
    else:
        prior_title = "LAST VERIFIED STARTERS"
        prior_html = "No prior explicit five-starter sample was verified from recent completed summaries."

    current_set = {str(x).lower() for x in current_starters}
    prior_set = {str(x).lower() for x in prior_starters}
    if current_set and prior_set:
        added = [x for x in current_starters if x.lower() not in prior_set]
        missing = [x for x in prior_starters if x.lower() not in current_set]
        if added or missing:
            change = "Confirmed starter change: "
            if added:
                change += "IN " + ", ".join(added)
            if missing:
                change += (" • " if added else "") + "OUT OF STARTING FIVE " + ", ".join(missing)
        else:
            change = "Current explicit starters match the last verified starting five."
    else:
        change = "Starter-change comparison is pending because both explicit starting fives are not yet available."

    return f"""<div class="kwl5-team">
<div class="kwl5-teamhead"><div class="kwl5-ident">{_logo(logo,name)}<div><b>{escape(name)}</b><small>{role}</small></div></div>{source_badge}</div>
<div class="kwl5-subtitle">CURRENT AVAILABILITY</div>{injury_html}
<div class="kwl5-box"><small>CURRENT EXPLICIT STARTERS</small><p>{starters_html}</p></div>
<div class="kwl5-box"><small>LIVE ROTATION • PLAYERS VERIFIED AS ENTERED</small><p>{rotation_html}</p><em>{len(entered_names)} player(s) observed</em></div>
<div class="kwl5-box"><small>{escape(prior_title)}</small><p>{prior_html}</p></div>
<div class="kwl5-change">{escape(change)}</div>
</div>"""


def _h2h_html(game: dict, context: dict) -> str:
    h = context.get("h2h") or {}
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    n = int(h.get("games") or 0)
    rel = str(h.get("reliability") or "NONE")
    rel_cls = "good" if rel == "HIGH" else ("warn" if rel in {"MEDIUM", "LOW"} else "thin")
    if n:
        record = f"{int(h.get('away_wins') or 0)}-{int(h.get('away_losses') or 0)}"
    else:
        record = "—"

    ledger = []
    for row in h.get("last5") or []:
        result = "W" if row.get("win") else "L"
        result_cls = "good" if result == "W" else "bad"
        ledger.append(f"""<div class="kwl5-hrow">
<span>{escape(_date(row.get('date')))}</span>
<span>{escape(str(row.get('venue') or ''))} vs {escape(str(row.get('opponent') or 'Opponent'))}</span>
<b>{int(row.get('score_for') or 0)}-{int(row.get('score_against') or 0)}</b>
<span class="{result_cls}">{result}</span>
<span>{_signed(row.get('h2_margin'),0)} 2H</span>
</div>""")
    ledger_html = "".join(ledger) if ledger else '<div class="kwl5-empty">No verified current-season H2H meeting before this live snapshot.</div>'

    return f"""<div class="kwl5-h2h">
<div class="kwl5-h2hhead"><div><small>CURRENT-SEASON H2H • {escape(away)} PERSPECTIVE</small><b>{escape(away)} vs {escape(home)}</b></div><span class="{rel_cls}">{escape(rel)} SAMPLE • {n} GP</span></div>
<div class="kwl5-grid">
<div><small>H2H RECORD</small><strong>{record}</strong></div>
<div><small>AVG FINAL MARGIN</small><strong>{_signed(h.get('away_avg_margin'))}</strong></div>
<div><small>AVG 2H MARGIN</small><strong>{_signed(h.get('away_avg_h2_margin'))}</strong></div>
<div><small>AVG GAME TOTAL</small><strong>{_num(h.get('avg_total'))}</strong></div>
<div><small>AVG Q3 MARGIN</small><strong>{_signed(h.get('away_avg_q3_margin'))}</strong></div>
<div><small>AVG Q4 MARGIN</small><strong>{_signed(h.get('away_avg_q4_margin'))}</strong></div>
</div>
<div class="kwl5-ledger"><small>RECENT VERIFIED H2H • UP TO LAST 5 THIS SEASON</small>{ledger_html}</div>
<div class="kwl5-hnote">H2H is descriptive and uses completed regular-season games strictly before this live snapshot. A thin H2H sample is labeled instead of being padded with unrelated games.</div>
</div>"""


def _game_html(game: dict, context: dict) -> str:
    av = context.get("availability") or {}
    h = context.get("h2h") or {}
    history_error = str((context.get("history_meta") or {}).get("error") or "")
    avail_error = str(av.get("error") or "")
    summary_ok = bool((context.get("current_summary_meta") or {}).get("available"))
    source_state = "VERIFIED" if not history_error and not avail_error and summary_ok else "CHECK"
    fetched = "—"
    try:
        fetched = pd.to_datetime(context.get("fetched_at"), utc=True).tz_convert(ET).strftime("%-I:%M:%S %p ET")
    except Exception:
        pass
    notes = []
    if history_error:
        notes.append("H2H history: " + history_error)
    if avail_error:
        notes.append("availability: " + avail_error)
    if not summary_ok:
        notes.append("current ESPN summary unavailable")
    diag = " • ".join(notes)

    return f"""<div class="kwl5-game">
<div class="kwl5-head"><div><small>VERIFIED LIVE MATCHUP</small><b>{escape(str(game.get('away_team') or 'Away'))} @ {escape(str(game.get('home_team') or 'Home'))}</b></div><div><strong>{game.get('away_score','—')}–{game.get('home_score','—')}</strong><small>{escape(str(game.get('phase') or 'LIVE'))} • {escape(str(game.get('clock') or ''))}</small></div></div>
<div class="kwl5-badges"><span class="{'good' if source_state == 'VERIFIED' else 'warn'}">CONTEXT • {source_state}</span><span>FETCH {fetched}</span><span>H2H {int(h.get('games') or 0)} GP</span><span>INJURY FEEDS {int(av.get('team_feeds_connected') or 0)}/2</span></div>
{_h2h_html(game,context)}
<div class="kwl5-teams">{_availability_html(game,context,'away')}{_availability_html(game,context,'home')}</div>
{f'<div class="kwl5-diag">SOURCE CHECK • {escape(diag)}</div>' if diag else ''}
<div class="kwl5-note">STEP 5 IS DESCRIPTIVE ONLY. H2H, current rotation, starter changes and availability can identify context/risk, but they are NOT fed into live moneyline/spread/total probabilities, Monte Carlo, edge, EV, qualification or a pick yet. Foul-trouble modeling is intentionally deferred until a reliable player-foul live feed is separately verified.</div>
</div>"""


def _css():
    st.markdown(r"""<style>
.kwl5-hero{border:1px solid #31566f;border-radius:22px;padding:20px;margin:28px 0 14px;background:linear-gradient(145deg,#0a1929,#081522)}.kwl5-eyebrow{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#8ad9ff}.kwl5-hero h3{font-size:1.45rem;margin:8px 0;color:#f6fbff}.kwl5-hero p{margin:0;color:#9bb0c0;line-height:1.55}.kwl5-hero b{color:#fff}.kwl5-game{border:1px solid #31566f;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl5-head{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid #213b4e;padding-bottom:12px}.kwl5-head>div{display:flex;flex-direction:column;gap:4px}.kwl5-head>div:last-child{text-align:right}.kwl5-head small{font-size:.64rem;color:#7892a6;font-weight:850;letter-spacing:.05em}.kwl5-head b{color:#f5f8fb;font-size:1rem}.kwl5-head strong{font-size:1.35rem;color:#fff}.kwl5-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl5-badges span,.kwl5-teamhead>span,.kwl5-h2hhead>span{font-size:.58rem;border:1px solid #28495e;border-radius:999px;padding:6px 8px;color:#9db4c5;font-weight:900}.kwl5-badges .good,.kwl5-teamhead .good,.kwl5-h2hhead .good,.kwl5-status .good,.kwl5-hrow .good{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl5-badges .warn,.kwl5-teamhead .warn,.kwl5-h2hhead .warn,.kwl5-status .warn{border-color:#8a722a;color:#ead879;background:#2a240d}.kwl5-teamhead .bad,.kwl5-status .bad,.kwl5-hrow .bad{border-color:#8f4b47;color:#ffada6;background:#311616}.kwl5-h2hhead .thin{border-color:#566675;color:#a9b8c3;background:#111c27}
.kwl5-h2h{border:1px solid #29495d;border-radius:17px;padding:13px;margin:12px 0;background:#07111d}.kwl5-h2hhead{display:flex;justify-content:space-between;gap:10px;align-items:center}.kwl5-h2hhead>div{display:flex;flex-direction:column}.kwl5-h2hhead small,.kwl5-subtitle,.kwl5-ledger>small{font-size:.58rem;color:#8fcff5;font-weight:950;letter-spacing:.05em}.kwl5-h2hhead b{color:#f5f8fb;margin-top:3px}.kwl5-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:10px}.kwl5-grid>div,.kwl5-box{border:1px solid #243f52;border-radius:12px;padding:10px;background:#081522}.kwl5-grid small,.kwl5-box small{color:#7f98aa;font-size:.55rem;font-weight:900}.kwl5-grid strong{display:block;color:#f5f8fb;font-size:.94rem;margin-top:4px}.kwl5-ledger{margin-top:11px;border-top:1px solid #213b4e;padding-top:9px}.kwl5-hrow{display:grid;grid-template-columns:78px 1fr 46px 30px 52px;gap:5px;align-items:center;border-bottom:1px solid #142b3a;padding:7px 0;color:#91a7b6;font-size:.55rem}.kwl5-hrow b{color:#e3edf3}.kwl5-hrow .good,.kwl5-hrow .bad{border-radius:999px;padding:3px;text-align:center}.kwl5-empty{color:#8298a7;font-size:.62rem;padding:9px 0}.kwl5-hnote{color:#758e9f;font-size:.58rem;line-height:1.45;margin-top:8px}
.kwl5-teams{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kwl5-team{border:1px solid #29495d;border-radius:17px;padding:12px;background:#07111d}.kwl5-teamhead{display:flex;justify-content:space-between;gap:8px;align-items:center}.kwl5-ident{display:flex;gap:9px;align-items:center}.kwl5-ident img{width:34px;height:34px;object-fit:contain}.kwl5-ball{font-size:1.5rem}.kwl5-ident>div{display:flex;flex-direction:column}.kwl5-ident b{color:#f5f8fb}.kwl5-ident small{color:#7d95a7;font-size:.56rem}.kwl5-subtitle{margin:12px 0 7px}.kwl5-status{display:flex;justify-content:space-between;gap:8px;align-items:center;border:1px solid #243f52;border-radius:12px;padding:9px;margin:6px 0}.kwl5-status>div{display:flex;flex-direction:column}.kwl5-status b{color:#eef5f8;font-size:.72rem}.kwl5-status small{color:#7891a3;font-size:.52rem;margin-top:2px}.kwl5-status>span{font-size:.54rem;font-weight:900;border:1px solid #31566f;border-radius:999px;padding:5px 7px}.kwl5-ok{border:1px solid #2c704f;background:#0c271d;color:#8ee0b0;border-radius:12px;padding:10px;font-size:.62rem;line-height:1.45}.kwl5-alert{border:1px solid #845049;background:#2b1714;color:#efaaa0;border-radius:12px;padding:10px;font-size:.62rem;line-height:1.45}.kwl5-box{margin-top:8px}.kwl5-box p{color:#dce7ed;font-size:.64rem;line-height:1.5;margin:5px 0 0}.kwl5-box em{color:#7891a3;font-size:.52rem;font-style:normal}.kwl5-change{border:1px solid #31566f;border-radius:12px;margin-top:8px;padding:9px;color:#9fb5c4;font-size:.6rem;line-height:1.45}.kwl5-diag{border:1px solid #735f24;background:#2a240d;color:#e1cf70;border-radius:13px;padding:10px;margin-top:10px;font-size:.6rem}.kwl5-note{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:15px;padding:12px;margin-top:12px;font-size:.65rem;line-height:1.5}.kwl5-boundary{border:1px solid #294b65;border-radius:15px;padding:13px;color:#8ea5b5;font-size:.68rem;line-height:1.55;margin:15px 0}
@media(max-width:640px){.kwl5-hero{padding:16px}.kwl5-game{padding:13px}.kwl5-teams{grid-template-columns:1fr}.kwl5-grid{grid-template-columns:1fr 1fr}.kwl5-hrow{grid-template-columns:68px 1fr 42px 26px 44px}.kwl5-h2hhead{align-items:flex-start;flex-direction:column}.kwl5-teamhead{align-items:flex-start;flex-direction:column}}
</style>""", unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    v43.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _css()
    st.markdown(f"""<div class="kwl5-hero"><div class="kwl5-eyebrow">🧩 {MODEL_VERSION}</div><h3>Step 5 • H2H + Roster + Availability Context</h3><p>Read-only context attached to the verified live state: <b>current-season H2H, current ESPN availability, explicit starters, live entered-player rotation and last verified starters.</b> Nothing here changes the live model because the live model does not exist yet.</p></div>""", unsafe_allow_html=True)

    if st.button("🔄 Refresh Step 5 context", use_container_width=True, key="wnba_live_v5_refresh"):
        ctx.clear_cache()
        st.rerun()

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    games, _, _ = v2._verified_live_games(day_str)
    if not games:
        st.info("No Step-1 verified WNBA game is live right now, so Step 5 has no live matchup to attach H2H/roster/availability context to.")
        st.markdown('<div class="kwl5-boundary">STEP 5 BOUNDARY • NO live projection • NO probability • NO Monte Carlo • NO edge/EV • NO qualification • NO pick</div>', unsafe_allow_html=True)
        return

    for game in games:
        context = ctx.context_for_game(game)
        st.markdown(_game_html(game, context), unsafe_allow_html=True)

    st.markdown('<div class="kwl5-boundary">STEP 5 BOUNDARY • H2H / roster / starter / availability context is DESCRIPTIVE ONLY • sportsbook prices remain isolated in Step 2 • NO live projection • NO probability • NO Monte Carlo • NO recommendation</div>', unsafe_allow_html=True)
