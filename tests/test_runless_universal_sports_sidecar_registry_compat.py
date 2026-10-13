import base64
import json

import pytest

from devsystem.frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    _hash,
    _payload_without_hash,
)
from runless_proof_plane.step2a import Step2AError


def _registry():
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 200,
        "source_main_sha": "1" * 40,
        "entries": {
            "FROZEN_PARENT": {
                "status": "FROZEN",
                "checkpoint_id": "FROZEN_PARENT",
                "source_main_sha": "1" * 40,
                "artifacts": {"shared.py": "a" * 40},
            }
        },
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    return payload


class FakeClient:
    def content(self, path, ref=None):
        payload = json.dumps(_registry()).encode()
        return {
            "encoding": "base64",
            "sha": "f" * 40,
            "content": base64.b64encode(payload).decode(),
        }


def test_sidecar_workstream_may_inherit_stale_legacy_registry_baseline():
    import runless_proof_plane.prove as prove

    result = prove._verify_frozen_candidate(
        FakeClient(),
        "c" * 40,
        {"shared.py": "b" * 40},
        main_sha="2" * 40,
        main_tree={"shared.py": "b" * 40},
        allow_inherited_registry_drift=True,
    )

    assert result["source_main_sha"] == "2" * 40
    assert result["inherited_frozen_paths"] == ["shared.py"]


def test_default_legacy_path_still_rejects_registry_main_identity_drift():
    import runless_proof_plane.prove as prove

    with pytest.raises(Step2AError, match="RUNLESS_REGISTRY_MAIN_IDENTITY_DRIFT"):
        prove._verify_frozen_candidate(
            FakeClient(),
            "c" * 40,
            {"shared.py": "b" * 40},
            main_sha="2" * 40,
            main_tree={"shared.py": "b" * 40},
        )


def test_sidecar_allowance_cannot_modify_unreconciled_legacy_frozen_path():
    import runless_proof_plane.prove as prove

    with pytest.raises(FrozenArtifactRegistryFailure, match="unreconciled inherited frozen state"):
        prove._verify_frozen_candidate(
            FakeClient(),
            "c" * 40,
            {"shared.py": "c" * 40},
            main_sha="2" * 40,
            main_tree={"shared.py": "b" * 40},
            allow_inherited_registry_drift=True,
        )


def test_only_universal_sports_sidecar_workstream_gets_transition_allowance():
    import runless_proof_plane.prove as prove

    assert prove._allow_inherited_registry_drift("universal-sports-source-finalization-v1") is True
    assert prove._allow_inherited_registry_drift("legacy-workstream") is False
