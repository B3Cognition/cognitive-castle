# Task4 capture journal implemented; foreground writer remains next

Capture journal: current candidate after03790d7, verified by94 functional cases +282 source contracts and actual fair-recovery/protected-export scope40956192720. Outer plan remains
`docs/superpowers/plans/2026-10-24-unified-lance-memory.md`, Task4.

## Required behavior

Ordinary remember and capture must publish through registered Lance authority;
SQLite holds body-free coordination, checkpoints and scope metadata only.
`LayoutSemanticSession` already hydrates registered published originals and
validates vector publication/receipt recovery. No public route is activated.

The write-ahead capture journal is implemented and wired. It reserves body-free
request/receipt/position/scope metadata before append; actual append confirmation
or fresh canonical receipt proof applies exact ID maps atomically. New attempts
never use rowid. Legacy pending-watermark recovery remains explicit. Fair recovery
probes at most2 with a durable keyset cursor; missing old receipts stay pending
without starving fresh capture. NUL byte reads, unknown states, actual second-ID
SQL rollback, first-Claude crash, changed hints/rotation and old unmapped data
all have evidence. The current canonical backend remains SQLite until the
registered Lance foreground writer is implemented; no fallback or cutover.

All journal metadata remains retained; add it and its indexes to Task5's real
capacity audit. Do not remove applied entries without proving immutable request
replay/scope recovery against canonical owner evidence. No pruning is authorized.

## Foreground writer prerequisite

Registered layout preparation currently validates immutable historical source
registrations. Ordinary request publication still lacks its explicit registered
foreground request domain. Do not fake a SQLite/native source descriptor, create
a second canonical body store, call unregistered flat remember, or synthesize
proofs. Define the foreground immutable request contract and its reservation,
Fresh/cold replay/group proof/publication lifecycle against the existing guarded
partition authority before connecting ordinary routes.

## Verification

Receipt mismatch, observer refusal/mutation and checkpoint replay are covered by
the new candidate. Retain the original capture/ingest/scope tests, especially:
- first Claude record crash after actual remember;
- crash after ingest before mapping, then changed host hint;
- old unmapped chunks never assigned from a later hint;
- metadata/workspace conflict and source generation replacement.

New foreground native qualification must be one frozen synthetic macOS scope,
with actual registered proofs and explicit interruption points. Original limits:
exact/vector192/256MiB; queue128/192MiB, heap16MiB; read2s/write3s and absolute
session5s. No local native/model/user-palace operation, cap changes or activation.
Full corpus capacity/reconciliation and reviewed B3 cutover remain outstanding.
