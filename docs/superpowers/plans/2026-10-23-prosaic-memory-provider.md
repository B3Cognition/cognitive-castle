# Optional Prosaic Castle Memory Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task after review. This is a planning deliverable; no implementation or publication has been requested.

**Goal:** Deliver a separately installed, read-only Castle memory provider consumed through Runtime custom tools and frozen Harness/native inputs.

**Architecture:** Castle owns a scoped memory service in a private worker; a Runtime-only optional adapter owns bounded transport and tool bindings. The host authorizes one namespace/palace and allowed wings. Harness persists execution/input evidence and does not acquire a memory engine.

**Tech Stack:** Python >=3.11 adapter, Castle >=3.10 worker, stdlib subprocess/JSON, existing `CustomTool`, `ToolExecutionContext`, Harness public bindings and pytest fixtures.

**Spec:** `../specs/2026-10-23-prosaic-memory-provider-design.md`; prerequisite `2026-10-23-castle-memory-hardening.md`.

## Global Constraints

- One palace per trust-domain namespace; explicit writable preparation binds its identity. Opening/serving never migrates or changes that binding.
- Search/fetch/snapshot scope enforcement is identical; paths, identity and credentials never come from model arguments.
- `memory-v1` does not import SOAR, SUE, quality analysis or generative provider clients. No model download on traffic.
- Preserve existing Castle public APIs and Prosaic serialized camelCase/on-disk contracts.
- Runtime executes models/granted tools; Harness owns durable workflow state; the host owns authorization/publication.
- No write/publish/SUE/delete/settings model tools in v1. No HTTP server, new Harness node or ambient native MCP grant.
- Use `apply_patch`, public installed APIs and candidate/released wheels with checksums; preserve unrelated work. Release/push is separate authorization.

## Review Focus

1. A forbidden record ID or KG recall result must not bypass search scope: M1.
2. Multibyte content, control characters and oversized metadata must remain exact and bounded: M1/M2.
3. A stalled/hostile worker or full stderr pipe must obey cancellation/deadline and leave no child process: M2/M4.
4. Domain failures must not be wrapped as successful results or leak exception text: M3/M4.
5. Resume after source changes must reuse frozen evidence; a missing conversation run ID must not broaden access: M5.

## Proposed package/file map

Castle new modules: `memory_types.py`, `memory.py`, `provider_protocol.py`, `provider_worker.py`, `provider_setup.py`; focused tests under `tests/test_memory_*.py`.

Optional distribution under `adapters/prosaic/`: `pyproject.toml`, `README.md`, appropriate licenses/notices; `src/prosaic_memory_castle/{__init__,client,transport,tools}.py`; `tests/`; `examples/`. Depends on Runtime, not Castle or Harness. Harness is an example/test extra only. Host supplies an absolute worker command from a separately installed Castle environment; installing the adapter never installs Castle/torch/spaCy or starts a process.

One generic Runtime patch lives upstream in `prosaic-runtime`, with its own tests/review/release. No Castle-specific imports in Core/Runtime/Harness.

Dependencies: hardening H1–H8 before qualification; M1 → M2; M3 may proceed independently; M2+M3 → M4 → M5 → M6. Every task produces a separately reviewable deliverable and scoped commit.

### M1: Define source-preserving scoped memory reads

**Files:** Create `cognitive_castle/memory_types.py`, `memory.py`, `provider_setup.py`; modify `cli.py`; tests `test_memory_service.py`, `test_memory_setup.py`, `test_memory_scopes.py`.

**Interfaces:** `prepare_provider(paths, *, namespace, config) -> ProviderHealth`; `MemoryService(context, *, namespace, allowed_wings)` with `search`, `fetch`, `snapshot`, `health` signatures from the spec. Define frozen dataclasses `SearchHit`, `SearchResult`, `MemorySlice`, `SourceExpectation(text_sha256, revision)`, `SourceBundle`, `ProviderHealth`; `MemoryError(code)` has only the spec's closed codes.

**Wire shapes:** Use new `schema_version=1` envelopes; these are new Castle-provider contracts, not changes to Prosaic's existing camelCase records. A search result has `hits`, `degraded_signals`; each hit includes `record_id`, `text_sha256`, `revision`, `representation`, `wing`, `captured_at`, `score`, `rank`, `excerpt`, `excerpt_is_complete`. A slice includes `record_id`, full/slice digests, `text`, `start_char`, `next_start_char`, `complete`, `provenance`. Bundle includes ordered `sources`, exact `texts`, digest and `schema_version`.

- [ ] Add tests that an unprepared/mismatched namespace is refused without disk changes; two palaces with identical wing names remain independent; out-of-scope `fetch` is indistinguishable from missing ID; dense, FTS and KG all apply scope before candidate caps; post-fetch validation rejects foreign IDs.
- [ ] Add exactness/bounds tests: 4,096/4,097-byte queries; limits 1/20/21; 8,000-character astral Unicode and control-character slices; offset at/beyond end; 49,152-byte payload cap; oversized provenance; source revision unknown; no matching records versus unavailable signals. Assert consecutive fetch slices reconstruct identical stored text/hash.
- [ ] Add snapshots with reversed backend result order, duplicate IDs, wrong scope, a changed record between search and selection, and missing sources. Require explicit expected digest/revision when freezing search-selected records; reject mismatch rather than silently snapshot a new version. Maximum bundle size counts encoded manifest+text JSON bytes and is 262,144 by default. Snapshot returns in-memory data and never writes the read-only palace; the host persists it.
- [ ] Run `.venv/bin/python -m pytest tests/test_memory_service.py tests/test_memory_setup.py tests/test_memory_scopes.py -q`; observe RED before implementation.
- [ ] Implement `castle provider prepare --palace PATH --namespace ID`: validate/migrate through H5, write `.provider/identity.json` under the mutation lock with schema version and opaque namespace, verify identity on subsequent preparation, refuse rebinding. Never download models or silently merge old palace state.
- [ ] Route service search exclusively to `memory-v1` with bound allowed-wing SQL and final record scope checks. Apply dedup before final result limiting, preserve alternate provenance without exceeding metadata bounds. Use exact fetch for full text; no raw absolute source paths in model-facing payloads.
- [ ] Verify both service reads and construction under a filesystem mutation trap. `health` reports versions/capabilities/degradation without corpus text or other namespaces. Commit `feat: expose scoped source-preserving castle memory reads`.

### M2: Add a private bounded worker protocol

**Files:** Create `provider_protocol.py`, `provider_worker.py`; modify `pyproject.toml` entry points; tests `test_memory_protocol.py`, `test_memory_worker.py`, `test_memory_worker_stdio.py`.

**Interfaces:** `castle-provider --palace ABS_PATH --namespace ID --config ABS_PATH --wing WING` (repeat `--wing`); never accept this grant via request JSON. Frame `{version:1,id:bounded_string,op:string,args:object}` → `{version:1,id,ok:true,result:object}` or `{version:1,id,ok:false,error:{code:enum}}`. Closed operations `hello/health/search/fetch/snapshot/close`; `close` terminates after response. `snapshot` is host-only in the adapter, though the pipe endpoint can serve it.

- [ ] Add malformed/non-object/duplicate-key/nonfinite/oversized/truncated frames, wrong version, duplicate in-flight ID, unknown operations and extra grant fields. Assert one bounded safe response or orderly termination; never execute a requested command or accept new identity.
- [ ] Add subprocess tests that imported dependency output cannot contaminate protocol stdout; long stderr is drained/bounded; queries never appear in process argv; closing releases all handles; missing models return safe unavailable diagnostics without a network call.
- [ ] Run `.venv/bin/python -m pytest tests/test_memory_protocol.py tests/test_memory_worker.py tests/test_memory_worker_stdio.py -q`; observe RED.
- [ ] Implement serial request processing, 1 MiB maximum encoded frame, strict JSON, bounded stderr diagnostics and protocol-only stdout. Read at most the bound before rejecting input; do not read an unbounded line then check its length. Heavy imports run after worker-only stdout protection, with no library-global stdio mutation.
- [ ] Preflight prepared store, namespace/config/model identity and offline model availability in `hello`; warm only already-provisioned models. Open strict read-only context; reject unavailable mandatory signals. Include semantic profile/model/config fingerprint in handshake.
- [ ] Add a hostile fake worker harness for M4 transport tests and a real-worker/real-Lance synthetic path using test encoders. Confirm optional-engine imports/network are forbidden. Commit `feat: serve memory reads over a bounded private worker protocol`.

### M3: Add safe generic custom-tool errors in Runtime

**Repository/files:** `/Users/michalbachorik/work/prosaics/prosaic-runtime`: `src/prosaic_runtime/tools.py`, `runtime.py`, `__init__.py`; tests `test_custom_tools.py`, `test_custom_tool_transport.py`, `test_cli_tools.py`; relevant SDK documentation.

**Interfaces:** Preserve `ToolExecutionError(code)`; add/export safe closed codes `tool_not_found`, `tool_unavailable`, `tool_invalid_request`, `tool_result_limit`, `tool_incompatible`, `tool_timeout`; advertise capability `custom_tool_errors_v1`. No arbitrary error strings/details, no provider-specific names and no change to journaled effect uncertainty.

- [ ] Add tests that each generic error yields Runtime `{status:error,error:code}`, unknown codes fail construction, raw exception/provider text is absent, existing CLI codes remain unchanged, and cancellation/deadline exceptions still take their control path. Ensure journaled handlers still record uncertain dispatch rather than treating an exception as completed.
- [ ] Run `.venv/bin/python -m pytest tests/test_custom_tools.py tests/test_custom_tool_transport.py tests/test_cli_tools.py -q`; observe RED for new codes/export/capability.
- [ ] Extend the existing closed code set and public export; no new dependency, memory-specific handler branch, tool authorization relaxation or retry behavior.
- [ ] Run focused and full Runtime suite, `.venv/bin/python -m build`, and clean installed smoke. Commit/review as a standalone generic SDK patch. Record the actual qualified package version/checksum; do not invent a released version floor in adapter metadata before this patch is published/selected.

### M4: Build the optional Runtime adapter package

**Files:** Create the `adapters/prosaic/` package/file map above, including license attribution, `tests/test_transport.py`, `test_tools.py`, `test_packaging.py`.

**Interfaces:** `WorkerCommand(argv: tuple[str, ...])`; `CastleMemoryProvider(command, *, palace_path, namespace, config_path, allowed_wings, startup_timeout=120, operation_timeout=30)`; context-manager/`close`; `search`, `fetch`, `snapshot`, `health` mirror M1, with internal deadline/cancellation controls. `memory_tools(provider, *, authorize) -> dict[str, CustomTool]` registers only `memory_search` and `memory_fetch`.

- [ ] Package/import tests run in a Runtime-only environment with imports of `cognitive_castle`, torch and spaCy forbidden. Construction/import must not spawn a process. Require absolute executable, explicit config/root and nonempty approved scope; no PATH fallback or mutable model-selected command.
- [ ] Transport tests cover handshake mismatch, ID mismatch, oversized/no-newline stdout, stderr saturation, EOF, a worker hanging before hello/during response, cancellation while queued, deadline while waiting for the serial lock, process descendants, and explicit `close` after errors. Assert bounded completion and child teardown; a subsequent independent read may start a new worker.
- [ ] Tool tests assert closed schemas, query/result limits, `with_context=True`, required authorizer and zero worker dispatch on denied authorization. Test conversation context with no run ID via trusted host-bound scope. Parent cancellation/deadline propagate; a narrower 30-second read timeout maps to `tool_timeout` if the parent still has time.
- [ ] Run adapter `.venv/bin/python -m pytest -q`; observe RED, then implement bounded nonblocking pipe reads/writes, cancellation-aware lock acquisition, monotonic shared deadlines and terminate→bounded wait→kill/drain teardown. Drain stderr with a 64 KiB tail cap; never include it in model-visible errors.
- [ ] Verify `custom_tool_errors_v1` before tool registration. Map M1 errors to M3 codes (`not_found`→`tool_not_found`, `unavailable`→`tool_unavailable`, `invalid_request`→`tool_invalid_request`, `result_limit`→`tool_result_limit`, `incompatible_store`→`tool_incompatible`). No successful domain-error envelope. Authorization uses existing Runtime denial behavior.
- [ ] Pin the actual qualified Runtime floor and worker protocol/profile version in the adapter release. Build the adapter wheel; install into a clean Runtime-only environment and smoke against a separately installed worker wheel. Commit `feat: add optional prosaic castle memory adapter`.

### M5: Demonstrate Harness and native snapshot consumption

**Files:** `adapters/prosaic/examples/{api_agent,workflow,conversation,native_snapshot}.py`; neutral prose under `examples/prose/`; tests `test_workflow_integration.py`, `test_conversation_integration.py`, `test_native_snapshot.py`, `test_resume_evidence.py`.

**Interfaces:** Use public `WorkflowBindings(custom_tools=...)`, `ConversationBindings(custom_tools=...)`, `InvocationScope`, Runtime tools and the host-side snapshot API. Harness dependency remains example/test-only. Add no Core/Harness engine code unless a separately reproduced generic defect requires upstream repair.

- [ ] Add owned local HTTP provider tests for an agent selecting `memory_search` then `memory_fetch`. Assert all returned text is unprivileged tool/user data, Runtime tool grants are intersected, and authorization/usage/receipts retain their normal contracts.
- [ ] Add a workflow pause/resume test: freeze source bundle, mutate/re-import the source before resume, then assert resumed inputs use identical bundle bytes/hash and invoke no fresh retrieval. Add a crash after model completion before checkpoint acceptance and prove existing Harness receipt recovery handles it without duplicate model dispatch.
- [ ] Add conversation tests resolving trusted owner binding without assuming `scope.run_id`; hostile model-supplied namespace/path fields fail schema before dispatch. Test exact fetch of a guessed foreign record ID.
- [ ] Add NativeRuntime example/test where the host supplies a frozen bundle in assignment arguments. Assert no custom tool grant or ambient Castle MCP becomes available, and memory text is never installed as a system resource. Keep default native reader isolation intact.
- [ ] Run focused integration tests against installed candidate wheels, with loopback fixtures and no credentials. Exercise memory disabled and worker unavailable paths; required-memory policy blocks explicitly, optional-memory policy continues with an unavailable label rather than fabricated empty history.
- [ ] Document `ALWAYS`/`NEVER` memory-use rules, capture coverage limits and host ownership. No autonomous writes, diary bookkeeping or SUE tool in the examples. Commit `test: qualify memory reads across runtime and harness consumers`.

### M6: Qualification and staged adoption

**Files:** Adapter CI/build documentation, `docs/verification/2026-10-23-prosaic-memory-provider.md` (actual execution date may differ), release metadata only after versions are selected; H8 actual-pipeline benchmark outputs with sanitized fixtures.

- [ ] Run the full Castle, generic Runtime patch and adapter suites in their own environments; provision pinned local encoder/reranker weights explicitly for the model lane. Run clean installed wheel/worker tests, optional-engine/network-forbidden tests and process teardown checks. Keep skipped optional SOAR tests distinct from required provider gates.
- [ ] Run H8's held-out production-pipeline benchmark and review cold/warm memory/latency costs against the text/FTS baseline. Record hashes/model identities and uncertainty; do not substitute old Chroma scores.
- [ ] Verify worker store identity, read-only no-write evidence, scope isolation and error handling with the exact release wheels. Keep the consuming application's provider feature disabled by default until its pilot evidence is reviewed.
- [ ] Publish only after explicit release authority and existing repository release checks. Keep personal developer palaces separate from application/customer palaces. Initial adoption has only search/fetch and explicit snapshots.
- [ ] Record deferred items: source-retention purge/compaction, slim worker packaging, write/publication outbox and optional SUE. None is silently shipped as an unqualified background capability.

## Self-review outcome

The design-builder review identified namespace binding, preservation policy, true read-only initialization, safe Runtime tool errors and worker provisioning as material decisions. They are resolved explicitly in the design and M1/M3/M4. No user-specific choice is required to prepare this proposed plan; pilot/release authorization remains an execution-stage decision.
