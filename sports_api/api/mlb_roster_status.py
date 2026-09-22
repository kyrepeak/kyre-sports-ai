from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-roster-status"])

MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
MLB_TRANSACTIONS_URL = "https://statsapi.mlb.com/api/v1/transactions"
ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _get_json(url: str, *, params=None, timeout=20.0):
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


def _parse_date(value: str, field_name: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from exc


def _fetch_person(player_id: int):
    payload = _get_json(
        f"{MLB_PEOPLE_URL}/{player_id}",
        params={"hydrate": "currentTeam"},
        timeout=15.0,
    )

    people = (payload or {}).get("people", [])
    if not people:
        raise HTTPException(
            status_code=404,
            detail=f"MLB player {player_id} was not found.",
        )

    return people[0]


def _fetch_team_roster(team_id: int, roster_type: str):
    payload = _get_json(
        f"{MLB_TEAMS_URL}/{team_id}/roster",
        params={"rosterType": roster_type},
        timeout=15.0,
    )
    return (payload or {}).get("roster", [])


def _find_roster_entry(roster, player_id: int):
    for entry in roster:
        if entry.get("person", {}).get("id") == player_id:
            return entry
    return None


def _normalize_roster_entry(entry):
    if not entry:
        return None

    person = entry.get("person", {})
    position = entry.get("position", {})
    status = entry.get("status", {})

    return {
        "player_id": person.get("id"),
        "player_name": person.get("fullName"),
        "jersey_number": entry.get("jerseyNumber"),
        "position_code": position.get("code"),
        "position_name": position.get("name"),
        "position_abbreviation": position.get("abbreviation"),
        "status_code": status.get("code"),
        "status_description": status.get("description"),
    }


def _fetch_transactions(*, start_date: str, end_date: str, player_id=None, team_id=None, limit=200):
    params = {
        "startDate": start_date,
        "endDate": end_date,
        "sportId": 1,
        "limit": limit,
    }
    if player_id is not None:
        params["playerId"] = player_id
    if team_id is not None:
        params["teamId"] = team_id

    payload = _get_json(MLB_TRANSACTIONS_URL, params=params, timeout=20.0) or {}
    transactions = payload.get("transactions", [])

    transactions.sort(
        key=lambda transaction: (
            transaction.get("effectiveDate") or transaction.get("date") or "",
            transaction.get("id") or 0,
        ),
        reverse=True,
    )
    return transactions


def _normalize_transaction(transaction):
    person = transaction.get("person", {})
    from_team = transaction.get("fromTeam", {})
    to_team = transaction.get("toTeam", {})

    return {
        "transaction_id": transaction.get("id"),
        "date": transaction.get("date"),
        "effective_date": transaction.get("effectiveDate"),
        "resolution_date": transaction.get("resolutionDate"),
        "type_code": transaction.get("typeCode"),
        "type_description": transaction.get("typeDesc"),
        "description": transaction.get("description"),
        "player_id": person.get("id"),
        "player_name": person.get("fullName"),
        "from_team_id": from_team.get("id"),
        "from_team_name": from_team.get("name"),
        "to_team_id": to_team.get("id"),
        "to_team_name": to_team.get("name"),
    }


def _infer_injured_list_state(transactions):
    for transaction in transactions:
        description = str(transaction.get("description") or "").lower()
        type_desc = str(transaction.get("typeDesc") or "").lower()
        combined = f"{type_desc} {description}"

        if "injured list" not in combined:
            continue

        if "activated" in combined or "reinstated" in combined:
            return {
                "on_injured_list": False,
                "source_transaction_id": transaction.get("id"),
                "source_description": transaction.get("description"),
            }

        if "placed" in combined or "transferred" in combined:
            return {
                "on_injured_list": True,
                "source_transaction_id": transaction.get("id"),
                "source_description": transaction.get("description"),
            }

    return {
        "on_injured_list": None,
        "source_transaction_id": None,
        "source_description": None,
    }


def _transaction_review_flags(transactions):
    if not transactions:
        return []

    latest_text = " ".join(
        str(value or "")
        for value in (
            transactions[0].get("typeDesc"),
            transactions[0].get("description"),
        )
    ).lower()

    flags = []
    checks = {
        "designated_for_assignment": "designated",
        "released": "released",
        "optioned": "optioned",
        "traded": "traded",
        "rehab_assignment": "rehab assignment",
        "bereavement_list": "bereavement list",
        "paternity_list": "paternity list",
        "restricted_list": "restricted list",
        "suspended": "suspended",
    }

    for flag, phrase in checks.items():
        if phrase in latest_text:
            flags.append(flag)

    return flags


def _verification_status(person, current_team_id, active_entry, forty_man_entry, il_state, review_flags):
    blocking_reasons = []

    if person.get("active") is False:
        blocking_reasons.append("player_marked_inactive")
    if current_team_id is None:
        blocking_reasons.append("current_team_missing")
    if active_entry is None:
        blocking_reasons.append("not_on_active_roster")
    if il_state.get("on_injured_list") is True:
        blocking_reasons.append("injured_list_signal")

    hard_block = len(blocking_reasons) > 0
    needs_review = bool(review_flags) or il_state.get("on_injured_list") is None

    if hard_block:
        status = "blocked"
    elif needs_review:
        status = "needs_review"
    else:
        status = "ready"

    return {
        "status": status,
        "projection_eligible": status == "ready",
        "blocking_reasons": blocking_reasons,
        "review_flags": review_flags,
        "active_roster_member": active_entry is not None,
        "forty_man_roster_member": forty_man_entry is not None,
    }


@router.get("/players/{player_id}/roster-status")
def get_mlb_player_roster_status(
    player_id: int,
    date: str | None = Query(
        default=None,
        description="Verification date in YYYY-MM-DD format. Defaults to today's Arizona date.",
    ),
    lookback_days: int = Query(
        default=60,
        ge=7,
        le=365,
        description="How many days of recent transactions to inspect.",
    ),
):
    target_text = date or datetime.now(ARIZONA_TZ).date().isoformat()
    target_date = _parse_date(target_text, "date")
    start_date = target_date - timedelta(days=lookback_days)

    person = _fetch_person(player_id)
    current_team = person.get("currentTeam", {})
    current_team_id = current_team.get("id")

    active_roster = []
    forty_man_roster = []
    if isinstance(current_team_id, int):
        active_roster = _fetch_team_roster(current_team_id, "active")
        forty_man_roster = _fetch_team_roster(current_team_id, "40Man")

    active_entry = _find_roster_entry(active_roster, player_id)
    forty_man_entry = _find_roster_entry(forty_man_roster, player_id)

    raw_transactions = _fetch_transactions(
        start_date=start_date.isoformat(),
        end_date=target_date.isoformat(),
        player_id=player_id,
        limit=200,
    )
    transactions = [_normalize_transaction(transaction) for transaction in raw_transactions]

    il_state = _infer_injured_list_state(raw_transactions)
    review_flags = _transaction_review_flags(raw_transactions)
    verification = _verification_status(
        person,
        current_team_id,
        active_entry,
        forty_man_entry,
        il_state,
        review_flags,
    )

    return {
        "source": "MLB Stats API",
        "verified_by": "Kyre Sports API",
        "player": {
            "player_id": person.get("id"),
            "full_name": person.get("fullName"),
            "active": person.get("active"),
            "current_team_id": current_team_id,
            "current_team_name": current_team.get("name"),
            "primary_position": person.get("primaryPosition", {}).get("abbreviation"),
        },
        "verification_date": target_date.isoformat(),
        "transaction_lookback_days": lookback_days,
        "roster": {
            "active": _normalize_roster_entry(active_entry),
            "forty_man": _normalize_roster_entry(forty_man_entry),
        },
        "injured_list": il_state,
        "verification": verification,
        "recent_transaction_count": len(transactions),
        "recent_transactions": transactions,
        "modeling_note": (
            "Roster-status verification is conservative. A blocked or needs_review player should "
            "not be projected as available without a later lineup/game-status confirmation."
        ),
    }


@router.get("/teams/{team_id}/transactions")
def get_mlb_team_transactions(
    team_id: int,
    start_date: str | None = Query(
        default=None,
        description="Start date in YYYY-MM-DD format. Defaults to 30 days before end_date.",
    ),
    end_date: str | None = Query(
        default=None,
        description="End date in YYYY-MM-DD format. Defaults to today's Arizona date.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum transactions to request from MLB.",
    ),
):
    end_text = end_date or datetime.now(ARIZONA_TZ).date().isoformat()
    parsed_end = _parse_date(end_text, "end_date")

    if start_date is None:
        parsed_start = parsed_end - timedelta(days=30)
    else:
        parsed_start = _parse_date(start_date, "start_date")

    if parsed_start > parsed_end:
        raise HTTPException(
            status_code=400,
            detail="start_date must be on or before end_date.",
        )

    raw_transactions = _fetch_transactions(
        start_date=parsed_start.isoformat(),
        end_date=parsed_end.isoformat(),
        team_id=team_id,
        limit=limit,
    )
    transactions = [_normalize_transaction(transaction) for transaction in raw_transactions]

    return {
        "source": "MLB Stats API",
        "team_id": team_id,
        "start_date": parsed_start.isoformat(),
        "end_date": parsed_end.isoformat(),
        "transaction_count": len(transactions),
        "transactions": transactions,
    }
