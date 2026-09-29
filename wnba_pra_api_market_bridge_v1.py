"""WNBA PRA API market bridge V1.

Step 1 moves the active PRA page's market transport behind the certified Kyre
Sports API.  Streamlit reads persisted WNBA player-prop snapshots from the API
and maps provider event identity back to the verified WNBA schedule.  The
existing PRA projection, grading, Monte Carlo, qualification, and ranking stack
continues to consume the same normalized market_snapshot contract.

No sportsbook credential is read in Streamlit and no provider is called
directly from this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import time
import unicodedata
from typing import Any, Mapping

import pandas as pd

from wnba_api_client_v1 import KyreWNBAAPIClient, KyreWNBAAPIError, SUPPORTED_SEASON

MODEL_VERSION = "WNBA PRA API MARKET BRIDGE V1"
API_SOURCE = "Kyre Sports API"
SNAPSHOT_PATH = "/api/v1/wnba/markets/player-props/collection-store/snapshots"
CACHE_TTL_SECONDS = 60.0

_STAT_MARKETS = {
    "points": ("points", "Points"),
    "rebounds": ("rebounds", "Rebounds"),
    "assists": ("assists", "Assists"),
    "pra": ("points+rebounds+assists", "PRA"),
    "points+rebounds+assists": ("points+rebounds+assists", "PRA"),
}

_TEAM_ALIASES = {
    "atlanta dream": "dream", "dream": "dream", "atl": "dream",
    "chicago sky": "sky", "sky": "sky", "chi": "sky",
    "connecticut sun": "sun", "sun": "sun", "con": "sun",
    "dallas wings": "wings", "wings": "wings", "dal": "wings",
    "golden state valkyries": "valkyries", "valkyries": "valkyries", "gsv": "valkyries",
    "indiana fever": "fever", "fever": "fever", "ind": "fever",
    "las vegas aces": "aces", "aces": "aces", "lva": "aces",
    "los angeles sparks": "sparks", "sparks": "sparks", "las": "sparks",
    "minnesota lynx": "lynx", "lynx": "lynx", "min": "lynx",
    "new york liberty": "liberty", "liberty": "liberty", "nyl": "liberty",
    "phoenix mercury": "mercury", "mercury": "mercury", "phx": "mercury",
    "seattle storm": "storm", "storm": "storm", "sea": "storm",
    "washington mystics": "mystics", "mystics": "mystics", "was": "mystics",
    "portland fire": "fire", "fire": "fire", "por": "fire",
    "toronto tempo": "tempo", "tempo": "tempo", "tor": "tempo",
}

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _ascii(value).lower()))


def _team_key(value: Any) -> str:
    norm = _norm(value)
    if norm in _TEAM_ALIASES:
        return _TEAM_ALIASES[norm]
    parts = norm.split()
    return parts[-1] if parts else ""


def _team_name(team: Mapping[str, Any] | None) -> str:
    obj = team if isinstance(team, Mapping) else {}
    for key in ("full_name", "display_name", "name"):
        value = str(obj.get(key) or "").strip()
        if value:
            return value
    city = str(obj.get("team_city") or "").strip()
    name = str(obj.get("team_name") or "").strip()
    if city or name:
        return " ".join(x for x in (city, name) if x)
    return str(obj.get("team_tricode") or "").strip()


def _game_lookup(schedule_payload: Mapping[str, Any]) -> tuple[dict[tuple[str, str], str], list[str]]:
    games = schedule_payload.get("games")
    if not isinstance(games, list):
        return {}, []
    lookup: dict[tuple[str, str], str] = {}
    labels: list[str] = []
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        gid = str(raw.get("game_id") or "").strip()
        away = _team_name(raw.get("away") if isinstance(raw.get("away"), Mapping) else {})
        home = _team_name(raw.get("home") if isinstance(raw.get("home"), Mapping) else {})
        ak, hk = _team_key(away), _team_key(home)
        if gid and ak and hk:
            lookup[(ak, hk)] = gid
            labels.append(f"{away} @ {home}")
    return lookup, labels


def _snapshot_offers(payload: Mapping[str, Any], day_str: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        return None, []
    for raw in snapshots:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("date") or "").strip() not in {"", day_str}:
            continue
        normalized = raw.get("normalized_input_feed")
        if not isinstance(normalized, Mapping):
            continue
        offers = normalized.get("offers")
        if isinstance(offers, list) and offers:
            return dict(raw), [dict(x) for x in offers if isinstance(x, Mapping)]
    return None, []


def _age_seconds(value: Any, now: datetime | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(0.0, (current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def _float(value: Any) -> float | None:
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except Exception:
        return None


def _american(value: Any) -> int | None:
    try:
        text = str(value or "").strip().replace(",", "")
        return int(round(float(text))) if text else None
    except Exception:
        return None


def _empty(day_str: str, state: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "selected_date": day_str,
        "provider": API_SOURCE,
        "league": "WNBA",
        "state": state,
        "events_received": 0,
        "schedule_games": 0,
        "matched_games": 0,
        "unmatched_games": [],
        "game_lines": pd.DataFrame(),
        "player_props": pd.DataFrame(),
        "error": error,
        "bookmakers": "",
        "market_source": None,
        "provider_id": None,
        "snapshot_id": None,
        "api_owned": True,
        "direct_provider_called": False,
    }


def _build_snapshot(
    day: Any,
    schedule_payload: Mapping[str, Any],
    snapshot_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    lookup, schedule_labels = _game_lookup(schedule_payload)
    if not lookup:
        out = _empty(day_str, "NO_WNBA_GAMES")
        out["schedule_games"] = len(schedule_payload.get("games") or []) if isinstance(schedule_payload.get("games"), list) else 0
        return out

    selected, offers = _snapshot_offers(snapshot_payload, day_str)
    if selected is None or not offers:
        out = _empty(day_str, "NO_STORED_MARKETS")
        out["schedule_games"] = len(lookup)
        return out

    rows: list[dict[str, Any]] = []
    unmatched: set[str] = set()
    event_ids: set[str] = set()
    books: set[str] = set()
    matched_games: set[str] = set()

    for offer in offers:
        stat_key = _norm(offer.get("stat")).replace(" ", "+")
        if stat_key == "points+rebounds+assists":
            canonical_stat = "points+rebounds+assists"
            market = "PRA"
        else:
            stat_norm = _norm(offer.get("stat"))
            mapped = _STAT_MARKETS.get(stat_norm)
            if mapped is None:
                continue
            canonical_stat, market = mapped

        side = str(offer.get("side") or "").strip().lower()
        if side not in {"over", "under"}:
            continue
        line = _float(offer.get("line"))
        odds = _american(offer.get("american_odds"))
        player_name = str(offer.get("player_name") or "").strip()
        if line is None or not player_name:
            continue

        away = str(offer.get("away_team") or "").strip()
        home = str(offer.get("home_team") or "").strip()
        pair = (_team_key(away), _team_key(home))
        game_id = lookup.get(pair)
        if not game_id and pair[0] and pair[1]:
            game_id = lookup.get((pair[1], pair[0]))
        if not game_id:
            label = f"{away or 'Away'} @ {home or 'Home'}"
            unmatched.add(label)
            continue

        source_event_id = str(offer.get("source_event_id") or "").strip()
        if source_event_id:
            event_ids.add(source_event_id)
        book = str(offer.get("sportsbook") or "").strip()
        if book:
            books.add(book)
        matched_games.add(game_id)
        updated = str(offer.get("market_captured_at_utc") or "").strip() or None

        rows.append({
            "game_id": game_id,
            "event_id": source_event_id,
            "player_id": "",
            "player_name": player_name,
            "player_key": _norm(player_name),
            "stat_id": canonical_stat,
            "market": market,
            "side": side,
            "line": line,
            "odds": odds,
            "book": book,
            "updated_at": updated,
            "age_seconds": _age_seconds(updated, now=now),
            "fair_odds": None,
            "fair_line": None,
        })

    props = pd.DataFrame(rows)
    state = "CONNECTED" if not props.empty else ("MATCH_FAILURE" if offers else "NO_STORED_MARKETS")
    out = _empty(day_str, state)
    out.update({
        "events_received": len(event_ids),
        "schedule_games": len(lookup),
        "matched_games": len(matched_games),
        "unmatched_games": sorted(unmatched),
        "player_props": props,
        "bookmakers": ",".join(sorted(books)),
        "market_source": str(selected.get("feed_source") or selected.get("provider_id") or "API snapshot"),
        "provider_id": selected.get("provider_id"),
        "snapshot_id": selected.get("snapshot_id"),
    })
    return out


def _read_api_snapshot(day_str: str) -> dict[str, Any]:
    api = KyreWNBAAPIClient()
    schedule = api.games_for_date(day_str, SUPPORTED_SEASON)
    snapshots = api.get_json(
        SNAPSHOT_PATH,
        params={
            "date": day_str,
            "season": SUPPORTED_SEASON,
            "limit": 20,
            "include_payload": "true",
        },
    )
    return _build_snapshot(day_str, schedule, snapshots)


def market_snapshot(day: Any) -> dict[str, Any]:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    cached = _CACHE.get(day_str)
    now_mono = time.monotonic()
    if cached and now_mono - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]
    try:
        result = _read_api_snapshot(day_str)
    except (KyreWNBAAPIError, Exception) as exc:
        result = _empty(day_str, "API_ERROR", error=f"{type(exc).__name__}: {exc}")
    _CACHE[day_str] = (now_mono, result)
    return result


def clear_cache() -> None:
    _CACHE.clear()


def render_market_panel(day: Any) -> None:
    import streamlit as st

    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    st.markdown("### 🎯 WNBA Kyre Sports API Market Bridge")
    st.caption(
        "API-owned WNBA player-prop transport • backend provider/failover ownership • "
        "Streamlit reads no sportsbook API secret • PRA projection math remains unchanged"
    )

    with st.spinner("🔌 Reading certified WNBA market truth from Kyre Sports API…"):
        snap = market_snapshot(day_str)

    state = str(snap.get("state") or "CHECK")
    prop_df = snap.get("player_props")
    source = str(snap.get("market_source") or "No current snapshot")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kyre API", "Connected" if state == "CONNECTED" else state.replace("_", " ").title())
    c2.metric("Games matched", f"{snap.get('matched_games', 0)}/{snap.get('schedule_games', 0)}")
    c3.metric("Market source", source[:22])
    c4.metric("Player prop rows", 0 if prop_df is None else len(prop_df))

    if state == "API_ERROR":
        st.warning(
            "Kyre Sports API market data could not be read safely. "
            "No sportsbook lines are being fabricated or substituted."
        )
        return
    if state == "NO_WNBA_GAMES":
        st.info("No verified WNBA games exist on the selected date, so no market snapshot is expected.")
        return
    if state == "NO_STORED_MARKETS":
        st.info(
            "Kyre Sports API has no stored WNBA player-prop market snapshot for this date yet. "
            "The projection engine stays independent and no lines are fabricated."
        )
        return
    if state == "MATCH_FAILURE":
        st.warning(
            "Kyre Sports API returned market offers, but none could be matched to the verified WNBA schedule identity. "
            "The page is failing closed."
        )
        return

    if snap.get("unmatched_games"):
        st.caption("Unmatched provider identities: " + " • ".join(snap["unmatched_games"][:6]))

    if prop_df is not None and not prop_df.empty:
        summary = (
            prop_df.groupby(["market", "book"], dropna=False)
            .agg(Players=("player_key", "nunique"), Markets=("line", "count"), FreshestSec=("age_seconds", "min"))
            .reset_index()
            .sort_values(["market", "Players"], ascending=[True, False])
        )
        summary["Freshest"] = summary["FreshestSec"].apply(
            lambda x: "—" if pd.isna(x) else (f"{int(x)}s" if float(x) < 120 else f"{int(float(x)//60)}m")
        )
        st.dataframe(
            summary[["market", "book", "Players", "Markets", "Freshest"]],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("API market details", expanded=False):
        st.write({
            "selected_date": snap.get("selected_date"),
            "api": API_SOURCE,
            "snapshot_id": snap.get("snapshot_id"),
            "provider_id": snap.get("provider_id"),
            "market_source": snap.get("market_source"),
            "events_received": snap.get("events_received"),
            "matched_games": snap.get("matched_games"),
            "api_owned": True,
            "direct_provider_called": False,
            "projection_math_changed": False,
        })
        if st.button("🔄 Refresh WNBA API market snapshot", use_container_width=True, key=f"wnba_api_market_refresh_{day_str}"):
            clear_cache()
            st.rerun()


def install() -> dict[str, Any]:
    import wnba_sportsgameodds_v1 as legacy

    legacy.market_snapshot = market_snapshot
    legacy.render_market_panel = render_market_panel
    legacy.clear_cache = clear_cache
    legacy._kyre_pra_api_market_bridge_installed = True
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "api_source": API_SOURCE,
        "snapshot_path": SNAPSHOT_PATH,
        "direct_provider_called": False,
        "projection_math_changed": False,
        "ranking_changed": False,
        "monte_carlo_changed": False,
    }


__all__ = [
    "API_SOURCE",
    "CACHE_TTL_SECONDS",
    "MODEL_VERSION",
    "SNAPSHOT_PATH",
    "_build_snapshot",
    "clear_cache",
    "install",
    "market_snapshot",
    "render_market_panel",
]
