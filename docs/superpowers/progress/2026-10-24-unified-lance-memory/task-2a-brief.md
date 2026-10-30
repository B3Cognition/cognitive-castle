# Task2a — pinned staged semantic runtime

Read this first: it is your requirements. This is only the runtime/windowing
portion of Task2; queue/vector publication is the next substep. Work in the
existing design/semantic-preservation worktree; base3208aea.

## Own files

Create focused modules `cognitive_castle/semantic_profile.py`,
`cognitive_castle/semantic_windows.py`, `cognitive_castle/semantic_worker.py`,
`cognitive_castle/semantic_runtime.py` and corresponding explicitly named tests.
Do not change existing dispatch, memory_runtime budgets, exact store, capture,
services or installed checkout. Coordinate if another file is essential.

## Profile and worker contract

Package the same qualified pinned model/tokenizer/pooling contract, including
all six exact file sizes and hashes, from the existing private diagnostic:
`/Users/ladislavbihari/myWorks/cognitive-castle-history-qualification/.superpowers/sdd/2026-10-24-unified-memory/semantic-onnx-probe.py`
and its run-semantic-onnx-gate.py runner. Those are reference evidence, not new
public entry points. Trusted existing artifact manifest is:
`/Users/ladislavbihari/.castle/backups/durable-memory-20261024/relocation/semantic-models/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/profile.json`.
Do not hardcode this user's home into product code; accept the artifact location
only from trusted host preparation, never from public tool arguments. No downloads.
Model is sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2,
revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42, qint8_arm64 ONNX,
384dim, attention-mask mean then L2 normalization,128tokens, no lowercasing.
Profile identity binds weights/tokenizer/config hashes plus windowing version,
pooling,normalization and effective CPU inference contract.

Provide one fixed worker executable with tokenize/infer operation allowlist and
512KiB maximum request/response frames, trusted checkout bootstrap, existing
guardian/session-chain verification before artifacts/native imports. Tokenizer
process imports Tokenizers only (no NumPy/ORT); infer imports NumPy/ORT only
(no Tokenizers). Deny networking, children, Torch/ST, providers and optional
Pandas/Lance. Verify pinned hashes before runtime initialization. Artifacts may
be existing HuggingFace cache symlinks only if resolved target is an owned regular
file, not group/world writable, with the verified expected hash; no mutable
untrusted profile override. Validate finite normalized vectors, dimensions,
token shapes/types/vocab/masks and exact handoff identity before returning.
Default ORT graph optimizations retained, single CPU thread, no CPU arena/memory
pattern, telemetry disabled, no permanent process. No new language/model choice.

## Windows and bindings

Input: at most8 full validated CanonicalRecord sources per request, each<=8192B.
Expected source text hash must agree with exact text/provenance before tokenizing.
Tokenize with the pinned tokenizer and use128-token windows including its actual
special tokens,32 content-token overlap. Use native overflow offsets or equivalent
exact token slicing; never re-encode decoded token text or assume XLMR token IDs.
Retain original exact character offsets, token span and canonical chunk offset.
Every content token must appear in a window; first/last coverage must include
leading/trailing source positions and NUL/Unicode inputs must remain unchanged.
All-whitespace/nonsemantic input must have explicit complete handling, not be
silently missing. Identity of each semantic unit binds canonical ID, source text
hash, profile, token window and exact offsets/input token hash.

Return at most32 windows per page with deterministic continuation binding the
entire input set/order/hashes/profile and next window. A caller must not be able
to resume different text under an old continuation. Output declares total units,
next continuation and completion; a partial page is never full coverage. Do not
store canonical text in any new SQLite location. Infer one window at a time to
bound activations while reusing a session within that short-lived worker.

## Trusted coordinator and fixed limits

Use existing memory_runtime admission/priority/supervision primitives, not a
second scheduler. Provide an internal reusable session/coordinator so later
retrieval can share its same admission and absolute deadline across tokenizer,
inference and Lance stages. Fixed512MiB task /640MiB aggregate and5s total,
including admission/validation/startup. No caller-specified increases. Early
deadline/refusal retains explicit unavailable reason; no larger retry. Interactive
intent/yield behavior mirrors current runtime; background never waits ahead of
an interactive waiter. Cleanup and admission release on all failure paths.
No model/native imports in the trusted host or test host. This remains inactive
until later integrated qualification and cutover; existing production unchanged.

## Tests/evidence

Use TDD and scripts/safe_brain_tests.py for explicit test files; supervise every
native/model operation. Pure tests cover identity validation, stale continuation,
duplicate/malformed frames, no host native imports and shared-deadline/refusal.
Real offline fixture tests use the already pinned assets under the approved
diagnostic profile, no palace data. Prove Czech/German/Spanish paraphrase rankings
against the existing eight-document fixture; Unicode and long-tail window paging
must cover the source without silent truncation; invalid profile and unsupervised
invocation must refuse before model load; process cleanup must be observable.
Measure larger returned pages and record peak task/aggregate RSS and elapsed,
including every pressure/admission/resource refusal. Do not disable capture or
relax guards for tests. Native operations sequential; coordinate with root first.
Existing test-only admission backoff can be reused, never add it to production.
Run covering tests after fixes, not repeated broad suites. Pinned Ruff executable
is /Users/ladislavbihari/.echelon/venv/bin/ruff. Report test commands/results, limits
and implementation interfaces. Commit only scoped product/test files. No push.

The primary Tokenizers API documents overflow windows and exact string offsets:
https://huggingface.co/docs/tokenizers/v0.20.3/en/api/encoding . Installed0.22.2
must be verified by actual guarded behavior rather than current rc documentation.
