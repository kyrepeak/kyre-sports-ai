#!/usr/bin/env bash
set -euo pipefail

registry_ref="monster-frozen-artifact-registry"
registry_path="devsystem/frozen_artifact_registry_state_v1.json"
initial_registry="/tmp/monster-frozen-artifact-registry.json"
resume_registry="/tmp/monster-frozen-artifact-registry-resume.json"
gate_json="/tmp/registry-race-gate.json"
resume_json="/tmp/registry-race-resume.json"

git fetch origin main --depth=256
current_main_sha="$(git rev-parse origin/main)"

git fetch origin "$registry_ref" --depth=1
git show FETCH_HEAD:"$registry_path" > "$initial_registry"

set +e
python devsystem/registry_wait_resume_v1.py evaluate-git-head   --registry-file "$initial_registry"   --candidate-head HEAD   --current-main-sha "$current_main_sha"   --json-out "$gate_json"
gate_rc=$?
set -e

gate_status="$(python - <<'PY'
import json
print(json.load(open("/tmp/registry-race-gate.json"))["status"])
PY
)"
gate_decision="$(python - <<'PY'
import json
print(json.load(open("/tmp/registry-race-gate.json"))["decision"])
PY
)"

echo "REGISTRY_RACE_GATE_STATUS=$gate_status"
echo "REGISTRY_RACE_GATE_DECISION=$gate_decision"

if [ "$gate_rc" -eq 0 ]; then
  python devsystem/frozen_artifact_registry_v1.py verify-head     --registry-file "$initial_registry"     --head HEAD
  echo "REGISTRY_RACE_V1_AUTHORITATIVE_REGISTRY_GREEN"
  exit 0
fi

if [ "$gate_rc" -ne 3 ]; then
  echo "REGISTRY_RACE_V1_AUTHORITY_BLOCKED"
  exit 1
fi

initial_hash="$(python - <<'PY'
import json
print(json.load(open("/tmp/registry-race-gate.json"))["registry_state_hash"])
PY
)"

echo "REGISTRY_RACE_V1_WAIT_REGISTRY_RECONCILIATION"
echo "REGISTRY_RACE_V1_WAIT_STATE_HASH=$initial_hash"
echo "REGISTRY_RACE_V1_WAIT_POLICY=STATE_ONLY_NO_PROOF_RERUN"

deadline=$((SECONDS + 180))
observed_hash="$initial_hash"

while [ "$SECONDS" -lt "$deadline" ]
do
  sleep 10
  git fetch origin "$registry_ref" --depth=1
  git show FETCH_HEAD:"$registry_path" > "$resume_registry"
  observed_hash="$(python - <<'PY'
import json
print(json.load(open("/tmp/monster-frozen-artifact-registry-resume.json"))["state_hash"])
PY
)"
  if [ "$observed_hash" != "$initial_hash" ]; then
    echo "REGISTRY_RACE_V1_STATE_CHANGE_DETECTED=$observed_hash"
    break
  fi
done

if [ "$observed_hash" = "$initial_hash" ]; then
  echo "REGISTRY_RACE_V1_WAIT_TIMEOUT_BLOCKED"
  exit 1
fi

set +e
python devsystem/registry_wait_resume_v1.py resume-git-head   --previous-wait-file "$gate_json"   --registry-file "$resume_registry"   --candidate-head HEAD   --current-main-sha "$current_main_sha"   --json-out "$resume_json"
resume_rc=$?
set -e

resume_status="$(python - <<'PY'
import json
print(json.load(open("/tmp/registry-race-resume.json"))["status"])
PY
)"
resume_decision="$(python - <<'PY'
import json
print(json.load(open("/tmp/registry-race-resume.json"))["decision"])
PY
)"

echo "REGISTRY_RACE_V1_RESUME_STATUS=$resume_status"
echo "REGISTRY_RACE_V1_RESUME_DECISION=$resume_decision"

if [ "$resume_rc" -ne 0 ]; then
  echo "REGISTRY_RACE_V1_ONE_RESUME_BLOCKED"
  exit 1
fi

python devsystem/frozen_artifact_registry_v1.py verify-head   --registry-file "$resume_registry"   --head HEAD

echo "REGISTRY_RACE_V1_RESUMED_ONCE_GREEN"
