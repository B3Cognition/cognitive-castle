# Optional provider split verification — 2026-10-24

Depends on shared hardening PR #107, commit
`93b6e034e985f5b6c1c93590b011ca05f1b3819d`. This stage adds the service,
worker/protocol, retrieval profiles and Prosaic adapter. Release metadata and
source-archive additions remain a separate dependent change.

Final local root verification used Python 3.11.15 on macOS ARM64, cached real
models offline and the same test-only CPU launcher as the shared stage:

```text
main suite: 2514 passed, 11 existing skips, two benchmark deselections; 96.26s
fresh-process supervision: 48 passed; 10.91s
combined coverage: 85.33%, unchanged 85% gate passed
adapter suite: 75 passed; 9.96s
```

The adapter suite uses the existing installed tool-capable candidate SDK test
environment. It does not establish model-tool compatibility with public Runtime
0.9.8, which lacks `custom_tool_errors_v1`. Public host health/search/fetch and
frozen snapshot/resume are independently qualified by the Lab native lanes.

The new explicit-config context exposed fake-backend test setup that only
patched the global collection getter. The fixture now supplies its same backend
at the context boundary, retaining every scope/ranking/forbidden-engine assertion
and the explicit-config identity assertion. All 45 focused profile/context tests
pass; the full passing counts above follow those fixture corrections.

FTS remains default, with raw backend ordering and recency disabled. Dense
retrieval and recency are explicit host options. Existing legacy modes,
standalone fast memory, SUE and SOAR remain available; provider reads execute
none of the optional engines. Installation does not enable host memory.

The unchanged Lab disabled-memory example hashes to
`f6c789fdb09cb7b7104902622ddbc27a39a07d0906571fde64d2cc62e4c2ed97`;
its public SDK manifest hashes to
`36eec99280acb8688d2496f704f4445b59c3ff269fc506a83d6e7fe83bc92698`.
Historical records retain original identities. Fresh benchmark/rebuilt/native
candidate evidence and full platform CI remain release gates.

See `docs/prosaic-sue.md` for existing SUE use and a separate optional review
application plan. No SUE implementation or provider activation is added here.
