# API2 Step 2G — Dual-Main + Streamlit Convergence Gate V1

## Intent
Prevent API2 from claiming 100% GREEN + FROZEN when the approved workstream exists on only one repository branch or is not visible on the configured Streamlit production surface.

## Permanent rule
For API2 workstreams, 100% GREEN + FROZEN is illegal until all three surfaces converge:
1. `main` contains every approved artifact at the approved blob identity.
2. `api2-main` contains every approved artifact at the approved blob identity.
3. The configured Streamlit production URL passes a browser-visible marker proof for the workstream and the permanent Step 2G deployment marker.

Whole-branch equality is explicitly NOT required. `main` and `api2-main` may carry independent unrelated history; Step 2G compares only the approved artifact map for the workstream.

## Fail-closed behavior
- Missing or stale `main` artifact: RED.
- Missing or stale `api2-main` artifact: RED.
- Missing live Streamlit proof, login/auth wall, stale required marker, or forbidden runtime marker: RED.
- Missing/invalid convergence sidecar: RED.
- Without Step 2G GREEN, maximum reportable completion is 99.9%; `GREEN_FROZEN` closeout must not be issued.

## Evidence ownership
- Pre-merge Runless receipt remains the source of the approved artifact map.
- GitHub branch trees are authoritative for `main` and `api2-main` artifact identity.
- `devsystem/production_targets_v1.json` owns the Streamlit hostname.
- A Playwright certificate produces the live-render evidence.
- An API2-only convergence sidecar branch stores the immutable Step 2G evidence consumed by Runless closeout.

## Isolation
This is API2-only. It must not read, mutate, infer, or satisfy MONSTER product/control state. Non-API2 Runless workstreams keep their existing closeout behavior.

## Success
Step 2G returns GREEN only when dual-main artifact parity and Streamlit render proof are both current and bound to the same workstream, freeze token, proof digest, candidate, and merged-main identity.