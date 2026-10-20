# NBA Spread Page 1 — S-Tier Analytics V2 Execution Plan

1. Enforce Step 2A: one branch, one PR, one candidate head, one proof path, no competing NBA Spread workstream.
2. Prove RED with a focused successor contract before implementation.
3. Add SportsGameOdds V3 with expanded major-book requests and real provider open/close fields while preserving exact schedule identity, paired-spread validation and freshness.
4. Add Odds-API.io as verified exact-game sportsbook gap-fill; never overwrite a primary same-book quote.
5. Add live repair V3 source chain: SportsGameOdds -> Odds-API.io -> ESPN credentialless fallback.
6. Add decision-board data V2 for per-book rows, median consensus, best available spread/price and actual open-to-current movement.
7. Add Page V9 with decision-first visual hierarchy and a single Page 2 CTA. Do not modify Page 2.
8. Bind NBA Spread through the workstream-unique `universal_runtime_v5_loader_nba_spread_stier_v2.py`. Do not write a shared numbered runtime-loader file owned by another live workstream. Dynamically delegate non-NBA-spread routes to V25 if it exists, otherwise V24.
9. If a live scope lease reveals a parallel write-path collision, declare `PARALLEL CONFLICT DETECTED`, invalidate the stale candidate before proof, repair the path ownership on the same branch/PR, and prove RED→GREEN for the isolation repair. Never mutate the competing lane.
10. Verify focused contract, frozen NBA regressions, Page 1/2 handoff, universal navigation and Universal Runtime V5 certification in one isolated preflight environment.
11. Acquire one real, live, non-overlapping NBA workstream scope lease through the authoritative scope-lease mechanism. No placeholder lease IDs.
12. Re-read protected main and the frozen-artifact registry. If main moved, reconcile before candidate locking. If a candidate-authored frozen delta exists, obtain exactly one authorized exact-head thaw before proof.
13. Lock the exact candidate only after the durable design/plan/ledger/proof plan, lease identity and any required thaw all match that head.
14. Reuse PR #1673. Submit exactly one authoritative Runless V2 proof request for that exact candidate head. Do not certify stale head and do not create a second PR.
15. Merge only after exact-head `runless-final-gate` succeeds from GitHub App 5204253 and immutable receipt read-back matches.
16. Verify merged main, production/finalization authority and frozen-registry read-back. Forward-port/retire any thaw and release the scope lease only after canonical Runless state reads GREEN_FROZEN.

## Failure policy
Classify the authoritative failure first. Patch only the root cause on the same branch, refresh the same preflight environment if needed, and invalidate stale proof/candidate identity after any branch mutation. No duplicate PR, deployment, proof request, lease, sandbox retry or blind polling loop.