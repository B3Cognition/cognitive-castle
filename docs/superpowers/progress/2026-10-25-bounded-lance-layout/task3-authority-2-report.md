# Task3 authority candidate2 — narrow orphan-route correction

Original candidate/report preserved. Root found ready-registry claim loss could falsely certify absence despite a surviving derived route. `resolve` now checks the existing bounded indexed route lookup before admitting a claim miss as absent. A route without a claim is unavailable; both missing retains the explicitly trusted ready-namespace path. Coherent authority+derived loss remains outside this observation model. No schema/queue/worker changes.

Focused RED reproduced false absence; GREEN passed2 tests (41.8MiB aggregate,1.7s). Prior31 pure checks were not repeated. Ruff/compile/scoped diff checks pass; source9/hooks3 unchanged. Actual SQL/native behavior remains unqualified. Exact hashes and argv are in `task3-authority-2-pure-results.json`; full four-file candidate is `task3-authority-2.diff`.
