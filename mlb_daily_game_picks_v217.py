"""MLB Daily Game Picks V2.1.7 — risk-aware final decision layer.

Decision/orchestration upgrade only. Production model formulas, simulation depths,
verified-market gates, Step 3 Pick Strength and all seven connector outputs remain
unchanged.

Adds:
- clear BEST BET / STRONG / MONITOR / AVOID hierarchy;
- stronger market-specific Why-this-pick explanations;
- hard removal/replacement of critical live-risk candidates;
- a small selection-priority penalty for unresolved MONITOR candidates so a
  comparably strong confirmed-safe candidate can replace them;
- shared Run Line/Total sportsbook-cache freshness protection.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math
import time

import streamlit as st

import mlb_daily_game_picks_v216b as previous
import mlb_daily_game_picks_v215 as provider_layer
import mlb_daily_game_picks_v212 as live
import mlb_daily_game_picks_v2123 as riskfix
import mlb_daily_game_picks_v211 as decision
import mlb_daily_game_picks_v209 as ui
import mlb_daily_game_picks_v206 as master

controller = previous.controller
VERSION = "MLB Daily Game Picks V2.1.7 • RISK-AWARE FINAL DECISION"

_BASE_RISK = riskfix._risk_context
MARKET_CACHE_WARN_SECONDS = 180
MARKET_CACHE_CRITICAL_SECONDS = 900
MONITOR_SELECTION_PENALTY = 4.0


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _safe_int(v):
    try:
        return int(float(v))
    except Exception:
        return None


def _candidate_key(c):
    return (
        str(c.get("game_pk") or ""),
        str(c.get("market") or ""),
        str(c.get("name") or ""),
        str(c.get("side") or ""),
        str(c.get("line") or ""),
    )


def _market_cache_context(c, games_df, minutes_to_pitch=None):
    """Freshness guard for the shared sportsbook snapshot used by Run Line/Total."""
    market = str(c.get("market") or "")
    if market not in {"Run Line", "Total"}:
        return None

    day = ui._day(games_df)
    stamp = st.session_state.get(provider_layer._provider_stamp_key(day))
    if stamp is None:
        return (
            "warn",
            "No current shared sportsbook-cache timestamp is available for this price/line context. The model projection remains valid, but refresh market data before relying on the displayed edge.",
            None,
        )
    try:
        age = max(0, int(time.time() - float(stamp)))
    except Exception:
        return (
            "warn",
            "The sportsbook-cache timestamp could not be validated. Refresh market data before relying on the displayed price/edge.",
            None,
        )

    if age <= MARKET_CACHE_WARN_SECONDS:
        return ("safe", f"Shared sportsbook market snapshot is fresh ({age}s old).", age)

    age_min = max(1, int(round(age / 60.0)))
    if age > MARKET_CACHE_CRITICAL_SECONDS and minutes_to_pitch is not None and minutes_to_pitch <= 90:
        return (
            "critical",
            f"Shared sportsbook market snapshot is about {age_min} minutes old with first pitch inside 90 minutes. Refresh the market before using this Run Line/Total pick.",
            age,
        )
    return (
        "warn",
        f"Shared sportsbook market snapshot is about {age_min} minutes old. Refresh market data before relying on the current price/edge.",
        age,
    )


def _risk_context_v217(c, games_df, snap, ts, baseline):
    """Extend the proven official-MLB risk check with sportsbook-cache freshness."""
    base = _BASE_RISK(c, games_df, snap, ts, baseline)
    out = dict(base or {})
    warnings = list(out.get("warnings") or [])
    market_ctx = _market_cache_context(c, games_df, out.get("minutes_to_pitch"))
    if market_ctx and market_ctx[0] in {"warn", "critical"}:
        warnings.append((market_ctx[0], market_ctx[1]))

    if any(level == "critical" for level, _ in warnings):
        badge = ("⛔ AVOID / REPLACE", "critical")
    elif warnings:
        badge = ("⚠️ MONITOR", "warn")
    else:
        badge = ("✅ PREGAME CHECKS OK", "safe")

    out["warnings"] = warnings
    out["badge"] = badge
    out["market_freshness"] = market_ctx
    return out


def _decision_label(c, risk):
    score = _finite(c.get("score"), 0.0) or 0.0
    warnings = list((risk or {}).get("warnings") or [])
    if any(level == "critical" for level, _ in warnings):
        return "⛔ AVOID", "avoid", "A critical live input changed or became too stale; this candidate is removed from the Final Card."
    if warnings:
        return "⚠️ MONITOR", "monitor", "The model still qualifies, but one or more pregame inputs are not fully confirmed/fresh yet."
    if score >= 82.0:
        return "🔥 BEST BET", "best", "Elite Pick Strength with confirmed live checks."
    if score >= 76.0:
        return "✅ STRONG", "strong", "Strong Pick Strength with confirmed live checks."
    return "✅ QUALIFIED", "qualified", "Clears the Final Card floor with confirmed live checks."


def _risk_penalty(risk):
    warnings = list((risk or {}).get("warnings") or [])
    if any(level == "critical" for level, _ in warnings):
        return 999.0
    if warnings:
        return MONITOR_SELECTION_PENALTY
    return 0.0


def _select_risk_aware(candidates, risks, limit=None):
    """Keep original guardrails; use risk only as a final-card selection overlay."""
    limit = int(limit or master.MASTER_LIMIT)
    ranked = []
    for c in candidates or []:
        score = _finite(c.get("score"), 0.0) or 0.0
        if score < master.MASTER_MIN_SCORE:
            continue
        risk = risks.get(_candidate_key(c)) or {}
        if any(level == "critical" for level, _ in (risk.get("warnings") or [])):
            continue
        priority = score - _risk_penalty(risk)
        ranked.append((priority, score, c))

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
            _finite(item[2].get("reliability"), 0.0) or 0.0,
            _finite(item[2].get("data_quality"), 0.0) or 0.0,
            _finite(item[2].get("probability"), 0.0) or 0.0,
        ),
        reverse=True,
    )

    selected = []
    used_games = set()
    used_players = set()
    used_exact = set()
    for _priority, _score, c in ranked:
        game_pk = str(c.get("game_pk") or "")
        if not game_pk or game_pk in used_games:
            continue
        exact = (game_pk, c.get("market"), c.get("name"), c.get("side"), str(c.get("line")))
        if exact in used_exact:
            continue

        market = str(c.get("market") or "")
        player_key = None
        if market in master.PLAYER_MARKETS:
            player_key = (
                str(c.get("name") or "").strip().lower(),
                str(c.get("team") or "").strip().lower(),
            )
            if player_key in used_players:
                continue

        selected.append(c)
        used_games.add(game_pk)
        used_exact.add(exact)
        if player_key:
            used_players.add(player_key)
        if len(selected) >= limit:
            break
    return selected


def _all_live_context(games_df):
    ui._prime_active_games(games_df)
    candidates = master._collect_candidates(games_df) or []
    pks = tuple(sorted({str(c.get("game_pk") or "") for c in candidates if c.get("game_pk")}))
    snaps = live._official_snapshots(pks)
    baseline = live._starter_baseline(games_df)
    ts = live._build_ts(games_df)
    risks = {}
    for c in candidates:
        snap = snaps.get(_safe_int(c.get("game_pk"))) or {}
        risks[_candidate_key(c)] = _risk_context_v217(c, games_df, snap, ts, baseline)
    selected = _select_risk_aware(candidates, risks)
    return candidates, selected, snaps, baseline, ts, risks


def _status_style(cls):
    styles = {
        "best": ("#082f23", "#74efb5", "#2a7658"),
        "strong": ("#09283a", "#6edfff", "#2b6685"),
        "qualified": ("#112234", "#b7d1e5", "#36536b"),
        "monitor": ("#3b3109", "#ffe27c", "#7c651c"),
        "avoid": ("#411416", "#ff9c9c", "#8f363b"),
    }
    bg, fg, border = styles.get(cls, styles["qualified"])
    return f"background:{bg};color:{fg};border:1px solid {border};border-radius:999px;padding:5px 8px;font-size:8px;font-weight:950;display:inline-flex;margin:5px 0 4px"


def _decision_card_v217(c, rank, games_df, ts, snap, baseline, risk):
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    score = _finite(c.get("score"), 0.0) or 0.0
    tier, tier_cls = ui._tier(score)
    prob = decision._pct(c.get("probability"))
    projection = decision._projection_summary(c)
    gap = live._market_gap(c, games_df)
    label, status_cls, _ = _decision_label(c, risk)
    lineup_label, lineup_cls, _ = risk.get("lineup") or ("🕒 Lineup check unavailable", "neutral", "")
    weather_label, weather_cls, _ = risk.get("weather") or ("🌦 Weather check unavailable", "neutral", "")
    freshness = decision._freshness(ts)

    return f'''<div class="kui-card k211-card k212-card {'first' if rank == 1 else ''}">
      <div class="kui-rank">{medals.get(rank, '•')} DAILY #{rank}</div>
      <div style="{_status_style(status_cls)}">{escape(label)}</div>
      <div class="kui-market">{escape(str(c.get('market') or ''))}</div>
      {decision._candidate_name_html(c)}
      <div class="kui-side">{escape(str(c.get('side') or ''))}</div>
      <div class="k211-prob-row"><div><b>{prob}</b><span> TRUE MODEL PROBABILITY</span></div></div>
      <div class="k211-projection">{escape(projection)}</div>
      <div class="k212-gap">{gap['html']}</div>
      <div class="kui-score">{score:.1f}<small> /100 PICK STRENGTH</small></div>
      <div class="kui-badge {tier_cls}">{tier}</div>
      <div class="kui-matchup">{ui._matchup_html(c.get('matchup'))}</div>
      <div class="k212-live-row">
        <span class="{escape(lineup_cls)}">{escape(lineup_label)}</span>
        <span class="{escape(weather_cls)}">{escape(weather_label)}</span>
      </div>
      <div class="k211-fresh">🕐 Card {escape(freshness)}</div>
      <div class="kui-meta">{escape(str(c.get('first_pitch') or 'TBD'))} ET • Reliability {(_finite(c.get('reliability'),0.0) or 0.0)*100:.0f}% • Data {(_finite(c.get('data_quality'),0.0) or 0.0)*100:.0f}%</div>
    </div>'''


def _why_sections(c, games_df, snap, ts, baseline, risk):
    score = _finite(c.get("score"), 0.0) or 0.0
    rel = (_finite(c.get("reliability"), 0.0) or 0.0) * 100.0
    dq = (_finite(c.get("data_quality"), 0.0) or 0.0) * 100.0
    label, _status_cls, status_reason = _decision_label(c, risk)
    gap = live._market_gap(c, games_df)
    starter_change = live._starter_change(c, games_df, snap, baseline)

    model_lines = [
        f"True probability: {decision._pct(c.get('probability'))} for {str(c.get('side') or 'the selected side')}.",
        decision._projection_summary(c) + ".",
        f"Pick Strength {score:.1f}/100 • reliability {rel:.0f}% • data quality {dq:.0f}%.",
    ]

    market_lines = []
    if gap.get("detail"):
        market_lines.append(str(gap["detail"]))
    market_ctx = risk.get("market_freshness")
    if market_ctx:
        market_lines.append(str(market_ctx[1]))
    elif str(c.get("market") or "") not in {"Run Line", "Total"}:
        market_lines.append("This market's production probability remains independent of the shared Run Line/Total sportsbook cache.")

    live_lines = []
    lineup = risk.get("lineup")
    weather = risk.get("weather")
    if lineup:
        live_lines.append(str(lineup[2]))
    if weather:
        live_lines.append(str(weather[2]))
    if starter_change:
        live_lines.append("🚨 " + starter_change)
    elif snap and snap.get("ok"):
        live_lines.append("No probable-starter change is detected versus the card baseline.")

    decision_lines = [f"Current decision status: {label}. {status_reason}"]
    warnings = list(risk.get("warnings") or [])
    if warnings:
        for level, text in warnings:
            decision_lines.append(("🚨 " if level == "critical" else "⚠️ ") + str(text))
    else:
        decision_lines.append("No active live-risk warning is reducing this candidate's Final Card priority.")
    decision_lines.append(
        "Critical changes are automatically removed from the Final Card. MONITOR candidates receive only a small selection-priority penalty, so a comparably strong confirmed-safe alternative can replace them without changing the underlying Pick Strength."
    )

    return [
        ("🎯 Model case", model_lines),
        ("📈 Market context", market_lines),
        ("🛰 Pregame verification", live_lines),
        ("🧠 Final decision", decision_lines),
    ]


def _render_master_v217(games_df):
    candidates, selected, snaps, baseline, ts, risks = _all_live_context(games_df)
    qualified = [c for c in candidates if (_finite(c.get("score"), 0.0) or 0.0) >= master.MASTER_MIN_SCORE]
    connected = len({(c.get("game_pk"), c.get("market")) for c in candidates})
    base_selected = master._select_master(candidates)
    base_keys = {_candidate_key(c) for c in base_selected}
    selected_keys = {_candidate_key(c) for c in selected}
    replacements = len(base_keys - selected_keys)

    monitor_count = 0
    blocked_count = 0
    for c in qualified:
        r = risks.get(_candidate_key(c)) or {}
        warnings = list(r.get("warnings") or [])
        if any(level == "critical" for level, _ in warnings):
            blocked_count += 1
    for c in selected:
        r = risks.get(_candidate_key(c)) or {}
        if r.get("warnings"):
            monitor_count += 1

    st.markdown(
        f'''<div class="kui-master k211-head">
          <div class="kui-kicker">KYRE SPORTS AI • STEP 6 • V2.1.7 RISK-AWARE FINAL DECISION</div>
          <div class="kui-master-title">🏆 Daily Master Card — Top 5 MLB Picks</div>
          <div class="kui-master-sub">Original production Pick Strength + official MLB live checks + sportsbook freshness guard • critical picks auto-removed • MONITOR picks softly deprioritized • model math unchanged.</div>
          <div class="kui-stats">
            <div class="kui-stat"><b>{len(candidates)}</b> scored candidates</div>
            <div class="kui-stat"><b>{len(qualified)}</b> at 70+</div>
            <div class="kui-stat"><b>{connected}</b> connected game-markets</div>
            <div class="kui-stat"><b>{len(selected)}/{master.MASTER_LIMIT}</b> final picks</div>
            <div class="kui-stat"><b>{monitor_count}</b> monitor</div>
            <div class="kui-stat"><b>{blocked_count}</b> blocked</div>
            <div class="kui-stat"><b>{replacements}</b> auto-replaced</div>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    if blocked_count:
        st.error(f"⛔ {blocked_count} qualified candidate(s) are currently blocked by critical pregame/freshness conditions and cannot enter the Final Card.")
    if replacements:
        st.info(f"🔄 Risk-aware selector replaced {replacements} base Top-5 candidate(s) with safer qualified alternatives while leaving every production score unchanged.")
    if monitor_count:
        st.warning(f"⚠️ {monitor_count} Final Card pick(s) remain MONITOR. They still qualify, but unresolved pregame inputs should be checked before first pitch.")

    if not selected:
        st.info("No currently usable candidate clears the Final Card rules. The system will not force a pick.")
    else:
        cols = st.columns(2)
        for i, c in enumerate(selected, 1):
            snap = snaps.get(_safe_int(c.get("game_pk"))) or {}
            risk = risks.get(_candidate_key(c)) or {}
            with cols[(i - 1) % 2]:
                st.markdown(_decision_card_v217(c, i, games_df, ts, snap, baseline, risk), unsafe_allow_html=True)
                with st.expander("🧠 Why this pick?", expanded=False):
                    for title, lines in _why_sections(c, games_df, snap, ts, baseline, risk):
                        st.markdown(f"**{title}**")
                        for line in lines:
                            if line:
                                st.markdown(f"• {line}")

    if candidates:
        with st.expander("🎯 Best qualified picks by market", expanded=False):
            leader_html = ui._market_leader_cards(candidates)
            if leader_html:
                st.markdown(f'<div class="kui-market-grid">{leader_html}</div>', unsafe_allow_html=True)
                st.caption("Market leaders retain their original production Pick Strength. Final Card risk guardrails are applied only during slate-wide selection.")
            else:
                st.info("No market candidate currently clears the 70/100 qualification floor.")
        with st.expander("🧠 Final Card decision rules", expanded=False):
            st.markdown(
                "**Hierarchy:** 🔥 BEST BET = elite + confirmed • ✅ STRONG = strong + confirmed • ⚠️ MONITOR = qualified but unresolved/stale live input • ⛔ AVOID = critical change/staleness and automatically excluded."
            )
            st.caption(
                "V2.1.7 does not modify production probabilities, simulation depth, Pick Strength, fair odds, or verified sportsbook lines. Risk changes only Final Card eligibility/priority."
            )


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # V2.1.2.3 reassigns the live-risk globals on every Streamlit rerun. Patch its
    # own callable, plus the V2.1.2 master renderer global, so the upgrade survives
    # the entire inherited wrapper chain.
    riskfix._risk_context = _risk_context_v217
    live._risk_context = _risk_context_v217
    live._render_master_decision = _render_master_v217
    ui._render_master_polished = _render_master_v217
    ui.master._render_master = _render_master_v217

    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
