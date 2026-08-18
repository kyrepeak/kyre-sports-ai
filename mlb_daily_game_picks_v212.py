"""MLB Daily Game Picks V2.1.2 — market gap + live risk intelligence.

Presentation/orchestration only. Preserves V2.1.1 decision screen, V2.1.0 bounded
sportsbook resume, V2.0.8 one-tap controller, V2.0.7 market-neutral normalization,
all seven production models, simulation depths, verified-market gates, Step 5/6
selection rules, and identity firewalls.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import escape
import math
import re

import requests
import streamlit as st

import mlb_daily_game_picks_v211 as previous
from engine import LIVE_API
import slate_lineup_v204 as lineup

ui = previous.ui
controller = previous.controller
master = previous.master
bridge = previous.bridge
BASE_INJECT = previous._inject_css_decision

VERSION = "MLB Daily Game Picks V2.1.2 • MARKET GAP + LIVE RISK INTELLIGENCE"
PLAYER_MARKETS = {"1+ Hit", "Home Run", "H+R+RBI", "Pitcher Strikeouts"}


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


def _parse_dt(v):
    if isinstance(v, datetime):
        dt = v
    else:
        s = str(v or "").strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@st.cache_data(ttl=180, show_spinner=False)
def _official_snapshots(game_pks):
    """Official MLB checks for only the current Final Card games."""
    pks = tuple(sorted({_safe_int(x) for x in game_pks if _safe_int(x) is not None}))
    if not pks:
        return {}
    headers = {"User-Agent": "KyreSportsAI/1.0"}

    def work(pk):
        fetched = datetime.now(timezone.utc)
        try:
            r = requests.get(
                f"{LIVE_API}/game/{int(pk)}/feed/live",
                headers=headers,
                timeout=6,
            )
            r.raise_for_status()
            payload = r.json()
            gd = payload.get("gameData") or {}
            probable = gd.get("probablePitchers") or {}
            weather = gd.get("weather") or {}
            status = gd.get("status") or {}
            dtblock = gd.get("datetime") or {}
            try:
                lus = lineup._parse_lineups(payload)
            except Exception:
                lus = {"away": [], "home": []}

            def pitcher(side):
                p = probable.get(side) or {}
                return {
                    "id": _safe_int(p.get("id")),
                    "name": str(p.get("fullName") or p.get("name") or "").strip(),
                }

            return int(pk), {
                "ok": True,
                "fetched_at": fetched.isoformat(),
                "away_pitcher": pitcher("away"),
                "home_pitcher": pitcher("home"),
                "away_lineup_count": len(lus.get("away") or []),
                "home_lineup_count": len(lus.get("home") or []),
                "weather": {
                    "condition": str(weather.get("condition") or "").strip(),
                    "temp": weather.get("temp"),
                    "wind": str(weather.get("wind") or "").strip(),
                },
                "status": str(
                    status.get("detailedState")
                    or status.get("abstractGameState")
                    or ""
                ).strip(),
                "game_datetime": dtblock.get("dateTime") or None,
            }
        except Exception as exc:
            return int(pk), {
                "ok": False,
                "fetched_at": fetched.isoformat(),
                "error": str(exc),
            }

    out = {}
    with ThreadPoolExecutor(max_workers=min(5, len(pks))) as pool:
        futs = [pool.submit(work, pk) for pk in pks]
        for fut in as_completed(futs):
            pk, snap = fut.result()
            out[int(pk)] = snap
    return out


def _game_row(games_df, game_pk):
    return previous._game_row(games_df, game_pk)


def _build_ts(games_df):
    return previous._build_timestamp(games_df)


def _baseline_key(day):
    return f"dgp_starter_baseline_v212::{day}"


def _starter_baseline(games_df):
    """Snapshot the starters associated with the latest completed card build."""
    day = ui._day(games_df)
    ts = _build_ts(games_df)
    ts_sig = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
    key = _baseline_key(day)
    old = st.session_state.get(key) or {}
    if old.get("build_ts") == ts_sig and old.get("games"):
        return old

    games = {}
    if games_df is not None and not getattr(games_df, "empty", True):
        for _, row in games_df.iterrows():
            pk = str(_safe_int(row.get("game_pk")) or row.get("game_pk") or "")
            games[pk] = {
                "away_id": _safe_int(row.get("away_pitcher_id")),
                "away_name": str(row.get("away_pitcher") or "").strip(),
                "home_id": _safe_int(row.get("home_pitcher_id")),
                "home_name": str(row.get("home_pitcher") or "").strip(),
            }
    state = {"build_ts": ts_sig, "games": games}
    st.session_state[key] = state
    return state


def _norm_name(v):
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def _starter_change(c, games_df, snap, baseline):
    if not snap or not snap.get("ok"):
        return None
    pk = str(c.get("game_pk") or "")
    base = (baseline.get("games") or {}).get(pk) or {}
    row = _game_row(games_df, pk)
    away_team = str(row.get("away_team") or "") if row is not None else ""
    home_team = str(row.get("home_team") or "") if row is not None else ""

    changes = []
    for side in ("away", "home"):
        current = snap.get(f"{side}_pitcher") or {}
        cur_id = _safe_int(current.get("id"))
        cur_name = str(current.get("name") or "").strip()
        old_id = _safe_int(base.get(f"{side}_id"))
        old_name = str(base.get(f"{side}_name") or "").strip()
        if cur_id and old_id and cur_id != old_id:
            changes.append((side, old_name or str(old_id), cur_name or str(cur_id)))
        elif cur_name and old_name and _norm_name(cur_name) != _norm_name(old_name):
            changes.append((side, old_name, cur_name))

    if str(c.get("market") or "") == "Pitcher Strikeouts":
        team = str(c.get("team") or "")
        side = "away" if team == away_team else "home" if team == home_team else None
        if side:
            current_name = str((snap.get(f"{side}_pitcher") or {}).get("name") or "")
            if current_name and _norm_name(current_name) != _norm_name(c.get("name")):
                changes.append((side, str(c.get("name") or ""), current_name))

    if not changes:
        return None
    labels = []
    for side, old, new in changes:
        team = away_team if side == "away" else home_team
        labels.append(f"{team}: {old or 'TBD'} → {new or 'TBD'}")
    return "Probable starter changed since this card was built: " + " • ".join(labels)


def _lineup_context(c, games_df, snap):
    if not snap or not snap.get("ok"):
        return ("🕒 Lineup check unavailable", "neutral", "Official MLB lineup check could not be refreshed.")

    away_n = int(snap.get("away_lineup_count") or 0)
    home_n = int(snap.get("home_lineup_count") or 0)
    row = _game_row(games_df, c.get("game_pk"))
    away_team = str(row.get("away_team") or "") if row is not None else ""
    home_team = str(row.get("home_team") or "") if row is not None else ""

    market = str(c.get("market") or "")
    if market in PLAYER_MARKETS:
        team = str(c.get("team") or "")
        if team == away_team:
            n, who = away_n, away_team
        elif team == home_team:
            n, who = home_n, home_team
        else:
            n, who = min(away_n, home_n), "Player team"
        if n >= 9:
            return ("✅ Player lineup confirmed", "safe", f"{who} has a confirmed 9-player batting order in the official MLB feed.")
        if n > 0:
            return ("🟡 Player lineup partial", "warn", f"{who} has only {n}/9 batting-order spots posted.")
        return ("🕒 Player lineup pending", "warn", f"{who} has not posted a full official batting order yet.")

    if away_n >= 9 and home_n >= 9:
        return ("✅ Both lineups confirmed", "safe", "Both teams have confirmed 9-player batting orders in the official MLB feed.")
    if away_n >= 9 or home_n >= 9:
        return ("🟡 One lineup confirmed", "warn", f"Official batting orders: away {away_n}/9 • home {home_n}/9.")
    if away_n or home_n:
        return ("🟡 Lineups partial", "warn", f"Official batting orders: away {away_n}/9 • home {home_n}/9.")
    return ("🕒 Lineups pending", "warn", "Neither team has a complete official batting order posted yet.")


def _weather_context(snap):
    if not snap or not snap.get("ok"):
        return ("🌦 Weather check unavailable", "neutral", "Official MLB weather block could not be refreshed.")
    w = snap.get("weather") or {}
    condition = str(w.get("condition") or "").strip()
    temp = w.get("temp")
    wind = str(w.get("wind") or "").strip()
    pieces = []
    if condition:
        pieces.append(condition)
    if temp not in (None, ""):
        pieces.append(f"{temp}°F")
    if wind:
        pieces.append(wind)

    fetched = _parse_dt(snap.get("fetched_at"))
    age = None
    if fetched is not None:
        age = max(0, int((datetime.now(timezone.utc) - fetched.astimezone(timezone.utc)).total_seconds() // 60))
    freshness = f" • {age}m old" if age is not None else ""

    if not pieces:
        return ("🌦 Weather pending from MLB", "neutral", "MLB has not populated a pregame weather block for this game yet.")

    text = " • ".join(pieces) + freshness
    low = f"{condition} {wind}".lower()
    severe_words = ("rain", "storm", "thunder", "shower", "drizzle", "snow")
    cls = "warn" if any(x in low for x in severe_words) else "safe"
    detail = f"Official MLB pregame weather: {text}."
    if cls == "warn":
        detail += " Weather may materially change playing conditions or delay risk."
    return (f"🌦 {text}", cls, detail)


def _minutes_to_pitch(snap):
    dt = _parse_dt((snap or {}).get("game_datetime"))
    if dt is None:
        return None
    return (dt.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 60.0


def _build_age_minutes(ts):
    if ts is None:
        return None
    try:
        return max(0.0, (ui._now_et() - ts.astimezone(ui.ET)).total_seconds() / 60.0)
    except Exception:
        return None


def _risk_context(c, games_df, snap, ts, baseline):
    warnings = []
    starter = _starter_change(c, games_df, snap, baseline)
    if starter:
        warnings.append(("critical", starter))

    lineup_label, lineup_cls, lineup_detail = _lineup_context(c, games_df, snap)
    weather_label, weather_cls, weather_detail = _weather_context(snap)
    if weather_cls == "warn":
        warnings.append(("warn", weather_detail))

    mins = _minutes_to_pitch(snap)
    age = _build_age_minutes(ts)
    if mins is not None:
        if mins <= 0:
            warnings.append(("critical", "Game has started or reached its scheduled start; this pregame card should no longer be treated as fresh."))
        elif mins <= 30 and age is not None and age > 5:
            warnings.append(("critical", f"First pitch is about {mins:.0f} minutes away and the card is {age:.0f} minutes old. Refresh before using it."))
        elif mins <= 90 and age is not None and age > 15:
            warnings.append(("warn", f"First pitch is about {mins:.0f} minutes away and the card is {age:.0f} minutes old. A refresh is recommended."))

        if mins <= 90 and lineup_cls == "warn" and str(c.get("market") or "") in PLAYER_MARKETS:
            warnings.append(("warn", f"{lineup_detail} First pitch is about {mins:.0f} minutes away."))

    if any(level == "critical" for level, _ in warnings):
        badge = ("🚨 REFRESH NOW", "critical")
    elif warnings:
        badge = ("⚠️ MONITOR", "warn")
    else:
        badge = ("✅ PREGAME CHECKS OK", "safe")

    return {
        "badge": badge,
        "warnings": warnings,
        "lineup": (lineup_label, lineup_cls, lineup_detail),
        "weather": (weather_label, weather_cls, weather_detail),
        "minutes_to_pitch": mins,
        "build_age": age,
    }


def _american_from_prob(p):
    p = _finite(p)
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def _implied_from_american(a):
    a = _finite(a)
    if a is None or a == 0:
        return None
    if a < 0:
        return (-a) / ((-a) + 100.0)
    return 100.0 / (a + 100.0)


def _profit_per_100(a):
    a = _finite(a)
    if a is None or a == 0:
        return None
    return (10000.0 / abs(a)) if a < 0 else a


def _market_gap(c, games_df):
    p = _finite(c.get("probability"))
    fair = _finite(c.get("fair_odds"))
    if fair is None:
        fair = _american_from_prob(p)

    book, price_text, _ = previous._cached_sportsbook_context(c, games_df)
    price = _finite(str(price_text or "").replace("+", ""))

    fair_text = previous._american(fair) if fair is not None else "—"
    if not book or price is None:
        return {
            "html": f"<b>MODEL FAIR {escape(fair_text)}</b><span>NO CACHED SPORTSBOOK PRICE • RANKING UNCHANGED</span>",
            "detail": "No matching cached sportsbook price is available; sportsbook price does not influence the production projection or Pick Strength.",
        }

    implied = _implied_from_american(price)
    edge_pp = ((p - implied) * 100.0) if p is not None and implied is not None else None
    profit = _profit_per_100(price)
    ev100 = (p * profit - (1.0 - p) * 100.0) if p is not None and profit is not None else None

    edge_text = f"{edge_pp:+.1f} pp" if edge_pp is not None else "—"
    ev_text = f"${ev100:+.1f}" if ev100 is not None else "—"
    price_fmt = previous._american(price)
    html = (
        f"<b>MODEL FAIR {escape(fair_text)}</b>"
        f"<span>{escape(str(book))} {escape(price_fmt)} • PROB EDGE {escape(edge_text)} • EV {escape(ev_text)} / $100</span>"
    )
    detail = (
        f"Market comparison only: model fair {fair_text} versus {book} {price_fmt}. "
        f"Probability edge {edge_text}; expected profit/loss at that price is {ev_text} per $100 risked. "
        "This comparison is not an input to the production projection or Pick Strength."
    )
    return {"html": html, "detail": detail}


def _decision_card(c, rank, games_df, ts, snap, baseline):
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    score = master._finite(c.get("score"))
    tier, tier_cls = ui._tier(score)
    prob = previous._pct(c.get("probability"))
    projection = previous._projection_summary(c)
    gap = _market_gap(c, games_df)
    risk = _risk_context(c, games_df, snap, ts, baseline)
    risk_label, risk_cls = risk["badge"]
    lineup_label, lineup_cls, _ = risk["lineup"]
    weather_label, weather_cls, _ = risk["weather"]
    freshness = previous._freshness(ts)

    return f"""<div class="kui-card k211-card k212-card {'first' if rank == 1 else ''}">
      <div class="kui-rank">{medals.get(rank, '•')} DAILY #{rank}</div>
      <div class="k212-risk {risk_cls}">{escape(risk_label)}</div>
      <div class="kui-market">{escape(str(c.get('market') or ''))}</div>
      {previous._candidate_name_html(c)}
      <div class="kui-side">{escape(str(c.get('side') or ''))}</div>
      <div class="k211-prob-row"><div><b>{prob}</b><span> TRUE MODEL PROBABILITY</span></div></div>
      <div class="k211-projection">{escape(projection)}</div>
      <div class="k212-gap">{gap['html']}</div>
      <div class="kui-score">{score:.1f}<small> /100 PICK STRENGTH</small></div>
      <div class="kui-badge {tier_cls}">{tier}</div>
      <div class="kui-matchup">{ui._matchup_html(c.get('matchup'))}</div>
      <div class="k212-live-row">
        <span class="{lineup_cls}">{escape(lineup_label)}</span>
        <span class="{weather_cls}">{escape(weather_label)}</span>
      </div>
      <div class="k211-fresh">🕐 Card {escape(freshness)}</div>
      <div class="kui-meta">{escape(str(c.get('first_pitch') or 'TBD'))} ET • Reliability {master._finite(c.get('reliability'))*100:.0f}% • Data {master._finite(c.get('data_quality'))*100:.0f}%</div>
    </div>"""


def _why_lines(c, games_df, snap, ts, baseline):
    lines = list(previous._why_lines(c, games_df))
    gap = _market_gap(c, games_df)
    if gap.get("detail"):
        lines.insert(-1 if lines else 0, gap["detail"])

    risk = _risk_context(c, games_df, snap, ts, baseline)
    lines.append(risk["lineup"][2])
    lines.append(risk["weather"][2])
    if risk["warnings"]:
        for level, text in risk["warnings"]:
            prefix = "🚨" if level == "critical" else "⚠️"
            lines.append(f"{prefix} {text}")
    else:
        mins = risk.get("minutes_to_pitch")
        if mins is not None and mins > 0:
            lines.append(f"Pregame freshness check passes with roughly {mins:.0f} minutes until first pitch.")
        else:
            lines.append("No live pregame risk flag is currently active.")
    return lines


def _selected_live_context(games_df):
    ui._prime_active_games(games_df)
    candidates = master._collect_candidates(games_df)
    selected = master._select_master(candidates)
    pks = tuple(str(c.get("game_pk") or "") for c in selected)
    snaps = _official_snapshots(pks)
    baseline = _starter_baseline(games_df)
    ts = _build_ts(games_df)
    return candidates, selected, snaps, baseline, ts


def _render_master_decision(games_df):
    candidates, selected, snaps, baseline, ts = _selected_live_context(games_df)
    qualified = [c for c in candidates if master._finite(c.get("score")) >= master.MASTER_MIN_SCORE]
    connected = len({(c.get("game_pk"), c.get("market")) for c in candidates})

    risk_count = 0
    critical_count = 0
    for c in selected:
        snap = snaps.get(_safe_int(c.get("game_pk"))) or {}
        r = _risk_context(c, games_df, snap, ts, baseline)
        if r["warnings"]:
            risk_count += 1
        if any(level == "critical" for level, _ in r["warnings"]):
            critical_count += 1

    risk_stat = (
        f'<div class="kui-stat k212-stat-alert"><b>{critical_count}</b> refresh-now alerts</div>'
        if critical_count
        else f'<div class="kui-stat"><b>{risk_count}</b> live risk flags</div>'
    )

    st.markdown(
        f"""<div class="kui-master k211-head">
          <div class="kui-kicker">KYRE SPORTS AI • STEP 6 • FINAL DECISION SCREEN</div>
          <div class="kui-master-title">🏆 Daily Master Card — Top 5 MLB Picks</div>
          <div class="kui-master-sub">Model fair vs market price • official MLB lineup/starter/weather checks • stale-pick protection • market-neutral Pick Strength • one final pick per game.</div>
          <div class="kui-stats">
            <div class="kui-stat"><b>{len(candidates)}</b> scored candidates</div>
            <div class="kui-stat"><b>{len(qualified)}</b> at 70+</div>
            <div class="kui-stat"><b>{connected}</b> connected game-markets</div>
            <div class="kui-stat"><b>{len(selected)}/{master.MASTER_LIMIT}</b> final picks</div>
            {risk_stat}
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    if critical_count:
        st.error(f"🚨 {critical_count} Final Card pick(s) need a refresh because a starter changed, the game started, or the card is too stale close to first pitch.")
    elif risk_count:
        st.warning(f"⚠️ {risk_count} Final Card pick(s) have live pregame items to monitor. Open Why this pick? for details.")

    if not selected:
        st.info("Build the production connectors above. The Final Card only displays real scored production outputs.")
    else:
        cols = st.columns(2)
        for i, c in enumerate(selected, 1):
            snap = snaps.get(_safe_int(c.get("game_pk"))) or {}
            with cols[(i - 1) % 2]:
                st.markdown(_decision_card(c, i, games_df, ts, snap, baseline), unsafe_allow_html=True)
                with st.expander("🧠 Why this pick?", expanded=False):
                    for line in _why_lines(c, games_df, snap, ts, baseline):
                        st.markdown(f"• {line}")

    if candidates:
        with st.expander("🎯 Best qualified picks by market", expanded=False):
            leader_html = ui._market_leader_cards(candidates)
            if leader_html:
                st.markdown(f'<div class="kui-market-grid">{leader_html}</div>', unsafe_allow_html=True)
                st.caption("Up to three qualified candidates per market. Missing or incompatible sportsbook markets remain absent/unscored.")
            else:
                st.info("No market candidate currently clears the 70/100 qualification floor.")
        with st.expander("🧠 Daily Master Card rules", expanded=False):
            st.caption(
                "V2.1.2 adds market-gap display and official MLB live risk checks only. "
                "Sportsbook price and live risk badges do not rewrite the seven production projections or market-neutral Pick Strength."
            )


def _critical_refresh_reason(games_df):
    try:
        _, selected, snaps, baseline, ts = _selected_live_context(games_df)
    except Exception:
        return None
    for c in selected:
        snap = snaps.get(_safe_int(c.get("game_pk"))) or {}
        r = _risk_context(c, games_df, snap, ts, baseline)
        for level, text in r["warnings"]:
            if level == "critical":
                return text
    return None


def _smart_refresh_stages(games_df):
    critical = _critical_refresh_reason(games_df)
    if critical:
        return [x[0] for x in controller.STAGES], f"Live pregame safety escalation: {critical} Rebuild all seven stages."
    return previous._smart_refresh_stages(games_df)


def _queue_smart_refresh(games_df):
    day = ui._day(games_df)
    stages, reason = _smart_refresh_stages(games_df)

    for stage in stages:
        key = controller._pack_key(games_df, stage)
        if key:
            st.session_state.pop(key, None)

    if "runline" in stages or "total" in stages:
        st.session_state.pop(bridge._odds_key(day), None)
        try:
            st.session_state.pop(previous.quota._stamp_key(day), None)
        except Exception:
            pass

    state_key = controller._state_key(day)
    old = st.session_state.get(state_key) or {}
    fresh = controller._initial_state(day)
    fresh["active"] = True
    fresh["runs"] = int(old.get("runs", 0) or 0) + 1
    st.session_state[state_key] = fresh
    st.session_state.pop(ui._timestamp_key(day), None)
    st.session_state.pop(_baseline_key(day), None)
    st.session_state[f"dgp_smart_refresh_note_v212::{day}"] = (
        f"{reason} Queued: " +
        ", ".join(label for stage, label, _ in controller.STAGES if stage in stages)
    )


def _render_refresh_controls(games_df):
    day = ui._day(games_df)
    auto_key = f"dgp_ui_autorefresh_v209::{day}"
    secs_key = f"dgp_ui_refreshsecs_v209::{day}"
    state = st.session_state.get(controller._state_key(day)) or {}

    if auto_key not in st.session_state:
        st.session_state[auto_key] = True
    if secs_key not in st.session_state:
        st.session_state[secs_key] = 300

    with st.expander("⚙️ Display & refresh settings", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.toggle(
                "Auto-refresh display",
                key=auto_key,
                help="Reruns the screen only. It never rebuilds a production connector.",
            )
        with c2:
            st.selectbox(
                "Display refresh interval",
                options=[120, 300, 600],
                format_func=lambda x: f"{x // 60} minutes",
                key=secs_key,
            )

        st.caption("Display refresh is quota-safe. Final Card live checks use the official MLB feed and are cached for about 3 minutes.")
        st.divider()
        stages, reason = _smart_refresh_stages(games_df)
        labels = [label for stage, label, _ in controller.STAGES if stage in stages]
        st.caption(f"🔄 Smart data refresh plan: {reason}")
        st.caption("Will queue: " + " • ".join(labels))
        disabled = bool(state.get("active"))
        if st.button(
            "🔄 REFRESH CARD DATA",
            type="primary",
            use_container_width=True,
            disabled=disabled,
            key=f"dgp_refresh_card_data_v212::{day}",
            help="Selectively rebuilds stale/mutable stages; starter changes or critical near-pitch staleness escalate to all seven.",
        ):
            _queue_smart_refresh(games_df)
            st.rerun()

        note_key = f"dgp_smart_refresh_note_v212::{day}"
        if st.session_state.get(note_key):
            st.info(st.session_state.pop(note_key))

    if ui.st_autorefresh is not None and bool(st.session_state.get(auto_key)) and not bool(state.get("active")):
        secs = int(st.session_state.get(secs_key, 300) or 300)
        ui.st_autorefresh(interval=max(120, secs) * 1000, key=f"dgp_ui_tick_v212::{day}")


def _inject_css():
    BASE_INJECT()
    st.markdown(
        """
<style>
.k212-card{position:relative}
.k212-risk{display:inline-flex;border-radius:999px;padding:4px 7px;font-size:7px;font-weight:950;margin:5px 0 2px;border:1px solid #34546b}
.k212-risk.safe{background:#073225;color:#77efb6;border-color:#1f7253}
.k212-risk.warn{background:#3a300b;color:#ffe17b;border-color:#775e18}
.k212-risk.critical{background:#411417;color:#ff9b9b;border-color:#8d3338}
.k212-gap{display:flex;flex-direction:column;gap:2px;border:1px solid #31586f;background:#081b29;border-radius:9px;padding:7px 8px;margin-top:8px}
.k212-gap b{color:#ffffff;font-size:8px}.k212-gap span{color:#6edfff;font-size:8px;font-weight:900;line-height:1.35}
.k212-live-row{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
.k212-live-row span{border:1px solid #315166;border-radius:999px;padding:4px 6px;font-size:7px;font-weight:850;line-height:1.2}
.k212-live-row .safe{color:#7beeb8;background:#092d23;border-color:#216a50}
.k212-live-row .warn{color:#ffe07a;background:#352b0b;border-color:#6c5718}
.k212-live-row .neutral{color:#a8bfd0;background:#0b1b29;border-color:#315166}
.k212-stat-alert{border-color:#8d3338!important;color:#ffb0b0!important}
@media(max-width:650px){.k212-gap span{font-size:7px}.k212-live-row span{font-size:6.7px}}
</style>
        """,
        unsafe_allow_html=True,
    )


# Patch V2.1.1 globals too, because its render function reassigns these hooks on each rerun.
previous._inject_css_decision = _inject_css
previous._render_refresh_controls_decision = _render_refresh_controls
previous._render_master_decision = _render_master_decision
ui._inject_css = _inject_css
ui._render_refresh_controls = _render_refresh_controls
ui._render_master_polished = _render_master_decision
ui.master._render_master = _render_master_decision


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    previous._inject_css_decision = _inject_css
    previous._render_refresh_controls_decision = _render_refresh_controls
    previous._render_master_decision = _render_master_decision
    ui._inject_css = _inject_css
    ui._render_refresh_controls = _render_refresh_controls
    ui._render_master_polished = _render_master_decision
    ui.master._render_master = _render_master_decision

    st.caption(
        "🛡️ V2.1.2 live-risk layer: model fair vs market price • official MLB lineup/starter/weather checks • stale-pick warnings • smart refresh escalation • production math unchanged."
    )
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
