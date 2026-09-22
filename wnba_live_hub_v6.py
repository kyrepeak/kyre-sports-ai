"""WNBA Live Games V6 — Step 6 live projection + 5M Monte Carlo UI.

Renders the frozen/verified V5.2 stack unchanged, then appends the first
prediction layer. The statistical mean is market-blind. Fresh Step-2 exact lines
are graded only after simulation and never alter the projection.

Step 6 intentionally stops before edge, EV, qualification, ranking or picks.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_hub_v1 as v1
import wnba_live_hub_v2 as v2
import wnba_live_hub_v52 as v52
import wnba_live_market_v1 as market
import wnba_live_projection_v1 as model

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V6 • STEP 6 LIVE PROJECTION + 5M MONTE CARLO"


def _pct(value, digits=1):
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except Exception:
        return "—"


def _num(value, digits=1, signed=False):
    try:
        x = float(value)
        return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    except Exception:
        return "—"


def _odds(value):
    try:
        x = int(value)
        return f"+{x}" if x > 0 else str(x)
    except Exception:
        return "—"


def _state_age(value):
    try:
        x = float(value)
        if x < 60:
            return f"{x:.0f}s"
        return f"{int(x // 60)}m {int(x % 60)}s"
    except Exception:
        return "—"


def _game_pairs(snapshot: dict, game: dict) -> list[dict]:
    key = str(game.get("espn_event_id") or f"{game.get('away_team_id')}-{game.get('home_team_id')}")
    rows = ((snapshot.get("by_game") or {}).get(key) or {}).get("pairs") or []
    return list(rows)


def _eligible_pairs(snapshot: dict, game: dict) -> list[dict]:
    return [r for r in _game_pairs(snapshot, game) if bool(r.get("model_eligible_later"))]


def _metric(label: str, value: str, sub: str = "") -> str:
    extra = f"<small>{escape(str(sub))}</small>" if sub else ""
    return f'<div class="kwl6-m"><span>{escape(label)}</span><b>{escape(str(value))}</b>{extra}</div>'


def _period_label(period: int) -> str:
    if period <= 4:
        return f"Q{period}"
    return "OT" if period == 5 else f"{period-4}OT"


def _projection_card(game: dict, p: dict, eligible: list[dict], state_age: float | None) -> str:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    score = f"{game.get('away_score','—')}–{game.get('home_score','—')}"
    phase = str(game.get("phase") or _period_label(int(game.get("period") or 1)))
    clock = str(game.get("clock") or "")
    ready = bool(p.get("ready"))
    quality = str(p.get("data_quality") or "LOW")
    ready_cls = "good" if ready else "bad"
    quality_cls = "good" if quality == "HIGH" else ("warn" if quality == "MEDIUM" else "bad")
    age_cls = "good" if state_age is not None and state_age <= model.MAX_STATE_AGE_SECONDS else "bad"
    avail = p.get("availability_meta") or {}

    segments = []
    for row in p.get("segments") or []:
        segments.append(
            f"{_period_label(int(row.get('period') or 1))} {float(row.get('minutes') or 0):.1f}m: "
            f"{away} {float(row.get('away_points') or 0):.1f} / {home} {float(row.get('home_points') or 0):.1f}"
        )
    segment_text = " • ".join(segments) if segments else "No competitive time remaining."

    return f'''<div class="kwl6-game">
<div class="kwl6-head"><div><small>VERIFIED LIVE MATCHUP • FIRST PREDICTION LAYER</small><b>{escape(away)} @ {escape(home)}</b></div><div><strong>{escape(score)}</strong><small>{escape(phase)}{(' • ' + escape(clock)) if clock else ''}</small></div></div>
<div class="kwl6-badges"><span class="{ready_cls}">MODEL READY • {'YES' if ready else 'NO'}</span><span class="{quality_cls}">MODEL DATA • {escape(quality)}</span><span class="{age_cls}">STATE AGE • {escape(_state_age(state_age))}</span><span>EXACT ELIGIBLE PAIRS • {len(eligible)}</span></div>
<div class="kwl6-title">STATE-CONDITIONAL STATISTICAL MEAN • BEFORE SPORTSBOOK</div>
<div class="kwl6-grid">
{_metric('PROJECTED REMAINING • ' + away, _num(p.get('projected_remaining_away'),1) + ' pts')}
{_metric('PROJECTED REMAINING • ' + home, _num(p.get('projected_remaining_home'),1) + ' pts')}
{_metric('BASE PROJECTED SCORE', f"{_num(p.get('projected_base_final_away'),1)}–{_num(p.get('projected_base_final_home'),1)}", 'regulation/current OT endpoint before tie-triggered extra periods')}
{_metric('BASE PROJECTED TOTAL', _num(p.get('projected_base_total'),1))}
{_metric('BASE HOME MARGIN', _num(p.get('projected_base_home_margin'),1,True) + ' pts')}
{_metric('RESIDUAL CORRELATION', _num(p.get('residual_correlation'),3))}
{_metric('UNCERTAINTY MULTIPLIER', _num(p.get('uncertainty_multiplier'),3) + '×')}
{_metric('HISTORY SAMPLE', f"A {int(p.get('away_history_games') or 0)} / H {int(p.get('home_history_games') or 0)}", f"{p.get('away_history_reliability','THIN')} / {p.get('home_history_reliability','THIN')}")}
{_metric('LIVE BOX QUALITY', str((p.get('flow') or {}).get('data_quality') or 'CHECK'))}
{_metric('AVAILABILITY COVERAGE', '2/2' if avail.get('both_teams_covered') else 'CHECK', f"active designations {int(avail.get('active_designations') or 0)}")}
</div>
<div class="kwl6-segments"><small>REMAINING-TIME CONSTRUCTION</small><p>{escape(segment_text)}</p></div>
<div class="kwl6-contract"><b>MODEL CONSTRUCTION.</b> Step-1 score/clock is the anchor. Step-3 pace/efficiency is regressed toward Step-4 completed-game scoring priors. Step-5 availability can widen uncertainty but V1 makes <b>no invented player-value point adjustment</b>. H2H is not used in the mean. Sportsbook price/no-vig probability is not a projection input.</div>
</div>'''


def _market_cards(game: dict, eligible: list[dict], result: dict) -> str:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    pieces = []
    seen = set()
    for row in eligible:
        book = str(row.get("book") or "Sportsbook")
        mkt = str(row.get("market") or "").upper()
        if mkt == "MONEYLINE":
            key = (book, mkt)
            if key in seen:
                continue
            seen.add(key)
            pieces.append(f'''<div class="kwl6-market"><div class="kwl6-markethead"><b>{escape(book)} • LIVE MONEYLINE</b><span>EXACT PAIR • STEP-2 FIREWALL PASS</span></div><div class="kwl6-marketgrid">
{_metric(away + ' WIN', _pct(result.get('away_win_probability')), 'FAIR ' + _odds(result.get('away_fair_odds')))}
{_metric(home + ' WIN', _pct(result.get('home_win_probability')), 'FAIR ' + _odds(result.get('home_fair_odds')))}
</div></div>''')
        elif mkt == "SPREAD":
            line = float(row.get("left_line") or 0.0)
            spec = (result.get("spread_results") or {}).get(f"SPREAD:{line:+.2f}") or {}
            if not spec:
                continue
            key = (book, mkt, line)
            if key in seen:
                continue
            seen.add(key)
            pieces.append(f'''<div class="kwl6-market"><div class="kwl6-markethead"><b>{escape(book)} • LIVE SPREAD</b><span>EXACT LINE • MARKET PRICE EXCLUDED</span></div><div class="kwl6-marketgrid">
{_metric(away + f' {line:+g}', _pct(spec.get('away_no_push_cover_probability')), 'FAIR ' + _odds(spec.get('away_fair_odds')))}
{_metric(home + f' {-line:+g}', _pct(spec.get('home_no_push_cover_probability')), 'FAIR ' + _odds(spec.get('home_fair_odds')))}
{_metric('PUSH', _pct(spec.get('push_probability')))}
{_metric('MC SE', _pct(spec.get('mc_se'),2), 'batch range ' + _num(spec.get('batch_range_pp'),2) + ' pp')}
</div></div>''')
        elif mkt == "TOTAL":
            line = float(row.get("left_line") or 0.0)
            spec = (result.get("total_results") or {}).get(f"TOTAL:{line:.2f}") or {}
            if not spec:
                continue
            key = (book, mkt, line)
            if key in seen:
                continue
            seen.add(key)
            pieces.append(f'''<div class="kwl6-market"><div class="kwl6-markethead"><b>{escape(book)} • LIVE TOTAL {line:g}</b><span>EXACT LINE • MARKET PRICE EXCLUDED</span></div><div class="kwl6-marketgrid">
{_metric('OVER ' + f'{line:g}', _pct(spec.get('over_no_push_probability')), 'FAIR ' + _odds(spec.get('over_fair_odds')))}
{_metric('UNDER ' + f'{line:g}', _pct(spec.get('under_no_push_probability')), 'FAIR ' + _odds(spec.get('under_fair_odds')))}
{_metric('PUSH', _pct(spec.get('push_probability')))}
{_metric('MC SE', _pct(spec.get('mc_se'),2), 'batch range ' + _num(spec.get('batch_range_pp'),2) + ' pp')}
</div></div>''')
    return "".join(pieces)


def _result_card(game: dict, eligible: list[dict], result: dict) -> str:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    period = int(game.get("period") or 0)
    ot_label = "ADDITIONAL OT PROBABILITY" if period > 4 else "OVERTIME PROBABILITY"
    convergence = str(result.get("convergence") or "CHECK")
    ccls = "good" if convergence == "PASS" else "warn"
    markets = _market_cards(game, eligible, result)
    no_markets = '<div class="kwl6-no-market">No Step-2 exact live pair currently passes the state/quote firewall. Moneyline win probabilities and projected final score remain valid statistical outputs, but no live spread/total line is attached.</div>' if not markets else markets

    return f'''<div class="kwl6-result">
<div class="kwl6-resulthead"><div><small>5,000,000-DRAW STATE-CONDITIONAL MONTE CARLO</small><b>Simulation Result • {escape(away)} @ {escape(home)}</b></div><span class="{ccls}">CONVERGENCE • {escape(convergence)}</span></div>
<div class="kwl6-biggrid">
<div><small>{escape(away)} WIN</small><strong>{_pct(result.get('away_win_probability'))}</strong><span>FAIR {_odds(result.get('away_fair_odds'))}</span></div>
<div><small>{escape(home)} WIN</small><strong>{_pct(result.get('home_win_probability'))}</strong><span>FAIR {_odds(result.get('home_fair_odds'))}</span></div>
</div>
<div class="kwl6-grid result-grid">
{_metric('MC EXPECTED FINAL', f"{_num(result.get('expected_final_away'),1)}–{_num(result.get('expected_final_home'),1)}", 'includes simulated OT when triggered')}
{_metric('MC EXPECTED TOTAL', _num(result.get('expected_final_total'),1))}
{_metric('MC HOME MARGIN', _num(result.get('expected_final_home_margin'),1,True) + ' pts')}
{_metric(ot_label, _pct(result.get('extra_period_probability')))}
{_metric('SIMULATIONS', f"{int(result.get('simulations') or 0):,}")}
{_metric('BATCHES', str(int(result.get('batches') or 0)), f"{int(result.get('batch_size') or 0):,} / batch")}
{_metric('HOME ML MC SE', _pct(result.get('home_ml_mc_se'),2))}
{_metric('MAX BATCH RANGE', _num(result.get('max_batch_range_pp'),2) + ' pp', f"PASS ≤ {_num(result.get('convergence_threshold_pp'),2)} pp")}
{_metric('RANDOM SEED', str(result.get('seed') or '—'))}
{_metric('RUNTIME', _num(result.get('runtime_seconds'),2) + ' s')}
</div>
<div class="kwl6-title">EXACT LIVE-LINE PROBABILITIES • ONLY FIREWALL-PASS PAIRS</div>
{no_markets}
<div class="kwl6-contract result"><b>STEP 6 BOUNDARY.</b> These are model probabilities and fair odds only. No sportsbook no-vig comparison, edge, EV, maximum-playable price, qualification, ranking or recommendation is calculated here.</div>
</div>'''


def _css():
    st.markdown(r'''<style>
.kwl6-hero{border:1px solid #42637a;border-radius:22px;padding:20px;margin:28px 0 14px;background:linear-gradient(145deg,#091827,#07131f)}.kwl6-eyebrow{font-size:.7rem;font-weight:950;letter-spacing:.08em;color:#8fd8ff}.kwl6-hero h3{font-size:1.48rem;margin:8px 0;color:#f7fbff}.kwl6-hero p{color:#9bb0bf;line-height:1.58;margin:0}.kwl6-hero b{color:#fff}
.kwl6-game,.kwl6-result{border:1px solid #36566c;border-radius:22px;padding:16px;margin:14px 0;background:#081522}.kwl6-head,.kwl6-resulthead{display:flex;justify-content:space-between;align-items:end;gap:12px;border-bottom:1px solid #213b4e;padding-bottom:12px}.kwl6-head>div,.kwl6-resulthead>div{display:flex;flex-direction:column;gap:4px}.kwl6-head>div:last-child{text-align:right}.kwl6-head small,.kwl6-resulthead small{font-size:.6rem;color:#7893a7;font-weight:900;letter-spacing:.06em}.kwl6-head b,.kwl6-resulthead b{color:#f6f9fb;font-size:1rem}.kwl6-head strong{color:#fff;font-size:1.4rem}.kwl6-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.kwl6-badges span,.kwl6-resulthead>span{border:1px solid #31546b;border-radius:999px;padding:6px 8px;font-size:.57rem;color:#9db5c4;font-weight:900}.kwl6-badges .good,.kwl6-resulthead .good{border-color:#2d8257;background:#0d2d21;color:#93efbc}.kwl6-badges .warn,.kwl6-resulthead .warn{border-color:#8a722a;background:#2a240d;color:#ead879}.kwl6-badges .bad{border-color:#8f4b47;background:#311616;color:#ffada6}
.kwl6-title{font-size:.68rem;color:#a8ddff;letter-spacing:.07em;font-weight:950;margin:16px 0 8px}.kwl6-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.kwl6-m{border:1px solid #29495d;border-radius:14px;padding:10px;background:#07111d;min-height:72px;display:flex;flex-direction:column;justify-content:center}.kwl6-m span{font-size:.57rem;color:#7f98aa;font-weight:900;letter-spacing:.035em}.kwl6-m b{font-size:1.02rem;color:#f6f9fb;margin-top:5px}.kwl6-m small{color:#8aa0b0;margin-top:3px;font-size:.55rem;line-height:1.35}.kwl6-segments{border:1px solid #29495d;border-radius:14px;padding:11px;margin-top:10px;background:#07111d}.kwl6-segments small{color:#8fcff5;font-size:.58rem;font-weight:950}.kwl6-segments p{color:#cbd9e1;font-size:.67rem;line-height:1.5;margin:5px 0 0}.kwl6-contract{border:1px solid #705f1f;background:#2b260c;color:#e9d875;border-radius:15px;padding:12px;margin-top:12px;font-size:.64rem;line-height:1.5}.kwl6-contract b{color:#fff2a3}.kwl6-contract.result{border-color:#31566f;background:#0a1723;color:#9fb4c1}.kwl6-contract.result b{color:#dff3ff}
.kwl6-runbox{border:1px solid #36566c;border-radius:16px;padding:12px;margin:10px 0 20px;background:#07111d}.kwl6-runbox p{color:#849cac;font-size:.63rem;line-height:1.45;margin:7px 0 0}.kwl6-biggrid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:14px 0}.kwl6-biggrid>div{border:1px solid #41647a;border-radius:16px;padding:13px;background:#0a1927;display:flex;flex-direction:column}.kwl6-biggrid small{font-size:.6rem;color:#8fcff5;font-weight:950}.kwl6-biggrid strong{font-size:2rem;color:#fff;margin:5px 0}.kwl6-biggrid span{font-size:.62rem;color:#9bb1bf}.kwl6-market{border:1px solid #2c4b5f;border-radius:16px;padding:11px;margin:8px 0;background:#07111d}.kwl6-markethead{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px}.kwl6-markethead b{color:#eef7fb;font-size:.72rem}.kwl6-markethead span{font-size:.52rem;color:#7f98aa}.kwl6-marketgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kwl6-no-market{border:1px dashed #705f1f;border-radius:14px;padding:11px;color:#d5c56a;font-size:.65rem;line-height:1.5;background:#211e0c}.kwl6-boundary{border:1px dashed #41647a;border-radius:14px;padding:12px;color:#859dac;font-size:.64rem;line-height:1.5;margin:14px 0 24px}
@media(max-width:640px){.kwl6-hero,.kwl6-game,.kwl6-result{padding:14px}.kwl6-head,.kwl6-resulthead{align-items:center}.kwl6-grid,.kwl6-biggrid,.kwl6-marketgrid{grid-template-columns:1fr 1fr}.kwl6-markethead{flex-direction:column}.kwl6-head b{font-size:.9rem}}
</style>''', unsafe_allow_html=True)


def _clear_live_step6_caches():
    try:
        v1._espn_live_snapshot.clear()
    except Exception:
        pass
    try:
        market.clear_cache()
    except Exception:
        pass
    try:
        model.clear_cache()
    except Exception:
        pass


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve the entire frozen/verified Steps 1-5 + preview/audit stack.
    v52.render_wnba_live_hub(section_header, status_info, team_logo, h)

    _css()
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    st.markdown(f'''<div class="kwl6-hero"><div class="kwl6-eyebrow">🎲 {MODEL_VERSION}</div><h3>Step 6 • Live Projection + 5M Monte Carlo</h3><p>The first prediction layer starts from the <b>exact verified live score, quarter and clock</b>. Current-game pace/efficiency is regressed toward completed regular-season scoring profiles before 5,000,000 state-conditional simulations. Fresh sportsbook lines can be graded afterward, but <b>market price never changes the statistical projection</b>.</p></div>''', unsafe_allow_html=True)

    if st.button("🔄 Refresh Step 6 live state + model inputs", use_container_width=True, key="wnba_live_v6_refresh"):
        _clear_live_step6_caches()
        st.rerun()

    games, _diag, _live_meta = v2._verified_live_games(day_str)
    if not games:
        st.info("No Step-1 verified WNBA game is live right now. Step 6 will not manufacture a projection from the completed-game Step-5 validation preview.")
        st.markdown('<div class="kwl6-boundary">STEP 6 LIVE-ONLY BOUNDARY • completed preview games are never projected • next verified live state will activate the model • NO edge/EV/qualification/pick</div>', unsafe_allow_html=True)
        return

    snapshot = market.market_snapshot_for_live_games(games, day_str)
    results_store = st.session_state.setdefault("wnba_live_v6_mc_results", {})

    for game in games:
        projection = model.projection_for_game(game)
        eligible = _eligible_pairs(snapshot, game)
        age = model.state_age_seconds(game)
        st.markdown(_projection_card(game, projection, eligible, age), unsafe_allow_html=True)

        fresh_state = age is not None and age <= model.MAX_STATE_AGE_SECONDS
        can_run = bool(projection.get("ready")) and fresh_state
        key = model.run_key(game, eligible)

        st.markdown('<div class="kwl6-runbox">', unsafe_allow_html=True)
        if st.button(
            "🎲 Run 5,000,000 live simulations",
            use_container_width=True,
            disabled=not can_run,
            key=f"wnba_live_v6_run_{game.get('espn_event_id')}",
        ):
            with st.spinner("Running 5,000,000 state-conditional WNBA simulations…"):
                result = model.simulate_5m(game, projection, eligible)
            results_store.clear()
            results_store[key] = result
        if not projection.get("ready"):
            st.warning(
                f"5M is blocked: Step 6 requires a valid live state and at least {model.MIN_HISTORY_GAMES} completed historical games per team. "
                f"Current history sample: away {int(projection.get('away_history_games') or 0)}, home {int(projection.get('home_history_games') or 0)}."
            )
        elif not fresh_state:
            st.warning(
                f"5M is blocked because the verified game-state snapshot is {_state_age(age)} old. "
                f"Use the Step-6 refresh button; the run gate is ≤ {model.MAX_STATE_AGE_SECONDS}s."
            )
        else:
            st.caption(
                f"Run gate PASS • state age {_state_age(age)} • {len(eligible)} Step-2 firewall-pass market pair(s). "
                "A simulation can still run with zero eligible lines; it will produce win probability/final-score distribution only."
            )
        st.markdown('</div>', unsafe_allow_html=True)

        result = results_store.get(key)
        if result:
            st.markdown(_result_card(game, eligible, result), unsafe_allow_html=True)
        elif results_store:
            st.info("A saved 5M result exists for an older game state or different exact live line. It is intentionally hidden until you run the current state.")

    st.markdown('<div class="kwl6-boundary">STEP 6 BOUNDARY • statistical projection + state-conditional 5M probability + fair odds only • sportsbook PRICE/no-vig is not a model input • NO edge • NO EV • NO maximum playable price • NO qualification • NO ranking • NO recommendation</div>', unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "render_wnba_live_hub"]
