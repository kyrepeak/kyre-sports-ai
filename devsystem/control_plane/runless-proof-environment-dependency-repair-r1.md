Runless V2 proof-environment dependency repair R1.

Scope is control-plane only. NBA product files are excluded.

Verified before protected integration:
- Runless V2 regression suite: 109/109 PASS.
- Exact NBA Step-3 proof commands under repaired bootstrap: py_compile PASS; pytest 35/35 PASS.
- Repair proof-plan commands under currently deployed old bootstrap: 22/22 PASS; py_compile PASS.
