# Existing persisted replay: static protocol assessment

Design-only review; no implementation, engine, test, source DB, or runtime action. This does not revise or pass the currently failed two-replay qualification.

The coordinator unconditionally invokes import_batch twice. In the existing-receipt branch, the first invocation already reopens the dataset under its writer lock, executes _verify_batch (including complete owner validation for published owners), and checks the regenerated digest, source binding and exact expected ID set before returning. Repeating that identical persisted proof is not independently required to distinguish a completed append from a lost response. Conversely, a fresh append validates pending in-memory rows and writes them: it still needs an independently reopened persisted replay before ACK.

A future private worker-established outcome can distinguish those two paths without weakening their content checks. It must be generated only after the existing-receipt proof completes, carry the same exact compact receipt, and bind destination/generation, source binding and observed dataset version. It cannot be selected by the caller, queue state, mere receipt existence, a persisted proof flag, or partial/cached proof. Public import_batch behavior need not change.

Required edges:

- An unknown append outcome, timeout, lost IPC or crash produces no successful proof witness. Pending survives; the next tick regenerates source and validates the persisted batch again.
- Missing, corrupt, conflicting, duplicate or unexpected receipt/ID content refuses; it cannot qualify the shortcut. A staging-only batch proves its interval and cannot claim owner publication/exposure.
- A fresh append followed by replay must obtain the existing-verified outcome on that replay, not silently permit another fresh append result.
- The returned proof version must govern subsequent owner observation. Current bulk_owner supports an expected version and fails stale, but the coordinator presently omits that argument. Without version binding, a later append/index update can make owner lookup report a version that was never fully proved. A conservative future protocol rejects that change and retries, or separately defines immutable-version reads.
- Keep regenerated pending equality, owner-manifest equality, original live receipt verification, transactional current-pending/cursor validation and exact verified-summary ACK. Never retain the ephemeral proof witness across ticks.
- Two immediate read proofs do not independently establish stronger hardware/power-loss durability than the underlying committed storage operation.

Recommendation: the conditional persisted-proof protocol is a reasonable architectural correction after timing attribution, subject to implementation review and targeted crash/race/corruption qualification. It must be approved as a new protocol, not retroactively used to label the failed old gate successful.

Source hashes read during review:
- cognitive_castle/migration_coordinator.py: e41676c50520ca8337d52ff17fc2bb4657ce7d49d8df6037a8c29c40fbe3feff
- cognitive_castle/bulk_exact_store.py: fecb8c50c09a7b5fe7340cc1d40330c456607eb256f19198100f7887621dc959
- cognitive_castle/lance_exact_store.py: 79282d84e5368a9745be85b43de4525460e933d0b5dfb2e6c9d21ff0c6c39787
- cognitive_castle/migration_codec.py: ba3536bb5b667a74ce017b91d32d6717955d2756328036a13c308cf81fd23e0f
- cognitive_castle/semantic_queue.py: 98d59b17ad11daefeaaaf48cc03a9fa0b0d416b680cc534025701721afa3758b

## Compact private outcome proposal

Keep public `import_batch` and its compact receipt unchanged. A private operation returns one closed tagged union, selected solely by the trusted worker's actual branch:

```text
FreshAppend { receipt: ExactCompactReceipt }
ExistingVerified {
  receipt: ExactCompactReceipt,
  witness: {
    destination: { canonical_generation_path, parent_dev_ino, directory_dev_ino },
    source_binding, batch_id, batch_digest,
    expected_id_set_digest, dataset_version
  }
}
```

`ExistingVerified` is constructed only after the complete existing-receipt proof, regenerated batch digest/source checks and exact expected-ID-set equality succeed under the writer lock. Its version comes from that same opened dataset. The ID-set digest uses a fixed domain-separated canonical encoding of sorted unique IDs after equality has been checked; a digest comparison does not replace that equality or any row/owner proof. Destination identity comes from the bound registration/qualification and verified filesystem identity. Validate the exact transport shape and field types; reject unknown tags, extra fields or missing bindings. No caller-selected outcome, generic trusted flag, persisted witness, or cross-tick reuse is introduced.

The coordinator checks the exact receipt and all witness bindings against the regenerated pending interval. `FreshAppend` requires a later reopened call returning `ExistingVerified`; an already verified existing batch needs no redundant second proof. For every finalized owner, use `bulk_owner(..., version=witness.dataset_version)`, preserve exact manifest and original live receipt checks, then perform the existing atomic pending/cursor/summary ACK. A version change refuses as stale; it cannot be relabeled as proof of the new version. This retains the existing storage-generation immutability/admission assumptions and does not claim a cross-store transaction.

Focused qualification cases:

- Fresh append → independent reopened existing proof → owner/live checks → one ACK; fresh result alone cannot ACK.
- Lost append response or crash before ACK → regenerated identical pending → one complete existing proof; crash/timeout during proof yields no witness and retains pending.
- Missing/partial/corrupt receipt, changed bytes, duplicate/unexpected/missing IDs, wrong digest/source/owner exposure → refuse without witness; unchanged public API responses remain compatible.
- Wrong destination/generation/inode, batch identity, witness version or malformed/extra transport fields → refuse; caller input cannot request the verified tag.
- Concurrent append/index update between proof and owner read → stale; changed pending/cursor before ACK → transactional conflict. A repeated identical ACK remains idempotent.
- Staging-only interval verifies its exact persisted batch and advances staging only; it cannot publish an owner. Multiple owners and live receipts retain every original check, all tied to the verified version where the API supports it.

This is a compact proposal for the next protocol review, not authorization to implement or reinterpret the failed current qualification.
