# MONSTER Coding Intelligence V1 — Design Spec

## Purpose

Build a standalone intelligence subsystem that makes MONSTER / API 2 materially better at understanding engineering problems, diagnosing root causes, choosing decisive tests, selecting safer fixes, predicting blast radius, challenging its own conclusions, verifying outcomes, and reusing lessons from prior failures.

The objective is not to make MONSTER merely "think longer." The objective is to create structured reasoning that reduces wrong paths, unnecessary patches, unnecessary runs, regressions, false proof, and repeated rediscovery of solved failure patterns.

This subsystem must be designed, implemented, tested, and certified independently before any production integration with the existing control plane.

## Architectural Boundary

The target long-term system has three layers:

1. Intelligence Layer
   - decides WHAT is wrong,
   - WHY it is wrong,
   - WHAT evidence supports competing explanations,
   - WHAT should be tested next,
   - WHAT solution is safest,
   - WHAT confidence is justified.

2. Control Plane
   - decides HOW work is executed and finalized,
   - includes Step 2A, Runless Final-Mile, Finalization Authority / 100% Convergence V1, Parallel Workstream Isolation, anti-loop protection, leases, proof gates, frozen registry, Universal Live Status Board V1, and existing multi-source control rules.

3. Execution Layer
   - performs GitHub edits, code changes, tests, deployments, API integrations, runtime checks, provider calls, UI verification, and other execution work.

MONSTER Coding Intelligence V1 belongs only to Layer 1 during this project.

### Hard separation rule

Until Step 10 certification is complete:

- do not wire intelligence decisions into production control-plane authority,
- do not replace or redesign Step 2A,
- do not replace Runless,
- do not replace Finalization Authority,
- do not replace Parallel Workstream Isolation,
- do not replace Universal Sports Multi-Source Architecture V1,
- do not create a second lease, proof, deployment, or finalization system,
- do not allow the Intelligence Layer to mutate GitHub, runtime, deployment, provider, or production state directly.

The Intelligence Layer may consume structured evidence and emit structured decision artifacts. Mutation remains outside its authority.

## Design Principles

### 1. Structured reasoning over free-form rumination

The Intelligence Layer must emit explicit artifacts instead of giant unbounded reasoning dumps. Important claims must be represented as typed fields such as evidence status, hypothesis confidence, predicted observations, falsifiers, selected test, risk, and outcome.

### 2. Evidence discipline

Facts, assumptions, unknowns, and contradictions must remain distinguishable. The system must never silently upgrade an inference into a fact.

### 3. Competing hypotheses before invasive action

For non-trivial failures, the system must consider multiple plausible causes before selecting an invasive repair path.

### 4. Uncertainty should shrink

Each selected investigation step should reduce uncertainty. Repeating actions that do not discriminate between hypotheses is a failure of strategy.

### 5. Root cause over symptom masking

A proposed fix must explain the causal chain from root cause to observed symptom. A patch that only hides the symptom must not be treated as a root-cause repair.

### 6. Cheap decisive tests first

Prefer read-only, reversible, low-cost tests that strongly distinguish competing hypotheses before code changes, deployments, or provider swaps.

### 7. Blast radius before patch

Before recommending a repair, the system must identify shared components, downstream consumers, cross-page and cross-sport impact, provider coupling, identity coupling, and regression risk.

### 8. Confidence controls behavior

Confidence is explicit: HIGH, MEDIUM, or LOW. LOW confidence requires more evidence before invasive action.

### 9. Outcome beats implementation state

A merge, passing unit test, or successful deployment is not sufficient proof that the original user-visible problem disappeared.

### 10. Lessons change priors, not truth

Prior incidents may raise or lower hypothesis priors. They must never override fresh contradictory evidence.

## Standalone Data Flow

```text
User Goal / Failure
        ↓
Problem Understanding
        ↓
Problem Classification
        ↓
Evidence Ledger
        ↓
Hypothesis Generation
        ↓
Hypothesis Ranking
        ↓
Cheapest Decisive Test
        ↓
Contradiction Resolution
        ↓
Root Cause Certification
        ↓
Blast Radius + Strategy Selection
        ↓
Counterfactual + Adversarial Review
        ↓
Outcome Verification
        ↓
Lesson Registry
```

During V1 development, the flow ends in a structured recommendation / certification packet. It does not directly execute mutations.

## Core Decision Artifact

The canonical output is a structured `IntelligenceDecisionPacket` with fields equivalent to:

- `case_id`
- `goal`
- `problem_class_primary`
- `problem_class_secondary`
- `known_evidence`
- `inferred_evidence`
- `unknown_evidence`
- `contradicted_evidence`
- `hypotheses`
- `ranked_hypotheses`
- `selected_decisive_test`
- `root_cause`
- `root_cause_confidence`
- `predicted_blast_radius`
- `recommended_strategy`
- `adversarial_findings`
- `outcome_status`
- `lesson_candidates`

The exact serialization may be Python dataclasses, TypedDicts, Pydantic models, or another existing project-compatible mechanism chosen during implementation planning. The design contract is semantic, not library-specific.

# Ten-Step Program

## Step 1 — Intelligence Case Contract V1

### Goal

Create the normalized input contract used by every intelligence investigation.

### Required fields

Every case must capture:

- user goal,
- visible symptom,
- success condition,
- constraints,
- do-not-change rules,
- affected system / page / component,
- environment when known,
- current known state,
- suspected subsystems when available,
- explicit definition of what counts as solved.

### Semantic rules

- A visible symptom is not automatically a root cause.
- A success condition must describe an observable outcome, not merely an implementation action.
- Do-not-change rules are hard constraints unless explicitly superseded by the user.
- Unknown fields remain unknown; they must not be guessed into certainty.
- The contract must be deterministic enough that materially equivalent problem statements normalize to materially equivalent cases.
- The contract must be side-effect free.

### Example

```text
GOAL:
CFB cards appear normally.

SYMPTOM:
Expected games/cards are absent.

SUCCESS:
Expected slate appears with verified underlying data and no false completeness.

DO NOT CHANGE:
Visual design.
Navigation.
Existing multi-source architecture.

POSSIBLE SYSTEMS:
schedule
identity
normalization
rendering
deployment
freshness
```

### Step 1 acceptance criteria

1. Equivalent descriptions of the same issue normalize to the same core case fields.
2. Missing information remains explicitly unknown.
3. User constraints and do-not-change rules survive normalization.
4. Success conditions are observable and testable.
5. Symptoms remain separate from causal diagnosis.
6. The contract grants no mutation authority.
7. Invalid or internally contradictory case definitions fail closed or surface explicit validation errors.
8. Serialization and rendering are deterministic for identical normalized input.

### Step 1 frozen artifact

`INTELLIGENCE CASE CONTRACT V1`

## Step 2 — Evidence Ledger + Failure Classifier V1

### Goal

Represent what is known and classify the problem so later strategy can be problem-specific.

### Failure classes

The classifier may assign one primary class and zero or more secondary classes from:

- UI
- DATA
- PROVIDER
- IDENTITY
- NORMALIZATION
- ROUTING
- STATE
- CI
- DEPLOYMENT
- INFRASTRUCTURE
- CODE
- REGRESSION
- PROOF
- STALE_STATE
- SOURCE_DISCREPANCY
- PERFORMANCE
- CONFIGURATION
- UNKNOWN

### Evidence states

Every important evidence item is one of:

- KNOWN
- INFERRED
- UNKNOWN
- CONTRADICTED

Evidence should preserve provenance where relevant:

- source,
- timestamp,
- SHA,
- branch,
- environment,
- deployment,
- provider,
- scope,
- freshness,
- authority.

### Step 2 acceptance criteria

The engine must preserve uncertainty, support multi-class problems, and refuse to silently convert inference into fact.

### Step 2 frozen artifact

`EVIDENCE LEDGER + CLASSIFIER V1`

## Step 3 — Multi-Hypothesis Engine V1

### Goal

Prevent premature commitment to the first plausible explanation.

For non-trivial failures, generate multiple plausible causal hypotheses when the evidence supports them.

Each hypothesis tracks:

- description,
- supporting evidence,
- contradicting evidence,
- confidence,
- predicted observations,
- falsifying evidence,
- affected subsystem.

Artificial filler hypotheses are prohibited. Breadth must remain plausible and evidence-linked.

### Step 3 acceptance criteria

Historical cases where the obvious first guess was wrong must retain viable alternatives long enough for evidence to separate them.

### Step 3 frozen artifact

`MULTI-HYPOTHESIS ENGINE V1`

## Step 4 — Decisive Test + Dynamic Strategy Engine V1

### Goal

Choose the next investigation that most efficiently reduces uncertainty.

Hypotheses should be ranked using factors such as:

- evidence strength,
- prior likelihood,
- discriminatory value of available test,
- verification cost,
- reversibility,
- operational risk,
- expected impact.

The selected test should normally maximize information gain while minimizing mutation and cost.

### Problem-specific strategy examples

- CI → failing job → failing command → dependency / environment → code
- DEPLOYMENT → expected SHA → deployed SHA → environment → runtime
- IDENTITY → canonical ID → provider aliases → normalization
- SPORTS DATA → source ownership → provider health → normalization → consensus
- UI → data presence → state → rendering → layout
- ROUTING → route → query / state → navigation target → render

### Step 4 acceptance criteria

Historical replay must show fewer unnecessary mutations or runs than blind patch-and-rerun behavior.

### Step 4 frozen artifact

`DECISIVE TEST + STRATEGY ENGINE V1`

## Step 5 — Contradiction Resolution Engine V1

### Goal

Resolve conflicting evidence by provenance instead of convenience.

Resolution compares, where applicable:

1. exact SHA,
2. environment,
3. branch,
4. timestamp,
5. source authority,
6. freshness,
7. identity normalization,
8. scope,
9. provenance,
10. deployment lineage.

If evidence cannot be reconciled, the correct state is:

```text
CONTRADICTION_UNRESOLVED
confidence decreases
more evidence required
```

### Step 5 acceptance criteria

Intentionally conflicting evidence must either resolve to the authoritative observation for an explainable reason or remain explicitly unresolved.

### Step 5 frozen artifact

`CONTRADICTION RESOLUTION V1`

## Step 6 — Root Cause Certification Engine V1

### Goal

Require a causal chain before declaring the root cause.

Example:

```text
player cards missing
→ render verification failed
→ selector searched wrong frame
→ content existed in nested frame
→ root cause: verification scope did not match rendering scope
```

Root-cause confidence is HIGH, MEDIUM, or LOW.

LOW confidence blocks invasive repair recommendation and returns the case to evidence/test selection.

### Step 6 acceptance criteria

Certified root causes must predict additional observations beyond the original symptom and survive falsification checks.

### Step 6 frozen artifact

`ROOT CAUSE CERTIFICATION ENGINE V1`

## Step 7 — Blast Radius + Solution Intelligence V1

### Goal

Recommend the safest causal repair, not merely the smallest diff.

Candidate strategies should be compared across:

- causal fit,
- files affected,
- services affected,
- pages affected,
- sports affected,
- provider coupling,
- canonical ID coupling,
- route / state ownership,
- shared components,
- downstream consumers,
- reversibility,
- regression potential.

### Step 7 acceptance criteria

Known shared-component and cross-page scenarios must surface realistic collateral risk before a repair is recommended.

### Step 7 frozen artifact

`BLAST RADIUS + SOLUTION INTELLIGENCE V1`

## Step 8 — Counterfactual + Adversarial Review Engine V1

### Goal

Challenge conclusions at decision boundaries without turning intelligence into endless deliberation.

Required review questions include:

- If this diagnosis is correct, what else should be observable?
- What evidence would prove it wrong?
- Did the proposed repair fix the cause or mask the symptom?
- What assumption carries the conclusion?
- Can another explanation still fit the evidence?
- Could the strategy break another consumer?
- Does the planned proof actually test the original user claim?

### Decision boundaries

Adversarial review is required:

- before root-cause certification,
- before an invasive solution recommendation,
- before final success certification.

It is not required after every trivial internal operation.

### Step 8 acceptance criteria

Seeded attractive-but-wrong diagnoses must be rejected or downgraded when falsifying evidence exists.

### Step 8 frozen artifact

`ADVERSARIAL REVIEW ENGINE V1`

## Step 9 — Outcome Learning + Lesson Registry V1

### Goal

Verify whether the original problem actually disappeared and preserve reusable lessons.

### Outcome states

At minimum:

- SOLVED
- NOT_SOLVED
- PARTIALLY_SOLVED
- REGRESSED
- UNVERIFIED

If a repair fails:

- reduce confidence in the hypothesis that justified it,
- classify the failed attempt,
- add the new evidence,
- re-rank remaining hypotheses,
- prohibit blind repetition of the same strategy without new evidence.

### Lesson record

Each solved hard incident should capture:

- symptom signature,
- root cause,
- repair class,
- proof that established resolution,
- future detection clue,
- relevant scope / context,
- confidence.

Initial historical lesson families should include:

- stale deployment,
- frame / selector mismatch,
- provider ID mismatch,
- timezone failure,
- CI dependency failure,
- provider outage,
- normalization mismatch,
- route / state ownership,
- proof loops,
- 97–99.9% convergence stalls.

Lessons change priors only. Fresh evidence always retains authority.

### Step 9 acceptance criteria

Historical lessons should improve initial ranking on matching cases without causing incorrect certainty on superficially similar but causally different failures.

### Step 9 frozen artifact

`OUTCOME LEARNING + LESSON REGISTRY V1`

## Step 10 — Intelligence Benchmark + Certification V1

### Goal

Prove MONSTER Coding Intelligence V1 is genuinely smarter before integration.

### Benchmark corpus

Use at least 8–12 historical API 2 / MONSTER incidents spanning:

- provider ID mismatch,
- stale deployment,
- frame / selector mismatch,
- timezone TypeError,
- missing CI dependency,
- sports-source outage,
- normalization filtering valid data,
- route / state failure,
- false proof,
- final-mile stall,
- genuine UI defect,
- conflicting provider evidence.

### Metrics

Track at minimum:

- root-cause hit rate,
- first-strategy quality,
- unnecessary patch count,
- unnecessary run count,
- false-certification rate,
- regression-risk detection,
- contradiction-resolution accuracy,
- lesson reuse quality,
- diagnostic convergence.

The system must not be certified because it produced more reasoning text. Certification requires measurable improvement in diagnostic quality and/or reduced wasted execution while preserving correctness.

### Step 10 terminal artifact

`MONSTER CODING INTELLIGENCE V1 — GREEN + FROZEN`

Only after this state exists may a separate integration design be created for Intelligence → Control Plane handoff.

# Interaction With Existing Universal Sports Multi-Source Architecture V1

MONSTER Coding Intelligence V1 must consume the existing sports architecture rather than recreate it.

For sports-data failures, intelligence may reason about:

- category-specific source ownership,
- primary / secondary / tertiary fallback,
- provider health,
- multi-source consensus,
- canonical `KYRE_TEAM_ID`,
- canonical `KYRE_PLAYER_ID`,
- canonical `KYRE_GAME_ID`,
- provider aliases,
- normalization,
- source freshness,
- Phoenix-time handling where configured,
- false completeness risk.

It must not introduce a new universal master provider or silently collapse the architecture to ESPN-only or any other single source.

# Interaction With Parallel Workstream Isolation

The Intelligence Layer may share architecture, standards, and lesson schemas across MONSTER / API 2 workstreams.

It must not share live execution state across workstreams.

The following remain workstream-local:

- active step,
- branch,
- PR,
- SHA,
- run,
- deployment,
- lease,
- blocker,
- proof,
- GREEN / FROZEN state,
- file ownership,
- finalization state.

Intelligence artifacts must therefore carry a workstream or case identifier so evidence cannot be accidentally imported across active lanes.

# Error Handling

The subsystem must fail closed on:

- malformed case definitions,
- impossible confidence values,
- evidence with invalid state,
- hypotheses without identifiers,
- unresolved contradictions presented as resolved facts,
- missing success conditions for terminal certification,
- outcome claims without proof references,
- cross-case evidence contamination.

Unknown must remain a valid state. The engine is permitted to say "insufficient evidence" rather than manufacture certainty.

# Testing Strategy

Each step receives independent unit and replay tests before the next step begins.

Testing categories:

1. Contract tests
   - schema validity,
   - deterministic normalization,
   - invalid-state rejection.

2. Historical replay tests
   - known API 2 / MONSTER incidents,
   - expected root-cause family,
   - expected decisive test behavior.

3. Adversarial tests
   - misleading evidence,
   - stale evidence,
   - wrong SHA,
   - wrong environment,
   - attractive but false diagnosis.

4. Regression tests
   - adding new intelligence logic must not alter frozen prior-step behavior without explicit version change.

5. Isolation tests
   - no mutation authority,
   - no cross-workstream execution-state leakage,
   - no implicit provider-master behavior.

# Step 1 Implementation Boundary

When implementation planning is approved, Step 1 should remain intentionally small.

It should provide only:

1. the Intelligence Case data contract,
2. deterministic normalization,
3. validation,
4. deterministic rendering / serialization,
5. tests proving the Step 1 acceptance criteria.

Step 1 must not implement:

- evidence ranking,
- hypothesis generation,
- root-cause inference,
- GitHub mutation,
- deployments,
- provider calls,
- control-plane hooks,
- lesson learning.

This prevents the first implementation step from quietly becoming the entire intelligence system.

# Step 1 Proposed Freeze Conditions

Step 1 may be declared GREEN + FROZEN only when:

1. the approved implementation plan is followed,
2. its test suite passes,
3. deterministic equivalent-case normalization is proven,
4. unknowns remain explicit,
5. constraints and do-not-change rules survive normalization,
6. observable success conditions are preserved,
7. mutation authority is absent,
8. exact-head proof succeeds under the existing control plane,
9. merge/finalization follows the existing Runless / Finalization Authority rules,
10. the frozen registry records the Step 1 artifact without altering unrelated workstreams.

# Non-Goals for V1

V1 does not attempt to:

- replace the language model,
- expose hidden chain-of-thought,
- autonomously mutate production from reasoning output,
- redesign all existing DevSystem architecture,
- create a new orchestration framework,
- create a new source-ownership system,
- create a new parallel-workstream authority model,
- optimize arbitrary product UX,
- solve every class of software engineering problem in one step.

The purpose is to make diagnosis and engineering decisions more reliable through explicit structure and measurable feedback.

# Final Integration Gate

The integration phase is a separate architectural task.

No Intelligence → Control Plane production adapter may be designed for merge until MONSTER Coding Intelligence V1 completes Step 10 certification and is GREEN + FROZEN as a standalone subsystem.
