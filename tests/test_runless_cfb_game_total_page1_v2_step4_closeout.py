from __future__ import annotations

from runless_proof_plane import cfb_game_total_page1_v2_step4_closeout as closeout


def test_step4_closeout_binding_is_exact() -> None:
    assert closeout.TASK_ID == "cfb-game-total-page1-v2-step4-prediction-market"
    assert closeout.WORKSTREAM == "cfb-game-total-page1-v2"
    assert closeout.SOURCE_MAIN_SHA == "8ad570f765daf0884fe6f963f10982b05a414b60"
    assert closeout.SOURCE_CANDIDATE_SHA == "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
    assert closeout.MAIN_SHA == "091226472ad03d11d86fa2843fc37c3dc2830023"
    assert closeout.PREMERGE_CHECK_ID == 113165457178
    assert closeout.PREMERGE_DIGEST == "9829d7b5bcc735f42cccdf86ededcb09e6434435e8cf037f59533c4bcabc1710"
    assert closeout.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_FROZEN"
    assert closeout.LEASE_ID == "SCOPE-LEASE-68C177FAE1838F91703FC3CF"
    assert closeout.LEASE_OWNER == "cfb-game-total-page1-v2-step4-closeout"
    assert closeout.EXPECTED_REGISTRY_REVISION == 196
    assert closeout.EXPECTED_REGISTRY_HASH == "b6779f297868cae2388f18bc60bc43ae42ee181742bb5f55ff87f43d1668d8c1"
    assert closeout.EXPECTED_EVENT_HASH == "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"
    assert len(closeout.FREEZE_PATHS) == 9


def test_step4_closeout_reuses_atomic_engine() -> None:
    source = open("runless_proof_plane/cfb_game_total_page1_v2_step4_closeout.py", encoding="utf-8").read()
    assert "task17_step5_atomic_closeout as core" in source
    assert "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT" in source
    assert 'result["step"] = "4/9"' in source
