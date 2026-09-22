from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-batter-pitcher"])

MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

MATCHUP_FIELDS = (
    "gamesPlayed",
    "plateAppearances",
    "atBats",
    "runs",
    "hits",
    "doubles",
    "triples",
    "homeRuns",
    "rbi",
    "baseOnBalls",
    "strikeOuts",
    "hitByPitch",
    "avg",
    "obp",
    "slg",
    "ops",
    "totalBases",
    "sacFlies",
)


def _get_json(url: str, *, params=None, timeout=15.0):
    try:
        response = httpx.get(url, params=params, timeout=timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream request failed: {exc}",
        ) from exc

    return response.json()


def _fetch_person(player_id: int):
    payload = _get_json(
        f"{MLB_PEOPLE_URL}/{player_id}",
        params={"hydrate": "currentTeam"},
    )

    people = (payload or {}).get("people", [])
    if not people:
        raise HTTPException(
            status_code=404,
            detail=f"MLB player {player_id} was not found.",
        )

    person = people[0]
    return {
        "player_id": person.get("id"),
        "full_name": person.get("fullName"),
        "bat_side": person.get("batSide", {}).get("code"),
        "bat_side_description": person.get("batSide", {}).get("description"),
        "pitch_hand": person.get("pitchHand", {}).get("code"),
        "pitch_hand_description": person.get("pitchHand", {}).get("description"),
        "primary_position": person.get("primaryPosition", {}).get("abbreviation"),
        "current_team_id": person.get("currentTeam", {}).get("id"),
        "current_team_name": person.get("currentTeam", {}).get("name"),
    }


def _fetch_bvp(batter_id: int, pitcher_id: int, season: int):
    payload = _get_json(
        f"{MLB_PEOPLE_URL}/{batter_id}/stats",
        params={
            "stats": "vsPlayer",
            "group": "hitting",
            "opposingPlayerId": pitcher_id,
            "season": season,
            "gameType": "R",
        },
    ) or {}

    blocks = []
    for block in payload.get("stats", []):
        stat_type = block.get("type", {}).get("displayName")
        normalized_splits = []

        for split in block.get("splits", []):
            stat = split.get("stat", {})
            normalized_splits.append(
                {
                    "season": split.get("season"),
                    "game_type": split.get("gameType"),
                    "date": split.get("date"),
                    "stats": {field: stat.get(field) for field in MATCHUP_FIELDS},
                }
            )

        blocks.append(
            {
                "type": stat_type,
                "splits": normalized_splits,
            }
        )

    return blocks


def _fetch_platoon_splits(player_id: int, season: int, group: str):
    payload = _get_json(
        f"{MLB_PEOPLE_URL}/{player_id}/stats",
        params={
            "stats": "statSplits",
            "group": group,
            "sitCodes": "vl,vr",
            "season": season,
            "gameType": "R",
        },
    ) or {}

    result = {}
    for block in payload.get("stats", []):
        for split in block.get("splits", []):
            split_meta = split.get("split", {})
            code = split_meta.get("code")
            if code not in {"vl", "vr"}:
                continue

            stat = split.get("stat", {})
            result[code] = {
                "code": code,
                "description": split_meta.get("description"),
                "season": split.get("season"),
                "game_type": split.get("gameType"),
                "stats": {field: stat.get(field) for field in MATCHUP_FIELDS},
            }

    return result


def _effective_batter_side(bat_side: str | None, pitcher_hand: str | None):
    if bat_side in {"L", "R"}:
        return bat_side

    if bat_side == "S":
        if pitcher_hand == "R":
            return "L"
        if pitcher_hand == "L":
            return "R"

    return None


def _sample_size_from_bvp(blocks):
    candidates = []

    for block in blocks:
        for split in block.get("splits", []):
            stats = split.get("stats", {})
            pa = stats.get("plateAppearances")
            ab = stats.get("atBats")

            for value in (pa, ab):
                if value is None:
                    continue
                try:
                    candidates.append(int(value))
                    break
                except (TypeError, ValueError):
                    continue

    return max(candidates) if candidates else 0


def _sample_label(sample_size: int):
    if sample_size <= 0:
        return "none"
    if sample_size < 10:
        return "very_small"
    if sample_size < 25:
        return "small"
    if sample_size < 50:
        return "moderate"
    return "larger"


@router.get("/matchups/batter/{batter_id}/pitcher/{pitcher_id}")
def get_mlb_batter_pitcher_matchup(
    batter_id: int,
    pitcher_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="Season used for BvP and platoon splits. Defaults to current Arizona year.",
    ),
):
    if batter_id == pitcher_id:
        raise HTTPException(
            status_code=400,
            detail="Batter and pitcher must be different MLB player IDs.",
        )

    target_season = season or datetime.now(ARIZONA_TZ).year

    batter = _fetch_person(batter_id)
    pitcher = _fetch_person(pitcher_id)

    bvp_blocks = _fetch_bvp(batter_id, pitcher_id, target_season)
    batter_platoon = _fetch_platoon_splits(batter_id, target_season, "hitting")
    pitcher_platoon = _fetch_platoon_splits(pitcher_id, target_season, "pitching")

    pitcher_hand = pitcher.get("pitch_hand")
    batter_hand = batter.get("bat_side")
    effective_batter_side = _effective_batter_side(batter_hand, pitcher_hand)

    batter_split_code = "vl" if pitcher_hand == "L" else "vr" if pitcher_hand == "R" else None
    pitcher_split_code = (
        "vl" if effective_batter_side == "L" else "vr" if effective_batter_side == "R" else None
    )

    sample_size = _sample_size_from_bvp(bvp_blocks)
    bvp_available = sample_size > 0

    selected_batter_platoon = batter_platoon.get(batter_split_code) if batter_split_code else None
    selected_pitcher_platoon = pitcher_platoon.get(pitcher_split_code) if pitcher_split_code else None

    missing_components = []
    if not bvp_available:
        missing_components.append("bvp_history")
    if selected_batter_platoon is None:
        missing_components.append("batter_platoon_split")
    if selected_pitcher_platoon is None:
        missing_components.append("pitcher_platoon_split")

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "season": target_season,
        "batter": batter,
        "pitcher": pitcher,
        "matchup_context": {
            "batter_bats": batter_hand,
            "pitcher_throws": pitcher_hand,
            "effective_batter_side": effective_batter_side,
            "batter_platoon_split_code": batter_split_code,
            "pitcher_platoon_split_code": pitcher_split_code,
            "same_side_matchup": (
                effective_batter_side == pitcher_hand
                if effective_batter_side in {"L", "R"} and pitcher_hand in {"L", "R"}
                else None
            ),
        },
        "batter_vs_pitcher": {
            "available": bvp_available,
            "sample_size_estimate": sample_size,
            "sample_size_label": _sample_label(sample_size),
            "blocks": bvp_blocks,
            "modeling_note": (
                "BvP is descriptive context only. Small samples should receive limited model weight."
            ),
        },
        "platoon": {
            "batter_all_splits": batter_platoon,
            "pitcher_all_splits": pitcher_platoon,
            "selected_batter_split": selected_batter_platoon,
            "selected_pitcher_split": selected_pitcher_platoon,
        },
        "data_quality": {
            "bvp_available": bvp_available,
            "batter_platoon_available": selected_batter_platoon is not None,
            "pitcher_platoon_available": selected_pitcher_platoon is not None,
            "missing_components": missing_components,
            "complete": len(missing_components) == 0,
        },
    }
