"""WNBA Rebounds V2.2 — Step 13 exact SportsGameOdds rebound lines.

Extends the verified V2.1 chain without changing Steps 1-12.

Step-13 rules:
- Read exact WNBA full-game player rebound O/U markets from SportsGameOdds v2 /events.
- Use statID=rebounds, periodID=game, betTypeID=ou only.
- Keep bookmaker lines/prices/timestamps separate; never substitute consensus odds.
- Pair Over/Under only when the SAME bookmaker offers the SAME rebound line.
- Join SportsGameOdds player identity to the verified Step-12 player list by
  provider player metadata / market name, with unique normalized-name matching.
- A verified player with no posted rebound market is VERIFIED NO MARKET, not a
  guessed sportsbook line.
- Step 13 is market ingestion only. No no-vig calculation, projection, EV or
  Monte Carlo is performed here.
"""
from __future__ import annotations

import os
import re
import unicodedata

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_schedule_v25 as schedule_v25
import wnba_rebounds_hub_v21 as base

MODEL_VERSION = "WNBA REBOUNDS V2.2 • STEP 13 EXACT SPORTSGAMEODDS REBOUND LINES"

SGO_API_BASE = "https://api.sportsgameodds.com/v2"
SGO_BOOKMAKERS = (
    "fanduel", "draftkings", "betmgm", "caesars", "espnbet",
    "bet365", "fanatics", "circa", "pinnacle",
)
BOOK_DISPLAY = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "espnbet": "ESPN BET",
    "bet365": "bet365",
    "fanatics": "Fanatics",
    "circa": "Circa",
    "pinnacle": "Pinnacle",
}
SECRET_NAMES = (
    "SPORTSGAMEODDS_API_KEY",
    "SPORTSGAMEODDS_KEY",
    "SGO_API_KEY",
)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(str(value).replace(",", "").strip())
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _api_key():
    """Resolve provider key without ever displaying it."""
    for name in SECRET_NAMES:
        value = os.environ.get(name)
        if value:
            return str(value).strip(), f"environment:{name}"
    try:
        for name in SECRET_NAMES:
            if name in st.secrets and st.secrets.get(name):
                return str(st.secrets.get(name)).strip(), f"streamlit-secret:{name}"
    except Exception:
        pass
    value = str(st.session_state.get("wnba_rebounds_sgo_session_key_v22") or "").strip()
    if value:
        return value, "session-password-input"
    return "", "missing"


def _team_name_from_side(side):
    if isinstance(side, str):
        return side
    if not isinstance(side, dict):
        return ""
    names = side.get("names") or {}
    if isinstance(names, dict):
        for key in ("long", "display", "medium", "short"):
            if names.get(key):
                return str(names.get(key))
    for key in ("displayName", "name", "longName", "shortName"):
        if side.get(key):
            return str(side.get(key))
    return ""


def _event_team_names(event: dict):
    teams = event.get("teams") or {}
    home = _team_name_from_side(teams.get("home")) if isinstance(teams, dict) else ""
    away = _team_name_from_side(teams.get("away")) if isinstance(teams, dict) else ""
    if home and away:
        return away, home

    home = _team_name_from_side(event.get("homeTeam") or {})
    away = _team_name_from_side(event.get("awayTeam") or {})
    return away, home


def _slate_pairs(slate: pd.DataFrame):
    pairs = {}
    if slate is None or slate.empty:
        return pairs
    for _, r in slate.iterrows():
        away = str(r.get("away_team") or "")
        home = str(r.get("home_team") or "")
        if away and home:
            key = tuple(sorted((_norm(away), _norm(home))))
            pairs[key] = {
                "away": away,
                "home": home,
                "away_id": int(r.get("away_team_id") or 0),
                "home_id": int(r.get("home_team_id") or 0),
            }
    return pairs


def _player_display(player_obj, fallback=""):
    if isinstance(player_obj, str):
        return player_obj
    if not isinstance(player_obj, dict):
        return fallback
    names = player_obj.get("names") or {}
    if isinstance(names, dict):
        for key in ("display", "long", "full", "fullName"):
            if names.get(key):
                return str(names.get(key))
    for key in ("displayName", "fullName", "name"):
        if player_obj.get(key):
            return str(player_obj.get(key))
    return fallback


def _event_player_map(event: dict):
    """Map SportsGameOdds playerID -> provider display name."""
    raw = event.get("players") or {}
    out = {}
    if isinstance(raw, dict):
        for pid, obj in raw.items():
            name = _player_display(obj)
            if name:
                out[str(pid)] = name
    elif isinstance(raw, list):
        for obj in raw:
            if not isinstance(obj, dict):
                continue
            pid = obj.get("playerID") or obj.get("id")
            name = _player_display(obj)
            if pid and name:
                out[str(pid)] = name
    return out


def _name_from_market(odd: dict):
    market = str(odd.get("marketName") or "")
    match = re.match(r"^\s*(.+?)\s+Rebounds?\b", market, flags=re.I)
    return str(match.group(1)).strip() if match else ""


def _provider_name(event: dict, odd: dict):
    entity = str(odd.get("statEntityID") or odd.get("playerID") or "")
    pmap = _event_player_map(event)
    name = pmap.get(entity, "")
    if name:
        return name
    name = _name_from_market(odd)
    if name:
        return name

    if entity and entity not in {"all", "home", "away"}:
        cleaned = re.sub(r"_\d+_WNBA$", "", entity, flags=re.I)
        cleaned = re.sub(r"_WNBA$", "", cleaned, flags=re.I)
        return cleaned.replace("_", " ").strip().title()
    return ""


def _quote_timestamp(value):
    text = str(value or "")
    if not text:
        return ""
    try:
        ts = pd.to_datetime(text, utc=True)
        if pd.isna(ts):
            return text
        return ts.isoformat()
    except Exception:
        return text


@st.cache_data(ttl=90, show_spinner=False, max_entries=8)
def _fetch_sgo_events(api_key: str):
    """One provider request; key is hashed by Streamlit cache, never displayed."""
    if not api_key:
        return [], {
            "ok": False,
            "status_code": 0,
            "error": "SportsGameOdds API key is not connected.",
        }
    try:
        response = requests.get(
            f"{SGO_API_BASE}/events",
            params={
                "leagueID": "WNBA",
                "oddsAvailable": "true",
                "finalized": "false",
                "limit": 100,
                "bookmakerID": ",".join(SGO_BOOKMAKERS),
                "includeAltLines": "false",
            },
            headers={"x-api-key": api_key},
            timeout=12,
        )
    except Exception as exc:
        return [], {
            "ok": False,
            "status_code": 0,
            "error": f"SportsGameOdds request failed: {type(exc).__name__}",
        }

    status = int(response.status_code)
    try:
        payload = response.json()
    except Exception:
        payload = {}

    if status != 200:
        provider_error = ""
        if isinstance(payload, dict):
            provider_error = str(payload.get("error") or payload.get("message") or "")
        return [], {
            "ok": False,
            "status_code": status,
            "error": provider_error or f"SportsGameOdds HTTP {status}",
        }

    data = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(data, list):
        data = []
    success = bool(payload.get("success", True)) if isinstance(payload, dict) else False
    return data, {
        "ok": bool(success),
        "status_code": status,
        "error": "" if success else str(payload.get("error") or "Provider returned success=false"),
        "events": int(len(data)),
    }


def _extract_rebound_quotes(events, slate_pairs):
    """Return exact available main-line rebound quotes for matched slate events."""
    quotes = []
    event_rows = []
    matched_events = {}

    for event in events or []:
        if not isinstance(event, dict):
            continue
        away, home = _event_team_names(event)
        pair_key = tuple(sorted((_norm(away), _norm(home)))) if away and home else None
        if not pair_key or pair_key not in slate_pairs:
            continue

        event_id = str(event.get("eventID") or event.get("id") or "")
        matched_events[pair_key] = event_id or f"{away}@{home}"
        odds = event.get("odds") or {}
        rebound_markets = 0
        available_quotes = 0

        if isinstance(odds, dict):
            iterable = odds.items()
        elif isinstance(odds, list):
            iterable = [(str(x.get("oddID") or i), x) for i, x in enumerate(odds) if isinstance(x, dict)]
        else:
            iterable = []

        for odd_id, odd in iterable:
            if not isinstance(odd, dict):
                continue
            stat_id = str(odd.get("statID") or "")
            period_id = str(odd.get("periodID") or "")
            bet_type = str(odd.get("betTypeID") or "")
            side = str(odd.get("sideID") or "").lower()
            entity = str(odd.get("statEntityID") or odd.get("playerID") or "")
            if (
                stat_id != "rebounds"
                or period_id != "game"
                or bet_type != "ou"
                or side not in {"over", "under"}
                or entity in {"", "all", "home", "away"}
            ):
                continue

            rebound_markets += 1
            player_name = _provider_name(event, odd)
            by_book = odd.get("byBookmaker") or {}
            if not isinstance(by_book, dict):
                continue

            for book, book_data in by_book.items():
                if not isinstance(book_data, dict):
                    continue
                if book not in SGO_BOOKMAKERS:
                    continue
                if book_data.get("available") is False:
                    continue
                line = _num(book_data.get("overUnder"))
                price_raw = book_data.get("odds")
                if not np.isfinite(line) or price_raw in (None, ""):
                    continue
                available_quotes += 1
                quotes.append({
                    "Event ID": event_id,
                    "Away": away,
                    "Home": home,
                    "SportsGameOdds Player ID": entity,
                    "Provider player": player_name,
                    "Player key": _norm(player_name),
                    "Bookmaker ID": str(book),
                    "Book": BOOK_DISPLAY.get(str(book), str(book)),
                    "Line": float(line),
                    "Side": side.upper(),
                    "Odds": str(price_raw),
                    "Last updated": _quote_timestamp(book_data.get("lastUpdatedAt")),
                    "Odd ID": str(odd.get("oddID") or odd_id),
                })

        event_rows.append({
            "Event ID": event_id,
            "Away": away,
            "Home": home,
            "Rebound markets": int(rebound_markets),
            "Available book quotes": int(available_quotes),
            "State": "VERIFIED",
        })

    return pd.DataFrame(quotes), pd.DataFrame(event_rows), matched_events


def _pair_quotes(quotes: pd.DataFrame):
    """Pair exact same-book/same-line Over and Under quotes."""
    if quotes is None or quotes.empty:
        return pd.DataFrame()

    rows = []
    group_cols = [
        "Event ID", "SportsGameOdds Player ID", "Provider player",
        "Bookmaker ID", "Book", "Line",
    ]
    for keys, part in quotes.groupby(group_cols, dropna=False, sort=False):
        event_id, player_id, player_name, book_id, book, line = keys
        over = part[part["Side"].eq("OVER")]
        under = part[part["Side"].eq("UNDER")]
        over_row = over.iloc[0] if not over.empty else None
        under_row = under.iloc[0] if not under.empty else None
        rows.append({
            "Event ID": event_id,
            "SportsGameOdds Player ID": player_id,
            "Provider player": player_name,
            "Player key": _norm(player_name),
            "Bookmaker ID": book_id,
            "Book": book,
            "Line": float(line),
            "Over odds": str(over_row.get("Odds")) if over_row is not None else "",
            "Under odds": str(under_row.get("Odds")) if under_row is not None else "",
            "Over updated": str(over_row.get("Last updated")) if over_row is not None else "",
            "Under updated": str(under_row.get("Last updated")) if under_row is not None else "",
            "Paired O/U": bool(over_row is not None and under_row is not None),
        })
    return pd.DataFrame(rows)


def _build_step13(api_key: str):
    records = st.session_state.get("wnba_rebounds_step12_players") or []
    players12 = pd.DataFrame(records)
    if players12.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "with_market": 0, "no_market": 0, "paired_quotes": 0,
            "reason": "no verified Step-12 player frame",
        }

    day = str(
        st.session_state.get("wnba_rebounds_step1_day")
        or pd.Timestamp.now().strftime("%Y-%m-%d")
    )
    try:
        slate = schedule_v25.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    slate_pairs = _slate_pairs(slate)
    events, provider = _fetch_sgo_events(api_key)
    quotes, event_rows, matched = _extract_rebound_quotes(events, slate_pairs)
    paired = _pair_quotes(quotes)

    verified_name_map = {}
    for idx, p in players12.iterrows():
        key = _norm(p.get("Player"))
        if key:
            verified_name_map.setdefault(key, []).append(idx)

    market_counts = {}
    quote_counts = {}
    pair_counts = {}
    if not quotes.empty:
        for key, part in quotes.groupby("Player key"):
            market_counts[str(key)] = int(part["Bookmaker ID"].nunique())
            quote_counts[str(key)] = int(len(part))
    if not paired.empty:
        for key, part in paired[paired["Paired O/U"]].groupby("Player key"):
            pair_counts[str(key)] = int(len(part))

    ambiguous_provider_keys = {
        str(key) for key, idxs in verified_name_map.items() if len(idxs) != 1
    }

    team_pair_by_name = {}
    for pair_key, info in slate_pairs.items():
        team_pair_by_name[_norm(info["away"])] = pair_key
        team_pair_by_name[_norm(info["home"])] = pair_key

    rows = []
    for _, p in players12.iterrows():
        name = str(p.get("Player") or "Player")
        key = _norm(name)
        team_key = _norm(p.get("Team"))
        pair_key = team_pair_by_name.get(team_key)
        event_verified = bool(pair_key and pair_key in matched)
        provider_ok = bool(provider.get("ok"))
        base_ok = str(p.get("Step12 state") or "") == "VERIFIED"

        provider_match_ambiguous = key in ambiguous_provider_keys
        books = int(market_counts.get(key, 0))
        quote_count = int(quote_counts.get(key, 0))
        paired_count = int(pair_counts.get(key, 0))

        if base_ok and provider_ok and event_verified and not provider_match_ambiguous:
            market_state = "MARKET FOUND" if quote_count > 0 else "VERIFIED NO MARKET"
            verified = True
        else:
            market_state = "CHECK"
            verified = False

        out = p.to_dict()
        out.update({
            "SGO books": books,
            "SGO exact quotes": quote_count,
            "SGO paired O/U": paired_count,
            "SGO market state": market_state,
            "Step13 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

    out = pd.DataFrame(rows)
    covered = int(out["Step13 state"].eq("VERIFIED").sum()) if not out.empty else 0
    with_market = int(out["SGO market state"].eq("MARKET FOUND").sum()) if not out.empty else 0
    no_market = int(out["SGO market state"].eq("VERIFIED NO MARKET").sum()) if not out.empty else 0
    paired_quotes = int(paired["Paired O/U"].sum()) if not paired.empty else 0
    matched_games = int(len(matched))
    slate_games = int(len(slate_pairs))

    ready = bool(
        provider.get("ok")
        and slate_games > 0
        and matched_games == slate_games
        and not out.empty
        and covered == len(out)
        and paired_quotes > 0
    )

    return out, paired, event_rows, {
        "ready": ready,
        "players": int(len(out)),
        "covered": covered,
        "with_market": with_market,
        "no_market": no_market,
        "paired_quotes": paired_quotes,
        "books": int(paired["Bookmaker ID"].nunique()) if not paired.empty else 0,
        "matched_games": matched_games,
        "slate_games": slate_games,
        "provider_ok": bool(provider.get("ok")),
        "provider_status": int(provider.get("status_code", 0) or 0),
        "provider_error": str(provider.get("error") or ""),
        "source": "SportsGameOdds v2 /events • WNBA • rebounds • game • O/U",
        "bookmakers": list(SGO_BOOKMAKERS),
    }


def _render_connection():
    api_key, source = _api_key()
    if api_key:
        st.caption(f"🔐 SportsGameOdds credential connected ({source}); key is never displayed.")
        return api_key

    st.warning(
        "🔐 Step 13 needs a SportsGameOdds API key. Add SPORTSGAMEODDS_API_KEY to "
        "Streamlit Secrets for persistent server-side use, or enter it below for this session only."
    )
    st.text_input(
        "SportsGameOdds API key (session only)",
        type="password",
        key="wnba_rebounds_sgo_session_key_v22",
        help="The value is used server-side for SportsGameOdds requests and is never shown in the output.",
    )
    return str(st.session_state.get("wnba_rebounds_sgo_session_key_v22") or "").strip()


def _render_step13():
    st.markdown("## 🧾 Step 13 — Exact SportsGameOdds Rebound Lines")
    st.caption(
        "This layer ingests exact full-game WNBA player rebound over/under lines directly from SportsGameOdds. "
        "Bookmakers stay separated: FanDuel is not blended with DraftKings, and an Over is paired with an Under "
        "only when the same book posts the exact same rebound line. Missing player markets are labeled NO MARKET; "
        "no sportsbook line is guessed. No-vig math is deferred to Step 14."
    )

    api_key = _render_connection()
    players13, paired, events, info = _build_step13(api_key)
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step13_ready"] = ready
    st.session_state["wnba_rebounds_step13_players"] = (
        players13.to_dict("records") if not players13.empty else []
    )
    st.session_state["wnba_rebounds_step13_quotes"] = (
        paired.to_dict("records") if not paired.empty else []
    )
    st.session_state["wnba_rebounds_step13_events"] = (
        events.to_dict("records") if not events.empty else []
    )

    a, b, c, d = st.columns(4)
    a.metric("Slate games", f"{info.get('matched_games',0)}/{info.get('slate_games',0)}")
    b.metric("Player states", f"{info.get('covered',0)}/{info.get('players',0)}")
    c.metric("Players w/ market", info.get("with_market", 0))
    d.metric("Paired exact O/U", info.get("paired_quotes", 0))

    if ready:
        st.success(
            "✅ STEP 13 PASSED • every Step-12 player has a verified SportsGameOdds market state, every selected "
            "WNBA game is matched, and at least one exact same-book/same-line Over+Under pair is available. "
            "Step 14 (same-book no-vig) is unlocked. No market price has influenced the rebound projection."
        )
    else:
        if not info.get("provider_ok"):
            err = info.get("provider_error") or "provider connection unavailable"
            st.error(
                f"⛔ STEP 13 CHECK • SportsGameOdds is not fully connected ({err}). "
                "Step 14 remains locked; sportsbook lines are never fabricated."
            )
        elif info.get("matched_games", 0) != info.get("slate_games", 0):
            st.error(
                "⛔ STEP 13 CHECK • SportsGameOdds did not reconcile every verified WNBA slate game. "
                "Step 14 remains locked until event identity is complete."
            )
        elif info.get("paired_quotes", 0) <= 0:
            st.warning(
                "⚠️ STEP 13 MARKET WAIT • provider/event identity is verified, but no exact same-book rebound "
                "Over+Under pair is currently available. Step 14 stays locked until a pair is posted."
            )
        else:
            st.error(
                "⛔ STEP 13 CHECK • at least one player market state could not be verified. "
                "Step 14 remains locked; ambiguous player identity is not guessed."
            )

    if not players13.empty:
        show = players13.copy()
        keep = [c for c in [
            "Player", "Team", "Opponent", "SGO books", "SGO exact quotes",
            "SGO paired O/U", "SGO market state", "Step13 state",
        ] if c in show.columns]
        st.dataframe(show[keep], hide_index=True, use_container_width=True)

    with st.expander("🧾 Exact SportsGameOdds rebound quote board"):
        if paired.empty:
            st.info("No exact rebound quote rows are currently available.")
        else:
            quote_show = paired.copy()
            quote_show["Line"] = pd.to_numeric(quote_show["Line"], errors="coerce").round(2)
            st.dataframe(
                quote_show[[
                    "Provider player", "Book", "Line", "Over odds", "Under odds",
                    "Paired O/U", "Over updated", "Under updated",
                ]],
                hide_index=True,
                use_container_width=True,
            )

    with st.expander("🧾 SportsGameOdds event reconciliation"):
        if events.empty:
            st.info("No selected-slate SportsGameOdds events matched yet.")
        else:
            st.dataframe(events, hide_index=True, use_container_width=True)

    with st.expander("🧾 Step-13 methodology / diagnostics"):
        st.write({
            "source": info.get("source"),
            "leagueID": "WNBA",
            "statID": "rebounds",
            "periodID": "game",
            "betTypeID": "ou",
            "bookmakers_requested": info.get("bookmakers"),
            "provider_HTTP_status": info.get("provider_status"),
            "main_lines_only": True,
            "alternate_lines_included": False,
            "available_bookmaker_quotes_only": True,
            "same_book_pair_rule": "Over and Under must share bookmakerID and exact overUnder line",
            "no_market_rule": "successful event query + no mapped rebound quote = VERIFIED NO MARKET",
            "consensus_line_substitution": False,
            "no_vig_applied": False,
            "applied_to_player_projection": False,
            "monte_carlo_used": False,
        })
        if not players13.empty and players13["Step13 state"].eq("CHECK").any():
            cols = [c for c in [
                "Player", "Team", "Opponent", "SGO market state", "Step12 state", "Step13 state"
            ] if c in players13.columns]
            st.dataframe(
                players13.loc[players13["Step13 state"].eq("CHECK"), cols],
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("## 🧱 Rebounds Build Order — Current")
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
        "Opponent rebounding allowed",
        "Position matchup — Guard/Wing/Big",
        "Pace + expected shot volume",
        "Lineup effects / rebound competition",
        "Player vs opponent rebound history",
        "Exact SportsGameOdds rebound lines",
        "Same-book no-vig",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 15), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.2 Step 13 only • Steps 1–12 preserved • exact SportsGameOdds bookmaker lines • "
        "same-book/same-line O/U pairing • no consensus substitution • no no-vig/EV/Monte Carlo/final projection."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step12_ready"):
        _render_step13()
    else:
        st.info("Step 13 remains locked until Step 12 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
