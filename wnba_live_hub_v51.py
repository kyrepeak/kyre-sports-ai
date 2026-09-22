"""WNBA Live Games V5.1 — isolated Step-5 completed-game validation preview.

The production Live Games stack remains V5. This wrapper only adds an opt-in
preview below Step 5 when there is NO Step-1 verified live WNBA game. A completed
ESPN game is used to validate H2H/starter/rotation/current-availability rendering.
It is never injected into the live-state, sportsbook or future model paths.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_context_v1 as ctx
import wnba_live_hub_v2 as v2
import wnba_live_hub_v5 as v5
import wnba_live_step5_preview_v1 as preview

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V5.1 • STEP-5 VALIDATION PREVIEW"


def _date(value):
    try:
        return pd.to_datetime(value, utc=True).tz_convert(ET).strftime("%b %-d, %Y • %-I:%M %p ET")
    except Exception:
        return str(value or "—")


def _injury_rows(av: dict, team_id: int) -> list[dict]:
    out = []
    for row in av.get("injuries") or []:
        try:
            if int(row.get("TEAM_ID") or 0) == int(team_id):
                out.append(row)
        except Exception:
            continue
    return out


def _preview_team_html(game: dict, context: dict, current_av: dict, side: str) -> str:
    team_id = int(game.get(f"{side}_team_id") or 0)
    name = str(game.get(f"{side}_team") or side.title())
    logo = str(game.get(f"{side}_logo") or "")
    role = "AWAY" if side == "away" else "HOME"

    coverage = {int(k): bool(v) for k, v in (current_av.get("team_status_coverage") or {}).items()}
    covered = bool(coverage.get(team_id, False))
    injuries = _injury_rows(current_av, team_id)

    if covered:
        feed_badge = '<span class="good">CURRENT INJURY FEED CONNECTED</span>'
    else:
        feed_badge = '<span class="bad">CURRENT AVAILABILITY UNVERIFIED</span>'

    if injuries:
        items = []
        for row in injuries:
            status = str(row.get("DESIGNATION") or "NO DESIGNATION")
            detail = str(row.get("DETAIL") or "").strip()
            source = str(row.get("SOURCE") or row.get("STATUS_SOURCE") or "ESPN WNBA")
            items.append(
                f'<div class="kwl5-status"><div><b>{escape(str(row.get("PLAYER_NAME") or "Player"))}</b>'
                f'<small>{escape(detail or source)}</small></div>'
                f'<span class="{v5._status_class(status)}">{escape(status)}</span></div>'
            )
        injury_html = "".join(items)
    elif covered:
        injury_html = '<div class="kwl5-ok">No ESPN-reported active designation in the CURRENT preview-time team injury feed.</div>'
    else:
        injury_html = '<div class="kwl5-alert">Current injury/status coverage is unavailable. Blank data is not treated as healthy.</div>'

    preview_starters = (context.get("current_starters") or {}).get(team_id) or []
    rotation = (context.get("rotation") or {}).get(team_id) or []
    entered = [str(x.get("name") or "") for x in rotation if x.get("name")]
    prior = (context.get("last_starters") or {}).get(team_id) or {}
    prior_starters = prior.get("starters") or []

    starters_html = " • ".join(escape(x) for x in preview_starters) if preview_starters else "No explicit five-starter sample found in this completed preview game's ESPN summary."
    rotation_html = " • ".join(escape(x) for x in entered) if entered else "No entered-player rotation parsed from this completed preview game."
    prior_html = " • ".join(escape(str(x)) for x in prior_starters) if prior_starters else "No prior explicit five-starter sample verified."
    prior_title = "PRIOR VERIFIED STARTERS"
    if prior.get("date"):
        prior_title += f" • {escape(_date(prior.get('date')))}"

    preview_set = {str(x).lower() for x in preview_starters}
    prior_set = {str(x).lower() for x in prior_starters}
    if preview_set and prior_set:
        added = [x for x in preview_starters if x.lower() not in prior_set]
        missing = [x for x in prior_starters if x.lower() not in preview_set]
        if added or missing:
            pieces = []
            if added:
                pieces.append("IN " + ", ".join(added))
            if missing:
                pieces.append("OUT OF STARTING FIVE " + ", ".join(missing))
            change = "Preview-game starter change vs prior verified game: " + " • ".join(pieces)
        else:
            change = "Preview-game explicit starters match the prior verified starting five."
    else:
        change = "Starter-change validation is pending because both explicit five-player starter samples are not available."

    return f"""<div class="kwl5-team kwl5p-team">
<div class="kwl5-teamhead"><div class="kwl5-ident">{v5._logo(logo,name)}<div><b>{escape(name)}</b><small>{role} • COMPLETED PREVIEW GAME</small></div></div>{feed_badge}</div>
<div class="kwl5-subtitle">CURRENT AVAILABILITY • PREVIEW-TIME SNAPSHOT</div>{injury_html}
<div class="kwl5-box"><small>PREVIEW GAME • EXPLICIT STARTERS</small><p>{starters_html}</p></div>
<div class="kwl5-box"><small>PREVIEW GAME • PLAYERS VERIFIED AS ENTERED</small><p>{rotation_html}</p><em>{len(entered)} player(s) observed</em></div>
<div class="kwl5-box"><small>{prior_title}</small><p>{prior_html}</p></div>
<div class="kwl5-change">{escape(change)}</div>
</div>"""


def _preview_html(game: dict, context: dict, current_av: dict, discovery_meta: dict) -> str:
    h = context.get("h2h") or {}
    hist_error = str((context.get("history_meta") or {}).get("error") or "")
    summary_ok = bool((context.get("current_summary_meta") or {}).get("available"))
    avail_error = str(current_av.get("error") or "")
    state = "READY" if not hist_error and summary_ok and not avail_error else "CHECK"

    diag = []
    if hist_error:
        diag.append("H2H: " + hist_error)
    if not summary_ok:
        diag.append("preview game summary unavailable")
    if avail_error:
        diag.append("current availability: " + avail_error)

    return f"""<div class="kwl5p-game">
<div class="kwl5p-head"><div><small>🧪 COMPLETED-GAME VALIDATION PREVIEW • NOT LIVE</small><b>{escape(str(game.get('away_team') or 'Away'))} @ {escape(str(game.get('home_team') or 'Home'))}</b></div><div><strong>{game.get('away_score','—')}–{game.get('home_score','—')}</strong><small>FINAL • {_date(game.get('captured_at'))}</small></div></div>
<div class="kwl5p-badges"><span class="{'good' if state == 'READY' else 'warn'}">PREVIEW CONTEXT • {state}</span><span>ESPN EVENT {escape(str(game.get('espn_event_id') or '—'))}</span><span>H2H {int(h.get('games') or 0)} GP BEFORE PREVIEW GAME</span><span>DISCOVERY {int(discovery_meta.get('usable') or 0)} RECENT GAME(S)</span></div>
<div class="kwl5p-warning"><b>ISOLATED TEST MODE.</b> The completed game below is never inserted into Step 1's live slate, Step 2 sportsbook markets, Step 3 pace analysis, Step 4 live context, or any future projection. H2H is calculated strictly before this preview game. Injury designations are a <b>current preview-time feed</b>, not a claim about the historical injury report on the preview game's date.</div>
{v5._h2h_html(game, context)}
<div class="kwl5-teams">{_preview_team_html(game,context,current_av,'away')}{_preview_team_html(game,context,current_av,'home')}</div>
{f'<div class="kwl5-diag">PREVIEW SOURCE CHECK • {escape(" • ".join(diag))}</div>' if diag else ''}
<div class="kwl5-note">PREVIEW BOUNDARY • DISPLAY/TRANSPORT VALIDATION ONLY • NO live state • NO sportsbook attachment • NO projection • NO probability • NO Monte Carlo • NO edge/EV • NO qualification • NO ranking • NO pick.</div>
</div>"""


def _css():
    st.markdown(r"""<style>
.kwl5p-shell{border:1px dashed #6a5d27;border-radius:22px;padding:18px;margin:24px 0 14px;background:linear-gradient(145deg,#151408,#0a1723)}
.kwl5p-shell h3{margin:7px 0;color:#f5f8fb;font-size:1.28rem}.kwl5p-shell p{color:#9db0bd;line-height:1.55;margin:0}.kwl5p-shell b{color:#fff}.kwl5p-eyebrow{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#ead879}
.kwl5p-game{border:1px solid #6e632d;border-radius:22px;padding:16px;margin:14px 0;background:#0a1723}.kwl5p-head{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid #3e3a20;padding-bottom:12px}.kwl5p-head>div{display:flex;flex-direction:column;gap:4px}.kwl5p-head>div:last-child{text-align:right}.kwl5p-head small{font-size:.61rem;color:#9e9a78;font-weight:850}.kwl5p-head b{color:#f5f8fb}.kwl5p-head strong{font-size:1.35rem;color:#fff}
.kwl5p-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl5p-badges span{font-size:.57rem;border:1px solid #4d543d;border-radius:999px;padding:6px 8px;color:#b7bea4;font-weight:900}.kwl5p-badges .good{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl5p-badges .warn{border-color:#8a722a;color:#ead879;background:#2a240d}
.kwl5p-warning{border:1px solid #8a722a;background:#2a240d;color:#ead879;border-radius:14px;padding:12px;font-size:.65rem;line-height:1.55;margin:10px 0 13px}.kwl5p-team{border-color:#405568}
@media(max-width:640px){.kwl5p-shell,.kwl5p-game{padding:14px}.kwl5p-head{align-items:center}.kwl5p-head b{font-size:.9rem}}
</style>""", unsafe_allow_html=True)


def _option_label(game: dict) -> str:
    return (
        f"{_date(game.get('captured_at')).split(' • ')[0]} • "
        f"{game.get('away_team','Away')} {game.get('away_score','—')}–{game.get('home_score','—')} {game.get('home_team','Home')}"
    )


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Production Steps 1-5 render unchanged first.
    v5.render_wnba_live_hub(section_header, status_info, team_logo, h)

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    live_games, _, _ = v2._verified_live_games(day_str)
    if live_games:
        # Preview is deliberately hidden while a verified live game exists.
        return

    _css()
    st.markdown(f"""<div class="kwl5p-shell"><div class="kwl5p-eyebrow">🧪 {MODEL_VERSION}</div><h3>Step 5 Validation Preview</h3><p>No verified WNBA game is live, so you can optionally load one <b>recent completed regular-season matchup</b> to validate Step-5 H2H, starter, rotation and availability presentation. This preview is isolated from every live/model path.</p></div>""", unsafe_allow_html=True)

    enabled = bool(st.session_state.get("wnba_live_step5_preview_enabled", False))
    if not enabled:
        if st.button("🧪 Load Step 5 validation preview", use_container_width=True, key="wnba_live_step5_preview_load"):
            st.session_state["wnba_live_step5_preview_enabled"] = True
            st.rerun()
        st.caption("Preview remains OFF by default. It cannot create a live game, market, probability or pick.")
        return

    top_left, top_right = st.columns(2)
    with top_left:
        if st.button("🔄 Refresh preview data", use_container_width=True, key="wnba_live_step5_preview_refresh"):
            preview.clear_cache()
            ctx.clear_cache()
            st.rerun()
    with top_right:
        if st.button("✖ Exit preview mode", use_container_width=True, key="wnba_live_step5_preview_exit"):
            st.session_state["wnba_live_step5_preview_enabled"] = False
            st.rerun()

    previews, discovery_meta = preview.recent_completed_previews(day_str)
    if not previews:
        st.warning(
            "Step-5 preview could not discover a recent completed regular-season game. "
            f"Diagnostic: {discovery_meta.get('error') or discovery_meta}"
        )
        return

    selected = st.selectbox(
        "Completed matchup used for Step-5 validation",
        options=list(range(len(previews))),
        format_func=lambda i: _option_label(previews[int(i)]),
        key="wnba_live_step5_preview_choice",
    )
    game = previews[int(selected)]

    with st.spinner("Building isolated Step-5 preview context…"):
        context = ctx.context_for_game(game)
        current_av = preview.current_availability_for_preview(game)

    st.markdown(_preview_html(game, context, current_av, discovery_meta), unsafe_allow_html=True)
    st.caption(
        "Preview transport: ESPN completed daily scoreboard + ESPN game summary. "
        "Current injury section: ESPN team injury feeds at preview time. No sportsbook data is requested by preview mode."
    )
