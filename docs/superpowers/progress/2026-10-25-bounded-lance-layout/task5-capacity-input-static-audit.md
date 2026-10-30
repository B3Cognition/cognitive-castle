# Task5 capacity-input static audit

Result: the saved inventory supplies useful component counts, but not a full expanded-corpus capacity permit. Missing inputs must yield qualification_required. This was a read-only audit of existing reports/metadata/code descriptions: no DB/source queries, inventory refresh, engines, tests, fixtures, product edits or Task5 implementation.

## Evidence boundary

fresh-live/result.json records187 complete summaries/nine anchors,438 total attempts, no partial/failure;40 attempts refreshed LIVE only. Eight histories passed stat/entry checks; their content hashes were not revalidated. source_currentness=last_observed_only, cross_store_atomic_snapshot=false, discovery=not_established. Nine roster main files have distinct recorded dev/ino pairs; that does not prove disjoint canonical content. Older LIVE/partial results must not be added to the replacement LIVE observation.

## Recorded components

| Component | Historical slots0–7 | LIVE slot8 | Permitted use/limitation |
| --- | ---: | ---: | --- |
| Stored chunks |523042|15652|Physical source chunk counts, not distinct global canonical IDs.|
| Chunk text bytes / maximum |650527116 /8192|11412547 /8192|Payload input; not Lance retained or indexed bytes.|
| Provenance bytes / maximum |112917338 /243|5927979 /386|Serialization input; JSON/columnar/index overhead still needed.|
| History owners / indexed attempts |483895 /483895|not present|These are corresponding lineage representations, not two owner populations.|
| Membership JSON elements |493609|15652 total|Historical max180 applies only to JSON form; LIVE max8 per receipt.|
| Relational membership rows |29433|not present|Seven present schemas; eight relational owners. Do not use JSON max180 as full-owner maximum.|
| Original LIVE receipts |0|15436|Require both LIVE owner and original receipt rows; history owners need no original LIVE receipt.|
| History metadata / columns bytes |222141532 /142777770|not present|Max658/371B respectively: each unchanged nonempty field fits one8192B page; at most967790 such pages for these historical rows, before scopes/descriptors.|
| Coverage rows / value bytes |0|449359 /121923502|Known AUDIT inputs; not canonical user chunks.|

Observed membership representations sum538694 (493609+29433+15652), matching the sum of source chunk counts. This arithmetic does not prove referential equality, cross-store uniqueness or lack of missing canonical IDs. Membership-form/reverse-lineage checks help but do not replace original source/canonical reconciliation. History aliases483895 and indexed attempts483895 refer to existing history owners and also become separate AUDIT units under the documented mapping; do not mistake either role for additional canonical user records.

The recorded mapping has1434687 AUDIT units:483895 attempts+483895 aliases+1 gap-resolution+854 checkpoints+449359 coverage+14975 chunk-scope rows+854 generation-scope rows+854 capture-source rows. With483895 history and15436 LIVE owners, this is1934018 pre-coalescing source units, not a frozen destination owner count. Practical AUDIT coalescing and new discovery preservation change the projection and must be counted explicitly. The theoretical240916472741888B repeated-hash work in the outcome note is IO-work arithmetic, not disk to reserve.

## Required checklist before freezing capacity

- [ ] Reconcile the original519641-row native boundary with these SQLite histories, remaining native occurrences, aliases and canonical IDs. Do not add519641 to483895 or infer35746 remaining by subtraction without lineage evidence. Determine the protected, current input set and LIVE delta without claiming a cross-store snapshot from this result.
- [ ] Obtain per-owner finalized planning totals/distributions for all fields, membership representations and original LIVE receipts, including scopes/descriptors, UTF8 page boundaries and JSON escaping. Existing sums/maxima cannot determine per-owner rounding, maximum complete owner expansion, packing or batch count. The known52MiB gate is one admitted fixture, not a corpus-wide maximum.
- [ ] Project physical rows by actual row kinds: unique newly stored canonical rows + membership pages + field pages + owner markers + original LIVE receipts + batch receipts. Dedup savings require verified IDs/provenance/exposure; otherwise retain conservative no-reuse charges. Count actual fixed packing and post-Task4 AUDIT grouping. Do not substitute source rows for expanded physical rows.
- [ ] Size ID claims and routes against every projected unique physical ID, including pages/owners/receipts and outstanding reserved-but-unwritten IDs. Add authoritative registry/epoch/partition rows, bounded owner spans/homes, jobs/pending/ACK/reference records, rebuild pages/state, indexes and the immutable qualification artifact. Claims and routes are separate metadata populations, not a single copy of user chunks. Their measured SQLite byte/index/journal growth is still missing.
- [ ] Resolve omitted/current LIVE scope:74 pending sources,14933696977 pending observed bytes,1 accounting-incomplete source,667 unscoped chunks and8 workspace-conflict sources remain. Capture observed29789691369/processed14855994392 bytes are transcript accounting, not future canonical-byte or disk estimates. Discovery is unestablished; no discovery_dirs/discovery_roots row/serialized-byte totals appear in these19 LIVE queries. Unsupported/tool/internal/oversized omissions remain explicit rather than silently excluded from completion.
- [ ] Build the physical retention ledger from the union of protected source/rollback/archive/generation roots, counting each physical file once and avoiding parent/subtree double counting. Distinct retained copies cost space even when semantically duplicate. Recorded historical main-file logical total is3117842432B; summed historical used-page bytes3117752320B and LIVE used pages268066816B are SQLite accounting, not allocated filesystem bytes or an all-root ledger. Never add text payload totals again as separate retained copies of those same files. Native archives, original Lance versions/indexes, prior failed destinations, diagnostic trees and current free headroom still need permitted accounting; no current values were obtained here.
- [ ] Freeze and measure one whole lifecycle under reviewed Task1–4 policies: every retained data/index/version/receipt, next output while old output persists, rollback journals, spill/temp/open-unlinked allowance, interrupted/orphan debt and required free headroom. Include no-rewrite reuse/conflict, lost replies, old/new/absent reads, bounded reconstruction, owner-boundary rollover and underestimated-owner refusal. Partition count, maintenance/index outputs, qualified remote fanout, aggregate physical allocation and semantic/vector cost are not established by inventory or tiny Task2 success. Stop on absent input or capacity refusal; no cap/fixture invention or retirement is authorized.

## Source hashes read

Paths are relative to the worktree; inventory paths below are under `.superpowers/sdd/2026-10-24-unified-lance-memory/sqlite-inventory/`.

| Source | SHA256 |
| --- | --- |
| fresh-live/result.json (99166B) |140a16743fce935bf8c9d29011f6851c0f3c276c81e72728a5eabdbe9dd7ec24|
| fresh-live-outcome.md (2600B) |cea5e1bcd7408f0af83973ffd8ceb78124890e3dc23103b7971599190535c310|
| roster.json (6880B) |f84d859f66dfbf2bd4372166f0ea10cca3e9828e0aa8a4b7304398be63583fd3|
| fresh-live/binding.json (3034B) |4792dbfe0b608a80802cf511c7d3b5a36c36b6792c9b1212f91343b3274a110c|
| v3-real-continuation/documentary/sqlite_source_export.py.txt (49147B) |114ae74080085007f217dda5dc369f155653ea1973a5f963a4286df4c0277e78|
| docs/superpowers/plans/2026-10-25-bounded-lance-layout.md (56924B, observed revision) |92d736b5d760582bd76ba5369d28d50d8dc86b35c08bd7ccf7771c4649c95029|
| docs/superpowers/plans/2026-10-24-unified-lance-memory.md (10625B) |bf2be7834117f7e15a547629761a77898ab0768cf436b3389a336d69ad3d657e|
