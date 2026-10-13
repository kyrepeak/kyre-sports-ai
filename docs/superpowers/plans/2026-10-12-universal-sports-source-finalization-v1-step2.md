# Universal Sports Source + Finalization V1 — Step 2 Plan

## Mission

Implement Step 2/8, **Credible Provider Registry**, for workstream `universal-sports-source-finalization-v1` without reopening frozen Step 1 or any sports product page.

## Step 2A Authority

- Source main: `6a1e4b739cf500ff42765016950a5dce13d2c81c`
- Authoritative branch: `api2-universal-sports-source-finalization-v1-step2-provider-registry`
- Authoritative PR: `#1527`
- One branch, one PR, one Runless proof path
- GitHub Actions fallback: `0`
- Render dependency: `false`

## Scope

Step 2 is metadata/control-plane only. It creates a capability-scoped approved provider pool that later Step 3 routing may consume.

The registry must:

1. keep `DATA_FIELD` as the routing unit;
2. forbid page-wide provider authority;
3. keep the approved pool distinct from active providers;
4. define explicit sport scopes and exact capability declarations;
5. represent schedule, identity, rosters, injuries, official stats, advanced stats, history, sportsbook lines, line movement, public bet count, public bet percentage, money percentage, and news/context;
6. keep incompatible betting metrics semantically distinct;
7. never claim credentials, configuration, or live reachability that were not proven;
8. permit official, licensed, reference, editorial, specialty, betting-market, and direct-feed sources in one registry without making any one source universal;
9. perform zero network calls and grant zero product/runtime mutation authority;
10. leave the legacy frozen registry and Step 1 frozen artifacts untouched.

## TDD

RED was established first at commit `5e99ab10f9014d5666e675562559e2d8b25fe23b` because `devsystem.universal_sports_provider_registry_v1` did not exist.

GREEN requires the focused Step-2 test file to pass on the exact final candidate and `py_compile` to pass for the validator module.

## Proof Contract

The exact final candidate must receive the protected `runless-final-gate` from GitHub App `5204253`. No GitHub Actions fallback is authorized. No public/product probe is required because Step 2 changes no runtime product path.

After exact-head proof succeeds, merge only that exact candidate. Then immediately append/finalize the Step-2 checkpoint through the provider-independent finalization ledger introduced by Step 1, independently read it back from GitHub, and certify only if the exact token/revision/hash/record blob match.

## Freeze Token

`UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP2_CREDIBLE_PROVIDER_REGISTRY_FROZEN`
