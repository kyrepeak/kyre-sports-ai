"""WNBA Live Games V1 — Step 1 verified live slate + current game state.

Brand-new isolated live-game route. Step 1 intentionally stops before sportsbook
markets, betting projections, Monte Carlo, edge, EV, qualification or picks.

State contract
--------------
- Use ESPN WNBA daily scoreboard for current score/period/clock/quarter lines.
- Reconcile every live matchup to the existing verified WNBA selected-date slate.
- Accept WNBA team identities only.
- Fail closed on matchup/source conflicts instead of displaying a fake live card.
- Capture the exact state-observation timestamp for later live-odds firewall work.
- Keep manual refresh during Step 1 so the parser can be visually verified before
  any automatic refresh/market synchronization is introduced.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_data_v232 as data232
import wnba_schedule_v25 as schedule25

MODEL_VERSION = "WNBA LIVE GAMES V1 • STEP 1 VERIFIED LIVE STATE"
ET = ZoneInfo("America/New_York")
ESPN_SCOREBOARD = data232.ESPN_SCOREBOARD


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_score(value):
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    try:
        return int(round(float(value)))
    except Exception:
        return None


def _team_id(team: dict) -> int:
    try:
        return int(data232._team_id(team or {}) or 0)
    except Exception:
        return 0


def _logo(team_id, espn_team: dict | None = None) -> str:
    try:
        direct = str(schedule25.logo_url(int(team_id)) or "")
    except Exception:
        direct = ""
    if direct:
        return direct
    team = espn_team or {}
    logos = team.get("logos") or []
    if logos and isinstance(logos[0], dict):
        return str(logos[0].get("href") or "")
    return str(team.get("logo") or "")


def _status_payload(event: dict, comp: dict) -> dict:
    status = event.get("status") or comp.get("status") or {}
    status_type = status.get("type") or {}
    state = str(status_type.get("state") or "").lower()
    completed = bool(status_type.get("completed"))
    detail = str(
        status_type.get("shortDetail")
        or status_type.get("detail")
        or status_type.get("description")
        or ""
    ).strip()
    period = _safe_int(status.get("period") or event.get("period") or comp.get("period"), 0)
    clock = str(status.get("displayClock") or event.get("displayClock") or comp.get("displayClock") or "").strip()

    dlow = detail.lower()
    is_live = (state in {"in", "live"} or any(x in dlow for x in ("quarter", "halftime", "end of", " ot", "overtime"))) and not completed
    if "halftime" in dlow or "half time" in dlow:
        phase = "HALFTIME"
    elif "end of" in dlow:
        phase = detail.upper()
    elif period <= 0:
        phase = detail.upper() if detail else "LIVE"
    elif period <= 4:
        phase = f"Q{period}"
    else:
        ot_number = max(1, period - 4)
        phase = "OT" if ot_number == 1 else f"{ot_number}OT"

    return {
        "state": state,
        "completed": completed,
        "detail": detail,
        "period": period,
        "clock": clock,
        "phase": phase,
        "is_live": bool(is_live),
    }


def _line_scores(competitor: dict) -> dict[int, int]:
    out: dict[int, int] = {}
    for idx, item in enumerate(competitor.get("linescores") or [], 1):
        if not isinstance(item, dict):
            continue
        period = _safe_int(item.get("period"), idx)
        score = _safe_score(item.get("displayValue", item.get("value")))
        if period > 0 and score is not None:
            out[period] = score
    return out


def _event_date_et(value) -> str:
    if not value:
        return ""
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert(ET).strftime("%Y-%m-%d")
    except Exception:
        return ""


@st.cache_data(ttl=8, show_spinner=False, max_entries=8)
def _espn_live_snapshot(day_str: str):
    fetched_at = datetime.now(ET)
    meta = {
        "provider": "ESPN WNBA daily scoreboard",
        "fetched_at": fetched_at.isoformat(),
        "http": None,
        "events": 0,
        "live_events": 0,
        "parsed": 0,
        "error": "",
    }
    try:
        response = requests.get(
            ESPN_SCOREBOARD,
            params={"dates": pd.to_datetime(day_str).strftime("%Y%m%d"), "limit": 100},
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            timeout=8,
        )
        meta["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return [], meta

    rows = []
    events = (payload or {}).get("events") or []
    meta["events"] = len(events)
    for event in events:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        sides = {}
        for competitor in comp.get("competitors") or []:
            sides[str(competitor.get("homeAway") or "").lower()] = competitor
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        away_id, home_id = _team_id(away_t), _team_id(home_t)
        if not away_id or not home_id:
            continue

        status = _status_payload(event, comp)
        if not status["is_live"]:
            continue
        meta["live_events"] += 1

        away_score = _safe_score(away_c.get("score"))
        home_score = _safe_score(home_c.get("score"))
        away_lines = _line_scores(away_c)
        home_lines = _line_scores(home_c)
        event_date = _event_date_et(event.get("date") or comp.get("date"))
        if event_date and event_date != day_str:
            continue

        venue = comp.get("venue") or {}
        address = venue.get("address") or {}
        city = str(address.get("city") or "").strip()
        state = str(address.get("state") or "").strip()
        venue_name = str(venue.get("fullName") or "Venue TBD").strip()
        venue_text = venue_name
        if city:
            venue_text += f" • {city}{(', ' + state) if state else ''}"

        rows.append({
            "espn_event_id": str(event.get("id") or ""),
            "event_date": event_date or day_str,
            "away_team_id": away_id,
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "away_abbr": str(away_t.get("abbreviation") or ""),
            "away_logo": _logo(away_id, away_t),
            "away_score": away_score,
            "away_lines": away_lines,
            "home_team_id": home_id,
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "home_abbr": str(home_t.get("abbreviation") or ""),
            "home_logo": _logo(home_id, home_t),
            "home_score": home_score,
            "home_lines": home_lines,
            "period": status["period"],
            "clock": status["clock"],
            "phase": status["phase"],
            "status_detail": status["detail"],
            "venue": venue_text,
            "captured_at": fetched_at.isoformat(),
        })
    meta["parsed"] = len(rows)
    return rows, meta


def _verified_pairs(schedule: pd.DataFrame) -> set[tuple[int, int]]:
    out = set()
    if schedule is None or schedule.empty:
        return out
    for _, row in schedule.iterrows():
        a = _safe_int(row.get("away_team_id"))
        h = _safe_int(row.get("home_team_id"))
        if a and h:
            out.add((a, h))
    return out


def _state_watch(game: dict, now: datetime):
    game_id = str(game.get("espn_event_id") or f"{game.get('away_team_id')}-{game.get('home_team_id')}")
    fingerprint = (
        game.get("away_score"), game.get("home_score"), game.get("period"), game.get("clock"),
        tuple(sorted((game.get("away_lines") or {}).items())), tuple(sorted((game.get("home_lines") or {}).items())),
    )
    store = st.session_state.setdefault("wnba_live_v1_state_watch", {})
    previous = store.get(game_id) or {}
    changed = previous.get("fingerprint") != fingerprint
    changed_at = now if changed or not previous.get("changed_at") else previous.get("changed_at")
    store[game_id] = {"fingerprint": fingerprint, "changed_at": changed_at}
    return changed_at, changed


def _img(url: str, alt: str) -> str:
    src = escape(str(url or ""), quote=True)
    alt = escape(str(alt or "WNBA team"), quote=True)
    return f'<img src="{src}" alt="{alt}">' if src else '<div class="kwl1-ball">🏀</div>'


def _period_label(period: int) -> str:
    if period <= 0:
        return "—"
    if period <= 4:
        return f"Q{period}"
    return "OT" if period == 5 else f"{period - 4}OT"


def _quarters_html(game: dict) -> str:
    away = game.get("away_lines") or {}
    home = game.get("home_lines") or {}
    periods = sorted(set(away) | set(home) | set(range(1, max(4, _safe_int(game.get("period"), 0)) + 1)))
    periods = [p for p in periods if p > 0][:8]
    if not periods:
        return '<div class="kwl1-empty-small">Quarter scoring has not populated yet.</div>'

    headers = "".join(f'<span>{escape(_period_label(p))}</span>' for p in periods)
    away_cells = "".join(f'<span>{escape(str(away.get(p, "—")))}</span>' for p in periods)
    home_cells = "".join(f'<span>{escape(str(home.get(p, "—")))}</span>' for p in periods)
    cols = len(periods)
    return f'''<div class="kwl1-qtable" style="--qcols:{cols}">
<div class="kwl1-qrow head"><b>TEAM</b>{headers}<b>T</b></div>
<div class="kwl1-qrow"><b>{escape(str(game.get('away_abbr') or 'AWAY'))}</b>{away_cells}<strong>{game.get('away_score') if game.get('away_score') is not None else '—'}</strong></div>
<div class="kwl1-qrow"><b>{escape(str(game.get('home_abbr') or 'HOME'))}</b>{home_cells}<strong>{game.get('home_score') if game.get('home_score') is not None else '—'}</strong></div>
</div>'''


def _card(game: dict, verification_source: str, now: datetime) -> str:
    changed_at, changed = _state_watch(game, now)
    if isinstance(changed_at, str):
        try:
            changed_at = datetime.fromisoformat(changed_at)
        except Exception:
            changed_at = now
    away = escape(str(game.get("away_team") or "Away"))
    home = escape(str(game.get("home_team") or "Home"))
    status = escape(str(game.get("status_detail") or game.get("phase") or "LIVE"))
    phase = escape(str(game.get("phase") or "LIVE"))
    clock = escape(str(game.get("clock") or ""))
    venue = escape(str(game.get("venue") or "Venue TBD"))
    captured = now.strftime("%-I:%M:%S %p ET")
    observed = changed_at.astimezone(ET).strftime("%-I:%M:%S %p ET") if hasattr(changed_at, "astimezone") else captured
    score_a = game.get("away_score") if game.get("away_score") is not None else "—"
    score_h = game.get("home_score") if game.get("home_score") is not None else "—"
    state_badge = "STATE CHANGED" if changed else "STATE RECONFIRMED"

    return f'''<div class="kwl1-card">
<div class="kwl1-top"><span class="kwl1-live"><i></i> VERIFIED LIVE STATE</span><span class="kwl1-state">{state_badge}</span></div>
<div class="kwl1-scoreboard">
<div class="kwl1-team">{_img(game.get('away_logo',''), away)}<div><b>{away}</b><small>AWAY</small></div><strong>{score_a}</strong></div>
<div class="kwl1-center"><span>{phase}</span><b>{clock or status}</b><small>{status}</small></div>
<div class="kwl1-team home"><strong>{score_h}</strong><div><b>{home}</b><small>HOME</small></div>{_img(game.get('home_logo',''), home)}</div>
</div>
<div class="kwl1-section-title">QUARTER-BY-QUARTER</div>
{_quarters_html(game)}
<div class="kwl1-meta-grid">
<div><small>GAME STATE</small><strong>{phase}{(' • ' + clock) if clock else ''}</strong></div>
<div><small>VENUE</small><strong>{venue}</strong></div>
<div><small>STATE SNAPSHOT</small><strong>{captured}</strong></div>
<div><small>LAST OBSERVED CHANGE</small><strong>{observed}</strong></div>
<div><small>EVENT ID</small><strong>{escape(str(game.get('espn_event_id') or '—'))}</strong></div>
<div><small>SLATE VERIFICATION</small><strong>{escape(verification_source or 'verified schedule')}</strong></div>
</div>
<div class="kwl1-boundary">STEP 1 ONLY • current score / quarter / clock / period scoring • NO live sportsbook line • NO projection • NO probability • NO Monte Carlo • NO pick</div>
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl1-hero{border:1px solid #294b65;border-radius:22px;padding:20px;margin:10px 0 14px;background:linear-gradient(145deg,#09192a,#071421);box-shadow:0 18px 45px rgba(0,0,0,.18)}
.kwl1-eyebrow{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#8ad9ff}.kwl1-hero h2{font-size:1.7rem;margin:8px 0 6px;color:#f7fbff}.kwl1-hero p{color:#91a8ba;line-height:1.55;margin:0}.kwl1-hero b{color:#8ef0be}
.kwl1-health{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 15px}.kwl1-chip{border:1px solid #315b73;border-radius:999px;padding:7px 10px;font-size:.62rem;font-weight:900;color:#bfdae9;background:#081a29}.kwl1-chip.good{border-color:#2d8058;background:#0c3025;color:#8bf0b7}.kwl1-chip.warn{border-color:#8b652d;background:#332512;color:#ffd28a}
.kwl1-card{border:1px solid #315b73;border-radius:22px;padding:18px;margin:14px 0;background:#081725;box-shadow:0 15px 35px rgba(0,0,0,.2)}
.kwl1-top{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center}.kwl1-live,.kwl1-state{font-size:.6rem;font-weight:950;letter-spacing:.05em;border-radius:999px;padding:7px 9px}.kwl1-live{background:#0c3326;border:1px solid #2b8b60;color:#83f0b8}.kwl1-live i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#4dff91;margin-right:5px;box-shadow:0 0 9px #4dff91}.kwl1-state{border:1px solid #335a72;color:#a9cbdd;background:#0a1e2d}
.kwl1-scoreboard{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px;margin:18px 0}.kwl1-team{display:flex;align-items:center;gap:9px;min-width:0}.kwl1-team.home{justify-content:flex-end;text-align:right}.kwl1-team img,.kwl1-ball{width:48px;height:48px;object-fit:contain;flex:0 0 48px}.kwl1-team b{display:block;color:#f5faff;font-size:.82rem;line-height:1.15}.kwl1-team small{display:block;color:#738fa3;font-size:.48rem;font-weight:900;margin-top:4px}.kwl1-team strong{font-size:2rem;color:#fff;margin-left:auto}.kwl1-team.home strong{margin-left:0;margin-right:auto}.kwl1-center{text-align:center;min-width:76px}.kwl1-center span{display:block;color:#7df0b5;font-size:.65rem;font-weight:950}.kwl1-center b{display:block;color:#fff;font-size:1.05rem;margin:2px 0}.kwl1-center small{display:block;color:#7f99aa;font-size:.5rem;max-width:100px}
.kwl1-section-title{font-size:.58rem;font-weight:950;color:#95dfff;letter-spacing:.07em;margin:11px 0 6px}.kwl1-qtable{overflow-x:auto;border:1px solid #25475d;border-radius:13px;background:#06131f}.kwl1-qrow{display:grid;grid-template-columns:70px repeat(var(--qcols),minmax(34px,1fr)) 42px;min-width:max-content;align-items:center;border-top:1px solid rgba(50,83,105,.45)}.kwl1-qrow:first-child{border-top:0}.kwl1-qrow span,.kwl1-qrow b,.kwl1-qrow strong{padding:8px 7px;text-align:center;font-size:.58rem}.kwl1-qrow b:first-child{text-align:left;color:#cfe1ec}.kwl1-qrow strong{color:#fff;font-size:.68rem}.kwl1-qrow.head{color:#66859a}.kwl1-qrow.head b,.kwl1-qrow.head span{font-size:.45rem;color:#6f8da0;font-weight:950}.kwl1-empty-small{color:#7891a1;font-size:.62rem;padding:10px;border:1px solid #25475d;border-radius:12px}
.kwl1-meta-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:13px 0}.kwl1-meta-grid div{border:1px solid #26485e;border-radius:12px;padding:10px;background:#071521;min-width:0}.kwl1-meta-grid small{display:block;color:#718da0;font-size:.43rem;font-weight:950;letter-spacing:.04em}.kwl1-meta-grid strong{display:block;color:#eef7fc;font-size:.62rem;margin-top:4px;line-height:1.35;overflow-wrap:anywhere}.kwl1-boundary{border-top:1px solid rgba(63,101,124,.45);margin-top:12px;padding-top:10px;color:#678497;font-size:.48rem;line-height:1.5}
.kwl1-empty{border:1px dashed #31556d;border-radius:18px;padding:22px;text-align:center;background:#071522;color:#9eb3c0}.kwl1-empty b{display:block;font-size:1rem;color:#edf8ff;margin-bottom:6px}.kwl1-slate-row{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid rgba(60,88,106,.35);padding:8px 2px;color:#9db1bf;font-size:.68rem}.kwl1-slate-row:last-child{border-bottom:0}.kwl1-slate-row b{color:#ecf5fa}
@media(max-width:640px){.kwl1-hero{padding:16px}.kwl1-hero h2{font-size:1.45rem}.kwl1-card{padding:14px}.kwl1-scoreboard{gap:5px}.kwl1-team{gap:5px}.kwl1-team img,.kwl1-ball{width:36px;height:36px;flex-basis:36px}.kwl1-team b{font-size:.64rem}.kwl1-team strong{font-size:1.65rem}.kwl1-center{min-width:63px}.kwl1-center b{font-size:.85rem}.kwl1-meta-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>''', unsafe_allow_html=True)


def _today_slate_expander(schedule: pd.DataFrame):
    if schedule is None or schedule.empty:
        return
    with st.expander("📋 Today's verified WNBA slate"):
        for _, row in schedule.iterrows():
            st.markdown(
                f'<div class="kwl1-slate-row"><span><b>{escape(str(row.get("away_team") or "Away"))}</b> @ <b>{escape(str(row.get("home_team") or "Home"))}</b></span><span>{escape(str(row.get("status_text") or row.get("status") or ""))}</span></div>',
                unsafe_allow_html=True,
            )


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _css()
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")

    st.markdown(f'''<div class="kwl1-hero">
<div class="kwl1-eyebrow">⚡ WNBA LIVE GAMES • {MODEL_VERSION}</div>
<h2>Step 1 • Verified Live Slate + Current Game State</h2>
<p>Live game-state foundation only. <b>No betting recommendation exists on this page yet.</b> We verify the matchup before displaying ESPN's current score, period, clock and quarter-by-quarter scoring.</p>
</div>''', unsafe_allow_html=True)

    if st.button("🔄 Refresh live game state", use_container_width=True, type="primary", key="wnba_live_v1_refresh"):
        try:
            _espn_live_snapshot.clear()
        except Exception:
            pass
        try:
            schedule25.clear_schedule_cache()
        except Exception:
            pass
        st.rerun()

    st.caption("Step 1 uses manual refresh while we verify the live parser. Automatic refresh + sportsbook synchronization will be added only after the state firewall is validated.")

    try:
        verified_schedule = schedule25.schedule_for_date(day_str)
        diag = schedule25.schedule_diagnostics(day_str) or {}
    except Exception as exc:
        verified_schedule = pd.DataFrame()
        diag = {"state": "PROVIDER_FAILURE", "chosen_source": "none", "error": str(exc)[:180]}

    live_rows, live_meta = _espn_live_snapshot(day_str)
    schedule_state = str(diag.get("state") or "CHECK").upper()
    schedule_ok = schedule_state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE"}
    pairs = _verified_pairs(verified_schedule)

    accepted, conflicts = [], []
    for game in live_rows:
        pair = (_safe_int(game.get("away_team_id")), _safe_int(game.get("home_team_id")))
        score_ok = game.get("away_score") is not None and game.get("home_score") is not None
        period_ok = _safe_int(game.get("period"), 0) >= 1 or "HALF" in str(game.get("phase") or "").upper()
        if schedule_ok and pair in pairs and score_ok and period_ok:
            accepted.append(game)
        else:
            conflicts.append({"game": game, "pair_verified": pair in pairs, "score_ok": score_ok, "period_ok": period_ok})

    source_name = str(diag.get("chosen_source") or "verified schedule")
    health = [
        f'<span class="kwl1-chip {"good" if schedule_ok else "warn"}">SLATE • {escape(schedule_state)}</span>',
        f'<span class="kwl1-chip {"good" if not live_meta.get("error") else "warn"}">LIVE FEED • {"CONNECTED" if not live_meta.get("error") else "SOURCE CHECK"}</span>',
        f'<span class="kwl1-chip good">WNBA ONLY</span>',
        f'<span class="kwl1-chip {"good" if not conflicts else "warn"}">STATE CONFLICTS • {len(conflicts)}</span>',
    ]
    st.markdown(f'<div class="kwl1-health">{"".join(health)}</div>', unsafe_allow_html=True)

    if not schedule_ok:
        if schedule_state == "VERIFIED_OFF_DAY":
            st.markdown('<div class="kwl1-empty"><b>No verified WNBA games on today\'s ET slate.</b>The live page fails closed instead of borrowing games from another date or league.</div>', unsafe_allow_html=True)
        else:
            st.error("WNBA slate verification is not healthy enough to certify a live game. Step 1 is failing closed until the schedule identity source reconnects.")
        _today_slate_expander(verified_schedule)
        return

    if live_meta.get("error"):
        st.error(f"ESPN WNBA live-state source check: {live_meta.get('error')}")
        _today_slate_expander(verified_schedule)
        return

    if conflicts:
        st.warning(f"{len(conflicts)} live event(s) were withheld because matchup identity, score, or period did not reconcile to the verified WNBA slate. No conflicted state is allowed onto the live board.")

    if not accepted:
        st.markdown(
            f'<div class="kwl1-empty"><b>No verified WNBA game is live right now.</b>Today\'s verified slate contains {len(verified_schedule)} game(s). ESPN returned {int(live_meta.get("live_events") or 0)} live-state candidate(s), and none passed the full Step-1 live-state gate.</div>',
            unsafe_allow_html=True,
        )
        _today_slate_expander(verified_schedule)
        st.info("STEP 1 BOUNDARY • No live sportsbook markets, model probabilities, spreads, totals, moneylines, Monte Carlo, EV, qualification or picks are connected yet.")
        return

    st.markdown(f"### 🔴 Verified Live Games ({len(accepted)})")
    st.caption(f"State captured {now.strftime('%-I:%M:%S %p ET')} • Slate verification: {source_name} • ESPN current-state feed")
    for game in accepted:
        st.markdown(_card(game, source_name, now), unsafe_allow_html=True)

    _today_slate_expander(verified_schedule)
    st.info("🔒 STEP 1 BOUNDARY • Current game state only. Live Moneyline / Spread / Game Total prices, projections, Monte Carlo, edge, EV, qualification and recommendations do not exist on this new page yet.")


__all__ = ["MODEL_VERSION", "render_wnba_live_hub"]
