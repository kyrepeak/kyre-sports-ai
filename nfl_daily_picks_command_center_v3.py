from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
import math
from typing import Any, Iterable, Mapping

try:
    import streamlit as st
except Exception:
    st = None

from nfl_daily_picks_core_v1 import DailyPickCandidate
from nfl_daily_picks_market_v3 import (
    SPORTSBOOK_PROJECTION_INFLUENCE,
    best_verified_book,
    line_movement,
    normalize_market_observations,
)
from nfl_daily_picks_parlay_v3 import (
    DEFAULT_RISK_MODE,
    RISK_MODES,
    build_parlay,
    estimate_parlay_probability,
)
from nfl_daily_picks_ranking_v1 import normalized_pick_score

MARKET_IDS = ("moneyline", "spread", "game-total")
MARKET_LABELS = {"moneyline": "Moneyline", "spread": "Spread", "game-total": "Game Total"}
MODEL_VERSION = "NFL DAILY PICKS COMMAND CENTER V3 • S-TIER • THREE-MARKET + PARLAY INTELLIGENCE"
ET_LABEL = "ET"


def _metadata(candidate: DailyPickCandidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    try:
        return {str(key): value for key, value in tuple(candidate.metadata or ())}
    except Exception:
        return {}


def _total_probability_certified(candidate: DailyPickCandidate | None) -> bool:
    if candidate is None or candidate.market_id != "game-total":
        return True
    return _metadata(candidate).get("source_probability_certified") is True


def _game_state(raw: Any) -> str:
    value = str(raw or "scheduled").strip().lower()
    if value in {"in", "live", "in_progress", "in-progress"}:
        return "live"
    if value in {"post", "final", "completed", "complete"}:
        return "final"
    return "scheduled"


def _kickoff(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return fallback


def _pick_for_market(candidates: Iterable[DailyPickCandidate], market_id: str) -> DailyPickCandidate | None:
    rows = [candidate for candidate in candidates if candidate.market_id == market_id]
    if not rows:
        return None
    return sorted(rows, key=lambda candidate: (-normalized_pick_score(candidate), str(candidate.side)))[0]


def _risk_copy(candidate: DailyPickCandidate) -> str:
    uncertainty = max(0.0, float(candidate.uncertainty))
    age = max(0.0, float(candidate.source_age_seconds))
    limit = max(1.0, float(candidate.freshness_limit_seconds))
    if uncertainty >= 0.20:
        return "Model uncertainty is elevated; normal game variance can erase this edge quickly."
    if age / limit >= 0.70:
        return "The source snapshot is nearing its freshness limit, so a new line can change the value."
    return "Normal variance plus late line, injury or availability movement can change the edge before kickoff."


def _market_payload(
    candidate: DailyPickCandidate | None,
    *,
    observations: list[dict[str, Any]],
    live_state: bool,
) -> dict[str, Any]:
    if candidate is None:
        return {
            "visible": True,
            "qualified": False,
            "parlay_eligible": False,
            "probability_state": "NO_QUALIFIED_SOURCE_PICK",
            "side": None,
            "probability": None,
            "projection": None,
            "market_line": None,
            "best_book": {"ready": False, "status": "No verified current book"},
            "line_movement": {"ready": False, "reason": "NO_QUALIFIED_SOURCE_PICK"},
            "freshness_seconds": None,
            "why": "Source engine is connected, but no qualified source-owned pick is available right now.",
            "risk": "No recommendation is published until the source contract is qualified and fresh.",
        }

    source_probability_ok = _total_probability_certified(candidate)
    probability_state = "CERTIFIED" if source_probability_ok else "SOURCE_PROBABILITY_UNAVAILABLE"
    best = best_verified_book(
        observations,
        game_id=str(candidate.game_id),
        market_id=str(candidate.market_id),
        side=str(candidate.side),
    )
    movement = {"ready": False, "reason": "OPENING_EVIDENCE_UNAVAILABLE"}
    if best.get("ready"):
        selected = next(
            (
                row
                for row in observations
                if str(row.get("game_id")) == str(candidate.game_id)
                and str(row.get("market_id")) == str(candidate.market_id)
                and str(row.get("side") or "").upper() == str(candidate.side).upper()
                and str(row.get("book")) == str(best.get("book"))
            ),
            None,
        )
        if selected is not None:
            movement = line_movement(selected)
    meta = _metadata(candidate)
    live_verified = meta.get("live_eligible_verified") is True
    source_fresh = float(candidate.source_age_seconds) <= float(candidate.freshness_limit_seconds)
    parlay_eligible = bool(
        source_probability_ok
        and candidate.source_ready
        and str(candidate.source_state or "").upper() == "READY"
        and source_fresh
        and (not live_state or live_verified)
    )
    reasons = [str(item).strip() for item in tuple(candidate.reason_components or ()) if str(item).strip()]
    return {
        "visible": True,
        "qualified": bool(candidate.source_ready),
        "parlay_eligible": parlay_eligible,
        "probability_state": probability_state,
        "side": str(candidate.side),
        "probability": float(candidate.model_probability) if source_probability_ok else None,
        "projection": candidate.model_projection,
        "market_line": candidate.market_line,
        "edge": candidate.edge_value,
        "source_grade": candidate.source_grade,
        "source_version": candidate.source_version,
        "freshness_seconds": float(candidate.source_age_seconds),
        "best_book": best,
        "line_movement": movement,
        "live_eligible_verified": live_verified,
        "why": reasons[0] if reasons else "Source-owned qualified result ranked by probability, edge, quality, freshness and uncertainty.",
        "risk": str(meta.get("risk_reason") or "").strip() or _risk_copy(candidate),
    }


def build_command_center_board(
    candidates: Iterable[DailyPickCandidate],
    *,
    now_utc: datetime,
    game_states: Mapping[str, Mapping[str, Any]] | None = None,
    observations: Iterable[Mapping[str, Any]] = (),
    risk_mode: str = DEFAULT_RISK_MODE,
) -> dict[str, Any]:
    values = tuple(candidate for candidate in tuple(candidates) if candidate.market_id in MARKET_IDS)
    mode = risk_mode if risk_mode in RISK_MODES else DEFAULT_RISK_MODE
    normalized_observations = normalize_market_observations(observations, now_utc=now_utc)
    supplied_states = {str(key): dict(value or {}) for key, value in dict(game_states or {}).items()}
    by_game: dict[str, list[DailyPickCandidate]] = {}
    for candidate in values:
        by_game.setdefault(str(candidate.game_id), []).append(candidate)
    all_game_ids = set(by_game) | set(supplied_states)

    rows: list[dict[str, Any]] = []
    for game_id in all_game_ids:
        game_candidates = by_game.get(game_id, [])
        first = game_candidates[0] if game_candidates else None
        state_payload = supplied_states.get(game_id, {})
        state = _game_state(state_payload.get("state"))
        fallback_kickoff = first.kickoff_at if first is not None else now_utc + timedelta(days=365)
        kickoff_at = _kickoff(state_payload.get("kickoff_at"), fallback_kickoff)
        if not state_payload.get("state") and kickoff_at <= now_utc:
            state = "live"
        markets = {
            market_id: _market_payload(
                _pick_for_market(game_candidates, market_id),
                observations=normalized_observations,
                live_state=state == "live",
            )
            for market_id in MARKET_IDS
        }
        matchup = str(state_payload.get("matchup") or (first.matchup_label if first is not None else game_id))
        live_recommendation_enabled = any(payload.get("live_eligible_verified") for payload in markets.values()) if state == "live" else False
        rows.append(
            {
                "game_id": game_id,
                "state": state,
                "kickoff_at": kickoff_at,
                "matchup": matchup,
                "markets": markets,
                "live_recommendation_enabled": bool(live_recommendation_enabled),
            }
        )
    rows.sort(key=lambda row: (row["kickoff_at"], row["game_id"]))
    live_rows = [row for row in rows if row["state"] == "live"]
    scheduled = [row for row in rows if row["state"] == "scheduled"]
    if scheduled:
        next_day = min(row["kickoff_at"].date() for row in scheduled)
        next_rows = [row for row in scheduled if row["kickoff_at"].date() == next_day]
    else:
        next_rows = []

    featured_candidates = [
        candidate
        for candidate in values
        if candidate.kickoff_at > now_utc and (candidate.market_id != "game-total" or _total_probability_certified(candidate))
    ]
    featured = sorted(featured_candidates, key=lambda candidate: (-normalized_pick_score(candidate), str(candidate.game_id)))[:3]
    parlay = build_parlay(featured_candidates, mode)
    verified_books = sorted({str(row.get("book")) for row in normalized_observations if row.get("book")})
    freshest_age = min((float(row.get("age_seconds") or 0.0) for row in normalized_observations), default=None)
    return {
        "model_version": MODEL_VERSION,
        "risk_mode": mode,
        "risk_modes": RISK_MODES,
        "market_ids": MARKET_IDS,
        "buckets": {"LIVE NOW": live_rows, "NEXT GAMES": next_rows, "ALL NFL": rows},
        "featured": tuple(featured),
        "generated_parlay": parlay,
        "summary": {
            "games_tracked": len(rows),
            "qualified_markets": sum(1 for candidate in values if candidate.source_ready),
            "verified_books": len(verified_books),
            "book_names": tuple(verified_books),
            "freshest_age_seconds": freshest_age,
        },
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def _safe(value: Any, fallback: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or fallback


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _number(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "—"


def _line(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    return f"{number:+.1f}" if number != 0 else "0.0"


def _freshness(value: Any) -> str:
    try:
        seconds = max(0.0, float(value))
    except Exception:
        return "Unavailable"
    return f"{seconds:.0f}s old" if seconds < 120 else f"{seconds / 60.0:.1f}m old"


def _movement_text(payload: Mapping[str, Any]) -> str:
    movement = dict(payload.get("line_movement") or {})
    if movement.get("ready") is not True:
        return "No verified opening line"
    opening = _number(movement.get("opening_line"))
    current = _number(movement.get("current_line"))
    try:
        delta = f"{float(movement.get('delta')):+.1f}"
    except Exception:
        delta = "—"
    return f"{opening} → {current} ({delta})"


def _spread_observation_rows(game_id: str, row: Mapping[str, Any], now_utc: datetime) -> tuple[dict[str, Any], ...]:
    raw_age = row.get("age_seconds")
    try:
        age = float(raw_age)
    except (TypeError, ValueError):
        return ()
    if not math.isfinite(age) or age < 0.0:
        return ()
    book = str(row.get("sportsbook") or "").strip()
    if not book:
        return ()
    updated = now_utc - timedelta(seconds=age)
    return (
        {"game_id": game_id, "market_id": "spread", "side": "AWAY", "book": book, "price": row.get("away_price"), "line": row.get("away_spread"), "updated_at": updated, "verified": True, "provider": "Kyre Sports API"},
        {"game_id": game_id, "market_id": "spread", "side": "HOME", "book": book, "price": row.get("home_price"), "line": row.get("home_spread"), "updated_at": updated, "verified": True, "provider": "Kyre Sports API"},
    )


def _collect_runtime_context(day: date, now_utc: datetime):
    from nfl_daily_picks_sources_v1 import _kickoff_from_slate, load_all_market_candidates
    import nfl_hub_v1 as nfl

    results = load_all_market_candidates(day, now_utc=now_utc)
    candidates = tuple(
        candidate
        for result in results
        if str(result.status or "").upper() == "READY"
        for candidate in result.candidates
        if candidate.market_id in MARKET_IDS
    )
    games, diag = nfl.load_nfl_slate(day.isoformat())
    states: dict[str, dict[str, Any]] = {}
    if (diag or {}).get("request_ok"):
        for _, series in games.iterrows():
            game = series.to_dict()
            game_id = str(game.get("game_id") or "").strip()
            if not game_id:
                continue
            kickoff_at = _kickoff_from_slate(game, day) or now_utc + timedelta(days=365)
            states[game_id] = {
                "state": game.get("state"),
                "kickoff_at": kickoff_at,
                "matchup": f"{_safe(game.get('away_abbr'))} at {_safe(game.get('home_abbr'))}",
            }
    observations: list[dict[str, Any]] = []
    try:
        import nfl_moneyline_market_v11 as ml_market
        pregame = games[games["state"].astype(str) == "pre"] if not games.empty and "state" in games else games
        snapshots, _ = ml_market.fetch_nfl_moneyline_markets(pregame, day.isoformat())
        for game_id, snapshot in snapshots.items():
            for row in snapshot.get("rows") or []:
                updated = row.get("updated_at")
                observations.extend(
                    [
                        {"game_id": game_id, "market_id": "moneyline", "side": "AWAY", "book": row.get("book"), "price": row.get("away_ml"), "line": None, "updated_at": updated, "verified": bool(row.get("usable")), "provider": row.get("provider")},
                        {"game_id": game_id, "market_id": "moneyline", "side": "HOME", "book": row.get("book"), "price": row.get("home_ml"), "line": None, "updated_at": updated, "verified": bool(row.get("usable")), "provider": row.get("provider")},
                    ]
                )
    except Exception:
        pass
    try:
        import nfl_spread_hub_v1 as spread_market
        markets = spread_market._fetch_markets(games)
        for game_id, snapshot in markets.items():
            for row in snapshot.get("books") or []:
                observations.extend(_spread_observation_rows(str(game_id), row, now_utc))
    except Exception:
        pass
    return candidates, states, observations


_CSS = r"""
<style>
.kcc-hero{border:1px solid #315b73;border-radius:22px;padding:18px;background:radial-gradient(circle at 90% 0%,rgba(56,189,248,.18),transparent 34%),linear-gradient(145deg,#07131f,#071019);box-shadow:0 18px 46px rgba(0,0,0,.22)}
.kcc-kicker{font-size:.68rem;font-weight:950;letter-spacing:.13em;color:#7dd3fc}.kcc-title{font-size:1.82rem;font-weight:950;color:#f8fafc;margin-top:4px}.kcc-sub{font-size:.79rem;line-height:1.55;color:#9db0bf;margin-top:6px}.kcc-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0}.kcc-stat{border:1px solid #294157;border-radius:12px;background:#091621;padding:10px}.kcc-stat b{display:block;color:#f2f8fc;font-size:1.02rem}.kcc-stat span{color:#7890a3;font-size:.47rem;font-weight:950;text-transform:uppercase}.kcc-section{margin:14px 0 7px;font-size:.62rem;font-weight:950;letter-spacing:.10em;color:#7dd3fc}.kcc-featured{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.kcc-feature{border:1px solid #31566f;border-radius:14px;background:linear-gradient(160deg,#0b1d2b,#08131d);padding:10px}.kcc-feature em{font-style:normal;color:#f0c96c;font-size:.48rem;font-weight:950}.kcc-feature b{display:block;color:#f7fbff;font-size:.82rem;margin-top:4px}.kcc-feature span{display:block;color:#89a0b2;font-size:.49rem;margin-top:3px;line-height:1.4}.kcc-card{border:1px solid #294c63;border-radius:18px;background:linear-gradient(160deg,#091724,#08111b);padding:13px;margin:10px 0}.kcc-game{display:flex;justify-content:space-between;gap:8px}.kcc-game b{color:#f8fafc;font-size:.98rem}.kcc-game span{color:#7dd3fc;font-size:.57rem;font-weight:950}.kcc-markets{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px}.kcc-market{border:1px solid #20384b;border-radius:11px;background:#07131d;padding:9px}.kcc-market h4{font-size:.59rem;color:#8bdcf8;margin:0 0 5px}.kcc-market strong{display:block;color:#f5f9fc;font-size:.82rem}.kcc-market small{display:block;color:#8196a7;font-size:.47rem;margin-top:4px;line-height:1.4}.kcc-why,.kcc-risk{margin-top:7px;border-radius:8px;padding:7px}.kcc-why{background:#0a1d29;border-left:2px solid #38bdf8}.kcc-risk{background:#17170f;border-left:2px solid #b9a04b}.kcc-why b,.kcc-risk b{font-size:.48rem}.kcc-why b{color:#bcecff}.kcc-risk b{color:#eadb98}.kcc-why span,.kcc-risk span{font-size:.43rem;color:#91a4b3;line-height:1.4}.kcc-slip{position:sticky;bottom:8px;z-index:6;border:1px solid #40708c;border-radius:14px;padding:10px;background:rgba(4,16,25,.96);box-shadow:0 12px 34px rgba(0,0,0,.3)}.kcc-slip b{color:#c8efff}.kcc-slip span{color:#98adbd;font-size:.58rem;margin-left:6px}
@media(max-width:760px){.kcc-summary{grid-template-columns:repeat(2,1fr)}.kcc-featured,.kcc-markets{grid-template-columns:1fr}.kcc-title{font-size:1.55rem}.kcc-sub{font-size:.74rem}}
</style>
"""


def _featured_html(featured: Iterable[DailyPickCandidate]) -> str:
    labels = ("BEST PICK", "STRONG EDGE", "TOP VALUE")
    blocks = []
    for index, candidate in enumerate(tuple(featured)[:3]):
        reasons = [str(item).strip() for item in tuple(candidate.reason_components or ()) if str(item).strip()]
        why = reasons[0] if reasons else "Source-owned qualified result."
        blocks.append(
            '<div class="kcc-feature">'
            f'<em>{labels[index]}</em><b>{escape(candidate.subject_label)} • {escape(candidate.market_label)}</b>'
            f'<span>{escape(candidate.side)} • {_pct(candidate.model_probability)} model probability • score {normalized_pick_score(candidate):.3f}</span>'
            f'<span>{escape(why)}</span></div>'
        )
    return '<div class="kcc-featured">' + ''.join(blocks) + '</div>' if blocks else ''


def render_nfl_daily_picks_command_center() -> None:
    if st is None:
        return
    from nfl_daily_picks_hub_v1 import _selected_day

    now_utc = datetime.now(timezone.utc)
    day = _selected_day()
    candidates, states, observations = _collect_runtime_context(day, now_utc)
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="kcc-hero"><div class="kcc-kicker">KYRE SPORTS AI • NFL LIVE COMMAND CENTER</div>'
        '<div class="kcc-title">NFL Daily Picks <span style="color:#7dd3fc">Decision Desk</span></div>'
        '<div class="kcc-sub">Certified model truth + verified multi-book market context. Sportsbooks can change settlement value, never the model projection or probability.</div></section>',
        unsafe_allow_html=True,
    )
    risk_mode = st.radio("Risk profile", RISK_MODES, index=RISK_MODES.index(DEFAULT_RISK_MODE), horizontal=True, key="nfl_daily_picks_v3_risk")
    board = build_command_center_board(candidates, now_utc=now_utc, game_states=states, observations=observations, risk_mode=risk_mode)
    summary = board["summary"]
    freshest = "—" if summary["freshest_age_seconds"] is None else f"{summary['freshest_age_seconds']:.0f}s"
    st.markdown(
        '<div class="kcc-summary">'
        f'<div class="kcc-stat"><b>{summary["games_tracked"]}</b><span>Games tracked</span></div>'
        f'<div class="kcc-stat"><b>{summary["qualified_markets"]}</b><span>Qualified signals</span></div>'
        f'<div class="kcc-stat"><b>{summary["verified_books"]}</b><span>Verified books</span></div>'
        f'<div class="kcc-stat"><b>{freshest}</b><span>Freshest update</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="kcc-section">FEATURED INTELLIGENCE</div>' + _featured_html(board["featured"]), unsafe_allow_html=True)
    bucket_name = st.radio("Slate view", ("LIVE NOW", "NEXT GAMES", "ALL NFL"), horizontal=True, key="nfl_daily_picks_v3_bucket")
    rows = board["buckets"][bucket_name]
    if not rows:
        st.info("No games are currently in this view. The command center will surface the next authoritative NFL slate automatically.")
    for row in rows:
        kickoff_text = row["kickoff_at"].strftime("%a %I:%M %p")
        chunks = []
        for market_id in MARKET_IDS:
            payload = row["markets"][market_id]
            best = payload.get("best_book") or {}
            book_text = _safe(best.get("book"), "No verified current book") if best.get("ready") else "No verified current book"
            probability_text = _pct(payload.get("probability")) if payload.get("probability_state") == "CERTIFIED" else "Source probability unavailable"
            projection_text = _number(payload.get("projection"))
            movement_text = _movement_text(payload)
            freshness_text = _freshness(payload.get("freshness_seconds"))
            chunks.append(
                f'<div class="kcc-market"><h4>{escape(MARKET_LABELS[market_id])}</h4><strong>{escape(_safe(payload.get("side"), "Connected"))}</strong>'
                f'<small>Model probability: {escape(probability_text)}</small><small>Model projection: {escape(projection_text)}</small>'
                f'<small>Market: {escape(_line(payload.get("market_line")))}</small><small>Line movement: {escape(movement_text)}</small>'
                f'<small>Best book: {escape(book_text)}</small><small>Freshness: {escape(freshness_text)}</small>'
                f'<div class="kcc-why"><b>Why it rates</b><span>{escape(_safe(payload.get("why")))}</span></div>'
                f'<div class="kcc-risk"><b>What could go wrong</b><span>{escape(_safe(payload.get("risk")))}</span></div></div>'
            )
        live_note = " • live rec verified" if row.get("live_recommendation_enabled") else (" • live model stays pregame-only" if row["state"] == "live" else "")
        st.markdown(
            f'<article class="kcc-card"><div class="kcc-game"><b>{escape(row["matchup"])}</b><span>{escape(row["state"].upper())} • {escape(kickoff_text)} {ET_LABEL}{escape(live_note)}</span></div><div class="kcc-markets">{"".join(chunks)}</div></article>',
            unsafe_allow_html=True,
        )

    generated = board["generated_parlay"]
    if "nfl_daily_picks_v3_slip_active" not in st.session_state:
        st.session_state["nfl_daily_picks_v3_slip_active"] = False
    if "nfl_daily_picks_v3_slip_trim" not in st.session_state:
        st.session_state["nfl_daily_picks_v3_slip_trim"] = 0
    a1, a2, a3 = st.columns(3)
    if a1.button("Build Me a Parlay", key="nfl_daily_picks_v3_build_parlay", use_container_width=True):
        st.session_state["nfl_daily_picks_v3_slip_active"] = True
        st.session_state["nfl_daily_picks_v3_slip_trim"] = 0
    if a2.button("Remove Last Leg", key="nfl_daily_picks_v3_remove_leg", use_container_width=True):
        st.session_state["nfl_daily_picks_v3_slip_active"] = True
        st.session_state["nfl_daily_picks_v3_slip_trim"] = int(st.session_state.get("nfl_daily_picks_v3_slip_trim", 0)) + 1
    if a3.button("Reset Slip", key="nfl_daily_picks_v3_reset_slip", use_container_width=True):
        st.session_state["nfl_daily_picks_v3_slip_active"] = False
        st.session_state["nfl_daily_picks_v3_slip_trim"] = 0

    if st.session_state.get("nfl_daily_picks_v3_slip_active") and generated.get("allowed"):
        base_legs = tuple(generated.get("legs") or ())
        trim = max(0, int(st.session_state.get("nfl_daily_picks_v3_slip_trim", 0)))
        legs = base_legs[: max(0, len(base_legs) - trim)]
        estimate = estimate_parlay_probability(legs) if len(legs) >= 2 else {"allowed": False}
        if estimate.get("allowed"):
            probability = _pct(estimate.get("estimated_probability"))
            grade = _safe(estimate.get("correlation_grade"))
            st.markdown(
                f'<div class="kcc-slip"><b>Parlay Slip • {escape(risk_mode)}</b><span>{len(legs)} legs • {escape(grade)} correlation • {escape(probability)} estimated parlay probability</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="kcc-slip"><b>Parlay Slip</b><span>Add at least 2 qualified non-conflicting legs.</span></div>', unsafe_allow_html=True)
    elif generated.get("allowed"):
        st.markdown('<div class="kcc-slip"><b>Parlay Slip ready</b><span>Tap Build Me a Parlay to load the current risk-profile combination.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kcc-slip"><b>Parlay builder • {escape(risk_mode)}</b><span>{escape(str(generated.get("reason") or "Waiting for enough qualified legs"))}</span></div>',
            unsafe_allow_html=True,
        )
    st.caption(f"{MODEL_VERSION} • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • Game Total probability fails closed unless source-certified")


def render_nfl_hub(market: str = "Daily Picks") -> None:
    if str(market or "Daily Picks") != "Daily Picks":
        raise ValueError("NFL Daily Picks Command Center V3 only owns the Daily Picks market.")
    render_nfl_daily_picks_command_center()


__all__ = [
    "DEFAULT_RISK_MODE",
    "MARKET_IDS",
    "MODEL_VERSION",
    "RISK_MODES",
    "build_command_center_board",
    "render_nfl_daily_picks_command_center",
    "render_nfl_hub",
]
