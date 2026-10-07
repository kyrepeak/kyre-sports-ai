import base64
import json

import pytest

from devsystem.frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    _hash,
    _payload_without_hash,
)


def _registry():
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 157,
        "source_main_sha": "b" * 40,
        "entries": {
            "FROZEN_PARENT": {
                "status": "FROZEN",
                "checkpoint_id": "FROZEN_PARENT",
                "source_main_sha": "1" * 40,
                "artifacts": {"shared.py": "1" * 40},
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


def test_candidate_inherits_authoritative_main_frozen_state_without_being_blame_owner():
    import runless_proof_plane.prove as prove

    result = prove._verify_frozen_candidate(
        FakeClient(),
        "a" * 40,
        {"shared.py": "2" * 40},
        main_sha="b" * 40,
        main_tree={"shared.py": "2" * 40},
    )

    assert result["revision"] == 157
    assert result["inherited_frozen_paths"] == ["shared.py"]


def test_candidate_cannot_modify_unreconciled_inherited_frozen_state():
    import runless_proof_plane.prove as prove

    with pytest.raises(FrozenArtifactRegistryFailure, match="unreconciled inherited frozen state"):
        prove._verify_frozen_candidate(
            FakeClient(),
            "a" * 40,
            {"shared.py": "3" * 40},
            main_sha="b" * 40,
            main_tree={"shared.py": "2" * 40},
        )
