"""College Football market identity reconciliation — odds integration Step 2.

This layer attaches provider market rows from Step 1 to the already-verified
College Football runtime game identities. It is intentionally market-context
only: sportsbook data never changes projection math and remains 0% model weight.

Matching policy:
- official identity comes from the verified runtime snapshot;
- event date must match in America/New_York;
- both away and home school names must pass deterministic normalization;
- ambiguous candidates fail closed;
- no synthetic official IDs are created.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.api.cfb_markets import _load_feed

router = APIRouter(prefix="/api/v1/cfb/markets", tags=["cfb"])

MODEL_VERSION = "CFB MARKET IDENTITY V1 • ODDS INTEGRATION STEP 2"
SNAPSHOT_PATH_ENV = "CFB_VERIFIED_SNAPSHOT_PATH"
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "cfb_runtime_snapshot_v1.json"
)
MATCH_THRESHOLD = 0.88
AMBIGUITY_MARGIN = 0.08
_ET = ZoneInfo("America/New_York")

_GENERIC_TOKENS = {
    "the",
    "university",
    "college",
    "football",
    "team",
}

_TOKEN_REPLACEMENTS = {
    "st": "state",
    "st.": "state",
}

_EXACT_ALIASES = {
    "southern california": "usc",
    "southern california trojans": "usc",
    "usc trojans": "usc",
    "connecticut": "uconn",
    "connecticut huskies": "uconn",
    "uconn huskies": "uconn",
    "central florida": "ucf",
    "central florida knights": "ucf",
    "ucf knights": "ucf",
    "southern methodist": "smu",
    "southern methodist mustangs": "smu",
    "smu mustangs": "smu",
    "brigham young": "byu",
    "brigham young cougars": "byu",
    "byu cougars": "byu",
    "texas christian": "tcu",
    "texas christian horned frogs": "tcu",
    "tcu horned frogs": "tcu",
    "north carolina state": "nc state",
    "north carolina state wolfpack": "nc state",
    "nc state wolfpack": "nc state",
    "mississippi rebels": "ole miss",
    "ole miss rebels": "ole miss",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalized_text(value: Any) -> str:
    text = _ascii(value).casefold().replace("&", " and ")
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _EXACT_ALIASES.get(text, text)


def _tokens(value: Any) -> tuple[str, ...]:
    text = _normalized_text(value)
    tokens: list[str] = []
    for raw in text.split():
        token = _TOKEN_REPLACEMENTS.get(raw, raw)
        if token and token not in _GENERIC_TOKENS:
            tokens.append(token)
    return tuple(tokens)


def _name_score(provider_name: Any, verified_name: Any) -> float:
    """Return a deterministic school-name agreement score in [0, 1]."""
    p_text = _normalized_text(provider_name)
    v_text = _normalized_text(verified_name)
    if not p_text or not v_text:
        return 0.0
    if p_text == v_text:
        return 1.0

    p = set(_tokens(provider_name))
    v = set(_tokens(verified_name))
    if not p or not v:
        return 0.0

    if p == v:
        return 1.0

    # Providers commonly append a mascot to the school/location name. Requiring
    # all verified location tokens to be present keeps this deterministic while
    # allowing "Ohio State Buckeyes" -> "Ohio State".
    if v.issubset(p):
        return 0.98 if len(v) >= 2 else 0.90
    if p.issubset(v):
        return 0.96 if len(p) >= 2 else 0.88

    overlap = len(p & v)
    union = len(p | v)
    if not union:
        return 0.0
    jaccard = overlap / union
    containment = overlap / min(len(p), len(v))
    return round((0.55 * containment) + (0.45 * jaccard), 6)


def _parse_market_date(start_time_utc: Any) -> str:
    text = _clean(start_time_utc)
    if not text:
        raise ValueError("start_time_utc is required for identity reconciliation")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("start_time_utc must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("start_time_utc must include a timezone")
    return parsed.astimezone(_ET).date().isoformat()


def _snapshot_path() -> Path:
    configured = _clean(os.environ.get(SNAPSHOT_PATH_ENV))
    if not configured:
        return DEFAULT_SNAPSHOT_PATH
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{SNAPSHOT_PATH_ENV} must be an absolute path")
    return path


def _normalize_verified_game(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    event_id = _clean(row.get("event_id"))
    game_date = _clean(row.get("game_date"))
    away_team = _clean(row.get("away_team"))
    home_team = _clean(row.get("home_team"))
    if not event_id or not game_date or not away_team or not home_team:
        return None

    away = row.get("away") if isinstance(row.get("away"), dict) else {}
    home = row.get("home") if isinstance(row.get("home"), dict) else {}
    return {
        "event_id": event_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "away_team_id": _clean(away.get("team_id")),
        "home_team_id": _clean(home.get("team_id")),
        "venue": _clean(row.get("venue")),
        "broadcast": _clean(row.get("broadcast")),
        "status": _clean(row.get("status")),
        "sources": list(row.get("sources") or []),
    }


def load_verified_games() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _snapshot_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError("verified CFB runtime snapshot is missing") from exc
    except OSError as exc:
        raise ValueError("verified CFB runtime snapshot is unavailable") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("verified CFB runtime snapshot is invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise ValueError("verified CFB runtime snapshot has an invalid contract")

    games: list[dict[str, Any]] = []
    malformed = 0
    seen_ids: set[str] = set()
    duplicate_ids = 0
    for row in payload["games"]:
        game = _normalize_verified_game(row)
        if game is None:
            malformed += 1
            continue
        if game["event_id"] in seen_ids:
            duplicate_ids += 1
            continue
        seen_ids.add(game["event_id"])
        games.append(game)

    return games, {
        "snapshot_version": payload.get("version"),
        "snapshot_generated_at": payload.get("generated_at"),
        "snapshot_window": payload.get("window"),
        "verified_games": len(games),
        "malformed_games_ignored": malformed,
        "duplicate_event_ids_ignored": duplicate_ids,
    }


def _qualified_candidates(
    market: Mapping[str, Any],
    verified_games: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    game_date = _parse_market_date(market.get("start_time_utc"))
    candidates: list[dict[str, Any]] = []
    for verified in verified_games:
        if verified.get("game_date") != game_date:
            continue
        away_score = _name_score(market.get("away_team"), verified.get("away_team"))
        home_score = _name_score(market.get("home_team"), verified.get("home_team"))
        if away_score < MATCH_THRESHOLD or home_score < MATCH_THRESHOLD:
            continue
        pair_score = (away_score + home_score) / 2.0
        candidates.append(
            {
                "verified": verified,
                "away_score": away_score,
                "home_score": home_score,
                "pair_score": pair_score,
            }
        )
    candidates.sort(
        key=lambda row: (
            -float(row["pair_score"]),
            str(row["verified"].get("event_id") or ""),
        )
    )
    return game_date, candidates


def _attach_market(
    market: Mapping[str, Any],
    verified: Mapping[str, Any],
    *,
    game_date: str,
    away_score: float,
    home_score: float,
    pair_score: float,
) -> dict[str, Any]:
    return {
        "official_game_id": str(verified["event_id"]),
        "provider_game_id": _clean(market.get("game_id")),
        "game_date": game_date,
        "provider_away_team": _clean(market.get("away_team")),
        "provider_home_team": _clean(market.get("home_team")),
        "official_away_team": _clean(verified.get("away_team")),
        "official_home_team": _clean(verified.get("home_team")),
        "away_team_id": _clean(verified.get("away_team_id")),
        "home_team_id": _clean(verified.get("home_team_id")),
        "start_time_utc": _clean(market.get("start_time_utc")),
        "total": market.get("total"),
        "sportsbook": _clean(market.get("sportsbook")),
        "updated_at_utc": _clean(market.get("updated_at_utc")),
        "line_status": _clean(market.get("line_status")),
        "venue": _clean(verified.get("venue")),
        "broadcast": _clean(verified.get("broadcast")),
        "official_status": _clean(verified.get("status")),
        "identity_verified": True,
        "match_method": "eastern-date + deterministic away/home school identity",
        "match_confidence": round(float(pair_score), 6),
        "away_name_score": round(float(away_score), 6),
        "home_name_score": round(float(home_score), 6),
    }


def reconcile_market_feed(
    feed: Mapping[str, Any],
    verified_games: list[dict[str, Any]],
) -> dict[str, Any]:
    markets = feed.get("games")
    if not isinstance(markets, list):
        raise ValueError("market feed games must be a list")

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for market in markets:
        if not isinstance(market, dict):
            unmatched.append(
                {
                    "provider_game_id": "",
                    "reason": "market_row_not_object",
                    "identity_verified": False,
                }
            )
            continue

        try:
            game_date, candidates = _qualified_candidates(market, verified_games)
        except ValueError as exc:
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "reason": str(exc),
                    "identity_verified": False,
                }
            )
            continue

        if not candidates:
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "game_date": game_date,
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "sportsbook": _clean(market.get("sportsbook")),
                    "total": market.get("total"),
                    "reason": "no_verified_match",
                    "identity_verified": False,
                }
            )
            continue

        best = candidates[0]
        if (
            len(candidates) > 1
            and float(best["pair_score"]) - float(candidates[1]["pair_score"])
            < AMBIGUITY_MARGIN
        ):
            unmatched.append(
                {
                    "provider_game_id": _clean(market.get("game_id")),
                    "game_date": game_date,
                    "provider_away_team": _clean(market.get("away_team")),
                    "provider_home_team": _clean(market.get("home_team")),
                    "sportsbook": _clean(market.get("sportsbook")),
                    "total": market.get("total"),
                    "reason": "ambiguous_verified_match",
                    "candidate_official_game_ids": [
                        str(row["verified"].get("event_id") or "")
                        for row in candidates[:3]
                    ],
                    "identity_verified": False,
                }
            )
            continue

        matched.append(
            _attach_market(
                market,
                best["verified"],
                game_date=game_date,
                away_score=float(best["away_score"]),
                home_score=float(best["home_score"]),
                pair_score=float(best["pair_score"]),
            )
        )

    official_ids = {row["official_game_id"] for row in matched}
    provider_ids = {row["provider_game_id"] for row in matched if row["provider_game_id"]}
    semantics = dict(feed.get("market_semantics") or {})
    semantics.update(
        {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }
    )
    return {
        "model_version": MODEL_VERSION,
        "schema_version": feed.get("schema_version"),
        "captured_at_utc": feed.get("captured_at_utc"),
        "source": feed.get("source"),
        "lines": matched,
        "unmatched": unmatched,
        "diagnostics": {
            "input_market_rows": len(markets),
            "matched_market_rows": len(matched),
            "unmatched_market_rows": len(unmatched),
            "unique_provider_games_matched": len(provider_ids),
            "unique_official_games_matched": len(official_ids),
            "all_lines_identity_verified": len(unmatched) == 0,
            "fail_closed": True,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
            "match_threshold": MATCH_THRESHOLD,
            "ambiguity_margin": AMBIGUITY_MARGIN,
        },
        "market_semantics": semantics,
    }


@router.get("/identity-status")
def identity_status():
    try:
        games, diag = load_verified_games()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "step": 2,
        "model_version": MODEL_VERSION,
        "identity_ready": bool(games),
        "verified_snapshot": diag,
        "identity_policy": {
            "official_id_source": "verified CFB runtime snapshot event_id",
            "fuzzy_matching": False,
            "synthetic_ids": False,
            "fail_closed": True,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


@router.get("/reconciled")
def reconciled(
    official_game_id: str | None = Query(default=None),
    provider_game_id: str | None = Query(default=None),
):
    feed = _load_feed()
    try:
        verified_games, snapshot_diag = load_verified_games()
        result = reconcile_market_feed(feed, verified_games)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    lines = result["lines"]
    if official_game_id is not None:
        lines = [
            row for row in lines
            if row["official_game_id"] == str(official_game_id).strip()
        ]
    if provider_game_id is not None:
        lines = [
            row for row in lines
            if row["provider_game_id"] == str(provider_game_id).strip()
        ]

    if (official_game_id is not None or provider_game_id is not None) and not lines:
        raise HTTPException(
            status_code=404,
            detail="No identity-verified CFB market line matched that game.",
        )

    output = dict(result)
    output["lines"] = lines
    output["verified_snapshot"] = snapshot_diag
    if official_game_id is not None or provider_game_id is not None:
        output["unmatched"] = []
        output["diagnostics"] = dict(result["diagnostics"])
        output["diagnostics"]["filtered_line_count"] = len(lines)
    return output


__all__ = [
    "AMBIGUITY_MARGIN",
    "MATCH_THRESHOLD",
    "MODEL_VERSION",
    "SNAPSHOT_PATH_ENV",
    "_name_score",
    "load_verified_games",
    "reconcile_market_feed",
    "router",
]
