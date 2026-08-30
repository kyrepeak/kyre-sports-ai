# WNBA Step 20A — End-to-End Graduation Certification

Date: 2026-08-30

## Parent freeze

Step 20A branches from the certified Step 19 production freeze:

- Certified Step 19 freeze SHA: `733155d93e1e1657f56fb3d1aac9694d2c54c945`
- Production-certified Step 19 code SHA: `aaf8b8a5425ea6e1b0ab33e6c42f35c95e8905ab`
- Step 19 production certification run: `33290456020`
- Step 19 freeze certification run: `33291168000`

No production code is changed by Step 20A. This step is a read-only graduation certification.

## Graduation gates

Step 20A has two independent gates.

### Gate A — deterministic full-chain proof

The frozen production contracts must prove the complete path through:

1. official WNBA first-party inputs and strict identity,
2. Step 8 projection handoff/core/context,
3. Step 8 joint Monte Carlo,
4. Step 9 threshold pricing and sportsbook comparison,
5. exact-line multibook consensus,
6. qualification and probability ranking,
7. Step 10 live-market assembly,
8. Step 11 controlled multibook shadow board,
9. Step 12 live runtime and board contracts,
10. Step 18 read-only Streamlit consumer contract,
11. Step 19 production compatibility and safety repairs.

### Gate B — genuine current-live witness

A full live graduation is earned only when the current production runtime exposes a genuine board built from current DraftKings and FanDuel markets. A quiet, empty, suspended, or different-line market is safe but does not count as a full live graduation witness.

The live witness requires:

- DraftKings ready and nonempty,
- FanDuel transport valid and identity errors zero,
- latest hosted provider trace has nonempty DraftKings and FanDuel records,
- scheduler cycle completes without failures,
- consumer circuit is closed with zero consecutive failures,
- cycle outcome is `shadow_board_ready`,
- Step 18 consumer reports an available board,
- qualified props are positive,
- at least one primary top card is present,
- every exposed top card reports a converged model with exactly 5,000,000 simulations.

`market_board_not_ready` is accepted as a safe state but is explicitly **not** a Step 20A live graduation pass.

## Frozen invariants

- Step 8 certified Monte Carlo count remains **5,000,000 simulations per built target**.
- Step 8 certified batch size remains **250,000**.
- Exact same-line DraftKings/FanDuel matching remains mandatory.
- Different sportsbook lines are never blended.
- No fake market overlap, fake projection, fake player identity, or fake board may be created.
- Real provider transport/identity failures remain fail-closed.
- Normal moving/empty market states may resolve only to the certified closed-circuit market-not-ready behavior.
- SportsGameOdds is not used and must not be reintroduced.
- Wagering remains disabled.
- General persistence and Supabase writes remain disabled during certification.
- Step 18 consumer reads already-computed scheduler output; it does not trigger sportsbook calls, scheduler cycles, or Monte Carlo work.

## Completion rule

Step 20A is complete only when **both** Gate A and Gate B pass. If Gate A passes while the current live market remains unavailable, Step 20A remains pending rather than relaxing exact-line or readiness requirements.
