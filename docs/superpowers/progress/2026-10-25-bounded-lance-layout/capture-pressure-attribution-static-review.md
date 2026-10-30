# Capture pressure attribution: static review

Approved for the narrow diagnostic change. No blocking finding. This does not establish the cause of the observed capture refusals and does not authorize a pressure-limit change.

Reviewed the complete delta d9d2c82da921ceb6ecb54af7e6889644b98f88b032b0ea81d6ab2490ce37e9dd against 0594472692ba5d444e846bb6462af2ef51dd25c3 in cognitive-castle-capture-priority. Independently matched all five current source hashes to capture-pressure-attribution-pure.json:

- brain_reader_guardian.py: 3fbfc8738796948b2311715ead4f1558fff44489711e6780fd6cbeba32a5986b
- memory_runtime.py: 2219bca536103e902a2c9b8028634a7cc846730c751af21030543e2ec42afafc
- memory_coordinator.py: edcdd046e6e487a62d01642415f3d139166e0a01428cad06970ed256de912bb2
- test_capture_pressure_attribution.py: 96c5c4cafc4f1bda98b1b34ab94c1d2e2795554bfaa8e68b5acac6fd3a1897d9
- test_memory_capture_priority.py: c4dc892e8df5d75d68090373bb3da6a780a08d8213e478332555f4bbdeaa3283

The original boolean pressure decision, one subprocess per check, 50 ms background host deadline, 0.5 s guardian timeout, and foreground-waiter precedence remain. Success leaves the sink without a failure record. Fixed site/outcome enums and bounded integer timing/pressure fields distinguish initial/periodic host/guardian checks without storing subprocess output, exception text, paths, or conversation bodies. Exact-shape validation bounds a propagated diagnostic to 512 bytes, and malformed/unrelated metadata is discarded. Coordinator now retains valid pressure attribution rather than losing it when recording capture-last.

Read the ten recorded AST-selected pure checks, including late-normal refusal, real non-normal value classification, timeout/OS-error privacy, no extra probe on exhausted deadline, original foreground mock compatibility, waiter precedence, and guardian-to-host-to-coordinator preservation. The author reports ten passing checks plus Ruff/compile validation; reviewer did not execute those checks, probe pressure, run capture, install code, or open any database. Existing native priority evidence remains separate.

The additive observation overhead is included in existing wall clocks. A later diagnostic reading is still required to attribute actual operational failures; this change alone is not evidence that the 50 ms window caused them.
