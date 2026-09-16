# CFB Game Total V152 — Production Rebuild Design

Date: 2026-09-16
Branch: `fix/cfb-game-total-v152-production-rebuild`
Base: `main@8bb4088b2b590e99728314d888d95152f91d8aa8`

## Purpose

Repair the College Football → Game Total experience so the deployed Streamlit app actually runs the newest certified router and visibly presents correct team identity, records, evidence, and a compact/fun dashboard without changing frozen Game Total model calculations.

The current production symptom is that the live site can still render the older Game Total experience even after V151 was merged and certified. The production entrypoint and production proof therefore need to become explicit parts of the contract, not assumptions.

## Immutable boundaries

These stay frozen and must not be changed by V152:

- Game Total Step 11 distribution math.
- Game Total Step 12 final synthesis, grade/tier, thresholds, and Top-5 ranking logic.
- Sportsbook projection influence remains `0.0%`.
- College Football Moneyline remains frozen.
- College Football Over/Under remains frozen.
- Existing NFL/MLB/WNBA routes remain unchanged except for shared deployment verification that is additive and non-behavioral.
- No display-only reconciliation result may flow back into frozen Step 11/12 calculations.

## Design principles

1. **Production truth over branch-local truth.** A green branch-local browser test is insufficient if the deployed Streamlit site is still on an older router.
2. **Identity before model.** Logos, records, team IDs, kickoff, venue, broadcast, and source identity must be reconciled before the UI claims a matchup is verified.
3. **Evidence before decoration.** The page must expose useful scoring/defense/recent-game evidence before model gates and deep audit sections.
4. **Compact by default, deep on demand.** Key evidence stays visible; detailed evidence and audit machinery live inside expanders.
5. **Fail closed on placeholders.** `0-0`, missing logos, and blank scoring evidence cannot satisfy a production certification that claims the Game Total page is healthy.
6. **No user-managed reboot requirement.** Deployment freshness must be verified automatically after merge.

## Eight-step build

### Step 1 — Production activation fix

Wire the real Streamlit entrypoint (`app.py`) to the newest additive router used for Game Total V152 rather than leaving production pinned to an older router chain.

Requirements:
- Add a unique V152 production heartbeat/build marker exposed in the running app.
- Preserve all frozen routes by delegating non-Game-Total traffic through the prior router.
- Add a contract test that proves the production entrypoint imports/calls the V152 router.
- Add a browser assertion that reads the V152 heartbeat from the rendered app.

Acceptance criteria:
- Branch-local Streamlit launched via the real production entrypoint shows the V152 heartbeat.
- College Football → Game Total routes to the V152 page.
- Non-Game-Total route regression checks remain green.

### Step 2 — Reboot / freshness protection

Make deployment freshness a required production property.

Requirements:
- Production verification must compare the deployed Streamlit build/router heartbeat against the expected merge commit/router version.
- A stale deployment must fail the production verification workflow.
- The workflow must verify the actual deployed Streamlit application, not just HTTP availability.
- The user should not need to manually reboot Streamlit to pick up a merged release.

Acceptance criteria:
- Post-merge production workflow cannot pass while the deployed app still reports the previous router/build.
- Production evidence records expected commit, observed commit/build marker, and observed router version.

### Step 3 — Team identity foundation

Reconcile exact identity for both teams before rendering a verified matchup.

Required fields:
- canonical team name
- ESPN/team provider ID
- team logo URL resolved through the existing strict logo resolver
- conference
- AP/ranking status when available
- kickoff time
- venue
- broadcast
- game status

Behavior:
- `IDENTITY VERIFIED` is shown only when both teams have canonical IDs and expected core identity fields.
- Missing optional venue/broadcast may be labeled unavailable, but missing team identity cannot silently pass as verified.

Acceptance criteria for Syracuse @ Pittsburgh, 2026-09-17:
- both logos render
- Syracuse and Pittsburgh resolve to exact provider IDs
- no false identity-verified state when IDs are absent

### Step 4 — Real records + team stats

Use the existing live/runtime reconciliation path to populate current completed-game evidence and derived display stats.

Required visible metrics where supported by completed-game evidence:
- season record
- points/game
- allowed/game
- point differential/game
- last-5 form / recent results
- recent scoring
- recent points allowed
- home/away split
- SOS / opponent-win context where coverage supports it

Rules:
- Do not fabricate values when no completed games are available.
- A `CHECK` quality state is correct when evidence is incomplete.
- Snapshot-backed `completed_games` must be carried through to the display profile when present.
- Runtime data source/provenance must be visible in the evidence layer.

Acceptance criteria:
- no default `0-0` record when the live source contains completed games
- no blank PPG/allowed metrics when source data exists
- source coverage is disclosed when a metric cannot be calculated

### Step 5 — Evidence Center

Create compact team evidence panels that expose useful facts immediately and deeper detail on demand.

Always visible:
- record
- points/game
- allowed/game
- point differential/game
- recent form summary
- source/quality badge

Expandable detail:
- recent completed games with opponent/result/score
- offense evidence
- defense evidence
- splits and SOS context
- NCAA/team-stat rows and ranking provenance
- raw reconciliation/source notes useful for debugging

Acceptance criteria:
- evidence is accessible without scrolling through the final audit first
- each team has an independently expandable evidence section
- browser certification proves the expanders open and contain evidence rows

### Step 6 — Fun compact redesign

Redesign the top of the Game Total page into a matchup-first dashboard while retaining the Monster identity.

Layout:
1. V152 Game Total header + compact live/freeze badges
2. matchup selector/date
3. two-column team hero area: logo, name, record, rank/conference, identity status
4. compact game strip: kickoff, venue, broadcast, status
5. scoring-vs-defense evidence summary
6. Evidence Center
7. model gate/final forecast area
8. deep audit + Top-5 scan in collapsed expanders

Color language:
- green = favorable/healthy/verified
- red = negative/failure/blocker
- amber/yellow = caution/incomplete/check
- blue = neutral factual information
- purple = Monster/model-specific information
- gray = secondary/supporting text

Constraints:
- no green border everywhere
- no giant audit wall in the default view
- no hidden critical identity/evidence fields
- responsive on iPad/iPhone and desktop

Acceptance criteria:
- key matchup/evidence content fits substantially earlier in the page than V150/V151
- no horizontal overflow at narrow width
- deep audit sections are collapsed by default

### Step 7 — Real production browser certification

Create a production-grade browser contract that validates the actual deployed Streamlit site after merge.

Target flow:
- open production Streamlit URL
- navigate to College Football
- select Game Total
- select the 2026-09-17 Syracuse @ Pittsburgh matchup when available
- assert V152 production heartbeat
- assert both team hero cards exist
- assert both logos are rendered
- assert records are non-placeholder when completed-game evidence exists
- assert scoring evidence is populated when source data exists
- open both evidence sections and assert evidence rows are present
- assert deep audit is collapsed by default
- assert frozen sportsbook influence remains `0.0%`

The test must distinguish:
- route/render success
- data-source incompleteness
- stale production deployment

### Step 8 — Final production proof + freeze

Freeze only after the merged `main` commit is proven on the deployed website.

Required final proof:
- PR merged to protected `main`
- V152 branch contracts green
- CFB critical lane green
- regression shield green
- Anti-Loop/permanent contract green
- DevSystem final gate green
- deployed Streamlit heartbeat equals V152/expected merge identity
- production browser Game Total proof green
- deployed Render/API health verification remains green
- freeze manifest/ledger updated with the final certified commit and rollback point

After Step 8 is green, V152 becomes the new closed checkpoint. No recertification/polling unless a genuinely new production failure is observed.

## Data flow

Frozen analysis path:

`selected game -> frozen Game Total Hub/Step 11 -> frozen Step 12 -> forecast/gates`

Display reconciliation path:

`copy(selected game) -> runtime/live team reconciliation -> provider IDs -> logo resolver -> completed-game/stat derivation -> compact UI/evidence center`

The two paths meet only at rendering. Display reconciliation must never mutate or replace the object used by frozen calculations.

## Deployment flow

`feature branch -> branch-local contracts -> PR -> protected main -> Streamlit deploy -> heartbeat/freshness check -> production browser proof -> freeze`

A merge is not considered complete for this work until the deployed site reports the expected V152 heartbeat/build identity.

## Error handling

- Provider/team lookup miss: show explicit identity `CHECK`; do not invent logo/record.
- Completed-game evidence unavailable: show evidence `CHECK` and preserve model gate behavior; do not invent averages.
- Venue/broadcast unavailable: label unavailable without failing team identity if canonical team IDs are otherwise verified.
- Stale deployment heartbeat: fail production verification.
- Browser cannot find the target slate because schedule changed: certification should report a schedule-target mismatch separately from a render/identity failure.
- Runtime source exception: preserve frozen analysis path and surface display-data quality as unavailable/check.

## Testing strategy

1. Unit/contract tests for router activation and immutable model boundaries.
2. Reconciliation tests for exact team IDs, records, completed games, and source provenance.
3. UI contract tests for hero cards, logos, evidence metrics, expanders, and compact layout markers.
4. Branch-local Playwright through the real `app.py` entrypoint.
5. Existing CFB critical + regression + permanent/Anti-Loop gates.
6. Post-merge deployed Streamlit heartbeat verification.
7. Post-merge production Playwright against the live site.

## Anti-loop rules for this build

- Once an 8-step checkpoint is green, do not reopen it without a new failure that directly invalidates its acceptance criteria.
- Certification-infrastructure failures are fixed at the harness layer unless evidence shows the product code is at fault.
- Do not replace frozen model logic to solve display-data problems.
- Do not call the project complete because branch-local CI is green; Step 8 requires live production proof.
- Report progress as `X/8 complete — Y left` with 🟢/🟡/🔴 statuses throughout execution.
