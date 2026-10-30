# Task 3c: bounded index next options

2026-10-25; **source diagnosis only**. No settings changed, native run, implementation or next experiment prepared. The preserved 262K refusal remains an actual 192 MiB task-RSS gate; it does not establish which allocation caused the peak. Root must read these findings before deciding further work.

## A supported spill-pool path exists; whole-process fit is unproven

Pin: official Lance 4.0.1 commit `5924c97123a25a3e3d500701ef3f158c01f6cd4b`, whose Python dataset wrapper matches installed bytes. Initial scalar training projects only values plus row IDs, requests ordering by values, and executes with `LanceExecutionOptions {use_spilling:true,..Default::default()}`. Thus bounded input Arrow batches do not bound the sorting stage, but a real spill-aware execution path already exists. [Training path, lines 113–148](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/rust/lance/src/index/scalar.rs#L113).

The exact native controls are:

| Control | Verified semantics |
|---|---|
| `LANCE_MEM_POOL_SIZE` | Unsigned integer **bytes**; default 100 MiB. Used by `FairSpillPool` when spilling is enabled. Reducing this reservation budget is an existing supported configuration path, not a guardian-cap increase. |
| `LANCE_MAX_TEMP_DIRECTORY_SIZE` | Unsigned integer bytes; default 100 GiB. Pinned DataFusion52.5.0 refines the name: shared tracked spill bytes per DiskManager across its directories, updated after writes; not a hard file or whole diagnostic-tree limit. |
| `LANCE_BYPASS_SPILLING` | Its **presence**, even with text `false`, disables spilling. Do not enable it as a memory fix. |

These values are resolved when execution contexts are selected/created; context cache keys include the resolved pool/spill settings. The Python BTREE API does not expose these as per-call parameters. No private spill-directory parameter is wired here. [Native options/context, lines 288–403](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/rust/lance-datafusion/src/exec.rs#L288).

This is evidence of an available **sort-reservation/spill control**, not a claim that all native allocations obey it. Imports, scan/decode/encoder buffers, caches, lookup statistics and allocations outside that pool still consume RSS. Multiple contexts/operators and temporary output need accounting. Lower reservations may trade RAM for spill I/O, failure or deadlines; neither 192/256 MiB nor 2/3 s becomes negotiable. Spill storage must be private, accounted and cleaned up; existing fixture-only disk inventory cannot silently omit OS temporary files. The failed receipt did not record resolved environment/pool/spill settings, so do not assert that its process actually used the default 100 MiB or had spilling enabled. No value is selected or applied in this note.

## What the BTREE API can and cannot constrain

Python's `"BTREE"` binding constructs scalar parameters without parsing generic memory/worker kwargs. `memory_limit` and `num_workers` are parsed only in the INVERTED/FTS branch. Do not pass guessed BTREE kwargs and interpret a non-error as enforcement. Public `IndexConfig(index_type="btree",parameters=...)` carries supported typed BTREE parameters, but those are `zone_size` and `range_id`, not a total-memory cap. Python Session controls caches only. [Binding branches, lines 1925–2022](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/python/src/dataset.rs#L1925), [session constructor](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/python/src/session.rs#L25).

`zone_size` controls page/chunk rows (default 4,096), not upstream sort reservations. Training streams sorted batches but retains one statistics entry per page before writing lookup metadata, so it is not constant total memory. `range_id` requires externally globally ordered, nonoverlapping value ranges; it adds partition/sort/merge obligations, not an automatic bounded sorter. Whole-index update merges sorted existing entries with new sorted data using `SortPreservingMergeExec` with spilling enabled, then writes replacement pages; it is legitimate derived replacement, not retained independent BTREE query segments. [BTREE merge, lines 1298–1348; training, 1818–1900; parameters, 2503–2530](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/rust/lance-index/src/scalar/btree.rs#L1298).

**Decision boundary:** there is a source-supported internal reservation/spill-budget route worth root's review before redesign. There is currently **no demonstrated full 192 MiB process-bounded 262K BTREE path**, no supported BTREE Python `memory_limit` argument, and no proof of million-row readiness. The single-UUID scalar query behavior already excludes treating independently published same-name BTREE fragments as a qualified workaround. This note authorizes no tuning, retry or native plan.

## Minimal metadata-only fallback if the supported route cannot qualify

SQLite may hold only an ID→Lance location index: original ID, dataset identity/generation/version, fragment ID, physical row offset and binding/check hashes. It must retain multiple physical locations or an explicit duplicate condition rather than silently overwrite duplicate IDs. All canonical text, provenance JSON, pages, owner manifests and durable receipts stay in Lance. A bounded metadata lookup would hydrate a small projected selection through the public fragment-local `LanceFragment.take`, verify exact ID/schema/content/provenance/owner visibility against Lance, and retain trusted exposure checks. No unbounded global scan or SQLite text fallback. [Public fragment take, lines 504–509](https://github.com/lance-format/lance/blob/5924c97123a25a3e3d500701ef3f158c01f6cd4b/python/python/lance/fragment.py#L504).

That alternative adds three concrete obligations:

- **Append/publication:** SQLite and Lance have no shared atomic commit. Mapping must never expose uncommitted rows; after a committed Lance batch but missing mapping, reads need an explicit incomplete/stale result or a strictly bounded unmapped tail. Do not acknowledge source checkpoints from a prepared mapping. Derive actual fragment/offset assignments from committed bounded output, not assumed writer geometry.
- **Read/staleness:** bind mapping generation and pinned Lance version; validate the fetched ID and canonical proof. Compaction, deletion, remapping and dataset replacement invalidate physical pointers; appends alone do not make pointers universally stable. Handle stale/absent metadata explicitly rather than broad-scan fallback.
- **Replay/recovery:** a lost acknowledgement must reconcile the canonical Lance batch/owner receipt before reusing or adding mappings. Resume bounded mapping work without duplicating physical rows, losing duplicate detection or inventing success. Bound and supervise SQLite metadata operations, rebuild/backfill and orphan cleanup under the same admission/RSS/deadline policy.

This is a small fallback interface sketch, not a replacement architecture or implementation plan. It remains unqualified and requires root's decision. Canonical storage remains Lance in either option.
