# Private conditional persisted replay: code review

Approved scoped implementation; no blocker found. This is code approval, not a passing revised native qualification or authorization to activate migration. Read the complete product delta, new protocol module and test file, and the author's focused evidence. Independently matched all four candidate hashes and confirmed the three frozen helper/worker/diagnostic hashes remain unchanged.

Candidate bindings:
- cognitive_castle/persisted_replay.py: 58bdfa067bdaf86cad83e4b70aaccf6da4263ba1ff84462ef45f96377ad78189
- cognitive_castle/bulk_exact_store.py: 50b0bd09a4da4c4bbeb9538798673b5e1608e3f24e9549d4a780b84cbc84db81
- cognitive_castle/migration_coordinator.py: 70be1e1c51dc299bf8b6380bc4227a3e4aaf5cfeef421e5bed0160ea20b5c99f
- tests/test_persisted_replay.py: af1346e5e72ddf90050a78e0de07e277fc58073f9504578b8484e560a5a54e76

The base store adds two result hooks whose defaults preserve the original compact receipt. The existing-receipt hook remains inside the writer lock and follows the original complete _verify_batch, regenerated digest/source checks and exact expected-ID-set equality. Only the private qualified subclass creates ExistingVerified, revalidating qualified paths/inodes after proof and taking version from that same opened dataset. FreshAppend contains no witness and does not certify persisted replay. No caller flag or ordinary worker operation selects either outcome.

The closed transport validates exact receipt keys/count types, fixed witness keys, source/batch/digest/ID-set bindings, canonical generation/destination path, private directory identities and positive exact-int dataset version. ID hashing is domain-separated and bounded; it supplements rather than replaces the original full byte/ID proof. Symlinks/replaced identities, boolean numeric fields, unknown tags/fields and late path binding refuse.

The private coordinator accepts one existing full proof or fresh append followed by a separate ExistingVerified result. Two fresh results refuse. It regenerates and compares the same pending interval, pins every owner lookup to the proved version, checks returned version and exact manifest, retains original live receipt checks, and uses the existing transactional pending/cursor/summary ACK. It never saves the witness. The ordinary v1 entry still uses two ordinary imports; its valid results and phase/reason handling remain compatible. A non-dict legacy response now correctly refuses rather than reaching owner/ACK.

Author-recorded39 new plus one affected existing pure case cover strict bindings, branch ordering under a mock writer lock, source/digest/ID/proof refusal, fresh/existing dispatch, unknown/lost replies, pending and inode changes, stale/wrong owner versions/manifests, live receipt failure, expired ACK, staging-only interpretation and ordinary-worker rejection of the private operation. Those are protocol/control-flow evidence, not native durability/performance proof. Reviewer did not rerun tests or import any engine.

The future fixed adapter must explicitly register only its private qualified operation, retain its3-second write classification and source/owner/ACK guards, and pin/charge the additional runtime module. Owner reads must stay qualified to the original destination generation as well as version. Existing admission and immutable-generation assumptions still apply; this code does not create a cross-store transaction. Current failed v1 cold evidence remains failed, and no original artifacts were edited by this review.
