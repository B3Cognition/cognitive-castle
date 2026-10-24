# Task 4 implementation report

Implemented trusted launch-host isolation in BrainAPI, supervised configured-host source routing, strict memory remember/read/status MCP registration through the existing registry, exact preview offsets/hashes with an encoded 8192-byte recall cap, and operator-only bounded private root registration and slice ingestion. Legacy unconfigured source routing is preserved. Both host skills and the brain-loop guide describe fast recall, exact requested storage, selective slow SUE and partial coverage.

Operator syntax:

```
castle --palace /absolute/palace memory register-root --name codex --path /absolute/original/codex/sessions --format codex
castle --palace /absolute/palace memory ingest --root codex --path /absolute/original/codex/sessions/session.jsonl
```

Formats are codex or claude. Ingestion processes one bounded slice per invocation. Public JSON commands are `castle memory remember|read|recall|status --input FILE` (or stdin); recall aliases the existing brain handler. Status without input supplies protocol_version1. Host comes exclusively from CASTLE_BRAIN_HOST.

## Red/green evidence

All pytest invocations used `/Users/ladislavbihari/.echelon/venv/bin/python scripts/safe_brain_tests.py` with explicit synthetic test files, temporary HOME, model/network denial and serialized execution.

- Initial RED: four new tests failed for missing host validation, host policy isolation and missing strict memory operations.
- Initial GREEN: 34 tests passed (new integration plus existing brain API), guard peak111.9MiB.
- Operator containment RED: escaped `original/../escape.jsonl` reached the mocked worker and failed. Parent validation added independently of worker validation; GREEN38passed.
- Replay test initially assumed byte-identical receipts; corrected to assert the preserved session identity because existing controller correctly charges replay requests to the root budget.
- Final focused API and integration run:41passed in5.20s, sampled test process aggregate peak115.0MiB; guard completed5.7s.
- Broader selected API/source/controller regression:139passed in17.43s, sampled harness aggregate peak338.3MiB; guard completed17.9s. This is test-harness memory, not a claim about installed runtime bounds.
- Ruff0.15.12 (the tool.ruff.required-version and CI pin): check passes; format check passes for all three changed Python files. The dev dependency pin0.17.1 mismatch is pre-existing; no package changes made.
- git diff --check passes.

Tests cover actual MCP strict argument rejection and encoded response envelope, exact remember→recall→page after restart, SUE archive binding across restart, replay revocation, distinct-host state/policy isolation, invalid launch-host rejection before mutation, policy changes during runtime reads, Unicode/control-character recall wire limits, registry owner-private mode and symlink/escaped-path denial. Existing tests retain native read-only/no-model boundary checks.

## Limits and scope

Only synthetic sidecars and original-root fixtures were used. No real archive, transcript or model was read; no full local suite, native archive scan, live config/hook/install change, branch switch or push occurred. Runtime and ingestion are separate agents' owned implementations; host API consumes their fixed public interface. Worker RSS tripwires are supervisory rather than kernel ceilings. Indexed-only recall does not imply historical completeness. Existing MCP clients require reconnection. Independent integration review remains with the parent/reviewer before integration.
