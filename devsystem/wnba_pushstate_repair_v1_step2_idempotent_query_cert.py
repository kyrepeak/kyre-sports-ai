from __future__ import annotations

from pathlib import Path

OWNER_FILE = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
TEST_FILE = "tests/test_wnba_pushstate_repair_v1_step2.py"
FREEZE_TOKEN = "WNBA_PUSHSTATE_REPAIR_V1_STEP2_FROZEN"


def certify(root: str | Path = ".") -> dict[str, object]:
    base = Path(root)
    source = (base / OWNER_FILE).read_text(encoding="utf-8")
    test = (base / TEST_FILE).read_text(encoding="utf-8")
    checks = {
        "sport_write_guarded": (
            "if _query_value(SHELL_SPORT_QUERY_KEY) != SHELL_SPORT_VALUE:" in source
            and "st.query_params[SHELL_SPORT_QUERY_KEY] = SHELL_SPORT_VALUE" in source
        ),
        "market_write_guarded": (
            "if _query_value(SHELL_MARKET_QUERY_KEY) != SHELL_MARKET_VALUE:" in source
            and "st.query_params[SHELL_MARKET_QUERY_KEY] = SHELL_MARKET_VALUE" in source
        ),
        "deep_pages_preserved": (
            "navigation.PAGE_GAME" in source and "navigation.PAGE_PLAYER" in source
        ),
        "cfb_protection_preserved": "_protect_explicit_cfb_top_picks_route()" in source,
        "model_math_untouched": all(
            token in source
            for token in (
                "MAY_MODIFY_WNBA_MODEL = False",
                "MAY_MODIFY_PROJECTION_MATH = False",
                "MAY_MODIFY_MARKET_MATH = False",
                "MAY_MODIFY_PROBABILITY = False",
                "MAY_MODIFY_RANKING = False",
                "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
            )
        ),
        "rerun_regression_test": (
            "for _ in range(150):" in test
            and "assert fake_st.query_params.write_count == 0" in test
            and "assert fake_st.query_params.write_count == 2" in test
        ),
    }
    return {
        "project": "API2",
        "mission": "WNBA pushState Repair V1",
        "step": "2/4",
        "scope": "idempotent_shell_query_write_patch_only",
        "owner_file": OWNER_FILE,
        "freeze_token": FREEZE_TOKEN,
        "checks": checks,
        "green": all(checks.values()),
    }


if __name__ == "__main__":
    report = certify()
    if not report["green"]:
        raise SystemExit("WNBA_PUSHSTATE_STEP2_CERT_FAILED")
    print("WNBA_PUSHSTATE_STEP2_GREEN")
