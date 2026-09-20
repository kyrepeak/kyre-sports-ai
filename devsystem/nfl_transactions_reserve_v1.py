"""Step 3 live transaction/reserve audit."""
from __future__ import annotations

import json

import nfl_game_day_availability_v1 as game_day


def _find(rows, name):
    target = name.lower()
    for row in rows:
        if str(row.get("name") or "").lower() == target:
            return row
    return None


def main() -> int:
    audit = game_day.audit_all_32_rosters()
    if not audit.get("ready"):
        raise AssertionError(
            "32-team transaction-aware roster audit failed: "
            + json.dumps(audit, default=str, sort_keys=True)[:12000]
        )

    sf_rows, sf_diag = game_day.load_current_team_roster("SF")
    if not sf_diag.get("ok"):
        raise AssertionError(f"SF live roster unavailable: {sf_diag}")

    willis = _find(sf_rows, "Brayden Willis")
    tonges = _find(sf_rows, "Jake Tonges")

    if not willis or not willis.get("prop_eligible"):
        raise AssertionError(
            "Recent active-roster promotion missing/ineligible: "
            + json.dumps({"Brayden Willis": willis}, default=str, sort_keys=True)
        )

    if tonges and tonges.get("prop_eligible"):
        raise AssertionError(
            "IR player incorrectly remains prop-eligible: "
            + json.dumps({"Jake Tonges": tonges}, default=str, sort_keys=True)
        )

    print(json.dumps({
        "teams_verified": audit["teams_verified"],
        "teams_total": audit["teams_total"],
        "sf_http": sf_diag.get("http"),
        "brayden_willis": willis,
        "jake_tonges": tonges,
    }, indent=2, default=str, sort_keys=True))
    print("NFL_TRANSACTIONS_RESERVE_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
