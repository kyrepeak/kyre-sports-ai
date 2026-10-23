# Universal Streamlit Navigation + Speed V1

## Goal
Keep internal site navigation in the current tab, make the newest navigation intent win during rapid tapping, and reduce avoidable shared Streamlit navigation overhead.

## Requirements
- Internal site links stay in the current tab.
- External links keep their normal browser behavior.
- Rapid taps use a monotonic navigation generation so stale delayed work cannot replace the newest intent.
- Newly rendered internal links inherit the same-tab rule without polling.
- Existing Runtime V5 stale-write guards remain authoritative.
- No sports model, probability, ranking, provider, or data semantics change.
- No background destination prefetch is added.
- The implementation is a forward-only universal successor; frozen sports pages remain untouched.

## Acceptance
Focused universal navigation tests and Python compile must pass on the exact candidate SHA before merge.
