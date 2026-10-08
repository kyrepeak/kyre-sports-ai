from pathlib import Path

FINALIZER = Path("runless_proof_plane/nfl_rb_wr_step2_closeout.py").read_text(encoding="utf-8")
BOOTSTRAP = Path("runless_proof_plane/bootstrap.py").read_text(encoding="utf-8")


def test_step2_closeout_binds_exact_terminal_identity() -> None:
    for token in (
        'TASK_ID = "nfl-rb-wr-render-repair-step2-presentation-transport"',
        'CANDIDATE_SHA = "6566751edbb03cb2ff8322078ba93056fe459178"',
        'MERGED_MAIN_SHA = "02f19b7ca4400e69d1c0b193e710e67e45184769"',
        'PREMERGE_CHECK_ID = 113551121106',
        'PREMERGE_DIGEST = "d0e0a5c27aaf93c4da2076bf32b2b881f32ea458846d091b96fd048b3194b817"',
        'FREEZE_TOKEN = "NFL_RB_WR_RENDER_REPAIR_V1_STEP2_PRESENTATION_TRANSPORT_FROZEN"',
    ):
        assert token in FINALIZER


def test_step2_closeout_is_lease_triggered_and_terminal() -> None:
    assert "holder is None" in FINALIZER
    assert "NFL_RB_WR_STEP2_NO_FINALIZER_LEASE" in FINALIZER
    assert '"decision": "NFL_RB_WR_STEP2_GREEN_FROZEN"' in FINALIZER
    assert 'remaining_target_mutation_authority", -1' in FINALIZER
    assert '"github_actions_fallback": 0' in FINALIZER
    assert 'resolver_ns["resolve_completion"]' in FINALIZER


def test_bootstrap_installs_step2_closeout() -> None:
    assert "from .nfl_rb_wr_step2_closeout import install_startup as install_step2_closeout" in BOOTSTRAP
    assert "install_step2_closeout(app)" in BOOTSTRAP
