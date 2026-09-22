"""WNBA Live Games V2 — Step 2 exact live sportsbook market verification.

This wrapper preserves the frozen Step-1 page by rendering wnba_live_hub_v1
unchanged, then adds a read-only market layer underneath it. No projection,
Monte Carlo, edge, EV, qualification or pick is created in Step 2.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_hub_v1 as v1
import wnba_live_market_v1 as markets
import wnba_schedule_v25 as schedule25

MODEL_VERSION = "WNBA LIVE GAMES V2 • STEP 2 EXACT LIVE MARKETS"
ET = ZoneInfo("America/New_York")


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _verified_live_games(day_str: str):
    """Rebuild the exact frozen V1 acceptance contract without modifying V1."""
    try:
        verified_schedule = schedule25.schedule_for_date(day_str)
        diag = schedule25.schedule_diagnostics(day_str) or {}
    except Exception as exc:
        return [], {"state": "PROVIDER_FAILURE", "chosen_source": "none", "error": str(exc)[:180]}, {}

    live_rows, live_meta = v1._espn_live_snapshot(day_str)
    schedule_state = str(diag.get("state") or "CHECK").upper()
    schedule_ok = schedule_state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE"}
    pairs = v1._verified_pairs(verified_schedule)
    accepted = []
    for game in live_rows:
        pair = (_safe_int(game.get("away_team_id")), _safe_int(game.get("home_team_id")))
        score_ok = game.get("away_score") is not None and game.get("home_score") is not None
        period_ok = _safe_int(game.get("period"), 0) >= 1 or "HALF" in str(game.get("phase") or "").upper()
        if schedule_ok and pair in pairs and score_ok and period_ok:
            accepted.append(game)
    return accepted, diag, live_meta


def _pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _odds(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def _line(value, signed=True):
    try:
        x = float(value)
        return f"{x:+g}" if signed else f"{x:g}"
    except Exception:
        return "—"


def _secs(value):
    try:
        x = max(0, int(round(float(value))))
    except Exception:
        return "—"
    if x < 60:
        return f"{x}s"
    return f"{x // 60}m {x % 60:02d}s"


def _stamp_et(value):
    if not value:
        return "—"
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert(ET).strftime("%-I:%M:%S %p ET")
    except Exception:
        return "—"


def _market_side_text(row: dict, side: str):
    name = str(row.get(f"{side}_name") or "—")
    price = _odds(row.get(f"{side}_price"))
    line_value = row.get(f"{side}_line")
    market = str(row.get("market") or "")
    if market == "SPREAD":
        title = f"{name} {_line(line_value, signed=True)}"
    elif market == "TOTAL":
        title = f"{name} {_line(line_value, signed=False)}"
    else:
        title = name
    raw = _pct(row.get(f"{side}_raw_prob"))
    novig = _pct(row.get(f"{side}_novig_prob"))
    return title, price, raw, novig


def _pair_html(row: dict) -> str:
    lt, lp, lr, lnv = _market_side_text(row, "left")
    rt, rp, rr, rnv = _market_side_text(row, "right")
    freshness = str(row.get("freshness") or "CHECK")
    badge_cls = "good" if row.get("model_eligible_later") else "bad"
    exact = "EXACT PAIR" if row.get("pair_exact") else "LINE MISMATCH"
    hold = _pct(row.get("book_hold"))
    quote_age = _secs(row.get("quote_age_seconds"))
    skew = _secs(row.get("pair_skew_seconds"))
    lag = _secs(row.get("state_lag_seconds"))
    updated = _stamp_et(row.get("older_updated_at"))
    book = escape(str(row.get("book") or "Sportsbook"))
    firewall = escape(str(row.get("firewall") or "BLOCKED"))
    return f'''<div class="kwl2-book">
<div class="kwl2-bookhead"><b>{book}</b><span class="kwl2-badge {badge_cls}">{escape(freshness)}</span></div>
<div class="kwl2-sides">
<div><small>{escape(lt)}</small><strong>{lp}</strong><p>RAW {lr} • NO-VIG {lnv}</p></div>
<div><small>{escape(rt)}</small><strong>{rp}</strong><p>RAW {rr} • NO-VIG {rnv}</p></div>
</div>
<div class="kwl2-proof"><span>{exact}</span><span>HOLD {hold}</span><span>AGE {quote_age}</span><span>PAIR SKEW {skew}</span><span>STATE LAG {lag}</span></div>
<div class="kwl2-time">Conservative pair timestamp • {updated} • FIREWALL: <b>{firewall}</b></div>
</div>'''


def _market_block(game: dict, game_data: dict) -> str:
    rows = list((game_data or {}).get("pairs") or [])
    by_market = {name: [] for name in ("MONEYLINE", "SPREAD", "TOTAL")}
    for row in rows:
        market = str(row.get("market") or "").upper()
        if market in by_market:
            by_market[market].append(row)

    parts = []
    labels = {"MONEYLINE": "LIVE MONEYLINE", "SPREAD": "LIVE SPREAD", "TOTAL": "LIVE GAME TOTAL"}
    for market in ("MONEYLINE", "SPREAD", "TOTAL"):
        market_rows = sorted(
            by_market[market],
            key=lambda r: (
                not bool(r.get("model_eligible_later")),
                float(r.get("quote_age_seconds")) if r.get("quote_age_seconds") is not None else 10**9,
                str(r.get("book") or ""),
            ),
        )
        if not market_rows:
            content = '<div class="kwl2-empty">No exact same-book paired market returned for this market.</div>'
        else:
            content = "".join(_pair_html(r) for r in market_rows)
        parts.append(f'<div class="kwl2-market"><h4>{labels[market]}</h4>{content}</div>')

    good = sum(1 for r in rows if r.get("model_eligible_later"))
    blocked = len(rows) - good
    event_id = escape(str((game_data or {}).get("event_id") or "—"))
    return f'''<div class="kwl2-game">
<div class="kwl2-gamehead"><div><small>VERIFIED LIVE MATCHUP</small><b>{escape(str(game.get('away_team') or 'Away'))} @ {escape(str(game.get('home_team') or 'Home'))}</b></div><div><strong>{game.get('away_score','—')}–{game.get('home_score','—')}</strong><small>{escape(str(game.get('phase') or 'LIVE'))} • {escape(str(game.get('clock') or ''))}</small></div></div>
<div class="kwl2-sync"><span>STATE {_stamp_et(game.get('captured_at'))}</span><span>SGO EVENT {event_id}</span><span>{good} VERIFIED/USABLE PAIR(S)</span><span>{blocked} BLOCKED PAIR(S)</span></div>
{''.join(parts)}
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl2-hero{border:1px solid #31566f;border-radius:22px;padding:20px;margin:24px 0 14px;background:linear-gradient(145deg,#0a1929,#081522)}
.kwl2-eyebrow{font-size:.72rem;font-weight:950;letter-spacing:.08em;color:#8ad9ff}.kwl2-hero h3{font-size:1.45rem;margin:8px 0;color:#f6fbff}.kwl2-hero p{margin:0;color:#9bb0c0;line-height:1.55}.kwl2-hero b{color:#fff}
.kwl2-health{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px}.kwl2-health span{border:1px solid #31566f;border-radius:999px;padding:8px 11px;color:#b9cede;font-size:.72rem;font-weight:850}.kwl2-health .ok{border-color:#2d8257;color:#93efbc;background:#0d2d21}.kwl2-health .bad{border-color:#8c513f;color:#ffc0ac;background:#301b17}
.kwl2-game{border:1px solid #31566f;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl2-gamehead{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid #213b4e;padding-bottom:12px}.kwl2-gamehead div{display:flex;flex-direction:column;gap:4px}.kwl2-gamehead div:last-child{text-align:right}.kwl2-gamehead small{font-size:.64rem;color:#7892a6;font-weight:850;letter-spacing:.06em}.kwl2-gamehead b{font-size:1rem;color:#f5f8fb}.kwl2-gamehead strong{font-size:1.35rem;color:#fff}.kwl2-sync{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl2-sync span{font-size:.63rem;border:1px solid #28495e;border-radius:999px;padding:6px 8px;color:#9db4c5}
.kwl2-market{margin:14px 0}.kwl2-market h4{font-size:.76rem;color:#a8ddff;letter-spacing:.07em;margin:0 0 8px}.kwl2-book{border:1px solid #294a60;border-radius:17px;padding:12px;margin:8px 0;background:#07111d}.kwl2-bookhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.kwl2-bookhead b{color:#f4f8fb}.kwl2-badge{font-size:.62rem;font-weight:950;letter-spacing:.05em;padding:6px 8px;border-radius:999px}.kwl2-badge.good{color:#91efb8;border:1px solid #34855e;background:#0d2b20}.kwl2-badge.bad{color:#ffb4a1;border:1px solid #8f5143;background:#301b18}.kwl2-sides{display:grid;grid-template-columns:1fr 1fr;gap:9px}.kwl2-sides>div{border:1px solid #233f52;border-radius:13px;padding:10px}.kwl2-sides small{display:block;color:#8199ab;font-size:.65rem;font-weight:850;min-height:30px}.kwl2-sides strong{display:block;color:#fff;font-size:1.15rem;margin:4px 0}.kwl2-sides p{font-size:.61rem;color:#9eb2c0;margin:0;line-height:1.4}.kwl2-proof{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.kwl2-proof span{font-size:.58rem;color:#95aabd;border:1px solid #233f52;border-radius:999px;padding:5px 7px}.kwl2-time{margin-top:8px;color:#758da0;font-size:.59rem;line-height:1.4}.kwl2-time b{color:#d8e5ed}.kwl2-empty{border:1px dashed #315066;border-radius:13px;padding:11px;color:#849aaa;font-size:.72rem}.kwl2-boundary{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:15px;padding:13px;margin:15px 0;font-size:.72rem;line-height:1.55}
@media(max-width:640px){.kwl2-hero{padding:16px}.kwl2-game{padding:13px}.kwl2-gamehead{align-items:center}.kwl2-gamehead b{font-size:.9rem}.kwl2-sides small{min-height:34px}.kwl2-sync span{font-size:.59rem}}
</style>''', unsafe_allow_html=True)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Frozen Step 1 renders first, unmodified.
    v1.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _css()
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    st.markdown(f'''<div class="kwl2-hero">
<div class="kwl2-eyebrow">🎯 {MODEL_VERSION}</div>
<h3>Step 2 • Exact Live Sportsbook Markets</h3>
<p>Market verification only. We pair <b>Moneyline • Spread • Game Total</b> within the same sportsbook and exact line, preserve each side's quote timestamp, calculate raw/no-vig probabilities, and compare quote age against the frozen Step-1 game-state snapshot. <b>No pick exists yet.</b></p>
</div>''', unsafe_allow_html=True)

    if st.button("🔄 Refresh live state + sportsbook markets", use_container_width=True, type="primary", key="wnba_live_v2_refresh"):
        try:
            v1._espn_live_snapshot.clear()
        except Exception:
            pass
        try:
            schedule25.clear_schedule_cache()
        except Exception:
            pass
        markets.clear_cache()
        try:
            import wnba_sportsgameodds_v1 as sgo
            sgo.clear_cache()
        except Exception:
            pass
        st.rerun()

    games, diag, live_meta = _verified_live_games(day_str)
    if not games:
        st.info("No Step-1 verified WNBA game is live right now, so Step 2 will not display sportsbook markets.")
        st.markdown('<div class="kwl2-boundary">STEP 2 BOUNDARY • no live state = no market card • NO projection • NO Monte Carlo • NO edge/EV • NO qualification • NO pick</div>', unsafe_allow_html=True)
        return

    snap = markets.market_snapshot_for_live_games(games, day_str)
    state = str(snap.get("state") or "CHECK").upper()
    matched = int(snap.get("games_matched") or 0)
    requested = int(snap.get("games_requested") or 0)
    pairs = list(snap.get("pairs") or [])
    usable = sum(1 for r in pairs if r.get("model_eligible_later"))
    blocked = len(pairs) - usable
    health_cls = "ok" if state == "CONNECTED" else "bad"
    st.markdown(
        f'''<div class="kwl2-health">
<span class="{health_cls}">SPORTSGAMEODDS • {escape(state.replace('_',' '))}</span>
<span>LIVE GAMES MATCHED • {matched}/{requested}</span>
<span>EXACT PAIRS • {len(pairs)}</span>
<span class="{'ok' if usable else 'bad'}">FIREWALL-PASS PAIRS • {usable}</span>
<span class="{'bad' if blocked else ''}">BLOCKED • {blocked}</span>
<span>MARKET FETCH • {_stamp_et(snap.get('fetched_at'))}</span>
</div>''',
        unsafe_allow_html=True,
    )

    if state == "NO_API_KEY":
        st.warning("The existing SportsGameOdds key is not available on this deployment. Step 2 is withholding all live markets instead of substituting another source.")
    elif state == "PROVIDER_ERROR":
        st.warning(f"SportsGameOdds is temporarily unavailable: {snap.get('error') or 'provider error'}. Step 1 live state remains unaffected.")
    elif state in {"MATCH_FAILURE", "NO_OPEN_LIVE_MARKETS", "NO_VERIFIED_PAIRS"}:
        st.warning("The live WNBA game is verified, but no exact paired SportsGameOdds live ML/spread/total market passed transport matching right now. Nothing is being guessed.")

    by_game = snap.get("by_game") or {}
    for game in games:
        key = str(game.get("espn_event_id") or f"{game.get('away_team_id')}-{game.get('home_team_id')}")
        st.markdown(_market_block(game, by_game.get(key) or {}), unsafe_allow_html=True)

    st.markdown(
        f'''<div class="kwl2-boundary"><b>STEP 2 FIREWALL</b> • exact same-book pair required • spread lines must be exact opposites • total lines must match • older pair timestamp is used for age • pair timestamp skew must be ≤ {markets.MAX_PAIR_SKEW_SECONDS}s • quote/state lag must be ≤ {markets.MAX_STATE_LAG_SECONDS}s • quotes older than {markets.STALE_SECONDS}s are BLOCKED. These labels are transport verification only and are NOT betting recommendations.</div>''',
        unsafe_allow_html=True,
    )
    st.caption(
        "Step 2 only • SportsGameOdds full-game live ML / spread / total • raw implied + same-pair no-vig math • "
        "NO live projection • NO Monte Carlo • NO EV • NO qualification • NO strongest-pick ranking."
    )


__all__ = ["MODEL_VERSION", "render_wnba_live_hub"]
