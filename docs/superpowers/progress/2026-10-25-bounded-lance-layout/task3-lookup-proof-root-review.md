# Root-only review: bounded lookup proof reuse

Independent agent review is unavailable after the recorded agent usage-limit error; this is not independent approval.

Actual RED run40226292687 on source3b253189 confirmed receipt_reads6 rather than1; original rows returned unchanged. One selected case failed as expected,0 errors/skips/native,0.8s37.8MiB. XML/log/result retained.

Candidate13df356 changes only _PartitionStore._lookup_rows. Geometry and actual decoded batch proof are lazy local variables. There is one local group for self.pid, bounded by existing MAX_ROUTES; every row still validates schema/content, original route version/hash and actual proof hash. Actual _context_batch validators remain unchanged. Before geometry, uncommitted absent rows, published rows, remote rows and no-intent calls preserve prior decisions. Requested batch receipt still checks geometry and avoids recursive proof. No self field, persisted hash or later-invocation reuse is introduced. _open and separate Fresh/Existing/grouped operations continue their own actual verification.

New14cases retain actual fixture/export/interval/receipt codecs and fake only native lookup, geometry and metadata authority. They cover actual proof read count, full returned row equality, changed receipt and geometry on next call, first/last wrong hash, missing proof row, wrong binding/digest, empty/published/no-intent laziness, receipt recursion and early future-version/row-hash refusal. Existing50facade/27coordinator cases cover remote lifecycle and grouped/ACK behavior.

No runtime guarantee is inferred from static review. GREEN91 and original47-start exact-tail case remain pending; no cap/source/fixture/queue changes are allowed.
