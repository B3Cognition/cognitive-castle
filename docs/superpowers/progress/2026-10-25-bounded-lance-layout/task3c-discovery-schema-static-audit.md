# Task3c discovery preservation prerequisite

The current exporter admits 15 source tables and refuses these two known LIVE tables at `sqlite_source_export.py:245–262`. The smallest preservation extension is two explicitly supported AUDIT tables, with original rowid evidence, using the existing owner/cursor/packing domains. This audit grants no implementation or native execution and does not complete Task3c.

Authoritative definitions are `memory_discovery.py:23–34`; writes are at lines 118–197. `_ensure` runs inside `MemoryStore._connect(True)`, whose transaction begins at `fast_memory.py:157` and commits at line 181. Thus the writer creates the pair and their index together. Old snapshots may lack both. Admit the exact pair when present; a partial pair is not a writer-produced completed schema. The already recorded LIVE schema corroborates the exact shapes and three index signatures (`sqlite-inventory/live-inventory/live_schema.py:2–24`); that inventory did not count either table's rows.

| Table | Columns in original ordinal order | Primary key / export order |
|---|---|---|
| discovery_dirs | root_key TEXT NOT NULL; path TEXT NOT NULL; cursor TEXT NOT NULL; identity TEXT nullable; done INTEGER NOT NULL | (root_key, path), BINARY ascending |
| discovery_roots | root_key TEXT PRIMARY KEY; path TEXT NOT NULL; format TEXT NOT NULL; sweep INTEGER NOT NULL; completed_sweeps INTEGER NOT NULL; complete_ns INTEGER nullable; errors INTEGER NOT NULL | root_key, BINARY ascending |

All declared defaults are NULL/no explicit default. Preserve the actual SQLite root_key shape: discovery_roots' TEXT primary key has table_info notnull=0, not 1. The two automatic PK indexes have a non-key rowid suffix. `discovery_pending` is the ordinary, non-partial index on discovery_dirs(root_key, done), BINARY ascending, with rowid suffix. Reuse the recorded fixed DDL/shape expectations for these two names rather than broadening unknown-table admission or changing the old 15-table policy. WITHOUT ROWID or alternate key/collation/column/type/null/default shapes are not the known schema.

Mapping:

- Add the declared columns and keys to TABLES. They become two additional AUDIT_TABLES entries, after coverage_observations and before history_aliases. Use the existing keyset traversal at `sqlite_source_export.py:366–395,918–930`: dirs key is `[root_key,path]`; roots key is `[root_key]`. Do not use OFFSET, rowid, or discovery cursor contents as the exporter cursor.
- One row becomes one AUDIT owner, with key `[table, _json(original_primary_key)]`, `original_table`, `original_key`, `original_version`, all original columns in `row`, and the existing source/manifest binding. Keep owner_key exactly `AUDIT:` + SHA256(_json(["audit", key])) and bulk.owner_id(owner_key, source_binding) (`sqlite_source_export.py:562–627`). Do not introduce canonical transcript members or a LIVE replay receipt.
- Add an integer `original_rowid` to each of these two new AUDIT descriptors, read from that exact original row. It is evidence, not a replacement key or owner-ID input. Preserve the signed SQLite integer exactly; do not renumber from export order. This is necessary for discovery_dirs: the writer chooses the next pending directory by `ORDER BY rowid LIMIT 1` (`memory_discovery.py:125`). A later reconstruction must insert the recorded rowid or otherwise prove identical pending-directory order. PK-order reconstruction alone is insufficient. Roots also retain their original implicit row identity; their current status traversal itself uses root_key order (line 214).
- Preserve TEXT exactly, including empty cursor, Unicode, escapes, and opaque identity; preserve integer and NULL values without normalization. Existing streaming `value/object/raw` at lines 278–337 distinguish empty TEXT from NULL. BLOB, null/non-string key, oversize-key and deadline/refusal handling remain fail-closed. The schema does not enforce all writer value restrictions: do not silently repair surprising values or treat their preservation as valid coverage.
- Audit owners have zero members/text, no metadata_id and no LIVE receipt, empty metadata/columns/scopes fields, descriptor pages and the ordinary final owner marker. Increment audit_owners only on admitted finalization (`sqlite_source_export.py:1020–1050`); discovery done/errors do not increment gaps, pending_stages or canonical members. Exact physical expansion also includes descriptor pages and interval batch receipts; source row count is not that expansion.

Writer semantics to retain: root_key is SHA256(absolute path + NUL + format), with format claude/codex (`memory_capture.py:28–29`, `memory_discovery.py:99–110`). Paths are bounded by the writer at 2048 UTF-8 bytes, but that is not a SQL constraint or an observed row-size proof. identity is the opaque `device:inode:mtime_ns` text; an identity change resets directory enumeration. done=-1 records a failed unfinished page, done=0 remains pending, done=1 is exhausted for that sweep. Failed pages preserve their cursor; new sweeps delete/reseed directory rows. completed_sweeps and complete_ns are historical observations, not present-day whole-corpus completeness. Preserve even the writer's initial sweep increments exactly; no counter correction or new live discovery is part of export.

Compatibility: FORMAT, PACKING, PHASES and all cursor fields stay unchanged (`sqlite_export_codec.py:16–34,176–239`). Old snapshots lacking the pair emit byte-identical old units and accept their existing pending cursors. A source containing these tables previously refused at open, so it has no legitimately completed exporter frontier past the new audit entries to adopt. A snapshot/schema change requires its own manifest/source binding; never resume a changed snapshot using an old cursor or rewrite an old terminal cursor. Existing history lineage, staged-row exclusions, original IDs, old audit descriptors and pending ACK behavior remain unchanged. Retain original DBs/archives.

Required later checks, under separately authorized test scope:

1. Exact optional-pair schema, PK order, null/default/type/index signatures; reject a partial pair, WITHOUT ROWID, changed shapes and unrelated unknown tables. Keep old-schema fixtures unchanged.
2. Original-to-AUDIT equality for both tables, including NULL versus empty text, Unicode/escapes, done=-1/0/1, incomplete/error and completed sweeps, complete_ns=NULL, and exact signed rowid. No fabricated canonical member or coverage claim.
3. A disposable SQLite fixture with composite-key order deliberately different from rowid order: export/reconstruct the original rowids and prove the next pending directory matches the original ORDER BY rowid behavior. Do not infer this from serialized PK order.
4. Multi-row keyset boundaries, empty tables, interrupted descriptor-page/finalization resume, identical retry, no double counts, and old v1 pending/history result compatibility. Check exact source binding/owner IDs and unchanged old descriptors.
5. Existing source guards, unchanged file identities/hash, no writes/sidecars, UTF-8 page/frame bounds, and refusal clears entries/finalizations/progress. Later capacity evidence must supply discovery row counts and descriptor-byte bounds; the current 19-query inventory supplies neither.

Read-only source bindings for this audit (SHA256):

| File | SHA256 |
|---|---|
| memory_discovery.py | 825783a397fae41be4c35d9211c20e508360daef304401a2791b4dd3f8230973 |
| memory_capture.py | 3709bb05f14f5042be666be63e5d025d820683307783aaf2ffc4696fa76c2498 |
| fast_memory.py | 7a251a009afcd584b1401984a267a14918348ae5d9316d1693a1cbe324ca23f1 |
| sqlite_source_export.py | 3552e24c672f6a39d2bbba180c4143972d6f52785979de38a1ad140371abffc1 |
| sqlite_export_codec.py | 00106cacf558dddc379f5ee19d459e79390358620eadfe218ecff5c51bf2b8cd |
| historical_export_evidence.py | 32be251789c60818c1df8e0401d1081f63149c89d5ff2e97080fe91376af6740 |
| live-inventory/live_schema.py | d83a0fcdfc628482bf03f973e199e9420a4e24b8718c5cd23ab00bdceffdccbc |
| live-inventory/schema-evidence.json | 1f92a50728994ca493c040e0cd2f7cecda01488f2c50e9a796e103d8ea8a377c |

Only static file reads, AST literal extraction and hashes were used. No DB query, inventory refresh, engine/test import, native execution, capture, or product edit occurred.
