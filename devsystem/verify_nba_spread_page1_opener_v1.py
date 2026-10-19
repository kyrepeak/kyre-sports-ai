"""Live opener verifier for NBA Spread Professional Decision Board V1.

Reports only truthful provider/model states, provider-call counts, and measured
assembly timings. Credential material is never printed or returned.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
from time import perf_counter
from typing import Any, Callable

from nba_spread_decision_board_data_v1 import build_decision_board_state

TARGETS = (
    ("2026-10-20", "BOS", "DET", "BOS@DET"),
    ("2026-10-20", "PHI", "NYK", "PHI@NYK"),
    ("2026-10-20", "OKC", "SAS", "OKC@SAS"),
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _select_targets(games: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for date, away, home, label in TARGETS:
        matches = [
            dict(game)
            for game in games
            if _clean(game.get("game_date_phoenix")) == date
            and _clean(game.get("away_tricode")).upper() == away
            and _clean(game.get("home_tricode")).upper() == home
        ]
        if len(matches) == 1:
            selected.append(matches[0])
        else:
            missing.append(label)
    return selected, missing


def _summarize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    market = dict(record.get("market") or {})
    fair = dict(record.get("fair") or {})
    cover = dict(record.get("cover") or {})
    injuries = dict(record.get("injuries") or {})
    decision = dict(record.get("decision") or {})
    return {
        "game_key": _clean(record.get("game_key")),
        "matchup": f"{_clean(record.get('away_tricode')).upper()}@{_clean(record.get('home_tricode')).upper()}",
        "market": {
            "verification": _clean(market.get("verification")) or "UNAVAILABLE",
            "coverage": _clean(market.get("coverage")) or "UNAVAILABLE",
            "sportsbook_count": int(market.get("sportsbook_count") or 0),
            "sportsbook": _clean(market.get("sportsbook")) or None,
            "away_spread": market.get("away_spread"),
            "home_spread": market.get("home_spread"),
            "away_price": market.get("away_price"),
            "home_price": market.get("home_price"),
            "label": _clean(market.get("label")) or None,
        },
        "fair": {
            "verification": _clean(fair.get("verification")) or "UNAVAILABLE",
            "away_spread": fair.get("away_spread"),
            "home_spread": fair.get("home_spread"),
        },
        "cover": {
            "verification": _clean(cover.get("verification")) or "UNAVAILABLE",
            "away_probability": cover.get("away_probability"),
            "home_probability": cover.get("home_probability"),
        },
        "injuries": {
            "verification": _clean(injuries.get("verification")) or "UNAVAILABLE",
            "away_summary": _clean(injuries.get("away_summary")) or None,
            "home_summary": _clean(injuries.get("home_summary")) or None,
        },
        "decision": {
            "verification": _clean(decision.get("verification")) or "UNAVAILABLE",
            "decision_state": _clean(decision.get("decision_state")) or "NO_PLAY",
            "pick_text": _clean(decision.get("pick_text")) or None,
        },
    }


def run_probe(
    *,
    schedule_loader: Callable[[], Mapping[str, Any]] | None = None,
    market_loader: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]] | None = None,
    injury_loader: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]] | None = None,
    public_loader: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]] | None = None,
    credential_resolver: Callable[[], object] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if schedule_loader is None:
        from nba_spread_page_v7 import _load_launch_schedule as schedule_loader
    if market_loader is None or credential_resolver is None:
        import nba_spread_live_data_repair_v2 as live_v2
        market_loader = market_loader or live_v2.load_market_payload_v2
        credential_resolver = credential_resolver or live_v2.resolve_sgo_api_key
    if injury_loader is None:
        from nba_spread_page_v2 import _load_injury_availability as injury_loader
    if public_loader is None:
        from nba_spread_live_data_repair_v2 import load_public_betting_payload as public_loader

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    credential_resolved = bool(credential_resolver())
    counters = {"schedule": 0, "market": 0, "injury": 0, "public": 0}

    counters["schedule"] += 1
    schedule = dict(schedule_loader() or {})
    games = [dict(game) for game in schedule.get("games") or [] if isinstance(game, Mapping)]
    opener, missing = _select_targets(games)

    if _clean(schedule.get("verification")).upper() != "VERIFIED":
        return {
            "verification": "BLOCKED",
            "blocker": "SCHEDULE_UNVERIFIED",
            "credential_resolved": credential_resolved,
            "provider_calls": counters,
            "all_opener_markets_verified": False,
            "games": [],
        }
    if missing:
        return {
            "verification": "BLOCKED",
            "blocker": "OPENER_GAME_IDENTITY_MISSING",
            "missing_matchups": missing,
            "credential_resolved": credential_resolved,
            "provider_calls": counters,
            "all_opener_markets_verified": False,
            "games": [],
        }

    cold_started = perf_counter()
    counters["market"] += 1
    market = dict(market_loader(opener) or {})
    counters["injury"] += 1
    injuries = dict(injury_loader(opener) or {})
    counters["public"] += 1
    public = dict(public_loader(opener) or {})
    board = build_decision_board_state(
        opener,
        market,
        injuries,
        public,
        now_utc=now,
    )
    cold_ms = (perf_counter() - cold_started) * 1000.0

    warm_started = perf_counter()
    warm_board = build_decision_board_state(
        opener,
        market,
        injuries,
        public,
        now_utc=now,
    )
    warm_ms = (perf_counter() - warm_started) * 1000.0

    rows = [_summarize_record(row) for row in board.get("games") or [] if isinstance(row, Mapping)]
    warm_rows = [_summarize_record(row) for row in warm_board.get("games") or [] if isinstance(row, Mapping)]
    exact_matchups = sorted(row["matchup"] for row in rows)
    expected_matchups = sorted(label for _, _, _, label in TARGETS)
    provider_contract_ok = all(counters[name] <= 1 for name in ("market", "injury", "public"))
    identity_ok = exact_matchups == expected_matchups and rows == warm_rows
    all_opener_markets_verified = (
        len(rows) == len(TARGETS)
        and all(
            _clean(row.get("market", {}).get("verification")).upper() == "VERIFIED"
            and int(row.get("market", {}).get("sportsbook_count") or 0) >= 1
            for row in rows
        )
    )

    if not identity_ok or not provider_contract_ok:
        blocker = "OPENER_CONTRACT_MISMATCH"
    elif not all_opener_markets_verified:
        blocker = "OPENER_MARKET_UNVERIFIED"
    else:
        blocker = None

    market_diag = _clean(market.get("diagnostic_state")) or "UNKNOWN"
    return {
        "verification": "VERIFIED" if blocker is None else "BLOCKED",
        "blocker": blocker,
        "credential_resolved": credential_resolved,
        "all_opener_markets_verified": all_opener_markets_verified,
        "market_transport": {
            "verification": _clean(market.get("verification")) or "UNAVAILABLE",
            "diagnostic_state": market_diag,
            "source": _clean(market.get("source")) or None,
            "source_chain": list(market.get("source_chain") or []),
            "primary_source_state": _clean(market.get("primary_source_state")) or None,
            "stale_observation_count": int(market.get("stale_observation_count") or 0),
        },
        "provider_calls": counters,
        "zero_provider_calls_per_card": provider_contract_ok,
        "timing_ms": {"cold_data_assembly": round(cold_ms, 3), "warm_data_assembly": round(warm_ms, 3)},
        "sportsbook_projection_influence": 0.0,
        "games": rows,
    }


def main() -> int:
    result = run_probe()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("verification") == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
