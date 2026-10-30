# Spec compliance: ❌ Issues found

- Important: accepted scope values can produce a successfully committed publication whose durable receipt cannot subsequently be recovered or replayed (`cognitive_castle/lance_vector_store.py:378`, `:478`; finding below).
- ⚠️ Production outbox/exact-publication coupling, authoritative registry selection, model driver, shared five-second coordination, preemption, public candidate rehydration, historical compatibility, and full-corpus quality remain Task 2c/later gates. This review does not approve those deferred requirements.

## Strengths

- Full ordered canonical references are rehydrated and their input binding verified, including sources absent from the current page (`cognitive_castle/lance_vector_store.py:268`); the two-page, two-source fixture exercises that case (`tests/test_lance_vector_store.py:350`).
- Float32 bytes determine vector digests; absent units and their receipt are appended together, while recovery checks the proof and referenced compact records (`cognitive_castle/lance_vector_store.py:44`, `:373`, `:485`). Lost-response recovery and corruption cases use supervised native fixtures (`tests/test_lance_vector_store.py:195`, `:218`).
- Queue scheduling persists its lane streak, acknowledgement requires contiguous positions and stable group bindings, and status explicitly avoids claiming corpus completeness (`cognitive_castle/semantic_queue.py:250`, `:281`, `:354`).
- Nearest filtering uses typed expressions and explicit prefiltering before ranking/limit; the fixture requires an authorized candidate to win despite closer unauthorized vectors (`cognitive_castle/lance_vector_store.py:513`, `:557`; `tests/test_lance_vector_store.py:243`).
- The worker retains a fixed operation/argument allowlist and checks the guardian chain before storage, then applies stricter phase budgets (`cognitive_castle/semantic_store_worker.py:83`, `:107`, `:140`).

## Important finding

1. **Publication and recovery disagree on the maximum durable proof size.** `cognitive_castle/lance_vector_store.py:378` rejects serialized receipt proofs over 49,152 UTF-8 bytes, but `:478` writes `canonical_json(proof)` without enforcing that bound. `cognitive_castle/semantic_queue.py:31` accepts up to 2,048/512/512 UTF-8 bytes for each workspace/wing/room, and up to eight independently scoped references are permitted. For eight references whose allowed scope strings contain backslashes or quotes at those lengths, JSON escaping consumes **49,152 bytes for scope string contents alone**, before keys, source identities, hashes, page receipt, or compact-record proofs. Such a request can fit the 512 KiB worker frame and publish successfully, yet the next `receipt()` or identical `publish()` returns `corrupt`. A lost response therefore cannot be recovered for an otherwise accepted publication.

   Derive one proof-size bound that covers the accepted reference/scope and page limits, enforce it before committing, and use the same bound for recovery. Preserve the advertised scope limits rather than silently narrowing them. Add a focused guarded publish/reopen/replay case using eight references and maximally escaped valid scopes, plus a check that any intentionally rejected oversized proof leaves no publication behind.

## Checks and scope

- Read the supplied brief, complete implementation report, AGENTS.md, task-reviewer instructions, and full `fba868f..abbd8e8` diff. No source, test, branch, or index changes were made; only this requested review artifact was written.
- Named dependency risk: full-group validation could assume an ordering or identity guarantee absent from exact storage. Checked `LanceExactStore.read_sources` (`cognitive_castle/lance_exact_store.py:322`) and semantic source/page validation (`cognitive_castle/semantic_windows.py:31`, `:81`, `:187`); the reused contracts support the implementation's ordering and binding assumptions.
- Named dependency risk: admission or private-path reuse could admit an unsupervised native host. Checked the reused chain check (`cognitive_castle/semantic_worker.py:74`) and storage supervision/private checks (`cognitive_castle/lance_exact_store.py:30`, `:80`).
- Named dependency risk: the shared frame decoder might not enforce the worker's strict JSON contract. Checked `cognitive_castle/semantic_profile.py:82`; duplicate keys and nonfinite numbers are rejected.
- Named dependency risk: scope validation might already exclude JSON-expanding characters. Checked `cognitive_castle/canonical_records.py:40`; it limits UTF-8 length but permits those characters, confirming the size mismatch by static arithmetic.
- No tests, native/model workers, palace operations, or subagents were run. The reported 31 passing tests and static checks were reviewed as implementer evidence, not independently rerun.

## Task quality: Needs fixes

- The implementation has clear queue/vector/worker boundaries and meaningful guarded fixtures. Fix the accepted-publication/recovery size mismatch before approving Task 2b durability.
