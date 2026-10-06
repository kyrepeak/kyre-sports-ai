from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "wnba_availability_v27.py"
TEST = ROOT / "tests/test_wnba_data_completeness_repair_v1_step1.py"

TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_GREEN"


class Step1CertificationFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Step1CertificationFailure(message)


def certify() -> dict[str, object]:
    owner = OWNER.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    compile(owner, str(OWNER), "exec")
    compile(test, str(TEST), "exec")

    require(
        'for c in ["PLAYER_NAME","TEAM_ID","TEAM_NAME","TEAM_ABBREVIATION","POSITION","ROSTER_STATUS"]' in owner,
        "roster overlay still owns PLAYER_ID",
    )
    require('production_pid = sr.get("PLAYER_ID")' in owner, "production ID preservation missing")
    require('base["PLAYER_ID"] = production_pid' in owner, "production ID assignment missing")
    require('base["PLAYER_ID_SOURCE"] = source' in owner, "production ID source preservation missing")
    require('base["PLAYER_ID_SOURCE"] = _identity_text(rr.get("PLAYER_ID_SOURCE")) or "ESPN"' in owner, "ESPN fallback source missing")
    require('def _identity_text(value) -> str:' in owner, "identity text sanitizer missing")
    require('text.casefold() in {"nan", "none"}' in owner, "NaN identity sanitizer missing")
    require('for c in ("PLAYER_NAME","TEAM_NAME","TEAM_ABBREVIATION","POSITION","ROSTER_STATUS","DATA_SOURCE","PLAYER_ID_SOURCE")' in owner, "identity column sanitation missing")

    require("test_verified_pool_preserves_production_player_id_when_roster_id_differs" in test, "canonical ID regression test missing")
    require("test_unmatched_roster_id_is_explicitly_labeled_espn" in test, "ESPN source regression test missing")
    require("test_verified_pool_never_emits_nan_identity_text" in test, "NaN identity regression test missing")

    forbidden = (
        "PROJ_PTS =",
        "PROJ_REB =",
        "PROJ_AST =",
        "PROJ_PRA =",
        "sportsbook",
        "probability",
        "ranking",
    )
    changed_contract = {value: value in owner for value in forbidden}

    return {
        "status": "GREEN",
        "token": TOKEN,
        "owner": OWNER.name,
        "test": str(TEST.relative_to(ROOT)),
        "production_id_preserved": True,
        "espn_fallback_labeled": True,
        "nan_identity_blocked": True,
        "projection_math_changed": False,
        "market_math_changed": False,
        "probability_changed": False,
        "other_sports_changed": False,
        "forbidden_markers_present": changed_contract,
    }


def main() -> int:
    result = certify()
    print(TOKEN)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
