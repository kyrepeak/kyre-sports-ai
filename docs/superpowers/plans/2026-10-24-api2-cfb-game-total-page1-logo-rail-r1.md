# API 2 CFB Game Total Page 1 Premium Logo Rail R1 — Implementation Plan

1. Preserve the merged upcoming-only CFB Game Total Page 1 baseline and all frozen model/API boundaries.
2. Add a RED contract covering V5 activation, logo/abbreviation/time-only chips, safe logo fallback, compact one-row snap CSS, and no forbidden provider/frontend fetch behavior.
3. Implement additive `cfb_game_total_page1_atier_v5.py` using V4 selection helpers, V3 selected-card rendering, and Kyre Sports API `team_identity` only.
4. Point the existing Page 1 bootstrap wrapper at V5; do not mutate Page 2 or model/projection math.
5. Repair predecessor regression tests only where they hard-pin obsolete successor activation or use an unpinned past kickoff fixture; keep all behavioral invariants intact.
6. Run focused RED→GREEN proof, Python compilation, source-policy proof, and the relevant CFB Game Total Page 1 regression suite.
7. Acquire and persist one scope-aware execution lease; bind proof artifacts to that lease.
8. Create execution plan, Runless proof plan, and task ledger.
9. Run fresh exact-head proof on the final branch head and verify PR #1783 points at that exact head.
10. Mark PR ready and merge with expected-head protection only after proof is green.
11. Re-run regression proof on merged `main`.
12. Persist `API2_CFB_GAME_TOTAL_PAGE1_LOGO_RAIL_R1_FROZEN` in the frozen registry, verify read-back, release the scope lease, and only then report GREEN + FROZEN.
