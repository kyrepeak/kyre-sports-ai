from __future__ import annotations

import json
import math
from urllib import request

from . import task17_step5_atomic_closeout as core

TASK_ID = "wnba-pra-history-multisource-v1-step1"
WORKSTREAM = "api2-wnba-pra-history-v1-step1"
PLAN_PATH = "devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json"
SOURCE_MAIN_SHA = "42b9bcf3465af8aca41141a1d2713d5731ea6c00"
SOURCE_CANDIDATE_SHA = "a6570bfc5f8cdc4fb78f6d0ec385afd906b82791"
MAIN_SHA = "f84bf63f966a52ed3cd1d6275bedc2a0cf3b125b"
PREMERGE_PROOF_ID = "wnba-pra-history-multisource-v1-step1-a6570bfc5f8cdc4f-9bf40a36a97ceb76"
PREMERGE_DIGEST = "33776e3a7e37bc90647c686713bff88ee28122c910676304b78e4f75003f8c3b"
PREMERGE_CHECK_ID = 113049559939
MERGED_PROOF_ID = "wnba-pra-history-multisource-v1-step1-f84bf63f966a52ed-reused"
FREEZE_TOKEN = "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_FROZEN"
FREEZE_PATHS = (
    "devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json",
    "devsystem/task_ledgers/wnba-pra-history-multisource-v1-step1.json",
    "docs/superpowers/plans/2026-10-07-wnba-pra-history-multisource-step1.md",
    "sports_api/api/wnba_pra_detail_bundle.py",
    "sports_api/wnba_pra_history_multisource_v1.py",
    "tests/test_wnba_pra_history_multisource_v1_step1.py",
)
LEASE_ID = "SCOPE-LEASE-58276A81543E070B30D3D29C"
LEASE_OWNER = "api2-wnba-pra-history-v1-step1"
EXPECTED_REGISTRY_REVISION = 186
EXPECTED_REGISTRY_HASH = "21d594e5f52335bb2b5eba22a23da5e467856ee238f2730a3459c29c99f03f6f"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"
PUBLIC_URL = "https://kyre-sports-api.onrender.com/api/v1/wnba/players/1627668/pra-detail?season=2026"


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


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pra(row: dict) -> float | None:
    values = [_number(row.get("points")), _number(row.get("rebounds")), _number(row.get("assists"))]
    if any(value is None for value in values):
        return None
    return float(sum(value for value in values if value is not None))


def _public_proof() -> dict:
    req = request.Request(PUBLIC_URL, headers={"User-Agent": "Runless-WNBA-Step1-Closeout/1"})
    with request.urlopen(req, timeout=45) as response:
        if int(response.status) != 200:
            raise RuntimeError(f"WNBA_STEP1_PUBLIC_HTTP_{response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    semantics = payload.get("semantics") if isinstance(payload.get("semantics"), dict) else {}
    if semantics.get("history_source_policy") != "official_wnba_profile_plus_espn_parallel":
        raise RuntimeError("WNBA_STEP1_PUBLIC_MULTISOURCE_POLICY_MISSING")
    if str(payload.get("history_error") or "").strip():
        raise RuntimeError("WNBA_STEP1_PUBLIC_HISTORY_ERROR:" + str(payload.get("history_error")))
    history = payload.get("history") if isinstance(payload.get("history"), dict) else None
    if history is None:
        raise RuntimeError("WNBA_STEP1_PUBLIC_HISTORY_MISSING")
    verification = history.get("verification") if isinstance(history.get("verification"), dict) else {}
    if verification.get("provider_policy") != "multi_source":
        raise RuntimeError("WNBA_STEP1_PUBLIC_PROVIDER_POLICY_MISSING")

    games = history.get("games") if isinstance(history.get("games"), list) else []
    if len(games) < 5:
        raise RuntimeError("WNBA_STEP1_PUBLIC_RECENT5_MISSING")
    recent5 = [dict(row) for row in games[:5] if isinstance(row, dict)]
    recent_pras = [_pra(row) for row in recent5]
    if len(recent5) != 5 or any(value is None for value in recent_pras):
        raise RuntimeError("WNBA_STEP1_PUBLIC_RECENT_CARD_NA_PRA")
    recent5_avg = round(sum(float(value) for value in recent_pras if value is not None) / 5.0, 1)
    if recent5_avg != 38.0:
        raise RuntimeError(f"WNBA_STEP1_PUBLIC_RECENT5_DRIFT:{recent5_avg}")

    h2h = []
    for row in games:
        if not isinstance(row, dict):
            continue
        matchup = row.get("matchup") if isinstance(row.get("matchup"), dict) else {}
        if str(matchup.get("opponent_team_key") or "").casefold() == "atlanta-dream":
            h2h.append(dict(row))
    h2h = h2h[:5]
    h2h_pras = [_pra(row) for row in h2h]
    if len(h2h) < 2 or any(value is None for value in h2h_pras):
        raise RuntimeError("WNBA_STEP1_PUBLIC_H2H_CARD_NA_PRA")
    h2h_avg = round(sum(float(value) for value in h2h_pras if value is not None) / len(h2h_pras), 1)

    return {
        "status": "GREEN",
        "player_id": 1627668,
        "provider_policy": verification.get("provider_policy"),
        "credible_provider_count_available": verification.get("credible_provider_count_available"),
        "recent5_pra_values": recent_pras,
        "recent5_pra_avg": recent5_avg,
        "h2h_game_count": len(h2h),
        "h2h_pra_values": h2h_pras,
        "h2h_pra_avg": h2h_avg,
        "na_pra_cards": 0,
    }


def execute(client):
    public_evidence = _public_proof()
    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_receipt(**kwargs):
        kwargs["step"] = "wnba-pra-history-multisource-v1-step1-merged-closeout"
        evidence = list(kwargs.get("evidence_digests") or [])
        evidence.append(core._hash(public_evidence))
        kwargs["evidence_digests"] = evidence
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
        "RUNLESS_TASK17_STEP5", "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["public_proof"] = public_evidence
    result["step"] = "1/3"
    return result


def install_startup(app):
    app.state.wnba_pra_history_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_pra_history_step1_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pra_history_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "WNBA_PRA_HISTORY_MULTISOURCE_V1_STEP1_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.wnba_pra_history_step1_closeout, sort_keys=True),
            flush=True,
        )

    return app
