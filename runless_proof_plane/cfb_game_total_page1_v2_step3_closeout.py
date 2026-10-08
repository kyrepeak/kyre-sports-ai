from __future__ import annotations

import json

from . import task17_step5_atomic_closeout as core

TASK_ID = "cfb-game-total-page1-v2-step3-matchup-hero-phx"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step3-matchup-hero-phx.json"
SOURCE_MAIN_SHA = "0244ed0b203ad2996cb6d79409f69ba151029008"
SOURCE_CANDIDATE_SHA = "6dc26d7e7afe84905125766c68bbd2065dedb12d"
MAIN_SHA = "8ad570f765daf0884fe6f963f10982b05a414b60"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step3-matchup-hero-phx-6dc26d7e7afe8490-0037dc81ac5111cb"
PREMERGE_DIGEST = "00dfc3bbe3c4b51330a725ea193fc348408047091eaaa2ddc2cd3a8a146d67fd"
PREMERGE_CHECK_ID = 113150132499
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step3-matchup-hero-phx-8ad570f765daf088-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP3_MATCHUP_HERO_PHX_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_step3_presentation_v1.py",
    "cfb_game_total_clean_page_v36.py",
    "cfb_game_total_page1_v2_step3_activation.py",
    "kyre_universal_shell_runtime_v1.py",
    "tests/test_cfb_game_total_page1_v2_step3_matchup_hero_phx.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step3-matchup-hero-phx.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step3-matchup-hero-phx.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step3-matchup-hero-phx.json",
    "docs/superpowers/plans/2026-10-07-cfb-game-total-page1-v2-step3-matchup-hero-phx.md",
)
LEASE_ID = "SCOPE-LEASE-1B99AF86A095301C9EE9FDDB"
LEASE_OWNER = "cfb-game-total-page1-v2-step3"
EXPECTED_REGISTRY_REVISION = 195
EXPECTED_REGISTRY_HASH = "b204d0f26807f4a2087c449f4888b48fd5d261ce6e237114cfe6d08733f9b86b"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"


def _bindings() -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "WORKSTREAM": WORKSTREAM,
        "PLAN_PATH": PLAN_PATH,
        "SOURCE_MAIN_SHA": SOURCE_MAIN_SHA,
        "SOURCE_CANDIDATE_SHA": SOURCE_CANDIDATE_SHA,
        "MAIN_SHA": MAIN_SHA,
        "PREMERGE_PROOF_ID": PREMERGE_PROOF_ID,
        "PREMERGE_DIGEST": PREMERGE_DIGEST,
        "PREMERGE_CHECK_ID": PREMERGE_CHECK_ID,
        "MERGED_PROOF_ID": MERGED_PROOF_ID,
        "FREEZE_TOKEN": FREEZE_TOKEN,
        "FREEZE_PATHS": FREEZE_PATHS,
        "LEASE_ID": LEASE_ID,
        "LEASE_OWNER": LEASE_OWNER,
        "EXPECTED_REGISTRY_REVISION": EXPECTED_REGISTRY_REVISION,
        "EXPECTED_REGISTRY_HASH": EXPECTED_REGISTRY_HASH,
        "EXPECTED_EVENT_HASH": EXPECTED_EVENT_HASH,
    }


def execute(client):
    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_receipt(**kwargs):
        kwargs["step"] = "cfb-game-total-page1-v2-step3-matchup-hero-phx"
        return original_build_receipt(**kwargs)

    try:
        for name, value in _bindings().items():
            setattr(core, name, value)
        core.build_runless_receipt = _build_receipt
        result = dict(core.execute(client))
    finally:
        core.build_runless_receipt = original_build_receipt
        for name, value in saved.items():
            setattr(core, name, value)

    decision = str(result.get("decision") or "")
    result["decision"] = decision.replace(
        "RUNLESS_TASK17_STEP5", "CFB_GAME_TOTAL_PAGE1_V2_STEP3"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "3/9"
    return result


def install_startup(app):
    app.state.cfb_game_total_page1_v2_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step3_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP3_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_page1_v2_step3_closeout, sort_keys=True),
            flush=True,
        )

    return app
