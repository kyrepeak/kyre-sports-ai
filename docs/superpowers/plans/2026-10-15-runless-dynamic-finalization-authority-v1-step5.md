# Runless Dynamic Finalization Authority V1 — Step 5

## Automatic Merge + Freeze Convergence

Step 5 adds only the orchestration boundary required by the approved design. It does not redesign Runless, create a second finalizer, or mutate the protected NBA lane.

The convergence controller accepts one already-authorized exact candidate and delegates each mutation to its existing owner:

1. require durable `MERGE_AUTHORIZED` identity for the exact proof/workstream/candidate/digest;
2. invoke the existing exact-candidate merge authority once;
3. independently read `main` and require the exact returned merged-main SHA;
4. invoke the existing certified finalization/frozen-ledger authority once;
5. invoke the existing durable Runless terminal completion latch;
6. independently read canonical Runless state and require `GREEN_FROZEN`;
7. if canonical state is already `GREEN_FROZEN`, return it without merge/freeze mutation.

The controller deliberately receives merge and certified-finalization transports as injected authorities. It therefore cannot become a second merge/freeze implementation and remains deterministic/testable without network mutation.

Freeze token: `RUNLESS_DYNAMIC_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN`.
