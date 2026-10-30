# Task2a implementation report

Status: implemented, scoped verification green, inactive pending review/integration.
Worktree: `/Users/ladislavbihari/myWorks/cognitive-castle-capacity-reuse`.
Parent: `3208aea`. Scoped commit: `56911a6` (`feat: add pinned staged semantic runtime and exact token windows`).

## Scope and interfaces

Only these product/test files were added:

- `cognitive_castle/semantic_profile.py`, `tests/test_semantic_profile.py`
- `cognitive_castle/semantic_windows.py`, `tests/test_semantic_windows.py`
- `cognitive_castle/semantic_worker.py`, `tests/test_semantic_worker.py`
- `cognitive_castle/semantic_runtime.py`, `tests/test_semantic_runtime.py`

No dispatch, existing memory-runtime budget, exact store, queue, capture, service,
installed checkout or palace data was changed. No vector publication or retrieval
cutover is implemented by this substep. No downloads or provider calls occurred.

`semantic_profile` contains the immutable qualified contract: the six exact byte
sizes and SHA256 hashes copied from the approved diagnostic, pinned model
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, qint8_arm64, 384 dimensions,
attention-mask mean followed by L2 normalization, no lowercasing, 128 total tokens,
32 content-token overlap and exact-overflow-v1 windowing. Identity also binds CPU
provider, sequential one-thread inference, default graph optimizations, disabled
CPU arena/memory pattern/telemetry, and qualified Tokenizers0.22.2/ORT1.25.1.

Current `PROFILE_ID`:
`a1fdc081cd5709ddda44d2c644a24cf0658198690f93a7b68d376b3c0edb0120`.

- `load_profile(manifest)` verifies the trusted host-supplied manifest and every
  artifact before any native runtime initialization. Locations are not encoded
  in profile identity and no user's home is hardcoded in product code. The
  manifest is a locations/receipts document, not an override of qualified choices.
- Existing cache symlinks are allowed only to owned regular, non-group/world-
  writable resolved targets with the pinned size/hash. The manifest itself must
  be absolute, regular, owned, non-symlink and non-group/world-writable.
- `validate_runtime_versions()` uses distribution metadata before native imports
  and rejects unqualified Tokenizers/ORT versions. No dependency installation was
  changed.
- `decode_frame(bytes)` rejects duplicate keys, malformed/non-object JSON,
  nonfinite numbers (including overflow notation `1e999`) and frames over512KiB.
- `validate_sequence` and `validate_vector` enforce JSON integer shapes, pinned
  vocabulary, masks/types,384 dimensions, finiteness and unit normalization.

`semantic_windows` accepts1..8 envelopes of
`{"source": full_CanonicalRecord_source, "expected_hash": exact_text_hash}`.
It revalidates canonical provenance, text hash,8192B chunks and source count.
`tokenize_page(tokenizer,sources,continuation=None)` uses the pinned native
postprocessor's actual special tokens and native overflow encodings. A separate
untruncated encoding of the unchanged original text verifies each content token
and exact offset against each overflow window. It never decodes/re-encodes token
text and never guesses special-token IDs. First/last window character coverage
includes source boundaries, even leading/trailing whitespace. Whitespace with no
content tokens produces an explicit nonsemantic unit spanning the source.

Each unit binds canonical ID, exact source hash, profile, content-token interval,
original local character offsets, canonical chunk/absolute offsets, full token
arrays, every token offset and input-token hash into `unit_id`. Source text is
never copied into a new SQLite location (these modules create no SQLite files).

Pages contain at most32 units and expose `input_binding`, `start_window`,
`total_units`, `next_continuation`, `complete`, `handoff_hash` and `units`.
Continuation binds the entire ordered validated input set, exact text/provenance
and profile. Changed sources cannot resume an old continuation. `complete=True`
means enumeration exhausted; a terminal continuation page is not proof all prior
pages were durably acknowledged or published. Task2b must require contiguous
acknowledged pages before claiming full semantic coverage.

`semantic_worker.py` is the only semantic executable. The trusted coordinator
supplies its fixed absolute checkout path with `python -I` and the prepared
manifest via command line; request arguments cannot select files/executables.
The worker checks the live host->exact guardian command->worker parent/session/
process-group/owner chain and live budgets before artifacts or native imports.
Its operation allowlist is exactly tokenize/infer, with512KiB frame bounds.

- Tokenize imports Tokenizers and blocks NumPy/ORT.
- Infer imports NumPy/ORT and blocks Tokenizers. It reuses one session within that
  short-lived worker and infers one window at a time.
- Both phases deny networking, child creation, Torch/ST/providers and optional
  Pandas/Lance/Arrow paths. Worker environments also force one-thread BLAS,
  offline flags and disabled tokenizer parallelism.
- Infer validates the exact page handoff before native initialization, CPU-only
  providers, ONNX input/output shape/type and finite normalized vectors.

`with SemanticSession(trusted_profile,interactive=True) as session` owns the
existing memory admission inode and one absolute5s budget starting at session
construction. `session.tokenize(sources,continuation)` then
`session.infer(page)` share admission and remaining time. The coordinator records
phase supervision evidence in `session.resources`, issues ephemeral page handoff
capabilities, rejects unissued/altered handoffs, and independently validates
returned page/request binding and inference vectors. Successful results arriving
after the absolute deadline are unavailable. `_run_stage` is a private trusted
extension point for a future fixed Lance stage under the same lease/deadline.
There are no caller-specified deadline/RSS increases and no production retry.

The coordinator uses existing `_admission`, `_waiting_marker`,
`interactive_waiting` and `_supervise`, with fixed512MiB task/640MiB aggregate.
Context exit closes admission/waiter descriptors after success/errors. Existing
supervisor cleanup kills/reaps the owned group before returning. Native tests
observe no new surviving child process identities after each session.

## Scheduling limitation retained for later work

Interactive intent and admission waiting mirror existing memory runtime behavior:
interactive contention waits up to0.5s; background never waits behind an
interactive waiter and checks/yields before each stage. An already-running stage
is not preempted when interactive intent arrives. A background32-window inference
stage measured1.03..1.16s and can therefore outlast an interactive0.5s admission
wait. Tokenizer stages also reached0.84s on an earlier observed run. Root explicitly
accepted reporting this limitation for supervisor cancellation/yield work in
Task2b/4. This report makes no prompt-preemption claim. The session's stage-level
readiness check is the current trusted yield boundary.

## TDD and verification evidence

All commands below used this worktree and the existing echelon Python environment.
No broad suite was run: the brief requested covering files rather than repeated
broad suites, and bounded/native work stayed sequential under safe_brain_tests.

Initial RED:

```
python scripts/safe_brain_tests.py tests/test_semantic_profile.py tests/test_semantic_windows.py tests/test_semantic_runtime.py
12 failed in0.08s (new modules absent)
[guard]40.9MiB;0.5s;completed
```

Initial GREEN after profile/windows/coordinator implementation:

```
12 passed in0.05s
[guard]33.6MiB;0.2s;completed
```

Worker RED with the opt-in pinned profile, before implementing the executable:

```
CASTLE_TEST_SEMANTIC_PROFILE=<approved profile> python scripts/safe_brain_tests.py --timeout 60 tests/test_semantic_worker.py -s
4 failed in0.28s (missing executable/worker_invalid_frame)
[guard]76.1MiB;0.5s;completed
```

Subsequent red/green checks:

- Native multilingual ranking, unsupervised invocation and invalid-profile
  refusal passed after the worker implementation. The original long fixture
  produced22 rather than>32 units: the test failed and was expanded to two full
  validated long sources, producing43 units including the whitespace source.
- Native NUL inside whitespace was observed to be a content token, so the explicit
  all-whitespace case was corrected to real whitespace. Long Unicode sources
  retain NUL; exact source text/hashes and offsets remain unchanged. Both fixture
  mistakes were test assumptions, not hidden product truncations.
- Added failing malformed-inference-response and late-success tests; fixed host
  response validation and absolute-deadline postchecks. GREEN5 runtime tests.
- One pure admission test encountered real concurrent admission contention and
  returned early instead of exercising its intended validation branch. The pure
  runtime tests now isolate only the admission directory using the real flock
  implementation; native qualification continues to use actual shared admission.
- Version-mismatch RED1 failed/8 passed, then metadata pinning GREEN.
- Numeric-overflow JSON RED1 failed/8 passed, then finite parse-float GREEN.
- Source-set/unit mismatch RED1 failed/3 passed and wrong-source tokenizer response
  RED1 failed/5 passed, then source membership and request/result binding GREEN.

Final covering command (full native opt-in; no skips):

```
CASTLE_TEST_SEMANTIC_PROFILE=/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/semantic-models/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/profile.json python scripts/safe_brain_tests.py --timeout 60 tests/test_canonical_records.py tests/test_semantic_profile.py tests/test_semantic_windows.py tests/test_semantic_runtime.py tests/test_semantic_worker.py -s
50 passed in4.43s
[guard] sampled aggregate peak466.3MiB;4.8s;completed
```

The eight-document English fixture and Czech/German/Spanish queries all produce
the expected top1 (meeting time, Prague train departure, rose watering).
Other checks cover stale input continuation, source hash/count, Unicode/NUL/tail
coverage, actual128-token overflow/32 overlap, explicit whitespace handling,
phase import/network/child denials, duplicate/malformed/nonfinite frames,
unqualified profiles/runtime versions, unsupervised invocation before artifact
access, normalized-vector validation, shared deadlines, interactive yielding,
malformed worker output, admission release and observable descendant cleanup.
The test host imported none of Tokenizers/NumPy/ORT/Torch/Lance.

Final pinned Ruff commands over exactly the eight scoped files:

```
/Users/ladislavbihari/.echelon/venv/bin/ruff check <eight scoped files>
All checks passed!
/Users/ladislavbihari/.echelon/venv/bin/ruff format --check <eight scoped files>
8 files already formatted
```

## Final resource observations

Fixed limits512MiB task /640MiB aggregate /5s session. RSS values are sampled
tripwires, not kernel ceilings; transient peaks remain possible. Stage aggregate
includes the trusted test host; safe_brain_tests uses its own differently timed
aggregate samples.

| Fixture/stage | Peak task bytes | Peak aggregate bytes | Stage seconds | Session seconds | Page/response bytes |
|---|---:|---:|---:|---:|---:|
|8 documents/tokenize|447070208|493371392|0.5541|1.0725|6952/65501|
|8 documents/infer|382959616|429670400|0.5083|same|same|
|3 queries/tokenize|447135744|494010368|0.4909|0.8324|2924/24840|
|3 queries/infer|380289024|427196416|0.3343|same|same|
|43-unit set,32-unit page/tokenize|453197824|500350976|0.5215|1.5989|103518/260352|
|32-unit page/infer|386236416|434077696|1.0589|same|same|
|Terminal11-unit page/tokenize|450805760|499286016|0.4857|0.4920|33953/33953|
|Invalid profile/refusal|46170112|94928896|0.1038|n/a|unavailable|

Across all observed native runs the largest task sample was453197824B
(432.20MiB), largest aggregate500350976B(477.17MiB). Earlier32-window inference
measured1.1621s, session2.0263s, inference task386957312B. These stayed inside
fixed limits. No native attempt encountered system-pressure, parent-memory,
aggregate-memory, task-memory or deadline refusal; no guard was relaxed and no
larger retry occurred. The test-only helper records every refusal and allows
bounded backoff only for existing busy/pressure/parent/aggregate admission reasons;
no retries were needed in the final native run. Deliberate invalid-profile and
unsupervised refusals are `semantic_invalid_request` and
`semantic_unsupervised`. Pre-implementation `worker_invalid_frame` failures and
one incidental pure-test admission contention are recorded above.

## Concerns / subsequent work

No remaining scoped test failures. Native qualification is local/offline/synthetic
and does not establish historical-vector compatibility or semantic recall quality
on real archives. Only the prepared qualified runtime versions are accepted.
Queue/vector durability, shared Lance integration, active-stage preemption,
contiguous publication accounting and production cutover remain later tasks.

## Review fix round1/5 — absolute preflight deadline

Addressed Important1 from `task-2a-review.md`; parent commit56911a6; fix commit`fba868f`. Root explicitly
authorized the minimal shared supervisor/guardian changes. Public budgets and
production dispatch remain unchanged.

Changes:

- `SemanticSession` now passes its absolute monotonic deadline into the real
  `_supervise`, in addition to its already bounded relative remainder.
- `_supervise` starts timing at entry, caps its own deadline by that absolute
  deadline, includes pressure/resource/serialization preflight in it, recomputes
  remaining time immediately before guardian launch, and refuses expired work
  without spawning. The same absolute timestamp travels to the guardian.
- Guardian caps its local deadline by the host's timestamp, checks initial
  pressure within it, and refuses before child launch if it has expired.
- Initial and recurring pressure probes use subprocess timeout
  `min(0.5, absolute_deadline-monotonic_now)` and skip spawning sysctl after
  expiry. Both host and guardian recheck the deadline after the blocking probe.
  Selector waits are also capped by remaining time. Deadline expiry returns
  `worker_deadline`; genuine pressure failures retain
  `system_pressure_unavailable`. Group kill/reap/admission cleanup remains intact.
- A small shared `_pressure_reason` helper keeps the exact pressure/deadline
  boundary consistent and avoids exceeding existing Ruff complexity limits.
- `tests/test_history_runtime.py` has one dependent pressure-fixture signature
  update only (`lambda **kwargs`); no history product behavior was changed.

RED evidence, exercising real supervisor and guardian preflight:

```
python scripts/safe_brain_tests.py tests/test_memory_runtime.py -k 'slow_initial_pressure or pressure_subprocess_timeout or guardian_slow_pressure'
3 failed,31 deselected in0.07s
[guard]37.6MiB;0.4s;completed
```

The first test failed because the real `_supervise` attempted an expired guardian
launch after the pressure probe advanced a controlled clock past its0.1s budget.
The guardian test likewise observed an expired child launch. The pressure helper
rejected the new deadline argument before implementation.

Intermediate GREEN:

```
5 passed,35 deselected in0.07s
8 passed,25 deselected in0.07s
23 passed,44 deselected in5.13s
```

The added semantic integration regression does not mock `_supervise`: it enters a
real isolated admission lease with absolute deadline105.0, advances to104.9,
lets the pressure boundary advance to105.1 and proves no guardian/native stage
launch occurs. The recurring-pressure integration test observes the identical
absolute deadline at both initial and recurring checks. Existing tests cover
pressure refusals, owned-descendant cleanup, stalled IPC, guardian deadlines and
unchanged production budgets.

The first covering run passed48 tests in10.76s. Ruff then correctly rejected the
expanded supervisor/guardian functions for C901 complexity; factoring the shared
pressure/deadline helper resolved that issue. Final covering verification after
that refactor:

```
CASTLE_TEST_SEMANTIC_PROFILE=/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/semantic-models/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/profile.json python scripts/safe_brain_tests.py --timeout 60 tests/test_memory_runtime.py tests/test_semantic_runtime.py tests/test_semantic_worker.py tests/test_history_runtime.py::test_pressure_rejection_happens_before_launch -s
48 passed in10.81s
[guard] sampled aggregate peak477.0MiB;11.1s;completed
```

Native slot was coordinated with root before this covering run. Earlier pure
preparation overlapped a separately supervised numeric diagnostic: root was
immediately informed that guardian edits had already occurred when a hold request
arrived; root subsequently confirmed that diagnostic ended and released the slot.
No native/model probes were run by this implementer before release.

Final native32-window inference: tokenize0.4675s, infer1.0259s, session1.5074s;
103518B token page /260352B inference response. Terminal11-window page0.4870s.
Maximum round1 native samples: task451395584B, aggregate500154368B. Deliberate
invalid-profile refusal peak47300608B task/96337920B aggregate,0.1120s. No
unexpected native pressure/admission/RSS/deadline refusals occurred and no guards
or limits were increased. Controlled expiry and pressure refusal tests passed.

Pinned Ruff check: `All checks passed!`; format check: `6 files already formatted`;
`git diff --check` clean. Six scoped source/test files changed in this fix round.
No remaining scoped failures. Previously documented active-stage preemption and
durable-publication coverage limitations remain later integration work.
