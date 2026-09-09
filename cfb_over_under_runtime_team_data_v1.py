"""CFB O/U runtime team-data adapter V1.

This is the central presentation/model input adapter above all frozen layers.

Problem fixed
-------------
The visible Over/Under page could load stale cfb_team_data_v2 profiles (0-0,
NR, blank coach/polls) before later reconciliation wrappers ran. If a live
provider hiccup occurred, the later reconciliation silently fell back to those
stale profiles.

This adapter makes reconciliation the FIRST team-data handoff used by the base
Over/Under hub. It is field-granular and never all-or-nothing:

1. frozen Team Data V2 baseline,
2. deep live reconciliation,
3. local verified runtime snapshot fallback,
4. schedule-event record/rank fallback.

The input game dictionary is enriched in place so every downstream frozen UI
function sees the same corrected venue/broadcast/event metadata.

No model formula, selection threshold, sportsbook input, market probability,
EV, or Monte Carlo behavior is added.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

import cfb_over_under_deep_data_reconciliation_v1 as deep
import cfb_team_data_v2 as frozen

MODEL_VERSION = "CFB O/U RUNTIME TEAM DATA V1 • CENTRAL RECONCILED ADAPTER"
FROZEN_TEAM_DATA = "cfb_team_data_v2"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "cfb_runtime_snapshot_v1.json"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", "")
    text = text.replace("(fl)", "fl").replace("(oh)", "oh")
    return re.sub(r"[^a-z0-9]+", "", text)


def _parse_record(text: Any) -> dict[str, int]:
    return deep._parse_record(text)


def _record_text(record: Mapping[str, Any]) -> str:
    return deep._record_text(record)


def _load_snapshot() -> dict[str, Any]:
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _find_snapshot(game: Mapping[str, Any]) -> dict[str, Any]:
    payload = _load_snapshot()
    event_id = _clean(game.get("espn_event_id"))
    day = _clean(game.get("game_date"))
    away = _key(game.get("away_team"))
    home = _key(game.get("home_team"))
    for row in payload.get("games") or []:
        if not isinstance(row, Mapping):
            continue
        if event_id and _clean(row.get("event_id")) == event_id:
            return dict(row)
        if (
            day
            and _clean(row.get("game_date")) == day
            and _key(row.get("away_team")) == away
            and _key(row.get("home_team")) == home
        ):
            return dict(row)
    return {}


def _merge_game_snapshot(game: dict[str, Any], snap: Mapping[str, Any]) -> None:
    mapping = {
        "event_id": "espn_event_id",
        "venue": "venue",
        "broadcast": "broadcast",
        "status": "status",
        "espn_week": "espn_week",
    }
    for source_key, target_key in mapping.items():
        value = snap.get(source_key)
        if value not in (None, "", []):
            game[target_key] = value

    for side in ("away", "home"):
        side_snap = snap.get(side) or {}
        if not isinstance(side_snap, Mapping):
            continue
        if _clean(side_snap.get("team_id")):
            game[f"{side}_espn_team_id"] = _clean(side_snap.get("team_id"))
        if _clean(side_snap.get("record_text")):
            game[f"{side}_record_summary"] = _clean(side_snap.get("record_text"))
        if _clean(side_snap.get("conference_record_text")):
            game[f"{side}_conference_record_summary"] = _clean(
                side_snap.get("conference_record_text")
            )
        try:
            rank = side_snap.get("ap_rank")
            if rank is not None:
                game[f"{side}_rank"] = int(rank)
        except Exception:
            pass

    game["runtime_snapshot_enriched"] = True


def _profile_from_snapshot(
    profile: Mapping[str, Any],
    side_snap: Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(profile)

    record_text = _clean(side_snap.get("record_text"))
    record = _parse_record(record_text)
    if record:
        out["record"] = record
        out["record_text"] = record_text

    for key in (
        "home_record",
        "away_record",
        "neutral_record",
    ):
        value = side_snap.get(key)
        if isinstance(value, Mapping):
            out[key] = dict(value)

    for key in (
        "conference_record_text",
        "recent_form",
        "head_coach",
        "division_context",
    ):
        value = side_snap.get(key)
        if value not in (None, ""):
            out[key] = value

    for key in (
        "ppg",
        "points_allowed_pg",
        "point_diff_pg",
        "ap_rank",
        "coaches_poll_rank",
        "cfp_rank",
    ):
        if key in side_snap:
            out[key] = side_snap.get(key)

    out["conference_record"] = _parse_record(
        out.get("conference_record_text")
    )

    polls = dict(out.get("polls") or {})
    if out.get("ap_rank") is not None:
        polls["ap"] = {
            "rank": out.get("ap_rank"),
            "state": "ranked",
            "source": "verified runtime snapshot",
        }
    elif _clean(out.get("division_context")).upper() == "FCS":
        polls.pop("ap", None)

    if out.get("coaches_poll_rank") is not None:
        polls["coaches"] = {
            "rank": out.get("coaches_poll_rank"),
            "state": "ranked",
            "source": "verified runtime snapshot",
        }
    elif _clean(out.get("division_context")).upper() == "FCS":
        polls.pop("coaches", None)

    if out.get("cfp_rank") is not None:
        polls["cfp"] = {
            "rank": out.get("cfp_rank"),
            "state": "ranked",
            "source": "verified runtime snapshot",
        }
    out["polls"] = polls

    out["runtime_snapshot_used"] = True
    out["runtime_reconciled"] = True
    if _clean(side_snap.get("team_id")):
        out["espn_team_id"] = _clean(side_snap.get("team_id"))
    return out


def _apply_game_event_fallback(
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    """Repair obvious stale visible fields from already-enriched schedule data."""
    out = dict(profile)

    summary = _clean(game.get(f"{side}_record_summary"))
    parsed = _parse_record(summary)
    if parsed:
        current = _clean(out.get("record_text"))
        current_parsed = _parse_record(current)
        if (
            not current_parsed
            or int(current_parsed.get("games") or 0)
            < int(parsed.get("games") or 0)
            or current in {"0-0", "—"}
        ):
            out["record"] = parsed
            out["record_text"] = summary

    conf = _clean(game.get(f"{side}_conference_record_summary"))
    if conf:
        out["conference_record_text"] = conf
        out["conference_record"] = _parse_record(conf)

    rank = game.get(f"{side}_rank")
    if rank is not None and _clean(out.get("division_context")).upper() != "FCS":
        try:
            out["ap_rank"] = int(rank)
            polls = dict(out.get("polls") or {})
            polls.setdefault("ap", {
                "rank": int(rank),
                "state": "ranked",
                "source": "verified schedule event",
            })
            out["polls"] = polls
        except Exception:
            pass

    team_id = _clean(game.get(f"{side}_espn_team_id"))
    if team_id:
        out["espn_team_id"] = team_id

    return out


def _runtime_status(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> tuple[str, list[str]]:
    issues: list[str] = []

    for side, profile in (("away", away), ("home", home)):
        event_record = _clean(game.get(f"{side}_record_summary"))
        visible_record = _clean(profile.get("record_text"))
        if event_record and event_record != visible_record:
            issues.append(
                f"{side} record mismatch event={event_record} profile={visible_record}"
            )

    if _clean(game.get("venue")) in {"", "Venue unavailable"}:
        issues.append("venue unavailable")
    if _clean(game.get("broadcast")) in {"", "Broadcast unavailable"}:
        issues.append("broadcast unavailable")

    status = "GREEN" if not issues else "PARTIAL"
    return status, issues


def reconcile_runtime(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return game, away, home, diagnostics with no silent stale fallback."""
    mutable_game = dict(game)
    profiles, base_diag = frozen.load_matchup_team_data(
        mutable_game,
        as_of_day,
    )
    away = dict(profiles.get("away") or {})
    home = dict(profiles.get("home") or {})

    # Prefer the checked-in verified snapshot when this matchup is present.
    # That removes deployed-runtime network dependence for current slates.
    snap = _find_snapshot(mutable_game)
    snapshot_used = bool(snap)
    deep_error = ""
    deep_ok = False
    deep_diag: dict[str, Any] = {}

    if snap:
        _merge_game_snapshot(mutable_game, snap)
        away = _profile_from_snapshot(
            away,
            snap.get("away") or {},
        )
        home = _profile_from_snapshot(
            home,
            snap.get("home") or {},
        )
    else:
        # No snapshot coverage: try live reconciliation, but never hide failure.
        try:
            evidence, deep_diag = deep.reconcile_matchup(
                mutable_game,
                as_of_day,
            )
            mutable_game.update(dict(evidence.get("game") or {}))
            away.update(dict(evidence.get("away") or {}))
            home.update(dict(evidence.get("home") or {}))
            deep_ok = True
        except Exception as exc:
            deep_error = f"{type(exc).__name__}: {exc}"[:500]

    away = _apply_game_event_fallback(away, mutable_game, "away")
    home = _apply_game_event_fallback(home, mutable_game, "home")

    # Mutate the selected game object too. The base hub passes this same dict to
    # every downstream frozen UI function after team-data loading.
    if isinstance(game, dict):
        game.update(mutable_game)

    status, issues = _runtime_status(mutable_game, away, home)

    diag = dict(base_diag)
    diag.update({
        "version": MODEL_VERSION,
        "runtime_reconciled": True,
        "runtime_status": status,
        "runtime_issues": issues,
        "deep_reconciliation_ok": deep_ok,
        "deep_reconciliation_error": deep_error,
        "runtime_snapshot_used": snapshot_used,
        "runtime_snapshot_path": str(SNAPSHOT_PATH.name),
        "deep_diag": deep_diag,
    })

    return mutable_game, away, home, diag


def load_matchup_team_data(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _, away, home, diag = reconcile_runtime(game, as_of_day)
    return {"away": away, "home": home}, diag


def clear_team_data_cache() -> None:
    try:
        frozen.clear_team_data_cache()
    except Exception:
        pass
    try:
        deep.clear_reconciliation_cache()
    except Exception:
        pass


__all__ = [
    "FROZEN_TEAM_DATA",
    "MODEL_VERSION",
    "SNAPSHOT_PATH",
    "_find_snapshot",
    "_runtime_status",
    "clear_team_data_cache",
    "load_matchup_team_data",
    "reconcile_runtime",
]
