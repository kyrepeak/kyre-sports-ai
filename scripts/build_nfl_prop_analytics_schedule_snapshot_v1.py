"""Build the certified rolling NFL Prop Analytics schedule snapshot.

Runs only in GitHub Actions where the live provider chain is certifiable. The
output is data-only and is consumed by Streamlit as a transport fallback when
public egress cannot produce a complete independently verified slate.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from nfl_prop_analytics_schedule_v1 import (
    AZ,
    SOURCE_PRIORITY,
    _from_cbs,
    _from_espn,
    _from_nfl_official,
    _from_nflverse,
    _reconcile_schedule,
    _target_sunday,
    _week_hint,
)

DEFAULT_WEEKS = 15


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return ""


def _build_date(target: date) -> dict[str, Any] | None:
    nflverse = _from_nflverse(target)
    if not nflverse:
        return None

    week = _week_hint(nflverse)
    season = target.year

    # ESPN is the proven second source on GitHub runners. CBS and NFL official
    # remain independent optional sources; no provider is mandatory by name.
    providers: dict[str, list[dict[str, Any]]] = {
        "NFLVERSE": nflverse,
        "ESPN": [],
        "CBS": [],
        "NFL": [],
    }
    errors: dict[str, str] = {}

    for label, loader in (
        ("ESPN", lambda: _from_espn(target, candidate_games=nflverse)),
        ("CBS", lambda: _from_cbs(target, week=week)),
        ("NFL", lambda: _from_nfl_official(target, season=season, week=week)),
    ):
        try:
            providers[label] = loader()
        except Exception as exc:
            errors[label] = f"{type(exc).__name__}:{str(exc)[:240]}"

    games = _reconcile_schedule(providers, target)
    verified = [game for game in games if game.get("verified") is True]
    available = tuple(
        source for source in SOURCE_PRIORITY if providers.get(source)
    )

    if not games:
        raise RuntimeError(f"SNAPSHOT_EMPTY_SLATE:{target.isoformat()}")
    if len(verified) != len(games):
        raise RuntimeError(
            f"SNAPSHOT_VERIFICATION_INCOMPLETE:{target.isoformat()}:"
            f"{len(verified)}/{len(games)}"
        )
    if len(available) < 2:
        raise RuntimeError(
            f"SNAPSHOT_SOURCE_ROUTER_INCOMPLETE:{target.isoformat()}:"
            + ",".join(available)
        )

    rows = []
    for game in games:
        rows.append(
            {
                "away": game["away"],
                "home": game["home"],
                "kickoff_utc": _iso(game.get("kickoff_utc")),
                "week": game.get("week"),
                "network": game.get("network", ""),
                "status": game.get("status", ""),
                "venue": game.get("venue", ""),
                "game_id": game.get("game_id", ""),
                "sources": list(game.get("sources") or ()),
                "source_count": int(game.get("source_count") or 0),
                "verified": True,
                "kickoff_consensus": bool(game.get("kickoff_consensus")),
            }
        )

    return {
        "target_date": target.isoformat(),
        "season": season,
        "week": week,
        "game_count": len(rows),
        "verified_count": len(rows),
        "sources_available": list(available),
        "source_errors": errors,
        "games": rows,
    }


def build_snapshot(*, start: date | None = None, weeks: int = DEFAULT_WEEKS) -> dict[str, Any]:
    if weeks < 2:
        raise ValueError("weeks must be at least 2")

    first = _target_sunday(start or datetime.now(AZ).date())
    slates: list[dict[str, Any]] = []
    for offset in range(weeks):
        target = first + timedelta(days=7 * offset)
        slate = _build_date(target)
        if slate is not None:
            slates.append(slate)

    if not slates:
        raise RuntimeError("SNAPSHOT_NO_VERIFIED_SLATES")

    next_sunday = first + timedelta(days=7)
    if not any(row["target_date"] == next_sunday.isoformat() for row in slates):
        raise RuntimeError(
            f"SNAPSHOT_NEXT_WEEK_MISSING:{next_sunday.isoformat()}"
        )

    total_games = sum(int(row["game_count"]) for row in slates)
    return {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Rolling independently verified NFL Sunday schedule transport fallback "
            "for NFL Prop Analytics Step 2."
        ),
        "window": {
            "start": slates[0]["target_date"],
            "end": slates[-1]["target_date"],
            "requested_weeks": weeks,
            "verified_sundays": len(slates),
        },
        "certification": {
            "minimum_independent_sources": 2,
            "minimum_kickoff_votes": 2,
            "kickoff_consensus_seconds": 600,
            "verification_rule": "verified_count == game_count for every stored Sunday",
            "total_games": total_games,
        },
        "slates": slates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="data/nfl_prop_analytics_schedule_snapshot_v1.json",
    )
    parser.add_argument("--weeks", type=int, default=DEFAULT_WEEKS)
    parser.add_argument("--start", default="")
    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    payload = build_snapshot(start=start, weeks=args.weeks)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        "NFL_PROP_ANALYTICS_SCHEDULE_SNAPSHOT_GREEN",
        f"sundays={payload['window']['verified_sundays']}",
        f"games={payload['certification']['total_games']}",
        f"window={payload['window']['start']}..{payload['window']['end']}",
    )


if __name__ == "__main__":
    main()
