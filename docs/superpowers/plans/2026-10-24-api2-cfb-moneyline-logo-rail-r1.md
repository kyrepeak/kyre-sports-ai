# API2 CFB Moneyline Logo Rail R1 — Implementation Plan

1. Lock one Step 2A path: branch `api2-cfb-moneyline-logo-rail-r1`, PR #1784, one proof sandbox, one scope lease.
2. Establish RED contract for the live Moneyline mobile rail.
3. Add `cfb_moneyline_clean_page_v8.py` as a presentation-only wrapper over V7.
4. Source team identity only through Kyre Sports API and fall back safely to monograms.
5. Activate V8 only for `cfb/moneyline` in the existing production terminal; do not edit frozen `app.py`.
6. Prove focused behavior, compile, Moneyline regressions, route-preservation tests, and source/gateway policies.
7. Classify only failures reproduced on the untouched base as inherited non-regressions.
8. Seal exact-head Runless proof with required `runless-final-gate` from App 5204253.
9. Merge only the proven exact PR head.
10. Re-run scoped proof on merged main, write finalization ledger record/manifest, execute Runless closeout to `GREEN_FROZEN`, release scope lease, and read back terminal state.
