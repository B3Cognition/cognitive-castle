# Task4 capture publication journal — BASE03790d7

Implement the approved explicit-ID capture boundary without changing the active
canonical backend. Existing registered Lance writer integration remains next.

1. Test actual pending metadata exists BEFORE remember; no original body in the
   journal. Test crashes before append and after durable append/lost response,
   changed hints/rotation, receipt refusal/corruption, bounded recovery and exact
   scope idempotence. Watch the smallest current-code failure first.
2. Add the existing backend's explicit bounded receipt-read operation, returning
   `{status,digest,receipt}` verified from the committed receipt and original
   chunks. Future registered Lance uses the same receipt boundary, not fallback.
3. Add a body-free immutable intent journal in capture coordination. Reserve the
   source-generation workspace before append; failure may conservatively retain
   a reservation, never loosen it or silently move old scope. Persist expected
   IDs/request digest/receipt, source/generation/record offset and frozen scope.
   Expected metadata is not evidence. Only actual append receipt or fresh backend
   receipt read authorizes applying exact ID mappings. The applied marker is a
   coordination acknowledgement, never cached canonical proof.
4. Prepare callback runs before remember; confirmation callback before checkpoint.
   Recovery reads at most two pending intents, leaves absent receipts pending and
   reports source coverage incomplete. Resource/backend refusal stops this tick.
   Old after_rowid attempts recover through their explicit old branch only; new
   attempts never read a rowid or infer candidate IDs from the SQLite body table.
5. Run new SQL fixture tests and original74 contracts with original20s256MiB
   guarded per-suite ceiling, remotely. No local native/model/palace access.
   Preserve original250ms slice/read2s/write3s/resource caps. Native Lance and full
   corpus/activation remain unqualified by this SQLite functional evidence.
6. Audit source hashes/XML, lint, ledger, commit and push feature fork. No B3 merge
   or installation before the complete reviewed cutover.
