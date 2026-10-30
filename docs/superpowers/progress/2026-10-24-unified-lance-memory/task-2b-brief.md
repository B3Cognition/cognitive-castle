# Task2b — durable vector and queue primitives

Read this first: requirements for a sequential substep after reviewed Task2a.
Task2c will wire these primitives to exact-publication recovery and background
indexing. Task2 remains incomplete until that integration is reviewed.

Own new modules `semantic_queue.py`, `lance_vector_store.py`,
`semantic_store_worker.py` in cognitive_castle and their focused test files.
Coordinate before changing shared files. No production routes, service/profile
changes, installed checkout, palace data, models or downloads. No subagents.

Use separate private exact/, vectors/, coordination/ children of a trusted
generation directory. No new public path/budget/worker arguments. Native work:
192MiB task/256aggregate, reads2s/writes3s. Queue-only:128/192,2s/3s. Existing
global admission/pressure/guardian cleanup; no host native/model imports. Explicit
tests through safe_brain_tests; fixture children separately supervised. No larger
retry after refusal. No corpus/index qualification claim from these fixtures.

## Vector storage

One explicit versioned Lance schema/dataset with compact semantic-unit rows and
receipt rows. Atomic append publishes units+receipt. Nonblocking private writer
lock, owner/mode/symlink/hardlink/schema validation and read-only no mutation;
match exact-store boundaries. Small bounded projections/caches/batches/readahead/
I/O buffers, no full-corpus materialization or index builds/legacy backend.

Publish a validated token page and matched inference response:<=32units,
<=8distinct canonical sources, stable batch/page key and trusted full scopes.
Publication also supplies the ordered canonical reference set for the ENTIRE
bound input group, even if this page contains units from only its first source.
Rehydrate that full ordered set to recompute input_binding; page unit membership
alone cannot prove a continuation's binding to sources absent from the page.
Use semantic_windows/profile validation. Rehydrate every source from
LanceExactStore(exact_directory).read_sources before publishing; verify immutable
ID/text hash/provenance-derived exposure hash/source length/chunk/absolute offsets
against unit and input binding. Never create absent canonical data on this path.
Exposure hash is exactly unified_memory._exposure on{id,text,provenance}.
Vectors finite normalized384D, cast float32 deterministically; hashes/replay
comparisons bind durable float32 bytes rather than original JSON spelling.
Persist compact source/unit/profile/token-input hashes, exact offsets, scope,
exposure hash and vector. Do not duplicate source text or raw token arrays.
Explicitly acknowledge nonsemantic units, exclude them from ranked candidates.

Receipt IDs separate from unit IDs. Receipt binds profile,input/page binding,
start_window,total_units,next continuation,unitIDs and vector digests. Validate
stored receipt and referenced compact records before replay ack. Identical retry
after restart/lost response returns original receipt; changed batch/page content
conflicts; matching units shared by batches are not duplicated. Stale sources or
corrupt vectors refuse. Bounded receipt lookup supports recovery without models.
Terminal enumeration is not proof prior pages were durably published.

Read-only nearest query: pin dataset version/profile; finite normalized384D query,
limit1..100. Return compact candidate/source IDs, hashes, exposure hashes,
profile/offsets/distance and actual dataset generation.
Generation may be None for a fresh query: open/pin latest once in this worker and
return that version. An explicit expected generation must match or refuse. This
avoids an extra cold status worker; stable publication receipts remain unchanged.
Apply all policy/scope filters BEFORE ranking/limit: explicit prefilter=True,
typed Arrow expressions.
Filter unit kind/profile/nonsemantic plus workspace<=2048B,wing/room<=512B.
allowed_source_hashes=None means trusted full scope;[] means no sources;
validate<=256lowercaseSHA256 hashes. Never interpolate scope text into SQL.
Full scopes come from trusted authoritative registry, not shortened caller data.
Scopes are per source reference, not one shared scope for a group: a bounded
batch may contain records from different workspaces/rooms. Each ordered reference
carries its own scope; bind the complete reference/scopes set into queue and
publication request identity in addition to the semantic input binding.
Generation/profile mismatch refuses; no implicit old-vector compatibility.

## Coordination queue

SQLite holds only references, hashes, profiles, scopes, lane, state, cursors,
receipt IDs and progress; NEVER bodies, token arrays or vectors. Private path
checks and SQLite heap limit in worker only; read creates nothing, writes are
durable transactions. Provide register/select/acknowledge/status/retry primitives.

Register stable batch key with1..8canonical references, profile,new/history lane.
Identical retry idempotent; changed binding conflicts. Future Task2c supplies refs
only after verified exact publication; this low-level queue must not claim its
caller reference alone proves publication. Select fairly:3new pages then1history
page when both lanes have work; progress remaining lane if other empty. Persist
scheduling state. Inflight groups survive restart and can replay last receipt.

Only contiguous acknowledged windows completing total_units for the complete
bound input set mark the group complete. Validate start,count,total,next cursor,
profile/input binding; identical ack idempotent, gap/changed totals/binding
conflict. Unavailable/crashed steps retain last durable position. Ack consumes a
verified durable vector-publication receipt from trusted coordinator, never a
merely computed model response. Report pending/inflight/complete/refused counts
and positions honestly; counters do not certify corpus-wide coverage.

## Worker and verification

Fixed queue/vector operation allowlist, strict bounded512KiB frames/unknown-key
and duplicate-key rejection, trusted absolute checkout bootstrap, supervisor
chain verified before storage. Queue phase denies native/model imports; vector
phase denies models/providers/Pandas. Both deny network and children. Internal
Task2c composes them under SemanticSession's shared5s deadline using stricter
store budgets; don't implement another scheduler or change that runtime now.

TDD: queue registration/conflict/restart/fairness/contiguous ack; vector
create/append/reopen/replay/corruption/float32 stability/stale-source rejection;
commit followed by lost response and receipt recovery; shared units across
batches; nonsemantic markers; read-only/private paths/unsupervised refusals.
Actual guarded Lance query fixtures prove prefilter selects an authorized
lower-ranked vector when unauthorized ones are closer, empty grants deny all,
full workspace/wing/room filters work and SQL-looking strings remain literals.
Test profile/generation mismatch, no host native imports and descendant cleanup.
Use deterministic valid unit fixtures and normalized synthetic vectors; no model
inference needed here. Coordinate native slot with root before tests.

Write full commands/red-green results/resources/refusals/interfaces/limits/files
to task-2b-report.md. Pinned Ruff is ~/.echelon/venv/bin/ruff. Focus covering tests,
no unrelated reruns. Self-review, commit only scoped files, no push; return brief
status/commit/test summary/concerns/report path.
